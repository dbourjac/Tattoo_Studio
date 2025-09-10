# ui/main_window.py
from pathlib import Path
import json

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton,
    QFrame, QStatusBar, QStackedWidget, QSizePolicy
)

# Widgets y helpers propios
from ui.widgets.user_panel import PanelUsuario
from ui.styles.themes import apply_theme

# Páginas (import centralizado desde ui/pages/__init__.py)
from ui.pages import (
    StudioPage, NewClientPage, ClientsPage, ClientDetailPage,
    StaffPage, StaffDetailPage, ReportsPage, make_simple_page,
    InventoryDashboardPage, InventoryItemsPage,
    InventoryItemDetailPage, InventoryMovementsPage, AgendaPage
)

SETTINGS = Path(__file__).parents[1] / "settings.json"


def _save_theme(mode: str) -> None:
    """Guarda el modo de tema seleccionado en settings.json."""
    SETTINGS.write_text(json.dumps({"theme": mode}, indent=2), encoding="utf-8")


class MainWindow(QMainWindow):
    """Shell principal: topbar, stack de páginas, panel de usuario y tema."""
    solicitar_switch_user = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TattooStudio")
        self.setMinimumSize(1200, 720)

        # =========================
        #  Topbar (3 columnas)
        # =========================
        topbar = QFrame(); topbar.setObjectName("Topbar")
        tb = QHBoxLayout(topbar); tb.setContentsMargins(16, 12, 16, 12); tb.setSpacing(8)

        # IZQUIERDA: Brand + stretch (para centrar el bloque central)
        left = QWidget()
        left_lay = QHBoxLayout(left); left_lay.setContentsMargins(0, 0, 0, 0); left_lay.setSpacing(0)
        brand = QLabel("TattooStudio"); brand.setObjectName("Brand")
        left_lay.addWidget(brand); left_lay.addStretch(1)
        tb.addWidget(left, stretch=1)

        # CENTRO: Navegación (geométricamente centrada)
        nav_box = QWidget()
        nav = QHBoxLayout(nav_box); nav.setContentsMargins(0, 0, 0, 0); nav.setSpacing(8)

        # 👇 AQUI definimos TODOS los botones, incluido Inventario
        self.btn_studio     = self._pill("Estudio")
        self.btn_sched      = self._pill("Agenda")
        self.btn_clients    = self._pill("Clientes")
        self.btn_staff      = self._pill("Staff")
        self.btn_reports    = self._pill("Reportes")
        self.btn_inventory  = self._pill("Inventario")   # <<— EXISTE

        for b in (self.btn_studio, self.btn_sched, self.btn_clients,
                  self.btn_staff, self.btn_reports, self.btn_inventory):
            nav.addWidget(b)

        nav_box.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        tb.addWidget(nav_box, stretch=0, alignment=Qt.AlignCenter)

        # DERECHA: stretch + botón de usuario
        right = QWidget()
        right_lay = QHBoxLayout(right); right_lay.setContentsMargins(0, 0, 0, 0); right_lay.setSpacing(0)
        self.btn_user = QToolButton(); self.btn_user.setObjectName("UserButton")
        self.btn_user.setText("Dylan Bourjac")
        self.btn_user.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_user.setCheckable(True)
        self.btn_user.toggled.connect(self._toggle_user_panel)
        right_lay.addStretch(1); right_lay.addWidget(self.btn_user)
        tb.addWidget(right, stretch=1)

        # Panel de usuario y tema
        self.user_panel = PanelUsuario(self)
        self.user_panel.cambiar_usuario.connect(self.solicitar_switch_user.emit)
        self.user_panel.cambiar_tema.connect(self._on_toggle_theme)

        # =========================
        #  Stack de páginas
        # =========================
        self.stack = QStackedWidget()

        # Portada (Estudio)
        self.studio_page = StudioPage()
        self.stack.addWidget(self.studio_page)              # índice 0

        self.agenda_page = AgendaPage()
        self.idx_agenda  = self.stack.addWidget(self.agenda_page)

        # Clientes
        self.clients_page     = ClientsPage()
        self.idx_clientes     = self.stack.addWidget(self.clients_page)

        self.client_detail    = ClientDetailPage()
        self.idx_cliente_det  = self.stack.addWidget(self.client_detail)

        # Staff (real)
        self.staff_page       = StaffPage()
        self.idx_staff        = self.stack.addWidget(self.staff_page)

        self.staff_detail     = StaffDetailPage()
        self.idx_staff_det    = self.stack.addWidget(self.staff_detail)

        self.idx_staff_new    = self.stack.addWidget(make_simple_page("Nuevo staff"))

        # Reportes (real)
        self.reports_page     = ReportsPage()
        self.idx_reportes     = self.stack.addWidget(self.reports_page)

        # Otros CTAs de portada como placeholders
        self.idx_portafolios  = self.stack.addWidget(make_simple_page("Portafolios"))
        self.idx_fila         = self.stack.addWidget(make_simple_page("Fila"))

        # Nuevo cliente (real)
        self.idx_nuevo_cliente = self.stack.addWidget(NewClientPage())

        # Inventario (real)
        self.inventory_dash   = InventoryDashboardPage()
        self.idx_inventory    = self.stack.addWidget(self.inventory_dash)

        self.inventory_items  = InventoryItemsPage()
        self.idx_inv_items    = self.stack.addWidget(self.inventory_items)

        self.inventory_detail = InventoryItemDetailPage()
        self.idx_inv_detail   = self.stack.addWidget(self.inventory_detail)

        self.inventory_moves  = InventoryMovementsPage()
        self.idx_inv_moves    = self.stack.addWidget(self.inventory_moves)

        # Placeholders para formularios de inventario
        self.idx_inv_new_item = self.stack.addWidget(make_simple_page("Nuevo ítem (placeholder)"))
        self.idx_inv_entry    = self.stack.addWidget(make_simple_page("Nueva entrada (placeholder)"))
        self.idx_inv_adjust   = self.stack.addWidget(make_simple_page("Ajuste de inventario (placeholder)"))

        # ===== Navegaciones internas =====
        # Portada
        self.studio_page.ir_nuevo_cliente.connect(lambda: self._ir(self.idx_nuevo_cliente))
        self.studio_page.ir_cliente_recurrente.connect(lambda: self._ir(self.idx_clientes))
        self.studio_page.ir_portafolios.connect(lambda: self._ir(self.idx_portafolios))
        self.studio_page.ir_fila.connect(lambda: self._ir(self.idx_fila))

        # Clientes
        self.clients_page.crear_cliente.connect(lambda: self._ir(self.idx_nuevo_cliente))
        self.clients_page.abrir_cliente.connect(self._open_client_detail)

        # Staff
        self.staff_page.agregar_staff.connect(lambda: self._ir(self.idx_staff_new))

        def _open_staff_detail(s):
            self.staff_detail.load_staff(s)
            self._ir(self.idx_staff_det)
        self.staff_page.abrir_staff.connect(_open_staff_detail)

        def _open_staff_portfolio(s):
            self.staff_detail.load_staff(s)
            self.staff_detail.go_to_portfolio()
            self._ir(self.idx_staff_det)
        self.staff_page.abrir_portafolio.connect(_open_staff_portfolio)

        # Inventario – wiring rápido entre páginas
        self.inventory_dash.ir_items        = lambda: self._ir(self.idx_inv_items)
        self.inventory_dash.ir_movimientos  = lambda: self._ir(self.idx_inv_moves)
        self.inventory_dash.nuevo_item      = lambda: self._ir(self.idx_inv_new_item)

        self.inventory_items.abrir_item     = lambda it: (self.inventory_detail.load_item(it),
                                                          self._ir(self.idx_inv_detail))
        self.inventory_items.nuevo_item     = lambda: self._ir(self.idx_inv_new_item)
        self.inventory_items.nueva_entrada  = lambda it=None: self._ir(self.idx_inv_entry)
        self.inventory_items.nuevo_ajuste   = lambda it=None: self._ir(self.idx_inv_adjust)

        self.inventory_moves.nueva_entrada  = lambda: self._ir(self.idx_inv_entry)
        self.inventory_moves.nueva_salida   = lambda: self._ir(self.idx_inv_adjust)
        self.inventory_moves.nuevo_ajuste   = lambda: self._ir(self.idx_inv_adjust)

        # =========================
        #  Conexiones de navegación (topbar)
        # =========================
        self.btn_studio.clicked.connect(lambda: self._ir(0))
        self.btn_sched.clicked.connect(lambda: self._ir(self.idx_agenda))
        self.btn_clients.clicked.connect(lambda: self._ir(self.idx_clientes))
        self.btn_staff.clicked.connect(lambda: self._ir(self.idx_staff))
        self.btn_reports.clicked.connect(lambda: self._ir(self.idx_reportes))
        self.btn_inventory.clicked.connect(lambda: self._ir(self.idx_inventory))
        self.agenda_page.crear_cita.connect(lambda: self._ir(self.idx_nuevo_cliente))
        self.btn_studio.setChecked(True)

        # Status bar
        status = QStatusBar(); self.setStatusBar(status)
        status.showMessage("Ver. 0.0.1 | Último respaldo —")

        # Layout raíz
        root = QWidget()
        rl = QVBoxLayout(root); rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(topbar); rl.addWidget(self.stack, stretch=1)
        self.setCentralWidget(root)

        # Sincroniza el check de tema
        try:
            mode = json.loads(SETTINGS.read_text(encoding="utf-8")).get("theme", "light")
            self.user_panel.chk_dark.setChecked(mode == "dark")
        except Exception:
            pass

    # ===== Callbacks / helpers =====
    def _open_client_detail(self, client: dict) -> None:
        """Abre la ficha de cliente con los datos emitidos desde ClientsPage."""
        self.client_detail.load_client(client)
        self._ir(self.idx_cliente_det)

    def _on_toggle_theme(self, is_dark: bool) -> None:
        """Aplica el tema y lo persiste en settings.json."""
        mode = "dark" if is_dark else "light"
        apply_theme(self.app(), mode); _save_theme(mode)

    def app(self):
        """Devuelve la instancia global de QApplication."""
        from PyQt5.QtWidgets import QApplication
        return QApplication.instance()

    # --------- utilidades de UI ----------
    def _pill(self, text) -> QToolButton:
        b = QToolButton(); b.setText(text); b.setCheckable(True); b.setObjectName("PillNav")
        return b

    def _ir(self, idx: int) -> None:
        """
        Cambia de página en el stack y marca/desmarca el botón de la topbar.
        """
        mapping = {
            0: self.btn_studio,
            self.idx_agenda: self.btn_sched,
            self.idx_clientes: self.btn_clients,
            self.idx_staff: self.btn_staff,
            self.idx_reportes: self.btn_reports,
            self.idx_inventory: self.btn_inventory,  # ← ya no rompe
        }

        # Desmarcar todas
        for btn in (self.btn_studio, self.btn_sched, self.btn_clients,
                    self.btn_staff, self.btn_reports, self.btn_inventory):
            btn.setChecked(False)

        # Marcar la correspondiente (si existe mapeo)
        if idx in mapping:
            mapping[idx].setChecked(True)

        self.stack.setCurrentIndex(idx)

    def _toggle_user_panel(self, checked: bool) -> None:
        """Muestra/oculta el panel de usuario, alineado al borde derecho del botón."""
        if checked:
            self.user_panel.adjustSize()
            btn = self.btn_user
            global_pos = btn.mapToGlobal(btn.rect().bottomRight())
            panel_w = self.user_panel.width()
            self.user_panel.move(global_pos.x() - panel_w, global_pos.y())
            self.user_panel.show()
        else:
            self.user_panel.hide()
