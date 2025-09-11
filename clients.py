from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSpacerItem, QSizePolicy, QFrame
)


class ClientsPage(QWidget):
    """
    Lista de clientes (cascarón estilizado como Agenda):
    - Toolbar compacta con "Nuevo cliente" y (futuro) Importar/Exportar.
    - Fila de filtros: Buscar, Ordenar por, Mostrar (tamaño de página).
    - Tabla (6 columnas): Cliente, Contacto, Artista, Próxima cita, Etiquetas, Estado.
    - Paginación simple.
    Señales:
      - crear_cliente()            -> navegar a 'Nuevo cliente'
      - abrir_cliente(client:dict) -> abrir ficha (con el dict del cliente)
    """
    crear_cliente = pyqtSignal()
    abrir_cliente = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        # Estado de UI / datos
        self.page_size = 10
        self.current_page = 1
        self.search_text = ""
        self.order_by = "A–Z"

        # ===== Root =====
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        # ========== Toolbar (estilo Agenda) ==========
        tb_frame = QFrame()
        tb_frame.setObjectName("Toolbar")
        tb = QHBoxLayout(tb_frame)
        tb.setContentsMargins(10, 8, 10, 8)
        tb.setSpacing(8)

        self.btn_new = QPushButton("Nuevo cliente")
        self.btn_new.setObjectName("CTA")
        self.btn_new.setFixedHeight(38)
        self.btn_new.clicked.connect(self.crear_cliente.emit)
        tb.addWidget(self.btn_new)

        tb.addStretch(1)

        # Import/Export (deshabilitados por ahora, con estilo suave)
        self.btn_import = QPushButton("Importar CSV")
        self.btn_import.setObjectName("GhostSmall")
        self.btn_import.setEnabled(False)

        self.btn_export = QPushButton("Exportar CSV")
        self.btn_export.setObjectName("GhostSmall")
        self.btn_export.setEnabled(False)

        tb.addWidget(self.btn_import)
        tb.addWidget(self.btn_export)

        root.addWidget(tb_frame)

        # ========== Filtros (Buscar / Ordenar / Mostrar) ==========
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
        self.cbo_order.currentTextChanged.connect(self._on_change_order)
        self.cbo_order.setFixedHeight(36)
        filters.addWidget(self.cbo_order)

        # NUEVO: selector de tamaño de página
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

        # 6 columnas (quitamos la última vacía)
        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels([
            "Cliente", "Contacto", "Artista", "Próxima cita", "Etiquetas", "Estado"
        ])

        # Anchos: Cliente y Contacto en stretch; el resto a contenido
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)           # Cliente
        header.setSectionResizeMode(1, QHeaderView.Stretch)           # Contacto
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

        # Datos demo y primer render
        self._seed_mock()
        self._refresh()

    # ---------- Datos mock + filtrado ----------
    def _seed_mock(self):
        # Algunos con Instagram, otros sin; el contacto se arma dinámicamente
        self._all = [
  {"id": 1,  "nombre": "Galileo Galilei",         "tel": "662-315-7842", "email": "galileo.galilei@gmail.com",         "ig": "galileo.galilei",        "artista": "Dylan", "proxima": "12 Sep 12:00", "etiquetas": "fineline, geometría",      "estado": "Activo"},
  {"id": 2,  "nombre": "Jenni Rivera",            "tel": "55-4312-9087", "email": "jenni.rivera@gmail.com",            "ig": "jennirivera.oficial",    "artista": "Pablo",       "proxima": "—",            "etiquetas": "VIP",                      "estado": "Activo"},
  {"id": 3,  "nombre": "José José",               "tel": "81-2745-6632", "email": "jose.jose@gmail.com",               "ig": "principe.de.la.cancion", "artista": "Alex",        "proxima": "11 Sep 17:30", "etiquetas": "referido",                 "estado": "Activo"},
  {"id": 4,  "nombre": "Lolita Ayala",            "tel": "55-7731-2209", "email": "lolita.ayala@outlook.com",          "ig": "lolitaayala.oficial",    "artista": "Dylan", "proxima": "—",            "etiquetas": "nuevo",                    "estado": "Seguimiento"},
  {"id": 5,  "nombre": "Juan Gabriel",            "tel": "662-482-9031", "email": "juan.gabriel@gmail.com",            "ig": "juangabriel.oficial",    "artista": "Pablo",       "proxima": "14 Sep 11:00", "etiquetas": "cover-up",                 "estado": "Activo"},
  {"id": 6,  "nombre": "Frida Kahlo",             "tel": "55-9182-4470", "email": "frida.kahlo@gmail.com",             "ig": "fridakahlo.art",         "artista": "Alex",        "proxima": "—",            "etiquetas": "blackwork, floral",       "estado": "Archivado"},
  {"id": 7,  "nombre": "Diego Rivera",            "tel": "33-6421-5083", "email": "diego.rivera@gmail.com",            "ig": "diegorivera.mx",         "artista": "Dylan", "proxima": "18 Sep 16:00", "etiquetas": "realismo",                 "estado": "Activo"},
  {"id": 8,  "nombre": "María Félix",             "tel": "55-2208-9713", "email": "maria.felix@gmail.com",             "ig": "lamariafelix",           "artista": "Pablo",       "proxima": "—",            "etiquetas": "VIP, retrato",            "estado": "Activo"},
  {"id": 9,  "nombre": "Pedro Infante",           "tel": "81-9301-7446", "email": "pedro.infante@gmail.com",           "ig": "pedroinfante.mx",        "artista": "Alex",        "proxima": "22 Sep 13:30", "etiquetas": "old school",               "estado": "Activo"},
  {"id": 10, "nombre": "Roberto Gómez Bolaños",   "tel": "33-5190-2841", "email": "roberto.gomez.bolanos@gmail.com",   "ig": "chespirito.oficial",     "artista": "Jesus", "proxima": "—",            "etiquetas": "humor, lettering",        "estado": "Reprogramado"},
  {"id": 11, "nombre": "Cantinflas",              "tel": "55-6402-7139", "email": "mario.moreno@gmail.com",            "ig": "cantinflas.mx",          "artista": "Pablo",       "proxima": "19 Sep 19:00", "etiquetas": "fineline",                 "estado": "Activo"},
  {"id": 12, "nombre": "Luis Miguel",             "tel": "55-2840-6675", "email": "luis.miguel@gmail.com",             "ig": "lmxlm",                  "artista": "Alex",        "proxima": "—",            "etiquetas": "VIP, dorado",             "estado": "Activo"},
  {"id": 13, "nombre": "Thalía",                  "tel": "55-7021-9934", "email": "thalia@gmail.com",                  "ig": "thalia",                 "artista": "Jesus", "proxima": "24 Sep 10:45", "etiquetas": "floral",                   "estado": "Activo"},
  {"id": 14, "nombre": "Paquita la del Barrio",   "tel": "229-341-2256", "email": "paquita.barrio@gmail.com",          "ig": "paquitaoficial",         "artista": "Pablo",       "proxima": "—",            "etiquetas": "lettering",               "estado": "Activo"},
  {"id": 15, "nombre": "Gloria Trevi",            "tel": "81-6102-9035", "email": "gloria.trevi@gmail.com",            "ig": "gloriatrevi",            "artista": "Alex",        "proxima": "26 Sep 17:00", "etiquetas": "color",                    "estado": "Activo"},
  {"id": 16, "nombre": "Belinda",                 "tel": "55-8302-1147", "email": "belinda@gmail.com",                 "ig": "belindapop",             "artista": "Jesus", "proxima": "—",            "etiquetas": "fineline, estrella",      "estado": "Seguimiento"},
  {"id": 17, "nombre": "Danna Paola",             "tel": "55-9120-4481", "email": "danna.paola@gmail.com",             "ig": "dannapaola",             "artista": "Pablo",       "proxima": "30 Sep 12:15", "etiquetas": "fineline",                 "estado": "Activo"},
  {"id": 18, "nombre": "Eugenio Derbez",          "tel": "55-3142-7605", "email": "eugenio.derbez@gmail.com",          "ig": "ederbez",                "artista": "Alex",        "proxima": "—",            "etiquetas": "walk-in",                 "estado": "No-show"},
  {"id": 19, "nombre": "Gael García Bernal",      "tel": "55-9910-5308", "email": "gael.garcia.bernal@gmail.com",      "ig": "gaelgarciab",            "artista": "Dylan", "proxima": "01 Oct 16:40", "etiquetas": "cine",                     "estado": "Activo"},
  {"id": 20, "nombre": "Guillermo del Toro",      "tel": "33-7210-8894", "email": "guillermo.del.toro@gmail.com",      "ig": "gdltoro",                "artista": "Pablo",       "proxima": "—",            "etiquetas": "fantasía, blackwork",     "estado": "Activo"},
  {"id": 21, "nombre": "Alfonso Cuarón",          "tel": "55-6741-2201", "email": "alfonso.cuaron@gmail.com",          "ig": "alfonsocuaron",          "artista": "Alex",        "proxima": "03 Oct 11:20", "etiquetas": "cine, minimal",           "estado": "Activo"},
  {"id": 22, "nombre": "Alejandro G. Iñárritu",   "tel": "55-9041-6678", "email": "alejandro.inarritu@gmail.com",      "ig": "aginarritu",             "artista": "Jesus", "proxima": "—",            "etiquetas": "realismo",                 "estado": "Archivado"},
  {"id": 23, "nombre": "Salma Hayek",             "tel": "229-802-5576", "email": "salma.hayek@gmail.com",             "ig": "salmahayek",             "artista": "Pablo",       "proxima": "05 Oct 15:30", "etiquetas": "floral, fine",            "estado": "Activo"},
  {"id": 24, "nombre": "Yalitza Aparicio",        "tel": "951-402-7714", "email": "yalitza.aparicio@gmail.com",        "ig": "yalitzaapariciomtz",     "artista": "Alex",        "proxima": "—",            "etiquetas": "botanical",               "estado": "Activo"},
  {"id": 25, "nombre": "Bad Bunny",               "tel": "55-3321-9086", "email": "bad.bunny@gmail.com",               "ig": "badbunnypr",             "artista": "Dylan", "proxima": "07 Oct 20:00", "etiquetas": "lettering, trap",         "estado": "Activo"},
  {"id": 26, "nombre": "Shakira",                 "tel": "55-2140-6619", "email": "shakira@gmail.com",                 "ig": "shakira",                "artista": "Pablo",       "proxima": "—",            "etiquetas": "geométrico",              "estado": "Reprogramado"},
  {"id": 27, "nombre": "Karol G",                 "tel": "81-5102-7440", "email": "karol.g@gmail.com",                 "ig": "karolg",                 "artista": "Alex",        "proxima": "09 Oct 14:00", "etiquetas": "color",                    "estado": "Activo"},
  {"id": 28, "nombre": "J Balvin",                "tel": "55-9918-2405", "email": "j.balvin@gmail.com",                "ig": "jbalvin",                "artista": "Jesus", "proxima": "—",            "etiquetas": "color, pop",              "estado": "Activo"},
  {"id": 29, "nombre": "Maluma",                  "tel": "33-8901-3344", "email": "maluma@gmail.com",                  "ig": "maluma",                 "artista": "Pablo",       "proxima": "11 Oct 19:45", "etiquetas": "fineline",                 "estado": "Activo"},
  {"id": 30, "nombre": "Rosalía",                 "tel": "55-6604-9012", "email": "rosalia@gmail.com",                 "ig": "rosalia.vt",             "artista": "Alex",        "proxima": "—",            "etiquetas": "experimental",            "estado": "Seguimiento"},
  {"id": 31, "nombre": "Taylor Swift",            "tel": "55-7722-1140", "email": "taylor.swift@gmail.com",            "ig": "taylorswift",            "artista": "Jesus", "proxima": "13 Oct 10:00", "etiquetas": "linework",                 "estado": "Activo"},
  {"id": 32, "nombre": "Billie Eilish",           "tel": "55-4412-9980", "email": "billie.eilish@gmail.com",           "ig": "billieeilish",           "artista": "Pablo",       "proxima": "—",            "etiquetas": "blackwork",               "estado": "Activo"},
  {"id": 33, "nombre": "Ariana Grande",           "tel": "55-6130-2295", "email": "ariana.grande@gmail.com",           "ig": "arianagrande",           "artista": "Alex",        "proxima": "16 Oct 12:30", "etiquetas": "floral",                   "estado": "Activo"},
  {"id": 34, "nombre": "Lionel Messi",            "tel": "81-2207-9041", "email": "lionel.messi@gmail.com",            "ig": "leomessi",               "artista": "Dylan", "proxima": "—",            "etiquetas": "deporte",                 "estado": "Activo"},
  {"id": 35, "nombre": "Cristiano Ronaldo",       "tel": "33-7711-2086", "email": "cristiano.ronaldo@gmail.com",       "ig": "cristiano",              "artista": "Pablo",       "proxima": "18 Oct 18:15", "etiquetas": "realismo",                 "estado": "Activo"},
  {"id": 36, "nombre": "Neymar Jr",               "tel": "55-9055-7731", "email": "neymar.jr@gmail.com",               "ig": "neymarjr",               "artista": "Alex",        "proxima": "—",            "etiquetas": "black&grey",              "estado": "Cancelado"},
  {"id": 37, "nombre": "Checo Pérez",             "tel": "33-4201-6684", "email": "sergio.perez@gmail.com",            "ig": "schecoperez",            "artista": "Jesus", "proxima": "20 Oct 09:30", "etiquetas": "motor, minimal",          "estado": "Activo"},
  {"id": 38, "nombre": "Hugo Sánchez",            "tel": "55-3102-7749", "email": "hugo.sanchez@gmail.com",            "ig": "hugosanchez.mx",         "artista": "Pablo",       "proxima": "—",            "etiquetas": "retro",                   "estado": "Archivado"},
  {"id": 39, "nombre": "Rafael Márquez",          "tel": "33-8811-4205", "email": "rafael.marquez@gmail.com",          "ig": "rafamarquez.a",          "artista": "Alex",        "proxima": "22 Oct 16:20", "etiquetas": "escudo, linework",        "estado": "Activo"},
  {"id": 40, "nombre": "El Babo",                 "tel": "81-5502-3310", "email": "el.babo@gmail.com",                 "ig": "babocartel",             "artista": "Dylan", "proxima": "—",            "etiquetas": "blackwork, letras",       "estado": "Activo"},
  {"id": 41, "nombre": "Santa Fe Klan",           "tel": "477-204-5590", "email": "santafeklan@gmail.com",             "ig": "santafeklan",            "artista": "Pablo",       "proxima": "23 Oct 20:30", "etiquetas": "letras, chicano",         "estado": "Activo"},
  {"id": 42, "nombre": "Julieta Venegas",         "tel": "664-780-1142", "email": "julieta.venegas@gmail.com",         "ig": "julietavenegasp",        "artista": "Alex",        "proxima": "—",            "etiquetas": "botanical",               "estado": "Seguimiento"},
  {"id": 43, "nombre": "Rubén Albarrán",          "tel": "55-7712-6638", "email": "ruben.albarran@gmail.com",          "ig": "rubenalbarran",          "artista": "Jesus", "proxima": "25 Oct 12:10", "etiquetas": "experimental",            "estado": "Activo"},
  {"id": 44, "nombre": "Alex Lora",               "tel": "55-2210-9940", "email": "alex.lora@gmail.com",               "ig": "alexloraoficial",        "artista": "Pablo",       "proxima": "—",            "etiquetas": "rock, old school",        "estado": "Activo"},
  {"id": 45, "nombre": "Fher Olvera",             "tel": "33-6104-7723", "email": "fher.olvera@gmail.com",             "ig": "fherolvera",             "artista": "Alex",        "proxima": "27 Oct 17:50", "etiquetas": "linework",                 "estado": "Activo"},
  {"id": 46, "nombre": "Natalia Lafourcade",      "tel": "229-415-7729", "email": "natalia.lafourcade@gmail.com",      "ig": "natalialafourcade",      "artista": "Dylan", "proxima": "—",            "etiquetas": "floral, fineline",        "estado": "Activo"},
  {"id": 47, "nombre": "Christian Nodal",         "tel": "644-202-8840", "email": "christian.nodal@gmail.com",         "ig": "nodal",                   "artista": "Pablo",       "proxima": "29 Oct 13:15", "etiquetas": "lettering",               "estado": "Activo"},
  {"id": 48, "nombre": "Peso Pluma",              "tel": "33-9901-6627", "email": "peso.pluma@gmail.com",              "ig": "pesopluma",              "artista": "Alex",        "proxima": "—",            "etiquetas": "black&grey",              "estado": "No-show"},
  {"id": 49, "nombre": "Kenia OS",                "tel": "33-2201-7743", "email": "kenia.os@gmail.com",                "ig": "keniaos",                "artista": "Jesus", "proxima": "31 Oct 11:40", "etiquetas": "fineline, pop",           "estado": "Activo"},
  {"id": 50, "nombre": "Ibai Llanos",             "tel": "55-4401-3380", "email": "ibai.llanos@gmail.com",             "ig": "ibaillanos",             "artista": "Pablo",       "proxima": "—",            "etiquetas": "gaming",                   "estado": "Activo"},
  {"id": 51, "nombre": "AuronPlay",               "tel": "55-6601-7228", "email": "auron.play@gmail.com",              "ig": "auronplay",              "artista": "Alex",        "proxima": "02 Nov 12:00", "etiquetas": "gaming, minimal",         "estado": "Activo"},
  {"id": 52, "nombre": "Juanpa Zurita",           "tel": "55-7002-8846", "email": "juanpa.zurita@gmail.com",           "ig": "juanpazurita",           "artista": "Dylan", "proxima": "—",            "etiquetas": "fineline",                 "estado": "Seguimiento"},
  {"id": 53, "nombre": "Germán Garmendia",        "tel": "55-9042-1183", "email": "german.garmendia@gmail.com",        "ig": "hola_soy_german",        "artista": "Pablo",       "proxima": "04 Nov 18:20", "etiquetas": "humor",                    "estado": "Activo"},
  {"id": 54, "nombre": "MrBeast",                 "tel": "55-8801-4466", "email": "mrbeast@gmail.com",                 "ig": "mrbeast",                "artista": "Alex",        "proxima": "—",            "etiquetas": "retoque, grande",         "estado": "Archivado"},
  {"id": 55, "nombre": "Elon Musk",               "tel": "55-3301-2217", "email": "elon.musk@gmail.com",               "ig": "elonmusk",               "artista": "Jesus", "proxima": "06 Nov 09:00", "etiquetas": "geometría, minimal",      "estado": "Activo"},
  {"id": 56, "nombre": "Steve Jobs",              "tel": "55-7713-9042", "email": "steve.jobs@gmail.com",              "ig": "stevejobs",              "artista": "Pablo",       "proxima": "—",            "etiquetas": "linework, tributo",       "estado": "Activo"},
  {"id": 57, "nombre": "Albert Einstein",         "tel": "55-6610-5529", "email": "albert.einstein@gmail.com",         "ig": "albert.einstein",        "artista": "Alex",        "proxima": "08 Nov 15:10", "etiquetas": "geometría, fórmula",      "estado": "Activo"},
  {"id": 58, "nombre": "Isaac Newton",            "tel": "55-9021-7730", "email": "isaac.newton@gmail.com",            "ig": "isaac.newton",           "artista": "Dylan", "proxima": "—",            "etiquetas": "blackwork, manzana",      "estado": "Activo"},
  {"id": 59, "nombre": "Marie Curie",             "tel": "55-4410-8821", "email": "marie.curie@gmail.com",             "ig": "marie.curie",            "artista": "Pablo",       "proxima": "10 Nov 13:25", "etiquetas": "ciencia, fineline",       "estado": "Activo"},
  {"id": 60, "nombre": "Nikola Tesla",            "tel": "55-5512-9040", "email": "nikola.tesla@gmail.com",            "ig": "nikola.tesla",           "artista": "Alex",        "proxima": "—",            "etiquetas": "eléctrico, black&grey",   "estado": "Activo"}
]


    def _apply_filters(self):
        txt = self.search_text.lower().strip()
        if txt:
            rows = [
                c for c in self._all
                if (txt in c["nombre"].lower()
                    or (c.get("tel") and txt in c["tel"].lower())
                    or (c.get("email") and txt in c["email"].lower())
                    or (c.get("ig") and txt in c["ig"].lower()))
            ]
        else:
            rows = list(self._all)

        if self.order_by == "A–Z":
            rows.sort(key=lambda c: c["nombre"].lower())
        # (Placeholders) Otros órdenes se implementarán con datos reales.

        return rows

    def _refresh(self):
        rows = self._apply_filters()

        # Calcular páginas según page_size actual
        total_pages = max(1, (len(rows) + self.page_size - 1) // self.page_size)
        self.current_page = min(self.current_page, total_pages)

        start = (self.current_page - 1) * self.page_size
        page_rows = rows[start:start + self.page_size]

        self.table.setRowCount(len(page_rows))
        for r, c in enumerate(page_rows):
            # Cliente
            self.table.setItem(r, 0, QTableWidgetItem(c["nombre"]))
            self.table.item(r, 0).setData(Qt.UserRole, c["id"])  # para doble clic

            # Contacto dinámico: Tel / @ig / Email (uno o dos)
            parts = []
            if c.get("tel"):
                parts.append(c["tel"])
            if c.get("ig"):
                parts.append("@" + c["ig"])
            if c.get("email"):
                parts.append(c["email"])
            # Si hay más de dos, priorizamos Tel e IG; deja email cuando solo haya uno de los otros
            if len(parts) > 2:
                # Heurística simple: intenta mantener Tel + Email; sino, Tel + IG
                tel = c.get("tel"); ig = ("@" + c["ig"]) if c.get("ig") else None; em = c.get("email")
                cand = [p for p in [tel, em] if p] or [p for p in [tel, ig] if p] or parts[:2]
                parts = cand[:2]
            self.table.setItem(r, 1, QTableWidgetItem("  ·  ".join(parts)))

            # Resto de columnas
            self.table.setItem(r, 2, QTableWidgetItem(c["artista"]))
            self.table.setItem(r, 3, QTableWidgetItem(c["proxima"]))
            self.table.setItem(r, 4, QTableWidgetItem(c["etiquetas"]))
            self.table.setItem(r, 5, QTableWidgetItem(c["estado"]))

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
        for c in self._all:
            if c["id"] == cid:
                self.abrir_cliente.emit(c)
                break
