from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel


def make_simple_page(nombre: str) -> QWidget:
    """
    Crea una página placeholder con un título centrado.
    Útil mientras no implementamos la lógica real.
    """
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(40, 40, 40, 40)
    title = QLabel(nombre)
    title.setObjectName("H1")
    lay.addWidget(title, alignment=Qt.AlignCenter)
    return w
