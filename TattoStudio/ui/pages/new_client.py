from __future__ import annotations

from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QGroupBox, QFormLayout,
    QLineEdit, QDateEdit, QComboBox, QCheckBox, QTextEdit, QListWidget,
    QListWidgetItem, QHBoxLayout, QPushButton, QMessageBox, QSizePolicy,
    QDialog
)

# BD / ORM
from sqlalchemy.orm import Session
from data.db.session import SessionLocal
from data.models.client import Client
from data.models.artist import Artist
from datetime import datetime

# RBAC (UI helper)
from ui.pages.common import ensure_permission

import unicodedata


def _norm(s: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", s or "")
        if unicodedata.category(ch) != "Mn"
    ).casefold().strip()


class NewClientPage(QWidget):
    """
    Formulario de Nuevo Cliente (popup):
    - Tabs: Identificación / Preferencias / Salud / Consentimientos / Emergencia / Notas
    - Botones al pie: Guardar / Guardar y agendar / Cancelar
    - Señales:
        * volver_atras()      -> el contenedor (QDialog) cierra
        * cliente_creado(int) -> id del cliente insertado en BD
    """
    volver_atras = pyqtSignal()
    cliente_creado = pyqtSignal(int)

    def __init__(self):
        super().__init__()

        # Base alta para evitar compresión
        self.setMinimumHeight(860)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # Asegura que todos los QLabel se vean sin recuadro de fondo
        self.setStyleSheet("QLabel { background: transparent; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 16, 16)
        root.setSpacing(12)

        # ---- Título centrado ----
        title = QLabel("Nuevo cliente")
        title.setObjectName("H1")
        title.setAlignment(Qt.AlignHCenter)
        title.setStyleSheet("font-size: 18pt;")
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
            b.setMinimumHeight(44)
        self.btn_cancelar.setProperty("ctaLike", True)

        btn_bar.addWidget(self.btn_guardar)
        btn_bar.addWidget(self.btn_guardar_agendar)
        btn_bar.addWidget(self.btn_cancelar)
        self.setLayoutDirection(Qt.LeftToRight)
        root.addLayout(btn_bar)

        # Wire de acciones (con gates de permiso en los handlers)
        self.btn_guardar.clicked.connect(lambda: self._on_guardar(open_schedule=False))
        self.btn_guardar_agendar.clicked.connect(lambda: self._on_guardar(open_schedule=True))
        self.btn_cancelar.clicked.connect(self.volver_atras.emit)

        # Validación mínima + resaltado visual
        self._wire_min_validation()

    # --- Forzar que el QDialog contenedor abra ALTO (sin tocar main_window) ---
    def showEvent(self, ev):
        super().showEvent(ev)
        # Sube por la jerarquía buscando el QDialog contenedor
        p = self.parentWidget()
        while p and not isinstance(p, QDialog):
            p = p.parentWidget()
        if isinstance(p, QDialog):
            p.setMinimumSize(980, 960)
            p.resize(1060, 1000)
            p.setSizeGripEnabled(True)

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
        """Habilita los CTAs sólo si: nombre, primer apellido, teléfono y consentimiento informado están completos.
           Además, marca visualmente los campos requeridos vacíos."""
        def update_enabled():
            obligatorios_ok = bool(self.in_nombres.text().strip()) and \
                              bool(self.in_ap1.text().strip()) and \
                              bool(self.in_tel.text().strip()) and \
                              self.chk_consent_info.isChecked()
            self.btn_guardar.setEnabled(obligatorios_ok)
            self.btn_guardar_agendar.setEnabled(obligatorios_ok)

            # resalta campos vacíos
            def mark(widget, ok: bool):
                widget.setProperty("invalid", not ok)
                widget.style().unpolish(widget); widget.style().polish(widget)

            mark(self.in_nombres, bool(self.in_nombres.text().strip()))
            mark(self.in_ap1, bool(self.in_ap1.text().strip()))
            mark(self.in_tel, bool(self.in_tel.text().strip()))

        for w in [self.in_nombres, self.in_ap1, self.in_tel]:
            w.textChanged.connect(update_enabled)
        self.chk_consent_info.stateChanged.connect(update_enabled)
        update_enabled()

    # ============================================================
    # Guardado real + Permisos
    # ============================================================
    def _collect_payload(self) -> dict:
        """Convierte inputs UI → dict para insertar. (Sólo campos que existan se asignarán)."""
        nombres = self.in_nombres.text().strip()
        ap1 = self.in_ap1.text().strip()
        ap2 = self.in_ap2.text().strip()
        full_name = " ".join([p for p in [nombres, ap1, ap2] if p]).strip()

        # Preferencias → serializar como metadatos en notas
        estilos = [self.lst_estilos.item(i).text() for i in range(self.lst_estilos.count()) if self.lst_estilos.item(i).isSelected()]
        zonas   = [self.lst_zonas.item(i).text()   for i in range(self.lst_zonas.count())   if self.lst_zonas.item(i).isSelected()]
        source  = self.cb_origen.currentText()
        meta_line = ""
        if estilos or zonas or source:
            meta_line = f"\nMETA_PREFS|styles={','.join(estilos)};zones={','.join(zonas)};source={source}"

        notes_user = self.txt_notas.toPlainText().strip()
        notes = (notes_user + meta_line).strip() if (notes_user or meta_line) else None

        payload = {
            "name": full_name,
            "phone": self.in_tel.text().strip() or None,
            "email": self.in_mail.text().strip() or None,
            "instagram": self.in_ig.text().strip() or None,
            "city": self.in_ciudad.text().strip() or None,
            "state": self.in_estado.text().strip() or None,
            "notes": notes,
            "gender": self.cb_genero.currentText(),
            "birthdate": self.in_fnac.date().toPyDate(),
            "consent_info": bool(self.chk_consent_info.isChecked()),
            "consent_image": bool(self.chk_uso_imagen.isChecked()),
            "consent_data": bool(self.chk_datos.isChecked()),
            "emergency_name": self.in_emerg_nombre.text().strip() or None,
            "emergency_relation": self.in_emerg_rel.text().strip() or None,
            "emergency_phone": self.in_emerg_tel.text().strip() or None,
            # Salud
            "health_allergies": bool(self.chk_alergias.isChecked()),
            "health_diabetes": bool(self.chk_diabetes.isChecked()),
            "health_coagulation": bool(self.chk_coagulacion.isChecked()),
            "health_epilepsy": bool(self.chk_epilepsia.isChecked()),
            "health_cardiac": bool(self.chk_cardiaco.isChecked()),
            "health_anticoagulants": bool(self.chk_anticoagulantes.isChecked()),
            "health_preg_lact": bool(self.chk_emb_lact.isChecked()),
            "health_substances": bool(self.chk_sustancias.isChecked()),
            "health_derm": bool(self.chk_derm.isChecked()),
            "health_obs": self.txt_salud_obs.toPlainText().strip() or None,
        }
        return payload

    def _find_artist_id_by_name(self, db, name: str) -> int | None:
        if not name or _norm(name) == "sin preferencia":
            return None
        target = _norm(name).split()[0]  # primer token del combo (ej. "jesus")
        winner_id = None
        for a in db.query(Artist).all():
            full = _norm(getattr(a, "name", "") or "")
            first = (full.split()[0] if full else "")
            if full == _norm(name) or first == target:
                aid = getattr(a, "id", None)
                if aid is not None and (winner_id is None or aid < winner_id):
                    winner_id = aid
        return winner_id

    def _save_client(self, db: Session, payload: dict, preferred_artist_name: str | None) -> int:
        """
        Inserta un Client con los campos que existan en el modelo.
        Usa hasattr para asignar solo lo que tu esquema soporte.
        Devuelve el id insertado.
        """
        obj = Client()

        # preferred_artist_id a partir del combo
        pref_id = self._find_artist_id_by_name(db, preferred_artist_name or "")
        if pref_id is not None and hasattr(obj, "preferred_artist_id"):
            try:
                setattr(obj, "preferred_artist_id", pref_id)
            except Exception:
                pass

        # Asignación segura campo a campo
        for key, value in payload.items():
            if hasattr(obj, key):
                try:
                    setattr(obj, key, value)
                except Exception:
                    pass

        # Garantiza campos mínimos conocidos
        if not getattr(obj, "name", None):
            raise ValueError("Nombre del cliente vacío.")
        if hasattr(obj, "is_active") and getattr(obj, "is_active", None) is None:
            setattr(obj, "is_active", True)

        # created_at: fallback por si la columna es NOT NULL y la BD no tiene default
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            try:
                setattr(obj, "created_at", datetime.now())
            except Exception:
                pass

        db.add(obj)
        db.commit()
        db.refresh(obj)
        return getattr(obj, "id")

    def _on_guardar(self, open_schedule: bool):
        """
        Handler de 'Guardar' y 'Guardar y agendar':
        - Gate de permisos (clients.create).
        - Inserción en BD.
        - Emite cliente_creado(id) y deja que MainWindow refresque/navegue.
        """
        if not ensure_permission(self, "clients", "create"):
            return

        # Validación extra (defensiva)
        if not self.in_nombres.text().strip() or not self.in_ap1.text().strip() or not self.in_tel.text().strip():
            QMessageBox.warning(self, "Validación", "Por favor completa los campos obligatorios.")
            return
        if not self.chk_consent_info.isChecked():
            QMessageBox.warning(self, "Consentimiento", "Debes aceptar el consentimiento informado.")
            return

        payload = self._collect_payload()
        pref_name = self.cb_artista.currentText() if self.cb_artista.count() else None

        self._set_buttons_enabled(False)
        try:
            with SessionLocal() as db:  # type: Session
                client_id = self._save_client(db, payload, pref_name)
        except Exception as ex:
            QMessageBox.critical(self, "BD", f"No se pudo guardar el cliente:\n{ex}")
            self._set_buttons_enabled(True)
            return

        # Notificar (QMessageBox toma el QSS del tema)
        self.cliente_creado.emit(client_id)
        if open_schedule:
            QMessageBox.information(self, "Cliente creado", "Cliente guardado. Continúa para agendar su cita.")
        else:
            QMessageBox.information(self, "Cliente creado", "Cliente guardado exitosamente.")

        self._set_buttons_enabled(True)
        self.volver_atras.emit()  # el contenedor (QDialog) debe cerrar aquí

    def _set_buttons_enabled(self, enabled: bool):
        self.btn_guardar.setEnabled(enabled)
        self.btn_guardar_agendar.setEnabled(enabled)
        self.btn_cancelar.setEnabled(enabled)
