# ui/pages/client_detail.py
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QTextEdit, QListWidget
)

class ClientDetailPage(QWidget):
    """
    Ficha de cliente (placeholder con tabs):
    Perfil | Citas | Archivos/Fotos | Formularios | Notas
    Método: load_client(dict) para actualizar el encabezado.
    """
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        self.title = QLabel("Ficha de cliente")
        self.title.setObjectName("H1")
        root.addWidget(self.title)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, stretch=1)

        # Tabs (vacías por ahora)
        self.tab_perfil = QWidget(); self._mk_placeholder(self.tab_perfil, "Datos del perfil (placeholder)")
        self.tab_citas = QWidget(); self._mk_list(self.tab_citas, ["(Ejemplo) 10 Sep 12:00 con Dylan", "(Ejemplo) 09 Sep 17:30 con Dylan"])
        self.tab_files = QWidget(); self._mk_placeholder(self.tab_files, "Galería/Archivos (placeholder)")
        self.tab_forms = QWidget(); self._mk_placeholder(self.tab_forms, "Formularios asignados/firmados (placeholder)")
        self.tab_notas = QWidget(); self._mk_text(self.tab_notas, "Notas internas (placeholder)")

        self.tabs.addTab(self.tab_perfil, "Perfil")
        self.tabs.addTab(self.tab_citas, "Citas")
        self.tabs.addTab(self.tab_files, "Archivos/Fotos")
        self.tabs.addTab(self.tab_forms, "Formularios")
        self.tabs.addTab(self.tab_notas, "Notas")

        self._client = None

    def load_client(self, client: dict):
        """Recibe el dict emitido desde ClientsPage y actualiza el título."""
        self._client = client
        self.title.setText(f'Cliente: {client.get("nombre", "")}')

    # --- helpers de placeholder ---
    def _mk_placeholder(self, w: QWidget, text: str):
        lay = QVBoxLayout(w); lay.addWidget(QLabel(text), alignment=Qt.AlignTop)

    def _mk_text(self, w: QWidget, text: str):
        lay = QVBoxLayout(w); te = QTextEdit(); te.setPlainText(text); lay.addWidget(te)

    def _mk_list(self, w: QWidget, items):
        lay = QVBoxLayout(w); lst = QListWidget(); lst.addItems(items); lay.addWidget(lst)
