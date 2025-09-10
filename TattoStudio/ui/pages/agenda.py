# ui/pages/agenda.py
from dataclasses import dataclass
from typing import List, Dict, Optional
from PyQt5.QtCore import Qt, QDate, QTime, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDateEdit, QFrame, QListWidget, QListWidgetItem, QCheckBox, QSplitter,
    QStackedWidget, QTableWidget, QTableWidgetItem, QSizePolicy, QLineEdit
)

# ==============================
#   MODELO (mock en memoria)
# ==============================

@dataclass
class Artist:
    id: str
    name: str
    color: str  # color principal (para chips)


@dataclass
class Appt:
    id: str
    client_name: str
    artist_id: str
    date: QDate          # fecha (día) de la cita
    start: QTime         # hora de inicio
    duration_min: int    # duración en minutos
    service: str
    status: str          # pending / confirmed / in_progress / done / no_show / cancelled


# ==============================
#   AGENDA PAGE (cascarón)
# ==============================

class AgendaPage(QWidget):
    """
    Agenda tipo Google Calendar (cascarón para Avance #1):
    - Toolbar: Hoy, <, >, selector de fecha, selector de vista (Día / Semana / Mes / Lista), CTA 'Nueva cita'.
    - Filtros laterales: Artistas (checklist), Estado, búsqueda.
    - Zona principal: stack de sub-vistas (Day/Week/Month/List) con citas mock.
    - Sin BD; todo en memoria.

    Señales disponibles si luego quieres enganchar:
    - crear_cita: cuando se pulsa 'Nueva cita' (aquí abre un diálogo mock o podrías navegar).
    - abrir_cita(dict): cuando el usuario hace clic en un chip (te manda el dict de la cita).
    """
    crear_cita = pyqtSignal()
    abrir_cita = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        # ------- Estado interno -------
        self.current_date: QDate = QDate.currentDate()
        self.current_view: str = "day"  # day | week | month | list
        self.selected_artist_ids: List[str] = []  # vacío = todos
        self.selected_status: str = "Todos"       # filtro sencillo
        self.search_text: str = ""

        # Jornada visible (puedes cambiarlo si quieres)
        self.day_start = QTime(9, 0)
        self.day_end   = QTime(21, 0)
        self.step_min  = 30   # intervalo en minutos

        # ------- Datos MOCK -------
        self.artists: List[Artist] = [
            Artist("a1", "Dylan", "#4ade80"),     # verde
            Artist("a2", "Sara",  "#60a5fa"),     # azul
            Artist("a3", "Alex",  "#f472b6"),     # rosa
        ]
        # algunas citas de muestra
        today = QDate.currentDate()
        self.appts: List[Appt] = [
            Appt("c1", "Juan Pérez", "a1", today, QTime(10, 0), 60, "Línea fina", "pending"),
            Appt("c2", "María López", "a2", today, QTime(11, 30), 90, "Color", "confirmed"),
            Appt("c3", "Luis Mora", "a1", today, QTime(15, 0), 120, "Realismo", "in_progress"),
            Appt("c4", "Ana Ríos", "a3", today.addDays(1), QTime(12, 0), 60, "Piercing", "done"),
            Appt("c5", "K. Gómez", "a2", today.addDays(2), QTime(17, 30), 60, "Retoque", "pending"),
        ]

        # ------- UI -------
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        # Título
        title = QLabel("Agenda")
        title.setObjectName("H1")
        root.addWidget(title)

        # Toolbar superior
        toolbar = self._build_toolbar()
        root.addLayout(toolbar)

        # Splitter: filtros (izq) | vistas (der)
        split = QSplitter()
        split.setOrientation(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        root.addWidget(split, stretch=1)

        # Panel lateral (filtros)
        self.sidebar = self._build_sidebar()
        split.addWidget(self.sidebar)

        # Zona de vistas (stack)
        self.views_stack = QStackedWidget()
        split.addWidget(self.views_stack)
        split.setSizes([280, 900])  # ancho inicial aproximado

        # Sub-vistas
        self.day_view   = DayView(self)     # requiere artists/appts/filters
        self.week_view  = WeekView(self)
        self.month_view = MonthView(self)
        self.list_view  = ListView(self)

        self.views_stack.addWidget(self.day_view)    # index 0
        self.views_stack.addWidget(self.week_view)   # index 1
        self.views_stack.addWidget(self.month_view)  # index 2
        self.views_stack.addWidget(self.list_view)   # index 3

        # Render inicial
        self._refresh_all()

    # ---------- Toolbar ----------
    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout(); bar.setSpacing(8)

        self.btn_today = QPushButton("Hoy")
        self.btn_prev  = QPushButton("‹")
        self.btn_next  = QPushButton("›")

        self.btn_today.clicked.connect(self._go_today)
        self.btn_prev.clicked.connect(self._go_prev)
        self.btn_next.clicked.connect(self._go_next)

        bar.addWidget(self.btn_today)
        bar.addWidget(self.btn_prev)
        bar.addWidget(self.btn_next)

        # selector de fecha
        self.dp = QDateEdit(self.current_date)
        self.dp.setCalendarPopup(True)
        self.dp.dateChanged.connect(self._on_date_changed)
        bar.addWidget(self.dp)

        # selector de vista
        bar.addSpacing(12)
        bar.addWidget(QLabel("Vista:"))
        self.cbo_view = QComboBox()
        self.cbo_view.addItems(["Día", "Semana", "Mes", "Lista"])
        self.cbo_view.currentTextChanged.connect(self._on_view_changed)
        bar.addWidget(self.cbo_view)

        # separar CTA a la derecha
        bar.addStretch(1)

        # CTA Nueva cita (por ahora no guarda, es demo)
        self.btn_new = QPushButton("Nueva cita")
        self.btn_new.setObjectName("CTA")
        self.btn_new.clicked.connect(lambda: self.crear_cita.emit())
        bar.addWidget(self.btn_new)

        # Bloquear tiempo (placeholder)
        self.btn_block = QPushButton("Bloquear tiempo")
        bar.addWidget(self.btn_block)

        return bar

    # ---------- Sidebar (filtros) ----------
    def _build_sidebar(self) -> QWidget:
        w = QFrame()
        w.setObjectName("Sidebar")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        # Búsqueda
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por cliente…")
        self.search.textChanged.connect(self._on_filter_changed)
        lay.addWidget(QLabel("Buscar"))
        lay.addWidget(self.search)

        # Filtro por artista (checklist)
        lay.addWidget(QLabel("Artistas"))
        self.artist_checks: Dict[str, QCheckBox] = {}
        for a in self.artists:
            chk = QCheckBox(a.name)
            chk.setChecked(True)  # por defecto todos
            chk.toggled.connect(self._on_filter_changed)
            self.artist_checks[a.id] = chk
            lay.addWidget(chk)

        # Filtro por estado
        lay.addSpacing(6)
        lay.addWidget(QLabel("Estado"))
        self.cbo_status = QComboBox()
        self.cbo_status.addItems(["Todos","pending","confirmed","in_progress","done","no_show","cancelled"])
        self.cbo_status.currentTextChanged.connect(self._on_filter_changed)
        lay.addWidget(self.cbo_status)

        lay.addStretch(1)
        return w

    # ---------- Navegación temporal ----------
    def _go_today(self):
        self.current_date = QDate.currentDate()
        self.dp.setDate(self.current_date)
        self._refresh_all()

    def _go_prev(self):
        if self.current_view == "day":
            self.current_date = self.current_date.addDays(-1)
        elif self.current_view == "week":
            self.current_date = self.current_date.addDays(-7)
        elif self.current_view == "month":
            self.current_date = self.current_date.addMonths(-1)
        else:  # list
            self.current_date = self.current_date.addDays(-1)
        self.dp.setDate(self.current_date)
        self._refresh_all()

    def _go_next(self):
        if self.current_view == "day":
            self.current_date = self.current_date.addDays(1)
        elif self.current_view == "week":
            self.current_date = self.current_date.addDays(7)
        elif self.current_view == "month":
            self.current_date = self.current_date.addMonths(1)
        else:
            self.current_date = self.current_date.addDays(1)
        self.dp.setDate(self.current_date)
        self._refresh_all()

    def _on_date_changed(self, d: QDate):
        self.current_date = d
        self._refresh_all()

    def _on_view_changed(self, txt: str):
        mapping = {"Día": ("day", 0), "Semana": ("week", 1), "Mes": ("month", 2), "Lista": ("list", 3)}
        self.current_view, idx = mapping.get(txt, ("day", 0))
        self.views_stack.setCurrentIndex(idx)
        self._refresh_all()

    def _on_filter_changed(self, *_):
        # artistas seleccionados (si todos checados → interpretamos “todos”)
        selected = [aid for aid, chk in self.artist_checks.items() if chk.isChecked()]
        self.selected_artist_ids = selected if len(selected) != len(self.artist_checks) else []
        self.selected_status = self.cbo_status.currentText()
        self.search_text = self.search.text().strip().lower()
        self._refresh_all()

    # ---------- Helpers de datos/filtrado ----------
    def _artist_by_id(self, aid: str) -> Optional[Artist]:
        for a in self.artists:
            if a.id == aid:
                return a
        return None

    def _filter_appts(self) -> List[Appt]:
        """Filtra por artista/estado/búsqueda según sidebar; además aplica rango de fecha según la vista."""
        rows = []
        for ap in self.appts:
            # Filtro por artista
            if self.selected_artist_ids and ap.artist_id not in self.selected_artist_ids:
                continue
            # Filtro por estado
            if self.selected_status != "Todos" and ap.status != self.selected_status:
                continue
            # Filtro por búsqueda
            if self.search_text and self.search_text not in ap.client_name.lower():
                continue
            rows.append(ap)

        # Rango temporal por vista
        if self.current_view == "day":
            rows = [r for r in rows if r.date == self.current_date]
        elif self.current_view == "week":
            monday = self.current_date.addDays(-(self.current_date.dayOfWeek()-1))
            sunday = monday.addDays(6)
            rows = [r for r in rows if monday <= r.date <= sunday]
        elif self.current_view == "month":
            first = QDate(self.current_date.year(), self.current_date.month(), 1)
            last  = first.addMonths(1).addDays(-1)
            rows = [r for r in rows if first <= r.date <= last]
        else:
            # lista: no recorta; o podrías limitar a ±30 días
            pass

        return rows

    # ---------- Render global ----------
    def _refresh_all(self):
        rows = self._filter_appts()
        # Day
        self.day_view.configure(self.artists, self.current_date, self.day_start, self.day_end, self.step_min,
                                self.selected_artist_ids or [a.id for a in self.artists])
        self.day_view.render(rows, self._artist_by_id)

        # Week
        self.week_view.configure(self.artists, self.current_date, self.day_start, self.day_end, self.step_min,
                                 self.selected_artist_ids or [a.id for a in self.artists])
        self.week_view.render(rows, self._artist_by_id)

        # Month
        self.month_view.configure(self.artists, self.current_date)
        self.month_view.render(rows, self._artist_by_id)

        # List
        self.list_view.render(rows, self._artist_by_id)


# ==============================
#   SUB-VISTAS
# ==============================

class DayView(QWidget):
    """
    Vista Día:
    - Columnas = artistas seleccionados (más 1 col de 'Hora')
    - Filas = intervalos de tiempo (step_min)
    - Coloca citas como 'spans' en la tabla (sin drag/drop por ahora).
    """
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        self.parent: AgendaPage = parent
        self.artists: List[Artist] = []
        self.date = QDate.currentDate()
        self.day_start = QTime(9, 0)
        self.day_end   = QTime(21, 0)
        self.step_min  = 30
        self.artist_order: List[str] = []  # ids visibles

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # título secundario
        self.subtitle = QLabel("")
        self.subtitle.setStyleSheet("color:#666;")
        lay.addWidget(self.subtitle)

        self.tbl = QTableWidget()
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionMode(self.tbl.NoSelection)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tbl, stretch=1)

    def configure(self, artists: List[Artist], date: QDate, start: QTime, end: QTime, step: int, artist_ids: List[str]):
        self.artists = artists
        self.date = date
        self.day_start, self.day_end, self.step_min = start, end, step
        self.artist_order = artist_ids

    def render(self, appts: List[Appt], artist_lookup):
        # Subtítulo (ej. "Mié 10 sep 2025")
        self.subtitle.setText(self.date.toString("ddd dd MMM yyyy"))

        # construir grid
        steps = int(self.day_start.secsTo(self.day_end) / 60 // self.step_min)
        self.tbl.clear()
        self.tbl.setRowCount(steps)
        self.tbl.setColumnCount(1 + len(self.artist_order))
        headers = ["Hora"] + [self._artist_name(aid) for aid in self.artist_order]
        self.tbl.setHorizontalHeaderLabels(headers)
        self.tbl.setColumnWidth(0, 80)

        # filas de hora
        t = QTime(self.day_start)
        for r in range(steps):
            if t.minute() == 0:
                self.tbl.setItem(r, 0, QTableWidgetItem(t.toString("hh:mm")))
            else:
                self.tbl.setItem(r, 0, QTableWidgetItem(""))
            t = t.addSecs(self.step_min * 60)

        # colocar citas del día
        for ap in appts:
            if ap.date != self.date:
                continue
            if ap.artist_id not in self.artist_order:
                continue

            col = 1 + self.artist_order.index(ap.artist_id)
            row_start = int(self.day_start.secsTo(ap.start) / 60 // self.step_min)
            row_span = max(1, ap.duration_min // self.step_min)

            # chip simple como QFrame con etiqueta
            chip = QFrame()
            chip.setObjectName("ChipAppt")
            chip_lay = QVBoxLayout(chip); chip_lay.setContentsMargins(6, 4, 6, 4)
            lbl = QLabel(f"{ap.client_name}\n{ap.service} • {ap.start.toString('hh:mm')}")
            lbl.setWordWrap(True)
            chip_lay.addWidget(lbl)

            # color por artista
            artist = artist_lookup(ap.artist_id)
            base_color = artist.color if artist else "#666"
            chip.setStyleSheet(f"QFrame#ChipAppt {{ background:{base_color}; color:white; border-radius:6px; }}")

            # span vertical para cubrir la duración
            # IMPORTANTE: limpiar cualquier contenido previo en el rango
            self.tbl.setSpan(row_start, col, row_span, 1)
            self.tbl.setCellWidget(row_start, col, chip)

    def _artist_name(self, aid: str) -> str:
        for a in self.artists:
            if a.id == aid:
                return a.name
        return "Artista"


class WeekView(QWidget):
    """
    Vista Semana (simple):
    - Columnas = Lunes..Domingo (+ col 'Hora')
    - Filas = intervalos de tiempo
    - Si hay múltiples artistas seleccionados, se toma el primero (para MVP).
    """
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        self.parent: AgendaPage = parent
        self.date = QDate.currentDate()
        self.day_start = QTime(9,0)
        self.day_end   = QTime(21,0)
        self.step_min  = 30
        self.artist_id = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.subtitle = QLabel("")
        self.subtitle.setStyleSheet("color:#666;")
        lay.addWidget(self.subtitle)

        self.tbl = QTableWidget()
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionMode(self.tbl.NoSelection)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tbl, stretch=1)

    def configure(self, artists: List[Artist], date: QDate, start: QTime, end: QTime, step: int, artist_ids: List[str]):
        self.date = date; self.day_start = start; self.day_end = end; self.step_min = step
        # Para MVP: tomamos el primer artista seleccionado; si no hay, tomamos todos y mostramos el primero
        self.artist_id = (artist_ids[0] if artist_ids else (artists[0].id if artists else None))

    def render(self, appts: List[Appt], artist_lookup):
        monday = self.date.addDays(-(self.date.dayOfWeek()-1))
        self.subtitle.setText(f"Semana de {monday.toString('dd MMM yyyy')}")

        steps = int(self.day_start.secsTo(self.day_end) / 60 // self.step_min)
        self.tbl.clear()
        self.tbl.setRowCount(steps)
        self.tbl.setColumnCount(1 + 7)
        headers = ["Hora"] + [(monday.addDays(i)).toString("ddd dd") for i in range(7)]
        self.tbl.setHorizontalHeaderLabels(headers)
        self.tbl.setColumnWidth(0, 80)

        # filas de hora
        t = QTime(self.day_start)
        for r in range(steps):
            self.tbl.setItem(r, 0, QTableWidgetItem(t.toString("hh:mm") if t.minute() == 0 else ""))
            t = t.addSecs(self.step_min * 60)

        # Solo un artista (MVP)
        if not self.artist_id:
            return

        # colocar citas de la semana de ese artista
        for ap in appts:
            if ap.artist_id != self.artist_id:
                continue
            # columna: día de la semana 0..6
            if not (monday <= ap.date <= monday.addDays(6)):
                continue
            col = 1 + monday.daysTo(ap.date)

            row_start = int(self.day_start.secsTo(ap.start) / 60 // self.step_min)
            row_span = max(1, ap.duration_min // self.step_min)

            chip = QFrame()
            chip.setObjectName("ChipAppt")
            chip_lay = QVBoxLayout(chip); chip_lay.setContentsMargins(6,4,6,4)
            lbl = QLabel(f"{ap.client_name}\n{ap.service} • {ap.start.toString('hh:mm')}")
            lbl.setWordWrap(True); chip_lay.addWidget(lbl)

            artist = artist_lookup(ap.artist_id)
            base_color = artist.color if artist else "#666"
            chip.setStyleSheet(f"QFrame#ChipAppt {{ background:{base_color}; color:white; border-radius:6px; }}")

            self.tbl.setSpan(row_start, col, row_span, 1)
            self.tbl.setCellWidget(row_start, col, chip)


class MonthView(QWidget):
    """
    Vista Mes (overview simple):
    - Tabla 7x6 (L-D) con el número de día y hasta 3 títulos de citas mock.
    """
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        self.parent: AgendaPage = parent
        self.date = QDate.currentDate()

        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
        self.subtitle = QLabel(""); self.subtitle.setStyleSheet("color:#666;")
        lay.addWidget(self.subtitle)

        self.tbl = QTableWidget()
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.horizontalHeader().setVisible(False)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionMode(self.tbl.NoSelection)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tbl, stretch=1)

    def configure(self, artists: List[Artist], date: QDate):
        self.date = date

    def render(self, appts: List[Appt], artist_lookup):
        y, m = self.date.year(), self.date.month()
        first = QDate(y, m, 1)
        first_col = first.dayOfWeek() - 1  # 0=lunes
        days_in_month = first.daysInMonth()

        self.subtitle.setText(self.date.toString("MMMM yyyy"))

        self.tbl.clear()
        self.tbl.setRowCount(6)
        self.tbl.setColumnCount(7)

        # Precalcular citas por día
        byday: Dict[int, List[Appt]] = {}
        for ap in appts:
            if ap.date.month() == m and ap.date.year() == y:
                byday.setdefault(ap.date.day(), []).append(ap)

        day = 1
        for row in range(6):
            for col in range(7):
                cell = QWidget(); lay = QVBoxLayout(cell); lay.setContentsMargins(6,6,6,6); lay.setSpacing(2)
                lbl_day = QLabel("")
                lay.addWidget(lbl_day)
                # celdas antes del primer día
                if row == 0 and col < first_col:
                    self.tbl.setCellWidget(row, col, cell)
                    continue
                if day > days_in_month:
                    self.tbl.setCellWidget(row, col, cell)
                    continue

                lbl_day.setText(f"{day}")
                # mostrar hasta 3 eventos
                for ap in byday.get(day, [])[:3]:
                    a = artist_lookup(ap.artist_id)
                    color = a.color if a else "#999"
                    chip = QLabel(f"• {ap.start.toString('hh:mm')} {ap.client_name}")
                    chip.setStyleSheet(f"color:{color};")
                    lay.addWidget(chip)

                self.tbl.setCellWidget(row, col, cell)
                day += 1


class ListView(QWidget):
    """
    Vista Lista (tabla simple):
    - Columnas: Fecha, Hora, Cliente, Artista, Servicio, Estado
    """
    def __init__(self, parent: AgendaPage):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Hora", "Cliente", "Artista", "Servicio", "Estado"])
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionMode(self.tbl.NoSelection)
        self.tbl.horizontalHeader().setStretchLastSection(True)
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
