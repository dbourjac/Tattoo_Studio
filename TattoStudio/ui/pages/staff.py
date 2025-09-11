# ui/pages/staff.py
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRect, QPoint
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QScrollArea, QFrame, QSizePolicy, QSpacerItem, QLayout, QStyle
)

# ---------------------------
# FlowLayout (wrap auto)
# Basado en el patrón clásico de Qt: distribuye widgets en filas y hace wrap
# según ancho disponible. Esto evita huecos feos del grid fijo.
# ---------------------------
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, hspacing=12, vspacing=12):
        super().__init__(parent)
        self._items = []
        self._hspace = hspacing
        self._vspace = vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    def _smart_spacing(self, pm):
        if self.parent():
            return self.parent().style().pixelMetric(pm, None, self.parent())
        return -1

    def horizontalSpacing(self):
        if self._hspace >= 0:
            return self._hspace
        return self._smart_spacing(QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self):
        if self._vspace >= 0:
            return self._vspace
        return self._smart_spacing(QStyle.PM_LayoutVerticalSpacing)

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(+left, +top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        hspace = self.horizontalSpacing()
        vspace = self.verticalSpacing()

        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            if w <= 0:
                continue

            nextX = x + w + hspace
            if nextX - hspace > effective_rect.right() and line_height > 0:
                # nueva línea
                x = effective_rect.x()
                y = y + line_height + vspace
                nextX = x + w + hspace
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = nextX
            line_height = max(line_height, h)

        total_height = (y + line_height - rect.y()) + bottom
        return total_height


class StaffPage(QWidget):
    """
    Staff:
      - Toolbar 1: Agregar staff | Importar CSV | Exportar CSV
      - Toolbar 2: Buscar + filtros (Rol/Estado/Orden)
      - Cards en FlowLayout (wrap) — sin paginación
      - 5 dummies para demo
    """
    agregar_staff = pyqtSignal()
    abrir_staff = pyqtSignal(dict)
    abrir_portafolio = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        # ---- estado UI ----
        self.search_text = ""
        self.filter_role = "Todos"
        self.filter_state = "Todos"
        self.order_by = "A–Z"

        # ---- layout raíz ----
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # ========================= Toolbar superior =========================
        bar_top = QFrame()
        bar_top.setObjectName("Toolbar")
        bar_top_l = QHBoxLayout(bar_top)
        bar_top_l.setContentsMargins(12, 8, 12, 8)
        bar_top_l.setSpacing(8)

        self.btn_new = QPushButton("Agregar staff")
        self.btn_new.setObjectName("CTA")
        self.btn_new.setMinimumHeight(34)
        self.btn_new.clicked.connect(self.agregar_staff.emit)
        bar_top_l.addWidget(self.btn_new)

        bar_top_l.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.btn_import = QPushButton("Importar CSV")
        self.btn_import.setObjectName("GhostSmall")
        self.btn_import.setEnabled(False)
        self.btn_export = QPushButton("Exportar CSV")
        self.btn_export.setObjectName("GhostSmall")
        self.btn_export.setEnabled(False)
        bar_top_l.addWidget(self.btn_import)
        bar_top_l.addWidget(self.btn_export)

        root.addWidget(bar_top)

        # ========================= Toolbar filtros =========================
        bar_filters = QFrame()
        bar_filters.setObjectName("Toolbar")
        f = QHBoxLayout(bar_filters)
        f.setContentsMargins(12, 8, 12, 8)
        f.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre, rol o especialidad…")
        self.search.textChanged.connect(self._on_search)
        f.addWidget(self.search, stretch=1)

        lbl_rol = QLabel("Rol:"); lbl_rol.setStyleSheet("background: transparent;")
        lbl_est = QLabel("Estado:"); lbl_est.setStyleSheet("background: transparent;")
        lbl_ord = QLabel("Ordenar por:"); lbl_ord.setStyleSheet("background: transparent;")

        self.cbo_role = QComboBox(); self.cbo_role.addItems(["Todos", "Tatuador", "Asistente", "Manager"])
        self.cbo_role.currentTextChanged.connect(self._on_filter_change)
        self.cbo_state = QComboBox(); self.cbo_state.addItems(["Todos", "Activo", "Vacaciones", "Archivado"])
        self.cbo_state.currentTextChanged.connect(self._on_filter_change)
        self.cbo_order = QComboBox(); self.cbo_order.addItems(["A–Z", "Rol"])
        self.cbo_order.currentTextChanged.connect(self._on_order_change)

        f.addWidget(lbl_rol); f.addWidget(self.cbo_role)
        f.addWidget(lbl_est); f.addWidget(self.cbo_state)
        f.addWidget(lbl_ord); f.addWidget(self.cbo_order)
        root.addWidget(bar_filters)

        # ========================= Zona de cards (Flow) ====================
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        host = QWidget()
        # FlowLayout compactito (menos huecos y tarjetas más grandes)
        self.flow = FlowLayout(host, margin=0, hspacing=16, vspacing=16)
        host.setLayout(self.flow)
        self.scroll.setWidget(host)
        root.addWidget(self.scroll, stretch=1)

        # ---- data demo (5 dummies) ----
        self._seed_mock()
        self._refresh()

    # ----------------------- datos mock -----------------------
    def _seed_mock(self):
        # Solo 5 dummies
        self._all = [
            {"id": 1, "nombre": "Dylan Bourjac", "rol": "Manager",  "especialidades": ["Blackwork", "Linework"],
             "estado": "Activo", "disp": "L–S 11:00–19:00", "bio": "Fundador y tatuador senior."},
            {"id": 2, "nombre": "Jesus Esquer",   "rol": "Tatuador", "especialidades": ["Realismo", "Sombras"],
             "estado": "Activo", "disp": "M–S 12:00–20:00", "bio": "Realismo en negro y gris."},
            {"id": 3, "nombre": "Pablo Velasquez",    "rol": "Tatuador", "especialidades": ["Tradicional", "Color"],
             "estado": "Vacaciones", "disp": "L–S 10:00–18:00", "bio": "Old school y color vibrante."},
            {"id": 4, "nombre": "Alex Chavez",    "rol": "Tatuador", "especialidades": ["Anime", "Neo-trad"],
             "estado": "Activo", "disp": "J–D 12:00–20:00", "bio": "Anime y neotrad en color."},
            {"id": 5, "nombre": "Jenni Rivera",    "rol": "Asistente","especialidades": ["Recepción", "Inventario"],
             "estado": "Activo", "disp": "M–D 11:00–19:00", "bio": "Front desk y proveedores."},
        ]

    # ----------------------- filtrado/orden -----------------------
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
        # limpiar flow actual
        while self.flow.count():
            it = self.flow.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        # crear cards y añadir al flow
        for s in self._apply_filters():
            card = self._make_card(s)
            self.flow.addWidget(card)

    # ----------------------- card -----------------------
    def _make_card(self, s: dict) -> QFrame:
        # Card más grande: se ve “pro”
        CARD_W = 520

        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumWidth(CARD_W)
        card.setMaximumWidth(CARD_W)
        card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)

        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(14)

        # Avatar circular
        avatar = QLabel()
        avatar.setFixedSize(64, 64)
        avatar.setStyleSheet("background: transparent;")
        avatar.setPixmap(self._make_avatar_pixmap(64, s["nombre"]))
        lay.addWidget(avatar, alignment=Qt.AlignTop)

        # Columna central
        col = QVBoxLayout(); col.setSpacing(6)

        name = QLabel(s["nombre"])
        name.setStyleSheet("font-weight:700; background: transparent;")
        col.addWidget(name)

        row_meta = QHBoxLayout(); row_meta.setSpacing(10)
        role = QLabel(s["rol"]);     role.setStyleSheet("background: transparent; color:#6C757D;")
        state = QLabel(s["estado"]); state.setStyleSheet("background: transparent; color:#6C757D;")
        row_meta.addWidget(role); row_meta.addWidget(state); row_meta.addStretch(1)
        col.addLayout(row_meta)

        esp = QLabel(" · ".join(s["especialidades"]) if s["especialidades"] else "—")
        esp.setStyleSheet("background: transparent; color:#6C757D;")
        col.addWidget(esp)

        disp = QLabel(s["disp"])
        disp.setStyleSheet("background: transparent; color:#6C757D;")
        col.addWidget(disp)

        lay.addLayout(col, stretch=1)

        # Acciones (estilo GhostSmall para consistencia)
        actions = QVBoxLayout(); actions.setSpacing(8)
        btn_profile = QPushButton("Ver perfil"); btn_profile.setObjectName("GhostSmall")
        btn_profile.clicked.connect(lambda: self.abrir_staff.emit(s))
        btn_port = QPushButton("Portafolio"); btn_port.setObjectName("GhostSmall")
        btn_port.clicked.connect(lambda: self.abrir_portafolio.emit(s))
        actions.addWidget(btn_profile); actions.addWidget(btn_port); actions.addStretch(1)
        lay.addLayout(actions)

        return card

    def _make_avatar_pixmap(self, size: int, nombre: str) -> QPixmap:
        initials = "".join([p[0].upper() for p in nombre.split()[:2]])
        pm = QPixmap(size, size); pm.fill(Qt.transparent)
        p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#d1d5db"))  # círculo claro (se ve bien en ambos temas)
        p.setPen(Qt.NoPen); p.drawEllipse(0, 0, size, size)
        p.setPen(QColor("#111")); p.drawText(pm.rect(), Qt.AlignCenter, initials)
        p.end()
        return pm

    # ----------------------- eventos -----------------------
    def _on_search(self, t: str):
        self.search_text = t
        self._refresh()

    def _on_filter_change(self, _):
        self.filter_role = self.cbo_role.currentText()
        self.filter_state = self.cbo_state.currentText()
        self._refresh()

    def _on_order_change(self, _):
        self.order_by = self.cbo_order.currentText()
        self._refresh()
