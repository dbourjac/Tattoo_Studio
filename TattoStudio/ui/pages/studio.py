# ui/pages/studio.py
from pathlib import Path
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QSpacerItem, QSizePolicy
)

class StudioPage(QWidget):
    """
    Portada:
      - Logo central (centrado y grande, sin deformarse).
      - Título del estudio.
      - 4 CTAs justo debajo del título.
    """
    ir_nueva_cita    = pyqtSignal()
    ir_nuevo_cliente = pyqtSignal()
    ir_caja          = pyqtSignal()
    ir_portafolios   = pyqtSignal()

    def __init__(self, studio_name: str = "TattooStudio"):
        super().__init__()
        self.studio_name = studio_name

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(0)

        # Un poco de aire respecto a la topbar
        root.addSpacerItem(QSpacerItem(0, 12, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # --- LOGO CENTRAL ---
        self._hero_src = self._load_logo()          # pixmap original (si existe)
        self.logo_lbl = QLabel()
        self.logo_lbl.setObjectName("HeroLogo")
        self.logo_lbl.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.logo_lbl.setScaledContents(False)      # ¡no deformar!
        root.addWidget(self.logo_lbl, 0, Qt.AlignHCenter)   # <- centrado en el layout

        # --- TÍTULO ---
        title = QLabel(self.studio_name)
        title.setObjectName("H1")
        title.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        root.addSpacing(8)
        root.addWidget(title, 0, Qt.AlignHCenter)

        # --- CTAs debajo del título ---
        root.addSpacing(12)
        ctas = QVBoxLayout(); ctas.setSpacing(10)

        def cta(texto: str) -> QPushButton:
            b = QPushButton(texto)
            b.setObjectName("CTA")
            b.setMinimumWidth(320)
            b.setMinimumHeight(40)
            return b

        btn_cita = cta("Nueva cita")
        btn_cli  = cta("Nuevo cliente")
        btn_caja = cta("Caja rápida")
        btn_port = cta("Portafolios")

        for b in (btn_cita, btn_cli, btn_caja, btn_port):
            ctas.addWidget(b, 0, Qt.AlignHCenter)

        root.addLayout(ctas)
        root.addStretch(1)  # empuja un poco hacia arriba el bloque principal

        # Señales públicas
        btn_cita.clicked.connect(self.ir_nueva_cita.emit)
        btn_cli.clicked.connect(self.ir_nuevo_cliente.emit)
        btn_caja.clicked.connect(self.ir_caja.emit)
        btn_port.clicked.connect(self.ir_portafolios.emit)

        # primer pintado del logo
        self._update_logo_pix()

    # ---------- utilidades ----------
    def _load_logo(self) -> QPixmap:
        """Carga assets/logo.png si existe."""
        logo_path = Path(__file__).parents[2] / "assets" / "logo.png"
        return QPixmap(str(logo_path)) if logo_path.exists() else QPixmap()

    def _update_logo_pix(self) -> None:
        """
        Escala el logo respetando proporción.
        - Altura objetivo ≈ 28% del alto de la ventana.
        - Clamp entre 200 y 380 px para que siempre se vea “pro”.
        """
        if self._hero_src.isNull():
            self.logo_lbl.clear()
            self.logo_lbl.setFixedSize(0, 0)
            return

        h_total = max(0, self.height())
        target_h = int(h_total * 0.90)
        target_h = max(200, min(target_h, 380))   # <- más grande que antes

        ar = self._hero_src.width() / self._hero_src.height() if self._hero_src.height() else 1.0
        target_w = int(target_h * ar)

        scaled = self._hero_src.scaled(
            target_w, target_h,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        self.logo_lbl.setPixmap(scaled)
        # el QLabel adopta el tamaño del pixmap (no se estira)
        self.logo_lbl.setFixedSize(scaled.size())
        self.logo_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_logo_pix()
