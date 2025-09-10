# ui/pages/staff.py
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QScrollArea, QFrame, QGridLayout, QSizePolicy, QSpacerItem
)

class StaffPage(QWidget):
    """
    Cascarón 'Staff':
      - Toolbar con 'Agregar staff'
      - Buscar + filtros + ordenar
      - Grid de cards con acciones rápidas
      - Paginación
    Señales:
      agregar_staff()
      abrir_staff(staff: dict)
      abrir_portafolio(staff: dict)
    """
    agregar_staff = pyqtSignal()
    abrir_staff = pyqtSignal(dict)
    abrir_portafolio = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        # ---- estado UI ----
        self.page_size = 8
        self.current_page = 1
        self.search_text = ""
        self.filter_role = "Todos"
        self.filter_state = "Todos"
        self.order_by = "A–Z"

        # ---- layout raíz ----
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # Título
        title = QLabel("Staff")
        title.setObjectName("H1")
        root.addWidget(title)

        # ---- Toolbar ----
        toolbar = QHBoxLayout(); toolbar.setSpacing(8)

        self.btn_new = QPushButton("Agregar staff")
        self.btn_new.setObjectName("CTA")
        self.btn_new.setMinimumHeight(34)
        self.btn_new.clicked.connect(self.agregar_staff.emit)
        toolbar.addWidget(self.btn_new)

        toolbar.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # (futuro) importar/exportar
        self.btn_import = QPushButton("Importar CSV"); self.btn_import.setEnabled(False)
        self.btn_export = QPushButton("Exportar CSV"); self.btn_export.setEnabled(False)
        toolbar.addWidget(self.btn_import); toolbar.addWidget(self.btn_export)

        root.addLayout(toolbar)

        # ---- Buscar + Filtros + Orden ----
        filters = QHBoxLayout(); filters.setSpacing(8)

        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar por nombre, rol o especialidad…")
        self.search.textChanged.connect(self._on_search)
        filters.addWidget(self.search, stretch=1)

        self.cbo_role = QComboBox(); self.cbo_role.addItems(["Todos", "Tatuador", "Asistente", "Manager"])
        self.cbo_role.currentTextChanged.connect(self._on_filter_change)
        filters.addWidget(QLabel("Rol:")); filters.addWidget(self.cbo_role)

        self.cbo_state = QComboBox(); self.cbo_state.addItems(["Todos", "Activo", "Vacaciones", "Archivado"])
        self.cbo_state.currentTextChanged.connect(self._on_filter_change)
        filters.addWidget(QLabel("Estado:")); filters.addWidget(self.cbo_state)

        self.cbo_order = QComboBox(); self.cbo_order.addItems(["A–Z", "Rol"])
        self.cbo_order.currentTextChanged.connect(self._on_order_change)
        filters.addWidget(QLabel("Ordenar por:")); filters.addWidget(self.cbo_order)

        root.addLayout(filters)

        # ---- Scroll + grid de cards ----
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self._grid_host = QWidget()
        self.grid = QGridLayout(self._grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(16)

        self.scroll.setWidget(self._grid_host)
        root.addWidget(self.scroll, stretch=1)

        # ---- Paginación ----
        pager = QHBoxLayout(); pager.setSpacing(8)
        self.btn_prev = QPushButton("⟵"); self.btn_next = QPushButton("⟶")
        self.lbl_page = QLabel("Página 1/1")
        self.btn_prev.clicked.connect(self._prev_page); self.btn_next.clicked.connect(self._next_page)
        pager.addWidget(self.btn_prev); pager.addWidget(self.btn_next); pager.addWidget(self.lbl_page)
        pager.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        root.addLayout(pager)

        # ---- datos de ejemplo ----
        self._seed_mock()
        self._refresh()

    # ==================== datos mock ====================
    def _seed_mock(self):
        self._all = [
            {"id": 1, "nombre": "Dylan Bourjac", "rol": "Manager",  "especialidades": ["Blackwork", "Linework"],
             "estado": "Activo", "disp": "L–S 11:00–19:00", "bio": "Fundador y tatuador senior."},
            {"id": 2, "nombre": "Karla Medina",   "rol": "Tatuador", "especialidades": ["Realismo", "Sombras"],
             "estado": "Activo", "disp": "M–S 12:00–20:00", "bio": "Realismo en negro y gris."},
            {"id": 3, "nombre": "Luis Rangel",    "rol": "Tatuador", "especialidades": ["Tradicional", "Color"],
             "estado": "Vacaciones", "disp": "L–S 10:00–18:00", "bio": "Old school y color vibrante."},
            {"id": 4, "nombre": "Sofía Reyes",    "rol": "Asistente","especialidades": ["Recepción", "Inventario"],
             "estado": "Activo", "disp": "M–D 11:00–19:00", "bio": "Front desk y proveedores."},
            {"id": 5, "nombre": "Alex Torres",    "rol": "Tatuador", "especialidades": ["Anime", "Neo-trad"],
             "estado": "Activo", "disp": "J–D 12:00–20:00", "bio": "Anime y neotrad en color."},
            {"id": 6, "nombre": "Mara Juárez",    "rol": "Tatuador", "especialidades": ["Fine line", "Minimalista"],
             "estado": "Archivado", "disp": "—", "bio": "Temporalmente fuera del estudio."},
            {"id": 7, "nombre": "Hiro Tanaka",    "rol": "Tatuador", "especialidades": ["Irezumi", "Dotwork"],
             "estado": "Activo", "disp": "L–V 13:00–21:00", "bio": "Inspiración japonesa."},
            {"id": 8, "nombre": "Nora Vega",      "rol": "Asistente","especialidades": ["Agendas", "Pagos"],
             "estado": "Activo", "disp": "L–S 11:00–19:00", "bio": "Atención a clientes y caja."},
            {"id": 9, "nombre": "Bruno Díaz",     "rol": "Tatuador", "especialidades": ["Geométrico"],
             "estado": "Activo", "disp": "M–S 12:00–20:00", "bio": "Patrones y simetría."},
        ]

    # ==================== filtrado/orden/paginación ====================
    def _apply_filters(self):
        txt = self.search_text.lower().strip()

        def match(s):
            if txt:
                if not (
                    txt in s["nombre"].lower()
                    or txt in s["rol"].lower()
                    or any(txt in e.lower() for e in s["especialidades"])
                ):
                    return False
            if self.filter_role != "Todos" and s["rol"] != self.filter_role:
                return False
            if self.filter_state != "Todos" and s["estado"] != self.filter_state:
                return False
            return True

        rows = [s for s in self._all if match(s)]

        if self.order_by == "A–Z":
            rows.sort(key=lambda s: s["nombre"].lower())
        elif self.order_by == "Rol":
            rows.sort(key=lambda s: (s["rol"], s["nombre"].lower()))

        return rows

    def _refresh(self):
        # destruir cards actuales
        for i in reversed(range(self.grid.count())):
            item = self.grid.itemAt(i)
            w = item.widget()
            if w:
                w.deleteLater()
            self.grid.removeItem(item)

        rows = self._apply_filters()
        total_pages = max(1, (len(rows) + self.page_size - 1) // self.page_size)
        self.current_page = min(self.current_page, total_pages)

        start = (self.current_page - 1) * self.page_size
        page_rows = rows[start:start + self.page_size]

        # crear cards en un grid 2xN o 3xN (ajustable)
        cols = 3
        r, c = 0, 0
        for s in page_rows:
            card = self._make_card(s)
            self.grid.addWidget(card, r, c)
            c += 1
            if c >= cols:
                c = 0; r += 1

        # actualizar paginación
        self.lbl_page.setText(f"Página {self.current_page}/{total_pages}")
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < total_pages)

        # fuerza relayout
        self._grid_host.adjustSize()

    # ==================== construcción de cards ====================
    def _make_card(self, s: dict) -> QFrame:
        card = QFrame(); card.setObjectName("Card")
        lay = QHBoxLayout(card); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(12)

        # Foto placeholder (círculo con iniciales)
        avatar = QLabel(); avatar.setFixedSize(64, 64)
        avatar.setPixmap(self._make_avatar_pixmap(64, s["nombre"]))
        lay.addWidget(avatar, alignment=Qt.AlignTop)

        # Columna central
        col = QVBoxLayout(); col.setSpacing(4)

        name = QLabel(s["nombre"]); name.setStyleSheet("font-weight:700;")
        col.addWidget(name)

        # Badges de rol y estado
        badges = QHBoxLayout(); badges.setSpacing(6)
        role = QLabel(f' {s["rol"]} '); role.setObjectName("BadgeRole")
        state = QLabel(f' {s["estado"]} '); state.setObjectName("BadgeState")
        badges.addWidget(role); badges.addWidget(state); badges.addStretch(1)
        col.addLayout(badges)

        # Especialidades
        esp = QLabel(" · ".join(s["especialidades"])) if s["especialidades"] else QLabel("—")
        esp.setStyleSheet("color: #666;")
        col.addWidget(esp)

        # Disponibilidad
        disp = QLabel(s["disp"]); disp.setStyleSheet("color: #666;")
        col.addWidget(disp)

        lay.addLayout(col, stretch=1)

        # Columna de acciones
        actions = QVBoxLayout(); actions.setSpacing(6)
        btn_profile = QPushButton("Ver perfil"); btn_profile.clicked.connect(lambda: self.abrir_staff.emit(s))
        btn_port = QPushButton("Portafolio"); btn_port.clicked.connect(lambda: self.abrir_portafolio.emit(s))
        for b in (btn_profile, btn_port):
            b.setMinimumHeight(28)
            actions.addWidget(b)
        actions.addStretch(1)
        lay.addLayout(actions)

        return card

    def _make_avatar_pixmap(self, size: int, nombre: str) -> QPixmap:
        """Dibuja un avatar circular con iniciales (placeholder)."""
        initials = "".join([p[0].upper() for p in nombre.split()[:2]])
        pm = QPixmap(size, size); pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#d1d5db"))  # gris claro
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, size, size)
        p.setPen(QColor("#111"))
        p.drawText(pm.rect(), Qt.AlignCenter, initials)
        p.end()
        return pm

    # ==================== eventos ====================
    def _on_search(self, t: str):
        self.search_text = t
        self.current_page = 1
        self._refresh()

    def _on_filter_change(self, _):
        self.filter_role = self.cbo_role.currentText()
        self.filter_state = self.cbo_state.currentText()
        self.current_page = 1
        self._refresh()

    def _on_order_change(self, _):
        self.order_by = self.cbo_order.currentText()
        self.current_page = 1
        self._refresh()

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._refresh()

    def _next_page(self):
        self.current_page += 1
        self._refresh()
