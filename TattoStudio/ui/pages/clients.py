from __future__ import annotations

# ============================================================
# clients.py — Lista de clientes (conexión real a BD + RBAC)
#
# Cambios:
# - Contacto: preferimos Teléfono + @instagram; si falta cualquiera, entra email como fallback.
# - Artista: si no hay próxima/última cita, usamos preferred_artist_id.
# - Método público reload_from_db_and_refresh() (ya existía) para refresco inmediato.
# ============================================================

from typing import List, Dict, Any, Optional
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSpacerItem, QSizePolicy, QFrame, QMessageBox
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

        # Estado de UI / datos
        self.page_size = 10
        self.current_page = 1
        self.search_text = ""
        self.order_by = "A–Z"

        # Dataset actual (cada item es un dict listo para render)
        self._all: List[Dict[str, Any]] = []

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
        self.search.setPlaceholderText("Buscar por nombre, teléfono o correo…")
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

        # Tamaño de página
        lbl_show = QLabel("Mostrar:")
        lbl_show.setStyleSheet("background: transparent;")
        filters.addWidget(lbl_show)

        self.cbo_page = QComboBox()
        self.cbo_page.addItems(["10", "25", "50", "100"])
        self.cbo_page.setCurrentText(str(self.page_size))
        self.cbo_page.currentTextChanged.connect(self._on_change_page_size)
        self.cbo_page.setFixedHeight(36)
        filters.addWidget(self.cbo_page)

        root.addLayout(filters)

        # ========== Tabla ==========
        table_box = QFrame()
        table_box.setObjectName("Card")
        tv = QVBoxLayout(table_box)
        tv.setContentsMargins(12, 12, 12, 12)
        tv.setSpacing(8)

        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels([
            "Cliente", "Contacto", "Artista", "Próxima cita", "Etiquetas", "Estado"
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in range(2, 6):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self._on_double_click)

        tv.addWidget(self.table)
        root.addWidget(table_box, stretch=1)

        # ========== Paginación ==========
        pager = QHBoxLayout()
        pager.setSpacing(8)

        self.btn_prev = QPushButton("⟵")
        self.btn_prev.setObjectName("GhostSmall")
        self.btn_next = QPushButton("⟶")
        self.btn_next.setObjectName("GhostSmall")

        self.lbl_page = QLabel("Página 1/1")
        self.lbl_page.setStyleSheet("background: transparent;")

        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)

        pager.addWidget(self.btn_prev)
        pager.addWidget(self.btn_next)
        pager.addWidget(self.lbl_page)
        pager.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        root.addLayout(pager)

        # Carga inicial desde BD
        self._reload_from_db()
        self._refresh()

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
                    etiquetas = ""
                    estado = "Activo" if getattr(next_session, "start", None) else "—"

                    # Contacto: prefer Tel + @ig; si falta alguno, usa email como fallback
                    parts: List[str] = []
                    primary = phone or email  # si no hay phone, usa email
                    if primary:
                        parts.append(str(primary))
                    if instagram:
                        parts.append("@" + str(instagram))
                    else:
                        # si no hay IG, intenta agregar email (si no lo usamos ya)
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
                        "etiquetas": etiquetas,
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

    # ---------- Filtro/orden/paginación ----------
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

    def _refresh(self) -> None:
        rows = self._apply_filters()

        total_pages = max(1, (len(rows) + self.page_size - 1) // self.page_size)
        self.current_page = min(self.current_page, total_pages)

        start = (self.current_page - 1) * self.page_size
        page_rows = rows[start:start + self.page_size]

        self.table.setRowCount(len(page_rows))
        for r, c in enumerate(page_rows):
            it0 = QTableWidgetItem(c["nombre"])
            it0.setData(Qt.UserRole, c["id"])
            self.table.setItem(r, 0, it0)

            self.table.setItem(r, 1, QTableWidgetItem(
                c.get("contacto") or "  ·  ".join([p for p in [
                    str(c.get("tel") or "") if c.get("tel") else (str(c.get("email") or "") if c.get("email") else None),
                    "@" + str(c.get("ig")) if c.get("ig") else (str(c.get("email") or "") if c.get("email") else None),
                ] if p])
            ))
            self.table.setItem(r, 2, QTableWidgetItem(c.get("artista") or "—"))
            self.table.setItem(r, 3, QTableWidgetItem(c.get("proxima") or "—"))
            self.table.setItem(r, 4, QTableWidgetItem(c.get("etiquetas") or ""))
            self.table.setItem(r, 5, QTableWidgetItem(c.get("estado") or "—"))

        self.lbl_page.setText(f"Página {self.current_page}/{total_pages}")
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < total_pages)

    # ---------- Público: refresco inmediato ----------
    def reload_from_db_and_refresh(self, *, keep_page: bool = False) -> None:
        self._reload_from_db()
        if not keep_page:
            self.current_page = 1
        self._refresh()

    # ---------- Eventos UI ----------
    def _on_search(self, text: str):
        self.search_text = text
        self.current_page = 1
        self._refresh()

    def _on_change_order(self, text: str):
        self.order_by = text
        self.current_page = 1
        self._refresh()

    def _on_change_page_size(self, text: str):
        try:
            self.page_size = int(text)
        except ValueError:
            self.page_size = 10
        self.current_page = 1
        self._refresh()

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._refresh()

    def _next_page(self):
        self.current_page += 1
        self._refresh()

    def _on_double_click(self, row: int, col: int):
        item = self.table.item(row, 0)
        if not item:
            return
        cid = item.data(Qt.UserRole)
        data = next((c for c in self._all if c["id"] == cid), None)
        if data:
            self.abrir_cliente.emit(data)

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
