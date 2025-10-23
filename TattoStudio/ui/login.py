# ui/login.py

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QIcon, QColor, QPixmap, QPainter, QPainterPath
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout,
    QMessageBox, QFrame, QGraphicsDropShadowEffect, QToolButton
)

from data.db.session import SessionLocal
from services.auth import authenticate


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        # ---- Ventana: toplevel + modal app + FRAMELESS (tipo popup)
        self.setWindowTitle("InkLink OS — Inicio de sesión")
        self.setMinimumSize(640, 420)                 # más ancha
        self.setParent(None)                          # toplevel (entrada propia si SO lo muestra)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.setAttribute(Qt.WA_TranslucentBackground, True)  # sin fondo: solo la card visible

        # Icono (si existe)
        try:
            self.setWindowIcon(QIcon("assets/logo.png"))
        except Exception:
            pass

        self.user = None  # (no tocamos la lógica)
        self._drag_pos = None  # para arrastrar la ventana

        # ---------- UI ----------
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(16)

        # Card principal (lo único visible)
        self.card = QFrame(self)
        self.card.setObjectName("AuthCard")
        self.card.setMinimumWidth(560)  # ancho cómodo de la card
        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(28, 28, 28, 24)
        card_lay.setSpacing(16)

        # Sombra sutil
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.card.setGraphicsEffect(shadow)

        # Centro vertical
        root.addStretch(1)
        root.addWidget(self.card, 0, Qt.AlignHCenter)
        root.addStretch(1)

        # --- Barra superior (drag area + botón cerrar)
        topbar = QHBoxLayout()
        topbar.setContentsMargins(0, 0, 0, 0)
        topbar.setSpacing(0)

        drag_label = QLabel("")          # superficie “vacía” para arrastrar
        drag_label.setObjectName("DragArea")
        drag_label.setMinimumHeight(6)

        btn_close = QToolButton(self.card)
        btn_close.setObjectName("CloseBtn")
        btn_close.setText("✕")
        btn_close.setToolTip("Cerrar")
        btn_close.clicked.connect(self.reject)  # solo visual; no toca lógica

        topbar.addWidget(drag_label, 1)
        topbar.addWidget(btn_close, 0, Qt.AlignRight)
        card_lay.addLayout(topbar)

        # --- Encabezado de marca: círculo = logo
        header = QVBoxLayout()
        header.setSpacing(8)
        header.setAlignment(Qt.AlignHCenter)
        header.setContentsMargins(0, -8, 0, 0)

        logo = QLabel(self.card)
        logo.setObjectName("BrandLogo")
        logo.setAlignment(Qt.AlignCenter)
        # el círculo ES el logo (recortado a círculo para consistencia)
        pm = QPixmap("assets/logo.png")
        if not pm.isNull():
            logo.setPixmap(self._circle_pixmap(pm, 360))
        else:
            # Fallback si no hay logo
            logo.setText("IL")
            logo.setStyleSheet("font-weight:800; color:#EAF0FF;")

        brand = QLabel("InkLink OS")
        brand.setObjectName("BrandTitle")
        brand.setAlignment(Qt.AlignCenter)

        header.addWidget(logo, 0, Qt.AlignHCenter)
        header.addWidget(brand)
        card_lay.addLayout(header)

        # --- Formulario
        form = QVBoxLayout()
        form.setSpacing(10)

        lbl_user = QLabel("Usuario")
        lbl_user.setObjectName("FieldLabel")
        self.in_user = QLineEdit()
        self.in_user.setPlaceholderText("Escribe tu usuario…")

        lbl_code = QLabel("Código de acceso")
        lbl_code.setObjectName("FieldLabel")
        self.in_code = QLineEdit()
        self.in_code.setPlaceholderText("Escribe tu código…")
        self.in_code.setEchoMode(QLineEdit.Password)

        form.addWidget(lbl_user)
        form.addWidget(self.in_user)
        form.addWidget(lbl_code)
        form.addWidget(self.in_code)
        card_lay.addLayout(form)

        # --- Botón centrado
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_login = QPushButton("Entrar")
        self.btn_login.setObjectName("CTA")
        self.btn_login.setMinimumHeight(44)
        self.btn_login.clicked.connect(self._do_login)
        row.addWidget(self.btn_login)
        row.addStretch(1)
        card_lay.addLayout(row)

        # (Se removieron el caption y el hint, como pediste)

        # UX: Enter para enviar
        self.in_user.returnPressed.connect(self.btn_login.click)
        self.in_code.returnPressed.connect(self.btn_login.click)

        # Estilos + centro en pantalla
        self._apply_styles()
        self._center_on_screen()

        self.in_user.setFocus()

    # ---------- Lógica (SIN cambios) ----------
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

        self.user = u
        self.accept()

    # ---------- Estilos (solo visual) ----------
    def _apply_styles(self):
        # Ventana sin fondo (transparente). La card define el color.
        self.setStyleSheet("""
        QDialog { background: transparent; }

        /* Card principal */
        #AuthCard {
            background: rgba(18, 22, 28, 0.96);
            border: 1px solid rgba(167, 199, 255, 0.16);
            border-radius: 20px;
        }

        /* Barra superior */
        QLabel#DragArea { background: transparent; }
        QToolButton#CloseBtn {
            background: transparent;
            color: rgba(234,240,255,.85);
            border: none;
            font-size: 14px;
            padding: 2px 6px;
            border-radius: 6px;
        }
        QToolButton#CloseBtn:hover {
            background: rgba(255,255,255,.08);
        }
        QToolButton#CloseBtn:pressed {
            background: rgba(255,255,255,.06);
        }

        /* Marca */
        QLabel#BrandLogo { background: transparent; }
        QLabel#BrandTitle {
            font-size: 44px;          /* antes 18px */
            font-weight: 800; 
            color: #EAF0FF; 
            letter-spacing: .3px;
            background: transparent;  /* elimina cualquier rectángulo de fondo */
            padding: 0;               /* evita “cajitas” por padding del estilo base */
        }

        /* Labels de campos */
        QLabel#FieldLabel {
            color: rgba(234,240,255,.85);
            margin-top: 4px; margin-bottom: 2px;
            background: transparent;
        }

        /* Inputs */
        QLineEdit {
            min-height: 46px;
            border-radius: 12px;
            padding: 10px 12px;
            color: #EAF0FF;
            background: rgba(255,255,255,.04);
            border: 1px solid rgba(167,199,255,.18);
            selection-background-color: rgba(167,199,255,.35);
        }
        QLineEdit::placeholder {
            color: rgba(234,240,255,.45);
        }
        QLineEdit:focus {
            border: 1px solid rgba(167,199,255,.55);
            background: rgba(255,255,255,.06);
        }

        /* Botón CTA */
        QPushButton#CTA {
            min-width: 200px;
            border-radius: 12px;
            padding: 12px 18px;
            font-weight: 800;
            color: #0E1217;
            background: #A7C7FF;
            border: 1px solid rgba(167,199,255,.32);
            letter-spacing: .2px;
        }
        QPushButton#CTA:hover { background: #B4CFFF; }
        QPushButton#CTA:pressed { background: #9FBEFC; }
        """)

    def _center_on_screen(self):
        # Centrar la ventana en la pantalla principal
        try:
            screen = self.screen().availableGeometry()
        except Exception:
            from PyQt5.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
        geom = self.frameGeometry()
        geom.moveCenter(screen.center())
        self.move(geom.topLeft())
    
    def showEvent(self, event):
        super().showEvent(event)
        # Recentrar cuando la ventana YA está calculada y visible
        self._center_on_screen()

    # ---------- Util: hacer circular el logo ----------
    def _circle_pixmap(self, pm: QPixmap, diameter: int) -> QPixmap:
        """Devuelve el QPixmap recortado en un círculo del tamaño indicado."""
        if pm.isNull():
            return pm
        pm_scaled = pm.scaled(diameter, diameter, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        result = QPixmap(diameter, diameter)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, diameter, diameter)
        painter.setClipPath(path)
        # centrar la imagen escalada dentro del círculo
        x = (diameter - pm_scaled.width()) // 2
        y = (diameter - pm_scaled.height()) // 2
        painter.drawPixmap(x, y, pm_scaled)
        painter.end()
        return result

    # ---------- Drag para ventana frameless ----------
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
