from pathlib import Path
import json

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton,
    QFrame, QStatusBar, QStackedWidget, QSizePolicy, QDialog
)

from ui.widgets.user_panel import PanelUsuario
from ui.styles.themes import apply_theme

# Login / sesión actual
from services.contracts import set_current_user, get_current_user
from ui.login import LoginDialog

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
        self._set_brand_logo(28)                   # altura estándar 28 px

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
        self.solicitar_switch_user.connect(self._switch_user)  # ← cambio de usuario

        # =========================
        #  Stack de páginas
        # =========================
        self.stack = QStackedWidget()

        # Portada
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

        # Señales: volver y refrescar tras cambios (guardar/archivar/eliminar)
        self.client_detail.back_to_list.connect(self._show_clients_and_refresh)
        self.client_detail.cliente_cambiado.connect(self._refresh_clients_table)

        # Staff
        self.staff_page     = StaffPage()
        self.idx_staff      = self.stack.addWidget(self.staff_page)
        self.staff_detail   = StaffDetailPage()
        self.idx_staff_det  = self.stack.addWidget(self.staff_detail)
        self.idx_staff_new  = self.stack.addWidget(make_simple_page("Nuevo staff"))  # (placeholder opcional)

        # Abrir ficha (ver/editar) y alta en modo "nuevo"
        self.staff_page.agregar_staff.connect(self._open_staff_create)
        self.staff_page.abrir_staff.connect(self._open_staff_detail)

        # Navegación y refrescos tras acciones
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
        self.inventory_dash.ir_items        = lambda: self._ir(self.idx_inv_items)
        self.inventory_dash.ir_movimientos  = lambda: self._ir(self.idx_inv_moves)
        self.inventory_dash.nuevo_item      = lambda: self._ir(self.idx_inv_new_item)
        self.inventory_items.abrir_item     = lambda it: (self.inventory_detail.load_item(it), self._ir(self.idx_inv_detail))
        self.inventory_items.nuevo_item     = lambda: self._ir(self.idx_inv_new_item)
        self.inventory_items.nueva_entrada  = lambda it: self._ir(self.idx_inv_entry)
        self.inventory_items.nuevo_ajuste   = lambda it: self._ir(self.idx_inv_adjust)
        self.inventory_detail.volver.connect(lambda: self._ir(self.idx_inv_items))

        # Placeholders de acciones inventario
        self.inventory_moves.volver.connect(lambda: self._ir(self.idx_inventory))
        self.idx_inv_new_item = self.stack.addWidget(make_simple_page("Nuevo ítem"))
        self.idx_inv_entry    = self.stack.addWidget(make_simple_page("Nueva entrada"))
        self.idx_inv_adjust   = self.stack.addWidget(make_simple_page("Ajuste de inventario"))

        # Nuevo cliente (existe en stack pero se usa como POPUP)
        self.new_client_page = NewClientPage()
        self.idx_nuevo_cliente = self.stack.addWidget(self.new_client_page)
        self.new_client_page.volver_atras.connect(lambda: self._ir(self.idx_clientes))

        # ----- Wiring desde portada (CTAs) -----
        self.studio_page.ir_nueva_cita.connect(lambda: self._ir(self.idx_agenda))
        # Abrir "Nuevo cliente" como POPUP:
        self.studio_page.ir_nuevo_cliente.connect(self._abrir_nuevo_cliente_popup)
        self.studio_page.ir_caja.connect(lambda: self._ir(self._ensure_cash_page()))
        self.studio_page.ir_portafolios.connect(lambda: self._ir(self._ensure_portfolios_page()))

        # Clients wiring
        self.clients_page.crear_cliente.connect(self._abrir_nuevo_cliente_popup)
        self.clients_page.abrir_cliente.connect(self._open_client_detail)

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
        status.showMessage("Ver. 0.1.6 | Último respaldo —")

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

    # ---------- RBAC ----------
    def _allowed_indices_for_role(self):
        """
        Devuelve el conjunto de índices de la stack permitidos para el rol actual.
        Reglas mínimas:
          - admin: todo
          - assistant: Estudio, Agenda, Clientes (y subpáginas), Reportes
          - artist: Estudio, Agenda, Reportes + Clientes (vista/detalle)
        """
        u = get_current_user() or {}
        role = u.get("role", "admin")
        allowed = {0, self.idx_agenda, self.idx_reportes}

        if role == "admin":
            # Todo lo que existe
            allowed |= {
                self.idx_clientes, self.idx_cliente_det, self.idx_nuevo_cliente,
                self.idx_staff, self.idx_staff_det, self.idx_staff_new,
                self.idx_inventory, self.idx_inv_items, self.idx_inv_detail,
                self.idx_inv_moves, self.idx_inv_new_item, self.idx_inv_entry, self.idx_inv_adjust,
            }
            if hasattr(self, "idx_cash"): allowed.add(self.idx_cash)
            if hasattr(self, "idx_portafolios"): allowed.add(self.idx_portafolios)
        elif role == "assistant":
            allowed |= {self.idx_clientes, self.idx_cliente_det, self.idx_nuevo_cliente}
        elif role == "artist":
            # Acceso de lectura a Clientes (lista + detalle)
            allowed |= {self.idx_clientes, self.idx_cliente_det}
            # (El popup de “Nuevo Cliente” se maneja fuera del stack.)

        return allowed

    def _apply_role_gates(self):
        """
        Oculta/mostrar navegación principal según rol y fija páginas permitidas.
        """
        u = get_current_user() or {}
        role = u.get("role", "admin")

        # Visibilidad de botones de la topbar
        self.btn_clients.setVisible(role in ("admin", "assistant", "artist"))
        self.btn_staff.setVisible(role in ("admin", "assistant", "artist"))
        self.btn_forms.setVisible(role == "admin")  # Inventario solo admin

        # Guardamos el set de páginas permitidas para validarlo en _ir
        def _allowed_indices_for_role(self):
            """
            Devuelve el conjunto de índices de la stack permitidos para el rol actual.
            - admin: todo
            - assistant: Estudio, Agenda, Clientes (y subpáginas), Staff (ver/detalle), Reportes
            - artist: Estudio, Agenda, Clientes (ver/detalle), Staff (ver/detalle), Reportes
            """
            u = get_current_user() or {}
            role = u.get("role", "admin")
            allowed = {0, self.idx_agenda, self.idx_reportes}

            if role == "admin":
                allowed |= {
                    self.idx_clientes, self.idx_cliente_det, self.idx_nuevo_cliente,
                    self.idx_staff, self.idx_staff_det, self.idx_staff_new,
                    self.idx_inventory, self.idx_inv_items, self.idx_inv_detail,
                    self.idx_inv_moves, self.idx_inv_new_item, self.idx_inv_entry, self.idx_inv_adjust,
                }
                if hasattr(self, "idx_cash"): allowed.add(self.idx_cash)
                if hasattr(self, "idx_portafolios"): allowed.add(self.idx_portafolios)

            elif role == "assistant":
                allowed |= {
                    self.idx_clientes, self.idx_cliente_det, self.idx_nuevo_cliente,
                    self.idx_staff, self.idx_staff_det,
                }

            elif role == "artist":
                allowed |= {
                    self.idx_clientes, self.idx_cliente_det,
                    self.idx_staff, self.idx_staff_det,
                }

            return allowed


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
            # Estudio
            0: self.btn_studio,

            # Agenda
            self.idx_agenda: self.btn_sched,

            # Clientes (lista, detalle y nuevo)
            self.idx_clientes: self.btn_clients,
            self.idx_cliente_det: self.btn_clients,
            self.idx_nuevo_cliente: self.btn_clients,

            # Staff (lista, detalle y nuevo)
            self.idx_staff: self.btn_staff,
            self.idx_staff_det: self.btn_staff,
            self.idx_staff_new: self.btn_staff,

            # Reportes
            self.idx_reportes: self.btn_reports,

            # Inventario (todas sus subpáginas)
            self.idx_inventory: self.btn_forms,
            self.idx_inv_items: self.btn_forms,
            self.idx_inv_detail: self.btn_forms,
            self.idx_inv_moves: self.btn_forms,
            self.idx_inv_new_item: self.btn_forms,
            self.idx_inv_entry: self.btn_forms,
            self.idx_inv_adjust: self.btn_forms,
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
        self.staff_detail.staff_saved.connect(self._on_staff_saved)
        self.staff_detail.back_requested.connect(self._back_to_staff_list)

    def _open_staff_portfolio(self, staff: dict) -> None:
        self.staff_detail.load_staff(staff)
        self.staff_detail.go_to_portfolio()
        self._ir(self.idx_staff_det)

    def _on_staff_saved(self):
        # Refresca la lista de staff y vuelve a la página de listado
        try:
            # si tu StaffPage expone este método
            self.staff_page.reload_from_db()
        except Exception:
            # fallback: si el método se llama distinto
            if hasattr(self.staff_page, "refresh"):
                self.staff_page.refresh()
        self._back_to_staff_list()


    # ====== Nuevo cliente como POPUP + refresco inmediato ======
    def _abrir_nuevo_cliente_popup(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Nuevo cliente")
        dlg.setModal(True)

        page = NewClientPage()
        page.volver_atras.connect(dlg.reject)
        page.cliente_creado.connect(lambda _id: self.clients_page.reload_from_db_and_refresh(keep_page=False))

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(page)

        dlg.resize(900, 700)
        dlg.exec_()

    def _on_cliente_creado(self, cid: int):
        # Refresca la tabla de clientes sin perder la página actual
        try:
            self.clients_page.reload_from_db_and_refresh(keep_page=True)
        except Exception:
            pass
        self._ir(self.idx_clientes)

    # ====== refrescos de Clientes ======
    def _show_clients_and_refresh(self):
        self._refresh_clients_table()
        self._ir(self.idx_clientes)

    def _refresh_clients_table(self):
        try:
            # Método implementado en ClientsPage para recargar datos desde BD
            self.clients_page.reload_from_db_and_refresh(keep_page=True)
        except Exception:
            pass

    # Cambio de usuario (desde PanelUsuario)
    def _switch_user(self):
        self.btn_user.setChecked(False)  # oculta panel
        dlg = LoginDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.user:
            set_current_user(dlg.user)
            try:
                self.btn_user.setText(f"{dlg.user.get('username', 'Usuario')} ({dlg.user.get('role', '-')})")
            except Exception:
                self.btn_user.setText("Usuario")
            self._apply_role_gates()
            # Si la página actual deja de ser válida, llévalo a Estudio
            if not self._is_allowed_index(self.stack.currentIndex()):
                self._ir(0)

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
# ====== Staff: helpers de navegación/refresco ======
    def _open_staff_create(self):
        """Abrir StaffDetail en modo 'nuevo usuario'."""
        self.staff_detail.start_create_mode()
        self._ir(self.idx_staff_det)

    def _open_staff_detail(self, staff: dict):
        """Abrir StaffDetail cargando desde BD el usuario elegido."""
        self.staff_detail.load_staff(staff)
        self._ir(self.idx_staff_det)

    def _back_to_staff_list(self):
        """Volver a la lista de Staff refrescándola."""
        self._refresh_staff_list()
        self._ir(self.idx_staff)

    def _refresh_staff_list(self):
        """Recarga StaffPage desde BD (seguro ante errores)."""
        try:
            self.staff_page.reload_from_db_and_refresh()
        except Exception:
            pass

    def mousePressEvent(self, event):
        if self.user_panel.isVisible() and not self.user_panel.geometry().contains(event.globalPos()):
            self.user_panel.hide()
            self.btn_user.setChecked(False)
        super().mousePressEvent(event)
