from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, time
import csv
import os
from pathlib import Path
import json

from PyQt5.QtCore import Qt, QDate, QTime, QPoint, pyqtSignal, QTimer, QEvent, QLocale, QRectF
from PyQt5.QtGui import QFontMetrics, QColor, QPainter, QPainterPath, QPixmap, QMouseEvent, QCursor, QIcon, QFont, QTextCharFormat, QPalette
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDateEdit, QFrame, QCheckBox, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QLineEdit, QHeaderView, QSizePolicy, QFileDialog,
    QMessageBox, QMenu, QDialog, QFormLayout, QDialogButtonBox, QSpinBox, QCompleter,
    QPlainTextEdit, QDoubleSpinBox, QToolButton, QCalendarWidget, QAbstractItemView, QToolTip, QTableView
)

# === BD / servicios ===
from services.sessions import (
    list_sessions, update_session, complete_session, cancel_session, create_session
)
# delete_session es opcional
try:
    from services.sessions import delete_session  # type: ignore
except Exception:
    delete_session = None  # fallback

from data.db.session import SessionLocal
from data.models.client import Client
from data.models.artist import Artist as DBArtist

# Permisos + menús
from ui.pages.common import ensure_permission, make_styled_menu

# Helpers compartidos
from ui.pages.common import (
    artist_colors_path, load_artist_colors, fallback_color_for, NoStatusTipMenu, ClickAwayDialog
)

# ==============================
#   MODELOS DE UI (DTOs)
# ==============================
# -------- Settings helpers (horario de agenda) --------
def _settings_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2] / "settings.json",
        Path(__file__).resolve().parents[1] / "settings.json",
        Path.cwd() / "settings.json",
    ]
    for p in candidates:
        try:
            if p.exists():
                return p
        except Exception:
            pass
    return candidates[0]

def _load_agenda_hours() -> tuple:
    start_s, end_s, step = "08:00", "21:30", 30
    try:
        data = json.loads(_settings_path().read_text(encoding="utf-8"))
        ah = (data or {}).get("agenda_hours") or {}
        start_s = str(ah.get("start", start_s))
        end_s   = str(ah.get("end",   end_s))
        step    = int(ah.get("step",  step))
    except Exception:
        pass

    def _qt(t, fallback):
        try:
            h, m = [int(x) for x in t.split(":")]
            return QTime(h, m)
        except Exception:
            return fallback

    qs = _qt(start_s, QTime(8, 0))
    qe = _qt(end_s or "21:30", QTime(21, 30))
    if not qe > qs:
        qe = QTime(min(23, qs.hour() + 1), qs.minute())
    if step not in (5, 10, 15, 20, 30, 60):
        step = 30
    return qs, qe, step

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
    try:
        ov = load_artist_colors()
        key = str(int(aid)).lower()
        if key in ov and ov[key]:
            return ov[key]
    except Exception:
        pass
    return fallback_color_for(idx_fallback)

def _state_color_hex(state: str) -> str:
    m = {
        "Activa":      "#3FBF8A",
        "En espera":   "#E0B252",
        "Completada":  "#67C1E8",
        "Cancelada":   "#E57373",
        "No-show":     "#B38AE3",
    }
    return m.get(state, "#9AA0A6")

# ==============================
#   ESTILO POR ESTADO
# ==============================
def _status_style(bg_override: str, artist_hex: str, state: str) -> str:
    def hex_to_rgba(h, a=1.0):
        h = h.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{a})"

    base = artist_hex or "#6b7280"
    if state == "Completada":
        back = hex_to_rgba(base, 0.92)
    elif state == "Cancelada":
        back = hex_to_rgba(base, 0.55)
    elif state == "En espera":
        back = hex_to_rgba(base, 0.82)
    else:  # Activa / default
        back = hex_to_rgba(base, 0.96)

    if bg_override:
        back = bg_override

    state_bar = _state_color_hex(state)

    return f"""
    QFrame {{
        background: {back};
        border: 1px solid rgba(255,255,255,0.10);
        border-left: 6px solid {state_bar};
        border-radius: 8px;
        color: #f6f7fb;
    }}
    QFrame:hover {{
        background: {hex_to_rgba(base, 1.0)};
    }}
    QLabel {{ background: transparent; }}
    """
def _surface_color_from(widget, default="#1f242b") -> str:
    """Toma el color de fondo efectivo del widget; si es claro (blanco/gris) usa default."""
    try:
        c = widget.palette().color(QPalette.Window)
        # luminosidad perceptual
        lum = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255.0
        name = c.name().lower()
        if name not in ("#ffffff", "#fff") and lum < 0.6:
            return name
    except Exception:
        pass
    return default


class PillHeader(QHeaderView):
    def __init__(self, orientation, parent=None, bg="#1f242b", fg="#e6eaf0"):
        super().__init__(orientation, parent)
        self._bg = QColor(bg)
        self._fg = QColor(fg)
        self.setDefaultAlignment(Qt.AlignCenter)
        self.setHighlightSections(False)
        self.setSortIndicatorShown(False)
        self.setSectionsClickable(False)
        # Fondo transparente para que solo se vean las 'cards'
        self.setStyleSheet("QHeaderView{background:transparent;border:none;} QHeaderView::section{background:transparent;border:none;}")

    def paintSection(self, painter, rect, logicalIndex):
        if not rect.isValid():
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        r = QRectF(rect.adjusted(6, 4, -6, -4))
        path = QPainterPath()
        path.addRoundedRect(r, 16.0, 16.0)

        painter.setPen(Qt.NoPen)
        painter.setBrush(self._bg)
        painter.drawPath(path)

        txt = str(self.model().headerData(logicalIndex, self.orientation(), Qt.DisplayRole) or "")
        painter.setPen(self._fg)
        painter.drawText(r, Qt.AlignCenter, txt)

        painter.restore()

    def setColors(self, bg: str, fg: str = "#e6eaf0"):
        self._bg = QColor(bg)
        self._fg = QColor(fg)
        self.viewport().update()


# ==============================
# DIÁLOGOS (frameless/arrastrables)
# ==============================
class _FramelessDialog(QDialog):
    def __init__(self, title: str, parent=None, close_on_click_outside: bool = False):
        super().__init__(parent)
        self._close_on_outside = close_on_click_outside

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

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
                if not self.frameGeometry().contains(ev.globalPos()):
                    self.reject()
                    return True
        return super().eventFilter(obj, ev)

class NewApptDialog(_FramelessDialog):
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
        self.cbo_artist.setCurrentIndex(-1)
        form.addRow("Tatuador:", self.cbo_artist)

        self.cb_client = QComboBox()
        self.cb_client.setEditable(True)
        self.cb_client.setInsertPolicy(QComboBox.NoInsert)
        for cid, cname in clients:
            self.cb_client.addItem(cname, cid)
        completer = QCompleter([n for _, n in clients], self.cb_client)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.cb_client.setCompleter(completer)
        self.cb_client.setCurrentIndex(-1)
        form.addRow("Cliente:", self.cb_client)

        self.ed_service = QPlainTextEdit(); self.ed_service.setPlaceholderText("Servicio / notas")
        self.ed_service.setFixedHeight(80)
        form.addRow("Servicio:", self.ed_service)

        self.cbo_status = QComboBox(); self.cbo_status.addItems(["Activa", "En espera", "Completada", "Cancelada"])
        form.addRow("Estado:", self.cbo_status)

        self.body_l.addLayout(form)

        btns = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancelar"); self.btn_cancel.setObjectName("cancelbtn")
        self.btn_ok = QPushButton("Crear"); self.btn_ok.setObjectName("okbtn")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self.accept)
        btns.addStretch(1); btns.addWidget(self.btn_cancel); btns.addWidget(self.btn_ok)
        self.body_l.addLayout(btns)

    def values(self) -> dict:
        date = self.dt_date.date()
        h, m = self.sp_hour.value(), self.sp_min.value()
        start = datetime(date.year(), date.month(), date.day(), h, m, 0)
        dur   = self.sp_dur.value()
        client_id = self.cb_client.currentData()
        client_name = self.cb_client.currentText().strip()
        aid = self.cbo_artist.currentData()
        artist_id = int(aid) if aid is not None else None

        client_id = self.cb_client.currentData()
        client_name = self.cb_client.currentText().strip()

        return {
            "artist_id": artist_id,
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

        self._orig_artist_id = ap.artist_id
        idx = self.cbo_artist.findData(ap.artist_id)
        if idx < 0:
            try:
                idx = self.cbo_artist.findData(int(ap.artist_id))
            except Exception:
                idx = -1
        self.cbo_artist.setCurrentIndex(idx)

        form.addRow("Tatuador:", self.cbo_artist)

        self.cb_client = QComboBox()
        self.cb_client.setEditable(True)
        self.cb_client.setInsertPolicy(QComboBox.NoInsert)
        for cid, cname in clients:
            self.cb_client.addItem(cname, cid)

        completer = QCompleter([n for _, n in clients], self.cb_client)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.cb_client.setCompleter(completer)

        self._orig_client_id = ap.client_id
        self._orig_client_name = ap.client_name

        idx_c = self.cb_client.findData(ap.client_id) if ap.client_id is not None else -1
        if idx_c >= 0:
            self.cb_client.setCurrentIndex(idx_c)
        else:
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

        aid = self.cbo_artist.currentData()
        if aid is None:
            aid = self._orig_artist_id
        artist_id = int(aid) if aid is not None else None

        cid = self.cb_client.currentData()
        if cid is None:
            cid = self._orig_client_id
        client_id = int(cid) if cid is not None else None

        client_name = (self.cb_client.currentText() or "").strip() or self._orig_client_name or None

        return {
            "artist_id": artist_id,
            "client_id": client_id,
            "client_name": client_name,
            "notes": (self.ed_service.toPlainText() or "").strip(),
            "status": self.cbo_status.currentText(),
            "start": start,
            "end": start + timedelta(minutes=dur),
        }

class PaymentDialog(_FramelessDialog):
    def __init__(self, parent=None, preset: Optional[dict] = None, title="Cobro"):
        super().__init__(title, parent)
        preset = preset or {}

        form = QFormLayout(); form.setContentsMargins(0,0,0,0)

        self.sp_amount = QDoubleSpinBox()
        self.sp_amount.setDecimals(2); self.sp_amount.setRange(0.00, 1_000_000.00)
        self.sp_amount.setSingleStep(50.00)
        self.sp_amount.setValue(float(preset.get("amount", 0.00)))
        form.addRow("Precio:", self.sp_amount)

        self.sp_comm = QDoubleSpinBox()
        self.sp_comm.setDecimals(2); self.sp_comm.setRange(0.00, 100.00)
        self.sp_comm.setSingleStep(5.00)
        self.sp_comm.setValue(float(preset.get("commission_pct", 0.00)))
        form.addRow("Comisión (%):", self.sp_comm)

        self.lbl_comm_calc = QLabel("Comisión: $0.00"); self.lbl_comm_calc.setStyleSheet("background:transparent;")
        form.addRow("", self.lbl_comm_calc)

        self.cbo_method = QComboBox()
        self.cbo_method.addItems(["Efectivo", "Tarjeta", "Transferencia", "Mixto"])
        if preset.get("method"):
            i = self.cbo_method.findText(str(preset["method"]), Qt.MatchFixedString)
            if i >= 0: self.cbo_method.setCurrentIndex(i)
        form.addRow("Método de pago:", self.cbo_method)

        self.ed_note = QPlainTextEdit()
        self.ed_note.setPlaceholderText("Nota / referencia de cobro…")
        self.ed_note.setFixedHeight(70)
        self.ed_note.setPlainText(str(preset.get("note") or ""))
        form.addRow("Nota:", self.ed_note)

        self.body_l.addLayout(form)

        btns = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancelar"); self.btn_cancel.setObjectName("cancelbtn")
        self.btn_ok = QPushButton("OK"); self.btn_ok.setObjectName("okbtn")
        self.btn_cancel.clicked.connect(self.reject); self.btn_ok.clicked.connect(self.accept)
        btns.addStretch(1); btns.addWidget(self.btn_cancel); btns.addWidget(self.btn_ok)
        self.body_l.addLayout(btns)

        def _recalc():
            amount = float(self.sp_amount.value())
            pct = float(self.sp_comm.value())
            comm_amount = round(amount * pct / 100.0, 2)
            self.lbl_comm_calc.setText(f"Comisión: ${comm_amount:,.2f}")
        self.sp_amount.valueChanged.connect(_recalc)
        self.sp_comm.valueChanged.connect(_recalc)
        _recalc()

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

        lay = QVBoxLayout(self); lay.setContentsMargins(8, 6, 8, 6); lay.setSpacing(2)

        title = QLabel(f"{ap.client_name}")
        title.setStyleSheet("font-weight:600;")
        subtitle = QLabel(f"{ap.service} • {ap.start.toString('hh:mm')}")
        subtitle.setStyleSheet("color: rgba(255,255,255,0.85); font-size:12px;")

        for lbl in (title, subtitle):
            lbl.setWordWrap(True); lbl.setToolTip(lbl.text())
            lay.addWidget(lbl)

        color = artist.color if artist else "#666"
        self.setStyleSheet(_status_style("", color, ap.status))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.controller._open_appt_detail(self.ap)
        super().mouseReleaseEvent(e)

    def contextMenuEvent(self, e):
        self.controller._show_appt_context_menu(self.ap, self.mapToGlobal(e.pos()))

# ==============================
#   AGENDA PAGE
# ==============================
class MiniCalendar(QCalendarWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLocale(QLocale(QLocale.Spanish, QLocale.Mexico))
        self.setGridVisible(False)
        self.setFirstDayOfWeek(Qt.Sunday)
        try:
            self.setHorizontalHeaderFormat(QCalendarWidget.SingleLetterDayNames)
        except Exception:
            self.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)

        self.setMouseTracking(True)
        self._hover_pos = QPoint(-1, -1)
        view = self.findChild(QTableView, "qt_calendar_calendarview")
        if view:
            view.viewport().installEventFilter(self)
            view.viewport().setMouseTracking(True)
            view.setStyleSheet(
                "QTableView{background:transparent;border:none;}"
                "QTableView::viewport{background:transparent;border:none;}"
            )
        view.setFrameShape(QFrame.NoFrame)
        view.setShowGrid(False)

        if view.horizontalHeader():
            hh = view.horizontalHeader()
            hh.setSectionResizeMode(QHeaderView.Stretch)
            hh.setMinimumSectionSize(0)
            hh.setDefaultSectionSize(22)
            hf = hh.font()
            hf.setCapitalization(QFont.AllUppercase)
            hf.setPointSizeF(9.0)
            hh.setFont(hf)
            hh.setDefaultAlignment(Qt.AlignCenter)
            hh.setAutoFillBackground(False)
            try:
                hh.viewport().setAutoFillBackground(False)
            except Exception:
                pass
            p = hh.parentWidget()
            if p:
                p.setStyleSheet("background:transparent;border:none;")
            hh.setStyleSheet(
                "QHeaderView{background:transparent;border:none;}"
                "QHeaderView::section{"
                " background:transparent;"
                " background-color: transparent;"
                " border:none;"
                " color:#c7cbd1;"
                " font-weight:700;"
                " padding:2px 0;"
                " margin:0;"
                " text-align:center;"
                "}"
            )
        if view.verticalHeader():
            vh = view.verticalHeader()
            vh.setSectionResizeMode(QHeaderView.Stretch)
            vh.setMinimumSectionSize(18)
            vh.setDefaultSectionSize(18)

        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#e6eaf0"))
        self.setWeekdayTextFormat(Qt.Saturday, fmt)
        self.setWeekdayTextFormat(Qt.Sunday, fmt)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(372)

        prev = self.findChild(QToolButton, "qt_calendar_prevmonth")
        nextb = self.findChild(QToolButton, "qt_calendar_nextmonth")
        for btn, txt in ((prev, "‹"), (nextb, "›")):
            if btn:
                btn.setIcon(QIcon())
                btn.setText(txt)
                btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setMinimumSize(30, 30)
                btn.setFixedSize(30, 30)
        self._mb = self.findChild(QToolButton, "qt_calendar_monthbutton")
        self._yb = self.findChild(QToolButton, "qt_calendar_yearbutton")
        for b in (self._mb, self._yb):
            if b:
                b.setCursor(Qt.ArrowCursor)
                b.setFocusPolicy(Qt.NoFocus)
                b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                b.setMinimumWidth(0)
                b.installEventFilter(self)
            if self._yb:
                self._yb.hide()

            self.currentPageChanged.connect(lambda y, m: self._update_nav_labels())
            self._update_nav_labels()

        nav = self.findChild(QWidget, "qt_calendar_navigationbar")
        if nav and nav.layout():
            lay = nav.layout()
            for w in (prev, self._mb, self._yb, nextb):
                if w:
                    lay.removeWidget(w)
            if self._mb: lay.addWidget(self._mb, 0, Qt.AlignLeft)
            if self._yb: lay.addWidget(self._yb, 0, Qt.AlignLeft)
            lay.addStretch(1)
            if prev:  lay.addWidget(prev,  0, Qt.AlignRight)
            if nextb: lay.addWidget(nextb, 0, Qt.AlignRight)

        self.setStyleSheet("""
        /* QCalendarWidget base y todo su árbol SIN fondo */
        QCalendarWidget, 
        QCalendarWidget * {
            background: transparent;
            border: none;
        }
        /* Barra de navegación */
        QCalendarWidget QWidget#qt_calendar_navigationbar {
            background: transparent;
            border: none;
            margin: 8px 8px 4px 8px;
            padding: 0;
        }
        /* Flechas: texto puro y centrado + hover con pill */
        QCalendarWidget QToolButton#qt_calendar_prevmonth,
        QCalendarWidget QToolButton#qt_calendar_nextmonth {
            min-width: 30px;  max-width: 30px;
            min-height: 30px; max-height: 30px;
            border: none;
            background: transparent;
            color: #e6eaf0;
            font-weight: 800;
            font-size: 20px;
            padding: 0;
            margin: 0;
            text-align: center;
            qproperty-autoRaise: true;
        }
        QCalendarWidget QToolButton#qt_calendar_prevmonth:hover,
        QCalendarWidget QToolButton#qt_calendar_nextmonth:hover {
            border-radius: 15px;
            background: rgba(255,255,255,0.10);
            border: 1px solid rgba(255,255,255,0.18);
        }
        /* Título Mes Año (sin indicador de menú) */
        QCalendarWidget QToolButton#qt_calendar_monthbutton,
        QCalendarWidget QToolButton#qt_calendar_yearbutton {
            border: none; 
            background: transparent; 
            color: #e6eaf0;
            font-weight: 700; 
            font-size: 20px; 
            padding: 0 6px; 
            margin: 0 2px; 
            min-width: 0;
        }
        QCalendarWidget QToolButton#qt_calendar_monthbutton::menu-indicator,
        QCalendarWidget QToolButton#qt_calendar_yearbutton::menu-indicator { 
            image: none; width: 0px; 
        }
        /* Vista de tabla y su header: todo transparente, sin esquinas ni franja */
        QCalendarWidget QTableView,
        QCalendarWidget QTableView::viewport,
        QCalendarWidget QTableView QHeaderView,
        QCalendarWidget QTableView QHeaderView::section,
        QCalendarWidget QTableCornerButton::section {
            background: transparent;
            background-color: transparent;
            border: none;
        }
        /* Área de celdas (números) */
        QCalendarWidget QAbstractItemView {
            background: transparent;
            color: #e6eaf0;
            font-size: 8.4px;
            outline: 0;
            border: none;
        }
    """)

    def wheelEvent(self, e):
        e.ignore()

    def eventFilter(self, obj, ev):
        if obj in (getattr(self, "_mb", None), getattr(self, "_yb", None)):
            if ev.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
                return True

        if ev.type() == QEvent.MouseMove:
            self._hover_pos = ev.pos()
            self.updateCells()
        elif ev.type() in (QEvent.Leave, QEvent.MouseButtonPress):
            self._hover_pos = QPoint(-1, -1)
            self.updateCells()
        elif ev.type() == QEvent.Wheel:
            return True
        return super().eventFilter(obj, ev)

    def paintCell(self, painter: QPainter, rect, date: QDate):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        in_month = (date.month() == self.monthShown() and date.year() == self.yearShown())
        is_today = (date == QDate.currentDate())
        is_selected = (date == self.selectedDate())

        f = painter.font()
        f.setPointSizeF(8.4)
        painter.setFont(f)

        rside = min(rect.width(), rect.height())
        d = int(rside * 0.96)
        circle = rect.adjusted((rect.width()-d)//2, (rect.height()-d)//2,
                            -(rect.width()-d)//2, -(rect.height()-d)//2)

        # 1) HOY
        if is_today and in_month:
            painter.setBrush(QColor(155, 185, 255, 140))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(circle)

        # 2) SELECCIONADO
        if is_selected:
            painter.setBrush(QColor(155, 185, 255, 95))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(circle)

        # 3) HOVER
        hovered = circle.contains(self._hover_pos)
        if hovered and in_month:
            painter.setBrush(QColor(255, 255, 255, 38))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(circle)

        if is_selected:
            pen = QColor("#0e1217")
        else:
            pen = QColor("#e6eaf0" if in_month else "#656b73")
        painter.setPen(pen)
        painter.drawText(rect, Qt.AlignCenter, str(date.day()))

        painter.restore()
    
    def _update_nav_labels(self):
        if not hasattr(self, "_mb"):
            return
        y = self.yearShown()
        m = self.monthShown()
        month_name = QDate(y, m, 1).toString("MMMM")
        if month_name:
            month_name = month_name[:1].upper() + month_name[1:]
        self._mb.setText(f"{month_name} {y}")

        f = self._mb.font()
        f.setPointSizeF(21.0)
        f.setBold(True)
        self._mb.setFont(f)

class AgendaPage(QWidget):
    crear_cita = pyqtSignal()
    abrir_cita = pyqtSignal(dict)

    def showEvent(self, e):
        super().showEvent(e)
        self._load_artists_from_db()
        self._rebuild_sidebar_artists()
        self._refresh_all()

    def _reload_colors_if_changed(self):
        try:
            p = Path(artist_colors_path())
            mt = p.stat().st_mtime if p.exists() else 0
            if mt != self._colors_mtime:
                self._colors_mtime = mt
                self._load_artists_from_db()
                if hasattr(self, "artists_checks_box"):
                    self._rebuild_sidebar_artists()
                self._refresh_all()
        except Exception:
            pass

    def __init__(self):
        super().__init__()

        # ------- Estado -------
        self.current_date: QDate = QDate.currentDate()
        self.current_view: str = "day"
        self.selected_artist_ids: List[str] = []
        self.selected_status: str = "Todos"
        self.search_text: str = ""

        self.day_start = QTime(8, 0)
        self.day_end   = QTime(22, 0)
        self.step_min  = 30

        s, e, step = _load_agenda_hours()
        self.day_start = s
        self.day_end   = e
        self.step_min  = step


        self.artists: List[Artist] = []
        self.appts: List[Appt] = []
        self._clients_cache: List[Tuple[int, str]] = []

        self._load_artists_from_db()
        self._load_clients_minimal()


        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)


        self.sidebar = self._build_sidebar()
        self.sidebar.setFixedWidth(260)
        root.addWidget(self.sidebar)

        right_wrap = QFrame()
        right_v = QVBoxLayout(right_wrap)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(8)

        self.toolbar = self._build_toolbar()
        right_v.addWidget(self.toolbar)

        self.views_stack = QStackedWidget()
        right_v.addWidget(self.views_stack, 1)
        root.addWidget(right_wrap, 1)

        self.day_view   = DayView(self)
        self.week_view  = WeekView(self)
        self.month_view = MonthView(self)
        self.list_view  = ListView(self)

        self.views_stack.addWidget(self.day_view)
        self.views_stack.addWidget(self.week_view)
        self.views_stack.addWidget(self.month_view)
        self.views_stack.addWidget(self.list_view)

        self.list_view.tbl.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_view.tbl.customContextMenuRequested.connect(self._show_list_context_menu)
        self.list_view.tbl.itemDoubleClicked.connect(self._open_from_list)

        self.sidebar_collapsed = False
        self._artist_label_cache: Dict[str, str] = {}

        self._rebuild_sidebar_artists()

        self._refresh_all()
        self._reload_colors_timer = QTimer(self)
        self._reload_colors_timer.setInterval(3000)
        self._reload_colors_timer.timeout.connect(self._reload_colors_if_changed)
        self._reload_colors_timer.start()
        self._colors_mtime = None

    def apply_hours_from_settings(self):
        s, e, step = _load_agenda_hours()
        self.day_start, self.day_end, self.step_min = s, e, step
        self._refresh_all()

    def _on_view_menu(self, txt: str):
        mapping = {"Día": ("day", 0), "Semana": ("week", 1), "Mes": ("month", 2), "Lista": ("list", 3)}
        self.current_view, idx = mapping.get(txt, ("day", 0))
        self.btn_view.setText(f"{txt} ▾")
        self.views_stack.setCurrentIndex(idx)
        self._refresh_all()

    def _sync_date_widgets(self):
        if hasattr(self, "lbl_date"):
            self.lbl_date.setText(self.current_date.toString("d 'de' MMMM 'de' yyyy"))
        if hasattr(self, "cal"):
            self.cal.setSelectedDate(self.current_date)


    # ---------- Toolbar ----------
    def _build_toolbar(self) -> QWidget:
        wrap = QFrame(); wrap.setObjectName("Toolbar")
        lay = QHBoxLayout(wrap); lay.setContentsMargins(10, 8, 10, 8); lay.setSpacing(8)

        self.btn_today = QPushButton("Hoy")
        self.btn_today.setObjectName("TodayBtn")

        self.btn_prev = QToolButton()
        self.btn_prev.setObjectName("NavBtn")
        self.btn_prev.setText("‹")
        self.btn_prev.setAutoRaise(True)
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        self.btn_prev.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.btn_prev.setFixedSize(40, 40)

        self.btn_next = QToolButton()
        self.btn_next.setObjectName("NavBtn")
        self.btn_next.setText("›")
        self.btn_next.setAutoRaise(True)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.btn_next.setFixedSize(40, 40)

        self.btn_today.clicked.connect(self._go_today)
        self.btn_prev.clicked.connect(self._go_prev)
        self.btn_next.clicked.connect(self._go_next)

        self.btn_today.setFixedHeight(40)
        self.btn_today.setStyleSheet("border-radius: 20px;")
        lay.addWidget(self.btn_today)
        lay.addWidget(self.btn_prev)
        lay.addWidget(self.btn_next)

        self.lbl_date = QLabel(self.current_date.toString("d 'de' MMMM 'de' yyyy"))
        self.lbl_date.setObjectName("BigDate")
        self.lbl_date.setStyleSheet("background:transparent;")
        lay.addWidget(self.lbl_date)

        lay.addStretch(1)

        self.btn_view = QToolButton()
        self.btn_view.setObjectName("OutlinePill")
        self.btn_view.setText("Día ▾")
        self.btn_view.setPopupMode(QToolButton.InstantPopup)
        self.btn_view.setCursor(Qt.PointingHandCursor)
        self.btn_view.setFixedHeight(40)

        menu_view = make_styled_menu(self.btn_view)
        for label in ("Día", "Semana", "Mes", "Lista"):
            act = menu_view.addAction(label)
            act.triggered.connect(lambda _=False, txt=label: self._on_view_menu(txt))
        self.btn_view.setMenu(menu_view)
        lay.addWidget(self.btn_view)

        self.btn_export = QToolButton()
        self.btn_export.setObjectName("OutlinePill")
        self.btn_export.setText("Exportar ▾")
        self.btn_export.setPopupMode(QToolButton.InstantPopup)
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setFixedHeight(40)

        m = make_styled_menu(self.btn_export)
        act_d = m.addAction("Día actual (CSV)")
        act_s = m.addAction("Semana (CSV)")
        act_l = m.addAction("Lista (CSV)")
        act_d.triggered.connect(lambda: self._export_csv("day"))
        act_s.triggered.connect(lambda: self._export_csv("week"))
        act_l.triggered.connect(lambda: self._export_csv("list"))
        self.btn_export.setMenu(m)
        lay.addWidget(self.btn_export)

        wrap.setStyleSheet("""
        /* Hoy: pill más grande */
        QPushButton#TodayBtn {
            font-size: 22px;
            font-weight: 600;
            padding: 9px 20px;
            border: 1px solid rgba(255,255,255,0.25);
            border-radius: 22px;   /* pill */
            background: transparent;
            color: #e6eaf0;
        }
        QPushButton#TodayBtn:hover {
            background: rgba(255,255,255,0.08);
        }
        /* Flechas tipo mini-calendario — texto más grande y centrado */
        QToolButton#NavBtn {
            min-width: 40px;  max-width: 40px;
            min-height: 40px; max-height: 40px;
            border: none;
            background: transparent;
            color: #e6eaf0;
            font-weight: 800;
            font-size: 28px;   /* chevron grande */
            padding: 0;
            margin: 0;
            qproperty-autoRaise: true;
            text-align: center;
        }
        QToolButton#NavBtn:hover {
            border-radius: 20px;
            background: rgba(255,255,255,0.10);
            border: 1px solid rgba(255,255,255,0.18);
        }
        /* Fecha grande */
        QLabel#BigDate {
            font-size: 22px;
            font-weight: 700;
            padding: 0 10px;
            background: transparent;
        }
        /* Botones desplegables con el mismo look “Hoy” / +Nueva cita */
        QToolButton#OutlinePill {
            font-size: 18px;
            font-weight: 600;
            padding: 8px 18px;
            border: 1px solid rgba(255,255,255,0.25);
            border-radius: 20px;    /* igual que +Nueva cita */
            background: transparent;
            color: #e6eaf0;
        }
        QToolButton#OutlinePill:hover {
            background: rgba(255,255,255,0.08);
        }
        QToolButton#OutlinePill::menu-indicator { image: none; width: 0px; height: 0px; }
        QToolButton#OutlinePill:hover {
            background: rgba(255,255,255,0.08);
        }
        /* ← elimina la flecha extra del QToolButton, dejando solo la del texto "▾" */
        QToolButton#OutlinePill::menu-indicator {
            image: none; width: 0px; height: 0px;
        }
        """)
        return wrap

    def _build_sidebar(self) -> QWidget:
        w = QFrame(); w.setObjectName("Sidebar")
        lay = QVBoxLayout(w); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(12)

        def title(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet("background: transparent; font-weight: 600;")
            return lbl

        # 1) NUEVA CITA
        self.btn_new_side = QPushButton("+ Nueva cita")
        self.btn_new_side.setObjectName("CTA")
        self.btn_new_side.setFixedHeight(40)
        self.btn_new_side.setStyleSheet("padding: 8px 14px;")
        self.btn_new_side.clicked.connect(self._open_new_appt_dialog)
        lay.addWidget(self.btn_new_side)

        # 2) MINICALENDAR
        self.cal = MiniCalendar(self)
        self.cal.setSelectedDate(self.current_date)
        self.cal.clicked.connect(self._on_calendar_clicked)
        lay.addWidget(self.cal)

        # 3) BUSCAR CLIENTE
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar cliente…")
        self.search.textChanged.connect(self._on_filter_changed)
        lay.addWidget(self.search)

        # Tatuadores
        lay.addWidget(title("Tatuadores"))
        self.artists_checks_box = QVBoxLayout()
        self.artists_checks_box.setContentsMargins(0, 0, 0, 0)
        self.artists_checks_box.setSpacing(6)
        lay.addLayout(self.artists_checks_box)

        # Estado
        lay.addWidget(title("Estado"))
        self.cbo_status = QComboBox()
        self.cbo_status.addItems(["Todos", "Activa", "Completada", "Cancelada", "En espera"])
        self.cbo_status.currentTextChanged.connect(self._on_filter_changed)
        lay.addWidget(self.cbo_status)

        lay.addStretch(1)
        return w

    # ---------- Sidebar helpers ----------
    def _toggle_sidebar(self):
        self.sidebar_collapsed = not self.sidebar_collapsed
        if self.sidebar_collapsed:
            self.sidebar.setFixedWidth(56)
            for aid, chk in self.artist_checks.items():
                self._artist_label_cache[aid] = chk.text()
                chk.setText("")
                chk.setToolTip(self._artist_label_cache[aid])
            self.search.setVisible(False)
            self.cbo_status.setVisible(False)
            if hasattr(self, "btn_new_side"): self.btn_new_side.setVisible(False)
            if hasattr(self, "cal"): self.cal.setVisible(False)
            if hasattr(self, "toolbar_left_spacer"):
                self.toolbar_left_spacer.setFixedWidth(56)
        else:
            self.sidebar.setFixedWidth(240)
            for aid, chk in self.artist_checks.items():
                lbl = self._artist_label_cache.get(aid, "")
                chk.setText(lbl)
                chk.setToolTip("")
            self.search.setVisible(True)
            self.cbo_status.setVisible(True)
            if hasattr(self, "btn_new_side"): self.btn_new_side.setVisible(True)
            if hasattr(self, "cal"): self.cal.setVisible(True)
            if hasattr(self, "toolbar_left_spacer"):
                self.toolbar_left_spacer.setFixedWidth(240)

    def _select_all_artists(self, value: bool):
        for chk in self.artist_checks.values():
            chk.blockSignals(True)
            chk.setChecked(value)
            chk.blockSignals(False)
        self._on_filter_changed()

    def _on_calendar_clicked(self, date: QDate):
        self.current_date = date
        self._sync_date_widgets()
        self._refresh_all()

    # ---------- Sidebar ----------
    def _rebuild_sidebar_artists(self):
        prev_selected = {aid for aid, chk in getattr(self, "artist_checks", {}).items() if chk.isChecked()}
        while self.artists_checks_box.count():
            item = self.artists_checks_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.artist_checks = {}
        for a in self.artists:
            chk = QCheckBox(a.name)
            chk.setChecked((a.id in prev_selected) or (not prev_selected))
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

        if self.sidebar_collapsed:
            for aid, chk in self.artist_checks.items():
                self._artist_label_cache[aid] = chk.text()
                chk.setText("")
                chk.setToolTip(self._artist_label_cache[aid])

        self._on_filter_changed()

    # ---------- Navegación temporal ----------
    def _go_today(self):
        self.current_date = QDate.currentDate()
        self._sync_date_widgets()
        self._refresh_all()

    def _go_prev(self):
        if   self.current_view == "day":   self.current_date = self.current_date.addDays(-1)
        elif self.current_view == "week":  self.current_date = self.current_date.addDays(-7)
        elif self.current_view == "month": self.current_date = self.current_date.addMonths(-1)
        else:                              self.current_date = self.current_date.addDays(-1)
        self._sync_date_widgets()
        self._refresh_all()

    def _go_next(self):
        if   self.current_view == "day":   self.current_date = self.current_date.addDays(1)
        elif self.current_view == "week":  self.current_date = self.current_date.addDays(7)
        elif self.current_view == "month": self.current_date = self.current_date.addMonths(1)
        else:                              self.current_date = self.current_date.addDays(1)
        self._sync_date_widgets()
        self._refresh_all()

    def _on_date_changed(self, d: QDate):
        self.current_date = d
        self._sync_date_widgets()
        self._refresh_all()

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

        if val.get("artist_id") is None:
            QMessageBox.warning(self, "Nueva cita", "Selecciona un tatuador.")
            return

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

    def _show_list_context_menu(self, pos):
        row = self.list_view.tbl.rowAt(pos.y())
        ap = self._find_appt_by_row(row)
        if not ap:
            return

        gpos = self.list_view.tbl.viewport().mapToGlobal(pos)
        self._show_appt_context_menu(ap, gpos)


    def _open_appt_detail(self, ap: Appt):
        dlg = ClickAwayDialog("Detalle de cita", self)

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

        btns = QHBoxLayout()
        b_edit = QPushButton("Editar")
        b_state = QPushButton("Cambiar estado")
        b_close = QPushButton("Cerrar")
        for b in (b_edit, b_state, b_close):
            b.setObjectName("okbtn")
        btns.addStretch(1)
        btns.addWidget(b_edit)
        btns.addWidget(b_state)
        btns.addWidget(b_close)
        dlg.body_l.addLayout(btns)

        def do_edit():
            dlg.close()
            self._edit_appt(ap)

        def do_state():
            m = make_styled_menu(dlg)
            acts = {
                "Activa": m.addAction("Activa"),
                "En espera": m.addAction("En espera"),
                "Completada": m.addAction("Completada"),
                "Cancelada": m.addAction("Cancelada"),
            }
            chosen = m.exec_(QCursor.pos())
            if not chosen:
                return
            for k, v in acts.items():
                if v is chosen:
                    self._set_status(ap, k)
                    break

        b_edit.clicked.connect(do_edit)
        b_state.clicked.connect(do_state)
        b_close.clicked.connect(dlg.close)

        dlg.exec_()

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
            if val["status"] == "Completada":
                complete_session(int(ap.id), {})
            elif val["status"] == "Cancelada":
                cancel_session(int(ap.id))
            QMessageBox.information(self, "Cita", "Cambios guardados.")
        except Exception as e:
            QMessageBox.critical(self, "Agenda", f"No se pudo guardar: {e}")
        self._refresh_all()

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
                update_session(int(ap.id), {"status": status, "artist_id": int(ap.artist_id)})
            QMessageBox.information(self, "Cita", "Estado actualizado.")
        except Exception as e:
            QMessageBox.critical(self, "Agenda", f"No se pudo actualizar: {e}")
        self._refresh_all()

    def _show_appt_context_menu(self, ap: Appt, global_pos: QPoint):
        m = make_styled_menu(self)

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
            dlg = PaymentDialog(self)
            if dlg.exec_() == QDialog.Accepted:
                payload = dlg.values()
                try:
                    complete_session(int(ap.id), payload)
                    QMessageBox.information(self, "Cita", "Cobro registrado.")
                except Exception as e:
                    msg = str(e).lower()
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
            self._open_appt_detail(ap)
            return

    # -------- Export genérico (día/semana/lista) --------
    def _export_csv(self, scope: str = "day"):
        if not ensure_permission(self, "agenda", "export"):
            return

        rows_all = self._filter_appts()

        if scope == "day":
            rows = [a for a in rows_all if a.date == self.current_date]
            if not rows:
                QMessageBox.information(self, "Exportar", "No hay citas en el día seleccionado.")
                return
            default_name = f"agenda_{self.current_date.toString('yyyyMMdd')}.csv"

        elif scope == "week":
            monday = self.current_date.addDays(-(self.current_date.dayOfWeek()-1))
            sunday = monday.addDays(6)
            rows = [a for a in rows_all if monday <= a.date <= sunday]
            if not rows:
                QMessageBox.information(self, "Exportar", "No hay citas en la semana seleccionada.")
                return
            default_name = f"agenda_semana_{monday.toString('yyyyMMdd')}_{sunday.toString('yyyyMMdd')}.csv"

        else:  # list
            rows = rows_all
            if not rows:
                QMessageBox.information(self, "Exportar", "No hay citas para exportar.")
                return
            default_name = f"agenda_lista_{self.current_date.toString('yyyyMMdd')}.csv"

        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar CSV",
            os.path.join(os.path.expanduser("~"), default_name),
            "CSV (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["Fecha", "Hora", "Cliente", "Artista", "Servicio", "Estado"])
                for ap in sorted(rows, key=lambda a: (a.date.toJulianDay(), a.start.hour(), a.start.minute())):
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

        counts: Dict[str, int] = {}
        for ap in rows:
            counts[ap.artist_id] = counts.get(ap.artist_id, 0) + 1
        for aid, chk in self.artist_checks.items():
            base = self._artist_label_cache.get(aid, chk.text()) or ""
            name_only = base if "(" not in base else base.split("(")[0].strip()
            label = f"{name_only} ({counts.get(aid, 0)})" if not self.sidebar_collapsed else ""
            if not self.sidebar_collapsed:
                chk.setText(label)
            chk.setToolTip(name_only)

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
        self.subtitle.setVisible(False)

        grid = QHBoxLayout(); grid.setContentsMargins(0, 0, 0, 0); grid.setSpacing(0)
        lay.addLayout(grid)

        self.tbl_hours = QTableWidget()
        self.tbl_hours.setObjectName("HoursGutter")
        self.tbl_hours.setFixedWidth(86)
        self.tbl_hours.setMinimumWidth(86)
        self.tbl_hours.setMaximumWidth(86)
        self.tbl_hours.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        hh_ = self.tbl_hours.horizontalHeader()
        hh_.setSectionResizeMode(QHeaderView.Fixed)
        self.tbl_hours.setFixedWidth(98)
        self.tbl_hours.setMinimumWidth(98)
        self.tbl_hours.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.tbl_hours.setFrameShape(QFrame.NoFrame)
        self.tbl_hours.verticalHeader().setVisible(False)
        self.tbl_hours.horizontalHeader().setVisible(False)
        self.tbl_hours.horizontalHeader().setStretchLastSection(True)
        self.tbl_hours.setEditTriggers(self.tbl_hours.NoEditTriggers)
        self.tbl_hours.setSelectionMode(self.tbl_hours.NoSelection)
        self.tbl_hours.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tbl_hours.setVerticalScrollMode(self.tbl_hours.ScrollPerPixel)
        self.hours_wrap = QFrame()
        self.hours_wrap.setObjectName("HoursWrap")
        _hours_v = QVBoxLayout(self.hours_wrap)
        _hours_v.setContentsMargins(0, 0, 0, 0)
        _hours_v.setSpacing(0)

        self.hours_pad = QWidget(self.hours_wrap)
        self.hours_pad.setFixedHeight(28) 
        _hours_v.addWidget(self.hours_pad)

        _hours_v.addWidget(self.tbl_hours, 1)
        grid.addWidget(self.hours_wrap)

        self.tbl_hours.setShowGrid(False)
        self.tbl_hours.setStyleSheet("""
            QTableWidget#HoursGutter { background: transparent; border: none; color:#e6eaf0; font-weight:600; }
            QTableWidget#HoursGutter::item { border: none; padding-right:6px; }
            QHeaderView::section { background: transparent; border: none; }
        """)

        self._hour_ticks = []
        self._hour_guides = []
        self._hour_gutter_offset = 22 

        # Tabla principal
        self.tbl = QTableWidget()
        self.tbl.setObjectName("DayGrid")
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionMode(self.tbl.NoSelection)
        self.tbl.setShowGrid(False)
        bg_cards = _surface_color_from(self.parent.sidebar, "#1f242b")
        hdr_day = PillHeader(Qt.Horizontal, self.tbl, bg=bg_cards, fg="#e6eaf0")
        self.tbl.setHorizontalHeader(hdr_day)
        self.tbl.setStyleSheet("""
            QTableWidget#DayGrid,
            QTableWidget#DayGrid::viewport { background: transparent; border: none; }
            QTableCornerButton::section { background: transparent; border: none; }
            QTableWidget#DayGrid::item,
            QTableWidget#DayGrid::item:selected { background: transparent; border: none; }
        """)

        self.tbl.setVerticalScrollMode(self.tbl.ScrollPerPixel)
        self.tbl.setHorizontalScrollMode(self.tbl.ScrollPerPixel)
        grid.addWidget(self.tbl, stretch=1)
        self._col_guides = []

        self.fade_top = QFrame(self.tbl.viewport())
        self.fade_top.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 rgba(14,18,23,0.75), stop:1 rgba(14,18,23,0));"
        )
        self.fade_top.setFixedHeight(18); self.fade_top.hide()

        self.fade_bottom = QFrame(self.tbl.viewport())
        self.fade_bottom.setStyleSheet(
            "background: qlineargradient(x1:0,y1:1,x2:0,y2:0,"
            "stop:0 rgba(14,18,23,0.75), stop:1 rgba(14,18,23,0));"
        )
        self.fade_bottom.setFixedHeight(18); self.fade_bottom.hide()

        self.tbl.verticalScrollBar().rangeChanged.connect(
            lambda mi, ma: self.tbl_hours.verticalScrollBar().setRange(mi, ma)
        )
        self.tbl_hours.verticalScrollBar().rangeChanged.connect(
            lambda mi, ma: self.tbl.verticalScrollBar().setRange(mi, ma)
        )

        self.tbl.verticalScrollBar().valueChanged.connect(self.tbl_hours.verticalScrollBar().setValue)
        self.tbl_hours.verticalScrollBar().valueChanged.connect(self.tbl.verticalScrollBar().setValue)

        self.tbl.verticalScrollBar().valueChanged.connect(self._update_now_line)
        self.tbl.verticalScrollBar().valueChanged.connect(lambda _=None: self._reposition_col_guides())
        self.tbl.verticalScrollBar().valueChanged.connect(lambda _=None: self._update_fades())
        self.tbl.verticalScrollBar().valueChanged.connect(lambda _=None: self._reposition_hour_ticks())
        self.tbl.verticalScrollBar().valueChanged.connect(lambda _=None: self._reposition_hour_guides())
        self.tbl_hours.verticalScrollBar().valueChanged.connect(lambda _=None: self._reposition_hour_ticks())
        self.tbl_hours.verticalScrollBar().valueChanged.connect(lambda _=None: self._reposition_hour_guides())
        self.tbl_hours.verticalScrollBar().valueChanged.connect(lambda _=None: self._reposition_col_guides())
        self.tbl_hours.verticalScrollBar().valueChanged.connect(lambda _=None: self._update_fades())


        self.now_line_main = QFrame(self.tbl.viewport()); self.now_line_main.setFrameShape(QFrame.HLine)
        self.now_line_main.setStyleSheet("color:#ff6161; background:#ff6161;")
        self.now_line_main.setFixedHeight(3); self.now_line_main.hide()

        self.now_glow_line = QFrame(self.tbl.viewport())
        self.now_glow_line.setFrameShape(QFrame.HLine)
        self.now_glow_line.setStyleSheet("background: rgba(255,97,97,0.30);")
        self.now_glow_line.setFixedHeight(7)
        self.now_glow_line.hide()

        self.now_line_hours = QFrame(self.tbl_hours.viewport()); self.now_line_hours.setFrameShape(QFrame.HLine)
        self.now_line_hours.setStyleSheet("color:#ff6161; background:#ff6161;")
        self.now_line_hours.setFixedHeight(2); self.now_line_hours.hide()

        self.now_dot = QFrame(self.tbl.viewport())
        self.now_dot.setObjectName("NowDot")
        self.now_dot.setStyleSheet("#NowDot{background:#ff6161;border-radius:5px;}")
        self.now_dot.setFixedSize(10, 10)
        self.now_dot.hide()

        self.hover_line = QFrame(self.tbl.viewport()); self.hover_line.setFrameShape(QFrame.HLine)
        self.hover_line.setStyleSheet("background: rgba(255,255,255,0.16);")
        self.hover_line.setFixedHeight(1); self.hover_line.hide()
        self.tbl.viewport().installEventFilter(self)
        self.tbl_hours.viewport().installEventFilter(self)

        self._timer = QTimer(self); self._timer.setInterval(30_000); self._timer.timeout.connect(self._update_now_line)
        self._timer.start()

        self.tbl.viewport().installEventFilter(self)
        self.tbl_hours.viewport().installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Resize:
            self._update_now_line()
            self._reposition_hour_ticks()
            self._reposition_hour_guides()
            self._reposition_col_guides()
            self._update_fades()
        if obj is self.tbl.viewport():
            if ev.type() == QEvent.MouseMove:
                y = ev.pos().y()
                self.hover_line.setFixedWidth(self.tbl.viewport().width())
                self.hover_line.move(0, y)
                self.hover_line.show()
            elif ev.type() in (QEvent.Leave, QEvent.MouseButtonPress):
                self.hover_line.hide()
        return super().eventFilter(obj, ev)

    def configure(self, artists: List[Artist], date: QDate, start: QTime, end: QTime, step: int, artist_ids: List[str]):
        self.artists = artists; self.date = date
        self.day_start, self.day_end, self.step_min = start, end, step
        self.artist_order = artist_ids
        self._auto_scrolled_date = None

    def render(self, appts: List[Appt], artist_lookup):
        self.subtitle.setText(self.date.toString("ddd dd MMM yyyy"))

        steps = int(self.day_start.secsTo(self.day_end) / 60 // self.step_min)
        row_height = 32

        self.tbl.clear(); self.tbl.setRowCount(steps); self.tbl.setColumnCount(len(self.artist_order))
        hdr = self.tbl.horizontalHeader()
        fm = QFontMetrics(self.font())
        for c, aid in enumerate(self.artist_order):
            name = self._artist_name(aid)
            a = artist_lookup(aid)
            bullet = "● " if a else ""
            it = QTableWidgetItem(f"{bullet}{name}"); it.setToolTip(name)
            self.tbl.setHorizontalHeaderItem(c, it)
            hdr.setSectionResizeMode(c, QHeaderView.Stretch)
            minw = max(140, fm.horizontalAdvance(name) + 24)
            self.tbl.setColumnWidth(c, minw)
        for r in range(steps):
            self.tbl.setRowHeight(r, row_height)

        self.tbl_hours.clear(); self.tbl_hours.setRowCount(steps); self.tbl_hours.setColumnCount(1)
        row_h = self.tbl.rowHeight(0) if self.tbl.rowCount() else row_height
        pad_top = self.tbl.horizontalHeader().height() + int(row_h * 0.56)
        if hasattr(self, "hours_pad"):
            self.hours_pad.setFixedHeight(pad_top)
        self.tbl_hours.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tbl_hours.setColumnWidth(0, 80)

        sb_day = self.tbl.verticalScrollBar()
        sb_day.setStyleSheet(f"""
        QScrollBar:vertical {{
            background: transparent;
            width: 12px;
            margin: {pad_top}px 4px 12px 4px;
            border: none;
            border-radius: 6px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255,255,255,0.30);
            border: none;
            border-radius: 6px;
            min-height: 48px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)

        t = QTime(self.day_start)
        for r in range(steps):
            txt = t.toString("hh:mm") if t.minute() == 0 else ""
            it = QTableWidgetItem(txt)
            it.setFlags(Qt.ItemIsEnabled)
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl_hours.setItem(r, 0, it)
            self.tbl_hours.setRowHeight(r, row_height)
            self.tbl_hours.setRowHeight(r, row_height)
            t = t.addSecs(self.step_min * 60)

        self._create_hour_guides(steps)
        self._clear_col_guides()
        QTimer.singleShot(0, self._update_fades)

        self.now_line_main.hide(); self.now_line_hours.hide()
        QTimer.singleShot(0, self._update_now_line)
        QTimer.singleShot(0, self._auto_scroll_to_now)

        # Chips
        any_chip = False
        for ap in appts:
            if ap.date != self.date or ap.artist_id not in self.artist_order: continue
            col = self.artist_order.index(ap.artist_id)
            row_start = int(self.day_start.secsTo(ap.start) / 60 // self.step_min)
            row_span  = max(1, ap.duration_min // self.step_min)

            a = artist_lookup(ap.artist_id)
            chip = ApptChip(ap, a, self.parent)
            self.tbl.setSpan(row_start, col, row_span, 1)
            self.tbl.setCellWidget(row_start, col, chip)
            any_chip = True

        # Empty state
        if hasattr(self, "_empty_state"):
            self._empty_state.hide()
        for _lbl in self.findChildren(QLabel):
            txt = (_lbl.text() or "").lower()
            if "no hay citas" in txt or "nueva cita" in txt:
                _lbl.hide()

    def _update_now_line(self):
        self.now_line_main.hide()
        self.now_line_hours.hide()
        self.now_dot.hide()

        if self.date != QDate.currentDate():
            return

        steps = int(self.day_start.secsTo(self.day_end) / 60 // self.step_min)
        if steps <= 0:
            return

        row_height = self.tbl.rowHeight(0) if self.tbl.rowCount() else 32
        minutes = self.day_start.secsTo(QTime.currentTime()) / 60.0
        if minutes < 0:
            return

        y_full = (minutes / self.step_min) * row_height
        scroll_px = float(self.tbl.verticalScrollBar().value())
        y_view = int(y_full - scroll_px)

        view_w = self.tbl.viewport().width()
        view_h = self.tbl.viewport().height()
        if y_view < 1 or y_view > view_h - 1:
            return

        dot_x = 0
        self.now_dot.move(dot_x, y_view - self.now_dot.height() // 2)
        self.now_dot.show()
        self.now_dot.raise_()

        line_left = self.now_dot.x() + self.now_dot.width() // 2
        self.now_line_main.setFixedWidth(max(1, view_w - line_left))
        self.now_line_main.move(line_left, y_view)
        self.now_line_main.show()
        self.now_line_main.raise_()
        self.now_glow_line.setFixedWidth(max(1, view_w - line_left))
        self.now_glow_line.move(line_left, y_view - (self.now_glow_line.height() - self.now_line_main.height()) // 2)
        self.now_glow_line.show()
        self.now_glow_line.lower()
        self.now_line_main.raise_
        self.now_dot.raise_()

    def _auto_scroll_to_now(self):
        if self.date != QDate.currentDate():
            return
        if self._auto_scrolled_date == self.date:
            return
        row_h = self.tbl.rowHeight(0) if self.tbl.rowCount() else 32
        minutes = self.day_start.secsTo(QTime.currentTime()) / 60.0
        if minutes < 0:
            return
        target_rows = max(0, (minutes - 60) / self.step_min)
        y_full = target_rows * row_h
        self.tbl.verticalScrollBar().setValue(int(y_full))
        self._auto_scrolled_date = self.date

    def _artist_name(self, aid: str) -> str:
        for a in self.artists:
            if a.id == aid: return a.name
        return "Artista"

    def _clear_hour_ticks(self):
        for _, tick in self._hour_ticks:
            tick.setParent(None)
            tick.deleteLater()
        self._hour_ticks.clear()

    def _create_hour_ticks(self, steps: int):
        self._clear_hour_ticks()
        t = QTime(self.day_start)
        for r in range(steps):
            if t.minute() == 0:
                tick = QFrame(self.tbl.viewport())
                tick.setObjectName("HourTick")
                tick.setFrameShape(QFrame.HLine)
                tick.setFixedHeight(2)
                tick.setFixedWidth(14)
                tick.setStyleSheet("#HourTick { background: rgba(255,255,255,0.22); }")
                tick.show()
                self._hour_ticks.append((r, tick))
            t = t.addSecs(self.step_min * 60)
        QTimer.singleShot(0, self._reposition_hour_ticks)

    def _reposition_hour_ticks(self):
        for r, tick in self._hour_ticks:
            y = self.tbl.rowViewportPosition(r)
            tick.move(0, y)
            tick.raise_()

    def _clear_hour_ticks(self):
        for _, tick in self._hour_ticks:
            tick.setParent(None)
            tick.deleteLater()
        self._hour_ticks.clear()

    def _create_hour_ticks(self, steps: int):
        self._clear_hour_ticks()
        t = QTime(self.day_start)
        for r in range(steps):
            if t.minute() == 0:
                tick = QFrame(self.tbl.viewport())
                tick.setObjectName("HourTick")
                tick.setFrameShape(QFrame.HLine)
                tick.setFixedHeight(2)
                tick.setFixedWidth(14)
                tick.setStyleSheet("#HourTick { background: rgba(255,255,255,0.22); }")
                tick.show()
                self._hour_ticks.append((r, tick))
            t = t.addSecs(self.step_min * 60)
        QTimer.singleShot(0, self._reposition_hour_ticks)

    def _reposition_hour_ticks(self):
        for r, tick in self._hour_ticks:
            y = self.tbl.rowViewportPosition(r)
            tick.move(0, y)
            tick.raise_()
    
    def _clear_hour_guides(self):
        for _, g in self._hour_guides:
            g.setParent(None)
            g.deleteLater()
        self._hour_guides.clear()

    def _create_hour_guides(self, steps: int):
        self._clear_hour_guides()
        t = QTime(self.day_start)
        for r in range(steps):
            if t.minute() == 0:
                g = QFrame(self.tbl.viewport())
                g.setObjectName("HourGuide")
                g.setFrameShape(QFrame.HLine)
                g.setFixedHeight(2)
                g.setStyleSheet("#HourGuide { background: rgba(255,255,255,0.28); }")
                g.show()
                self._hour_guides.append((r, g))
            t = t.addSecs(self.step_min * 60)
        QTimer.singleShot(0, self._reposition_hour_guides)

    def _reposition_hour_guides(self):
        vw = self.tbl.viewport().width()
        for r, g in self._hour_guides:
            y = self.tbl.rowViewportPosition(r)
            g.setFixedWidth(vw)
            g.move(0, y)
            g.lower()
    
    def _clear_col_guides(self):
        for _, g in self._col_guides:
            g.setParent(None); g.deleteLater()
        self._col_guides.clear()

    def _create_col_guides(self):
        self._clear_col_guides()
        cols = self.tbl.columnCount()
        if cols <= 0: return
        h = self.tbl.viewport().height()
        for c in range(1, cols):
            x = self.tbl.columnViewportPosition(c) - 1
            g = QFrame(self.tbl.viewport())
            g.setFrameShape(QFrame.VLine)
            g.setStyleSheet("background: rgba(255,255,255,0.16);")
            g.setFixedWidth(1); g.setFixedHeight(h)
            g.move(x, 0); g.show()
            self._col_guides.append((c, g))

    def _reposition_col_guides(self):
        vw_h = self.tbl.viewport().height()
        for c, g in self._col_guides:
            x = self.tbl.columnViewportPosition(c) - 1
            g.setFixedHeight(vw_h)
            g.move(x, 0)
            g.raise_()

    def _update_fades(self):
        vw = self.tbl.viewport()
        if not vw.isVisible(): return
        w = vw.width()
        self.fade_top.setFixedWidth(w)
        self.fade_bottom.setFixedWidth(w)
        self.fade_top.move(0, 0)
        self.fade_bottom.move(0, vw.height() - self.fade_bottom.height())

        sb = self.tbl.verticalScrollBar()
        show_top = sb.value() > 0
        show_bottom = sb.value() < (sb.maximum() - 1)
        self.fade_top.setVisible(show_top)
        self.fade_bottom.setVisible(show_bottom)

class WeekView(QWidget):
    def _clear_hour_guides(self):
        for _, g in self._hour_guides:
            g.setParent(None)
            g.deleteLater()
        self._hour_guides.clear()

    def _create_hour_guides(self, steps: int):
        self._clear_hour_guides()
        t = QTime(self.day_start)
        for r in range(steps):
            if t.minute() == 0:
                g = QFrame(self.tbl.viewport())
                g.setObjectName("HourGuideW")
                g.setFrameShape(QFrame.HLine)
                g.setFixedHeight(2)
                g.setStyleSheet("#HourGuideW { background: rgba(255,255,255,0.28); }")
                g.show()
                self._hour_guides.append((r, g))
            t = t.addSecs(self.step_min * 60)
        QTimer.singleShot(0, self._reposition_hour_guides)

    def _reposition_hour_guides(self):
        vw = self.tbl.viewport().width()
        for r, g in self._hour_guides:
            y = self.tbl.rowViewportPosition(r)
            g.setFixedWidth(vw)
            g.move(0, y)
            g.lower()   # ← siempre debajo de las citas
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        self.parent: AgendaPage = parent
        self.date = QDate.currentDate(); self.day_start = QTime(8,0); self.day_end = QTime(22,0); self.step_min = 30
        self.artist_id = None

        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
        self.subtitle = QLabel(""); self.subtitle.setStyleSheet("color:#888; background: transparent;")
        lay.addWidget(self.subtitle)
        self.subtitle.setVisible(False)

        grid = QHBoxLayout(); grid.setContentsMargins(0,0,0,0); grid.setSpacing(0)
        lay.addLayout(grid)

        self.tbl_hours = QTableWidget()
        self.tbl_hours.setObjectName("HoursGutterW")
        self.tbl_hours.setFixedWidth(98)
        self.tbl_hours.setMinimumWidth(98)
        self.tbl_hours.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.tbl_hours.verticalHeader().setVisible(False)
        self.tbl_hours.horizontalHeader().setVisible(False)
        self.tbl_hours.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)

        self.tbl_hours.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_hours.setSelectionMode(QTableWidget.NoSelection)
        self.tbl_hours.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tbl_hours.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tbl_hours.setShowGrid(False)

        self.tbl_hours.setStyleSheet("""
            QTableWidget#HoursGutterW { background: transparent; border: none; color:#e6eaf0; font-weight:600; }
            QTableWidget#HoursGutterW::item { border: none; padding-right:6px; }
            QHeaderView::section { background: transparent; border: none; }
        """)

        self.hours_wrapW = QFrame()
        _hours_vW = QVBoxLayout(self.hours_wrapW)
        _hours_vW.setContentsMargins(0, 0, 0, 0)
        _hours_vW.setSpacing(0)

        self.hours_padW = QWidget(self.hours_wrapW)
        self.hours_padW.setFixedHeight(28)
        _hours_vW.addWidget(self.hours_padW)

        _hours_vW.addWidget(self.tbl_hours, 1)
        grid.addWidget(self.hours_wrapW)

        self.tbl = QTableWidget()
        self.tbl.setObjectName("WeekGrid")
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionMode(self.tbl.NoSelection)
        bg_cards = _surface_color_from(self.parent.sidebar, "#1f242b")
        hdr_week = PillHeader(Qt.Horizontal, self.tbl, bg=bg_cards, fg="#e6eaf0")
        self.tbl.setHorizontalHeader(hdr_week)
        self.tbl.setStyleSheet("""
            QTableWidget#WeekGrid,
            QTableWidget#WeekGrid::viewport { background: transparent; border: none; }
            QTableCornerButton::section { background: transparent; border: none; }
            QTableWidget#WeekGrid::item { background: transparent; border: none; }
        """)
        self.tbl.setVerticalScrollMode(self.tbl.ScrollPerPixel)
        self.tbl.setHorizontalScrollMode(self.tbl.ScrollPerPixel)
        self.tbl.setShowGrid(False)
        grid.addWidget(self.tbl, stretch=1)

        self.tbl.verticalScrollBar().rangeChanged.connect(
            lambda mi, ma: self.tbl_hours.verticalScrollBar().setRange(mi, ma)
        )
        self.tbl_hours.verticalScrollBar().rangeChanged.connect(
            lambda mi, ma: self.tbl.verticalScrollBar().setRange(mi, ma)
        )
        self.tbl.verticalScrollBar().valueChanged.connect(self.tbl_hours.verticalScrollBar().setValue)
        self.tbl_hours.verticalScrollBar().valueChanged.connect(self.tbl.verticalScrollBar().setValue)
        self.tbl.verticalScrollBar().valueChanged.connect(self._update_now_line)

        self.now_line_main = QFrame(self.tbl.viewport()); self.now_line_main.setFrameShape(QFrame.HLine)
        self.now_line_main.setStyleSheet("color:#ff6161; background:#ff6161;")
        self.now_line_main.setFixedHeight(3); self.now_line_main.hide()

        self.now_line_hours = QFrame(self.tbl_hours.viewport()); self.now_line_hours.hide()

        self.now_dot = QFrame(self.tbl.viewport())
        self.now_dot.setObjectName("NowDot")
        self.now_dot.setStyleSheet("#NowDot{background:#ff6161;border-radius:5px;}")
        self.now_dot.setFixedSize(10, 10)
        self.now_dot.hide()

        self.hover_line = QFrame(self.tbl.viewport()); self.hover_line.setFrameShape(QFrame.HLine)
        self.hover_line.setStyleSheet("background: rgba(255,255,255,0.16);")
        self.hover_line.setFixedHeight(1); self.hover_line.hide()

        self._hour_ticks = []
        self._hour_guides = []

        self._timer = QTimer(self); self._timer.setInterval(30_000); self._timer.timeout.connect(self._update_now_line)
        self._timer.start()
        self.tbl.viewport().installEventFilter(self)
        self.tbl_hours.viewport().installEventFilter(self)
        self.tbl.verticalScrollBar().valueChanged.connect(lambda _=None: self._reposition_hour_guides())
        self.tbl_hours.verticalScrollBar().valueChanged.connect(lambda _=None: self._reposition_hour_guides())

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Resize:
            self._update_now_line()
            self._reposition_hour_guides()
        if obj is self.tbl.viewport():
            if ev.type() == QEvent.MouseMove:
                y = ev.pos().y()
                self.hover_line.setFixedWidth(self.tbl.viewport().width())
                self.hover_line.move(0, y)
                self.hover_line.show()
            elif ev.type() in (QEvent.Leave, QEvent.MouseButtonPress):
                self.hover_line.hide()
        return super().eventFilter(obj, ev)

    def _clear_hour_ticks(self):
        for _, tick in self._hour_ticks:
            tick.setParent(None)
            tick.deleteLater()
        self._hour_ticks.clear()

    def _create_hour_ticks(self, steps: int):
        self._clear_hour_ticks()
        t = QTime(self.day_start)
        for r in range(steps):
            if t.minute() == 0:
                tick = QFrame(self.tbl.viewport())
                tick.setObjectName("HourTickW")
                tick.setFrameShape(QFrame.HLine)
                tick.setFixedHeight(2)
                tick.setFixedWidth(14)
                tick.setStyleSheet("#HourTickW { background: rgba(255,255,255,0.22); }")
                tick.show()
                self._hour_ticks.append((r, tick))
            t = t.addSecs(self.step_min * 60)
        QTimer.singleShot(0, self._reposition_hour_ticks)

    def _reposition_hour_ticks(self):
        for r, tick in self._hour_ticks:
            y = self.tbl.rowViewportPosition(r)
            tick.move(0, y)
            tick.raise_()

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
        labels = []
        for i in range(7):
            d = (monday.addDays(i))
            lab = d.toString("ddd dd")
            if d == QDate.currentDate(): lab += " • hoy"
            labels.append(lab)
        self.tbl.setHorizontalHeaderLabels(labels)
        hdr = self.tbl.horizontalHeader()
        for c in range(7):
            hdr.setSectionResizeMode(c, QHeaderView.Stretch)
        for r in range(steps): 
            self.tbl.setRowHeight(r, row_height)

        self.tbl_hours.clear(); self.tbl_hours.setRowCount(steps); self.tbl_hours.setColumnCount(1)
        self.tbl_hours.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tbl_hours.setColumnWidth(0, 80)

        row_h = self.tbl.rowHeight(0) if self.tbl.rowCount() else row_height
        pad_top = self.tbl.horizontalHeader().height() + int(row_h * 0.56)

        try:
            self.tbl_hours.viewport().setContentsMargins(0, pad_top, 0, 0)
        except Exception:
            pass

        row_h = self.tbl.rowHeight(0) if self.tbl.rowCount() else row_height
        pad_top = self.tbl.horizontalHeader().height() + int(row_h * 0.56)
        if hasattr(self, "hours_padW"):
            self.hours_padW.setFixedHeight(pad_top)

        self.tbl_hours.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tbl_hours.setColumnWidth(0, 80)

        # Scrollbar vertical en Week: alinear con el área de citas y estilo transparente/redondeado
        sb_week = self.tbl.verticalScrollBar()
        sb_week.setStyleSheet(f"""
        QScrollBar:vertical {{
            background: transparent;
            width: 12px;
            margin: {pad_top}px 4px 12px 4px;   /* solo el área de citas */
            border: none;
            border-radius: 6px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255,255,255,0.30);
            border: none;
            border-radius: 6px;                 /* óvalo real */
            min-height: 48px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)
        t = QTime(self.day_start)
        for r in range(steps):
            txt = t.toString("hh:mm") if t.minute() == 0 else ""
            it = QTableWidgetItem(txt)
            it.setFlags(Qt.ItemIsEnabled)
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl_hours.setItem(r, 0, it)
            self.tbl_hours.setRowHeight(r, row_height)
            t = t.addSecs(self.step_min * 60)

        self._create_hour_guides(steps)
        self.now_line_main.hide()
        self.now_dot.hide()
        QTimer.singleShot(0, self._update_now_line)

        if not self.artist_id:
            return

        for ap in appts:
            if ap.artist_id != self.artist_id: 
                continue
            if not (monday <= ap.date <= monday.addDays(6)): 
                continue

            col = monday.daysTo(ap.date)
            row_start = int(self.day_start.secsTo(ap.start) / 60 // self.step_min)
            row_span  = max(1, ap.duration_min // self.step_min)

            a = artist_lookup(ap.artist_id)
            chip = ApptChip(ap, a, self.parent)
            self.tbl.setSpan(row_start, col, row_span, 1)
            self.tbl.setCellWidget(row_start, col, chip)

    def _update_now_line(self):
        self.now_line_main.hide()
        self.now_dot.hide()

        monday = self.date.addDays(-(self.date.dayOfWeek()-1))
        today = QDate.currentDate()
        if not (monday <= today <= monday.addDays(6)):
            return

        steps = int(self.day_start.secsTo(self.day_end) / 60 // self.step_min)
        if steps <= 0:
            return

        row_height = self.tbl.rowHeight(0) if self.tbl.rowCount() else 32
        minutes = self.day_start.secsTo(QTime.currentTime()) / 60.0
        if minutes < 0:
            return

        y_full = (minutes / self.step_min) * row_height
        scroll_px = float(self.tbl.verticalScrollBar().value())
        y_view = int(y_full - scroll_px)

        view_h = self.tbl.viewport().height()
        if y_view < 1 or y_view > view_h - 1:
            return

        col_today = monday.daysTo(today)   # 0..6
        if not (0 <= col_today < self.tbl.columnCount()):
            return
        x_left = self.tbl.columnViewportPosition(col_today)
        col_w  = self.tbl.columnWidth(col_today)
        if col_w <= 0:
            return

        dot_x = x_left
        self.now_dot.move(dot_x, y_view - self.now_dot.height() // 2)
        self.now_dot.show()
        self.now_dot.raise_()

        line_left = dot_x + self.now_dot.width() // 2
        line_w = max(1, col_w - (self.now_dot.width() // 2))
        self.now_line_main.setFixedWidth(line_w)
        self.now_line_main.move(line_left, y_view)
        self.now_line_main.show()
        self.now_line_main.raise_()

class MonthView(QWidget):
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
        self.subtitle = QLabel(""); self.subtitle.setStyleSheet("color:#888; background: transparent;")
        lay.addWidget(self.subtitle)
        self.subtitle.setVisible(False)

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

                items = byday.get(day, [])
                for ap in items[:4]:
                    a = artist_lookup(ap.artist_id); color = a.color if a else "#999"
                    text = f"{ap.start.toString('hh:mm')} · {ap.client_name}"
                    chip = QLabel(text); chip.setToolTip(f"{text}\n{ap.service}")
                    chip.setStyleSheet(f"padding:1px 2px; border-left:4px solid {color};")
                    lay.addWidget(chip)
                if len(items) > 4:
                    more = QLabel(f"+{len(items)-4}")
                    more.setStyleSheet("color:#9aa0a6;")
                    lay.addWidget(more)

                lay.addStretch(1)
                self.tbl.setCellWidget(r, c, cell); day += 1


class ListView(QWidget):
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

    def _pill(self, text: str, bg: str) -> QWidget:
        w = QLabel(text)
        w.setStyleSheet(f"padding:2px 8px; border-radius:10px; background:{bg}; color:#0e1217; font-weight:600;")
        wrap = QWidget(); l = QHBoxLayout(wrap); l.setContentsMargins(0,0,0,0); l.addWidget(w, 0, Qt.AlignLeft)
        return wrap

    def _artist_cell(self, name: str, color: str) -> QWidget:
        dot = QLabel("●"); dot.setStyleSheet(f"color:{color}; padding-right:6px;")
        lbl = QLabel(name); lbl.setStyleSheet("background:transparent;")
        w = QWidget(); l = QHBoxLayout(w); l.setContentsMargins(0,0,0,0)
        l.addWidget(dot); l.addWidget(lbl); l.addStretch(1)
        return w

    def render(self, appts: List[Appt], artist_lookup):
        self.tbl.setRowCount(0)
        rows = sorted(appts, key=lambda a: (a.date.toJulianDay(), a.start.hour(), a.start.minute()))
        for ap in rows:
            row = self.tbl.rowCount(); self.tbl.insertRow(row)
            artist = artist_lookup(ap.artist_id)
            self.tbl.setItem(row, 0, QTableWidgetItem(ap.date.toString("dd/MM/yyyy")))
            self.tbl.setItem(row, 1, QTableWidgetItem(ap.start.toString("hh:mm")))
            self.tbl.setItem(row, 2, QTableWidgetItem(ap.client_name))
            self.tbl.setCellWidget(row, 3, self._artist_cell(artist.name if artist else "", artist.color if artist else "#999"))
            it_srv = QTableWidgetItem(ap.service or "")
            it_srv.setToolTip(ap.service or "")
            self.tbl.setItem(row, 4, it_srv)
            pill = self._pill(ap.status, _state_color_hex(ap.status))
            self.tbl.setCellWidget(row, 5, pill)
