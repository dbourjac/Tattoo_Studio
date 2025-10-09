from __future__ import annotations

from datetime import datetime, date, time, timedelta
from typing import Optional, List, Tuple

from PyQt5.QtCore import Qt, QDate, QPoint
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtWidgets import (
    QDialog, QFrame, QLabel, QComboBox, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QMessageBox, QCheckBox
)

# BD (SQLAlchemy)
from data.db.session import SessionLocal
from data.models.artist import Artist
from data.models.session_tattoo import TattooSession
from data.models.transaction import Transaction


# =======================
#   Estilo de popups
# =======================
class FramelessPanel(QDialog):
    """Popup estilo 'Card' sin barra de título, arrastrable y bordeado."""
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self._drag: Optional[QPoint] = None

        # Card contenedor
        self.wrap = QFrame(self)
        self.wrap.setObjectName("Card")
        self.wrap.setStyleSheet("""
            QFrame#Card {
                background: #2b2f36;
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 12px;
            }
            QLabel { background: transparent; color: #e8eaf0; }
            QLineEdit, QComboBox {
                background: #1f232a; color: #e8eaf0;
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 8px; padding: 8px 10px;
            }
            QPushButton#CTA {
                background: #3b82f6; color: white; padding: 8px 14px;
                border-radius: 10px; font-weight: 600;
            }
            QPushButton#GhostSmall {
                background: rgba(255,255,255,0.06); color: #e8eaf0;
                padding: 8px 14px; border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.10);
            }
            QPushButton#CTA:hover { filter: brightness(1.08); }
            QPushButton#GhostSmall:hover { border-color: rgba(255,255,255,0.18); }
            QCheckBox { color:#e8eaf0; background:transparent; }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.wrap)

        self.v = QVBoxLayout(self.wrap)
        self.v.setContentsMargins(16, 16, 16, 16)
        self.v.setSpacing(10)

        if title:
            t = QLabel(title)
            t.setStyleSheet("font-weight:700; font-size:12pt; background:transparent;")
            self.v.addWidget(t)

    # arrastre
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPos() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag and e.buttons() & Qt.LeftButton:
            self.move(e.globalPos() - self._drag)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag = None
        super().mouseReleaseEvent(e)


# =======================
#   Caja / Registrar pago
# =======================
class CashRegisterDialog(FramelessPanel):
    """
    Registrar cobros:
      - Sesión primero, luego Tatuador
      - Artistas activos solamente (sin selección por defecto)
      - Sesiones del día elegido (todas si no hay tatuador elegido, filtradas si lo hay)
      - Monto y Comisión con QLineEdit (sin flechas), validación numérica
      - Sin "Fecha/hora del cobro": se usa datetime.now()
      - En el combo de sesiones se muestra el NOMBRE DEL CLIENTE (no el ID)
    """
    def __init__(self, parent=None):
        super().__init__("Registrar pago", parent)

        # ====== Campos
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        # 1) Sesión (primero)
        self.cbo_session = QComboBox()
        self.cbo_session.setEditable(False)
        self.cbo_session.setInsertPolicy(QComboBox.NoInsert)
        grid.addWidget(QLabel("Sesión:"), 0, 0)
        grid.addWidget(self.cbo_session, 0, 1)

        # 2) Tatuador
        self.cbo_artist = QComboBox()
        self.cbo_artist.setEditable(False)
        self.cbo_artist.setInsertPolicy(QComboBox.NoInsert)
        grid.addWidget(QLabel("Tatuador:"), 1, 0)
        grid.addWidget(self.cbo_artist, 1, 1)

        # 3) Concepto
        self.txt_concept = QLineEdit()
        self.txt_concept.setPlaceholderText("Descripción breve del cobro…")
        grid.addWidget(QLabel("Concepto:"), 2, 0)
        grid.addWidget(self.txt_concept, 2, 1)

        # 4) Monto (QLineEdit con validador)
        self.txt_amount = QLineEdit()
        self.txt_amount.setPlaceholderText("0.00")
        self.txt_amount.setValidator(QDoubleValidator(0.0, 999999.0, 2, notation=QDoubleValidator.StandardNotation))
        grid.addWidget(QLabel("Monto:"), 3, 0)
        grid.addWidget(self.txt_amount, 3, 1)

        # 5) Método
        self.cbo_method = QComboBox()
        self.cbo_method.addItems(["Efectivo", "Tarjeta", "Transferencia", "Otro"])
        grid.addWidget(QLabel("Método:"), 4, 0)
        grid.addWidget(self.cbo_method, 4, 1)

        # 6) Comisión %
        self.txt_commission = QLineEdit()
        self.txt_commission.setPlaceholderText("0.00")
        self.txt_commission.setValidator(QDoubleValidator(0.0, 100.0, 2, notation=QDoubleValidator.StandardNotation))
        grid.addWidget(QLabel("Comisión %:"), 5, 0)
        grid.addWidget(self.txt_commission, 5, 1)

        # 7) Fecha (para cargar sesiones del día) — sin el texto “(sesiones del día)”
        #    Se usa QDate en memoria; no se muestra un control con calendario para mantener el diseño simple.
        self._date_for_sessions = QDate.currentDate()

        # 8) Flag completar sesión
        self.chk_complete = QCheckBox("Marcar la sesión como Completada")
        grid.addWidget(self.chk_complete, 6, 1)

        self.v.addLayout(grid)

        # Botones
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_cancel = QPushButton("Cancelar"); self.btn_cancel.setObjectName("GhostSmall")
        self.btn_ok = QPushButton("Registrar"); self.btn_ok.setObjectName("CTA")
        row.addWidget(self.btn_cancel); row.addWidget(self.btn_ok)
        self.v.addLayout(row)

        # Señales
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._save)

        # Carga inicial
        self._load_artists(active_only=True)
        self._reload_sessions()  # con el día actual y sin filtro de artista

        # Cuando cambia el artista, recargar sesiones del día filtradas
        self.cbo_artist.currentIndexChanged.connect(self._reload_sessions)

        # Tamaño
        self.resize(540, 360)

    # ===== Helpers de BD
    def _load_artists(self, *, active_only: bool = True):
        """Carga artistas en el combo. No selecciona ninguno por defecto."""
        self.cbo_artist.blockSignals(True)
        self.cbo_artist.clear()
        self.cbo_artist.addItem("-- Selecciona un tatuador --", None)  # placeholder
        with SessionLocal() as db:
            q = db.query(Artist)
            if hasattr(Artist, "active") and active_only:
                q = q.filter(Artist.active == True)  # noqa: E712
            for a in q.order_by(Artist.name).all():
                self.cbo_artist.addItem(a.name or f"Artist {a.id}", int(a.id))
        self.cbo_artist.setCurrentIndex(0)  # sin selección
        self.cbo_artist.blockSignals(False)

    # === Sesiones del día ===
    def _day_utc_bounds(self, qd: QDate) -> Tuple[datetime, datetime]:
        """Devuelve (start, end) UTC aproximado para el día de QDate (asumiendo timestamps en UTC)."""
        # Usamos hora local -> UTC para conformarnos con DB en UTC naive
        d_py = date(qd.year(), qd.month(), qd.day())
        local_start = datetime.combine(d_py, time(0, 0, 0)).astimezone()  # local tz
        local_end = (local_start + timedelta(days=1)) - timedelta(microseconds=1)
        start_utc = local_start.astimezone().astimezone().astimezone().astimezone().astimezone()
        # lo anterior mantiene tz local; para DB naive/UTC convertimos a “naive” en UTC:
        start_utc = local_start.astimezone(datetime.now().astimezone().tzinfo).astimezone().replace(tzinfo=None)
        end_utc = local_end.astimezone(datetime.now().astimezone().tzinfo).astimezone().replace(tzinfo=None)
        return start_utc, end_utc

    def _reload_sessions(self):
        """Rellena el combo de 'Sesión' para el día y artista seleccionados."""
        self.cbo_session.blockSignals(True)
        self.cbo_session.clear()
        self.cbo_session.addItem("Sin sesión (cobro suelto)", None)

        artist_id = self.cbo_artist.currentData()  # puede ser None
        day = self._date_for_sessions
        start, end = self._day_utc_bounds(day)

        with SessionLocal() as db:
            q = db.query(TattooSession)
            # Campo de fecha/hora: intentamos resolver nombres comunes
            dt_attr = None
            for cand in ("start_time", "start_at", "scheduled_at", "datetime", "date"):
                if hasattr(TattooSession, cand):
                    dt_attr = getattr(TattooSession, cand)
                    break
            if dt_attr is None:
                # no sabemos el nombre; mostramos sin filtrar por día (peor caso)
                sessions = q.all()
            else:
                q = q.filter(dt_attr >= start, dt_attr <= end)
                if artist_id:
                    if hasattr(TattooSession, "artist_id"):
                        q = q.filter(TattooSession.artist_id == int(artist_id))
                sessions = q.order_by(dt_attr.asc()).all()

            # Construir etiqueta: CLIENTE (no ID) + hora + estado + monto si existe
            for s in sessions:
                label = self._session_label(db, s)
                self.cbo_session.addItem(label, int(getattr(s, "id", 0) or 0))

        self.cbo_session.blockSignals(False)

    def _session_label(self, db, s) -> str:
        # Cliente
        client_name = ""
        try:
            c = getattr(s, "client", None)
            if c is not None:
                client_name = getattr(c, "name", "") or getattr(c, "full_name", "") or ""
            if not client_name:
                client_name = getattr(s, "client_name", "") or getattr(s, "customer_name", "") or ""
        except Exception:
            pass

        # Hora
        hhmm = ""
        for cand in ("start_time", "start_at", "scheduled_at", "datetime", "date"):
            if hasattr(s, cand):
                v = getattr(s, cand)
                try:
                    if v:
                        if isinstance(v, datetime):
                            hhmm = v.strftime("%H:%M")
                        else:
                            # si fuera date
                            hhmm = str(v)
                except Exception:
                    pass
                break

        status = getattr(s, "status", "") or getattr(s, "state", "") or ""
        amount = getattr(s, "amount", None)
        amount_txt = f"$ {amount:.2f}" if isinstance(amount, (int, float)) else ""

        parts: List[str] = []
        if client_name: parts.append(client_name)
        if hhmm: parts.append(hhmm)
        if status: parts.append(status)
        if amount_txt: parts.append(amount_txt)

        return " · ".join(parts) if parts else "Sesión"

    # ===== Guardar cobro
    def _save(self):
        # Validaciones
        amount_txt = (self.txt_amount.text() or "0").strip()
        commission_txt = (self.txt_commission.text() or "0").strip()

        try:
            amount = float(amount_txt)
        except Exception:
            amount = -1.0
        try:
            commission_pct = float(commission_txt)
        except Exception:
            commission_pct = 0.0

        if amount <= 0:
            QMessageBox.warning(self, "Monto", "Ingresa un monto válido mayor que 0.")
            return

        # Determinar artista y sesión seleccionados
        session_id = self.cbo_session.currentData()  # None = cobro suelto
        artist_id = self.cbo_artist.currentData()    # None si no eligió tatuador

        if session_id is None and artist_id is None:
            QMessageBox.warning(
                self, "Campos requeridos",
                "Selecciona una **sesión** o, si es cobro suelto, elige un **tatuador**."
            )
            return

        concept = (self.txt_concept.text() or "").strip()
        method = self.cbo_method.currentText()
        now = datetime.now()  # fecha/hora actual del cobro

        # Si eligió sesión pero dejó artista en blanco, intentamos deducir el artista de esa sesión
        if session_id is not None and artist_id is None:
            with SessionLocal() as db:
                s = db.query(TattooSession).get(int(session_id))
                if s and hasattr(s, "artist_id") and getattr(s, "artist_id", None):
                    artist_id = int(getattr(s, "artist_id"))

        try:
            with SessionLocal() as db:
                # Crear transacción
                t = Transaction(
                    session_id=int(session_id) if session_id else None,
                    artist_id=int(artist_id) if artist_id else None,
                    amount=amount,
                    method=method,
                    date=now
                )
                # Campos opcionales si existen en el modelo
                try: setattr(t, "concept", concept)
                except Exception: pass
                try: setattr(t, "commission_pct", commission_pct)
                except Exception: pass

                db.add(t)

                # Si se marcó como completada, intentar actualizar sesión
                if session_id and self.chk_complete.isChecked():
                    s = db.query(TattooSession).get(int(session_id))
                    if s is not None:
                        for attr, value in (("status", "Completada"), ("state", "Completed"), ("is_completed", True)):
                            if hasattr(s, attr):
                                try:
                                    setattr(s, attr, value)
                                except Exception:
                                    pass

                db.commit()

            QMessageBox.information(self, "Pago", "Pago registrado correctamente.")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo registrar el pago:\n{e}")
