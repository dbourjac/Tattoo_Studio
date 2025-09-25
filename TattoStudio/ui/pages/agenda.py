from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, time
import csv
import os

from PyQt5.QtCore import Qt, QDate, QTime, QPoint, pyqtSignal, QTimer, QEvent
from PyQt5.QtGui import QFontMetrics, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDateEdit, QFrame, QCheckBox, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QLineEdit, QHeaderView, QSizePolicy, QFileDialog,
    QMessageBox, QMenu, QDialog, QFormLayout, QDialogButtonBox, QSpinBox, QCompleter
)

# === BD / servicios ===
from services.sessions import (
    list_sessions, update_session, complete_session, cancel_session, create_session
)
from data.db.session import SessionLocal
from data.models.client import Client
from data.models.artist import Artist as DBArtist

# Permisos centralizados (elevación incluida)
from ui.pages.common import ensure_permission


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
#   DIALOGOS
# ==============================

class PaymentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Completar cita")
        self.setModal(True)

        form = QFormLayout(self)
        self.cbo = QComboBox()
        self.cbo.addItems(["Efectivo", "Tarjeta", "Transferencia"])
        form.addRow("Método de pago:", self.cbo)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def method(self) -> str:
        return self.cbo.currentText()


class NewApptDialog(QDialog):
    """Diálogo de nueva cita con autocompletado de clientes."""
    def __init__(self, parent, artists: List[Artist], clients: List[Tuple[int, str]], default_date: QDate):
        super().__init__(parent)
        self.setWindowTitle("Nueva cita")
        self.setModal(True)

        form = QFormLayout(self)

        self.dt_date = QDateEdit(default_date)
        self.dt_date.setCalendarPopup(True)
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
        self.cb_client = QComboBox()
        self.cb_client.setEditable(True)
        self.cb_client.setInsertPolicy(QComboBox.NoInsert)
        for cid, cname in clients:
            self.cb_client.addItem(cname, cid)
        completer = QCompleter([n for _, n in clients], self.cb_client)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.cb_client.setCompleter(completer)
        form.addRow("Cliente:", self.cb_client)

        self.ed_service = QLineEdit(placeholderText="Servicio / notas")
        form.addRow("Servicio:", self.ed_service)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def values(self) -> dict:
        date = self.dt_date.date()
        h, m = self.sp_hour.value(), self.sp_min.value()
        start = datetime(date.year(), date.month(), date.day(), h, m, 0)
        dur   = self.sp_dur.value()
        # Si el usuario escribió un nombre que no coincide con ítem, currentData será None
        client_id = self.cb_client.currentData()
        client_name = self.cb_client.currentText().strip()
        return {
            "artist_id": int(self.cbo_artist.currentData()),
            "client_id": int(client_id) if client_id is not None else None,
            "client_name": client_name or None,
            "notes": (self.ed_service.text() or "").strip(),
            "start": start,
            "end": start + timedelta(minutes=dur),
        }


# ==============================
#   AGENDA PAGE
# ==============================

class AgendaPage(QWidget):
    crear_cita = pyqtSignal()
    abrir_cita = pyqtSignal(dict)

    _PALETTE = ["#4ade80", "#60a5fa", "#f472b6", "#9d0dc1", "#f59e0b", "#22d3ee", "#a78bfa", "#34d399"]

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

        self._refresh_all()

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
        # Ajuste sutil para alineación vertical
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

    # ---------- Sidebar ----------
    def _build_sidebar(self) -> QWidget:
        w = QFrame(); w.setObjectName("Sidebar")
        lay = QVBoxLayout(w); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(12)

        def title(text: str) -> QLabel:
            lbl = QLabel(text); lbl.setStyleSheet("background: transparent; font-weight: 600;"); return lbl

        self.search = QLineEdit(placeholderText="Buscar cliente…")
        self.search.textChanged.connect(self._on_filter_changed)
        lay.addWidget(title("Buscar")); lay.addWidget(self.search)

        lay.addWidget(title("Artistas"))
        self.artist_checks: Dict[str, QCheckBox] = {}
        for a in self.artists:
            chk = QCheckBox(a.name); chk.setChecked(True); chk.toggled.connect(self._on_filter_changed)
            self.artist_checks[a.id] = chk; lay.addWidget(chk)

        lay.addWidget(title("Estado"))
        self.cbo_status = QComboBox()
        self.cbo_status.addItems(["Todos", "Activa", "Completada", "Cancelada", "En espera"])
        self.cbo_status.currentTextChanged.connect(self._on_filter_changed)
        lay.addWidget(self.cbo_status)

        lay.addStretch(1)
        return w

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
        self.selected_status = self.cbo_status.currentText()
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
            color = self._PALETTE[idx % len(self._PALETTE)]
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

    # ---------- Acciones ----------
    def _open_new_appt_dialog(self):
        dlg = NewApptDialog(self, self.artists, self._clients_cache, self.current_date)
        if dlg.exec_() != QDialog.Accepted:
            return
        val = dlg.values()
        owner_id = val["artist_id"]
        if not ensure_permission(self, "agenda", "create", owner_id=owner_id):
            return

        # Si la BD requiere client_id not null, pedimos selección.
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
                "client_name": val["client_name"],  # opcional si quieres conservar el nombre libre
            })
            QMessageBox.information(self, "Cita", "Cita creada.")
            self._refresh_all()
        except Exception as e:
            QMessageBox.critical(self, "Agenda", f"No se pudo crear la cita: {e}")

    def _open_from_list(self):
        row = self.list_view.tbl.currentRow()
        ap = self._find_appt_by_row(row)
        if not ap: return
        self.abrir_cita.emit({"id": int(ap.id), "client_id": ap.client_id, "artist_id": int(ap.artist_id)})

    def _show_list_context_menu(self, pos: QPoint):
        row = self.list_view.tbl.rowAt(pos.y())
        ap = self._find_appt_by_row(row)
        if not ap: return

        menu = QMenu(self)
        act_open = menu.addAction("Abrir ficha")
        menu.addSeparator()
        act_edit = menu.addAction("Editar (reprogramar)")
        act_complete = menu.addAction("Completar (cobrar)")
        act_cancel = menu.addAction("Cancelar")
        act_noshow = menu.addAction("Marcar no-show")
        act_block = menu.addAction("Bloqueo/Ausencia (no disponible)")
        act_block.setEnabled(False)

        chosen = menu.exec_(self.list_view.tbl.viewport().mapToGlobal(pos))
        if not chosen:
            return

        owner_id = int(ap.artist_id)

        if chosen is act_open:
            self._open_from_list(); return

        if chosen is act_edit:
            if not ensure_permission(self, "agenda", "edit", owner_id=owner_id):
                return
            try:
                start_dt = datetime(ap.date.year(), ap.date.month(), ap.date.day(), ap.start.hour(), ap.start.minute()) + timedelta(hours=1)
                end_dt   = start_dt + timedelta(minutes=ap.duration_min)
                update_session(int(ap.id), {"start": start_dt, "end": end_dt})
                QMessageBox.information(self, "Cita", "Cita reprogramada (+1h demo).")
            except Exception as e:
                QMessageBox.critical(self, "Agenda", f"No se pudo reprogramar: {e}")
            self._refresh_all(); return

        if chosen is act_complete:
            if not ensure_permission(self, "agenda", "complete", owner_id=owner_id):
                return
            dlg = PaymentDialog(self)
            if dlg.exec_() == QDialog.Accepted:
                try:
                    complete_session(int(ap.id), {"method": dlg.method()})
                    QMessageBox.information(self, "Cita", "Cita completada y registrada en caja.")
                except Exception as e:
                    QMessageBox.critical(self, "Agenda", f"No se pudo completar: {e}")
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
        # Scroll en píxeles para poder compensar la línea "ahora"
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
            show = t.toString("hh:mm") if t.minute() == 0 else t.toString("hh:mm")  # mostraremos ambas
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

            chip = QFrame(); chip.setAutoFillBackground(True); chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            lay = QVBoxLayout(chip); lay.setContentsMargins(6, 4, 6, 4)
            text = f"{ap.client_name}\n{ap.service} • {ap.start.toString('hh:mm')}"
            lbl = QLabel(text); lbl.setWordWrap(True); lbl.setToolTip(text); lay.addWidget(lbl)

            a = artist_lookup(ap.artist_id); base = a.color if a else "#666666"
            chip.setStyleSheet(f"background:{base};border:1px solid rgba(0,0,0,0.18);border-radius:6px;color:white;")
            self.tbl.setSpan(row_start, col, row_span, 1); self.tbl.setCellWidget(row_start, col, chip)

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

        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)
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

            chip = QFrame(); chip.setAutoFillBackground(True); chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            lay = QVBoxLayout(chip); lay.setContentsMargins(6,4,6,4)
            text = f"{ap.client_name}\n{ap.service} • {ap.start.toString('hh:mm')}"
            lbl = QLabel(text); lbl.setWordWrap(True); lbl.setToolTip(text); lay.addWidget(lbl)

            a = artist_lookup(ap.artist_id); base = a.color if a else "#666666"
            chip.setStyleSheet(f"background:{base};border:1px solid rgba(0,0,0,0.18);border-radius:6px;color:white;")
            self.tbl.setSpan(row_start, col, row_span, 1); self.tbl.setCellWidget(row_start, col, chip)

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
