from pathlib import Path
import json

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton,
    QFrame, QStatusBar, QStackedWidget, QSizePolicy, QDialog, QPushButton
)

from ui.widgets.user_panel import PanelUsuario
from ui.styles.themes import apply_theme

from services.contracts import set_current_user, get_current_user
from ui.login import LoginDialog

from ui.pages import (
    StudioPage, NewClientPage, ClientsPage, ClientDetailPage,
    StaffPage, StaffDetailPage, ReportsPage, make_simple_page,
    InventoryDashboardPage, InventoryItemsPage, InventoryItemDetailPage, InventoryMovementsPage,
    AgendaPage
)

from ui.pages.cash_register import CashRegisterDialog

SETTINGS = Path(__file__).parents[1] / "settings.json"

def _save_theme(mode: str) -> None:
    SETTINGS.write_text(json.dumps({"theme": mode}, indent=2), encoding="utf-8")


class MainWindow(QMainWindow):
    solicitar_switch_user = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TattooStudio")
        self.setMinimumSize(1200, 720)

        self._build_ui()
        self._login_and_apply_user()

    # =========================
    # INTERFAZ
    # =========================
    def _build_ui(self):
        # Topbar
        topbar = QFrame()
        topbar.setObjectName("Topbar")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(16, 12, 16, 12)
        tb.setSpacing(8)

        # IZQUIERDA
        left = QWidget()
        left_lay = QHBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(8)

        self.brand_logo = QLabel()
        self.brand_logo.setObjectName("BrandLogo")
        self._set_brand_logo(28)

        brand = QLabel("TattooStudio")
        brand.setObjectName("Brand")

        left_lay.addWidget(self.brand_logo, 0, Qt.AlignVCenter)
        left_lay.addWidget(brand, 0, Qt.AlignVCenter)
        left_lay.addStretch(1)
        tb.addWidget(left, stretch=1)

        # CENTRO
        nav_box = QWidget()
        nav = QHBoxLayout(nav_box)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(8)

        self.btn_studio  = self._pill("Estudio")
        self.btn_sched   = self._pill("Agenda")
        self.btn_clients = self._pill("Clientes")
        self.btn_staff   = self._pill("Staff")
        self.btn_reports = self._pill("Reportes")
        self.btn_forms   = self._pill("Inventario")

        for b in (self.btn_studio, self.btn_sched, self.btn_clients,
                  self.btn_staff, self.btn_reports, self.btn_forms):
            nav.addWidget(b)

        nav_box.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        tb.addWidget(nav_box, stretch=0, alignment=Qt.AlignCenter)

        # DERECHA
        right = QWidget()
        right_lay = QHBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        self.btn_user = QToolButton()
        self.btn_user.setObjectName("UserButton")
        self.btn_user.setText("Usuario")
        self.btn_user.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_user.setCheckable(True)
        self.btn_user.toggled.connect(self._toggle_user_panel)

        right_lay.addStretch(1)
        right_lay.addWidget(self.btn_user)
        tb.addWidget(right, stretch=1)

        # Panel usuario
        self.user_panel = PanelUsuario(self)
        self.user_panel.cambiar_usuario.connect(self.solicitar_switch_user.emit)
        self.user_panel.cambiar_tema.connect(self._on_toggle_theme)
        self.solicitar_switch_user.connect(self._switch_user)

        # =========================
        # Stack de páginas
        # =========================
        self.stack = QStackedWidget()

        self.studio_page = StudioPage(studio_name="TattooStudio")
        self.stack.addWidget(self.studio_page)

        self.agenda_page = AgendaPage()
        self.idx_agenda = self.stack.addWidget(self.agenda_page)

        self.clients_page = ClientsPage()
        self.idx_clientes = self.stack.addWidget(self.clients_page)
        self.client_detail = ClientDetailPage()
        self.idx_cliente_det = self.stack.addWidget(self.client_detail)
        self.client_detail.back_to_list.connect(self._show_clients_and_refresh)
        self.client_detail.cliente_cambiado.connect(self._refresh_clients_table)

        self.staff_page = StaffPage()
        self.idx_staff = self.stack.addWidget(self.staff_page)
        self.staff_detail = StaffDetailPage()
        self.idx_staff_det = self.stack.addWidget(self.staff_detail)
        self.idx_staff_new = self.stack.addWidget(make_simple_page("Nuevo staff"))
        self.staff_page.agregar_staff.connect(self._open_staff_create)
        self.staff_page.abrir_staff.connect(self._open_staff_detail)
        self.staff_detail.back_requested.connect(self._back_to_staff_list)
        self.staff_detail.staff_saved.connect(self._refresh_staff_list)

        self.reports_page = ReportsPage()
        self.idx_reportes = self.stack.addWidget(self.reports_page)

        self.inventory_dash   = InventoryDashboardPage()
        self.idx_inventory    = self.stack.addWidget(self.inventory_dash)
        self.inventory_items  = InventoryItemsPage()
        self.idx_inv_items    = self.stack.addWidget(self.inventory_items)
        self.inventory_detail = InventoryItemDetailPage()
        self.idx_inv_detail   = self.stack.addWidget(self.inventory_detail)
        self.inventory_moves  = InventoryMovementsPage()
        self.idx_inv_moves    = self.stack.addWidget(self.inventory_moves)
        self.idx_inv_new_item = self.stack.addWidget(make_simple_page("Nuevo ítem"))
        self.idx_inv_entry    = self.stack.addWidget(make_simple_page("Nueva entrada"))
        self.idx_inv_adjust   = self.stack.addWidget(make_simple_page("Ajuste de inventario"))

        self.new_client_page = NewClientPage()
        self.idx_nuevo_cliente = self.stack.addWidget(self.new_client_page)
        self.new_client_page.volver_atras.connect(lambda: self._ir(self.idx_clientes))

        # Conectar botones portada
        self.studio_page.ir_nueva_cita.connect(lambda: self._ir(self.idx_agenda))
        self.studio_page.ir_nuevo_cliente.connect(self._abrir_nuevo_cliente_popup)
        self.studio_page.ir_caja.connect(self._abrir_caja_popup)
        self.studio_page.ir_portafolios.connect(lambda: self._ir(self._ensure_portfolios_page()))

        self.clients_page.crear_cliente.connect(self._abrir_nuevo_cliente_popup)
        self.clients_page.abrir_cliente.connect(self._open_client_detail)

        # Topbar navegación
        self.btn_studio.clicked.connect(lambda: self._ir(0))
        self.btn_sched.clicked.connect(lambda: self._ir(self.idx_agenda))
        self.btn_clients.clicked.connect(lambda: self._ir(self.idx_clientes))
        self.btn_staff.clicked.connect(lambda: self._ir(self.idx_staff))
        self.btn_reports.clicked.connect(lambda: self._ir(self.idx_reportes))
        self.btn_forms.clicked.connect(lambda: self._ir(self.idx_inventory))
        self.btn_studio.setChecked(True)

        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Ver. 0.1.6 | Último respaldo —")

        root = QWidget()
        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(topbar)
        rl.addWidget(self.stack, stretch=1)
        self.setCentralWidget(root)

        try:
            mode = json.loads(SETTINGS.read_text(encoding="utf-8")).get("theme", "light")
            self.user_panel.chk_dark.setChecked(mode == "dark")
        except Exception:
            pass

    # =========================
    # LOGIN
    # =========================
    def _login_and_apply_user(self):
        dlg = LoginDialog(self)
        if dlg.exec_() != QDialog.Accepted or not dlg.user:
            self.close()
            return
        set_current_user(dlg.user)
        try:
            self.btn_user.setText(f"{dlg.user.get('username', 'Usuario')} ({dlg.user.get('role', '-')})")
        except Exception:
            self.btn_user.setText("Usuario")
        self._apply_role_gates()
        if not self._is_allowed_index(self.stack.currentIndex()):
            self._ir(0)

    # =========================
    # MÉTODOS DE NAVEGACIÓN
    # =========================
    def _ir(self, idx: int):
        self.stack.setCurrentIndex(idx)

    def _pill(self, text: str) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setCheckable(True)
        return btn

    # =========================
    # MÉTODOS DE CAJA
    # =========================
    def _abrir_caja_popup(self):
        dlg = CashRegisterDialog(self)
        dlg.exec_()

    # =========================
    # MÉTODOS PANEL USUARIO / TEMA
    # =========================
    def _toggle_user_panel(self, checked: bool):
        self.user_panel.setVisible(checked)

    def _on_toggle_theme(self, dark: bool):
        mode = "dark" if dark else "light"
        apply_theme(self, mode)
        _save_theme(mode)

    def _switch_user(self):
        # Lógica para cambiar usuario
        pass

    # =========================
    # MÉTODOS PLACEHOLDER PARA CLIENTES / STAFF
    # =========================
    def _open_staff_detail(self, staff):
        pass

    def _open_staff_create(self):
        pass

    def _open_client_detail(self, client):
        pass

    def _show_clients_and_refresh(self):
        pass

    def _refresh_clients_table(self):
        pass

    def _refresh_staff_list(self):
        pass

    def _apply_role_gates(self):
        pass

    def _is_allowed_index(self, idx: int) -> bool:
        return True

    def _ensure_cash_page(self):
        return 0

    def _ensure_portfolios_page(self):
        return 0

    def _abrir_nuevo_cliente_popup(self):
        dlg = NewClientPage()
        dlg.exec_()

    def _set_brand_logo(self, height: int):
        # Aquí puedes cargar un QPixmap si tienes logo
        self.brand_logo.setText("🖊")  # placeholder
        self.brand_logo.setFixedHeight(height)

        # =========================
    # MÉTODOS PLACEHOLDER PARA STAFF
    # =========================
    def _back_to_staff_list(self):
        """Regresa a la lista de staff desde el detalle."""
        self._ir(self.idx_staff)
