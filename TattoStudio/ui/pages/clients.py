from __future__ import annotations

# ============================================================
# clients.py — Lista de clientes (conexión real a BD + RBAC)
#
# Cambios en esta entrega:
# - Columna "Etiquetas" eliminada → 5 columnas: Cliente, Contacto, Artista, Próxima cita, Estado.
# - Placeholder del buscador actualizado: incluye Instagram.
# - Paginación visual eliminada: se implementa "lista infinita" (lazy load) en scroll.
# - Acciones rápidas con menú contextual: Abrir ficha, Copiar teléfono, Copiar email, Abrir Instagram.
# - Contacto: preferimos Tel + @instagram; si falta IG, se usa email como fallback.
# ============================================================

from typing import List, Dict, Any, Optional
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFrame, QMessageBox, QMenu, QApplication
)

# DB & modelos
from sqlalchemy import asc
from sqlalchemy.orm import Session

from data.db.session import SessionLocal
from data.models.client import Client
from data.models.artist import Artist
from data.models.session_tattoo import TattooSession

# RBAC helpers (UI)
from ui.pages.common import ensure_permission
from services.contracts import get_current_user


class ClientsPage(QWidget):
    crear_cliente = pyqtSignal()
    abrir_cliente = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        # Estado de datos
        self.search_text = ""
        self.order_by = "A–Z"

        # Dataset completo y filtrado
        self._all: List[Dict[str, Any]] = []
        self._filtered: List[Dict[str, Any]] = []

        # Lazy load
        self._batch_size = 50
        self._rendered_rows = 0

        # ===== Root =====
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        # ========== Toolbar ==========
        tb_frame = QFrame()
        tb_frame.setObjectName("Toolbar")
        tb = QHBoxLayout(tb_frame)
        tb.setContentsMargins(10, 8, 10, 8)
        tb.setSpacing(8)

        self.btn_new = QPushButton("Nuevo cliente")
        self.btn_new.setObjectName("CTA")
        self.btn_new.setFixedHeight(38)
        self.btn_new.clicked.connect(self._on_new_client_clicked)
        tb.addWidget(self.btn_new)

        tb.addStretch(1)

        # Import/Export (deshabilitados por ahora)
        self.btn_import = QPushButton("Importar CSV")
        self.btn_import.setObjectName("GhostSmall")
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self._on_import_clicked)

        self.btn_export = QPushButton("Exportar CSV")
        self.btn_export.setObjectName("GhostSmall")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._on_export_clicked)

        tb.addWidget(self.btn_import)
        tb.addWidget(self.btn_export)
        root.addWidget(tb_frame)

        # ========== Filtros ==========
        filters = QHBoxLayout()
        filters.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre, teléfono, correo o Instagram…")
        self.search.textChanged.connect(self._on_search)
        filters.addWidget(self.search, stretch=1)

        lbl_order = QLabel("Ordenar por:")
        lbl_order.setStyleSheet("background: transparent;")
        filters.addWidget(lbl_order)

        self.cbo_order = QComboBox()
        self.cbo_order.addItems(["A–Z", "Última cita", "Próxima cita", "Fecha de alta"])
        self.cbo_order.setCurrentText(self.order_by)
        self.cbo_order.currentTextChanged.connect(self._on_change_order)
        self.cbo_order.setFixedHeight(36)
        filters.addWidget(self.cbo_order)

        root.addLayout(filters)

        # ========== Tabla ==========
        table_box = QFrame()
        table_box.setObjectName("Card")
        tv = QVBoxLayout(table_box)
        tv.setContentsMargins(12, 12, 12, 12)
        tv.setSpacing(8)

        # 5 columnas: Cliente, Contacto, Artista, Próxima cita, Estado
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels([
            "Cliente", "Contacto", "Artista", "Próxima cita", "Estado"
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Cliente
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Contacto
        for col in range(2, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self._on_double_click)

        # Menú contextual (acciones rápidas)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._open_context_menu)

        # Lazy load al hacer scroll
        self.table.verticalScrollBar().valueChanged.connect(self._on_scroll)

        tv.addWidget(self.table)
        root.addWidget(table_box, stretch=1)

        # Carga inicial desde BD
        self._reload_from_db()
        self._apply_and_reset_render()

    # ---------- Datos ----------
    def _reload_from_db(self) -> None:
        try:
            with SessionLocal() as db:  # type: Session
                clients: List[Client] = (
                    db.query(Client)
                    .order_by(asc(Client.id))
                    .all()
                )

                now = datetime.now()
                rows: List[Dict[str, Any]] = []

                for cl in clients:
                    cid: int = getattr(cl, "id", None)
                    name: str = getattr(cl, "name", None) or f"Cliente {cid}"
                    phone: Optional[str] = getattr(cl, "phone", None)
                    email: Optional[str] = getattr(cl, "email", None)
                    instagram: Optional[str] = getattr(cl, "instagram", None)
                    created_at: Optional[datetime] = getattr(cl, "created_at", None)

                    # Próxima y última cita
                    next_session = (
                        db.query(TattooSession)
                        .filter(TattooSession.client_id == cid, TattooSession.start >= now)
                        .order_by(asc(TattooSession.start))
                        .first()
                    )
                    last_session = (
                        db.query(TattooSession)
                        .filter(TattooSession.client_id == cid, TattooSession.start < now)
                        .order_by(TattooSession.start.desc())
                        .first()
                    )

                    # Artista a mostrar (sesiones → fallback preferred_artist_id)
                    artist_name = "—"
                    artist_id = None
                    if next_session:
                        artist_id = getattr(next_session, "artist_id", None)
                    elif last_session:
                        artist_id = getattr(last_session, "artist_id", None)
                    if not artist_id:
                        artist_id = getattr(cl, "preferred_artist_id", None)

                    if artist_id:
                        a = db.query(Artist).filter(Artist.id == artist_id).one_or_none()
                        if a and getattr(a, "name", None):
                            artist_name = a.name

                    def fmt_dt(dt: Optional[datetime]) -> str:
                        return dt.strftime("%d %b %H:%M") if dt else "—"

                    proxima_str = fmt_dt(getattr(next_session, "start", None))
                    estado = "Activo" if getattr(next_session, "start", None) else "—"

                    # Contacto: prefer Tel + @ig; si falta IG, usar email (si no duplicamos)
                    parts: List[str] = []
                    primary = phone or email
                    if primary:
                        parts.append(str(primary))
                    if instagram:
                        parts.append("@" + str(instagram))
                    else:
                        if email and email != primary:
                            parts.append(str(email))
                    contacto_str = "  ·  ".join([p for p in parts if p])[:200]

                    rows.append({
                        "id": cid,
                        "nombre": name,
                        "tel": phone,
                        "email": email,
                        "ig": instagram,
                        "artista": artist_name,
                        "proxima": proxima_str,
                        "estado": estado,
                        "_created_at": created_at,
                        "_last_session": getattr(last_session, "start", None),
                        "_next_session": getattr(next_session, "start", None),
                        "contacto": contacto_str,
                    })

                self._all = rows

        except Exception as ex:
            QMessageBox.critical(self, "BD", f"Error al cargar clientes: {ex}")
            self._all = []

    # ---------- Filtro/orden ----------
    def _apply_filters(self) -> List[Dict[str, Any]]:
        txt = self.search_text.lower().strip()
        if txt:
            rows = [
                c for c in self._all
                if (txt in c["nombre"].lower()
                    or (c.get("tel") and txt in str(c["tel"]).lower())
                    or (c.get("email") and txt in str(c["email"]).lower())
                    or (c.get("ig") and txt in str(c["ig"]).lower()))
            ]
        else:
            rows = list(self._all)

        if self.order_by == "A–Z":
            rows.sort(key=lambda c: c["nombre"].lower())
        elif self.order_by == "Última cita":
            rows.sort(key=lambda c: c.get("_last_session") or datetime.min, reverse=True)
        elif self.order_by == "Próxima cita":
            rows.sort(key=lambda c: (c.get("_next_session") is None, c.get("_next_session") or datetime.max))
        elif self.order_by == "Fecha de alta":
            rows.sort(key=lambda c: c.get("_created_at") or datetime.min, reverse=True)

        return rows

    # ---------- Render lazy ----------
    def _apply_and_reset_render(self) -> None:
        self._filtered = self._apply_filters()
        self._rendered_rows = 0
        self.table.setRowCount(0)
        self._append_next_batch()

    def _append_next_batch(self) -> None:
        if self._rendered_rows >= len(self._filtered):
            return
        start = self._rendered_rows
        end = min(start + self._batch_size, len(self._filtered))
        self.table.setRowCount(end)
        for r in range(start, end):
            c = self._filtered[r]
            it0 = QTableWidgetItem(c["nombre"])
            it0.setData(Qt.UserRole, c["id"])
            self.table.setItem(r, 0, it0)

            self.table.setItem(r, 1, QTableWidgetItem(c.get("contacto") or "—"))
            self.table.setItem(r, 2, QTableWidgetItem(c.get("artista") or "—"))
            self.table.setItem(r, 3, QTableWidgetItem(c.get("proxima") or "—"))
            self.table.setItem(r, 4, QTableWidgetItem(c.get("estado") or "—"))

        self._rendered_rows = end

    # ---------- Público: refresco inmediato ----------
    def reload_from_db_and_refresh(self, keep_page: bool = False) -> None:
        self._reload_from_db()
        self._apply_and_reset_render()

    # ---------- Eventos UI ----------
    def _on_search(self, text: str):
        self.search_text = text
        self._apply_and_reset_render()

    def _on_change_order(self, text: str):
        self.order_by = text
        self._apply_and_reset_render()

    def _on_double_click(self, row: int, col: int):
        item = self.table.item(row, 0)
        if not item:
            return
        cid = item.data(Qt.UserRole)
        data = next((c for c in self._filtered if c["id"] == cid), None)
        if data:
            self.abrir_cliente.emit(data)

    def _on_scroll(self, value: int):
        sb = self.table.verticalScrollBar()
        if sb.maximum() - value < 5:  # cerca del fondo
            self._append_next_batch()

    # ---------- Menú contextual ----------
    def _open_context_menu(self, pos: QPoint):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        data = self._filtered[row] if row < len(self._filtered) else None
        if not data:
            return

        m = QMenu(self)
        act_open = m.addAction("Abrir ficha")
        act_copy_phone = m.addAction("Copiar teléfono")
        act_copy_mail = m.addAction("Copiar correo")
        ig = data.get("ig")
        act_open_ig = m.addAction("Abrir Instagram") if ig else None

        chosen = m.exec_(self.table.viewport().mapToGlobal(pos))
        if not chosen:
            return

        if chosen == act_open:
            self.abrir_cliente.emit(data)
        elif chosen == act_copy_phone:
            if data.get("tel"):
                QApplication.clipboard().setText(str(data["tel"]))
        elif chosen == act_copy_mail:
            if data.get("email"):
                QApplication.clipboard().setText(str(data["email"]))
        elif act_open_ig and chosen == act_open_ig:
            # abrir perfil IG en navegador
            import webbrowser
            handle = str(ig).lstrip("@")
            webbrowser.open(f"https://instagram.com/{handle}")

    # ---------- Acciones Toolbar ----------
    def _on_new_client_clicked(self):
        if not ensure_permission(self, "clients", "create"):
            return
        self.crear_cliente.emit()

    def _on_import_clicked(self):
        if not ensure_permission(self, "clients", "export"):
            return
        QMessageBox.information(self, "Importar", "Función de importar aún no implementada.")

    def _on_export_clicked(self):
        if not ensure_permission(self, "clients", "export"):
            return
        QMessageBox.information(self, "Exportar", "Función de exportar aún no implementada.")
