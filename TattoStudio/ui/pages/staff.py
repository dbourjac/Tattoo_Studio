from __future__ import annotations

from typing import List, Dict

from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRect, QPoint
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QScrollArea, QFrame, QSizePolicy, QSpacerItem, QLayout, QStyle
)

# BD
from sqlalchemy.orm import Session
from data.db.session import SessionLocal
from data.models.user import User
from data.models.artist import Artist

# Sesión actual (para RBAC)
from services.contracts import get_current_user


# ---------------------------
# FlowLayout (wrap auto)
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


def _role_text(role: str) -> str:
    return {"admin": "Admin", "assistant": "Asistente", "artist": "Tatuador"}.get(role, role)


class StaffPage(QWidget):
    """
    Staff (conectado a BD):
      - Toolbar (solo admin): Agregar staff | Importar/Exportar (disabled)
      - Filtros: Buscar + rol + estado + orden
      - Cards en FlowLayout (wrap), sin paginación
    """
    agregar_staff = pyqtSignal()       # MainWindow abrirá el detalle en modo “nuevo”
    abrir_staff = pyqtSignal(dict)     # Emite diccionario compacto del usuario

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

        # ========================= Toolbar superior (solo admin) =========================
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

        self.btn_import = QPushButton("Importar CSV");  self.btn_import.setObjectName("GhostSmall"); self.btn_import.setEnabled(False)
        self.btn_export = QPushButton("Exportar CSV");  self.btn_export.setObjectName("GhostSmall"); self.btn_export.setEnabled(False)
        bar_top_l.addWidget(self.btn_import)
        bar_top_l.addWidget(self.btn_export)

        root.addWidget(bar_top)
        # guardamos referencia para RBAC
        self._admin_toolbar = bar_top

        # ========================= Toolbar filtros (visible para todos) ==================
        bar_filters = QFrame()
        bar_filters.setObjectName("Toolbar")
        f = QHBoxLayout(bar_filters)
        f.setContentsMargins(12, 8, 12, 8)
        f.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre/usuario, rol o artista…")
        self.search.textChanged.connect(self._on_search)
        f.addWidget(self.search, stretch=1)

        lbl_rol = QLabel("Rol:"); lbl_rol.setStyleSheet("background: transparent;")
        lbl_est = QLabel("Estado:"); lbl_est.setStyleSheet("background: transparent;")
        lbl_ord = QLabel("Ordenar por:"); lbl_ord.setStyleSheet("background: transparent;")

        self.cbo_role = QComboBox(); self.cbo_role.addItems(["Todos", "Admin", "Asistente", "Tatuador"])
        self.cbo_role.currentTextChanged.connect(self._on_filter_change)
        self.cbo_state = QComboBox(); self.cbo_state.addItems(["Todos", "Activo", "Inactivo"])
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
        self.flow = FlowLayout(host, margin=0, hspacing=16, vspacing=16)
        host.setLayout(self.flow)
        self.scroll.setWidget(host)
        root.addWidget(self.scroll, stretch=1)

        # Carga inicial desde BD
        self._all: List[Dict] = []
        self.reload_from_db_and_refresh()

        # Aplica RBAC inicial de la toolbar (y también en showEvent)
        self._apply_toolbar_rbac()

    # ----------------------- RBAC toolbar -----------------------
    def _apply_toolbar_rbac(self):
        """Muestra/oculta toda la barra superior según el rol actual."""
        cu = get_current_user() or {}
        is_admin = (cu.get("role") == "admin")

        # barra completa solo para admin
        self._admin_toolbar.setVisible(is_admin)

        # y por claridad, también los botones (aunque estén dentro)
        self.btn_new.setVisible(is_admin)
        self.btn_import.setVisible(is_admin)
        self.btn_export.setVisible(is_admin)

    def showEvent(self, e):
        super().showEvent(e)
        # Al entrar a la vista (o cambiar de usuario) reevalúa la toolbar
        self._apply_toolbar_rbac()

    # ----------------------- BD -----------------------
    def _load_from_db(self) -> List[Dict]:
        """
        Devuelve una lista de dicts con los campos necesarios para pintar las cards.
        """
        rows: List[Dict] = []
        with SessionLocal() as db:  # type: Session
            # LEFT JOIN para traer el nombre del artista si aplica
            q = (
                db.query(
                    User.id, User.username, User.role, User.is_active, User.artist_id,
                    Artist.name.label("artist_name")
                )
                .outerjoin(Artist, Artist.id == User.artist_id)
            )
            for (uid, username, role, is_active, artist_id, artist_name) in q.all():
                nombre_visible = artist_name if (role == "artist" and artist_name) else username
                rows.append({
                    "id": uid,
                    "username": username,
                    "nombre": nombre_visible or username,
                    "rol": _role_text(role),
                    "role_raw": role,
                    "estado": "Activo" if is_active else "Inactivo",
                    "is_active": bool(is_active),
                    "artist_id": artist_id,
                    "artist_name": artist_name or "—",
                })
        return rows

    def reload_from_db_and_refresh(self):
        self._all = self._load_from_db()
        self._refresh()

    # ----------------------- filtrado/orden -----------------------
    def _apply_filters(self) -> List[Dict]:
        txt = self.search_text.lower().strip()

        def match(s: Dict) -> bool:
            if txt:
                if not (
                    txt in s["nombre"].lower()
                    or txt in s["username"].lower()
                    or txt in s["rol"].lower()
                    or (s.get("artist_name") and txt in s["artist_name"].lower())
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
    def _make_card(self, s: Dict) -> QFrame:
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

        # Si es artista, muestra el username debajo; si no, muestra “—”
        extra = QLabel(s["username"] if s["role_raw"] == "artist" else "—")
        extra.setStyleSheet("background: transparent; color:#6C757D;")
        col.addWidget(extra)

        lay.addLayout(col, stretch=1)

        # Acciones
        actions = QVBoxLayout(); actions.setSpacing(8)
        btn_profile = QPushButton("Ver perfil"); btn_profile.setObjectName("GhostSmall")
        btn_profile.clicked.connect(lambda: self.abrir_staff.emit(s))
        actions.addWidget(btn_profile); actions.addStretch(1)
        lay.addLayout(actions)

        return card

    def _make_avatar_pixmap(self, size: int, nombre: str) -> QPixmap:
        initials = "".join([p[0].upper() for p in nombre.split()[:2]]) or "?"
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
