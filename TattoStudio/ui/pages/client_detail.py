from __future__ import annotations

# ============================================================
# client_detail.py — Ficha de cliente (BD real + RBAC, UI intacto)
#
# Cambios:
# - Header "Artista asignado": si no hay sesiones, usa preferred_artist_id.
# - Se agregan pestañas: Preferencias, Salud, Consentimientos, Emergencia (solo lectura).
# - Lectura defensiva de columnas (getattr con fallback).
# ============================================================

from typing import Optional, List
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTextEdit, QListWidget, QListWidgetItem, QFrame, QGridLayout, QMessageBox,
    QGroupBox, QFormLayout, QCheckBox
)

from sqlalchemy.orm import Session
from sqlalchemy import asc

from data.db.session import SessionLocal
from data.models.client import Client
from data.models.artist import Artist
from data.models.session_tattoo import TattooSession

from ui.pages.common import ensure_permission
from services.permissions import can
from services.contracts import get_current_user


class ClientDetailPage(QWidget):
    back_to_list = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setStyleSheet("QLabel { background: transparent; }")

        self._client: dict = {}
        self._client_db: Optional[Client] = None
        self._owner_artist_id: Optional[int] = None
        self._notes_dirty: bool = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # ===== Toolbar (volver) =====
        bar = QHBoxLayout(); bar.setSpacing(8)
        self.btn_back = QPushButton("← Volver a clientes")
        self.btn_back.setObjectName("GhostSmall")
        self.btn_back.setMinimumHeight(32)
        self.btn_back.clicked.connect(self._on_back_clicked)
        bar.addWidget(self.btn_back)
        bar.addStretch(1)
        root.addLayout(bar)

        # ===== Header card =====
        self.header = QFrame()
        self.header.setObjectName("Card")
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(12, 12, 12, 12)
        hl.setSpacing(12)

        # Avatar
        self.avatar = QLabel()
        self.avatar.setFixedSize(72, 72)
        self.avatar.setPixmap(self._make_avatar_pixmap(72, "C"))
        hl.addWidget(self.avatar, 0, Qt.AlignTop)

        # Columna datos
        info = QVBoxLayout(); info.setSpacing(4)

        self.name_lbl = QLabel("Cliente")
        self.name_lbl.setStyleSheet("font-weight:700; font-size:16pt;")
        info.addWidget(self.name_lbl)

        badges = QHBoxLayout(); badges.setSpacing(6)
        self.badge_tag = QLabel(" — ")
        self.badge_tag.setObjectName("BadgeRole")
        self.badge_state = QLabel(" — ")
        self.badge_state.setObjectName("BadgeState")
        badges.addWidget(self.badge_tag)
        badges.addWidget(self.badge_state)
        badges.addStretch(1)
        info.addLayout(badges)

        grid = QGridLayout(); grid.setHorizontalSpacing(16); grid.setVerticalSpacing(4)

        self.phone_lbl = QLabel("—")
        self.email_lbl = QLabel("—")
        self.ig_lbl    = QLabel("—")

        grid.addWidget(QLabel("Teléfono:"), 0, 0, Qt.AlignRight)
        grid.addWidget(self.phone_lbl,     0, 1)
        grid.addWidget(QLabel("Email:"),   1, 0, Qt.AlignRight)
        grid.addWidget(self.email_lbl,     1, 1)
        grid.addWidget(QLabel("Instagram:"), 2, 0, Qt.AlignRight)
        grid.addWidget(self.ig_lbl,          2, 1)

        self.artist_lbl  = QLabel("—")
        self.next_lbl    = QLabel("—")

        grid.addWidget(QLabel("Artista asignado:"), 0, 2, Qt.AlignRight)
        grid.addWidget(self.artist_lbl,             0, 3)
        grid.addWidget(QLabel("Próxima cita:"),     1, 2, Qt.AlignRight)
        grid.addWidget(self.next_lbl,               1, 3)

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

        self.tab_perfil = QWidget(); self._mk_perfil(self.tab_perfil)
        self.tab_citas  = QWidget(); self._mk_list(self.tab_citas, [])
        self.tab_files  = QWidget(); self._mk_placeholder(self.tab_files, "Galería/Archivos (placeholder)")
        self.tab_forms  = QWidget(); self._mk_placeholder(self.tab_forms, "Formularios asignados/firmados (placeholder)")
        self.tab_notas  = QWidget(); self._mk_text(self.tab_notas, "Notas internas (placeholder)")

        # Nuevas pestañas (solo lectura, estilo sobrio)
        self.tab_pref   = QWidget(); self._mk_pref(self.tab_pref)
        self.tab_salud  = QWidget(); self._mk_salud(self.tab_salud)
        self.tab_consent= QWidget(); self._mk_consent(self.tab_consent)
        self.tab_emerg  = QWidget(); self._mk_emerg(self.tab_emerg)

        self.tabs.addTab(self.tab_perfil, "Perfil")
        self.tabs.addTab(self.tab_citas,  "Citas")
        self.tabs.addTab(self.tab_files,  "Archivos/Fotos")
        self.tabs.addTab(self.tab_forms,  "Formularios")
        self.tabs.addTab(self.tab_notas,  "Notas")
        self.tabs.addTab(self.tab_pref,   "Preferencias")
        self.tabs.addTab(self.tab_salud,  "Salud")
        self.tabs.addTab(self.tab_consent,"Consentimientos")
        self.tabs.addTab(self.tab_emerg,  "Emergencia")

        root.addWidget(tabs_card, 1)

    # ===== API =====
    def load_client(self, client: dict):
        self._client = client or {}
        cid = client.get("id")
        name_hint = client.get("nombre") or client.get("name") or "—"

        self.name_lbl.setText(name_hint)
        self.avatar.setPixmap(self._make_avatar_pixmap(72, name_hint))
        self.badge_tag.setText(f" {client.get('etiquetas','—') or '—'} ")
        self.badge_state.setText(f" {client.get('estado','—') or '—'} ")
        self.phone_lbl.setText(client.get("tel") or "—")
        self.email_lbl.setText(client.get("email") or "—")
        self.ig_lbl.setText(client.get("ig") or client.get("instagram") or "—")
        self.artist_lbl.setText(client.get("artista") or "—")
        self.next_lbl.setText(client.get("proxima") or "—")
        self._perfil_name.setText(name_hint)
        self._perfil_contact.setText(f"{client.get('tel','—')}  ·  {client.get('email','—')}")

        # Limpia tabs nuevas
        self._pref_artist_lbl.setText("—")
        self._pref_city_lbl.setText("—")
        self._pref_state_lbl.setText("—")
        for cb in self._health_checks:
            cb.setChecked(False)
        self._health_obs.setPlainText("")
        for cb in self._consent_checks:
            cb.setChecked(False)
        self._emerg_name.setText("—")
        self._emerg_rel.setText("—")
        self._emerg_tel.setText("—")

        if not cid:
            self._perfil_notes.setPlainText("Notas del perfil (sin id de cliente)")
            self._apply_notes_permissions(owner_artist_id=None)
            self._set_citas_list([f'{client.get("proxima","—")} · {client.get("artista","—")}'])
            return

        try:
            with SessionLocal() as db:  # type: Session
                self._client_db = db.query(Client).filter(Client.id == cid).one_or_none()
                if not self._client_db:
                    QMessageBox.warning(self, "Cliente", f"Cliente id={cid} no encontrado.")
                    self._apply_notes_permissions(owner_artist_id=None)
                    return

                # --- Header/contacto ---
                name = getattr(self._client_db, "name", None) or name_hint
                self.name_lbl.setText(name)
                self.avatar.setPixmap(self._make_avatar_pixmap(72, name))
                phone = getattr(self._client_db, "phone", None) or self.phone_lbl.text()
                email = getattr(self._client_db, "email", None) or self.email_lbl.text()
                ig    = getattr(self._client_db, "instagram", None) or self.ig_lbl.text()
                self.phone_lbl.setText(phone or "—")
                self.email_lbl.setText(email or "—")
                self.ig_lbl.setText(ig or "—")
                self._perfil_name.setText(name)
                self._perfil_contact.setText(f"{phone or '—'}  ·  {email or '—'}")

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

                # Artista “dueño” de la ficha (para permisos y header)
                self._owner_artist_id = (
                    getattr(next_session, "artist_id", None)
                    if next_session else getattr(last_session, "artist_id", None)
                )
                if not self._owner_artist_id:
                    self._owner_artist_id = getattr(self._client_db, "preferred_artist_id", None)

                artist_name = "—"
                if self._owner_artist_id:
                    a = db.query(Artist).filter(Artist.id == self._owner_artist_id).one_or_none()
                    if a and getattr(a, "name", None):
                        artist_name = a.name
                self.artist_lbl.setText(artist_name)

                def fmt_dt(dt: Optional[datetime]) -> str:
                    return dt.strftime("%d %b %H:%M") if dt else "—"
                self.next_lbl.setText(fmt_dt(getattr(next_session, "start", None)))

                # Citas (resumen)
                items: List[str] = []
                if next_session:
                    items.append(f'{fmt_dt(next_session.start)} · {artist_name}')
                if last_session:
                    ln_artist_name = artist_name
                    if getattr(last_session, "artist_id", None) and last_session.artist_id != self._owner_artist_id:
                        a2 = db.query(Artist).filter(Artist.id == last_session.artist_id).one_or_none()
                        if a2 and getattr(a2, "name", None):
                            ln_artist_name = a2.name
                    items.append(f'{fmt_dt(last_session.start)} · {ln_artist_name}')
                if not items:
                    items = ["—"]
                self._set_citas_list(items)

                # Notas (perfil)
                existing_notes = getattr(self._client_db, "notes", None)
                self._perfil_notes.blockSignals(True)
                self._perfil_notes.setPlainText(existing_notes or "Notas del perfil (—)")
                self._perfil_notes.blockSignals(False)
                self._notes_dirty = False
                self._perfil_notes.textChanged.connect(self._on_notes_changed)

                # ---- Preferencias ----
                pref_id = getattr(self._client_db, "preferred_artist_id", None)
                if pref_id:
                    pa = db.query(Artist).filter(Artist.id == pref_id).one_or_none()
                    if pa and getattr(pa, "name", None):
                        self._pref_artist_lbl.setText(pa.name)
                self._pref_city_lbl.setText(getattr(self._client_db, "city", None) or "—")
                self._pref_state_lbl.setText(getattr(self._client_db, "state", None) or "—")

                # ---- Salud ----
                flags = [
                    "health_allergies","health_diabetes","health_coagulation","health_epilepsy",
                    "health_cardiac","health_anticoagulants","health_preg_lact","health_substances","health_derm"
                ]
                for cb, attr in zip(self._health_checks, flags):
                    cb.setChecked(bool(getattr(self._client_db, attr, False)))
                self._health_obs.setPlainText(getattr(self._client_db, "health_obs", None) or "")

                # ---- Consentimientos ----
                self._consent_checks[0].setChecked(bool(getattr(self._client_db, "consent_info", False)))
                self._consent_checks[1].setChecked(bool(getattr(self._client_db, "consent_image", False)))
                self._consent_checks[2].setChecked(bool(getattr(self._client_db, "consent_data", False)))

                # ---- Emergencia ----
                self._emerg_name.setText(getattr(self._client_db, "emergency_name", None) or "—")
                self._emerg_rel.setText(getattr(self._client_db, "emergency_relation", None) or "—")
                self._emerg_tel.setText(getattr(self._client_db, "emergency_phone", None) or "—")

                # Permisos (notas)
                self._apply_notes_permissions(owner_artist_id=self._owner_artist_id)

        except Exception as ex:
            QMessageBox.critical(self, "BD", f"Error al cargar cliente: {ex}")
            self._apply_notes_permissions(owner_artist_id=None)

    # ===== Helpers de UI =====
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
        self._pref_artist_lbl = QLabel("—")
        self._pref_city_lbl = QLabel("—")
        self._pref_state_lbl = QLabel("—")
        form.addRow("Artista preferido:", self._pref_artist_lbl)
        form.addRow("Ciudad:", self._pref_city_lbl)
        form.addRow("Estado:", self._pref_state_lbl)
        lay.addWidget(box)
        lay.addStretch(1)

    def _mk_salud(self, w: QWidget):
        lay = QVBoxLayout(w); lay.setSpacing(8)
        box = QGroupBox("Tamizaje de salud")
        v = QVBoxLayout(box)
        # Checkboxes readonly
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
            v.addWidget(cb)
        self._health_obs = QTextEdit(); self._health_obs.setReadOnly(True)
        self._health_obs.setPlaceholderText("Observaciones")
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
            v.addWidget(cb)
        lay.addWidget(box)
        lay.addStretch(1)

    def _mk_emerg(self, w: QWidget):
        lay = QVBoxLayout(w); lay.setSpacing(8)
        box = QGroupBox("Contacto de emergencia")
        form = QFormLayout(box); form.setLabelAlignment(Qt.AlignRight)
        self._emerg_name = QLabel("—")
        self._emerg_rel  = QLabel("—")
        self._emerg_tel  = QLabel("—")
        form.addRow("Nombre:", self._emerg_name)
        form.addRow("Relación:", self._emerg_rel)
        form.addRow("Teléfono:", self._emerg_tel)
        lay.addWidget(box)
        lay.addStretch(1)

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

    # ===== Permisos de notas =====
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

    # ===== Guardado de notas =====
    def _on_notes_changed(self):
        self._notes_dirty = True

    def _save_notes_if_needed(self) -> None:
        if not self._notes_dirty or not self._client_db:
            return
        user = get_current_user()
        if not user:
            return
        if not ensure_permission(self, "clients", "notes", owner_id=self._owner_artist_id):
            return
        if not hasattr(self._client_db, "notes"):
            return
        new_val = self._perfil_notes.toPlainText().strip()
        try:
            with SessionLocal() as db:  # type: Session
                obj = db.query(Client).filter(Client.id == getattr(self._client_db, "id")).one_or_none()
                if not obj:
                    return
                obj.notes = new_val  # type: ignore[attr-defined]
                db.commit()
                self._notes_dirty = False
        except Exception as ex:
            QMessageBox.warning(self, "Notas", f"No se pudieron guardar las notas: {ex}")

    # ===== Navegación (volver) =====
    def _on_back_clicked(self):
        self._save_notes_if_needed()
        self.back_to_list.emit()
