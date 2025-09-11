# ui/pages/new_client.py
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QGroupBox, QFormLayout,
    QLineEdit, QDateEdit, QComboBox, QCheckBox, QTextEdit, QListWidget,
    QListWidgetItem, QHBoxLayout, QPushButton
)

class NewClientPage(QWidget):
    """
    Formulario (mock) de Nuevo Cliente:
    - UI únicamente (sin guardado real).
    - Tabs: Identificación & Contacto / Preferencias / Salud / Consentimientos / Emergencia / Notas & Archivos
    - Botones al pie: Guardar / Guardar y agendar / Cancelar
    Cambios:
      * Eliminado WhatsApp (campo + checkbox) y reemplazado por Instagram
      * Botón '← Volver' que emite la señal 'volver_atras'
    """
    # Señal para que MainWindow navegue hacia atrás
    volver_atras = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Asegura que todos los QLabel se vean sin recuadro de fondo
        self.setStyleSheet("QLabel { background: transparent; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 16, 16)
        root.setSpacing(12)

        # ---- Barra superior: Volver + Título ----
        top = QHBoxLayout(); top.setSpacing(8)
        self.btn_back = QPushButton("← Volver")
        self.btn_back.setObjectName("GhostSmall")
        self.btn_back.setMinimumHeight(32)
        self.btn_back.clicked.connect(self.volver_atras.emit)
        top.addWidget(self.btn_back)
        top.addStretch(1)
        root.addLayout(top)

        title = QLabel("Nuevo cliente")
        title.setObjectName("H1")
        root.addWidget(title)

        # ---- Tabs ----
        tabs = QTabWidget()
        tabs.addTab(self._tab_identificacion_contacto(), "Identificación")
        tabs.addTab(self._tab_preferencias(), "Preferencias")
        tabs.addTab(self._tab_salud(), "Salud")
        tabs.addTab(self._tab_consentimientos(), "Consentimientos")
        tabs.addTab(self._tab_emergencia(), "Emergencia")
        tabs.addTab(self._tab_notas_archivos(), "Notas")
        root.addWidget(tabs, stretch=1)

        # ---- Barra de botones (footer) ----
        btn_bar = QHBoxLayout()
        btn_bar.addStretch(1)
        self.btn_guardar = QPushButton("Guardar"); self.btn_guardar.setObjectName("CTA")
        self.btn_guardar_agendar = QPushButton("Guardar y agendar"); self.btn_guardar_agendar.setObjectName("CTA")
        self.btn_cancelar = QPushButton("Cancelar"); self.btn_cancelar.setObjectName("GhostSmall")
        for b in (self.btn_guardar, self.btn_guardar_agendar, self.btn_cancelar):
            b.setMinimumHeight(36)
            btn_bar.addWidget(b)
        root.addLayout(btn_bar)

        # Validación mínima para habilitar guardado
        self._wire_min_validation()

    # ---------- Tabs ----------
    def _tab_identificacion_contacto(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(12)

        # ----- Identificación -----
        box_id = QGroupBox("Identificación")
        form_id = QFormLayout(box_id); form_id.setLabelAlignment(Qt.AlignRight)
        self.in_nombres = QLineEdit();      self.in_nombres.setPlaceholderText("Nombre(s) *")
        self.in_ap1 = QLineEdit();          self.in_ap1.setPlaceholderText("Primer apellido *")
        self.in_ap2 = QLineEdit();          self.in_ap2.setPlaceholderText("Segundo apellido (opcional)")
        self.in_fnac = QDateEdit();         self.in_fnac.setCalendarPopup(True)
        self.in_fnac.setDisplayFormat("dd/MM/yyyy"); self.in_fnac.setDate(QDate.currentDate().addYears(-18))
        self.cb_genero = QComboBox()
        self.cb_genero.addItems([
            "Femenino", "Masculino", "Prefiero no decir",
            "No binario", "Agénero", "Género fluido",
            "No conforme con el género", "Queer", "Maverique",
            "Transfemenino", "Transmasculino", "Hombre trans", "Mujer trans",
            "Intergénero", "Poligénero",
            "En exploración", "Es una larga historia", "Depende del día",
            "Sorpréndeme"])

        form_id.addRow("Nombre(s):", self.in_nombres)
        form_id.addRow("Primer apellido:", self.in_ap1)
        form_id.addRow("Segundo apellido:", self.in_ap2)
        form_id.addRow("Fecha de nacimiento:", self.in_fnac)
        form_id.addRow("Género:", self.cb_genero)

        # ----- Contacto -----
        box_ct = QGroupBox("Contacto")
        form_ct = QFormLayout(box_ct); form_ct.setLabelAlignment(Qt.AlignRight)
        self.in_tel = QLineEdit();    self.in_tel.setPlaceholderText("Teléfono principal *")
        self.in_ig = QLineEdit();     self.in_ig.setPlaceholderText("Instagram (opcional)")
        self.in_mail = QLineEdit();   self.in_mail.setPlaceholderText("Correo (opcional)")
        self.in_ciudad = QLineEdit(); self.in_ciudad.setPlaceholderText("Ciudad (opcional)")
        self.in_estado = QLineEdit(); self.in_estado.setPlaceholderText("Estado (opcional)")

        # (Se eliminó el checkbox 'WhatsApp igual al teléfono' y el campo WhatsApp)
        form_ct.addRow("Teléfono:", self.in_tel)
        form_ct.addRow("Instagram:", self.in_ig)
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
        self.cb_artista = QComboBox(); self.cb_artista.addItems(["Sin preferencia", "Dylan", "Jesús", "Pablo", "Alex"])

        self.lst_estilos = QListWidget(); self.lst_estilos.setSelectionMode(QListWidget.MultiSelection)
        for estilo in ["Línea fina", "Realismo", "Tradicional", "Acuarela", "Geométrico", "Blackwork", "Anime"]:
            QListWidgetItem(estilo, self.lst_estilos)

        self.lst_zonas = QListWidget(); self.lst_zonas.setSelectionMode(QListWidget.MultiSelection)
        for zona in ["Brazo", "Antebrazo", "Pierna", "Espalda", "Pecho", "Muñeca", "Tobillo"]:
            QListWidgetItem(zona, self.lst_zonas)

        self.cb_origen = QComboBox()
        self.cb_origen.addItems(["Instagram", "TikTok", "Google", "Referido", "Otro"])

        form_p.addRow("Artista preferido:", self.cb_artista)
        form_p.addRow("Estilos favoritos:", self.lst_estilos)
        form_p.addRow("Zonas de interés:", self.lst_zonas)
        form_p.addRow("¿Cómo nos conoció?", self.cb_origen)

        lay.addWidget(box_pref)
        lay.addStretch(1)
        return w

    def _tab_salud(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(12)

        box_s = QGroupBox("Tamizaje de salud")
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

        self.txt_salud_obs = QTextEdit(); self.txt_salud_obs.setPlaceholderText("Observaciones")
        v.addWidget(self.txt_salud_obs)

        lay.addWidget(box_s)
        lay.addStretch(1)
        return w

    def _tab_consentimientos(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(12)

        box_c = QGroupBox("Consentimientos")
        v = QVBoxLayout(box_c)
        self.chk_consent_info = QCheckBox("He leído y acepto el consentimiento informado*")
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
    def _wire_min_validation(self):
        """Habilita los CTAs sólo si: nombre, primer apellido, teléfono y consentimiento informado están completos."""
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
