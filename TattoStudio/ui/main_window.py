from pathlib import Path
import json

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton,
    QFrame, QStatusBar, QStackedWidget, QSizePolicy, QDialog, QVBoxLayout as QVBL
)

from ui.widgets.user_panel import PanelUsuario
from ui.styles.themes import apply_theme
from ui.pages.new_item import NewItemPage
from ui.pages.common import FramelessPopup

# Login / sesión actual
from services.contracts import set_current_user, get_current_user
from ui.login import LoginDialog

# Portafolios
from ui.pages.portfolios import PortfoliosPage

# Páginas exportadas por ui/pages/__init__.py
from ui.pages import (
    StudioPage, NewClientPage, ClientsPage, ClientDetailPage,
    StaffPage, StaffDetailPage, ReportsPage, make_simple_page,
    InventoryDashboardPage, InventoryItemsPage, InventoryItemDetailPage, InventoryMovementsPage,
    AgendaPage
)

from ui.pages.nueva_entrada import EntradaProductoWidget
from data.models.product import Product

# Caja (opcional)
try:
    from ui.pages.cash_register import CashRegisterDialog
except Exception:
    CashRegisterDialog = None  # fallback si aún no existe

SETTINGS = Path(__file__).parents[1] / "settings.json"


def _save_theme(mode: str) -> None:
    """Persistimos el modo de tema (light/dark) en settings.json."""
    SETTINGS.write_text(json.dumps({"theme": mode}, indent=2), encoding="utf-8")


class MainWindow(QMainWindow):
    """Ventana principal: topbar (logo+marca, navegación centrada, usuario) y stack de páginas."""
    solicitar_switch_user = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("InkLink OS")
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

        self.brand_logo = QLabel()
        self.brand_logo.setObjectName("BrandLogo")
        self._set_brand_logo(28)

        brand = QLabel("InkLink OS")
        brand.setObjectName("Brand")

        left_lay.addWidget(self.brand_logo, 0, Qt.AlignVCenter)
        left_lay.addWidget(brand, 0, Qt.AlignVCenter)
        left_lay.addStretch(1)
        tb.addWidget(left, stretch=1)

        # ----- CENTRO: navegación (centrada) -----
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

        # ----- DERECHA: stretch + botón usuario -----
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

        # Panel de usuario
        self.user_panel = PanelUsuario(self)
        self.user_panel.cambiar_usuario.connect(self.solicitar_switch_user.emit)
        self.user_panel.cambiar_tema.connect(self._on_toggle_theme)
        self.solicitar_switch_user.connect(self._switch_user)

        # =========================
        #  Stack de páginas
        # =========================
        self.stack = QStackedWidget()

        # Portada
        self.studio_page = StudioPage(studio_name="InkLink OS")
        self.stack.addWidget(self.studio_page)  # idx 0

        # Agenda
        self.agenda_page = AgendaPage()
        self.idx_agenda  = self.stack.addWidget(self.agenda_page)

        # Clientes
        self.clients_page    = ClientsPage()
        self.idx_clientes    = self.stack.addWidget(self.clients_page)
        self.client_detail   = ClientDetailPage()
        self.idx_cliente_det = self.stack.addWidget(self.client_detail)
        self.client_detail.back_to_list.connect(self._show_clients_and_refresh)
        self.client_detail.cliente_cambiado.connect(self._refresh_clients_table)

        # Señales clientes
        self.clients_page.crear_cliente.connect(self._abrir_nuevo_cliente_popup)
        self.clients_page.abrir_cliente.connect(self._open_client_detail)

        # Staff
        self.staff_page     = StaffPage()
        self.idx_staff      = self.stack.addWidget(self.staff_page)
        self.staff_detail   = StaffDetailPage()
        self.idx_staff_det  = self.stack.addWidget(self.staff_detail)
        self.idx_staff_new  = self.stack.addWidget(make_simple_page("Nuevo staff"))  # placeholder

        self.staff_page.agregar_staff.connect(self._open_staff_create)
        self.staff_page.abrir_staff.connect(self._open_staff_detail)
        self.staff_detail.back_requested.connect(self._back_to_staff_list)
        self.staff_detail.staff_saved.connect(self._refresh_staff_list)

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

        # Wiring Inventario
        self.inventory_dash.ir_items        = lambda: self._ir(self.idx_inv_items)
        self.inventory_dash.ir_movimientos  = lambda: self._ir(self.idx_inv_moves)
        self.inventory_dash.nuevo_item      = self._abrir_popup_nuevo_item

        self.inventory_items.abrir_item     = lambda it: (self.inventory_detail.load_item(it),
                                                          self._ir(self.idx_inv_detail))
        self.inventory_items.nuevo_item     = self._abrir_popup_nuevo_item
        # Placeholders hasta que existan diálogos reales:
        self.idx_inv_entry    = self.stack.addWidget(make_simple_page("Nueva entrada"))
        self.idx_inv_adjust   = self.stack.addWidget(make_simple_page("Ajuste de inventario"))
        self.inventory_items.nueva_entrada  = self._abrir_entrada_producto
        self.inventory_items.nuevo_ajuste   = lambda it: self._ir(self.idx_inv_adjust)

        self.inventory_detail.volver.connect(lambda: self._ir(self.idx_inv_items))
        self.inventory_moves.volver.connect(lambda: self._ir(self.idx_inventory))

        # Nuevo cliente (en popup)
        self.new_client_page = NewClientPage()
        self.idx_nuevo_cliente = self.stack.addWidget(self.new_client_page)
        self.new_client_page.volver_atras.connect(lambda: self._ir(self.idx_clientes))

        # Portafolios (página real)
        self.portfolios_page = PortfoliosPage()
        self.idx_portafolios = self.stack.addWidget(self.portfolios_page)
        if hasattr(self.studio_page, "ir_portafolios"):
            self.studio_page.ir_portafolios.connect(lambda: self._ir(self.idx_portafolios))

        # ----- Wiring desde portada (CTAs) -----
        self.studio_page.ir_nueva_cita.connect(lambda: self._ir(self.idx_agenda))
        self.studio_page.ir_nuevo_cliente.connect(self._abrir_nuevo_cliente_popup)
        self.studio_page.ir_caja.connect(self._open_cash_dialog)

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
        #  Status bar
        # =========================
        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Ver. 0.2.0 | Último respaldo —")

        # =========================
        #  Layout raíz
        # =========================
        root = QWidget()
        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(topbar)
        rl.addWidget(self.stack, stretch=1)
        self.setCentralWidget(root)

        # Tema persistido
        try:
            mode = json.loads(SETTINGS.read_text(encoding="utf-8")).get("theme", "light")
            self.user_panel.chk_dark.setChecked(mode == "dark")
        except Exception:
            pass

        # =========================
        #  LOGIN + RBAC
        # =========================
        dlg = LoginDialog(self)
        if dlg.exec_() != QDialog.Accepted or not dlg.user:
            self.close()
            return

        set_current_user(dlg.user)  # guardar sesión actual (id, role, artist_id)
        try:
            self.btn_user.setText(f"{dlg.user.get('username', 'Usuario')} ({dlg.user.get('role', '-')})")
        except Exception:
            self.btn_user.setText("Usuario")

        # Aplica gates de rol (ocultar menús/páginas y fijar páginas permitidas)
        self._apply_role_gates()
        # Asegura que la página inicial sea válida para el rol actual
        if not self._is_allowed_index(self.stack.currentIndex()):
            self._ir(0)  # portada

    # =========================
    #  Helpers de marca/tema
    # =========================
    def _set_brand_logo(self, height_px: int = 28) -> None:
        """Carga assets/logo.png y lo escala a 'height_px' manteniendo proporción."""
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
    
    def _open_client_detail(self, client: dict) -> None:
        self.client_detail.load_client(client)
        self._ir(self.idx_cliente_det)

    # ---------- RBAC ----------
    def _allowed_indices_for_role(self):
        """
        Devuelve el conjunto de índices de la stack permitidos para el rol actual.
          - admin: todo
          - assistant: Estudio, Agenda, Clientes (y subpáginas), Reportes, Staff (ver/detalle)
          - artist: Estudio, Agenda, Reportes, Clientes (ver/detalle), Staff (ver/detalle)
        """
        u = get_current_user() or {}
        role = u.get("role", "admin")
        allowed = {0, self.idx_agenda, self.idx_reportes}

        if role == "admin":
            allowed |= {
                self.idx_clientes, self.idx_cliente_det, self.idx_nuevo_cliente,
                self.idx_staff, self.idx_staff_det, self.idx_staff_new,
                self.idx_inventory, self.idx_inv_items, self.idx_inv_detail,
                self.idx_inv_moves, self.idx_inv_entry, self.idx_inv_adjust,
            }
            if hasattr(self, "idx_cash"): allowed.add(self.idx_cash)
            if hasattr(self, "idx_portafolios"): allowed.add(self.idx_portafolios)

        elif role == "assistant":
            allowed |= {
                self.idx_clientes, self.idx_cliente_det, self.idx_nuevo_cliente,
                self.idx_staff, self.idx_staff_det,
            }
            if hasattr(self, "idx_portafolios"): allowed.add(self.idx_portafolios)

        elif role == "artist":
            allowed |= {
                self.idx_clientes, self.idx_cliente_det,
                self.idx_staff, self.idx_staff_det,
            }
            if hasattr(self, "idx_portafolios"): allowed.add(self.idx_portafolios)

        return allowed

    def _apply_role_gates(self):
        """Oculta/mostrar navegación principal según rol y fija páginas permitidas."""
        u = get_current_user() or {}
        role = u.get("role", "admin")

        # Visibilidad de botones de la topbar
        self.btn_clients.setVisible(role in ("admin", "assistant", "artist"))
        self.btn_staff.setVisible(role in ("admin", "assistant", "artist"))
        self.btn_forms.setVisible(role == "admin")  # Inventario solo admin

        # Calcula y guarda índices permitidos
        self._allowed_idx = self._allowed_indices_for_role()

    def _is_allowed_index(self, idx: int) -> bool:
        try:
            return idx in self._allowed_idx
        except Exception:
            return True  # fallback seguro

    def _ir(self, idx: int) -> None:
        # Si la página no es permitida para el rol, redirigimos a portada
        if not self._is_allowed_index(idx):
            self.statusBar().showMessage("Tu rol no tiene acceso a esa sección.", 3000)
            idx = 0

        # Qué botón debe quedar marcado según la página visitada
        mapping = {
            0: self.btn_studio,                   # Estudio
            self.idx_agenda: self.btn_sched,     # Agenda

            # Clientes
            self.idx_clientes: self.btn_clients,
            self.idx_cliente_det: self.btn_clients,
            self.idx_nuevo_cliente: self.btn_clients,

            # Staff
            self.idx_staff: self.btn_staff,
            self.idx_staff_det: self.btn_staff,
            self.idx_staff_new: self.btn_staff,

            # Reportes
            self.idx_reportes: self.btn_reports,

            # Inventario
            self.idx_inventory: self.btn_forms,
            self.idx_inv_items: self.btn_forms,
            self.idx_inv_detail: self.btn_forms,
            self.idx_inv_moves: self.btn_forms,
            self.idx_inv_entry: self.btn_forms,
            self.idx_inv_adjust: self.btn_forms,
        }

        for btn in (self.btn_studio, self.btn_sched, self.btn_clients,
                    self.btn_staff, self.btn_reports, self.btn_forms):
            btn.setChecked(False)

        if idx in mapping:
            mapping[idx].setChecked(True)

        self.stack.setCurrentIndex(idx)

    # ====== Clientes ======
    def _abrir_nuevo_cliente_popup(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Nuevo cliente")
        dlg.setModal(True)

        page = NewClientPage()
        page.volver_atras.connect(dlg.reject)
        page.cliente_creado.connect(lambda _id: self.clients_page.reload_from_db_and_refresh(keep_page=False))

        lay = QVBL(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(page)

        dlg.resize(900, 700)
        dlg.exec_()

    def _on_cliente_creado(self, cid: int):
        try:
            self.clients_page.reload_from_db_and_refresh(keep_page=True)
        except Exception:
            pass
        self._ir(self.idx_clientes)

    def _show_clients_and_refresh(self):
        self._refresh_clients_table()
        self._ir(self.idx_clientes)

    def _refresh_clients_table(self):
        try:
            self.clients_page.reload_from_db_and_refresh(keep_page=True)
        except Exception:
            pass

    # ====== Staff ======
    def _open_staff_create(self):
        self.staff_detail.start_create_mode()
        self._ir(self.idx_staff_det)

    def _open_staff_detail(self, staff: dict):
        self.staff_detail.load_staff(staff)
        self._ir(self.idx_staff_det)

    def _back_to_staff_list(self):
        self._refresh_staff_list()
        self._ir(self.idx_staff)

    def _refresh_staff_list(self):
        try:
            self.staff_page.reload_from_db_and_refresh()
        except Exception:
            pass

    # ====== Caja ======
    def _open_cash_dialog(self):
        if CashRegisterDialog is None:
            try:
                return self._ir(self._ensure_cash_page())
            except Exception:
                return

        dlg = CashRegisterDialog(self)
        try:
            dlg.setModal(True)
        except Exception:
            pass

        dlg.exec_()

        # Refrescar vistas afectadas por transacciones
        for refresher in (getattr(self, "reports_page", None),
                          getattr(self, "agenda_page", None)):
            try:
                if hasattr(refresher, "reload_from_db_and_refresh"):
                    refresher.reload_from_db_and_refresh()
                elif hasattr(refresher, "refresh_all"):
                    refresher.refresh_all()
                elif hasattr(refresher, "refresh"):
                    refresher.refresh()
            except Exception:
                pass

    # ====== Usuario ======
    def _switch_user(self):
        self.btn_user.setChecked(False)
        dlg = LoginDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.user:
            set_current_user(dlg.user)
            try:
                self.btn_user.setText(f"{dlg.user.get('username', 'Usuario')} ({dlg.user.get('role', '-')})")
            except Exception:
                self.btn_user.setText("Usuario")
            self._apply_role_gates()
            if not self._is_allowed_index(self.stack.currentIndex()):
                self._ir(0)

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

    # ====== Inventario: popup y refrescos ======
    def _on_item_creado(self, sku: str):
        print(f"Producto creado")  
        self.inventory_items._seed_mock()
        self.inventory_items._refresh() 
        self.inventory_dash.refrescar_datos()# <- actualizar KPIs

    def _abrir_popup_nuevo_item(self):
         # Crear instancia de NewItemPage
        dlg = FramelessPopup(self)
        dlg.setObjectName("NewItemDlg")
        dlg.setModal(True)

        dlg.resize(860, 720)

        outer = QVBL(dlg)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        from PyQt5.QtGui import QColor

        panel = QFrame(dlg)
        panel.setObjectName("PopupPanel")
        panel_lay = QVBL(panel)
        panel_lay.setContentsMargins(24, 24, 24, 24)
        panel_lay.setSpacing(0)

        form = NewItemPage(panel)
        panel_lay.addWidget(form)

        dlg.setStyleSheet("""
        #NewItemDlg { background: transparent; }
        #PopupPanel {
            background: #2A2F34;
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 16px;
        }
        """)
        shadow = QGraphicsDropShadowEffect(dlg)
        shadow.setBlurRadius(32); shadow.setXOffset(0); shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 120))
        panel.setGraphicsEffect(shadow)

        # Señales
        try: form.item_creado.connect(self._on_item_creado)
        except: pass
        try: form.btn_guardar.clicked.connect(dlg.accept)
        except: pass
        try: form.btn_cancelar.clicked.connect(dlg.reject)
        except: pass

        outer.addWidget(panel)
        dlg.exec_()

#entrada_producto_popup
    def _abrir_entrada_producto(self, item_dict):
        """
        Abre el diálogo de entrada de producto como un popup modal
        y actualiza la tabla cuando se guarda.
        """
        # Convertir el diccionario en objeto Product temporal
        producto = Product(
            sku=item_dict["sku"],
            name=item_dict["nombre"],
            category=item_dict["categoria"],
            unidad=item_dict["unidad"],
            stock=item_dict["stock"],
            min_stock=item_dict["minimo"],
            caduca=item_dict["caduca"],
            proveedor=item_dict["proveedor"],
            activo=item_dict["activo"],
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("Nueva Entrada de Producto")
        dialog.setModal(True)  # bloquea la ventana principal

        # Agregar el formulario dentro del diálogo
        layout = QVBoxLayout(dialog)
        form = EntradaProductoWidget(producto)
        form.entrada_creada.connect(self._on_entrada_creada)
        form.btn_guardar.clicked.connect(dialog.accept)
        form.btn_cancelar.clicked.connect(dialog.reject)
        layout.addWidget(form)
        dialog.exec_()

    def _on_entrada_creada(self, nombre):
        print(f"✅ Entrada creada para el producto: {nombre}")
        self.inventory_items._seed_mock()
        self.inventory_items._refresh()
        self.inventory_dash.refrescar_datos()
