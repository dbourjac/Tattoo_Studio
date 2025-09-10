from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSpacerItem, QSizePolicy, QFrame
)

class ClientsPage(QWidget):
    """
    Lista maestra de clientes (cascarón):
    - Toolbar con "Nuevo cliente"
    - Buscador + ordenar
    - Tabla con datos mock y paginación simple
    - Doble clic abre la "Ficha de cliente" (placeholder)
    Señales:
      - crear_cliente()           -> navegar al formulario "Nuevo cliente"
      - abrir_cliente(client:dict)-> abrir ficha (con dict del cliente)
    """
    crear_cliente = pyqtSignal()
    abrir_cliente = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        self.page_size = 10
        self.current_page = 1
        self.search_text = ""
        self.order_by = "A–Z"

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # Título
        title = QLabel("Clientes")
        title.setObjectName("H1")
        root.addWidget(title)

        # ---- Toolbar ----
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_new = QPushButton("Nuevo cliente")
        self.btn_new.setObjectName("CTA")
        self.btn_new.setMinimumHeight(34)
        self.btn_new.clicked.connect(self.crear_cliente.emit)
        toolbar.addWidget(self.btn_new)

        toolbar.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # (futuros) Importar/Exportar deshabilitados
        self.btn_import = QPushButton("Importar CSV"); self.btn_import.setEnabled(False)
        self.btn_export = QPushButton("Exportar CSV"); self.btn_export.setEnabled(False)
        toolbar.addWidget(self.btn_import)
        toolbar.addWidget(self.btn_export)

        root.addLayout(toolbar)

        # ---- Filtros: Buscar + Ordenar ----
        filters = QHBoxLayout(); filters.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre, teléfono o correo…")
        self.search.textChanged.connect(self._on_search)
        filters.addWidget(self.search, stretch=1)

        self.cbo_order = QComboBox()
        self.cbo_order.addItems(["A–Z", "Última cita", "Próxima cita", "Fecha de alta"])
        self.cbo_order.currentTextChanged.connect(self._on_change_order)
        filters.addWidget(QLabel("Ordenar por:"))
        filters.addWidget(self.cbo_order)

        root.addLayout(filters)

        # ---- Tabla ----
        table_box = QFrame()
        table_box.setObjectName("Card")
        tv = QVBoxLayout(table_box); tv.setContentsMargins(12, 12, 12, 12); tv.setSpacing(8)

        self.table = QTableWidget(0, 7, self)
        self.table.setHorizontalHeaderLabels([
            "Cliente", "Contacto", "Artista", "Próxima cita", "Etiquetas", "Estado", " "
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self._on_double_click)

        tv.addWidget(self.table)
        root.addWidget(table_box, stretch=1)

        # ---- Paginación ----
        pager = QHBoxLayout(); pager.setSpacing(8)
        self.btn_prev = QPushButton("⟵"); self.btn_next = QPushButton("⟶")
        self.lbl_page = QLabel("Página 1/1")
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        pager.addWidget(self.btn_prev); pager.addWidget(self.btn_next)
        pager.addWidget(self.lbl_page)
        pager.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        root.addLayout(pager)

        # Datos de demo (mock)
        self._seed_mock()
        self._refresh()

    # ---------- Datos mock y filtrado ----------
    def _seed_mock(self):
        self._all = [
            {"id": 1,  "nombre": "Ana López",        "tel": "555-1010", "email": "ana@demo.com",
             "artista": "Dylan", "proxima": "10 Sep 12:00", "etiquetas": "VIP", "estado": "Activo"},
            {"id": 2,  "nombre": "Bruno Pérez",      "tel": "555-1011", "email": "bruno@demo.com",
             "artista": "Karla", "proxima": "—",               "etiquetas": "walk-in", "estado": "Activo"},
            {"id": 3,  "nombre": "Carla Gómez",      "tel": "555-1012", "email": "carla@demo.com",
             "artista": "Dylan", "proxima": "09 Sep 17:30", "etiquetas": "", "estado": "Activo"},
            {"id": 4,  "nombre": "Daniel Ortiz",     "tel": "555-1013", "email": "daniel@demo.com",
             "artista": "Luis",  "proxima": "—",               "etiquetas": "no-show", "estado": "Activo"},
            {"id": 5,  "nombre": "Elena Ruiz",       "tel": "555-1014", "email": "elena@demo.com",
             "artista": "Karla", "proxima": "14 Sep 11:00", "etiquetas": "referido", "estado": "Activo"},
            {"id": 6,  "nombre": "Fernando Silva",   "tel": "555-1015", "email": "fer@demo.com",
             "artista": "Dylan", "proxima": "—",               "etiquetas": "", "estado": "Archivado"},
            {"id": 7,  "nombre": "Gina Torres",      "tel": "555-1016", "email": "gina@demo.com",
             "artista": "Luis",  "proxima": "08 Sep 16:00", "etiquetas": "nuevo", "estado": "Activo"},
            {"id": 8,  "nombre": "Hugo Ramírez",     "tel": "555-1017", "email": "hugo@demo.com",
             "artista": "Dylan", "proxima": "—",               "etiquetas": "", "estado": "Activo"},
            {"id": 9,  "nombre": "Irene Villalobos", "tel": "555-1018", "email": "irene@demo.com",
             "artista": "Karla", "proxima": "—",               "etiquetas": "VIP", "estado": "Activo"},
            {"id": 10, "nombre": "Javier Núñez",     "tel": "555-1019", "email": "javi@demo.com",
             "artista": "Luis",  "proxima": "15 Sep 09:00", "etiquetas": "", "estado": "Activo"},
            {"id": 11, "nombre": "Kevin Araujo",     "tel": "555-1020", "email": "kevin@demo.com",
             "artista": "Dylan", "proxima": "—",               "etiquetas": "", "estado": "Activo"},
            {"id": 12, "nombre": "Leslie Peña",      "tel": "555-1021", "email": "leslie@demo.com",
             "artista": "Karla", "proxima": "—",               "etiquetas": "", "estado": "Activo"},
        ]

    def _apply_filters(self):
        txt = self.search_text.lower().strip()
        rows = [c for c in self._all if (
            txt in c["nombre"].lower()
            or txt in c["tel"].lower()
            or txt in c["email"].lower()
        )] if txt else list(self._all)

        if self.order_by == "A–Z":
            rows.sort(key=lambda c: c["nombre"].lower())
        # Otros órdenes (placeholders por ahora):
        # "Última cita", "Próxima cita", "Fecha de alta" – se implementarán en Avance #2.

        return rows

    def _refresh(self):
        rows = self._apply_filters()
        total_pages = max(1, (len(rows) + self.page_size - 1) // self.page_size)
        self.current_page = min(self.current_page, total_pages)

        start = (self.current_page - 1) * self.page_size
        page_rows = rows[start:start + self.page_size]

        self.table.setRowCount(len(page_rows))
        for r, c in enumerate(page_rows):
            self.table.setItem(r, 0, QTableWidgetItem(c["nombre"]))
            self.table.setItem(r, 1, QTableWidgetItem(f'{c["tel"]}  ·  {c["email"]}'))
            self.table.setItem(r, 2, QTableWidgetItem(c["artista"]))
            self.table.setItem(r, 3, QTableWidgetItem(c["proxima"]))
            self.table.setItem(r, 4, QTableWidgetItem(c["etiquetas"]))
            self.table.setItem(r, 5, QTableWidgetItem(c["estado"]))
            # Columna acciones vacía por ahora (podríamos poner un botón "Ver")
            # Guardamos el id en "data" para recuperarlo al doble clic:
            self.table.item(r, 0).setData(Qt.UserRole, c["id"])

        self.lbl_page.setText(f"Página {self.current_page}/{total_pages}")
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < total_pages)

    # ---------- Eventos UI ----------
    def _on_search(self, text: str):
        self.search_text = text
        self.current_page = 1
        self._refresh()

    def _on_change_order(self, text: str):
        self.order_by = text
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
        # busca el dict completo
        for c in self._all:
            if c["id"] == cid:
                self.abrir_cliente.emit(c)
                break
