from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, time
import csv
import os
from pathlib import Path

from PyQt5.QtCore import Qt, QDate, QTime, QPoint, pyqtSignal, QTimer, QEvent
from PyQt5.QtGui import QFontMetrics, QColor, QPainter, QPainterPath, QPixmap, QMouseEvent, QCursor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDateEdit, QFrame, QCheckBox, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QLineEdit, QHeaderView, QSizePolicy, QFileDialog,
    QMessageBox, QMenu, QDialog, QFormLayout, QDialogButtonBox, QSpinBox, QCompleter,
    QPlainTextEdit, QDoubleSpinBox
)

# === BD / servicios ===
from services.sessions import (
    list_sessions, update_session, complete_session, cancel_session, create_session
)
# delete_session es opcional: si no existe, lo manejamos abajo
try:
    from services.sessions import delete_session  # type: ignore
except Exception:
    delete_session = None  # fallback

from data.db.session import SessionLocal
from data.models.client import Client
from data.models.artist import Artist as DBArtist

# Permisos centralizados (elevación incluida)
from ui.pages.common import ensure_permission

# Helpers compartidos (optimización: sin duplicar lógica de colores/menús)
from ui.pages.common import (
    artist_colors_path, load_artist_colors, fallback_color_for, NoStatusTipMenu
)


# ==============================
#   MODELOS DE UI (DTOs)
# ==============================

@dataclass
class Artist:
    id: str
    name: str
    color: str


@dataclass
class Appt:
    id: str
    client_id: Optional[int]
    client_name: str
    artist_id: str
    date: QDate
    start: QTime
    duration_min: int
    service: str
    status: str


# ==============================
#   COLORES (centralizado)
# ==============================
def _artist_color_for(aid: int, idx_fallback: int) -> str:
    """
    Obtiene color por ID desde artist_colors.json (vía common.load_artist_colors()),
    si no existe usa fallback_color_for(idx_fallback) para mantener paleta consistente.
    """
    try:
        ov = load_artist_colors()
        key = str(int(aid)).lower()
        if key in ov and ov[key]:
            return ov[key]
    except Exception:
        pass
    return fallback_color_for(idx_fallback)


# ==============================
#   ESTILO POR ESTADO
# ==============================

def _status_style(bg: str, border_hex: str, state: str) -> str:
    """
    Fondo sólido con el color del artista (relleno total) y variación mínima por estado.
    """
    def hex_to_rgba(h, a=1.0):
        h = h.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{a})"

    base = border_hex or "#6b7280"

    # Relleno casi pleno; pequeñas variaciones por estado
    if state == "Completada":
        back = hex_to_rgba(base, 0.95)
    elif state == "Cancelada":
        back = hex_to_rgba(base, 0.55)
    elif state == "En espera":
        back = hex_to_rgba(base, 0.85)
    else:  # Activa
        back = hex_to_rgba(base, 0.98)

    if bg:
        back = bg

    return f"""
    QFrame {{
        background: {back};
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 8px;
        color: white;
    }}
    QFrame:hover {{
        background: {hex_to_rgba(base, 1.0)};
    }}
    QLabel {{ background: transparent; }}
    """


# ==============================
# DIÁLOGOS (frameless/arrastrables)
# ==============================
class _FramelessDialog(QDialog):
    def __init__(self, title: str, parent=None, close_on_click_outside: bool = False):
        super().__init__(parent)
        self._close_on_outside = close_on_click_outside

        # Sin barra de título; NO DeleteOnClose (evita crash al leer values())
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # “outer” cubre todo el QDialog: esquinas 100% redondeadas (sin triángulos)
        self.outer = QFrame(self)
        self.outer.setObjectName("outer")
        root.addWidget(self.outer)

        wrap = QVBoxLayout(self.outer)
        wrap.setContentsMargins(14, 14, 14, 14)
        wrap.setSpacing(10)

        self.header = QLabel(title, self.outer)
        self.header.setStyleSheet("font-weight:700; background: transparent;")
        wrap.addWidget(self.header)

        self.body = QFrame(self.outer)
        self.body.setStyleSheet("background: transparent;")
        self.body_l = QVBoxLayout(self.body)
        self.body_l.setContentsMargins(0, 0, 0, 0)
        self.body_l.setSpacing(8)
        wrap.addWidget(self.body)

        # Estilo homogéneo (inputs NO quedan blancos)
        self.setStyleSheet("""
        QDialog { background: transparent; }
        QFrame#outer {
            background: #1f242b;
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 10px;
        }
        QLabel, QPlainTextEdit { background: transparent; }
        QDateEdit, QSpinBox, QComboBox, QLineEdit, QPlainTextEdit {
            background: #2a3139;
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 8px;
            padding: 6px 8px;
            color: #e6eaf0;
        }
        QDateEdit:hover, QSpinBox:hover, QComboBox:hover, QLineEdit:hover, QPlainTextEdit:hover {
            border-color: rgba(255,255,255,0.20);
        }
        QPushButton#okbtn, QPushButton#cancelbtn {
            border: 1px solid rgba(255,255,255,0.20);
            border-radius: 8px;
            padding: 6px 12px;
        }
        QPushButton#okbtn:hover, QPushButton#cancelbtn:hover {
            background: rgba(255,255,255,0.08);
        }
        """)

        self.resize(460, 340)
        self._drag_pos = None
        self._filter_installed = False

    # Arrastrable
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_pos and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPos() - self._drag_pos)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        super().mouseReleaseEvent(e)

    # Click fuera (solo si se activó)
    def showEvent(self, e):
        if self._close_on_outside and not self._filter_installed:
            from PyQt5.QtWidgets import QApplication
            QApplication.instance().installEventFilter(self)
            self._filter_installed = True
        return super().showEvent(e)

    def closeEvent(self, e):
        if self._filter_installed:
            from PyQt5.QtWidgets import QApplication
            QApplication.instance().removeEventFilter(self)
            self._filter_installed = False
        return super().closeEvent(e)

    def eventFilter(self, obj, ev):
        if self._close_on_outside and ev.type() == QEvent.MouseButtonPress:
            if isinstance(ev, QMouseEvent):
                # Usa frameGeometry() (coordenadas globales) para detectar fuera
                if not self.frameGeometry().contains(ev.globalPos()):
                    self.reject()
                    return True
        return super().eventFilter(obj, ev)

class _ClickAwayDialog(_FramelessDialog):
    """
    Igual que _FramelessDialog pero con comportamiento tipo 'popup':
    se cierra automáticamente al perder foco o al hacer click fuera.
    """
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent, close_on_click_outside=False)
        # Qt.Popup hace que se cierre al click fuera y al perder foco.
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)

    # Si por alguna razón pierde el foco, ciérralo (comportamiento de popup)
    def focusOutEvent(self, e):
        try:
            self.reject()
        except Exception:
            pass
        super().focusOutEvent(e)


class NewApptDialog(_FramelessDialog):
    """Diálogo de nueva cita con autocompletado de clientes."""
    def __init__(self, parent, artists: List[Artist], clients: List[Tuple[int, str]], default_date: QDate):
        super().__init__("Nueva cita", parent)

        form = QFormLayout(); form.setContentsMargins(0,0,0,0)

        self.dt_date = QDateEdit(default_date); self.dt_date.setCalendarPopup(True)
        form.addRow("Fecha:", self.dt_date)

        self.sp_hour = QSpinBox(); self.sp_hour.setRange(0, 23); self.sp_hour.setValue(12)
        self.sp_min  = QSpinBox(); self.sp_min.setRange(0, 59);  self.sp_min.setSingleStep(5); self.sp_min.setValue(0)
        hh = QHBoxLayout(); hh.addWidget(self.sp_hour); hh.addWidget(QLabel(":")); hh.addWidget(self.sp_min)
        wrap_time = QFrame(); wrap_time.setLayout(hh)
        form.addRow("Hora:", wrap_time)

        self.sp_dur = QSpinBox(); self.sp_dur.setRange(15, 600); self.sp_dur.setSingleStep(15); self.sp_dur.setValue(60)
        form.addRow("Duración (min):", self.sp_dur)

        self.cbo_artist = QComboBox()
        for a in artists:
            self.cbo_artist.addItem(a.name, a.id)
        form.addRow("Artista:", self.cbo_artist)

        # Cliente con combo editable + completer
        self.cb_client = QComboBox(); self.cb_client.setEditable(True); self.cb_client.setInsertPolicy(QComboBox.NoInsert)
        for cid, cname in clients:
            self.cb_client.addItem(cname, cid)
        completer = QCompleter([n for _, n in clients], self.cb_client)
        completer.setCaseSensitivity(Qt.CaseInsensitive); self.cb_client.setCompleter(completer)
        form.addRow("Cliente:", self.cb_client)

        self.ed_service = QPlainTextEdit(); self.ed_service.setPlaceholderText("Servicio / notas")
        self.ed_service.setFixedHeight(80)
        form.addRow("Servicio:", self.ed_service)

        self.cbo_status = QComboBox(); self.cbo_status.addItems(["Activa", "En espera", "Completada", "Cancelada"])
        form.addRow("Estado:", self.cbo_status)

        self.body_l.addLayout(form)

        btns = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancelar"); self.btn_cancel.setObjectName("cancelbtn")
        self.btn_ok = QPushButton("OK"); self.btn_ok.setObjectName("okbtn")
        self.btn_cancel.clicked.connect(self.reject); self.btn_ok.clicked.connect(self.accept)
        btns.addStretch(1); btns.addWidget(self.btn_cancel); btns.addWidget(self.btn_ok)
        self.body_l.addLayout(btns)

    def values(self) -> dict:
        date = self.dt_date.date()
        h, m = self.sp_hour.value(), self.sp_min.value()
        start = datetime(date.year(), date.month(), date.day(), h, m, 0)
        dur   = self.sp_dur.value()
        client_id = self.cb_client.currentData()
        client_name = self.cb_client.currentText().strip()
        return {
            "artist_id": int(self.cbo_artist.currentData()),
            "client_id": int(client_id) if client_id is not None else None,
            "client_name": client_name or None,
            "notes": (self.ed_service.toPlainText() or "").strip(),
            "status": self.cbo_status.currentText(),
            "start": start,
            "end": start + timedelta(minutes=dur),
        }


class EditApptDialog(_FramelessDialog):
    def __init__(self, parent, artists: List[Artist], clients: List[Tuple[int, str]], ap: Appt):
        super().__init__("Editar cita", parent)

        form = QFormLayout(); form.setContentsMargins(0,0,0,0)

        self.dt_date = QDateEdit(ap.date); self.dt_date.setCalendarPopup(True)
        form.addRow("Fecha:", self.dt_date)

        self.sp_hour = QSpinBox(); self.sp_hour.setRange(0, 23); self.sp_hour.setValue(ap.start.hour())
        self.sp_min  = QSpinBox(); self.sp_min.setRange(0, 59); self.sp_min.setSingleStep(5); self.sp_min.setValue(ap.start.minute())
        hh = QHBoxLayout(); hh.addWidget(self.sp_hour); hh.addWidget(QLabel(":")); hh.addWidget(self.sp_min)
        wrap_time = QFrame(); wrap_time.setLayout(hh)
        form.addRow("Hora:", wrap_time)

        self.sp_dur = QSpinBox(); self.sp_dur.setRange(15, 600); self.sp_dur.setSingleStep(15); self.sp_dur.setValue(ap.duration_min)
        form.addRow("Duración (min):", self.sp_dur)

        self.cbo_artist = QComboBox()
        for a in artists:
            self.cbo_artist.addItem(a.name, a.id)
        self.cbo_artist.setCurrentIndex(max(0, self.cbo_artist.findData(ap.artist_id)))
        form.addRow("Artista:", self.cbo_artist)

        self.cb_client = QComboBox(); self.cb_client.setEditable(True); self.cb_client.setInsertPolicy(QComboBox.NoInsert)
        for cid, cname in clients:
            self.cb_client.addItem(cname, cid)
        completer = QCompleter([n for _, n in clients], self.cb_client)
        completer.setCaseSensitivity(Qt.CaseInsensitive); self.cb_client.setCompleter(completer)
        self.cb_client.setCurrentText(ap.client_name or "")
        form.addRow("Cliente:", self.cb_client)

        self.ed_service = QPlainTextEdit(ap.service or ""); self.ed_service.setFixedHeight(80)
        form.addRow("Servicio:", self.ed_service)

        self.cbo_status = QComboBox(); self.cbo_status.addItems(["Activa", "En espera", "Completada", "Cancelada"])
        self.cbo_status.setCurrentText(ap.status or "Activa")
        form.addRow("Estado:", self.cbo_status)

        self.body_l.addLayout(form)

        btns = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancelar"); self.btn_cancel.setObjectName("cancelbtn")
        self.btn_ok = QPushButton("Guardar"); self.btn_ok.setObjectName("okbtn")
        self.btn_cancel.clicked.connect(self.reject); self.btn_ok.clicked.connect(self.accept)
        btns.addStretch(1); btns.addWidget(self.btn_cancel); btns.addWidget(self.btn_ok)
        self.body_l.addLayout(btns)

    def values(self) -> dict:
        date = self.dt_date.date()
        h, m = self.sp_hour.value(), self.sp_min.value()
        start = datetime(date.year(), date.month(), date.day(), h, m, 0)
        dur   = self.sp_dur.value()
        client_id = self.cb_client.currentData()
        client_name = self.cb_client.currentText().strip()
        return {
            "artist_id": int(self.cbo_artist.currentData()),
            "client_id": int(client_id) if client_id is not None else None,
            "client_name": client_name or None,
            "notes": (self.ed_service.toPlainText() or "").strip(),
            "status": self.cbo_status.currentText(),
            "start": start,
            "end": start + timedelta(minutes=dur),
        }


class PaymentDialog(_FramelessDialog):
    """
    Diálogo para registrar/editar el pago de una cita.
    Devuelve un dict con:
      - amount (float, MXN)
      - commission_pct (float, 0-100)
      - commission_amount (float, MXN)
      - method (str)
      - note (str)
    """
    def __init__(self, parent=None, preset: Optional[dict] = None, title="Cobro"):
        super().__init__(title, parent)
        preset = preset or {}

        form = QFormLayout(); form.setContentsMargins(0,0,0,0)

        # Monto total
        self.sp_amount = QDoubleSpinBox()
        self.sp_amount.setDecimals(2); self.sp_amount.setRange(0.00, 1_000_000.00)
        self.sp_amount.setSingleStep(50.00)
        self.sp_amount.setValue(float(preset.get("amount", 0.00)))
        form.addRow("Precio:", self.sp_amount)

        # Comisión (%)
        self.sp_comm = QDoubleSpinBox()
        self.sp_comm.setDecimals(2); self.sp_comm.setRange(0.00, 100.00)
        self.sp_comm.setSingleStep(5.00)
        self.sp_comm.setValue(float(preset.get("commission_pct", 0.00)))
        form.addRow("Comisión (%):", self.sp_comm)

        # Comisión calculada (sólo display)
        self.lbl_comm_calc = QLabel("Comisión: $0.00"); self.lbl_comm_calc.setStyleSheet("background:transparent;")
        form.addRow("", self.lbl_comm_calc)

        # Método
        self.cbo_method = QComboBox()
        self.cbo_method.addItems(["Efectivo", "Tarjeta", "Transferencia", "Mixto"])
        if preset.get("method"):
            i = self.cbo_method.findText(str(preset["method"]), Qt.MatchFixedString)
            if i >= 0: self.cbo_method.setCurrentIndex(i)
        form.addRow("Método de pago:", self.cbo_method)

        # Nota
        self.ed_note = QPlainTextEdit()
        self.ed_note.setPlaceholderText("Nota / referencia de cobro…")
        self.ed_note.setFixedHeight(70)
        self.ed_note.setPlainText(str(preset.get("note") or ""))
        form.addRow("Nota:", self.ed_note)

        self.body_l.addLayout(form)

        # Botones
        btns = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancelar"); self.btn_cancel.setObjectName("cancelbtn")
        self.btn_ok = QPushButton("OK"); self.btn_ok.setObjectName("okbtn")
        self.btn_cancel.clicked.connect(self.reject); self.btn_ok.clicked.connect(self.accept)
        btns.addStretch(1); btns.addWidget(self.btn_cancel); btns.addWidget(self.btn_ok)
        self.body_l.addLayout(btns)

        # Recalcular comisión en vivo
        def _recalc():
            amount = float(self.sp_amount.value())
            pct = float(self.sp_comm.value())
            comm_amount = round(amount * pct / 100.0, 2)
            self.lbl_comm_calc.setText(f"Comisión: ${comm_amount:,.2f}")
        self.sp_amount.valueChanged.connect(_recalc)
        self.sp_comm.valueChanged.connect(_recalc)
        _recalc()

    def values(self) -> dict:
        amount = float(self.sp_amount.value())
        pct = float(self.sp_comm.value())
        comm_amount = round(amount * pct / 100.0, 2)
        return {
            "amount": amount,
            "commission_pct": pct,
            "commission_amount": comm_amount,
            "method": self.cbo_method.currentText(),
            "note": (self.ed_note.toPlainText() or "").strip(),
            # bandera para permitir actualizar si ya hay transacción
            "update_if_exists": True,
        }


# ==============================
#   CHIP DE CITA (click/hover/menu)
# ==============================

class ApptChip(QFrame):
    def __init__(self, ap: Appt, artist: Optional[Artist], controller: 'AgendaPage'):
        super().__init__()
        self.setAutoFillBackground(True)
        self.ap = ap
        self.artist = artist
        self.controller = controller

        lay = QVBoxLayout(self); lay.setContentsMargins(6, 4, 6, 4); lay.setSpacing(2)
        text = f"{ap.client_name}\n{ap.service} • {ap.start.toString('hh:mm')}"
        lbl = QLabel(text); lbl.setWordWrap(True); lbl.setToolTip(text); lay.addWidget(lbl)

        color = artist.color if artist else "#666"
        self.setStyleSheet(_status_style("", color, ap.status))

    # Click izquierdo = abrir detalle
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.controller._open_appt_detail(self.ap)
        super().mouseReleaseEvent(e)

    # Menú contextual
    def contextMenuEvent(self, e):
        self.controller._show_appt_context_menu(self.ap, self.mapToGlobal(e.pos()))


# ==============================
#   AGENDA PAGE
# ==============================

class AgendaPage(QWidget):
    crear_cita = pyqtSignal()
    abrir_cita = pyqtSignal(dict)

    def showEvent(self, e):
        super().showEvent(e)
        # Relee artistas y reconstruye sidebar (nuevos y/o colores)
        self._load_artists_from_db()
        self._rebuild_sidebar_artists()
        self._refresh_all()

    def _reload_colors_if_changed(self):
        try:
            # Usamos la misma ruta centralizada de common.py
            p = Path(artist_colors_path())
            mt = p.stat().st_mtime if p.exists() else 0
            if mt != self._colors_mtime:
                self._colors_mtime = mt
                # Releer artistas (para aplicar colores) y reconstruir sidebar
                self._load_artists_from_db()
                if hasattr(self, "artists_checks_box"):
                    self._rebuild_sidebar_artists()
                self._rebuild_sidebar_artists()
                self._refresh_all()
        except Exception:
            pass

    def __init__(self):
        super().__init__()

        # ------- Estado -------
        self.current_date: QDate = QDate.currentDate()
        self.current_view: str = "day"   # day | week | month | list
        self.selected_artist_ids: List[str] = []
        self.selected_status: str = "Todos"
        self.search_text: str = ""

        self.day_start = QTime(8, 0)
        self.day_end   = QTime(22, 0)
        self.step_min  = 30

        # Datos
        self.artists: List[Artist] = []
        self.appts: List[Appt] = []
        self._clients_cache: List[Tuple[int, str]] = []

        self._load_artists_from_db()
        self._load_clients_minimal()

        # ------- UI -------
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        root.addWidget(self._build_toolbar())

        split = QSplitter(Qt.Horizontal); split.setChildrenCollapsible(False)
        root.addWidget(split, stretch=1)

        self.sidebar = self._build_sidebar()
        self.sidebar.setFixedWidth(240)
        split.addWidget(self.sidebar)

        self.views_stack = QStackedWidget(); split.addWidget(self.views_stack); split.setSizes([240, 1000])

        self.day_view   = DayView(self)
        self.week_view  = WeekView(self)
        self.month_view = MonthView(self)
        self.list_view  = ListView(self)

        self.views_stack.addWidget(self.day_view)
        self.views_stack.addWidget(self.week_view)
        self.views_stack.addWidget(self.month_view)
        self.views_stack.addWidget(self.list_view)

        # Menú contextual en la vista Lista
        self.list_view.tbl.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_view.tbl.customContextMenuRequested.connect(self._show_list_context_menu)
        self.list_view.tbl.itemDoubleClicked.connect(self._open_from_list)
        self._rebuild_sidebar_artists()

        self._refresh_all()
        self._reload_colors_timer = QTimer(self)
        self._reload_colors_timer.setInterval(3000)  # cada 3s
        self._reload_colors_timer.timeout.connect(self._reload_colors_if_changed)
        self._reload_colors_timer.start()
        self._colors_mtime = None

    # ---------- Toolbar ----------
    def _build_toolbar(self) -> QWidget:
        wrap = QFrame(); wrap.setObjectName("Toolbar")
        lay = QHBoxLayout(wrap); lay.setContentsMargins(10, 8, 10, 8); lay.setSpacing(8)

        self.btn_today = QPushButton("Hoy"); self.btn_today.setObjectName("Chip")
        self.btn_prev  = QPushButton("‹");   self.btn_prev.setObjectName("Chip")
        self.btn_next  = QPushButton("›");   self.btn_next.setObjectName("Chip")
        for b in (self.btn_today, self.btn_prev, self.btn_next):
            b.setFixedHeight(36); b.setMinimumWidth(48)
        self.btn_today.clicked.connect(self._go_today)
        self.btn_prev.clicked.connect(self._go_prev)
        self.btn_next.clicked.connect(self._go_next)
        lay.addWidget(self.btn_today); lay.addWidget(self.btn_prev); lay.addWidget(self.btn_next)

        self.dp = QDateEdit(self.current_date); self.dp.setCalendarPopup(True)
        self.dp.dateChanged.connect(self._on_date_changed)
        self.dp.setFixedHeight(36); self.dp.setMinimumWidth(140)
        lay.addWidget(self.dp)

        lbl_vista = QLabel("Vista:"); lbl_vista.setStyleSheet("background: transparent;")
        lay.addSpacing(6); lay.addWidget(lbl_vista)
        self.cbo_view = QComboBox()
        self.cbo_view.addItems(["Día", "Semana", "Mes", "Lista"])
        self.cbo_view.currentTextChanged.connect(self._on_view_changed)
        self.cbo_view.setFixedHeight(36)
        self.cbo_view.setMinimumWidth(120)
        self.cbo_view.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.cbo_view.setStyleSheet("QComboBox{padding-top:2px;padding-bottom:2px;}")
        lay.addWidget(self.cbo_view)

        lay.addStretch(1)

        self.btn_export = QPushButton("Exportar día")
        self.btn_export.setObjectName("GhostSmall")
        self.btn_export.clicked.connect(self._export_day_csv)
        self.btn_export.setFixedHeight(36)
        lay.addWidget(self.btn_export)

        self.btn_new = QPushButton("Nueva cita")
        self.btn_new.setObjectName("CTA")
        self.btn_new.clicked.connect(self._open_new_appt_dialog)
        self.btn_new.setFixedHeight(38); self.btn_new.setMinimumWidth(120)
        lay.addWidget(self.btn_new)

        return wrap

    def _build_sidebar(self) -> QWidget:
        w = QFrame(); w.setObjectName("Sidebar")
        lay = QVBoxLayout(w); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(12)

        def title(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet("background: transparent; font-weight: 600;")
            return lbl

        # Buscar
        lay.addWidget(title("Buscar"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar cliente…")
        self.search.textChanged.connect(self._on_filter_changed)
        lay.addWidget(self.search)

        # Tatuadores (checkboxes)
        lay.addWidget(title("Tatuadores"))
        self.artists_checks_box = QVBoxLayout()
        self.artists_checks_box.setContentsMargins(0, 0, 0, 0)
        self.artists_checks_box.setSpacing(6)
        lay.addLayout(self.artists_checks_box)

        self.artist_checks: Dict[str, QCheckBox] = {}

        # Estado (se crea aquí pero NO disparamos refresh todavía)
        lay.addWidget(title("Estado"))
        self.cbo_status = QComboBox()
        self.cbo_status.addItems(["Todos", "Activa", "Completada", "Cancelada", "En espera"])
        self.cbo_status.currentTextChanged.connect(self._on_filter_changed)
        lay.addWidget(self.cbo_status)

        lay.addStretch(1)
        return w

    # ---------- Sidebar ----------
    def _rebuild_sidebar_artists(self):
        """
        Reconstruye los checkboxes de 'Tatuadores' preservando la selección
        cuando sea posible. Llama a este método cada que se recargan artistas/colores.
        """
        # Selección previa
        prev_selected = {aid for aid, chk in getattr(self, "artist_checks", {}).items() if chk.isChecked()}

        # Vaciar contenedor
        while self.artists_checks_box.count():
            item = self.artists_checks_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.artist_checks = {}

        # Crear checkboxes con el color del artista en el indicador
        for a in self.artists:
            chk = QCheckBox(a.name)
            chk.setChecked((a.id in prev_selected) or (not prev_selected))  # si no había selección previa, marcar todos
            chk.toggled.connect(self._on_filter_changed)
            chk.setStyleSheet(f"""
                QCheckBox {{ background: transparent; }}
                QCheckBox::indicator {{
                    width: 14px; height: 14px;
                    border: 1px solid rgba(255,255,255,0.35);
                    border-radius: 3px;
                    background: transparent;
                }}
                QCheckBox::indicator:checked {{
                    background: {a.color};
                    border-color: {a.color};
                }}
            """)
            self.artist_checks[a.id] = chk
            self.artists_checks_box.addWidget(chk)

        # Reaplicar filtro con el nuevo mapa
        self._on_filter_changed()

    # ---------- Navegación temporal ----------
    def _go_today(self): self.current_date = QDate.currentDate(); self.dp.setDate(self.current_date); self._refresh_all()
    def _go_prev(self):
        if   self.current_view == "day":   self.current_date = self.current_date.addDays(-1)
        elif self.current_view == "week":  self.current_date = self.current_date.addDays(-7)
        elif self.current_view == "month": self.current_date = self.current_date.addMonths(-1)
        else:                              self.current_date = self.current_date.addDays(-1)
        self.dp.setDate(self.current_date); self._refresh_all()
    def _go_next(self):
        if   self.current_view == "day":   self.current_date = self.current_date.addDays(1)
        elif self.current_view == "week":  self.current_date = self.current_date.addDays(7)
        elif self.current_view == "month": self.current_date = self.current_date.addMonths(1)
        else:                              self.current_date = self.current_date.addDays(1)
        self.dp.setDate(self.current_date); self._refresh_all()
    def _on_date_changed(self, d: QDate): self.current_date = d; self._refresh_all()
    def _on_view_changed(self, txt: str):
        mapping = {"Día": ("day", 0), "Semana": ("week", 1), "Mes": ("month", 2), "Lista": ("list", 3)}
        self.current_view, idx = mapping.get(txt, ("day", 0))
        self.views_stack.setCurrentIndex(idx); self._refresh_all()
    def _on_filter_changed(self, *_):
        selected = [aid for aid, chk in self.artist_checks.items() if chk.isChecked()]
        self.selected_artist_ids = selected if len(selected) != len(self.artist_checks) else []
        cbo = getattr(self, "cbo_status", None)
        self.selected_status = cbo.currentText() if cbo else "Todos"
        self.search_text = (self.search.text() or "").strip().lower()
        self._refresh_all()

    # ---------- Carga de datos ----------
    def _load_artists_from_db(self):
        self.artists.clear()
        with SessionLocal() as db:
            try:
                rows = db.query(DBArtist.id, DBArtist.name).filter(getattr(DBArtist, "active", True) == True).order_by(DBArtist.name.asc()).all()  # noqa: E712
            except Exception:
                rows = db.query(DBArtist.id, DBArtist.name).order_by(DBArtist.name.asc()).all()
        for idx, (aid, name) in enumerate(rows):
            color = _artist_color_for(int(aid), idx)
            self.artists.append(Artist(id=str(aid), name=name, color=color))

    def _load_clients_minimal(self):
        """Cache ligero para autocompletar en 'Nueva cita'."""
        with SessionLocal() as db:
            rows = db.query(Client.id, Client.name).order_by(Client.name.asc()).all()
            self._clients_cache = [(int(cid), nm) for cid, nm in rows]

    def _current_visible_range(self) -> Tuple[QDate, QDate]:
        if self.current_view == "day":
            return self.current_date, self.current_date
        if self.current_view == "week":
            monday = self.current_date.addDays(-(self.current_date.dayOfWeek()-1))
            return monday, monday.addDays(6)
        if self.current_view == "month":
            first = QDate(self.current_date.year(), self.current_date.month(), 1)
            last  = first.addMonths(1).addDays(-1)
            return first, last
        # Lista: amplio
        return self.current_date.addDays(-365), self.current_date.addDays(365)

    def _fetch_sessions_from_db(self):
        q_from, q_to = self._current_visible_range()
        start_dt = datetime.combine(q_from.toPyDate(), time(0, 0, 0))
        end_dt   = datetime.combine(q_to.toPyDate(),   time(23, 59, 59))

        rows = list_sessions({"from": start_dt, "to": end_dt})

        client_ids = {r["client_id"] for r in rows if r.get("client_id") is not None}
        client_name_by_id: Dict[int, str] = {}
        if client_ids:
            with SessionLocal() as db:
                for cid, name in db.query(Client.id, Client.name).filter(Client.id.in_(client_ids)).all():
                    client_name_by_id[cid] = name

        appts: List[Appt] = []
        for r in rows:
            start: datetime = r["start"]
            end: Optional[datetime] = r.get("end") or (start + timedelta(minutes=60))
            qd = QDate(start.year, start.month, start.day)
            qt = QTime(start.hour, start.minute)
            duration = max(1, int((end - start).total_seconds() // 60))
            appts.append(
                Appt(
                    id=str(r["id"]),
                    client_id=r.get("client_id"),
                    client_name=client_name_by_id.get(r["client_id"], r.get("client_name") or "Cliente"),
                    artist_id=str(r["artist_id"]),
                    date=qd,
                    start=qt,
                    duration_min=duration,
                    service=r.get("notes") or "Tatuaje",
                    status=r.get("status") or "Activa",
                )
            )
        self.appts = appts

    # ---------- Helpers ----------
    def _artist_by_id(self, aid: str) -> Optional[Artist]:
        for a in self.artists:
            if a.id == aid: return a
        return None

    def _filter_appts(self) -> List[Appt]:
        self._fetch_sessions_from_db()

        rows: List[Appt] = []
        for ap in self.appts:
            if self.selected_artist_ids and ap.artist_id not in self.selected_artist_ids:
                continue
            if self.selected_status != "Todos" and ap.status != self.selected_status:
                continue
            stext = self.search_text
            if stext and (stext not in ap.client_name.lower()) and (stext not in (ap.service or "").lower()):
                continue
            rows.append(ap)

        start_q, end_q = self._current_visible_range()
        def in_range(a: Appt) -> bool:
            if self.current_view == "day":   return a.date == start_q
            return start_q <= a.date <= end_q
        return [r for r in rows if in_range(r)]

    def _find_appt_by_row(self, row: int) -> Optional[Appt]:
        if row < 0: return None
        rows = sorted(self._filter_appts(), key=lambda a: (a.date.toJulianDay(), a.start.hour(), a.start.minute()))
        return rows[row] if 0 <= row < len(rows) else None

    # ---------- Acciones / popups ----------
    def _open_new_appt_dialog(self):
        dlg = NewApptDialog(self, self.artists, self._clients_cache, self.current_date)
        if dlg.exec_() != QDialog.Accepted:
            return
        val = dlg.values()
        owner_id = val["artist_id"]
        if not ensure_permission(self, "agenda", "create", owner_id=owner_id):
            return

        if val.get("client_id") is None:
            QMessageBox.warning(self, "Nueva cita", "Selecciona un cliente de la lista.")
            return

        try:
            create_session({
                "artist_id": val["artist_id"],
                "start": val["start"],
                "end": val["end"],
                "notes": val["notes"],
                "client_id": val["client_id"],
                "client_name": val["client_name"],
                "status": val.get("status", "Activa"),
            })
            QMessageBox.information(self, "Cita", "Cita creada.")
            self._refresh_all()
        except Exception as e:
            QMessageBox.critical(self, "Agenda", f"No se pudo crear la cita: {e}")

    def _open_from_list(self):
        row = self.list_view.tbl.currentRow()
        ap = self._find_appt_by_row(row)
        if not ap: return
        self._open_appt_detail(ap)

    # Detalle
    def _open_appt_detail(self, ap: Appt):
        # Popup que se cierra al click fuera
        dlg = _ClickAwayDialog("Detalle de cita", self)

        form = QFormLayout(); form.setContentsMargins(0,0,0,0)
        a = self._artist_by_id(ap.artist_id)
        form.addRow("Cliente:", QLabel(ap.client_name))
        form.addRow("Tatuador:", QLabel(a.name if a else ""))
        form.addRow("Fecha:", QLabel(ap.date.toString("dd/MM/yyyy")))
        form.addRow("Hora:", QLabel(ap.start.toString("hh:mm")))
        form.addRow("Duración:", QLabel(f"{ap.duration_min} min"))
        form.addRow("Estado:", QLabel(ap.status))
        notes = QLabel(ap.service or "—"); notes.setWordWrap(True)
        form.addRow("Servicio / nota:", notes)
        dlg.body_l.addLayout(form)

        # Botones
        btns = QHBoxLayout()
        b_edit = QPushButton("Editar"); b_state = QPushButton("Cambiar estado"); b_repg = QPushButton("Reprogramar")
        b_del = QPushButton("Eliminar"); b_close = QPushButton("Cerrar")
        for b in (b_edit, b_state, b_repg, b_del, b_close):
            b.setObjectName("okbtn")
        btns.addStretch(1); btns.addWidget(b_edit); btns.addWidget(b_state); btns.addWidget(b_repg); btns.addWidget(b_del); btns.addWidget(b_close)
        dlg.body_l.addLayout(btns)

        # Acciones
        def do_edit():
            dlg.close()
            self._edit_appt(ap)

        def do_state():
            m = NoStatusTipMenu(dlg)  # <-- evita limpiar el status bar
            acts = {
                "Activa": m.addAction("Activa"),
                "En espera": m.addAction("En espera"),
                "Completada": m.addAction("Completada"),
                "Cancelada": m.addAction("Cancelada"),
            }
            chosen = m.exec_(QCursor.pos())
            if not chosen: return
            for k, v in acts.items():
                if v is chosen:
                    self._set_status(ap, k); break

        def do_repg():
            dlg.close()
            self._edit_appt(ap, focus_time=True)

        def do_del():
            owner_id = int(ap.artist_id)
            if not ensure_permission(self, "agenda", "delete", owner_id=owner_id):
                return
            try:
                if delete_session:
                    delete_session(int(ap.id))
                else:
                    cancel_session(int(ap.id))
                QMessageBox.information(self, "Cita", "Cita eliminada.")
            except Exception as e:
                QMessageBox.critical(self, "Agenda", f"No se pudo eliminar: {e}")
            self._refresh_all()
            dlg.close()

        b_edit.clicked.connect(do_edit)
        b_state.clicked.connect(do_state)
        b_repg.clicked.connect(do_repg)
        b_del.clicked.connect(do_del)
        b_close.clicked.connect(dlg.close)

        dlg.exec_()

    # Editar
    def _edit_appt(self, ap: Appt, focus_time: bool = False):
        owner_id = int(ap.artist_id)
        if not ensure_permission(self, "agenda", "edit", owner_id=owner_id):
            return

        dlg = EditApptDialog(self, self.artists, self._clients_cache, ap)
        if focus_time:
            dlg.sp_hour.setFocus()
        if dlg.exec_() != QDialog.Accepted:
            return
        val = dlg.values()

        try:
            payload = {
                "artist_id": val["artist_id"],
                "start": val["start"],
                "end": val["end"],
                "notes": val["notes"],
                "client_id": val["client_id"],
                "client_name": val["client_name"],
                "status": val["status"],
            }
            update_session(int(ap.id), payload)
            # Ejecutar acción semántica si corresponde
            if val["status"] == "Completada":
                complete_session(int(ap.id), {})
            elif val["status"] == "Cancelada":
                cancel_session(int(ap.id))
            QMessageBox.information(self, "Cita", "Cambios guardados.")
        except Exception as e:
            QMessageBox.critical(self, "Agenda", f"No se pudo guardar: {e}")
        self._refresh_all()

    # Estado directo
    def _set_status(self, ap: Appt, status: str):
        owner_id = int(ap.artist_id)
        if not ensure_permission(self, "agenda", "edit", owner_id=owner_id):
            return
        try:
            if status == "Completada":
                complete_session(int(ap.id), {})
            elif status == "Cancelada":
                cancel_session(int(ap.id))
            else:
                update_session(int(ap.id), {"status": status})
            QMessageBox.information(self, "Cita", "Estado actualizado.")
        except Exception as e:
            QMessageBox.critical(self, "Agenda", f"No se pudo actualizar: {e}")
        self._refresh_all()

    # Menú contextual directo desde chip
    def _show_appt_context_menu(self, ap: Appt, global_pos: QPoint):
        m = NoStatusTipMenu(self)  # <-- reemplazo de QMenu
        m.setStyleSheet("""
            QMenu {
                background: #1f242b;
                border: 1px solid rgba(255,255,255,0.14);
                padding: 6px;
            }
            QMenu::item {
                padding: 6px 10px;
                background: transparent;
            }
            QMenu::item:selected {
                background: rgba(255,255,255,0.10);
                border-radius: 6px;
            }
        """)
        act_open = m.addAction("Ver detalles")
        m.addSeparator()
        act_edit = m.addAction("Editar (reprogramar)")
        act_complete = m.addAction("Completar (cobrar)")
        act_cancel = m.addAction("Cancelar")
        act_state = m.addMenu("Cambiar estado")
        a1 = act_state.addAction("Activa")
        a2 = act_state.addAction("En espera")
        a3 = act_state.addAction("Completada")
        a4 = act_state.addAction("Cancelada")
        m.addSeparator()
        act_delete = m.addAction("Eliminar…")

        chosen = m.exec_(global_pos)
        if not chosen:
            return

        if chosen in (a1, a2, a3, a4):
            self._set_status(ap, chosen.text()); return
        if chosen is act_open:
            self._open_appt_detail(ap); return
        if chosen is act_edit:
            self._edit_appt(ap); return
        if chosen is act_complete:
            if not ensure_permission(self, "agenda", "complete", owner_id=int(ap.artist_id)):
                return
            dlg = PaymentDialog(self)  # puedes pasar 'preset' si luego lees los datos actuales
            if dlg.exec_() == QDialog.Accepted:
                payload = dlg.values()
                try:
                    # primer intento normal
                    complete_session(int(ap.id), payload)
                    QMessageBox.information(self, "Cita", "Cobro registrado.")
                except Exception as e:
                    msg = str(e).lower()
                    # si ya existía, ofrecemos ACTUALIZAR
                    if "ya tiene transacción" in msg or "already has" in msg:
                        ask = QMessageBox.question(
                            self, "Editar cobro",
                            "Esta cita ya tiene transacción.\n¿Actualizarla con los nuevos datos?"
                        )
                        if ask == QMessageBox.Yes:
                            payload["update_if_exists"] = True
                            try:
                                complete_session(int(ap.id), payload)
                                QMessageBox.information(self, "Cita", "Transacción actualizada.")
                            except Exception as e2:
                                QMessageBox.critical(self, "Cita", f"No se pudo actualizar: {e2}")
                    else:
                        QMessageBox.critical(self, "Cita", f"No se pudo completar: {e}")
                self._refresh_all()
            return

        if chosen is act_cancel:
            if not ensure_permission(self, "agenda", "cancel", owner_id=int(ap.artist_id)):
                return
            try:
                cancel_session(int(ap.id))
                QMessageBox.information(self, "Cita", "Cita cancelada.")
            except Exception as e:
                QMessageBox.critical(self, "Agenda", f"No se pudo cancelar: {e}")
            self._refresh_all(); return
        if chosen is act_delete:
            self._open_appt_detail(ap)  # reutilizamos confirmaciones del detalle
            return

    def _show_list_context_menu(self, pos: QPoint):
        row = self.list_view.tbl.rowAt(pos.y())
        ap = self._find_appt_by_row(row)
        if not ap: return

        menu = NoStatusTipMenu(self)  # <-- reemplazo de QMenu
        act_open = menu.addAction("Abrir ficha")
        menu.addSeparator()
        act_edit = menu.addAction("Editar (reprogramar)")
        act_complete = menu.addAction("Completar (cobrar)")
        act_cancel = menu.addAction("Cancelar")
        act_noshow = menu.addAction("Marcar no-show")
        act_block = menu.addAction("Bloqueo/Ausencia (no disponible)"); act_block.setEnabled(False)

        chosen = menu.exec_(self.list_view.tbl.viewport().mapToGlobal(pos))
        if not chosen:
            return

        owner_id = int(ap.artist_id)

        if chosen is act_open:
            self._open_from_list(); return

        if chosen is act_edit:
            self._edit_appt(ap); return

        if chosen is act_complete:
            if not ensure_permission(self, "agenda", "complete", owner_id=owner_id):
                return
            dlg = PaymentDialog(self)
            if dlg.exec_() == QDialog.Accepted:
                payload = dlg.values()
                try:
                    complete_session(int(ap.id), payload)
                    QMessageBox.information(self, "Cita", "Cobro registrado.")
                except Exception as e:
                    msg = str(e).lower()
                    if "ya tiene transacción" in msg or "already has" in msg:
                        if QMessageBox.question(self, "Editar cobro",
                            "Esta cita ya tiene transacción.\n¿Actualizarla con los nuevos datos?") == QMessageBox.Yes:
                            payload["update_if_exists"] = True
                            try:
                                complete_session(int(ap.id), payload)
                                QMessageBox.information(self, "Cita", "Transacción actualizada.")
                            except Exception as e2:
                                QMessageBox.critical(self, "Cita", f"No se pudo actualizar: {e2}")
                    else:
                        QMessageBox.critical(self, "Cita", f"No se pudo completar: {e}")
                self._refresh_all()
            return

        if chosen is act_cancel:
            if not ensure_permission(self, "agenda", "cancel", owner_id=owner_id):
                return
            try:
                cancel_session(int(ap.id))
                QMessageBox.information(self, "Cita", "Cita cancelada.")
            except Exception as e:
                QMessageBox.critical(self, "Agenda", f"No se pudo cancelar: {e}")
            self._refresh_all(); return

        if chosen is act_noshow:
            if not ensure_permission(self, "agenda", "no_show", owner_id=owner_id):
                return
            try:
                cancel_session(int(ap.id), as_no_show=True)
                QMessageBox.information(self, "Cita", "Cita marcada como no-show.")
            except Exception as e:
                QMessageBox.critical(self, "Agenda", f"No se pudo marcar no-show: {e}")
            self._refresh_all(); return

    def _export_day_csv(self):
        if not ensure_permission(self, "agenda", "export"):
            return
        rows = [a for a in self._filter_appts() if a.date == self.current_date]
        if not rows:
            QMessageBox.information(self, "Exportar", "No hay citas en el día seleccionado.")
            return

        default_name = f"agenda_{self.current_date.toString('yyyyMMdd')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", os.path.join(os.path.expanduser("~"), default_name), "CSV (*.csv)")
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Fecha", "Hora", "Cliente", "Artista", "Servicio", "Estado"])
                for ap in rows:
                    artist = self._artist_by_id(ap.artist_id)
                    w.writerow([
                        ap.date.toString("dd/MM/yyyy"),
                        ap.start.toString("hh:mm"),
                        ap.client_name,
                        artist.name if artist else "",
                        ap.service,
                        ap.status,
                    ])
            QMessageBox.information(self, "Exportar", "Exportación realizada.")
        except Exception as e:
            QMessageBox.critical(self, "Exportar", f"No se pudo exportar: {e}")

    # ---------- Render ----------
    def _refresh_all(self):
        rows = self._filter_appts()

        self.day_view.configure(
            self.artists, self.current_date, self.day_start, self.day_end, self.step_min,
            self.selected_artist_ids or [a.id for a in self.artists]
        )
        self.day_view.render(rows, self._artist_by_id)

        self.week_view.configure(
            self.artists, self.current_date, self.day_start, self.day_end, self.step_min,
            self.selected_artist_ids or [a.id for a in self.artists]
        )
        self.week_view.render(rows, self._artist_by_id)

        self.month_view.configure(self.artists, self.current_date)
        self.month_view.render(rows, self._artist_by_id)

        self.list_view.render(rows, self._artist_by_id)


# ==============================
#   SUB-VISTAS
# ==============================

class DayView(QWidget):
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        self.parent: AgendaPage = parent
        self.artists: List[Artist] = []
        self.date = QDate.currentDate()
        self.day_start = QTime(8, 0); self.day_end = QTime(22, 0); self.step_min = 30
        self.artist_order: List[str] = []

        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)
        self.subtitle = QLabel(""); self.subtitle.setStyleSheet("color:#888; background: transparent;")
        lay.addWidget(self.subtitle)

        grid = QHBoxLayout(); grid.setContentsMargins(0, 0, 0, 0); grid.setSpacing(0)
        lay.addLayout(grid)

        # Tabla de horas (columna fija)
        self.tbl_hours = QTableWidget()
        self.tbl_hours.setFixedWidth(80)
        self.tbl_hours.verticalHeader().setVisible(False)
        self.tbl_hours.horizontalHeader().setVisible(True)
        self.tbl_hours.horizontalHeader().setStretchLastSection(True)
        self.tbl_hours.setEditTriggers(self.tbl_hours.NoEditTriggers)
        self.tbl_hours.setSelectionMode(self.tbl_hours.NoSelection)
        self.tbl_hours.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        grid.addWidget(self.tbl_hours)

        # Tabla principal
        self.tbl = QTableWidget()
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers); self.tbl.setSelectionMode(self.tbl.NoSelection)
        self.tbl.setStyleSheet("QHeaderView::section { background: transparent; }")
        # Scroll en píxeles para poder compensar la línea “ahora”
        self.tbl.setVerticalScrollMode(self.tbl.ScrollPerPixel)
        self.tbl.setHorizontalScrollMode(self.tbl.ScrollPerPixel)
        grid.addWidget(self.tbl, stretch=1)

        # Sincroniza scroll vertical: principal => horas
        self.tbl.verticalScrollBar().valueChanged.connect(self.tbl_hours.verticalScrollBar().setValue)
        self.tbl.verticalScrollBar().valueChanged.connect(self._update_now_line)

        # Línea del “ahora”
        self.now_line_main = QFrame(self.tbl.viewport()); self.now_line_main.setFrameShape(QFrame.HLine)
        self.now_line_main.setStyleSheet("color:#ff6161; background:#ff6161;")
        self.now_line_main.setFixedHeight(2); self.now_line_main.hide()

        self.now_line_hours = QFrame(self.tbl_hours.viewport()); self.now_line_hours.setFrameShape(QFrame.HLine)
        self.now_line_hours.setStyleSheet("color:#ff6161; background:#ff6161;")
        self.now_line_hours.setFixedHeight(2); self.now_line_hours.hide()

        # Timer para actualizar posición/anchos
        self._timer = QTimer(self); self._timer.setInterval(30_000); self._timer.timeout.connect(self._update_now_line)
        self._timer.start()

        # Escuchar resize para corregir ancho inicial de la línea
        self.tbl.viewport().installEventFilter(self)
        self.tbl_hours.viewport().installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Resize:
            self._update_now_line()
        return super().eventFilter(obj, ev)

    def configure(self, artists: List[Artist], date: QDate, start: QTime, end: QTime, step: int, artist_ids: List[str]):
        self.artists = artists; self.date = date
        self.day_start, self.day_end, self.step_min = start, end, step
        self.artist_order = artist_ids

    def render(self, appts: List[Appt], artist_lookup):
        self.subtitle.setText(self.date.toString("ddd dd MMM yyyy"))

        steps = int(self.day_start.secsTo(self.day_end) / 60 // self.step_min)
        row_height = 32

        # ----- tabla principal primero -----
        self.tbl.clear(); self.tbl.setRowCount(steps); self.tbl.setColumnCount(len(self.artist_order))
        hdr = self.tbl.horizontalHeader()
        fm = QFontMetrics(self.font())
        for c, aid in enumerate(self.artist_order):
            name = self._artist_name(aid)
            it = QTableWidgetItem(name); it.setToolTip(name)
            self.tbl.setHorizontalHeaderItem(c, it)
            hdr.setSectionResizeMode(c, QHeaderView.Stretch)
            minw = max(140, fm.horizontalAdvance(name) + 24)
            self.tbl.setColumnWidth(c, minw)
        for r in range(steps):
            self.tbl.setRowHeight(r, row_height)

        # ----- tabla horas (con header alineado) -----
        self.tbl_hours.clear(); self.tbl_hours.setRowCount(steps); self.tbl_hours.setColumnCount(1)
        self.tbl_hours.horizontalHeader().setFixedHeight(self.tbl.horizontalHeader().height())
        self.tbl_hours.setHorizontalHeaderItem(0, QTableWidgetItem(""))
        t = QTime(self.day_start)
        for r in range(steps):
            show = t.toString("hh:mm") if t.minute() == 0 else t.toString("hh:mm")
            it = QTableWidgetItem(show if t.minute() in (0, 30) else "")
            if t.minute() == 30:
                it.setForeground(QColor("#9aa0a6"))  # tono atenuado
            it.setFlags(Qt.ItemIsEnabled)
            self.tbl_hours.setItem(r, 0, it)
            self.tbl_hours.setRowHeight(r, row_height)
            t = t.addSecs(self.step_min * 60)

        # Indicador “ahora”
        self.now_line_main.hide(); self.now_line_hours.hide()
        QTimer.singleShot(0, self._update_now_line)  # asegura ancho/posición correctos iniciales

        # Chips de cita
        for ap in appts:
            if ap.date != self.date or ap.artist_id not in self.artist_order: continue
            col = self.artist_order.index(ap.artist_id)
            row_start = int(self.day_start.secsTo(ap.start) / 60 // self.step_min)
            row_span  = max(1, ap.duration_min // self.step_min)

            a = artist_lookup(ap.artist_id)
            chip = ApptChip(ap, a, self.parent)
            self.tbl.setSpan(row_start, col, row_span, 1)
            self.tbl.setCellWidget(row_start, col, chip)

    def _update_now_line(self):
        """Coloca la línea roja de 'ahora' con precisión de minutos y corrige scroll/anchos."""
        self.now_line_main.hide(); self.now_line_hours.hide()
        if self.date != QDate.currentDate():
            return

        steps = int(self.day_start.secsTo(self.day_end) / 60 // self.step_min)
        if steps <= 0:
            return

        row_height = self.tbl.rowHeight(0) if self.tbl.rowCount() else 32
        minutes = self.day_start.secsTo(QTime.currentTime()) / 60.0
        if minutes < 0:
            return
        # posición en píxeles desde la PRIMERA fila
        y_full = (minutes / self.step_min) * row_height
        # compensar scroll (en píxeles porque usamos ScrollPerPixel)
        scroll_px = float(self.tbl.verticalScrollBar().value())
        y_view = int(max(1, min(steps * row_height - 1, y_full - scroll_px)))

        self.now_line_main.setFixedWidth(self.tbl.viewport().width())
        self.now_line_hours.setFixedWidth(self.tbl_hours.viewport().width())
        self.now_line_main.move(0, y_view)
        self.now_line_hours.move(0, y_view)
        self.now_line_main.show(); self.now_line_hours.show()

    def _artist_name(self, aid: str) -> str:
        for a in self.artists:
            if a.id == aid: return a.name
        return "Artista"


class WeekView(QWidget):
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        self.parent: AgendaPage = parent
        self.date = QDate.currentDate(); self.day_start = QTime(8,0); self.day_end = QTime(22,0); self.step_min = 30
        self.artist_id = None

        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
        self.subtitle = QLabel(""); self.subtitle.setStyleSheet("color:#888; background: transparent;")
        lay.addWidget(self.subtitle)

        grid = QHBoxLayout(); grid.setContentsMargins(0,0,0,0); grid.setSpacing(0)
        lay.addLayout(grid)

        self.tbl_hours = QTableWidget()
        self.tbl_hours.setFixedWidth(80)
        self.tbl_hours.verticalHeader().setVisible(False)
        self.tbl_hours.horizontalHeader().setVisible(True)
        self.tbl_hours.horizontalHeader().setStretchLastSection(True)
        self.tbl_hours.setEditTriggers(self.tbl_hours.NoEditTriggers); self.tbl_hours.setSelectionMode(self.tbl_hours.NoSelection)
        self.tbl_hours.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        grid.addWidget(self.tbl_hours)

        self.tbl = QTableWidget()
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers); self.tbl.setSelectionMode(self.tbl.NoSelection)
        self.tbl.setStyleSheet("QHeaderView::section { background: transparent; }")
        self.tbl.setVerticalScrollMode(self.tbl.ScrollPerPixel)
        grid.addWidget(self.tbl, stretch=1)

        # Sync scroll
        self.tbl.verticalScrollBar().valueChanged.connect(self.tbl_hours.verticalScrollBar().setValue)
        self.tbl.verticalScrollBar().valueChanged.connect(self._update_now_line)

        # Línea “ahora”
        self.now_line_main = QFrame(self.tbl.viewport()); self.now_line_main.setFrameShape(QFrame.HLine)
        self.now_line_main.setStyleSheet("color:#ff6161; background:#ff6161;")
        self.now_line_main.setFixedHeight(2); self.now_line_main.hide()

        self.now_line_hours = QFrame(self.tbl_hours.viewport()); self.now_line_hours.setFrameShape(QFrame.HLine)
        self.now_line_hours.setStyleSheet("color:#ff6161; background:#ff6161;")
        self.now_line_hours.setFixedHeight(2); self.now_line_hours.hide()

        # Timer y resize
        self._timer = QTimer(self); self._timer.setInterval(30_000); self._timer.timeout.connect(self._update_now_line)
        self._timer.start()
        self.tbl.viewport().installEventFilter(self)
        self.tbl_hours.viewport().installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Resize:
            self._update_now_line()
        return super().eventFilter(obj, ev)

    def configure(self, artists: List[Artist], date: QDate, start: QTime, end: QTime, step: int, artist_ids: List[str]):
        self.date = date; self.day_start = start; self.day_end = end; self.step_min = step
        self.artist_id = (artist_ids[0] if artist_ids else (artists[0].id if artists else None))
        artist_name = ""
        for a in artists:
            if a.id == self.artist_id:
                artist_name = a.name; break
        monday = self.date.addDays(-(self.date.dayOfWeek()-1))
        self.subtitle.setText(f"Semana de {monday.toString('dd MMM yyyy')} · Artista: {artist_name}")

    def render(self, appts: List[Appt], artist_lookup):
        monday = self.date.addDays(-(self.date.dayOfWeek()-1))
        steps = int(self.day_start.secsTo(self.day_end) / 60 // self.step_min)
        row_height = 32

        self.tbl.clear(); self.tbl.setRowCount(steps); self.tbl.setColumnCount(7)
        self.tbl.setHorizontalHeaderLabels([(monday.addDays(i)).toString("ddd dd") for i in range(7)])
        hdr = self.tbl.horizontalHeader()
        for c in range(7):
            hdr.setSectionResizeMode(c, QHeaderView.Stretch)
        for r in range(steps): self.tbl.setRowHeight(r, row_height)

        # Horas con header alineado
        self.tbl_hours.clear(); self.tbl_hours.setRowCount(steps); self.tbl_hours.setColumnCount(1)
        self.tbl_hours.horizontalHeader().setFixedHeight(self.tbl.horizontalHeader().height())
        self.tbl_hours.setHorizontalHeaderItem(0, QTableWidgetItem(""))
        t = QTime(self.day_start)
        for r in range(steps):
            txt = t.toString("hh:mm") if t.minute() in (0, 30) else ""
            it = QTableWidgetItem(txt)
            if t.minute() == 30:
                it.setForeground(QColor("#9aa0a6"))
            it.setFlags(Qt.ItemIsEnabled)
            self.tbl_hours.setItem(r, 0, it)
            self.tbl_hours.setRowHeight(r, row_height)
            t = t.addSecs(self.step_min * 60)

        # Línea “ahora”
        self.now_line_main.hide(); self.now_line_hours.hide()
        QTimer.singleShot(0, self._update_now_line)

        if not self.artist_id: return

        # Chips
        for ap in appts:
            if ap.artist_id != self.artist_id: continue
            if not (monday <= ap.date <= monday.addDays(6)): continue

            col = monday.daysTo(ap.date)
            row_start = int(self.day_start.secsTo(ap.start) / 60 // self.step_min)
            row_span  = max(1, ap.duration_min // self.step_min)

            a = artist_lookup(ap.artist_id)
            chip = ApptChip(ap, a, self.parent)
            self.tbl.setSpan(row_start, col, row_span, 1)
            self.tbl.setCellWidget(row_start, col, chip)

    def _update_now_line(self):
        self.now_line_main.hide(); self.now_line_hours.hide()
        if self.date != QDate.currentDate():
            return
        steps = int(self.day_start.secsTo(self.day_end) / 60 // self.step_min)
        if steps <= 0: return

        row_height = self.tbl.rowHeight(0) if self.tbl.rowCount() else 32
        minutes = self.day_start.secsTo(QTime.currentTime()) / 60.0
        if minutes < 0: return
        y_full = (minutes / self.step_min) * row_height
        scroll_px = float(self.tbl.verticalScrollBar().value())
        y_view = int(max(1, min(steps * row_height - 1, y_full - scroll_px)))

        self.now_line_main.setFixedWidth(self.tbl.viewport().width())
        self.now_line_hours.setFixedWidth(self.tbl_hours.viewport().width())
        self.now_line_main.move(0, y_view)
        self.now_line_hours.move(0, y_view)
        self.now_line_main.show(); self.now_line_hours.show()


class MonthView(QWidget):
    """Vista Mes con 7 columnas iguales y día actual destacado."""
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
        self.subtitle = QLabel(""); self.subtitle.setStyleSheet("color:#888; background: transparent;")
        lay.addWidget(self.subtitle)

        self.tbl = QTableWidget(); self.tbl.verticalHeader().setVisible(False); self.tbl.horizontalHeader().setVisible(False)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers); self.tbl.setSelectionMode(self.tbl.NoSelection)
        lay.addWidget(self.tbl, stretch=1)
        self.date = QDate.currentDate()

    def configure(self, artists: List[Artist], date: QDate): self.date = date

    def render(self, appts: List[Appt], artist_lookup):
        y, m = self.date.year(), self.date.month()
        first = QDate(y, m, 1); first_col = first.dayOfWeek() - 1
        days_in_month = first.daysInMonth()
        self.subtitle.setText(self.date.toString("MMMM yyyy"))

        self.tbl.clear(); self.tbl.setRowCount(6); self.tbl.setColumnCount(7)
        hdr = self.tbl.horizontalHeader()
        for c in range(7):
            hdr.setSectionResizeMode(c, QHeaderView.Stretch)
        for r in range(6): self.tbl.setRowHeight(r, 140)

        today = QDate.currentDate()
        byday: Dict[int, List[Appt]] = {}
        for ap in appts:
            if ap.date.month() == m and ap.date.year() == y:
                byday.setdefault(ap.date.day(), []).append(ap)

        day = 1
        for r in range(6):
            for c in range(7):
                cell = QWidget(); lay = QVBoxLayout(cell); lay.setContentsMargins(8,6,8,6); lay.setSpacing(4)
                lbl_day = QLabel(""); lbl_day.setStyleSheet("font-weight:600;"); lay.addWidget(lbl_day)
                if (r == 0 and c < first_col) or day > days_in_month:
                    self.tbl.setCellWidget(r, c, cell)
                    if not (r == 0 and c < first_col): day += 1
                    continue
                lbl_day.setText(f"{day:02d}")
                if QDate(y, m, day) == today:
                    lbl_day.setStyleSheet("font-weight:700; padding:2px 6px; border:1px solid rgba(255,255,255,0.2); border-radius:6px;")

                # Chips compactos (máx 4) con barra por artista
                for ap in byday.get(day, [])[:4]:
                    a = artist_lookup(ap.artist_id); color = a.color if a else "#999"
                    text = f"{ap.start.toString('hh:mm')} · {ap.client_name}"
                    chip = QLabel(text); chip.setToolTip(f"{text}\n{ap.service}")
                    chip.setStyleSheet(f"padding:1px 2px; border-left:4px solid {color};")
                    lay.addWidget(chip)
                lay.addStretch(1)
                self.tbl.setCellWidget(r, c, cell); day += 1


class ListView(QWidget):
    """Vista Lista: todas las citas filtradas (rango amplio)."""
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Hora", "Cliente", "Artista", "Servicio", "Estado"])
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers); self.tbl.setSelectionMode(self.tbl.SingleSelection)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setStyleSheet("QHeaderView::section { background: transparent; }")
        lay.addWidget(self.tbl, stretch=1)

    def render(self, appts: List[Appt], artist_lookup):
        self.tbl.setRowCount(0)
        rows = sorted(appts, key=lambda a: (a.date.toJulianDay(), a.start.hour(), a.start.minute()))
        for ap in rows:
            row = self.tbl.rowCount(); self.tbl.insertRow(row)
            artist = artist_lookup(ap.artist_id)
            self.tbl.setItem(row, 0, QTableWidgetItem(ap.date.toString("dd/MM/yyyy")))
            self.tbl.setItem(row, 1, QTableWidgetItem(ap.start.toString("hh:mm")))
            self.tbl.setItem(row, 2, QTableWidgetItem(ap.client_name))
            self.tbl.setItem(row, 3, QTableWidgetItem(artist.name if artist else ""))
            it_srv = QTableWidgetItem(ap.service or "")
            it_srv.setToolTip(ap.service or "")
            self.tbl.setItem(row, 4, it_srv)
            self.tbl.setItem(row, 5, QTableWidgetItem(ap.status))
