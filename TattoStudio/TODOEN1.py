import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QToolButton,
    QHBoxLayout, QVBoxLayout, QFrame, QStatusBar, QStackedWidget,
    QSpacerItem, QSizePolicy, QLineEdit, QTabWidget, QFormLayout, QDateEdit, QTextEdit, QCheckBox,
    QListWidget, QListWidgetItem, QGroupBox, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QDate

# -------------------- Login --------------------
class LoginWindow(QWidget):
    # Señal para que la ventana principal pueda pasar del login a la app
    acceso_solicitado = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TattooStudio — Inicio de sesión")
        self.setMinimumSize(420, 280)

        # --- Layout raíz ---
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(16)

        # --- Título (mismo estilo que la portada) ---
        title = QLabel("Bienvenido a TattooStudio")
        title.setObjectName("H1")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        # --- Formulario ---
        form = QVBoxLayout(); form.setSpacing(10)

        lbl_user = QLabel("Usuario")
        self.in_user = QLineEdit()
        self.in_user.setPlaceholderText("Escribe tu usuario...")

        lbl_code = QLabel("Código de acceso")
        self.in_code = QLineEdit()
        self.in_code.setPlaceholderText("Ej. 1234-ABCD")
        self.in_code.setEchoMode(QLineEdit.Password)  # oculta el código

        form.addWidget(lbl_user);  form.addWidget(self.in_user)
        form.addWidget(lbl_code);  form.addWidget(self.in_code)
        root.addLayout(form)

        # --- Botón CTA (negro, redondeado) ---
        self.btn_login = QPushButton("Entrar")
        self.btn_login.setObjectName("CTA")
        self.btn_login.setMinimumHeight(36)
        # No valida nada: solo emite la señal para que MainWindow muestre la app
        self.btn_login.clicked.connect(self.acceso_solicitado.emit)
        root.addWidget(self.btn_login)

        # --- Nota ---
        hint = QLabel("*(Mock) No valida credenciales; solo continúa)*")
        hint.setAlignment(Qt.AlignCenter)
        hint.setObjectName("Hint")
        root.addWidget(hint)

        # Estilos locales (idénticos a tu main). Si ya cargas QSS global, puedes comentar esta línea.
        self._qss()

    def _qss(self):
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI', Arial; font-size: 11pt; color: #111; }
            #H1 { font-size: 32px; font-weight: 800; letter-spacing: -0.5px; }
            QLabel#Hint { color: #666; font-size: 10pt; }

            /* Inputs agradables a juego con tu UI */
            QLineEdit {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 8px 10px;
                background: #fff;
                color: #111;
            }
            QLineEdit:focus {
                border: 1px solid #111;
                outline: none;
            }

            /* Botón principal (CTA) */
            QPushButton#CTA {
                background: #2b2b2b; color: #fff; border: none; border-radius: 10px;
                padding: 10px 16px; font-weight: 600;
            }
            QPushButton#CTA:hover { background: #1f1f1f; }
        """)


# -------------------- Panel de usuario (desplegable) --------------------
class PanelUsuario(QFrame):
    cambiar_usuario = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Ventana tipo popup: se cierra si haces clic fuera
        self.setWindowFlags(self.windowFlags() | Qt.Popup)
        self.setObjectName("UserPanel")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        nombre = QLabel("Dylan Bourjac"); nombre.setObjectName("UserName")
        rol    = QLabel("Tatuador");       rol.setObjectName("UserMeta")
        mail   = QLabel("dbourjac@hotmail.com"); mail.setObjectName("UserMeta")
        lay.addWidget(nombre); lay.addWidget(rol); lay.addWidget(mail)

        btn_switch  = QPushButton("Cambiar usuario"); btn_switch.setObjectName("GhostSmall")
        btn_settings= QPushButton("Ajustes");         btn_settings.setObjectName("GhostSmall")
        btn_info    = QPushButton("Información");     btn_info.setObjectName("GhostSmall")
        btn_switch.clicked.connect(self.cambiar_usuario.emit)

        for b in (btn_switch, btn_settings, btn_info):
            b.setFixedHeight(28)
            lay.addWidget(b)


# -------------------- Páginas --------------------
class StudioPage(QWidget):
    ir_nuevo_cliente = pyqtSignal()
    ir_cliente_recurrente = pyqtSignal()
    ir_portafolios = pyqtSignal()
    ir_fila = pyqtSignal()

    def __init__(self):
        super().__init__()
        root = QHBoxLayout(self)
        root.setContentsMargins(40, 20, 40, 20)
        root.setSpacing(24)

        # Spacer izquierdo
        root.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Columna central (logo/título/CTAs)
        col = QVBoxLayout()
        col.setSpacing(16)
        col.setAlignment(Qt.AlignHCenter)

        logo = QLabel()                 # (luego puedes setPixmap)
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


class NewClientPage(QWidget):
    """
    Formulario (mock) de Nuevo Cliente:
    - Solo UI, sin guardado real.
    - Tabs: Identificación & Contacto / Preferencias / Salud / Consentimientos / Emergencia / Notas & Archivos
    - Botones al pie: Guardar / Guardar y agendar / Cancelar (sin lógica)
    """
    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 16)
        root.setSpacing(12)

        title = QLabel("Nuevo cliente")
        title.setObjectName("H1")
        root.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._tab_identificacion_contacto(), "Identificación & Contacto")
        tabs.addTab(self._tab_preferencias(), "Preferencias")
        tabs.addTab(self._tab_salud(), "Salud")
        tabs.addTab(self._tab_consentimientos(), "Consentimientos")
        tabs.addTab(self._tab_emergencia(), "Emergencia")
        tabs.addTab(self._tab_notas_archivos(), "Notas & Archivos")
        root.addWidget(tabs, stretch=1)

        # Barra de botones
        btn_bar = QHBoxLayout()
        btn_bar.addStretch(1)
        self.btn_guardar = QPushButton("Guardar"); self.btn_guardar.setObjectName("CTA")
        self.btn_guardar_agendar = QPushButton("Guardar y agendar"); self.btn_guardar_agendar.setObjectName("CTA")
        self.btn_cancelar = QPushButton("Cancelar"); self.btn_cancelar.setObjectName("GhostSmall")
        for b in (self.btn_guardar, self.btn_guardar_agendar, self.btn_cancelar):
            b.setMinimumHeight(36)
            btn_bar.addWidget(b)
        root.addLayout(btn_bar)

        # Habilita/deshabilita "Guardar" según campos obligatorios (validación mínima local)
        self._wire_min_validation()

    # ---------- Tabs ----------
    def _tab_identificacion_contacto(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(12)

        # Identificación
        box_id = QGroupBox("Identificación")
        form_id = QFormLayout(box_id); form_id.setLabelAlignment(Qt.AlignRight)
        self.in_nombres = QLineEdit();      self.in_nombres.setPlaceholderText("Nombre(s) *")
        self.in_ap1 = QLineEdit();          self.in_ap1.setPlaceholderText("Primer apellido *")
        self.in_ap2 = QLineEdit();          self.in_ap2.setPlaceholderText("Segundo apellido (opcional)")
        self.in_fnac = QDateEdit();         self.in_fnac.setCalendarPopup(True)
        self.in_fnac.setDisplayFormat("dd/MM/yyyy"); self.in_fnac.setDate(QDate.currentDate().addYears(-18))
        self.cb_genero = QComboBox();       self.cb_genero.addItems(["No especifica", "Femenino", "Masculino"])

        form_id.addRow("Nombre(s):", self.in_nombres)
        form_id.addRow("Primer apellido:", self.in_ap1)
        form_id.addRow("Segundo apellido:", self.in_ap2)
        form_id.addRow("Fecha de nacimiento:", self.in_fnac)
        form_id.addRow("Género:", self.cb_genero)

        # Contacto
        box_ct = QGroupBox("Contacto")
        form_ct = QFormLayout(box_ct); form_ct.setLabelAlignment(Qt.AlignRight)
        self.in_tel = QLineEdit();      self.in_tel.setPlaceholderText("Teléfono principal *")
        self.in_wa = QLineEdit();       self.in_wa.setPlaceholderText("WhatsApp (opcional)")
        self.in_mail = QLineEdit();     self.in_mail.setPlaceholderText("Correo (opcional)")
        self.in_ciudad = QLineEdit();   self.in_ciudad.setPlaceholderText("Ciudad (opcional)")
        self.in_estado = QLineEdit();   self.in_estado.setPlaceholderText("Estado (opcional)")

        self.chk_wa_igual = QCheckBox("WhatsApp igual al teléfono")
        self.chk_wa_igual.stateChanged.connect(self._sync_whatsapp)

        form_ct.addRow("Teléfono:", self.in_tel)
        form_ct.addRow("", self.chk_wa_igual)
        form_ct.addRow("WhatsApp:", self.in_wa)
        form_ct.addRow("Correo:", self.in_mail)
        form_ct.addRow("Ciudad:", self.in_ciudad)
        form_ct.addRow("Estado:", self.in_estado)

        lay.addWidget(box_id)
        lay.addWidget(box_ct)
        lay.addStretch(1)
        return w

    def _tab_preferencias(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(12)

        box_pref = QGroupBox("Preferencias del cliente")
        form_p = QFormLayout(box_pref); form_p.setLabelAlignment(Qt.AlignRight)
        self.cb_artista = QComboBox(); self.cb_artista.addItems(["(Sin preferencia)", "Dylan", "Saúl", "Mariana"])
        self.lst_estilos = QListWidget(); self.lst_estilos.setSelectionMode(QListWidget.MultiSelection)
        for estilo in ["Línea fina", "Realismo", "Tradicional", "Acuarela", "Geométrico", "Blackwork"]:
            QListWidgetItem(estilo, self.lst_estilos)
        self.lst_zonas = QListWidget(); self.lst_zonas.setSelectionMode(QListWidget.MultiSelection)
        for zona in ["Brazo", "Antebrazo", "Pierna", "Espalda", "Pecho", "Muñeca", "Tobillo"]:
            QListWidgetItem(zona, self.lst_zonas)

        self.cb_origen = QComboBox(); self.cb_origen.addItems(["Instagram", "TikTok", "Google", "Referido", "Walk-in", "Otro"])
        self.chk_recordatorios = QCheckBox("Acepta recibir recordatorios")
        self.chk_promos = QCheckBox("Acepta promociones (WhatsApp/Email)")

        form_p.addRow("Artista preferido:", self.cb_artista)
        form_p.addRow("Estilos de interés:", self.lst_estilos)
        form_p.addRow("Zonas de interés:", self.lst_zonas)
        form_p.addRow("¿Cómo nos conoció?", self.cb_origen)
        form_p.addRow("", self.chk_recordatorios)
        form_p.addRow("", self.chk_promos)

        lay.addWidget(box_pref)
        lay.addStretch(1)
        return w

    def _tab_salud(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(12)

        box_s = QGroupBox("Tamizaje de salud (básico)")
        v = QVBoxLayout(box_s)
        self.chk_alergias = QCheckBox("Alergias (látex, lidocaína, pigmentos, antibióticos)")
        self.chk_diabetes = QCheckBox("Diabetes")
        self.chk_coagulacion = QCheckBox("Trastorno de coagulación / hemofilia")
        self.chk_epilepsia = QCheckBox("Epilepsia")
        self.chk_cardiaco = QCheckBox("Condiciones cardiacas")
        self.chk_anticoagulantes = QCheckBox("Anticoagulantes / Accutane (12m)")
        self.chk_emb_lact = QCheckBox("Embarazo / lactancia")
        self.chk_sustancias = QCheckBox("Alcohol/drogas en 24–48h")
        self.chk_derm = QCheckBox("Problemas dermatológicos en la zona")

        for c in [self.chk_alergias, self.chk_diabetes, self.chk_coagulacion, self.chk_epilepsia,
                  self.chk_cardiaco, self.chk_anticoagulantes, self.chk_emb_lact, self.chk_sustancias, self.chk_derm]:
            v.addWidget(c)

        self.txt_salud_obs = QTextEdit(); self.txt_salud_obs.setPlaceholderText("Observaciones (opcional)…")
        v.addWidget(self.txt_salud_obs)

        lay.addWidget(box_s)
        lay.addStretch(1)
        return w

    def _tab_consentimientos(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(12)

        box_c = QGroupBox("Consentimientos")
        v = QVBoxLayout(box_c)
        self.chk_consent_info = QCheckBox("He leído y acepto el consentimiento informado *")
        self.chk_uso_imagen = QCheckBox("Autorizo el uso de imágenes con fines de portafolio/redes")
        self.chk_datos = QCheckBox("Acepto la política de datos personales")
        v.addWidget(self.chk_consent_info)
        v.addWidget(self.chk_uso_imagen)
        v.addWidget(self.chk_datos)

        box_tutor = QGroupBox("Tutor (solo si es menor de edad)")
        form_t = QFormLayout(box_tutor); form_t.setLabelAlignment(Qt.AlignRight)
        self.in_tutor_nombre = QLineEdit(); self.in_tutor_nombre.setPlaceholderText("Nombre completo del tutor")
        self.in_tutor_tel = QLineEdit();    self.in_tutor_tel.setPlaceholderText("Teléfono del tutor")
        form_t.addRow("Nombre del tutor:", self.in_tutor_nombre)
        form_t.addRow("Teléfono del tutor:", self.in_tutor_tel)

        lay.addWidget(box_c)
        lay.addWidget(box_tutor)
        lay.addStretch(1)
        return w

    def _tab_emergencia(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w); form.setLabelAlignment(Qt.AlignRight)
        self.in_emerg_nombre = QLineEdit(); self.in_emerg_nombre.setPlaceholderText("Nombre")
        self.in_emerg_rel = QLineEdit();    self.in_emerg_rel.setPlaceholderText("Relación (madre, amigo, etc.)")
        self.in_emerg_tel = QLineEdit();    self.in_emerg_tel.setPlaceholderText("Teléfono")
        form.addRow("Nombre:", self.in_emerg_nombre)
        form.addRow("Relación:", self.in_emerg_rel)
        form.addRow("Teléfono:", self.in_emerg_tel)
        return w

    def _tab_notas_archivos(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(12)
        self.txt_notas = QTextEdit(); self.txt_notas.setPlaceholderText("Notas internas…")
        lbl_arch = QLabel("Archivos (próximamente: subir referencias, identidad, etc.)")
        lbl_arch.setObjectName("Hint")
        lay.addWidget(self.txt_notas)
        lay.addWidget(lbl_arch)
        lay.addStretch(1)
        return w

    # ---------- Helpers ----------
    def _sync_whatsapp(self, state):
        if self.chk_wa_igual.isChecked():
            self.in_wa.setText(self.in_tel.text())
            # si se edita el teléfono, sincroniza
            self.in_tel.textChanged.connect(self._copy_tel_to_wa)
        else:
            try:
                self.in_tel.textChanged.disconnect(self._copy_tel_to_wa)
            except Exception:
                pass

    def _copy_tel_to_wa(self, _):
        self.in_wa.setText(self.in_tel.text())

    def _wire_min_validation(self):
        def update_enabled():
            obligatorios_ok = bool(self.in_nombres.text().strip()) and \
                              bool(self.in_ap1.text().strip()) and \
                              bool(self.in_tel.text().strip()) and \
                              self.chk_consent_info.isChecked()
            self.btn_guardar.setEnabled(obligatorios_ok)
            self.btn_guardar_agendar.setEnabled(obligatorios_ok)

        for w in [self.in_nombres, self.in_ap1, self.in_tel]:
            w.textChanged.connect(update_enabled)
        self.chk_consent_info.stateChanged.connect(update_enabled)
        update_enabled()


def make_simple_page(nombre: str) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(40, 40, 40, 40)
    title = QLabel(nombre)
    title.setObjectName("H1")
    lay.addWidget(title, alignment=Qt.AlignCenter)
    return w


# -------------------- Ventana Principal --------------------
class MainWindow(QMainWindow):
    solicitar_switch_user = pyqtSignal()  # para volver al login

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TattooStudio")
        self.setMinimumSize(1200, 720)

        # Topbar
        topbar = QFrame(); topbar.setObjectName("Topbar")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(16, 12, 16, 12)
        tb.setSpacing(8)

        brand = QLabel("TattooStudio"); brand.setObjectName("Brand")
        tb.addWidget(brand, alignment=Qt.AlignLeft)

        # Navegación (centro)
        nav_box = QWidget()
        nav = QHBoxLayout(nav_box); nav.setContentsMargins(0, 0, 0, 0); nav.setSpacing(8)

        self.btn_studio   = self._pill("Estudio")
        self.btn_sched    = self._pill("Agenda")
        self.btn_clients  = self._pill("Clientes")
        self.btn_staff    = self._pill("Personal")
        self.btn_reports  = self._pill("Reportes")
        self.btn_forms    = self._pill("Formularios")

        for b in (self.btn_studio, self.btn_sched, self.btn_clients, self.btn_staff, self.btn_reports, self.btn_forms):
            nav.addWidget(b)

        tb.addWidget(nav_box, stretch=1, alignment=Qt.AlignHCenter)

        # Separación visual antes del botón de usuario
        tb.addStretch(1)

        # Botón de usuario (derecha)
        self.btn_user = QToolButton()
        self.btn_user.setObjectName("UserButton")
        self.btn_user.setText("Dylan Bourjac")
        self.btn_user.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_user.setCheckable(True)  # para abrir/cerrar el panel
        self.btn_user.toggled.connect(self._toggle_user_panel)
        tb.addWidget(self.btn_user, alignment=Qt.AlignRight)

        # Panel desplegable del usuario
        self.user_panel = PanelUsuario(self)
        self.user_panel.cambiar_usuario.connect(self.solicitar_switch_user.emit)

        # Stack de páginas
        self.stack = QStackedWidget()

        self.studio_page = StudioPage()
        # Navegaciones desde portada
        self.studio_page.ir_nuevo_cliente.connect(lambda: self._ir(self.idx_nuevo_cliente))
        self.studio_page.ir_cliente_recurrente.connect(lambda: self._ir(self.idx_clientes))
        self.studio_page.ir_portafolios.connect(lambda: self._ir(self.idx_portafolios))
        self.studio_page.ir_fila.connect(lambda: self._ir(self.idx_fila))

        self.stack.addWidget(self.studio_page)                        # 0 Estudio
        self.idx_agenda       = self.stack.addWidget(make_simple_page("Agenda"))
        self.idx_clientes     = self.stack.addWidget(make_simple_page("Clientes"))
        self.idx_personal     = self.stack.addWidget(make_simple_page("Personal"))
        self.idx_reportes     = self.stack.addWidget(make_simple_page("Reportes"))
        self.idx_forms        = self.stack.addWidget(make_simple_page("Formularios"))
        self.idx_portafolios  = self.stack.addWidget(make_simple_page("Portafolios"))  # CTA
        self.idx_fila         = self.stack.addWidget(make_simple_page("Fila"))         # CTA
        self.idx_nuevo_cliente= self.stack.addWidget(NewClientPage())                  # NUEVO

        # Conexiones de navegación (topbar)
        self.btn_studio.clicked.connect(lambda: self._ir(0))
        self.btn_sched.clicked.connect(lambda: self._ir(self.idx_agenda))
        self.btn_clients.clicked.connect(lambda: self._ir(self.idx_clientes))
        self.btn_staff.clicked.connect(lambda: self._ir(self.idx_personal))
        self.btn_reports.clicked.connect(lambda: self._ir(self.idx_reportes))
        self.btn_forms.clicked.connect(lambda: self._ir(self.idx_forms))
        self.btn_studio.setChecked(True)

        # Status bar (sin selector de idioma)
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

        # Estilos
        self._qss()

    # ---- helpers ----
    def _pill(self, text) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setCheckable(True)
        b.setObjectName("PillNav")
        return b

    def _ir(self, idx: int):
        # Desmarcar todos, marcar el correspondiente si existe mapeo
        mapping = {
            0: self.btn_studio,
            self.idx_agenda: self.btn_sched,
            self.idx_clientes: self.btn_clients,
            self.idx_personal: self.btn_staff,
            self.idx_reportes: self.btn_reports,
            self.idx_forms: self.btn_forms,
        }
        for btn in (self.btn_studio, self.btn_sched, self.btn_clients, self.btn_staff, self.btn_reports, self.btn_forms):
            btn.setChecked(False)
        if idx in mapping:
            mapping[idx].setChecked(True)
        self.stack.setCurrentIndex(idx)

    def _toggle_user_panel(self, checked: bool):
        if checked:
            # Posicionar panel justo bajo el botón de usuario
            self.user_panel.adjustSize()
            btn = self.btn_user
            global_pos = btn.mapToGlobal(btn.rect().bottomRight())
            panel_w = self.user_panel.width()
            # lo alineamos al borde derecho del botón
            self.user_panel.move(QPoint(global_pos.x() - panel_w, global_pos.y()))
            self.user_panel.show()
        else:
            self.user_panel.hide()

    def mousePressEvent(self, event):
        # Si haces clic fuera del panel, lo cerramos y desmarcamos el botón
        if self.user_panel.isVisible() and not self.user_panel.geometry().contains(event.globalPos()):
            self.user_panel.hide()
            self.btn_user.setChecked(False)
        super().mousePressEvent(event)

    def _qss(self):
        self.setStyleSheet("""
        QWidget { font-family: 'Segoe UI', Arial; font-size: 11pt; }
        #Topbar { background: #ffffff; border-bottom: 1px solid #eee; }
        #Brand { font-weight: 700; font-size: 18px; padding-left: 4px; }
        #H1 { font-size: 32px; font-weight: 800; letter-spacing: -0.5px; }
        #Logo { background: transparent; }

        QToolButton#PillNav {
            background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 10px;
            padding: 6px 12px; color: #111;
        }
        QToolButton#PillNav:hover { background: #e5e7eb; }
        QToolButton#PillNav:checked {
            background: #111; color: #fff; border-color: #111;
        }

        QPushButton#CTA {
            background: #2b2b2b; color: #fff; border: none; border-radius: 10px;
            padding: 10px 16px; font-weight: 600;
        }
        QPushButton#CTA:hover { background: #1f1f1f; }

        QPushButton#GhostSmall {
            background: #f3f4f6; color: #111; border: 1px solid #e5e7eb;
            border-radius: 8px; padding: 4px 10px; text-align: left;
        }
        QPushButton#GhostSmall:hover { background: #e5e7eb; }

        /* Botón de usuario (avatar textual + nombre) */
        QToolButton#UserButton {
            background: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px;
            padding: 6px 10px; color: #111;
        }
        QToolButton#UserButton:hover { background: #f6f6f6; }

        /* Panel del usuario (popup) */
        QFrame#UserPanel {
            background: #ffffff; border: 1px solid #e5e7eb; border-radius: 10px;
        }
        QLabel#UserName { font-weight: 700; }
        QLabel#UserMeta  { color: #555; }

        QLabel#Hint { color: #666; font-size: 10pt; }

        /* ---- Estilos para formularios del Nuevo Cliente ---- */
        QLineEdit, QTextEdit, QDateEdit, QComboBox {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 8px 10px;
            background: #fff;
            color: #111;
        }
        QLineEdit:focus, QTextEdit:focus, QDateEdit:focus, QComboBox:focus {
            border: 1px solid #111;
            outline: none;
        }

        QGroupBox {
            border: 1px solid #eee;
            border-radius: 8px;
            margin-top: 10px;
            padding: 8px 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: #222;
            font-weight: 600;
        }

        QTabWidget::pane { border: 1px solid #eee; border-radius: 8px; }
        QTabBar::tab {
            background: #f3f4f6; border: 1px solid #e5e7eb; border-bottom: none;
            padding: 6px 12px; margin-right: 4px; border-top-left-radius: 8px; border-top-right-radius: 8px;
        }
        QTabBar::tab:selected { background: #fff; border-color: #e5e7eb; }
        """)


# -------------------- Orquestación --------------------
def main():
    app = QApplication(sys.argv)
    login = LoginWindow()
    mainw = MainWindow()

    # flujo: login -> principal
    login.acceso_solicitado.connect(lambda: (login.hide(), mainw.show()))
    # flujo: panel usuario -> cambiar usuario -> login
    mainw.solicitar_switch_user.connect(lambda: (mainw.hide(), login.show(), mainw.btn_user.setChecked(False)))

    login.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
