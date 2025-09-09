# ui/widgets/user_panel.py
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel, QPushButton, QCheckBox


class PanelUsuario(QFrame):
    """
    Panel desplegable con datos del usuario y acciones rápidas.
    Se muestra anclado al botón de usuario en la Topbar.
    """
    cambiar_usuario = pyqtSignal()
    cambiar_tema = pyqtSignal(bool)   # emite True si modo oscuro, False si claro

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.Popup)
        self.setObjectName("UserPanel")

        # IMPORTANTE: crear el layout ANTES de usarlo
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        # Datos del usuario
        nombre = QLabel("Dylan Bourjac"); nombre.setObjectName("UserName")
        rol    = QLabel("Tatuador");       rol.setObjectName("UserMeta")
        mail   = QLabel("dbourjac@hotmail.com"); mail.setObjectName("UserMeta")
        lay.addWidget(nombre); lay.addWidget(rol); lay.addWidget(mail)

        # Toggle de tema
        self.chk_dark = QCheckBox("Modo oscuro")
        self.chk_dark.stateChanged.connect(lambda s: self.cambiar_tema.emit(s == Qt.Checked))
        lay.addWidget(self.chk_dark)

        # Acciones
        btn_switch   = QPushButton("Cambiar usuario"); btn_switch.setObjectName("GhostSmall")
        btn_settings = QPushButton("Ajustes");         btn_settings.setObjectName("GhostSmall")
        btn_info     = QPushButton("Información");     btn_info.setObjectName("GhostSmall")
        btn_switch.clicked.connect(self.cambiar_usuario.emit)

        for b in (btn_switch, btn_settings, btn_info):
            b.setFixedHeight(28)
            lay.addWidget(b)
