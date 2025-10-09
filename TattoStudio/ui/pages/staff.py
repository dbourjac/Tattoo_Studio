from __future__ import annotations

from typing import List, Dict, Optional
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRect, QPoint
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPainterPath
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QScrollArea,
    QFrame, QSizePolicy, QStyle, QToolButton, QGraphicsDropShadowEffect, QMenu,
    QTableWidgetItem
)

# BD
from sqlalchemy.orm import Session
from data.db.session import SessionLocal
from data.models.user import User
from data.models.artist import Artist

# Sesión actual (para RBAC)
from services.contracts import get_current_user

# === Helpers centralizados (sin cambiar lógica) ===
from ui.pages.common import (
    role_to_label, load_artist_colors, fallback_color_for, round_pixmap,
    FlowLayout, NoStatusTipMenu
)


# ========================= Helpers de presentación =========================

def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]

def _avatar_dir() -> Path:
    p = _project_root() / "assets" / "avatars"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _avatar_path(uid: int) -> Path:
    return _avatar_dir() / f"{uid}.png"

def _placeholder_avatar(size: int, nombre: str) -> QPixmap:
    initials = "".join([p[0].upper() for p in (nombre or "").split()[:2]]) or "?"
    pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#d1d5db")); p.setPen(Qt.NoPen); p.drawEllipse(0, 0, size, size)
    p.setPen(QColor("#111")); p.drawText(pm.rect(), Qt.AlignCenter, initials); p.end()
    return pm

def _artist_color_hex(artist_id: Optional[int]) -> str:
    """
    Usa overrides de assets/artist_colors.json (common.load_artist_colors)
    y si no existe color definido, aplica un fallback estable por índice.
    """
    if not artist_id:
        return "#9CA3AF"
    try:
        ov = load_artist_colors()
        key = str(int(artist_id)).lower()
        if key in ov and ov[key]:
            return ov[key]
    except Exception:
        pass
    # 10 colores base (mismo criterio que en otras páginas)
    idx = int(artist_id) % 10
    return fallback_color_for(idx)


# -------------------------- Card interactiva --------------------------
class StaffCard(QFrame):
    open_requested = pyqtSignal(dict)

    def __init__(self, data: Dict):
        super().__init__()
        self.data = data
        self.setObjectName("StaffCard")     # ← outer único (no “Card” para evitar doble borde)
        self.setMouseTracking(True)

        self._body = None  # se asigna después

        # Anchura inicial (se sobreescribe dinámicamente por la página)
        self._fixed_w = 420
        self.setMinimumWidth(self._fixed_w)
        self.setMaximumWidth(self._fixed_w)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Barra de color superior
        artist_hex = _artist_color_hex(data.get("artist_id") if data.get("role_raw") == "artist" else None)
        bar = QFrame(); bar.setFixedHeight(4)
        bar.setStyleSheet(f"background:{artist_hex}; border-radius:2px;")
        outer.addWidget(bar)

        # Cuerpo: el que tiene fondo "Card" y al que aplicamos el hover
        body = QFrame(); body.setObjectName("Card")
        body_l = QHBoxLayout(body)
        pad_top_bot = 22 if data.get("role_raw") == "artist" else 18
        body_l.setContentsMargins(14, pad_top_bot, 14, pad_top_bot)
        body_l.setSpacing(14)

        # Avatar grande
        AV_SIZE = 96
        avatar = QLabel(); avatar.setFixedSize(AV_SIZE, AV_SIZE)
        avatar.setStyleSheet("background:transparent;")
        ap = _avatar_path(int(data["id"]))
        if ap.exists():
            pm = round_pixmap(QPixmap(str(ap)), AV_SIZE)  # ← common.round_pixmap
        else:
            pm = _placeholder_avatar(AV_SIZE, data["nombre"] or data["username"])
        avatar.setPixmap(pm)
        body_l.addWidget(avatar, alignment=Qt.AlignTop)

        # Columna central
        col = QVBoxLayout(); col.setSpacing(6)

        # Nombre + punto
        name_row = QHBoxLayout(); name_row.setSpacing(8)
        dot = QLabel(); dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"background:{artist_hex}; border-radius:5px;")
        name_row.addWidget(dot, 0, Qt.AlignVCenter)

        name = QLabel(data["nombre"])
        name.setStyleSheet("font-weight:700; background:transparent;")
        name_row.addWidget(name, 1)
        col.addLayout(name_row)

        # Chips
        chips = QHBoxLayout(); chips.setSpacing(8)
        chip_role = QLabel(role_to_label(data["role_raw"]))  # ← common.role_to_label
        chip_state = QLabel("Activo" if data["is_active"] else "Inactivo")
        chip_role.setStyleSheet(f"background:transparent; color:{artist_hex}; border:1px solid {artist_hex}; padding:2px 8px; border-radius:8px;")
        if data["is_active"]:
            chip_state.setStyleSheet(f"background:transparent; color:{artist_hex}; border:1px solid {artist_hex}; padding:2px 8px; border-radius:8px;")
        else:
            chip_state.setStyleSheet("background:transparent; color:#9CA3AF; border:1px solid #555a61; padding:2px 8px; border-radius:8px;")
        chips.addWidget(chip_role); chips.addWidget(chip_state); chips.addStretch(1)
        col.addLayout(chips)

        # Línea info (instagram · email)
        info = []
        if data.get("instagram"): info.append(data["instagram"])
        if data.get("email"): info.append(data["email"])
        extra = QLabel("  ·  ".join(info) if info else "—")
        extra.setStyleSheet("background:transparent; color:#6C757D;")
        col.addWidget(extra)

        body_l.addLayout(col, stretch=1)
        outer.addWidget(body)
        self._body = body

        # Sombra ligera (solo al crear; se intensifica en hover)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setOffset(0, 2)
        self._shadow.setBlurRadius(12)
        self._shadow.setColor(QColor(0, 0, 0, 80))
        self._body.setGraphicsEffect(self._shadow)

    # Interacciones
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.open_requested.emit(self.data)
        super().mouseReleaseEvent(e)

    def contextMenuEvent(self, e):
        m = NoStatusTipMenu(self)  # ← evita limpiar el status bar
        act = m.addAction("Ver perfil")
        chosen = m.exec_(e.globalPos())
        if chosen == act:
            self.open_requested.emit(self.data)

    def enterEvent(self, e):
        # sombreado suave (sin dibujar bordes cuadrados sobre el body)
        self._body.setStyleSheet("background: rgba(255,255,255,0.04);")
        self._shadow.setBlurRadius(18)
        self._shadow.setColor(QColor(0, 0, 0, 120))
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._body.setStyleSheet("")  # vuelve a QSS por defecto
        self._shadow.setBlurRadius(12)
        self._shadow.setColor(QColor(0, 0, 0, 80))
        super().leaveEvent(e)

    # para que la página pueda fijar el ancho exacto de 3-col
    def set_fixed_width(self, w: int):
        self._fixed_w = max(360, w)
        self.setMinimumWidth(self._fixed_w)
        self.setMaximumWidth(self._fixed_w)


# ============================== Página Staff ==============================
class StaffPage(QWidget):
    agregar_staff = pyqtSignal()
    abrir_staff = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        # ---- estado UI (por defecto Estado = Activo) ----
        self.search_text = ""
        self.filter_role = "Todos"
        self.filter_state = "Activo"
        self.order_by = "A–Z"

        # ---- layout raíz ----
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # ----------------- Filtros -----------------
        bar_filters = QFrame(); bar_filters.setObjectName("Toolbar")
        f = QHBoxLayout(bar_filters); f.setContentsMargins(12, 8, 12, 8); f.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre/usuario, rol o artista…")
        self.search.setStyleSheet("""
            QLineEdit{ color:#E8EAF0; }
            QLineEdit::placeholder{ color:#B9C2CF; }
        """)
        self.search.textChanged.connect(self._on_search)
        f.addWidget(self.search, stretch=1)

        lbl_rol = QLabel("Rol:"); lbl_rol.setStyleSheet("background:transparent;")
        lbl_est = QLabel("Estado:"); lbl_est.setStyleSheet("background:transparent;")
        lbl_ord = QLabel("Ordenar por:"); lbl_ord.setStyleSheet("background:transparent;")

        # --- combos ---
        self.cbo_role = QComboBox(); self.cbo_role.addItems(["Todos", "Admin", "Asistente", "Tatuador"])
        self.cbo_state = QComboBox(); self.cbo_state.addItems(["Todos", "Activo", "Inactivo"])
        self.cbo_order = QComboBox(); self.cbo_order.addItems(["A–Z", "Rol"])

        # Seleccionar "Activo" sin disparar signals durante __init__
        self.cbo_state.blockSignals(True)
        self.cbo_state.setCurrentText("Activo")
        self.cbo_state.blockSignals(False)

        # Ahora sí conectar signals
        self.cbo_role.currentTextChanged.connect(self._on_filter_change)
        self.cbo_state.currentTextChanged.connect(self._on_filter_change)
        self.cbo_order.currentTextChanged.connect(self._on_order_change)

        f.addWidget(lbl_rol); f.addWidget(self.cbo_role)
        f.addWidget(lbl_est); f.addWidget(self.cbo_state)
        f.addWidget(lbl_ord); f.addWidget(self.cbo_order)
        root.addWidget(bar_filters)

        # ----------------- Zona de cards -----------------
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame)
        self.host = QWidget()
        self.flow = FlowLayout(self.host, margin=0, spacing=16)  # ← common.FlowLayout
        self.host.setLayout(self.flow)
        self.scroll.setWidget(self.host)
        root.addWidget(self.scroll, stretch=1)

        # ----------------- FAB (+) abajo derecha (solo admin) -----------------
        bottom_row = QHBoxLayout(); bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.addStretch(1)
        self.btn_fab = QToolButton()
        self.btn_fab.setText("+"); self.btn_fab.setToolTip("Agregar staff")
        self.btn_fab.setFixedSize(56, 56)
        self.btn_fab.setObjectName("GhostSmall")
        self.btn_fab.setStyleSheet("""
            QToolButton {
                border-radius: 28px;
                border: 1px solid rgba(255,255,255,0.14);
                padding: 0px; font-weight:800; font-size:22px;
                background: rgba(255,255,255,0.08);
            }
            QToolButton:hover { background: rgba(255,255,255,0.16); }
        """)
        self.btn_fab.clicked.connect(self.agregar_staff.emit)
        bottom_row.addWidget(self.btn_fab, 0, Qt.AlignRight)
        root.addLayout(bottom_row)

        # Carga inicial
        self._cards: List[StaffCard] = []
        self._all: List[Dict] = []
        self.reload_from_db_and_refresh()
        self._apply_fab_rbac()

    # ----------------------- RBAC FAB -----------------------
    def _apply_fab_rbac(self):
        cu = get_current_user() or {}
        self.btn_fab.setVisible(cu.get("role") == "admin")

    def showEvent(self, e):
        super().showEvent(e)
        self._apply_fab_rbac()
        self._update_card_widths()  # asegurar 3-col al mostrarse

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_card_widths()  # recalcular al redimensionar ventana

    # ----------------------- BD -----------------------
    def _load_from_db(self) -> List[Dict]:
        out: List[Dict] = []
        with SessionLocal() as db:  # type: Session
            q = (
                db.query(
                    User.id, User.username, User.role, User.is_active, User.artist_id,
                    User.email, User.instagram, Artist.name.label("artist_name")
                )
                .outerjoin(Artist, Artist.id == User.artist_id)
            )
            for (uid, username, role, is_active, artist_id, email, instagram, artist_name) in q.all():
                nombre = artist_name if (role == "artist" and artist_name) else (username or "")
                out.append({
                    "id": uid,
                    "username": username or "",
                    "nombre": nombre,
                    "role_raw": role,
                    "is_active": bool(is_active),
                    "artist_id": artist_id,
                    "artist_name": artist_name or "",
                    "email": email or "",
                    "instagram": ("@" + (instagram or "").lstrip("@")) if instagram else "",
                })
        return out

    def reload_from_db_and_refresh(self):
        self._all = self._load_from_db()
        self._refresh()

    # ----------------------- filtro/orden -----------------------
    def _apply_filters(self) -> List[Dict]:
        txt = self.search_text.lower().strip()

        def match(s: Dict) -> bool:
            if txt:
                if not (
                    txt in s["nombre"].lower()
                    or txt in s["username"].lower()
                    or txt in role_to_label(s["role_raw"]).lower()  # ← common.role_to_label
                    or (s.get("artist_name") and txt in s["artist_name"].lower())
                    or (s.get("email") and txt in s["email"].lower())
                    or (s.get("instagram") and txt in s["instagram"].lower())
                ):
                    return False
            if self.cbo_role.currentText() != "Todos" and role_to_label(s["role_raw"]) != self.cbo_role.currentText():
                return False
            if self.cbo_state.currentText() != "Todos":
                if self.cbo_state.currentText() == "Activo" and not s["is_active"]:
                    return False
                if self.cbo_state.currentText() == "Inactivo" and s["is_active"]:
                    return False
            return True

        rows = [s for s in self._all if match(s)]
        if self.cbo_order.currentText() == "A–Z":
            rows.sort(key=lambda s: s["nombre"].lower())
        else:
            rows.sort(key=lambda s: (role_to_label(s["role_raw"]), s["nombre"].lower()))
        return rows

    def _refresh(self):
        # limpiar flow
        while self.flow.count():
            it = self.flow.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        self._cards.clear()

        # crear cards
        for s in self._apply_filters():
            card = StaffCard(s)
            card.open_requested.connect(self.abrir_staff.emit)
            self.flow.addWidget(card)
            self._cards.append(card)

        # ajustar ancho a 3-col luego de crear
        self._update_card_widths()

    # ----------------------- cálculo 3 columnas -----------------------
    def _update_card_widths(self):
        if not self._cards:
            return
        spacing = self.flow.horizontalSpacing() if hasattr(self.flow, "horizontalSpacing") else 16
        cols = 3
        avail = self.scroll.viewport().width()
        # margen lateral del layout raíz: 24 a cada lado; el FlowLayout tiene margin 0.
        usable = max(200, avail - 0)
        card_w = int((usable - (cols - 1) * spacing) / cols)
        card_w = max(380, card_w)  # límite bajo para no romper layout

        for c in self._cards:
            c.set_fixed_width(card_w)

        # Forzar relayout
        self.host.updateGeometry()
        if hasattr(self.flow, "invalidate"):
            self.flow.invalidate()

    # ----------------------- eventos -----------------------
    def _on_search(self, t: str):
        self.search_text = t
        self._refresh()

    def _on_filter_change(self, _):
        self._refresh()

    def _on_order_change(self, _):
        self._refresh()
