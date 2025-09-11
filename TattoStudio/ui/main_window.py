# ui/main_window.py
from pathlib import Path
import json

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton,
    QFrame, QStatusBar, QStackedWidget, QSizePolicy
)

from ui.widgets.user_panel import PanelUsuario
from ui.styles.themes import apply_theme

# Páginas exportadas por ui/pages/__init__.py
from ui.pages import (
    StudioPage, NewClientPage, ClientsPage, ClientDetailPage,
    StaffPage, StaffDetailPage, ReportsPage, make_simple_page,
    InventoryDashboardPage, InventoryItemsPage, InventoryItemDetailPage, InventoryMovementsPage,
    AgendaPage
)

SETTINGS = Path(__file__).parents[1] / "settings.json"


def _save_theme(mode: str) -> None:
    """Persistimos el modo de tema (light/dark) en settings.json."""
    SETTINGS.write_text(json.dumps({"theme": mode}, indent=2), encoding="utf-8")


class MainWindow(QMainWindow):
    """Ventana principal: topbar (logo+marca, navegación centrada, usuario) y stack de páginas."""
    solicitar_switch_user = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TattooStudio")
        self.setMinimumSize(1200, 720)

        # =========================
        #  Topbar (3 columnas)
        # =========================
        topbar = QFrame()
        topbar.setObjectName("Topbar")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(16, 12, 16, 12)
        tb.setSpacing(8)

        # ----- IZQUIERDA: logo + marca + stretch -----
        left = QWidget()
        left_lay = QHBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(8)

        self.brand_logo = QLabel()                 # logo de topbar
        self.brand_logo.setObjectName("BrandLogo")
        self._set_brand_logo(28)                   # altura estándar 28 px (ajústalo si quieres)

        brand = QLabel("TattooStudio")
        brand.setObjectName("Brand")

        left_lay.addWidget(self.brand_logo, 0, Qt.AlignVCenter)
        left_lay.addWidget(brand, 0, Qt.AlignVCenter)
        left_lay.addStretch(1)
        tb.addWidget(left, stretch=1)

        # ----- CENTRO: navegación (centrada geométricamente) -----
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

        # El centro NO se estira: mide lo que ocupan los botones → queda centrado
        nav_box.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        tb.addWidget(nav_box, stretch=0, alignment=Qt.AlignCenter)

        # ----- DERECHA: stretch + botón usuario -----
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
        tb.addWidget(right, stretch=1)

        # Panel de usuario
        self.user_panel = PanelUsuario(self)
        self.user_panel.cambiar_usuario.connect(self.solicitar_switch_user.emit)
        self.user_panel.cambiar_tema.connect(self._on_toggle_theme)

        # =========================
        #  Stack de páginas
        # =========================
        self.stack = QStackedWidget()

        # Portada (con nombre real del estudio)
        self.studio_page = StudioPage(studio_name="TattooStudio")
        self.stack.addWidget(self.studio_page)                 # idx 0

        # Agenda real
        self.agenda_page = AgendaPage()
        self.idx_agenda  = self.stack.addWidget(self.agenda_page)

        # Clientes
        self.clients_page    = ClientsPage()
        self.idx_clientes    = self.stack.addWidget(self.clients_page)
        self.client_detail   = ClientDetailPage()
        self.idx_cliente_det = self.stack.addWidget(self.client_detail)
        self.client_detail.back_to_list.connect(lambda: self._ir(self.idx_clientes))

        # Staff
        self.staff_page     = StaffPage()
        self.idx_staff      = self.stack.addWidget(self.staff_page)
        self.staff_detail   = StaffDetailPage()
        self.idx_staff_det  = self.stack.addWidget(self.staff_detail)
        self.idx_staff_new  = self.stack.addWidget(make_simple_page("Nuevo staff"))
        self.staff_detail.back_requested.connect(lambda: self._ir(self.idx_staff))

        # Reportes
        self.reports_page = ReportsPage()
        self.idx_reportes = self.stack.addWidget(self.reports_page)

        # Inventario
        self.inventory_dash   = InventoryDashboardPage()
        self.idx_inventory    = self.stack.addWidget(self.inventory_dash)
        self.inventory_items  = InventoryItemsPage()
        self.idx_inv_items    = self.stack.addWidget(self.inventory_items)
        self.inventory_detail = InventoryItemDetailPage()
        self.idx_inv_detail   = self.stack.addWidget(self.inventory_detail)
        self.inventory_moves  = InventoryMovementsPage()
        self.idx_inv_moves    = self.stack.addWidget(self.inventory_moves)

        # Placeholders de acciones inventario
        self.idx_inv_new_item = self.stack.addWidget(make_simple_page("Nuevo ítem (placeholder)"))
        self.idx_inv_entry    = self.stack.addWidget(make_simple_page("Nueva entrada (placeholder)"))
        self.idx_inv_adjust   = self.stack.addWidget(make_simple_page("Ajuste de inventario (placeholder)"))

        # Nuevo cliente (página de pestañas)
        self.new_client_page = NewClientPage()
        self.idx_nuevo_cliente = self.stack.addWidget(self.new_client_page)

        # Botón volver de Nuevo cliente → regresa a Clientes (o a donde prefieras)
        self.new_client_page.volver_atras.connect(lambda: self._ir(self.idx_clientes))


        # ----- Wiring desde portada (CTAs) -----
        self.studio_page.ir_nueva_cita.connect(lambda: self._ir(self.idx_agenda))
        self.studio_page.ir_nuevo_cliente.connect(lambda: self._ir(self.idx_nuevo_cliente))
        self.studio_page.ir_caja.connect(lambda: self._ir(self._ensure_cash_page()))
        self.studio_page.ir_portafolios.connect(lambda: self._ir(self._ensure_portfolios_page()))

        # Clients wiring
        self.clients_page.crear_cliente.connect(lambda: self._ir(self.idx_nuevo_cliente))
        self.clients_page.abrir_cliente.connect(self._open_client_detail)

        # Staff wiring
        self.staff_page.agregar_staff.connect(lambda: self._ir(self.idx_staff_new))
        self.staff_page.abrir_staff.connect(self._open_staff_detail)
        self.staff_page.abrir_portafolio.connect(self._open_staff_portfolio)

        # =========================
        #  Topbar → navegación
        # =========================
        self.btn_studio.clicked.connect(lambda: self._ir(0))
        self.btn_sched.clicked.connect(lambda: self._ir(self.idx_agenda))
        self.btn_clients.clicked.connect(lambda: self._ir(self.idx_clientes))
        self.btn_staff.clicked.connect(lambda: self._ir(self.idx_staff))
        self.btn_reports.clicked.connect(lambda: self._ir(self.idx_reportes))
        self.btn_forms.clicked.connect(lambda: self._ir(self.idx_inventory))
        self.btn_studio.setChecked(True)

        # =========================
        #  Status bar (sin reloj)
        # =========================
        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Ver. 0.1.1 | Último respaldo —")

        # =========================
        #  Layout raíz
        # =========================
        root = QWidget()
        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(topbar)
        rl.addWidget(self.stack, stretch=1)
        self.setCentralWidget(root)

        # Sincroniza el toggle del tema con lo persistido
        try:
            mode = json.loads(SETTINGS.read_text(encoding="utf-8")).get("theme", "light")
            self.user_panel.chk_dark.setChecked(mode == "dark")
        except Exception:
            pass

    # =========================
    #  Helpers de marca/tema
    # =========================
    def _set_brand_logo(self, height_px: int = 28) -> None:
        """
        Carga assets/logo.png y lo escala a 'height_px' manteniendo proporción.
        Si no existe, deja un espacio reservado para que no “salte” la UI.
        """
        logo_path = Path(__file__).parents[1] / "assets" / "logo.png"
        if logo_path.exists():
            pm = QPixmap(str(logo_path)).scaledToHeight(height_px, Qt.SmoothTransformation)
            self.brand_logo.setPixmap(pm)
            self.brand_logo.setFixedSize(pm.size())
        else:
            self.brand_logo.setFixedSize(height_px, height_px)  # reserva

    def _on_toggle_theme(self, is_dark: bool) -> None:
        mode = "dark" if is_dark else "light"
        apply_theme(self.app(), mode)
        _save_theme(mode)

    def app(self):
        from PyQt5.QtWidgets import QApplication
        return QApplication.instance()

    # =========================
    #  Navegación / utilidades
    # =========================
    def _pill(self, text) -> QToolButton:
        """Crea un botón tipo 'pill' para la topbar."""
        b = QToolButton()
        b.setText(text)
        b.setCheckable(True)
        b.setObjectName("PillNav")
        return b

    def _ensure_cash_page(self) -> int:
        """Crea (una vez) la página 'Caja rápida' (placeholder) y devuelve su índice."""
        if not hasattr(self, "idx_cash"):
            self.idx_cash = self.stack.addWidget(make_simple_page("Caja rápida"))
        return self.idx_cash

    def _ensure_portfolios_page(self) -> int:
        """Crea (una vez) la página 'Portafolios' (placeholder) y devuelve su índice."""
        if not hasattr(self, "idx_portafolios"):
            self.idx_portafolios = self.stack.addWidget(make_simple_page("Portafolios"))
        return self.idx_portafolios

    def _ir(self, idx: int) -> None:
    # Qué botón debe quedar marcado según la página visitada
        mapping = {
            # Estudio
            0: self.btn_studio,

            # Agenda
            self.idx_agenda: self.btn_sched,

            # Clientes (lista, detalle y nuevo)
            self.idx_clientes: self.btn_clients,
            self.idx_cliente_det: self.btn_clients,       # << añadido
            self.idx_nuevo_cliente: self.btn_clients,     # << añadido

            # Staff (lista, detalle y nuevo)
            self.idx_staff: self.btn_staff,
            self.idx_staff_det: self.btn_staff,           # << añadido
            self.idx_staff_new: self.btn_staff,           # << añadido

            # Reportes
            self.idx_reportes: self.btn_reports,

            # Inventario (todas sus subpáginas)
            self.idx_inventory: self.btn_forms,
            self.idx_inv_items: self.btn_forms,           # << añadido (opcional)
            self.idx_inv_detail: self.btn_forms,          # << añadido (opcional)
            self.idx_inv_moves: self.btn_forms,           # << añadido (opcional)
            self.idx_inv_new_item: self.btn_forms,        # << añadido (opcional)
            self.idx_inv_entry: self.btn_forms,           # << añadido (opcional)
            self.idx_inv_adjust: self.btn_forms,          # << añadido (opcional)
        }

        # Desmarcar todas las pills
        for btn in (self.btn_studio, self.btn_sched, self.btn_clients,
                    self.btn_staff, self.btn_reports, self.btn_forms):
            btn.setChecked(False)

        # Marcar la que corresponda
        if idx in mapping:
            mapping[idx].setChecked(True)

        self.stack.setCurrentIndex(idx)


    # ====== wiring a fichas (clientes / staff) ======
    def _open_client_detail(self, client: dict) -> None:
        self.client_detail.load_client(client)
        self._ir(self.idx_cliente_det)

    def _open_staff_detail(self, staff: dict) -> None:
        self.staff_detail.load_staff(staff)
        self._ir(self.idx_staff_det)

    def _open_staff_portfolio(self, staff: dict) -> None:
        self.staff_detail.load_staff(staff)
        self.staff_detail.go_to_portfolio()
        self._ir(self.idx_staff_det)

    # Cerrar popup de usuario si clicas fuera
    def _toggle_user_panel(self, checked: bool) -> None:
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
        if self.user_panel.isVisible() and not self.user_panel.geometry().contains(event.globalPos()):
            self.user_panel.hide()
            self.btn_user.setChecked(False)
        super().mousePressEvent(event)
