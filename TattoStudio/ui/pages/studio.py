from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QSpacerItem, QSizePolicy
)


class StudioPage(QWidget):
    """
    Portada con los CTAs principales del flujo:
    - Nuevo cliente (abre formulario)
    - Cliente recurrente (va a Clientes)
    - Portafolios
    - Fila (Queue)
    """
    ir_nuevo_cliente = pyqtSignal()
    ir_cliente_recurrente = pyqtSignal()
    ir_portafolios = pyqtSignal()
    ir_fila = pyqtSignal()

    def __init__(self):
        super().__init__()

        root = QHBoxLayout(self)
        root.setContentsMargins(40, 20, 40, 20)
        root.setSpacing(24)

        # Spacer izquierdo (centrado flexible)
        root.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Columna central (logo/título/CTAs)
        col = QVBoxLayout()
        col.setSpacing(16)
        col.setAlignment(Qt.AlignHCenter)

        logo = QLabel()                 # (más adelante puedes setPixmap)
        logo.setFixedSize(160, 160)
        logo.setObjectName("Logo")
        col.addWidget(logo, alignment=Qt.AlignHCenter)

        title = QLabel("TattooStudio")
        title.setObjectName("H1")
        col.addWidget(title, alignment=Qt.AlignHCenter)

        ctas = QVBoxLayout(); ctas.setSpacing(10)

        btn_new = QPushButton("Nuevo cliente"); btn_new.setObjectName("CTA")
        btn_new.setMinimumWidth(320); btn_new.setMinimumHeight(36)
        btn_new.clicked.connect(self.ir_nuevo_cliente.emit)

        btn_return = QPushButton("Cliente recurrente"); btn_return.setObjectName("CTA")
        btn_return.setMinimumWidth(320); btn_return.setMinimumHeight(36)
        btn_return.clicked.connect(self.ir_cliente_recurrente.emit)

        btn_port = QPushButton("Portafolios"); btn_port.setObjectName("CTA")
        btn_port.setMinimumWidth(320); btn_port.setMinimumHeight(36)
        btn_port.clicked.connect(self.ir_portafolios.emit)

        btn_queue = QPushButton("Fila"); btn_queue.setObjectName("CTA")
        btn_queue.setMinimumWidth(320); btn_queue.setMinimumHeight(36)
        btn_queue.clicked.connect(self.ir_fila.emit)

        for b in (btn_new, btn_return, btn_port, btn_queue):
            ctas.addWidget(b)

        col.addLayout(ctas)
        root.addLayout(col, stretch=2)

        # Spacer derecho
        root.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
