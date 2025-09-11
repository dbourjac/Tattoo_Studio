from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton


class LoginWindow(QWidget):
    """
    Ventana de inicio de sesión (mock). No valida credenciales;
    solo emite 'acceso_solicitado' para pasar a la ventana principal.
    """
    acceso_solicitado = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TattooStudio — Inicio de sesión")
        self.setMinimumSize(420, 280)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(16)

        title = QLabel("Bienvenido a TattooStudio")
        title.setObjectName("H1")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        form = QVBoxLayout(); form.setSpacing(10)

        lbl_user = QLabel("Usuario")
        self.in_user = QLineEdit(); self.in_user.setPlaceholderText("Escribe tu usuario...")

        lbl_code = QLabel("Código de acceso")
        self.in_code = QLineEdit(); self.in_code.setPlaceholderText("Escribe tu código...")
        self.in_code.setEchoMode(QLineEdit.Password)

        form.addWidget(lbl_user);  form.addWidget(self.in_user)
        form.addWidget(lbl_code);  form.addWidget(self.in_code)
        root.addLayout(form)

        self.btn_login = QPushButton("Entrar")
        self.btn_login.setObjectName("CTA")
        self.btn_login.setMinimumHeight(36)
        self.btn_login.clicked.connect(self.acceso_solicitado.emit)
        root.addWidget(self.btn_login)

        hint = QLabel("*No valida credenciales xd*")
        hint.setAlignment(Qt.AlignCenter)
        hint.setObjectName("Hint")
        root.addWidget(hint)
