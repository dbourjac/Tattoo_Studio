# ui/login.py
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QMessageBox
)

from data.db.session import SessionLocal
from services.auth import authenticate


class LoginDialog(QDialog):
    """
    Diálogo de inicio de sesión con la MISMA UI que el LoginWindow previo,
    pero ahora valida usuario/contraseña contra la base de datos.

    - Campos:
        Usuario (texto)
        Código de acceso (password)
    - Botón: Entrar (CTA)
    - Hint: texto informativo
    - Acepta con Enter en cualquiera de los campos
    - Si las credenciales son válidas: self.user = {id, username, role, artist_id} y accept()
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("InkLink OS — Inicio de sesión")
        self.setMinimumSize(420, 280)
        self.setModal(True)

        self.user = None  # dict con {id, username, role, artist_id} si login OK

        # ---------- UI ----------
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(16)

        title = QLabel("Bienvenido a InkLink OS")
        title.setObjectName("H1")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        form = QVBoxLayout()
        form.setSpacing(10)

        lbl_user = QLabel("Usuario")
        self.in_user = QLineEdit()
        self.in_user.setPlaceholderText("Escribe tu usuario...")

        lbl_code = QLabel("Código de acceso")
        self.in_code = QLineEdit()
        self.in_code.setPlaceholderText("Escribe tu código...")
        self.in_code.setEchoMode(QLineEdit.Password)

        form.addWidget(lbl_user)
        form.addWidget(self.in_user)
        form.addWidget(lbl_code)
        form.addWidget(self.in_code)
        root.addLayout(form)

        # Botonera
        row = QHBoxLayout()
        row.addStretch(1)

        self.btn_login = QPushButton("Entrar")
        self.btn_login.setObjectName("CTA")
        self.btn_login.setMinimumHeight(36)
        self.btn_login.clicked.connect(self._do_login)

        row.addWidget(self.btn_login)
        root.addLayout(row)

        hint = QLabel("• Usa tus credenciales. Roles de ejemplo: admin/assistant/artist")
        hint.setAlignment(Qt.AlignCenter)
        hint.setObjectName("Hint")
        root.addWidget(hint)

        # UX: Enter para enviar
        self.in_user.returnPressed.connect(self.btn_login.click)
        self.in_code.returnPressed.connect(self.btn_login.click)

        self.in_user.setFocus()

    # ---------- Lógica ----------
    def _do_login(self):
        username = self.in_user.text().strip()
        password = self.in_code.text()

        if not username or not password:
            QMessageBox.information(self, "Login", "Escribe usuario y contraseña.")
            return

        try:
            with SessionLocal() as db:
                u = authenticate(db, username, password)
        except Exception as ex:
            QMessageBox.critical(self, "Login", f"Error al validar credenciales:\n{ex}")
            return

        if not u:
            QMessageBox.warning(self, "Login", "Credenciales inválidas o usuario inactivo.")
            return

        # OK
        self.user = u
        self.accept()
