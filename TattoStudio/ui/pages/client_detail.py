from __future__ import annotations

# ============================================================
# client_detail.py — Ficha de cliente (BD real + RBAC + edición)
#
# Cambios en esta versión:
# - Admin puede editar/guardar sin fricción.
# - Assistant puede editar/guardar y eliminar con elevación (código maestro).
# - Artista no puede editar ni eliminar (solo lectura).
# - Botón Eliminar en rojo (fallback inline, y soporta QSS vía objectName "Danger").
# - Avatar recortado a círculo (con borde); admin siempre puede reemplazar;
#   assistant puede reemplazar si es dueño de la imagen o con elevación.
# - Señal cliente_cambiado() para que MainWindow/Clients recarguen la tabla.
# - Refrescos tras guardar/archivar/eliminar -> regresa a lista y actualiza.
# - Dirty check en edición.
# ============================================================

from typing import Optional, List, Tuple
from datetime import datetime
import os, json
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, QRectF
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPainterPath
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTextEdit, QListWidget, QListWidgetItem, QFrame, QGridLayout, QMessageBox,
    QGroupBox, QFormLayout, QCheckBox, QFileDialog, QLineEdit, QComboBox
)

from sqlalchemy.orm import Session
from sqlalchemy import asc
from sqlalchemy.exc import IntegrityError

from data.db.session import SessionLocal
from data.models.client import Client
from data.models.artist import Artist
from data.models.session_tattoo import TattooSession

from services.permissions import can
from services.contracts import get_current_user
from ui.pages.common import ensure_permission, request_elevation_if_needed


class ClientDetailPage(QWidget):
    back_to_list = pyqtSignal()
    cliente_cambiado = pyqtSignal()  # para refrescar tabla/lista

    # --------------------------------------------------------
    # Init
    # --------------------------------------------------------
    def __init__(self):
        super().__init__()
        self.setStyleSheet("QLabel { background: transparent; }")

        self._client: dict = {}
        self._client_db: Optional[Client] = None
        self._owner_artist_id: Optional[int] = None
        self._notes_dirty: bool = False
        self._any_dirty: bool = False
        self._avatar_owner_user_id: Optional[int] = None
        self._edit_mode: bool = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 8, 24, 24)  # top reducido
        root.setSpacing(8)

        # ===== Toolbar =====
        bar = QHBoxLayout(); bar.setSpacing(8)
        self.btn_back = QPushButton("← Volver")
        self.btn_back.setObjectName("GhostSmall")
        self.btn_back.setMinimumHeight(32)
        self.btn_back.clicked.connect(self._on_back_clicked)
        bar.addWidget(self.btn_back)

        self.btn_edit = QPushButton("Editar")
        self.btn_edit.setObjectName("GhostSmall")
        self.btn_edit.setMinimumHeight(32)
        self.btn_edit.clicked.connect(self._enter_edit_mode)
        bar.addWidget(self.btn_edit)

        self.btn_save = QPushButton("Guardar")
        self.btn_save.setObjectName("CTA")
        self.btn_save.setMinimumHeight(32)
        self.btn_save.clicked.connect(self._save_changes)
        bar.addWidget(self.btn_save)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("GhostSmall")
        self.btn_cancel.setProperty("ctaLike", True)  # pill como los CTA
        self.btn_cancel.setMinimumHeight(32)
        self.btn_cancel.clicked.connect(self._cancel_edit)
        bar.addWidget(self.btn_cancel)

        bar.addStretch(1)

        self.btn_delete = QPushButton("Eliminar")
        self.btn_delete.setObjectName("Danger")  # para QSS (si lo agregas)
        self.btn_delete.setMinimumHeight(32)
        # Fallback inline si tu QSS aún no define "Danger"
        self.btn_delete.setStyleSheet(
            "QPushButton#Danger{background:#b91c1c;color:white;border-radius:12px;padding:0 14px;}"
            "QPushButton#Danger:hover{background:#dc2626;}"
            "QPushButton#Danger:disabled{background:#6b7280;color:#cbd5e1;}"
        )
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        bar.addWidget(self.btn_delete)

        root.addLayout(bar)

        # ===== Header card =====
        self.header = QFrame()
        self.header.setObjectName("Card")
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(12, 12, 12, 12)
        hl.setSpacing(12)

        # Avatar + botón cambiar
        box_avatar = QVBoxLayout(); box_avatar.setSpacing(6)
        self.avatar = QLabel()
        self.avatar.setFixedSize(72, 72)
        self.avatar.setPixmap(self._make_avatar_pixmap(72, "C"))
        box_avatar.addWidget(self.avatar, 0, Qt.AlignTop)

        self.btn_avatar = QPushButton("Cambiar foto")
        self.btn_avatar.setObjectName("GhostSmall")
        self.btn_avatar.setMinimumHeight(24)
        self.btn_avatar.clicked.connect(self._on_change_avatar)
        box_avatar.addWidget(self.btn_avatar, 0, Qt.AlignTop)
        hl.addLayout(box_avatar, 0)

        # Columna datos (labels + inputs ocultos para edición)
        info = QVBoxLayout(); info.setSpacing(4)

        # Nombre
        self.name_lbl = QLabel("Cliente")
        self.name_lbl.setStyleSheet("font-weight:700; font-size:16pt;")
        info.addWidget(self.name_lbl)

        self.name_edit = QLineEdit()
        self.name_edit.setVisible(False)
        self.name_edit.textChanged.connect(self._mark_dirty)
        info.addWidget(self.name_edit)

        # Badges (placeholder; estado/etiqueta visual)
        badges = QHBoxLayout(); badges.setSpacing(6)
        self.badge_tag = QLabel(" — ")
        self.badge_tag.setObjectName("BadgeRole")
        self.badge_state = QLabel(" — ")
        self.badge_state.setObjectName("BadgeState")
        badges.addWidget(self.badge_tag)
        badges.addWidget(self.badge_state)
        badges.addStretch(1)
        info.addLayout(badges)

        # Grid de contacto / meta
        grid = QGridLayout(); grid.setHorizontalSpacing(16); grid.setVerticalSpacing(4)

        # Tel / Email / IG (labels + edits)
        self.phone_lbl = QLabel("—");  self.phone_edit = QLineEdit();  self.phone_edit.setVisible(False);  self.phone_edit.textChanged.connect(self._mark_dirty)
        self.email_lbl = QLabel("—");  self.email_edit = QLineEdit();  self.email_edit.setVisible(False);  self.email_edit.textChanged.connect(self._mark_dirty)
        self.ig_lbl    = QLabel("—");  self.ig_edit    = QLineEdit();  self.ig_edit.setVisible(False);      self.ig_edit.textChanged.connect(self._mark_dirty)

        grid.addWidget(QLabel("Teléfono:"), 0, 0, Qt.AlignRight)
        grid.addWidget(self.phone_lbl,      0, 1); grid.addWidget(self.phone_edit, 0, 1)
        grid.addWidget(QLabel("Email:"),    1, 0, Qt.AlignRight)
        grid.addWidget(self.email_lbl,      1, 1); grid.addWidget(self.email_edit, 1, 1)
        grid.addWidget(QLabel("Instagram:"), 2, 0, Qt.AlignRight)
        grid.addWidget(self.ig_lbl,          2, 1); grid.addWidget(self.ig_edit, 2, 1)

        # Artista asignado (label + combo)
        self.artist_lbl  = QLabel("—")
        self.artist_combo = QComboBox(); self.artist_combo.setVisible(False); self.artist_combo.currentIndexChanged.connect(self._mark_dirty)

        grid.addWidget(QLabel("Artista asignado:"), 0, 2, Qt.AlignRight)
        grid.addWidget(self.artist_lbl,             0, 3)
        grid.addWidget(self.artist_combo,           0, 3)

        # Próxima cita (solo lectura)
        self.next_lbl    = QLabel("—")
        grid.addWidget(QLabel("Próxima cita:"), 1, 2, Qt.AlignRight)
        grid.addWidget(self.next_lbl,           1, 3)

        info.addLayout(grid)
        hl.addLayout(info, 1)
        root.addWidget(self.header)

        # ===== Tabs (en card) =====
        tabs_card = QFrame()
        tabs_card.setObjectName("Card")
        tl = QVBoxLayout(tabs_card)
        tl.setContentsMargins(12, 12, 12, 12)
        tl.setSpacing(8)

        self.tabs = QTabWidget()
        tl.addWidget(self.tabs)

        # Perfil
        self.tab_perfil = QWidget(); self._mk_perfil(self.tab_perfil)

        # Citas
        self.tab_citas  = QWidget(); self._mk_list(self.tab_citas, [])

        # Galería
        self.tab_files  = QWidget(); self._mk_placeholder(self.tab_files, "Galería (placeholder)")

        # Notas
        self.tab_notas  = QWidget(); self._mk_text(self.tab_notas, "Notas internas (placeholder)")

        # Preferencias
        self.tab_pref   = QWidget(); self._mk_pref(self.tab_pref)

        # Salud
        self.tab_salud  = QWidget(); self._mk_salud(self.tab_salud)

        # Consentimientos
        self.tab_consent= QWidget(); self._mk_consent(self.tab_consent)

        # Emergencia
        self.tab_emerg  = QWidget(); self._mk_emerg(self.tab_emerg)

        self.tabs.addTab(self.tab_perfil, "Perfil")
        self.tabs.addTab(self.tab_citas,  "Citas")
        self.tabs.addTab(self.tab_files,  "Galería")
        self.tabs.addTab(self.tab_notas,  "Notas")
        self.tabs.addTab(self.tab_pref,   "Preferencias")
        self.tabs.addTab(self.tab_salud,  "Salud")
        self.tabs.addTab(self.tab_consent,"Consentimientos")
        self.tabs.addTab(self.tab_emerg,  "Emergencia")

        root.addWidget(tabs_card, 1)

        # Estado UI
        self._refresh_edit_buttons()

    # --------------------------------------------------------
    # Carga de datos
    # --------------------------------------------------------
    def load_client(self, client: dict):
        self._client = client or {}
        cid = client.get("id")
        name_hint = client.get("nombre") or client.get("name") or "—"

        self.name_lbl.setText(name_hint)
        self.name_edit.setText(name_hint)
        self.avatar.setPixmap(self._load_avatar_or_initials(cid, name_hint))
        self.badge_tag.setText(f" {client.get('etiquetas','—') or '—'} ")
        self.badge_state.setText(f" {client.get('estado','—') or '—'} ")
        self.phone_lbl.setText(client.get("tel") or "—"); self.phone_edit.setText(client.get("tel") or "")
        self.email_lbl.setText(client.get("email") or "—"); self.email_edit.setText(client.get("email") or "")
        self.ig_lbl.setText(client.get("ig") or client.get("instagram") or "—"); self.ig_edit.setText(client.get("ig") or client.get("instagram") or "")
        self.artist_lbl.setText(client.get("artista") or "—")
        self.next_lbl.setText(client.get("proxima") or "—")
        self._perfil_name.setText(name_hint)
        self._perfil_contact.setText(f"{client.get('tel','—')}  ·  {client.get('email','—')}")

        # Limpieza y estado
        self._reset_editable_tabs()
        self._any_dirty = False
        self._notes_dirty = False
        self._exit_edit_mode(silent=True)

        if not cid:
            self._apply_notes_permissions(owner_artist_id=None)
            self._set_citas_list([f'{client.get("proxima","—")} · {client.get("artista","—")}'])
            self._set_avatar_perm(None)
            return

        try:
            with SessionLocal() as db:  # type: Session
                self._client_db = db.query(Client).filter(Client.id == cid).one_or_none()
                if not self._client_db:
                    QMessageBox.warning(self, "Cliente", f"Cliente id={cid} no encontrado.")
                    self._apply_notes_permissions(owner_artist_id=None)
                    self._set_avatar_perm(None)
                    return

                # Header/contacto
                name = getattr(self._client_db, "name", None) or name_hint
                self.name_lbl.setText(name); self.name_edit.setText(name)
                self.avatar.setPixmap(self._load_avatar_or_initials(cid, name))
                phone = getattr(self._client_db, "phone", None)
                email = getattr(self._client_db, "email", None)
                ig    = getattr(self._client_db, "instagram", None)
                self.phone_lbl.setText(phone or "—"); self.phone_edit.setText(phone or "")
                self.email_lbl.setText(email or "—"); self.email_edit.setText(email or "")
                self.ig_lbl.setText(ig or "—");       self.ig_edit.setText(ig or "")
                self._perfil_name.setText(name)
                self._perfil_contact.setText(f"{phone or '—'}  ·  {email or '—'}")

                # Próxima/última cita
                now = datetime.now()
                next_session: Optional[TattooSession] = (
                    db.query(TattooSession)
                    .filter(TattooSession.client_id == cid, TattooSession.start >= now)
                    .order_by(asc(TattooSession.start))
                    .first()
                )
                last_session: Optional[TattooSession] = (
                    db.query(TattooSession)
                    .filter(TattooSession.client_id == cid, TattooSession.start < now)
                    .order_by(TattooSession.start.desc())
                    .first()
                )

                # “Dueño” para reglas 👤
                self._owner_artist_id = (
                    getattr(next_session, "artist_id", None)
                    if next_session else getattr(last_session, "artist_id", None)
                ) or getattr(self._client_db, "preferred_artist_id", None)

                # Artista asignado label + combo
                artist_name = "—"
                if self._owner_artist_id:
                    a = db.query(Artist).filter(Artist.id == self._owner_artist_id).one_or_none()
                    if a and getattr(a, "name", None):
                        artist_name = a.name
                self.artist_lbl.setText(artist_name)
                self._load_artists_combo(db, preselect_id=getattr(self._client_db, "preferred_artist_id", None))

                # Citas (texto)
                def fmt_dt(dt: Optional[datetime]) -> str:
                    return dt.strftime("%d %b %H:%M") if dt else "—"
                self.next_lbl.setText(fmt_dt(getattr(next_session, "start", None)))

                # Notas
                existing_notes = getattr(self._client_db, "notes", None)
                self._perfil_notes.blockSignals(True)
                self._perfil_notes.setPlainText(existing_notes or "")
                self._perfil_notes.blockSignals(False)
                self._notes_dirty = False
                self._perfil_notes.textChanged.connect(self._on_notes_changed)

                # Preferencias desde notas
                styles, zones, source = self._extract_prefs_from_notes(existing_notes or "")
                self._pref_styles_lbl.setText(styles or "—")
                self._pref_zones_lbl.setText(zones or "—")
                self._pref_source_lbl.setText(source or "—")

                pref_id = getattr(self._client_db, "preferred_artist_id", None)
                if pref_id:
                    pa = db.query(Artist).filter(Artist.id == pref_id).one_or_none()
                    if pa and getattr(pa, "name", None):
                        self._pref_artist_lbl.setText(pa.name)
                self._pref_city_lbl.setText(getattr(self._client_db, "city", None) or "—")
                self._pref_state_lbl.setText(getattr(self._client_db, "state", None) or "—")
                self._pref_city_edit.setText(getattr(self._client_db, "city", "") or "")
                self._pref_state_edit.setText(getattr(self._client_db, "state", "") or "")

                # Salud
                flags = [
                    "health_allergies","health_diabetes","health_coagulation","health_epilepsy",
                    "health_cardiac","health_anticoagulants","health_preg_lact","health_substances","health_derm"
                ]
                for cb, attr in zip(self._health_checks, flags):
                    cb.setChecked(bool(getattr(self._client_db, attr, False)))
                self._health_obs.setPlainText(getattr(self._client_db, "health_obs", None) or "")

                # Consentimientos
                self._consent_checks[0].setChecked(bool(getattr(self._client_db, "consent_info", False)))
                self._consent_checks[1].setChecked(bool(getattr(self._client_db, "consent_image", False)))
                self._consent_checks[2].setChecked(bool(getattr(self._client_db, "consent_data", False)))

                # Emergencia
                self._emerg_name.setText(getattr(self._client_db, "emergency_name", None) or "—")
                self._emerg_rel.setText(getattr(self._client_db, "emergency_relation", None) or "—")
                self._emerg_tel.setText(getattr(self._client_db, "emergency_phone", None) or "—")
                self._emerg_name_edit.setText(getattr(self._client_db, "emergency_name", "") or "")
                self._emerg_rel_edit.setText(getattr(self._client_db, "emergency_relation", "") or "")
                self._emerg_tel_edit.setText(getattr(self._client_db, "emergency_phone", "") or "")

                # Permisos
                self._apply_notes_permissions(owner_artist_id=self._owner_artist_id)
                self._set_avatar_perm(cid)
                self._refresh_edit_buttons()

        except Exception as ex:
            QMessageBox.critical(self, "BD", f"Error al cargar cliente: {ex}")
            self._apply_notes_permissions(owner_artist_id=None)
            self._set_avatar_perm(None)

    def _reset_editable_tabs(self):
        # Pref
        self._pref_artist_lbl.setText("—")
        self._pref_city_lbl.setText("—");   self._pref_city_edit.setText("")
        self._pref_state_lbl.setText("—");  self._pref_state_edit.setText("")
        self._pref_styles_lbl.setText("—")
        self._pref_zones_lbl.setText("—")
        self._pref_source_lbl.setText("—")
        # Salud
        for cb in self._health_checks: cb.setChecked(False)
        self._health_obs.setPlainText("")
        # Consentimientos
        for cb in self._consent_checks: cb.setChecked(False)
        # Emergencia
        self._emerg_name.setText("—"); self._emerg_name_edit.setText("")
        self._emerg_rel.setText("—");  self._emerg_rel_edit.setText("")
        self._emerg_tel.setText("—");  self._emerg_tel_edit.setText("")

    # --------------------------------------------------------
    # UI helpers (pestañas)
    # --------------------------------------------------------
    def _mk_perfil(self, w: QWidget):
        lay = QVBoxLayout(w); lay.setSpacing(8)
        title = QLabel("Resumen")
        title.setStyleSheet("font-weight:600;")
        lay.addWidget(title)
        self._perfil_name = QLabel("—"); self._perfil_name.setStyleSheet("font-weight:600;")
        self._perfil_contact = QLabel("—")
        lay.addWidget(self._perfil_name)
        lay.addWidget(self._perfil_contact)
        self._perfil_notes = QTextEdit()
        self._perfil_notes.setPlaceholderText("Notas del perfil…")
        self._perfil_notes.textChanged.connect(self._mark_dirty_notes)
        lay.addWidget(self._perfil_notes, 1)

    def _mk_placeholder(self, w: QWidget, text: str):
        lay = QVBoxLayout(w)
        lbl = QLabel(text); lay.addWidget(lbl, 0, Qt.AlignTop)

    def _mk_text(self, w: QWidget, text: str):
        lay = QVBoxLayout(w)
        te = QTextEdit(); te.setPlainText(text)
        lay.addWidget(te)
        if "Notas internas" in text:
            self._notes_tab = te

    def _mk_list(self, w: QWidget, items):
        lay = QVBoxLayout(w)
        self.lst_citas = QListWidget()
        for it in items:
            self.lst_citas.addItem(QListWidgetItem(it))
        lay.addWidget(self.lst_citas)

    def _set_citas_list(self, items):
        self.lst_citas.clear()
        for it in items:
            self.lst_citas.addItem(QListWidgetItem(it))

    def _mk_pref(self, w: QWidget):
        lay = QVBoxLayout(w); lay.setSpacing(8)
        box = QGroupBox("Preferencias")
        form = QFormLayout(box); form.setLabelAlignment(Qt.AlignRight)

        # Lectura
        self._pref_artist_lbl = QLabel("—")
        self._pref_city_lbl   = QLabel("—")
        self._pref_state_lbl  = QLabel("—")
        self._pref_styles_lbl = QLabel("—")
        self._pref_zones_lbl  = QLabel("—")
        self._pref_source_lbl = QLabel("—")

        # Inputs edición
        self._pref_city_edit  = QLineEdit(); self._pref_city_edit.setVisible(False); self._pref_city_edit.textChanged.connect(self._mark_dirty)
        self._pref_state_edit = QLineEdit(); self._pref_state_edit.setVisible(False); self._pref_state_edit.textChanged.connect(self._mark_dirty)

        form.addRow("Artista preferido:", self._pref_artist_lbl)  # combo en header
        form.addRow("Ciudad:", self._pref_city_lbl);  form.addRow("", self._pref_city_edit)
        form.addRow("Estado:", self._pref_state_lbl); form.addRow("", self._pref_state_edit)
        form.addRow("Estilos favoritos:", self._pref_styles_lbl)
        form.addRow("Zonas de interés:", self._pref_zones_lbl)
        form.addRow("¿Cómo nos conoció?", self._pref_source_lbl)

        lay.addWidget(box)
        lay.addStretch(1)

    def _mk_salud(self, w: QWidget):
        lay = QVBoxLayout(w); lay.setSpacing(8)
        box = QGroupBox("Tamizaje de salud")
        v = QVBoxLayout(box)
        self._health_checks = [
            QCheckBox("Alergias (látex, lidocaína, pigmentos, antibióticos)"),
            QCheckBox("Diabetes"),
            QCheckBox("Trastorno de coagulación / hemofilia"),
            QCheckBox("Epilepsia"),
            QCheckBox("Condiciones cardiacas"),
            QCheckBox("Anticoagulantes / Accutane (12m)"),
            QCheckBox("Embarazo / lactancia"),
            QCheckBox("Alcohol/drogas en 24–48h"),
            QCheckBox("Problemas dermatológicos en la zona"),
        ]
        for cb in self._health_checks:
            cb.setEnabled(False)
            cb.stateChanged.connect(self._mark_dirty)
            v.addWidget(cb)
        self._health_obs = QTextEdit(); self._health_obs.setReadOnly(True)
        self._health_obs.setPlaceholderText("Observaciones")
        self._health_obs.textChanged.connect(self._mark_dirty)
        v.addWidget(self._health_obs)
        lay.addWidget(box)
        lay.addStretch(1)

    def _mk_consent(self, w: QWidget):
        lay = QVBoxLayout(w); lay.setSpacing(8)
        box = QGroupBox("Consentimientos")
        v = QVBoxLayout(box)
        self._consent_checks = [
            QCheckBox("He leído y acepto el consentimiento informado*"),
            QCheckBox("Autorizo el uso de imágenes con fines de portafolio/redes"),
            QCheckBox("Acepto la política de datos personales"),
        ]
        for cb in self._consent_checks:
            cb.setEnabled(False)
            cb.stateChanged.connect(self._mark_dirty)
            v.addWidget(cb)
        lay.addWidget(box)
        lay.addStretch(1)

    def _mk_emerg(self, w: QWidget):
        lay = QVBoxLayout(w); lay.setSpacing(8)
        box = QGroupBox("Contacto de emergencia")
        form = QFormLayout(box); form.setLabelAlignment(Qt.AlignRight)
        # Lectura
        self._emerg_name = QLabel("—")
        self._emerg_rel  = QLabel("—")
        self._emerg_tel  = QLabel("—")
        # Inputs edición
        self._emerg_name_edit = QLineEdit(); self._emerg_name_edit.setVisible(False); self._emerg_name_edit.textChanged.connect(self._mark_dirty)
        self._emerg_rel_edit  = QLineEdit(); self._emerg_rel_edit.setVisible(False);  self._emerg_rel_edit.textChanged.connect(self._mark_dirty)
        self._emerg_tel_edit  = QLineEdit(); self._emerg_tel_edit.setVisible(False);  self._emerg_tel_edit.textChanged.connect(self._mark_dirty)

        form.addRow("Nombre:", self._emerg_name); form.addRow("", self._emerg_name_edit)
        form.addRow("Relación:", self._emerg_rel); form.addRow("", self._emerg_rel_edit)
        form.addRow("Teléfono:", self._emerg_tel); form.addRow("", self._emerg_tel_edit)
        lay.addWidget(box)
        lay.addStretch(1)

    # --------------------------------------------------------
    # Artistas
    # --------------------------------------------------------
    def _load_artists_combo(self, db: Session, preselect_id: Optional[int]):
        self.artist_combo.clear()
        items: List[Tuple[str, Optional[int]]] = [("Sin preferencia", None)]
        for a in db.query(Artist).order_by(Artist.name.asc()).all():
            items.append((a.name, a.id))
        for name, _id in items:
            self.artist_combo.addItem(name, _id)
        # Preselección
        if preselect_id is None:
            self.artist_combo.setCurrentIndex(0)
        else:
            for i in range(self.artist_combo.count()):
                if self.artist_combo.itemData(i) == preselect_id:
                    self.artist_combo.setCurrentIndex(i)
                    break

    def _selected_artist_id(self) -> Optional[int]:
        idx = self.artist_combo.currentIndex()
        return None if idx < 0 else self.artist_combo.itemData(idx)

    # --------------------------------------------------------
    # Avatar (circular + permisos)
    # --------------------------------------------------------
    def _uploads_dir(self) -> Path:
        base = Path(__file__).resolve().parents[2]  # .../ui/pages -> proyecto
        d = base / "assets" / "uploads" / "clients"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _avatar_paths(self, client_id: Optional[int]) -> Tuple[Path, Path]:
        up = self._uploads_dir()
        png = up / f"{client_id}.png"
        meta = up / f"{client_id}.meta.json"
        return png, meta

    def _circularize(self, pm: QPixmap, size: int) -> QPixmap:
        """Recorta el pixmap a un círculo con borde sutil."""
        if pm.isNull():
            return pm
        target = QPixmap(size, size)
        target.fill(Qt.transparent)
        painter = QPainter(target)
        painter.setRenderHint(QPainter.Antialiasing, True)

        path = QPainterPath()
        path.addEllipse(QRectF(0, 0, size, size))
        painter.setClipPath(path)

        scaled = pm.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)

        painter.setClipping(False)
        painter.setPen(QColor(0, 0, 0, 40))  # borde sutil (se ve bien en ambos temas)
        painter.drawEllipse(0, 0, size-1, size-1)
        painter.end()
        return target

    def _load_avatar_or_initials(self, client_id: Optional[int], name: str) -> QPixmap:
        if client_id:
            png, meta = self._avatar_paths(client_id)
            if png.exists():
                self._avatar_owner_user_id = None
                if meta.exists():
                    try:
                        data = json.loads(meta.read_text(encoding="utf-8"))
                        self._avatar_owner_user_id = data.get("owner_user_id")
                    except Exception:
                        pass
                pm = QPixmap(str(png))
                return self._circularize(pm, 72)
        return self._make_avatar_pixmap(72, name)

    def _set_avatar_perm(self, client_id: Optional[int]):
        user = get_current_user() or {}
        if not client_id:
            self.btn_avatar.setEnabled(False)
            return
        png, _ = self._avatar_paths(client_id)
        if not png.exists():  # cualquiera puede subir si no hay (se respetará elevación para assistant al cambiar)
            self.btn_avatar.setEnabled(True)
            return
        if user.get("role") == "admin":
            self.btn_avatar.setEnabled(True)
            return
        # Dueño original
        can_edit = (user.get("id") and self._avatar_owner_user_id and int(user["id"]) == int(self._avatar_owner_user_id))
        self.btn_avatar.setEnabled(bool(can_edit) or user.get("role") == "assistant")

    def _on_change_avatar(self):
        if not self._client or not self._client.get("id"):
            return
        cid = self._client["id"]
        user = get_current_user() or {}

        # Reglas:
        # - Admin: siempre puede.
        # - Si NO hay imagen previa: cualquiera puede (pero si es assistant, pedimos elevación).
        # - Si hay imagen previa:
        #       dueño o admin -> ok
        #       assistant -> requiere elevación
        #       artista (no dueño) -> no
        png, meta = self._avatar_paths(cid)
        role = user.get("role")
        needs_elevation = False

        if role == "admin":
            pass
        else:
            if png.exists():
                if user.get("id") and self._avatar_owner_user_id and int(user["id"]) == int(self._avatar_owner_user_id):
                    # dueño, ok
                    pass
                elif role == "assistant":
                    needs_elevation = True
                else:
                    QMessageBox.warning(self, "Permisos", "No tienes permiso para reemplazar la foto.")
                    return
            else:
                # No hay imagen previa
                if role == "assistant":
                    needs_elevation = True
                elif role == "artist":
                    # permitido subir si no existe
                    pass

        if needs_elevation:
            if not request_elevation_if_needed(self, "clients", "update"):
                return

        fn, _ = QFileDialog.getOpenFileName(self, "Seleccionar imagen", "", "Imágenes (*.png *.jpg *.jpeg)")
        if not fn:
            return
        try:
            pm = QPixmap(fn)
            if pm.isNull():
                raise ValueError("Archivo de imagen no válido.")
            pm = pm.scaled(512, 512, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            pm = self._circularize(pm, 512)
            pm.save(str(png), "PNG")
            meta.write_text(json.dumps({"owner_user_id": user.get("id")}, ensure_ascii=False), encoding="utf-8")
            self._avatar_owner_user_id = user.get("id")
            self.avatar.setPixmap(self._load_avatar_or_initials(cid, self.name_lbl.text()))
            self._set_avatar_perm(cid)
        except Exception as ex:
            QMessageBox.critical(self, "Avatar", f"No se pudo guardar la imagen: {ex}")

    def _make_avatar_pixmap(self, size: int, nombre: str) -> QPixmap:
        initials = "·"
        if nombre:
            parts = [p for p in nombre.split() if p]
            initials = "".join([p[0].upper() for p in parts[:2]]) or "·"
        pm = QPixmap(size, size); pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#d1d5db"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, size, size)
        p.setPen(QColor("#111"))
        p.drawText(pm.rect(), Qt.AlignCenter, initials)
        p.end()
        return pm

    # --------------------------------------------------------
    # Preferencias: parse de notas (META_PREFS|styles=...;zones=...;source=...)
    # --------------------------------------------------------
    def _extract_prefs_from_notes(self, notes: str) -> Tuple[str, str, str]:
        if not notes:
            return "", "", ""
        line = next((ln for ln in notes.splitlines() if ln.strip().startswith("META_PREFS|")), "")
        if not line:
            return "", "", ""
        try:
            payload = line.split("|", 1)[1]
            parts = dict(kv.split("=", 1) for kv in payload.split(";") if "=" in kv)
            styles = (parts.get("styles") or "").strip()
            zones  = (parts.get("zones")  or "").strip()
            source = (parts.get("source") or "").strip()
            return styles, zones, source
        except Exception:
            return "", "", ""

    # --------------------------------------------------------
    # Permisos de notas
    # --------------------------------------------------------
    def _apply_notes_permissions(self, owner_artist_id: Optional[int]) -> None:
        user = get_current_user()
        if not user:
            self._perfil_notes.setReadOnly(True)
            self._perfil_notes.setToolTip("Inicia sesión para editar notas.")
            return
        allowed = can(
            user.get("role"), "clients", "notes",
            owner_id=owner_artist_id,
            user_artist_id=user.get("artist_id"),
            user_id=user.get("id"),
        )
        self._perfil_notes.setReadOnly(not allowed)
        tip = "Notas internas del cliente."
        if not allowed:
            tip = "No tienes permiso para editar notas (solo lectura)."
        self._perfil_notes.setToolTip(tip)

    # --------------------------------------------------------
    # Dirty flags
    # --------------------------------------------------------
    def _mark_dirty(self, *args):
        self._any_dirty = True

    def _mark_dirty_notes(self, *args):
        self._notes_dirty = True
        self._any_dirty = True

    def _save_notes_if_needed(self, db: Session) -> None:
        if not self._notes_dirty or not self._client_db:
            return
        obj = db.query(Client).filter(Client.id == getattr(self._client_db, "id")).one_or_none()
        if not obj:
            return
        obj.notes = self._perfil_notes.toPlainText().strip()
        self._notes_dirty = False

    # --------------------------------------------------------
    # Edit mode
    # --------------------------------------------------------
    def _refresh_edit_buttons(self):
        # Mostrar/ocultar botones según modo
        self.btn_edit.setVisible(not self._edit_mode)
        self.btn_save.setVisible(self._edit_mode)
        self.btn_cancel.setVisible(self._edit_mode)

        # Mostrar labels vs inputs
        for w in (self.name_lbl, self.phone_lbl, self.email_lbl, self.ig_lbl, self.artist_lbl,
                  self._pref_city_lbl, self._pref_state_lbl,
                  self._emerg_name, self._emerg_rel, self._emerg_tel):
            w.setVisible(not self._edit_mode)
        for w in (self.name_edit, self.phone_edit, self.email_edit, self.ig_edit, self.artist_combo,
                  self._pref_city_edit, self._pref_state_edit,
                  self._emerg_name_edit, self._emerg_rel_edit, self._emerg_tel_edit):
            w.setVisible(self._edit_mode)

        # Salud/Consentimientos/Obs activables solo en edición (si hay permiso)
        can_update = self._user_can_update()
        for cb in self._health_checks:
            cb.setEnabled(self._edit_mode and can_update)
        self._health_obs.setReadOnly(not (self._edit_mode and can_update))
        for cb in self._consent_checks:
            cb.setEnabled(self._edit_mode and can_update)

    def _enter_edit_mode(self):
        # Reglas explícitas para evitar ambigüedad:
        user = get_current_user() or {}
        role = user.get("role")

        if role == "admin":
            self._edit_mode = True
            self._any_dirty = False
            self._refresh_edit_buttons()
            return

        if role == "assistant":
            # Pedimos elevación si aplica (ensure_permission maneja prompt)
            if not ensure_permission(self, "clients", "update", owner_id=self._owner_artist_id):
                return
            self._edit_mode = True
            self._any_dirty = False
            self._refresh_edit_buttons()
            return

        # Artist: no permitido
        QMessageBox.information(self, "Permisos", "Tu rol no permite editar este cliente.")
        return

    def _exit_edit_mode(self, silent: bool = False):
        self._edit_mode = False
        self._refresh_edit_buttons()
        if not silent:
            self.load_client(self._client)  # re-sincroniza labels

    def _cancel_edit(self):
        if self._any_dirty:
            res = QMessageBox.question(self, "Descartar cambios",
                                       "Tienes cambios sin guardar. ¿Deseas descartarlos?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if res != QMessageBox.Yes:
                return
        self._exit_edit_mode()

    def _user_can_update(self) -> bool:
        user = get_current_user() or {}
        role = user.get("role")
        if role == "admin":
            return True
        if role == "assistant":
            # En edición ya pasó ensure_permission; aquí devolvemos True para habilitar inputs.
            return True
        return False

    # --------------------------------------------------------
    # Guardado
    # --------------------------------------------------------
    def _save_changes(self):
        # Admin: ok. Assistant: requiere elevación (ya la pidió al entrar, pero revalidamos).
        user = get_current_user() or {}
        role = user.get("role")
        if role == "assistant":
            if not ensure_permission(self, "clients", "update", owner_id=self._owner_artist_id):
                return
        elif role != "admin":
            QMessageBox.information(self, "Permisos", "Tu rol no permite editar este cliente.")
            return

        if not self._client_db:
            return

        # Validación mínima
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validación", "El nombre no puede estar vacío.")
            return
        if not self.phone_edit.text().strip():
            QMessageBox.warning(self, "Validación", "El teléfono no puede estar vacío.")
            return

        try:
            with SessionLocal() as db:  # type: Session
                obj = db.query(Client).filter(Client.id == getattr(self._client_db, "id")).one_or_none()
                if not obj:
                    QMessageBox.warning(self, "Cliente", "No se encontró el registro en BD.")
                    return

                # Campos editables
                obj.name = self.name_edit.text().strip()
                obj.phone = self.phone_edit.text().strip()
                obj.email = self.email_edit.text().strip() or None
                obj.instagram = self.ig_edit.text().strip() or None

                obj.city = self._pref_city_edit.text().strip() or None
                obj.state = self._pref_state_edit.text().strip() or None

                # Artista preferido
                obj.preferred_artist_id = self._selected_artist_id()

                # Salud
                flags = [
                    "health_allergies","health_diabetes","health_coagulation","health_epilepsy",
                    "health_cardiac","health_anticoagulants","health_preg_lact","health_substances","health_derm"
                ]
                for cb, attr in zip(self._health_checks, flags):
                    setattr(obj, attr, bool(cb.isChecked()))
                obj.health_obs = self._health_obs.toPlainText().strip() or None

                # Consentimientos
                obj.consent_info  = bool(self._consent_checks[0].isChecked())
                obj.consent_image = bool(self._consent_checks[1].isChecked())
                obj.consent_data  = bool(self._consent_checks[2].isChecked())

                # Emergencia
                obj.emergency_name     = self._emerg_name_edit.text().strip() or None
                obj.emergency_relation = self._emerg_rel_edit.text().strip() or None
                obj.emergency_phone    = self._emerg_tel_edit.text().strip() or None

                # Notas si las cambiaste
                self._save_notes_if_needed(db)

                db.commit()

            QMessageBox.information(self, "Cliente", "Cambios guardados.")
            self._exit_edit_mode()
            self.cliente_cambiado.emit()
            self.back_to_list.emit()

        except Exception as ex:
            QMessageBox.critical(self, "BD", f"No se pudieron guardar los cambios:\n{ex}")

    # --------------------------------------------------------
    # Eliminar / Archivar
    # --------------------------------------------------------
    def _on_delete_clicked(self):
        # Reglas explícitas:
        user = get_current_user() or {}
        role = user.get("role")
        if role == "assistant":
            if not ensure_permission(self, "clients", "delete", owner_id=self._owner_artist_id):
                return
        elif role != "admin":
            QMessageBox.information(self, "Permisos", "Tu rol no permite eliminar clientes.")
            return

        if not self._client_db:
            return

        # ¿Tiene sesiones?
        has_sessions = False
        try:
            with SessionLocal() as db:
                cnt = db.query(TattooSession).filter(TattooSession.client_id == self._client_db.id).count()
                has_sessions = cnt > 0
        except Exception:
            has_sessions = False

        if has_sessions:
            msg = ("Este cliente tiene sesiones relacionadas.\n"
                   "Recomendado: archivar (se conserva el historial).\n\n"
                   "¿Deseas archivar en lugar de eliminar?")
            btn = QMessageBox.question(self, "Eliminar o archivar", msg,
                                       QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                                       QMessageBox.Yes)
            if btn == QMessageBox.Cancel:
                return
            if btn == QMessageBox.Yes:
                self._archive_client()
                return
            # Si No -> intenta eliminar igualmente
        else:
            ok = QMessageBox.question(self, "Eliminar cliente",
                                      "Esta acción eliminará al cliente. ¿Continuar?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ok != QMessageBox.Yes:
                return

        # Intentar eliminar
        try:
            with SessionLocal() as db:
                obj = db.query(Client).filter(Client.id == self._client_db.id).one_or_none()
                if not obj:
                    QMessageBox.information(self, "Cliente", "El registro ya no existe.")
                    self.cliente_cambiado.emit()
                    self.back_to_list.emit()
                    return
                db.delete(obj)
                db.commit()
            QMessageBox.information(self, "Cliente", "Cliente eliminado.")
            self.cliente_cambiado.emit()
            self.back_to_list.emit()
        except IntegrityError:
            # Si hay restricciones, archivar
            self._archive_client()
        except Exception as ex:
            QMessageBox.critical(self, "BD", f"No se pudo eliminar:\n{ex}")

    def _archive_client(self):
        try:
            with SessionLocal() as db:
                obj = db.query(Client).filter(Client.id == self._client_db.id).one_or_none()
                if not obj:
                    QMessageBox.information(self, "Cliente", "El registro ya no existe.")
                    self.cliente_cambiado.emit()
                    self.back_to_list.emit()
                    return
                if hasattr(obj, "is_active"):
                    obj.is_active = False
                else:
                    notes = (obj.notes or "").rstrip()
                    obj.notes = (notes + ("\n" if notes else "") + "ARCHIVED: true")
                db.commit()
            QMessageBox.information(self, "Cliente", "Cliente archivado.")
            self.cliente_cambiado.emit()
            self.back_to_list.emit()
        except Exception as ex:
            QMessageBox.critical(self, "BD", f"No se pudo archivar:\n{ex}")

    # --------------------------------------------------------
    # Guardado de notas (desde Perfil)
    # --------------------------------------------------------
    def _on_notes_changed(self):
        self._notes_dirty = True
        self._any_dirty = True

    # --------------------------------------------------------
    # Navegación (volver)
    # --------------------------------------------------------
    def _on_back_clicked(self):
        if self._edit_mode and self._any_dirty:
            res = QMessageBox.question(self, "Cambios sin guardar",
                                       "Tienes cambios sin guardar. ¿Salir de todos modos?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if res != QMessageBox.Yes:
                return
        # Guarda notas si no estás en modo edición (y tienes permiso)
        if self._notes_dirty and not self._edit_mode and self._user_can_update():
            try:
                with SessionLocal() as db:
                    self._save_notes_if_needed(db)
                    db.commit()
            except Exception:
                pass
        self.back_to_list.emit()
