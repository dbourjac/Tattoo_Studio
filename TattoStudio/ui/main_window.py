from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton,
    QFrame, QStatusBar, QStackedWidget, QSizePolicy
)

# Importamos páginas y widgets de nuestra UI
from ui.widgets.user_panel import PanelUsuario
from ui.pages.studio import StudioPage
from ui.pages.new_client import NewClientPage
from ui.pages.common import make_simple_page
from ui.styles.themes import apply_theme
from pathlib import Path
import json

SETTINGS = Path(__file__).parents[1] / "settings.json"


def _save_theme(mode: str):
    SETTINGS.write_text(json.dumps({"theme": mode}, indent=2), encoding="utf-8")


class MainWindow(QMainWindow):
    """
    Ventana principal:
    - Topbar con marca (izq), navegación centrada y botón de usuario (der).
    - QStackedWidget con todas las páginas (placeholders + Nuevo Cliente real).
    """
    solicitar_switch_user = pyqtSignal()  # para volver al login

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TattooStudio")
        self.setMinimumSize(1200, 720)

        # --- Topbar ---
        topbar = QFrame()
        topbar.setObjectName("Topbar")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(16, 12, 16, 12)
        tb.setSpacing(8)

        # ===== Columna IZQUIERDA (brand + stretch) =====
        left = QWidget()
        left_lay = QHBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(0)

        brand = QLabel("TattooStudio")
        brand.setObjectName("Brand")
        left_lay.addWidget(brand)
        left_lay.addStretch(1)
        tb.addWidget(left, stretch=1)   # esta columna se expande

        # ===== Columna CENTRAL (navegación) =====
        nav_box = QWidget()
        nav = QHBoxLayout(nav_box)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(8)

        self.btn_studio  = self._pill("Estudio")
        self.btn_sched   = self._pill("Agenda")
        self.btn_clients = self._pill("Clientes")
        self.btn_staff   = self._pill("Personal")
        self.btn_reports = self._pill("Reportes")
        self.btn_forms   = self._pill("Formularios")

        for b in (self.btn_studio, self.btn_sched, self.btn_clients,
                  self.btn_staff, self.btn_reports, self.btn_forms):
            nav.addWidget(b)

        # el centro mide lo que ocupa (no se estira), así queda geométricamente centrado
        nav_box.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        tb.addWidget(nav_box, stretch=0, alignment=Qt.AlignCenter)

        # ===== Columna DERECHA (stretch + botón usuario) =====
        right = QWidget()
        right_lay = QHBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        self.btn_user = QToolButton()
        self.btn_user.setObjectName("UserButton")
        self.btn_user.setText("Dylan Bourjac")
        self.btn_user.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_user.setCheckable(True)
        self.btn_user.toggled.connect(self._toggle_user_panel)

        right_lay.addStretch(1)
        right_lay.addWidget(self.btn_user)
        tb.addWidget(right, stretch=1)  # esta columna también se expande

        # --- Panel del usuario (popup) ---
        self.user_panel = PanelUsuario(self)
        self.user_panel.cambiar_usuario.connect(self.solicitar_switch_user.emit)

        # --- Stack de páginas ---
        self.stack = QStackedWidget()

        self.studio_page = StudioPage()
        # Navegaciones desde portada
        self.studio_page.ir_nuevo_cliente.connect(lambda: self._ir(self.idx_nuevo_cliente))
        self.studio_page.ir_cliente_recurrente.connect(lambda: self._ir(self.idx_clientes))
        self.studio_page.ir_portafolios.connect(lambda: self._ir(self.idx_portafolios))
        self.studio_page.ir_fila.connect(lambda: self._ir(self.idx_fila))

        self.stack.addWidget(self.studio_page)                        # 0 Estudio
        self.idx_agenda        = self.stack.addWidget(make_simple_page("Agenda"))
        self.idx_clientes      = self.stack.addWidget(make_simple_page("Clientes"))
        self.idx_personal      = self.stack.addWidget(make_simple_page("Personal"))
        self.idx_reportes      = self.stack.addWidget(make_simple_page("Reportes"))
        self.idx_forms         = self.stack.addWidget(make_simple_page("Formularios"))
        self.idx_portafolios   = self.stack.addWidget(make_simple_page("Portafolios"))  # CTA
        self.idx_fila          = self.stack.addWidget(make_simple_page("Fila"))         # CTA
        self.idx_nuevo_cliente = self.stack.addWidget(NewClientPage())                  # NUEVO

        # Conexiones de navegación (topbar)
        self.btn_studio.clicked.connect(lambda: self._ir(0))
        self.btn_sched.clicked.connect(lambda: self._ir(self.idx_agenda))
        self.btn_clients.clicked.connect(lambda: self._ir(self.idx_clientes))
        self.btn_staff.clicked.connect(lambda: self._ir(self.idx_personal))
        self.btn_reports.clicked.connect(lambda: self._ir(self.idx_reportes))
        self.btn_forms.clicked.connect(lambda: self._ir(self.idx_forms))
        self.btn_studio.setChecked(True)

        # Status bar
        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Ver. 0.0.1 | Último respaldo —")

        # Layout raíz
        root = QWidget()
        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(topbar)
        rl.addWidget(self.stack, stretch=1)
        self.setCentralWidget(root)

        # Toggle de tema desde el panel de usuario
        self.user_panel.cambiar_tema.connect(self._on_toggle_theme)
        # Sincronizar el check con la preferencia guardada
        try:
            mode = json.loads(SETTINGS.read_text(encoding="utf-8")).get("theme", "light")
            self.user_panel.chk_dark.setChecked(mode == "dark")
        except Exception:
            pass

    def _on_toggle_theme(self, is_dark: bool):
        mode = "dark" if is_dark else "light"
        apply_theme(self.app(), mode)
        _save_theme(mode)

    def app(self):
        # helper para acceder al QApplication actual
        from PyQt5.QtWidgets import QApplication
        return QApplication.instance()

    # ---- helpers ----
    def _pill(self, text) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setCheckable(True)
        b.setObjectName("PillNav")
        return b

    def _ir(self, idx: int):
        """
        Cambia de página en el stack y marca el botón de navegación correspondiente.
        (Las páginas que no están en la topbar —como 'Nuevo cliente'— no necesitan mapeo.)
        """
        mapping = {
            0: self.btn_studio,
            self.idx_agenda: self.btn_sched,
            self.idx_clientes: self.btn_clients,
            self.idx_personal: self.btn_staff,
            self.idx_reportes: self.btn_reports,
            self.idx_forms: self.btn_forms,
        }
        for btn in (self.btn_studio, self.btn_sched, self.btn_clients,
                    self.btn_staff, self.btn_reports, self.btn_forms):
            btn.setChecked(False)
        if idx in mapping:
            mapping[idx].setChecked(True)
        self.stack.setCurrentIndex(idx)

    def _toggle_user_panel(self, checked: bool):
        """Muestra/oculta el panel del usuario, alineado al borde derecho del botón."""
        if checked:
            self.user_panel.adjustSize()
            btn = self.btn_user
            global_pos = btn.mapToGlobal(btn.rect().bottomRight())
            panel_w = self.user_panel.width()
            self.user_panel.move(global_pos.x() - panel_w, global_pos.y())
            self.user_panel.show()
        else:
            self.user_panel.hide()

    def mousePressEvent(self, event):
        """Si haces clic fuera del panel de usuario, se cierra y desmarca el botón."""
        if self.user_panel.isVisible() and not self.user_panel.geometry().contains(event.globalPos()):
            self.user_panel.hide()
            self.btn_user.setChecked(False)
        super().mousePressEvent(event)
