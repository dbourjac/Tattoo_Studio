from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime, timedelta, time

from PyQt5.QtCore import Qt, QDate, QTime, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDateEdit, QFrame, QCheckBox, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QLineEdit, QHeaderView, QSizePolicy
)

# === NUEVO: importamos servicios/modelos para leer de la BD ===
from services.sessions import list_sessions  # API que ya devuelve sesiones con start/end/artist_id/client_id/status
from data.db.session import SessionLocal
from data.models.client import Client
from data.models.artist import Artist as DBArtist


# ==============================
#   MODELOS DE UI (DTOs)
# ==============================

@dataclass
class Artist:
    """Modelo ligero SOLO para la UI (color friendly)."""
    id: str            # usamos str para que encaje con el código existente
    name: str
    color: str         # color del artista para pintar la cita


@dataclass
class Appt:
    """Cita ‘renderizable’ en las vistas."""
    id: str
    client_name: str
    artist_id: str
    date: QDate
    start: QTime
    duration_min: int
    service: str       # usamos ‘notes’ como servicio/título
    status: str        # Activa/Completada/Cancelada/En espera


# ==============================
#   AGENDA PAGE
# ==============================

class AgendaPage(QWidget):
    """
    Agenda integrada con BD:
    - Toolbar: Hoy, <, >, selector de fecha, selector de vista, CTA 'Nueva cita'
    - Sidebar: Búsqueda, filtros por artista/estado
    - Vistas: Día / Semana / Mes / Lista
    - Los datos YA NO son mocks: se leen de SQLite mediante services/models.
    """
    crear_cita = pyqtSignal()
    abrir_cita = pyqtSignal(dict)

    # Paleta fija para colorear artistas (mismo color por artista de forma estable)
    _PALETTE = ["#4ade80", "#60a5fa", "#f472b6", "#9d0dc1", "#f59e0b", "#22d3ee", "#a78bfa", "#34d399"]

    def __init__(self):
        super().__init__()

        # ------- Estado -------
        self.current_date: QDate = QDate.currentDate()
        self.current_view: str = "day"   # day | week | month | list
        self.selected_artist_ids: List[str] = []
        self.selected_status: str = "Todos"
        self.search_text: str = ""

        # Jornada visible
        self.day_start = QTime(8, 0)
        self.day_end   = QTime(22, 0)
        self.step_min  = 30

        # ------- Datos desde BD -------
        self.artists: List[Artist] = []   # se llena con _load_artists_from_db()
        self.appts: List[Appt] = []       # se llena con _fetch_sessions_from_db() según el rango visible

        # Cargamos artistas ANTES de construir la sidebar (para generar los checkboxes correctos)
        self._load_artists_from_db()

        # ------- UI -------
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        # Toolbar
        root.addWidget(self._build_toolbar())

        # Splitter: Sidebar | Vistas
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        root.addWidget(split, stretch=1)

        self.sidebar = self._build_sidebar()
        self.sidebar.setFixedWidth(220)
        split.addWidget(self.sidebar)

        self.views_stack = QStackedWidget()
        split.addWidget(self.views_stack)
        split.setSizes([220, 900])

        # Subvistas (sin cambios de estructura)
        self.day_view   = DayView(self)
        self.week_view  = WeekView(self)
        self.month_view = MonthView(self)
        self.list_view  = ListView(self)

        self.views_stack.addWidget(self.day_view)
        self.views_stack.addWidget(self.week_view)
        self.views_stack.addWidget(self.month_view)
        self.views_stack.addWidget(self.list_view)

        self._refresh_all()

    # ---------- Toolbar ----------
    def _build_toolbar(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("Toolbar")
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(8)

        # Navegación temporal
        self.btn_today = QPushButton("Hoy"); self.btn_today.setObjectName("Chip")
        self.btn_prev  = QPushButton("‹");   self.btn_prev.setObjectName("Chip")
        self.btn_next  = QPushButton("›");   self.btn_next.setObjectName("Chip")
        for b in (self.btn_today, self.btn_prev, self.btn_next):
            b.setFixedHeight(36)
            b.setMinimumWidth(48)
        self.btn_today.clicked.connect(self._go_today)
        self.btn_prev.clicked.connect(self._go_prev)
        self.btn_next.clicked.connect(self._go_next)
        lay.addWidget(self.btn_today); lay.addWidget(self.btn_prev); lay.addWidget(self.btn_next)

        # Fecha
        self.dp = QDateEdit(self.current_date)
        self.dp.setCalendarPopup(True)
        self.dp.dateChanged.connect(self._on_date_changed)
        self.dp.setFixedHeight(36)
        self.dp.setMinimumWidth(120)
        lay.addWidget(self.dp)

        # Vista
        lbl_vista = QLabel("Vista:")
        lbl_vista.setStyleSheet("background: transparent;")
        lay.addSpacing(6); lay.addWidget(lbl_vista)
        self.cbo_view = QComboBox()
        self.cbo_view.addItems(["Día", "Semana", "Mes", "Lista"])
        self.cbo_view.currentTextChanged.connect(self._on_view_changed)
        self.cbo_view.setFixedHeight(36); self.cbo_view.setMinimumWidth(90)
        lay.addWidget(self.cbo_view)

        lay.addStretch(1)

        # CTA Nueva cita (sigue emitiendo la señal, la crearemos en otra etapa)
        self.btn_new = QPushButton("Nueva cita")
        self.btn_new.setObjectName("CTA")
        self.btn_new.clicked.connect(lambda: self.crear_cita.emit())
        self.btn_new.setFixedHeight(38)
        self.btn_new.setMinimumWidth(120)
        lay.addWidget(self.btn_new)

        return wrap

    # ---------- Sidebar ----------
    def _build_sidebar(self) -> QWidget:
        w = QFrame(); w.setObjectName("Sidebar")
        lay = QVBoxLayout(w); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(12)

        def title(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet("background: transparent; font-weight: 600;")
            return lbl

        # Búsqueda
        self.search = QLineEdit(placeholderText="Buscar cliente")
        self.search.textChanged.connect(self._on_filter_changed)
        lay.addWidget(title("Buscar")); lay.addWidget(self.search)

        # Artistas (desde BD)
        lay.addWidget(title("Artistas"))
        self.artist_checks: Dict[str, QCheckBox] = {}
        for a in self.artists:
            chk = QCheckBox(a.name); chk.setChecked(True)
            chk.toggled.connect(self._on_filter_changed)
            self.artist_checks[a.id] = chk
            lay.addWidget(chk)

        # Estado (ALINEADO con la BD: Activa/Completada/Cancelada/En espera)
        lay.addWidget(title("Estado"))
        self.cbo_status = QComboBox()
        self.cbo_status.addItems(["Todos", "Activa", "Completada", "Cancelada", "En espera"])
        self.cbo_status.currentTextChanged.connect(self._on_filter_changed)
        lay.addWidget(self.cbo_status)

        lay.addStretch(1)
        return w

    # ---------- Navegación temporal ----------
    def _go_today(self):
        self.current_date = QDate.currentDate(); self.dp.setDate(self.current_date)
        self._refresh_all()

    def _go_prev(self):
        if self.current_view == "day":     self.current_date = self.current_date.addDays(-1)
        elif self.current_view == "week":  self.current_date = self.current_date.addDays(-7)
        elif self.current_view == "month": self.current_date = self.current_date.addMonths(-1)
        else:                              self.current_date = self.current_date.addDays(-1)
        self.dp.setDate(self.current_date); self._refresh_all()

    def _go_next(self):
        if self.current_view == "day":     self.current_date = self.current_date.addDays(1)
        elif self.current_view == "week":  self.current_date = self.current_date.addDays(7)
        elif self.current_view == "month": self.current_date = self.current_date.addMonths(1)
        else:                              self.current_date = self.current_date.addDays(1)
        self.dp.setDate(self.current_date); self._refresh_all()

    def _on_date_changed(self, d: QDate):
        self.current_date = d; self._refresh_all()

    def _on_view_changed(self, txt: str):
        mapping = {"Día": ("day", 0), "Semana": ("week", 1), "Mes": ("month", 2), "Lista": ("list", 3)}
        self.current_view, idx = mapping.get(txt, ("day", 0))
        self.views_stack.setCurrentIndex(idx)
        self._refresh_all()

    def _on_filter_changed(self, *_):
        selected = [aid for aid, chk in self.artist_checks.items() if chk.isChecked()]
        # Si todos están seleccionados, usamos [] (equivale a "todos") para no filtrar por artista
        self.selected_artist_ids = selected if len(selected) != len(self.artist_checks) else []
        self.selected_status = self.cbo_status.currentText()
        self.search_text = self.search.text().strip().lower()
        self._refresh_all()

    # ---------- Carga de datos desde BD ----------
    def _load_artists_from_db(self):
        """Lee artistas de la BD y genera un color estable por artista."""
        self.artists.clear()
        with SessionLocal() as db:
            rows = db.query(DBArtist.id, DBArtist.name).order_by(DBArtist.name.asc()).all()
        for idx, (aid, name) in enumerate(rows):
            # color estable por índice (o podrías hashear el id)
            color = self._PALETTE[idx % len(self._PALETTE)]
            self.artists.append(Artist(id=str(aid), name=name, color=color))

    def _current_visible_range(self) -> (QDate, QDate):
        """Devuelve el rango [desde, hasta] (QDate) según la vista/fecha actual."""
        if self.current_view == "day":
            return self.current_date, self.current_date
        if self.current_view == "week":
            monday = self.current_date.addDays(-(self.current_date.dayOfWeek()-1))
            return monday, monday.addDays(6)
        if self.current_view == "month":
            first = QDate(self.current_date.year(), self.current_date.month(), 1)
            last  = first.addMonths(1).addDays(-1)
            return first, last
        # list: por defecto 30 días a partir de la fecha actual seleccionada
        return self.current_date, self.current_date.addDays(30)

    def _fetch_sessions_from_db(self):
        """Consulta sesiones reales desde la BD (usando services.list_sessions) y arma self.appts."""
        # 1) Determinar rango temporal en datetimes
        q_from, q_to = self._current_visible_range()
        start_dt = datetime.combine(q_from.toPyDate(), time(0, 0, 0))
        end_dt   = datetime.combine(q_to.toPyDate(),   time(23, 59, 59))

        # 2) Filtros por artista/estado (en esta versión filtramos artista desde la UI;
        #    el estado lo filtramos también en UI porque en la BD usamos valores exactos)
        params = {"from": start_dt, "to": end_dt}
        rows = list_sessions(params)  # devuelve dicts: id, client_id, artist_id, start, end, status, price, notes

        # 3) Resolver nombres de clientes de un jalón (cache en dict)
        client_ids = {r["client_id"] for r in rows if r.get("client_id") is not None}
        client_name_by_id: Dict[int, str] = {}
        if client_ids:
            with SessionLocal() as db:
                for cid, name in db.query(Client.id, Client.name).filter(Client.id.in_(client_ids)).all():
                    client_name_by_id[cid] = name

        # 4) Armar los Appt para la UI
        appts: List[Appt] = []
        for r in rows:
            # Convertir a tipos Qt para las vistas
            start: datetime = r["start"]
            end: Optional[datetime] = r.get("end") or (start + timedelta(minutes=60))  # fallback 60 min
            qd = QDate(start.year, start.month, start.day)
            qt = QTime(start.hour, start.minute)
            duration = max(1, int((end - start).total_seconds() // 60))

            appts.append(
                Appt(
                    id=str(r["id"]),
                    client_name=client_name_by_id.get(r["client_id"], "Cliente"),
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
            if a.id == aid:
                return a
        return None

    def _filter_appts(self) -> List[Appt]:
        """Filtra en memoria según checkboxes/estado/búsqueda y rango visible."""
        # Refrescar desde BD ANTES de filtrar (para que la vista siempre esté al día)
        self._fetch_sessions_from_db()

        rows: List[Appt] = []
        for ap in self.appts:
            # Filtrar por artista: si hay selección, solo esos
            if self.selected_artist_ids and ap.artist_id not in self.selected_artist_ids:
                continue
            # Filtrar por estado (usa los valores de la BD)
            if self.selected_status != "Todos" and ap.status != self.selected_status:
                continue
            # Búsqueda por cliente
            if self.search_text and self.search_text not in ap.client_name.lower():
                continue
            rows.append(ap)

        # Filtrar por rango visible (seguridad extra, aunque ya pedimos por rango)
        start_q, end_q = self._current_visible_range()
        def in_range(a: Appt) -> bool:
            if self.current_view == "day":
                return a.date == start_q
            if self.current_view == "week" or self.current_view == "month" or self.current_view == "list":
                return start_q <= a.date <= end_q
            return True
        rows = [r for r in rows if in_range(r)]
        return rows

    def _refresh_all(self):
        rows = self._filter_appts()

        # Day
        self.day_view.configure(
            self.artists, self.current_date, self.day_start, self.day_end, self.step_min,
            self.selected_artist_ids or [a.id for a in self.artists]
        )
        self.day_view.render(rows, self._artist_by_id)

        # Week
        self.week_view.configure(
            self.artists, self.current_date, self.day_start, self.day_end, self.step_min,
            self.selected_artist_ids or [a.id for a in self.artists]
        )
        self.week_view.render(rows, self._artist_by_id)

        # Month
        self.month_view.configure(self.artists, self.current_date)
        self.month_view.render(rows, self._artist_by_id)

        # List
        self.list_view.render(rows, self._artist_by_id)


# ==============================
#   SUB-VISTAS (sin cambios estructurales)
# ==============================

def _short_name(name: str, limit: int = 12) -> str:
    """Trunca con ‘…’ si excede el límite (para encabezados)."""
    return name if len(name) <= limit else (name[:limit-1] + "…")


class DayView(QWidget):
    """Vista Día: columna Hora fija + artistas en Stretch, chips de color sólido."""
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        self.parent: AgendaPage = parent
        self.artists: List[Artist] = []
        self.date = QDate.currentDate()
        self.day_start = QTime(8, 0)
        self.day_end   = QTime(22, 0)
        self.step_min  = 30
        self.artist_order: List[str] = []

        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)
        self.subtitle = QLabel(""); self.subtitle.setStyleSheet("color:#666; background: transparent;")
        lay.addWidget(self.subtitle)

        self.tbl = QTableWidget(); self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers); self.tbl.setSelectionMode(self.tbl.NoSelection)
        # encabezados “transparentes”
        self.tbl.setStyleSheet("QHeaderView::section { background: transparent; }")
        lay.addWidget(self.tbl, stretch=1)

    def configure(self, artists: List[Artist], date: QDate, start: QTime, end: QTime, step: int, artist_ids: List[str]):
        self.artists = artists; self.date = date
        self.day_start, self.day_end, self.step_min = start, end, step
        self.artist_order = artist_ids

    def render(self, appts: List[Appt], artist_lookup):
        self.subtitle.setText(self.date.toString("ddd dd MMM yyyy"))

        steps = int(self.day_start.secsTo(self.day_end) / 60 // self.step_min)
        self.tbl.clear()
        self.tbl.setRowCount(steps)
        self.tbl.setColumnCount(1 + len(self.artist_order))

        headers = ["Hora"] + [_short_name(self._artist_name(aid)) for aid in self.artist_order]
        self.tbl.setHorizontalHeaderLabels(headers)

        # Misma anchura para artistas (centrados)
        hdr = self.tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Fixed)
        self.tbl.setColumnWidth(0, 80)                          # Hora
        for c in range(1, 1 + len(self.artist_order)):
            hdr.setSectionResizeMode(c, QHeaderView.Stretch)    # artistas comparten espacio

        # Filas de hora
        t = QTime(self.day_start)
        for r in range(steps):
            self.tbl.setItem(r, 0, QTableWidgetItem(t.toString("hh:mm") if t.minute() == 0 else ""))
            t = t.addSecs(self.step_min * 60)

        # Citas del día
        for ap in appts:
            if ap.date != self.date or ap.artist_id not in self.artist_order:
                continue

            col = 1 + self.artist_order.index(ap.artist_id)
            row_start = int(self.day_start.secsTo(ap.start) / 60 // self.step_min)
            row_span  = max(1, ap.duration_min // self.step_min)

            # Chip con RELLENO sólido
            chip = QFrame()
            chip.setAutoFillBackground(True)
            chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            lay = QVBoxLayout(chip); lay.setContentsMargins(6, 4, 6, 4)

            lbl = QLabel(f"{ap.client_name}\n{ap.service} • {ap.start.toString('hh:mm')}")
            lbl.setWordWrap(True)
            lay.addWidget(lbl)

            a = artist_lookup(ap.artist_id)
            base = a.color if a else "#666666"
            chip.setStyleSheet(
                f"background:{base};"
                f"border:1px solid rgba(0,0,0,0.18);"
                f"border-radius:6px; color:white;"
            )

            self.tbl.setSpan(row_start, col, row_span, 1)
            self.tbl.setCellWidget(row_start, col, chip)

    def _artist_name(self, aid: str) -> str:
        for a in self.artists:
            if a.id == aid: return a.name
        return "Artista"


class WeekView(QWidget):
    """Vista Semana: columna Hora + 7 días en Stretch (MVP: 1 artista)."""
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        self.parent: AgendaPage = parent
        self.date = QDate.currentDate()
        self.day_start = QTime(8,0)
        self.day_end   = QTime(22,0)
        self.step_min  = 30
        self.artist_id = None

        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(6)
        self.subtitle = QLabel(""); self.subtitle.setStyleSheet("color:#666; background: transparent;")
        lay.addWidget(self.subtitle)

        self.tbl = QTableWidget(); self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers); self.tbl.setSelectionMode(self.tbl.NoSelection)
        self.tbl.setStyleSheet("QHeaderView::section { background: transparent; }")
        lay.addWidget(self.tbl, stretch=1)

    def configure(self, artists: List[Artist], date: QDate, start: QTime, end: QTime, step: int, artist_ids: List[str]):
        self.date = date; self.day_start = start; self.day_end = end; self.step_min = step
        self.artist_id = (artist_ids[0] if artist_ids else (artists[0].id if artists else None))

    def render(self, appts: List[Appt], artist_lookup):
        monday = self.date.addDays(-(self.date.dayOfWeek()-1))
        self.subtitle.setText(f"Semana de {monday.toString('dd MMM yyyy')}")

        steps = int(self.day_start.secsTo(self.day_end) / 60 // self.step_min)
        self.tbl.clear()
        self.tbl.setRowCount(steps)
        self.tbl.setColumnCount(1 + 7)
        self.tbl.setHorizontalHeaderLabels(["Hora"] + [(monday.addDays(i)).toString("ddd dd") for i in range(7)])

        hdr = self.tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Fixed)
        self.tbl.setColumnWidth(0, 80)
        for c in range(1, 8):
            hdr.setSectionResizeMode(c, QHeaderView.Stretch)

        # Filas de hora
        t = QTime(self.day_start)
        for r in range(steps):
            self.tbl.setItem(r, 0, QTableWidgetItem(t.toString("hh:mm") if t.minute() == 0 else ""))
            t = t.addSecs(self.step_min * 60)

        if not self.artist_id:
            return

        for ap in appts:
            if ap.artist_id != self.artist_id: continue
            if not (monday <= ap.date <= monday.addDays(6)): continue

            col = 1 + monday.daysTo(ap.date)
            row_start = int(self.day_start.secsTo(ap.start) / 60 // self.step_min)
            row_span  = max(1, ap.duration_min // self.step_min)

            chip = QFrame(); chip.setAutoFillBackground(True)
            chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            lay = QVBoxLayout(chip); lay.setContentsMargins(6,4,6,4)
            lbl = QLabel(f"{ap.client_name}\n{ap.service} • {ap.start.toString('hh:mm')}")
            lbl.setWordWrap(True); lay.addWidget(lbl)

            a = artist_lookup(ap.artist_id); base = a.color if a else "#666666"
            chip.setStyleSheet(
                f"background:{base};border:1px solid rgba(0,0,0,0.18);"
                f"border-radius:6px; color:white;"
            )

            self.tbl.setSpan(row_start, col, row_span, 1)
            self.tbl.setCellWidget(row_start, col, chip)


class MonthView(QWidget):
    """Vista Mes (overview)."""
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
        self.subtitle = QLabel(""); self.subtitle.setStyleSheet("color:#666; background: transparent;")
        lay.addWidget(self.subtitle)

        self.tbl = QTableWidget()
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.horizontalHeader().setVisible(False)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionMode(self.tbl.NoSelection)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tbl, stretch=1)
        self.date = QDate.currentDate()

    def configure(self, artists: List[Artist], date: QDate):
        self.date = date

    def render(self, appts: List[Appt], artist_lookup):
        y, m = self.date.year(), self.date.month()
        first = QDate(y, m, 1)
        first_col = first.dayOfWeek() - 1
        days_in_month = first.daysInMonth()
        self.subtitle.setText(self.date.toString("MMMM yyyy"))

        self.tbl.clear()
        self.tbl.setRowCount(6); self.tbl.setColumnCount(7)

        # Agrupar por día
        byday: Dict[int, List[Appt]] = {}
        for ap in appts:
            if ap.date.month() == m and ap.date.year() == y:
                byday.setdefault(ap.date.day(), []).append(ap)

        day = 1
        for r in range(6):
            for c in range(7):
                cell = QWidget(); lay = QVBoxLayout(cell); lay.setContentsMargins(6,6,6,6); lay.setSpacing(2)
                lbl_day = QLabel(""); lay.addWidget(lbl_day)
                if (r == 0 and c < first_col) or day > days_in_month:
                    self.tbl.setCellWidget(r, c, cell)
                    if not (r == 0 and c < first_col): day += 1
                    continue

                lbl_day.setText(f"{day}")
                for ap in byday.get(day, [])[:3]:
                    a = artist_lookup(ap.artist_id)
                    color = a.color if a else "#999"
                    chip = QLabel(f"• {ap.start.toString('hh:mm')} {ap.client_name}")
                    chip.setStyleSheet(f"color:{color};")
                    lay.addWidget(chip)

                self.tbl.setCellWidget(r, c, cell)
                day += 1


class ListView(QWidget):
    """Vista Lista: tabla simple con todas las citas filtradas."""
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Hora", "Cliente", "Artista", "Servicio", "Estado"])
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers); self.tbl.setSelectionMode(self.tbl.NoSelection)
        self.tbl.horizontalHeader().setStretchLastSection(True)
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
            self.tbl.setItem(row, 4, QTableWidgetItem(ap.service))
            self.tbl.setItem(row, 5, QTableWidgetItem(ap.status))
