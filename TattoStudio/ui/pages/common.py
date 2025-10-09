from __future__ import annotations

# ============================================================
# common.py — Helpers compartidos (UI, RBAC, colores, etc.)
#
# Incluye:
# 1) Páginas simples:
#    - make_simple_page(nombre)
# 2) Permisos / elevación (RBAC):
#    - request_elevation_if_needed(parent, resource, action) -> bool
#    - ensure_permission(parent, resource, action, owner_id=None) -> bool
# 3) Utilidades de texto / i18n:
#    - ROLE_LABELS, role_to_label(role)
#    - normalize_instagram(handle), render_instagram(handle)
# 4) Colores por tatuador (artist_colors.json):
#    - artist_colors_path()
#    - load_artist_colors() -> dict[str,str]
#    - save_artist_color(key, hex_color)
#    - DEFAULT_PALETTE, fallback_color_for(index)
# 5) Avatares e imagen:
#    - round_pixmap(QPixmap, size, border_px=0, border_hex="#000000") -> QPixmap
# 6) Menús / popups base:
#    - NoStatusTipMenu(QMenu)  (no borra el status bar)
#    - FramelessPopup(QDialog) (sin barra de título, arrastrable)
# 7) Layouts:
#    - FlowLayout  (flujo horizontal con salto de línea)
# 8) Tiempo (opcional, para uso futuro):
#    - fmt_dt_local(value, fmt="%d/%m/%Y %H:%M") -> str
#
# NOTA: Sólo centraliza helpers. No modifica lógicas existentes.
# ============================================================

from typing import Optional, Dict, Any
import os, json, math
from datetime import datetime, timezone

from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QEvent, QRectF
from PyQt5.QtGui import QPainter, QPixmap, QBrush, QPen, QColor, QPainterPath
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QInputDialog, QLineEdit, QMessageBox,
    QMenu, QDialog, QLayout, QSizePolicy
)

# SQLAlchemy / sesión
from sqlalchemy.orm import Session
from data.db.session import SessionLocal

# RBAC & sesión actual (ya presentes en tu proyecto)
from services.permissions import assistant_needs_code, verify_master_code, elevate_for, can
from services.contracts import get_current_user


# ------------------------------------------------------------
# Configuración
# ------------------------------------------------------------
ELEVATION_MINUTES: int = 5  # ventana de elevación (min) para assistant

# Paleta por defecto (coherente con lo que vienes usando)
DEFAULT_PALETTE = [
    "#4ade80", "#60a5fa", "#f472b6", "#9d0dc1",
    "#f59e0b", "#22d3ee", "#a78bfa", "#34d399",
    "#ffd166", "#b197fc",
]

ROLE_LABELS = {"admin": "Admin", "assistant": "Asistente", "artist": "Tatuador"}


# ------------------------------------------------------------
# Páginas simples
# ------------------------------------------------------------
def make_simple_page(nombre: str) -> QWidget:
    """Crea una página placeholder con un título centrado."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(40, 40, 40, 40)
    title = QLabel(nombre)
    title.setObjectName("H1")
    lay.addWidget(title, alignment=Qt.AlignCenter)
    return w


# ------------------------------------------------------------
# Elevación: solicitar código maestro SOLO si es necesario
# ------------------------------------------------------------
def request_elevation_if_needed(parent: QWidget, resource: str, action: str) -> bool:
    """
    Si el usuario actual es assistant y la acción es 🔒, solicita código maestro,
    valida contra MASTER_CODE_HASH y eleva permisos por ELEVATION_MINUTES.
    """
    user = get_current_user()
    if not user:
        QMessageBox.warning(parent, "Sesión", "No hay usuario activo.")
        return False

    role = user.get("role")
    if role != "assistant" or not assistant_needs_code(resource, action):
        return True  # no requiere elevación

    code, ok = QInputDialog.getText(
        parent, "Código maestro", "Ingresa el código maestro:", QLineEdit.Password
    )
    if not ok:
        return False

    code = (code or "").strip()
    if not code:
        QMessageBox.warning(parent, "Código maestro", "El código no puede estar vacío.")
        return False

    with SessionLocal() as db:  # type: Session
        if verify_master_code(code, db):
            elevate_for(user.get("id"), minutes=ELEVATION_MINUTES)
            QMessageBox.information(
                parent, "Permiso concedido",
                f"Permisos elevados por {ELEVATION_MINUTES} minutos."
            )
            return True

    QMessageBox.critical(parent, "Código inválido", "El código maestro no es correcto.")
    return False


def ensure_permission(
    parent: QWidget,
    resource: str,
    action: str,
    *,
    owner_id: Optional[int] = None,
) -> bool:
    """
    1) Gestiona elevación si aplica (assistant + acción 🔒).
    2) Valida permiso con la matriz RBAC (incluye casos 'own').
    """
    user = get_current_user()
    if not user:
        QMessageBox.warning(parent, "Sesión", "No hay usuario activo.")
        return False

    if not request_elevation_if_needed(parent, resource, action):
        return False

    allowed = can(
        user.get("role"),
        resource,
        action,
        owner_id=owner_id,
        user_artist_id=user.get("artist_id"),
        user_id=user.get("id"),
    )
    if not allowed:
        QMessageBox.warning(parent, "Permisos", "No tienes permiso para esta acción.")
        return False
    return True


# ------------------------------------------------------------
# Utilidades de texto / i18n
# ------------------------------------------------------------
def role_to_label(role: str) -> str:
    """admin/assistant/artist → Admin/Asistente/Tatuador (display)."""
    return ROLE_LABELS.get((role or "").strip(), role or "")


def normalize_instagram(handle: str) -> str:
    """Guarda sin @."""
    if not handle:
        return ""
    h = handle.strip()
    return h[1:] if h.startswith("@") else h


def render_instagram(handle: str) -> str:
    """Muestra con @ (display/UI)."""
    h = normalize_instagram(handle)
    return f"@{h}" if h else ""


# ------------------------------------------------------------
# Colores por tatuador (artist_colors.json)
# ------------------------------------------------------------
def _app_root() -> str:
    # ui/pages/common.py -> ui/pages -> ui -> <root>
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))


def artist_colors_path() -> str:
    """Ruta estándar del proyecto: ./assets/artist_colors.json."""
    return os.path.join(_app_root(), "assets", "artist_colors.json")


def _candidate_color_paths() -> list[str]:
    """
    Rutas candidatas (se respeta primero TATTOO_COLORS si existe):
    - %TATTOO_COLORS%
    - ./assets/artist_colors.json
    - ./artist_colors.json
    - ./data/artist_colors.json
    - %USERPROFILE%/.tattoo_studio/artist_colors.json
    """
    env = os.environ.get("TATTOO_COLORS")
    root = _app_root()
    paths = [
        env,
        os.path.join(root, "assets", "artist_colors.json"),
        os.path.join(root, "artist_colors.json"),
        os.path.join(root, "data", "artist_colors.json"),
        os.path.join(os.path.expanduser("~"), ".tattoo_studio", "artist_colors.json"),
    ]
    # únicos y existentes
    out, seen = [], set()
    for p in paths:
        if not p:
            continue
        try:
            p = os.path.abspath(p)
        except Exception:
            pass
        if p in seen:
            continue
        seen.add(p)
        if os.path.exists(p):
            out.append(p)
    return out


def load_artist_colors() -> Dict[str, str]:
    """
    Carga un dict { clave: "#hex" } indiferente a mayúsculas.
    Acepta varios formatos:
      {"12": "#ff00aa", "Nombre": "#00ff55"}
      {"colors": {...}}
      {"12": {"hex":"#ff00aa"}, ...}
    """
    for p in _candidate_color_paths():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            # soporta envoltura {"colors": {...}}
            if isinstance(data, dict) and "colors" in data and isinstance(data["colors"], dict):
                data = data["colors"]
            out = {}
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, dict) and "hex" in v:
                        v = v.get("hex")
                    if isinstance(v, str) and v.strip():
                        out[str(k).lower()] = v.strip()
            return out
        except Exception:
            continue
    return {}


def save_artist_color(key: str, hex_color: str) -> None:
    """
    Guarda/actualiza un color en ./assets/artist_colors.json (clave case-insensitive).
    Si no existe el archivo, lo crea.
    """
    key = (key or "").lower()
    if not key or not hex_color:
        return

    p = artist_colors_path()
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        data = {}
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        # normaliza al mismo formato plano {clave: hex}
        data = {str(k).lower(): str(v) for k, v in (data or {}).items()}
        data[key] = hex_color
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        # Escritura “best effort”: si falla, se ignora silenciosamente
        pass


def fallback_color_for(index: Optional[int]) -> str:
    """Devuelve un color de DEFAULT_PALETTE según índice."""
    if index is None:
        return DEFAULT_PALETTE[0]
    return DEFAULT_PALETTE[index % len(DEFAULT_PALETTE)]


# ------------------------------------------------------------
# Imagen / Avatares
# ------------------------------------------------------------
def round_pixmap(src: QPixmap, size: int, border_px: int = 0, border_hex: str = "#000000") -> QPixmap:
    """Hace un pixmap circular con borde opcional."""
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    if src is None or src.isNull():
        return out
    pm = src.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.Antialiasing, True)
    path = QPainterPath()
    path.addEllipse(QRectF(0.0, 0.0, float(size), float(size)))
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pm)
    if border_px > 0:
        pen = QPen(QColor(border_hex))
        pen.setWidth(border_px)
        painter.setPen(pen)
        inset = border_px // 2
        painter.drawEllipse(QRect(inset, inset, size - border_px, size - border_px))
    painter.end()
    return out


# ------------------------------------------------------------
# Menús y Popups base
# ------------------------------------------------------------
class NoStatusTipMenu(QMenu):
    """QMenu que ignora StatusTip para no “borrar” el status bar al hover."""
    def event(self, e):
        if e.type() == QEvent.StatusTip:
            return True
        return super().event(e)


class FramelessPopup(QDialog):
    """
    Popup sin barra de título y arrastrable (usa QSS del tema).
    Ideal para “Cambiar color”, “Cambiar contraseña”, etc.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground, False)  # dejamos el QSS actual
        self._drag_pos: Optional[QPoint] = None

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


# ------------------------------------------------------------
# FlowLayout (para chips/cards en filas con salto)
# ------------------------------------------------------------
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=8):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._hspace = spacing
        self._vspace = spacing
        self._items = []

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, i): return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i): return self._items.pop(i) if 0 <= i < len(self._items) else None
    def expandingDirections(self): return Qt.Orientations(Qt.Orientation(0))
    def hasHeightForWidth(self): return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self): return QSize(200, self.heightForWidth(200))

    def _do_layout(self, rect: QRect, test_only: bool):
        x, y, line_height = rect.x(), rect.y(), 0
        for i in self._items:
            w = i.sizeHint().width(); h = i.sizeHint().height()
            if x + w > rect.right() and line_height > 0:
                x = rect.x(); y += line_height + self._vspace
                line_height = 0
            if not test_only:
                i.setGeometry(QRect(QPoint(x, y), QSize(w, h)))
            x += w + self._hspace
            line_height = max(line_height, h)
        return y + line_height - rect.y()


# ------------------------------------------------------------
# Tiempo (opcional — para centralizar formatos locales)
# ------------------------------------------------------------
def fmt_dt_local(value: Any, fmt: str = "%d/%m/%Y %H:%M") -> str:
    """
    Formatea robustamente en hora local:
    - Si es aware: convierte a local.
    - Si es naive: prueba como 'naive=local' y 'naive=UTC→local' y elige:
        1) el que NO quede en el futuro; si ambos son pasados, el más reciente;
        2) si ambos quedan en el futuro, el más cercano a ahora.
    - Acepta datetime, str ISO/SQL y epoch (int/float).
    """
    if value is None:
        return "—"

    # Normaliza a datetime
    dt: Optional[datetime] = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        try:
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            dt = None
    elif isinstance(value, str):
        try:
            # Soporta 'YYYY-MM-DD HH:MM:SS[.fff][Z]'
            s = value.strip().replace("T", " ")
            if s.endswith("Z"):
                s = s[:-1]
                dt = datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
            else:
                dt = datetime.fromisoformat(s)
        except Exception:
            dt = None

    if not isinstance(dt, datetime):
        return str(value)

    now_local = datetime.now().astimezone()

    if dt.tzinfo is not None:
        # aware -> a local
        try:
            return dt.astimezone().strftime(fmt)
        except Exception:
            return dt.strftime(fmt)

    # naive -> probar local vs. UTC→local
    try:
        as_local = dt.replace(tzinfo=None)         # interpretarlo como local (naive)
        as_local = as_local.astimezone()           # a aware local (no-op si ya local)
    except Exception:
        as_local = None

    try:
        as_utc = dt.replace(tzinfo=timezone.utc).astimezone()
    except Exception:
        as_utc = None

    candidates = [x for x in (as_local, as_utc) if isinstance(x, datetime)]
    if not candidates:
        return dt.strftime(fmt)

    # elegir candidato según heurística
    def score(d: datetime) -> tuple[int, float]:
        # 0 si no está en futuro; 1 si está en futuro. Luego distancia a 'now'.
        delta = (d - now_local).total_seconds()
        return (1 if delta > 0 else 0, abs(delta))

    best = sorted(candidates, key=score)[0]
    return best.strftime(fmt)
