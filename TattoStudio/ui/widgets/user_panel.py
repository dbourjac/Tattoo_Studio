# ui/widgets/user_panel.py

from typing import Optional, Union

from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QPushButton, QCheckBox, QHBoxLayout
)

from ui.pages.common import (
    role_to_label,
    normalize_instagram,
    render_instagram,
)


class PanelUsuario(QFrame):
    """
    Panel desplegable con datos del usuario y acciones rápidas.
    Se muestra anclado al botón de usuario en la Topbar.
    """

    # Señales que consumen las ventanas superiores (MainWindow)
    cambiar_tema = pyqtSignal(bool)       # emite True si modo oscuro, False si claro
    logout = pyqtSignal()                 # cerrar sesión explícitamente
    abrir_ajustes = pyqtSignal()          # ir a Ajustes
    abrir_info = pyqtSignal()             # abrir diálogo "Acerca de / Información"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.Popup)
        self.setObjectName("UserPanel")

        self._block_theme_signal = False
        self._current_user_id: Optional[int] = None

        # ---------- Layout raíz
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # ---------- Header (nombre + rol)
        self.nombre_lbl = QLabel("—")
        self.nombre_lbl.setObjectName("UserName")

        self.rol_lbl = QLabel("—")
        self.rol_lbl.setObjectName("UserMeta")

        # Email clicable (mailto)
        self.mail_lbl = QLabel()
        self.mail_lbl.setObjectName("UserMeta")
        self.mail_lbl.setTextFormat(Qt.RichText)
        self.mail_lbl.setOpenExternalLinks(True)
        self.mail_lbl.setText('<a href="mailto:—">—</a>')

        # Instagram clicable
        self.ig_lbl = QLabel()
        self.ig_lbl.setObjectName("UserMeta")
        self.ig_lbl.setTextFormat(Qt.RichText)
        self.ig_lbl.setOpenExternalLinks(True)
        self.ig_lbl.setText("—")

        root.addWidget(self.nombre_lbl)
        root.addWidget(self.rol_lbl)
        root.addWidget(self.mail_lbl)
        root.addWidget(self.ig_lbl)

        # ---------- Separador fino
        root.addLayout(self._thin_sep())

        # ---------- Toggle de tema
        self.chk_dark = QCheckBox("Modo oscuro")
        self.chk_dark.stateChanged.connect(self._on_theme_toggle)
        root.addWidget(self.chk_dark)

        # ---------- Acciones
        actions = QVBoxLayout()
        actions.setAlignment(Qt.AlignHCenter)
        actions.setSpacing(8)

        self.btn_logout = QPushButton("Cerrar sesión")
        self.btn_logout.setObjectName("GhostSmall")
        self.btn_logout.setFixedHeight(28)
        self.btn_logout.clicked.connect(lambda: self._emit_and_close(self.logout))

        self.btn_settings = QPushButton("Ajustes")
        self.btn_settings.setObjectName("GhostSmall")
        self.btn_settings.setFixedHeight(28)
        self.btn_settings.clicked.connect(lambda: self._emit_and_close(self.abrir_ajustes))

        self.btn_info = QPushButton("Información")
        self.btn_info.setObjectName("GhostSmall")
        self.btn_info.setFixedHeight(28)
        self.btn_info.clicked.connect(lambda: self._emit_and_close(self.abrir_info))

        for b in (self.btn_logout, self.btn_settings, self.btn_info):
            actions.addWidget(b)

        root.addLayout(actions)
        self._apply_styles()
    
    def _apply_styles(self) -> None:
        self.setStyleSheet("""
        /* Tipografía y separadores */
        #UserPanel QLabel#UserName { font-weight: 700; letter-spacing: .2px; }
        #UserPanel QLabel#UserMeta { color: rgba(255,255,255,.82); }
        #UserPanel #ThinSep { border-top: 1px solid rgba(255,255,255,.18); }

        /* Botones más bonitos (solo dentro del panel) */
        #UserPanel QPushButton {
            min-width: 200px;
            min-height: 30px;
            padding: 6px 12px;
            border-radius: 12px;
            background: rgba(255,255,255,.06);
            border: 1px solid rgba(255,255,255,.12);
            font-weight: 600;
            qproperty-iconSize: 16px;
        }
        #UserPanel QPushButton:hover {
            background: rgba(255,255,255,.10);
            border-color: rgba(255,255,255,.22);
        }
        #UserPanel QPushButton:pressed {
            background: rgba(255,255,255,.08);
        }
        """)

    # ---------------------------------------------------------------------
    # Métodos públicos (para usar desde MainWindow / Topbar)
    # ---------------------------------------------------------------------

    def set_user(self, user: Union[dict, object], *, is_dark: Optional[bool] = None) -> None:
        """
        Inyecta los datos del usuario autenticado.
        Acepta tanto un dict como un objeto (SQLAlchemy u otro).
        Campos esperados (si existen): id, name|username, email, role, instagram
        """
        def g(src, key, default=None):
            if isinstance(src, dict):
                return src.get(key, default)
            return getattr(src, key, default)

        self._current_user_id = g(user, "id", None)

        # name ← (name) o (username) como fallback
        name = g(user, "name", None) or g(user, "username", None) or "—"
        role = g(user, "role", None)
        email = g(user, "email", None)

        # Instagram puede venir como "instagram", "ig" o "insta"
        ig = g(user, "instagram", None) or g(user, "ig", None) or g(user, "insta", None)
        ig_norm = normalize_instagram(ig) if ig else None          # sin @
        ig_disp = render_instagram(ig_norm) if ig_norm else "—"     # con @

        self.nombre_lbl.setText(name)
        self.rol_lbl.setText(role_to_label(role) if role else "—")

        if email:
            self.mail_lbl.setText(
            f'<a href="mailto:{email}" style="color:#A7C7FF; text-decoration:none">{email}</a>'
        )
        else:
            self.mail_lbl.setText("—")

        if ig_norm:
            self.ig_lbl.setText(
            f'<a href="https://instagram.com/{ig_norm}" target="_blank" '
            f'style="color:#A7C7FF; text-decoration:none">{ig_disp}</a>'
        )
        else:
            self.ig_lbl.setText("—")

        if is_dark is not None:
            self.set_theme(is_dark)

    def set_theme(self, is_dark: bool) -> None:
        """Actualiza el checkbox de tema sin re-emitir la señal."""
        try:
            self._block_theme_signal = True
            self.chk_dark.setChecked(bool(is_dark))
        finally:
            self._block_theme_signal = False

    def show_near(self, anchor_widget) -> None:
        """Muestra el panel anclado al widget (botón de usuario en la Topbar)."""
        self.adjustSize()
        if anchor_widget is None:
            self.move(QCursor.pos())
        else:
            p = anchor_widget.mapToGlobal(QPoint(0, anchor_widget.height()))
            p += QPoint(0, 4)  # para que la sombra no se pegue al anchor
            self.move(p)
        self.show()

    def show_at_cursor(self) -> None:
        self.adjustSize()
        self.move(QCursor.pos())
        self.show()

    # ---------------------------------------------------------------------
    # Internos
    # ---------------------------------------------------------------------

    def _thin_sep(self) -> QHBoxLayout:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        line.setObjectName("ThinSep")

        box = QHBoxLayout()
        box.setContentsMargins(0, 4, 0, 8)
        box.addWidget(line)
        return box

    def _on_theme_toggle(self, state: int) -> None:
        if self._block_theme_signal:
            return
        self.cambiar_tema.emit(state == Qt.Checked)

    def _emit_and_close(self, signal: pyqtSignal) -> None:
        """Emite la señal y cierra el panel (UX correcta)."""
        try:
            signal.emit()
        finally:
            self.close()
