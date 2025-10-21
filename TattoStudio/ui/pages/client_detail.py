from __future__ import annotations

from typing import Optional, List, Tuple
from datetime import datetime
import os, json
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor, QKeySequence
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTextEdit, QListWidget, QListWidgetItem, QFrame, QGridLayout, QMessageBox,
    QGroupBox, QFormLayout, QCheckBox, QFileDialog, QLineEdit, QComboBox, QSizePolicy,
    QToolButton, QMenu, QSpacerItem, QShortcut
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
from ui.pages.common import (
    ensure_permission,
    request_elevation_if_needed,
    round_pixmap,            # avatar circular
    render_instagram,        # mostrar @
    normalize_instagram,     # guardar sin @
)
from ui.pages.portfolios import (
    FlowLayout,              # grid fluido para las miniaturas
    PortfolioCard,           # tarjeta reutilizable
    PortfolioDetailDialog,   # popup de detalle
    PortfolioService,        # consultas reutilizables
)

class ClientDetailPage(QWidget):
    back_to_list = pyqtSignal()
    cliente_cambiado = pyqtSignal()  # para refrescar tabla/lista
    def __init__(self):
        super().__init__()
        # Fondo transparente para labels
        self.setStyleSheet("QLabel { background: transparent; }")

        self._client: dict = {}
        self._client_db: Optional[Client] = None
        self._owner_artist_id: Optional[int] = None
        self._notes_dirty: bool = False
        self._any_dirty: bool = False
        self._avatar_owner_user_id: Optional[int] = None
        self._edit_mode: bool = False

        # ===== LAYOUT =====
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # ---------- IZQUIERDA (card grande)
        self.card = QFrame()
        self.card.setObjectName("Card")
        self.card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.card.setMinimumWidth(440)      # más ancho, como en staff_detail
        left = QVBoxLayout(self.card)
        left.setContentsMargins(18, 18, 18, 14)  # +top para “bajarlo” un poco
        left.setSpacing(12)

        # Header: avatar + nombre + kebab (alineado como en staff_detail)
        head = QHBoxLayout()
        head.setSpacing(12)

        # Avatar
        avatar_col = QVBoxLayout()
        avatar_col.setSpacing(0)
        avatar_col.setContentsMargins(0, 0, 0, 0)

        self.avatar = QLabel(self.card)
        self.avatar.setScaledContents(True)
        self.avatar.setFixedSize(96, 96)
        self.avatar.setStyleSheet("background: transparent; border-radius:48px;")
        self.avatar.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # <<< NUEVO: fija la alineación como en staff
        avatar_col.addWidget(self.avatar, 0, Qt.AlignLeft | Qt.AlignTop)

        # Botón overlay (✎) sobre el avatar — reemplaza al "Cambiar foto"
        self.btn_photo = QPushButton("✎", self.avatar)
        self.btn_photo.setObjectName("GhostSmall")
        self.btn_photo.setToolTip("Cambiar foto")
        self.btn_photo.setFixedSize(36, 36)
        self.btn_photo.setStyleSheet(
            "border-radius:18px; background: rgba(0,0,0,0.45); color: white; font-weight:700;"
        )
        self.btn_photo.hide()
        self.btn_photo.clicked.connect(self._on_change_avatar)

        head.addLayout(avatar_col, 0)

        # Nombre
        name_col = QVBoxLayout()
        name_col.setSpacing(6)

        # Nombre (mismo look que staff_detail)
        self.name_lbl = QLabel("Cliente", self.card)  # parent SIEMPRE, para que no sea ventana
        self.name_lbl.setStyleSheet("font-weight:700; font-size:20pt; background: transparent;")
        self.name_lbl.setWordWrap(True)  # permite dos líneas si el nombre es largo
        self.name_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        name_col.addWidget(self.name_lbl)

        # Campo editable (oculto por defecto)
        self.name_edit = QLineEdit(self.card)
        self.name_edit.setPlaceholderText("Nombre del cliente")
        self.name_edit.setVisible(False)
        self.name_edit.textChanged.connect(self._mark_dirty)
        name_col.addWidget(self.name_edit)

        head.addLayout(name_col, 1)

        # Kebab (···) con acciones Editar / Archivar / Eliminar
        self.btn_kebab = QToolButton()
        self.btn_kebab.setText("···")
        self.btn_kebab.setPopupMode(QToolButton.InstantPopup)
        self.btn_kebab.setStyleSheet("""
            QToolButton { padding: 2px 8px; border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; }
            QToolButton:hover { border-color: rgba(255,255,255,0.18); }
        """)
        menu = QMenu(self)
        # --- feedback hover del menú kebab ---
        menu.setStyleSheet("""
            QMenu {
                background: #2b2f36;
                border: 1px solid rgba(255,255,255,.08);
                border-radius: 10px;
                padding: 6px 0;
            }
            QMenu::item {
                padding: 8px 14px;
                background: transparent;
            }
            QMenu::item:selected {
                background: rgba(255,255,255,.08);
            }
        """)
    
        act_edit = menu.addAction("Editar");             act_edit.triggered.connect(self._enter_edit_mode)
        act_arch = menu.addAction("Archivar (desactivar)"); act_arch.triggered.connect(self._archive_client)
        act_del  = menu.addAction("Eliminar");           act_del.triggered.connect(self._on_delete_clicked)
        self.btn_kebab.setMenu(menu)
        self.btn_edit = self.btn_kebab 
        kcol = QVBoxLayout(); kcol.addWidget(self.btn_kebab, alignment=Qt.AlignRight | Qt.AlignTop)
        head.addLayout(kcol)

        left.addLayout(head)
        # --- Card con datos de contacto (debajo del header) ---
        profile_card = QFrame(self.card)
        profile_card.setObjectName("Card")
        profile_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        profile_lay = QVBoxLayout(profile_card)
        profile_lay.setContentsMargins(12, 12, 12, 12)
        profile_lay.setSpacing(8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        profile_lay.addLayout(grid)

        # Campos (re-uso de tus widgets actuales)
        self.phone_lbl = QLabel("—", profile_card);  self.phone_edit = QLineEdit(profile_card)
        self.email_lbl = QLabel("—", profile_card);  self.email_edit = QLineEdit(profile_card)
        self.ig_lbl    = QLabel("—", profile_card);  self.ig_edit    = QLineEdit(profile_card)
        self.artist_lbl  = QLabel("—", profile_card)
        self.artist_combo = QComboBox(profile_card)
        self.next_lbl = QLabel("—", profile_card)

        grid.addWidget(QLabel("Teléfono:", profile_card),  0, 0, Qt.AlignRight)
        grid.addWidget(QLabel("Email:", profile_card),     1, 0, Qt.AlignRight)
        grid.addWidget(QLabel("Instagram:", profile_card), 2, 0, Qt.AlignRight)
        grid.addWidget(QLabel("Artista asignado:", profile_card), 0, 2, Qt.AlignRight)
        grid.addWidget(QLabel("Próxima cita:", profile_card),     1, 2, Qt.AlignRight)

        # Valores (modo lectura)
        grid.addWidget(self.phone_lbl,  0, 1)
        grid.addWidget(self.email_lbl,  1, 1)
        grid.addWidget(self.ig_lbl,     2, 1)
        grid.addWidget(self.artist_lbl, 0, 3)
        grid.addWidget(self.next_lbl,   1, 3)

        # Editores (mismas celdas, superpuestos; sólo se hacen visibles en editar)
        grid.addWidget(self.phone_edit,   0, 1)
        grid.addWidget(self.email_edit,   1, 1)
        grid.addWidget(self.ig_edit,      2, 1)
        grid.addWidget(self.artist_combo, 0, 3)

        # Opcional: igualar alto para que se vea más “form”
        for w in (self.phone_edit, self.email_edit, self.ig_edit, self.artist_combo):
            w.setMinimumHeight(36)

        # Respiro
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        left.addWidget(profile_card)

        # === TABS IZQUIERDA (Notas, Preferencias, Salud, Consentimientos, Emergencia) ===
        left_tabs_card = QFrame()
        left_tabs_card.setObjectName("Card")
        left_tabs = QVBoxLayout(left_tabs_card)
        left_tabs.setContentsMargins(12, 12, 12, 12)
        left_tabs.setSpacing(8)

        self.tabs_left = QTabWidget()
        left_tabs.addWidget(self.tabs_left, stretch=1)

        # Creamos los widgets de cada pestaña
        # Mantener vivos los widgets del “perfil” (nombre/contacto/notes) para reutilizar SOLO el editor de notas.
        # Ojo: si el contenedor temporal se destruye, los QLabel quedan “deleted” en Qt.
        self._perfil_container = QWidget(self)            # <-- padre fijo; no se destruye
        self._mk_perfil(self._perfil_container)           # crea self._perfil_notes, self._perfil_name, self._perfil_contact
        self._perfil_container.hide()                     # no lo mostramos en la UI

        self.tab_notas = QWidget()
        _lay_notas = QVBoxLayout(self.tab_notas)
        _lay_notas.setContentsMargins(0, 0, 0, 0)
        _lay_notas.setSpacing(8)
        # Movemos SOLO el editor de notas al tab "Notas"
        self._perfil_notes.setParent(self.tab_notas)
        _lay_notas.addWidget(self._perfil_notes, 1)


        self.tab_pref   = QWidget(); self._mk_pref(self.tab_pref)
        self.tab_salud  = QWidget(); self._mk_salud(self.tab_salud)
        self.tab_consent= QWidget(); self._mk_consent(self.tab_consent)
        self.tab_emerg  = QWidget(); self._mk_emerg(self.tab_emerg)

        self.tabs_left.addTab(self.tab_notas,   "Notas")
        self.tabs_left.addTab(self.tab_pref,    "Preferencias")
        self.tabs_left.addTab(self.tab_salud,   "Salud")
        self.tabs_left.addTab(self.tab_consent, "Consentimientos")
        self.tabs_left.addTab(self.tab_emerg,   "Emergencia")

        left.addWidget(left_tabs_card)

        # Botones de edición al pie (mismos handlers de tu lógica)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.btn_cancel = QPushButton("Cancelar"); self.btn_cancel.setObjectName("GhostSmall"); self.btn_cancel.clicked.connect(self._cancel_edit)
        self.btn_save   = QPushButton("Guardar");  self.btn_save.setObjectName("CTA");         self.btn_save.clicked.connect(self._save_changes)
        actions.addWidget(self.btn_cancel); actions.addWidget(self.btn_save)
        left.addLayout(actions)

        # meta (espaciador)
        left.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        root.addWidget(self.card, stretch=0)

        # ---------- DERECHA (tabs: Galería y Citas) ----------
        tabs_card = QFrame()
        tabs_card.setObjectName("Card")
        right = QVBoxLayout(tabs_card)
        right.setContentsMargins(12, 12, 12, 12)
        right.setSpacing(8)

        self.tabs_right = QTabWidget()
        right.addWidget(self.tabs_right, stretch=1)

        # Reutilizamos constructores existentes
        self.tab_files = QWidget(); self._mk_client_gallery(self.tab_files)
        self.tab_citas = QWidget(); self._mk_list(self.tab_citas, [])
        
        # Orden solicitado: Galería y Citas
        self.tabs_right.addTab(self.tab_files, "Galería")
        self.tabs_right.addTab(self.tab_citas,  "Citas")

        root.addWidget(tabs_card, stretch=1)

        # Hovers como en staff_detail (para kebab y ✎)
        self.card.installEventFilter(self)
        self.avatar.installEventFilter(self)

        self._esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._esc.activated.connect(self._on_back_clicked)

        # Mantener el card izquierdo sin efectos de hover de fondo
        self.card.setStyleSheet("QLabel { background: transparent; }")

        
        # --------------------------------------------------------
        # Galería del CLIENTE
        # --------------------------------------------------------
    def _mk_client_gallery(self, w: QWidget):
        lay = QVBoxLayout(w); lay.setContentsMargins(0,0,0,0); lay.setSpacing(8)

        # Contenedor scrolleable + FlowLayout (grid fluido)
        from PyQt5.QtWidgets import QScrollArea
        self._gal_scroll = QScrollArea(w)
        self._gal_scroll.setWidgetResizable(True)
        self._gal_host = QWidget(self._gal_scroll)
        self._gal_flow = FlowLayout(self._gal_host, hspacing=12, vspacing=12)
        self._gal_host.setLayout(self._gal_flow)
        self._gal_scroll.setWidget(self._gal_host)
        lay.addWidget(self._gal_scroll, 1)

    def _clear_client_gallery(self):
        while self._gal_flow.count():
            it = self._gal_flow.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

    def _refresh_client_gallery(self, client_id: Optional[int]):
        self._clear_client_gallery()
        if not client_id:
            emp = QLabel("Selecciona un cliente para ver su galería.")
            emp.setStyleSheet("color:#99A;")
            self._gal_flow.addWidget(emp)
            return

        try:
            items = PortfolioService.portfolio_for_client(int(client_id), limit=200, offset=0)
        except Exception as ex:
            err = QLabel(f"Error al cargar la galería: {ex}")
            err.setStyleSheet("color:#E99;")
            self._gal_flow.addWidget(err)
            return

        if not items:
            emp = QLabel("Este cliente aún no tiene imágenes en su galería.")
            emp.setStyleSheet("color:#99A;")
            self._gal_flow.addWidget(emp)
            return

        for it in items:
            card = PortfolioCard(it, on_click=self._open_portfolio_detail, parent=self._gal_host)
            self._gal_flow.addWidget(card)

    def _open_portfolio_detail(self, item):
        # Reusa tu diálogo popup de portfolios
        payload = PortfolioService.item_detail(int(item.id)) or {"item": item, "artist": None, "session": None, "client": None, "transaction": None}
        dlg = PortfolioDetailDialog(payload, self)
        dlg.show_at_cursor()

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
        a = self.avatar.size(); b = self.btn_photo.size()
        self.btn_photo.move((a.width()-b.width())//2, (a.height()-b.height())//2)
        self.phone_lbl.setText(client.get("tel") or "—"); self.phone_edit.setText(client.get("tel") or "")
        self.email_lbl.setText(client.get("email") or "—"); self.email_edit.setText(client.get("email") or "")
        ig_val = client.get("ig") or client.get("instagram") or ""
        self.ig_lbl.setText(render_instagram(ig_val) if ig_val else "—")
        self.ig_edit.setText(render_instagram(ig_val) if ig_val else "")
        self.artist_lbl.setText(client.get("artista") or "—")
        self.next_lbl.setText(client.get("proxima") or "—")
        self._perfil_name.setText(name_hint)
        self._perfil_contact.setText(f"{client.get('tel','—')}  ·  {client.get('email','—')}")

        self._reset_editable_tabs()
        self._any_dirty = False
        self._notes_dirty = False
        self._exit_edit_mode(silent=True)

        if not cid:
            self._apply_notes_permissions(owner_artist_id=None)
            self._set_citas_list([f'{client.get("proxima","—")} · {client.get("artista","—")}'])
            self._set_avatar_perm(None)
            self._refresh_client_gallery(None)
            return

        try:
            with SessionLocal() as db:  # type: Session
                self._client_db = db.query(Client).filter(Client.id == cid).one_or_none()
                if not self._client_db:
                    QMessageBox.warning(self, "Cliente", f"Cliente id={cid} no encontrado.")
                    self._apply_notes_permissions(owner_artist_id=None)
                    self._set_avatar_perm(None)
                    return

                name = getattr(self._client_db, "name", None) or name_hint
                self.name_lbl.setText(name); self.name_edit.setText(name)
                self.avatar.setPixmap(self._load_avatar_or_initials(cid, name))
                phone = getattr(self._client_db, "phone", None)
                email = getattr(self._client_db, "email", None)
                ig    = getattr(self._client_db, "instagram", None)
                self.phone_lbl.setText(phone or "—"); self.phone_edit.setText(phone or "")
                self.email_lbl.setText(email or "—"); self.email_edit.setText(email or "")
                self.ig_lbl.setText(render_instagram(ig) if ig else "—")
                self.ig_edit.setText(render_instagram(ig) if ig else "")
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

                self._owner_artist_id = (
                    getattr(next_session, "artist_id", None)
                    if next_session else getattr(last_session, "artist_id", None)
                ) or getattr(self._client_db, "preferred_artist_id", None)

                artist_name = "—"
                if self._owner_artist_id:
                    a = db.query(Artist).filter(Artist.id == self._owner_artist_id).one_or_none()
                    if a and getattr(a, "name", None):
                        artist_name = a.name
                self.artist_lbl.setText(artist_name)
                self._load_artists_combo(db, preselect_id=getattr(self._client_db, "preferred_artist_id", None))

                def fmt_dt(dt: Optional[datetime]) -> str:
                    return dt.strftime("%d %b %H:%M") if dt else "—"
                self.next_lbl.setText(fmt_dt(getattr(next_session, "start", None)))

                existing_notes = getattr(self._client_db, "notes", None)
                self._perfil_notes.blockSignals(True)
                self._perfil_notes.setPlainText(existing_notes or "")
                self._perfil_notes.blockSignals(False)
                self._notes_dirty = False
                self._perfil_notes.textChanged.connect(self._on_notes_changed)

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

                flags = [
                    "health_allergies","health_diabetes","health_coagulation","health_epilepsy",
                    "health_cardiac","health_anticoagulants","health_preg_lact","health_substances","health_derm"
                ]
                for cb, attr in zip(self._health_checks, flags):
                    cb.setChecked(bool(getattr(self._client_db, attr, False)))
                self._health_obs.setPlainText(getattr(self._client_db, "health_obs", None) or "")

                self._consent_checks[0].setChecked(bool(getattr(self._client_db, "consent_info", False)))
                self._consent_checks[1].setChecked(bool(getattr(self._client_db, "consent_image", False)))
                self._consent_checks[2].setChecked(bool(getattr(self._client_db, "consent_data", False)))

                self._emerg_name.setText(getattr(self._client_db, "emergency_name", None) or "—")
                self._emerg_rel.setText(getattr(self._client_db, "emergency_relation", None) or "—")
                self._emerg_tel.setText(getattr(self._client_db, "emergency_phone", None) or "—")
                self._emerg_name_edit.setText(getattr(self._client_db, "emergency_name", "") or "")
                self._emerg_rel_edit.setText(getattr(self._client_db, "emergency_relation", "") or "")
                self._emerg_tel_edit.setText(getattr(self._client_db, "emergency_phone", "") or "")

                self._apply_notes_permissions(owner_artist_id=self._owner_artist_id)
                self._set_avatar_perm(cid)
                self._refresh_edit_buttons()
                self._refresh_client_gallery(cid)

        except Exception as ex:
            QMessageBox.critical(self, "BD", f"Error al cargar cliente: {ex}")
            self._apply_notes_permissions(owner_artist_id=None)
            self._set_avatar_perm(None)

    # --------------------------------------------------------
    # Reset de pestañas editables (SIN CAMBIOS)
    # --------------------------------------------------------
    def _reset_editable_tabs(self):
        self._pref_artist_lbl.setText("—")
        self._pref_city_lbl.setText("—");   self._pref_city_edit.setText("")
        self._pref_state_lbl.setText("—");  self._pref_state_edit.setText("")
        self._pref_styles_lbl.setText("—")
        self._pref_zones_lbl.setText("—")
        self._pref_source_lbl.setText("—")
        for cb in self._health_checks: cb.setChecked(False)
        self._health_obs.setPlainText("")
        for cb in self._consent_checks: cb.setChecked(False)
        self._emerg_name.setText("—"); self._emerg_name_edit.setText("")
        self._emerg_rel.setText("—");  self._emerg_rel_edit.setText("")
        self._emerg_tel.setText("—");  self._emerg_tel_edit.setText("")

    # --------------------------------------------------------
    # UI helpers (pestañas) — SIN CAMBIOS
    # --------------------------------------------------------
    def _mk_perfil(self, w: QWidget):
        lay = QVBoxLayout(w); lay.setSpacing(8)
        title = QLabel("Resumen", w); title.setStyleSheet("font-weight:600;")
        lay.addWidget(title)
        self._perfil_name = QLabel("—", w); self._perfil_name.setStyleSheet("font-weight:600;")
        self._perfil_contact = QLabel("—", w)
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

        self._pref_artist_lbl = QLabel("—")
        self._pref_city_lbl   = QLabel("—")
        self._pref_state_lbl  = QLabel("—")
        self._pref_styles_lbl = QLabel("—")
        self._pref_zones_lbl  = QLabel("—")
        self._pref_source_lbl = QLabel("—")

        self._pref_city_edit  = QLineEdit(); self._pref_city_edit.setVisible(False); self._pref_city_edit.textChanged.connect(self._mark_dirty)
        self._pref_state_edit = QLineEdit(); self._pref_state_edit.setVisible(False); self._pref_state_edit.textChanged.connect(self._mark_dirty)

        form.addRow("Artista preferido:", self._pref_artist_lbl)
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
        self._emerg_name = QLabel("—")
        self._emerg_rel  = QLabel("—")
        self._emerg_tel  = QLabel("—")
        self._emerg_name_edit = QLineEdit(); self._emerg_name_edit.setVisible(False); self._emerg_name_edit.textChanged.connect(self._mark_dirty)
        self._emerg_rel_edit  = QLineEdit(); self._emerg_rel_edit.setVisible(False);  self._emerg_rel_edit.textChanged.connect(self._mark_dirty)
        self._emerg_tel_edit  = QLineEdit(); self._emerg_tel_edit.setVisible(False);  self._emerg_tel_edit.textChanged.connect(self._mark_dirty)

        form.addRow("Nombre:", self._emerg_name); form.addRow("", self._emerg_name_edit)
        form.addRow("Relación:", self._emerg_rel);  form.addRow("", self._emerg_rel_edit)
        form.addRow("Teléfono:", self._emerg_tel);  form.addRow("", self._emerg_tel_edit)
        lay.addWidget(box)
        lay.addStretch(1)

    # --------------------------------------------------------
    # Artistas / avatar / permisos / edición / guardado
    # (todo SIN CAMBIOS respecto a tu versión anterior)
    # --------------------------------------------------------
    def _load_artists_combo(self, db: Session, preselect_id: Optional[int]):
        self.artist_combo.clear()
        items: List[Tuple[str, Optional[int]]] = [("Sin preferencia", None)]
        for a in db.query(Artist).order_by(Artist.name.asc()).all():
            items.append((a.name, a.id))
        for name, _id in items:
            self.artist_combo.addItem(name, _id)
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

    def _uploads_dir(self) -> Path:
        base = Path(__file__).resolve().parents[2]
        d = base / "assets" / "uploads" / "clients"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _avatar_paths(self, client_id: Optional[int]) -> Tuple[Path, Path]:
        up = self._uploads_dir()
        png = up / f"{client_id}.png"
        meta = up / f"{client_id}.meta.json"
        return png, meta

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
                return round_pixmap(pm, 128)
        return self._make_avatar_pixmap(128, name)

    def _set_avatar_perm(self, client_id: Optional[int]):
        user = get_current_user() or {}
        if not client_id:
            self.btn_photo.setEnabled(False)
            return
        png, _ = self._avatar_paths(client_id)
        if not png.exists():
            self.btn_photo.setEnabled(True)
            return
        if user.get("role") == "admin":
            self.btn_photo.setEnabled(True)
            return
        can_edit = (user.get("id") and self._avatar_owner_user_id and int(user["id"]) == int(self._avatar_owner_user_id))
        self.btn_photo.setEnabled(bool(can_edit) or user.get("role") == "assistant")

    def _on_change_avatar(self):
        if not self._client or not self._client.get("id"):
            return
        cid = self._client["id"]
        user = get_current_user() or {}

        png, meta = self._avatar_paths(cid)
        role = user.get("role")
        needs_elevation = False

        if role == "admin":
            pass
        else:
            if png.exists():
                if user.get("id") and self._avatar_owner_user_id and int(user["id"]) == int(self._avatar_owner_user_id):
                    pass
                elif role == "assistant":
                    needs_elevation = True
                else:
                    QMessageBox.warning(self, "Permisos", "No tienes permiso para reemplazar la foto.")
                    return
            else:
                if role == "assistant":
                    needs_elevation = True

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
            pm = round_pixmap(pm, 512)
            pm.save(str(png), "PNG")
            meta.write_text(json.dumps({"owner_user_id": user.get("id")}, ensure_ascii=False), encoding="utf-8")
            self._avatar_owner_user_id = user.get("id")
            self.avatar.setPixmap(self._load_avatar_or_initials(cid, self.name_lbl.text()))
            a = self.avatar.size(); b = self.btn_photo.size()
            self.btn_photo.move((a.width()-b.width())//2, (a.height()-b.height())//2)
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

    # ---- Dirty flags / edición / guardado / eliminar / navegar (SIN CAMBIOS) ----
    def _mark_dirty(self, *args): self._any_dirty = True
    def _mark_dirty_notes(self, *args): self._notes_dirty = True; self._any_dirty = True

    def _save_notes_if_needed(self, db: Session) -> None:
        if not self._notes_dirty or not self._client_db:
            return
        obj = db.query(Client).filter(Client.id == getattr(self._client_db, "id")).one_or_none()
        if not obj:
            return
        obj.notes = self._perfil_notes.toPlainText().strip()
        self._notes_dirty = False

    def _refresh_edit_buttons(self):
        if hasattr(self, "btn_kebab"):
            self.btn_kebab.setVisible(not self._edit_mode)  # oculta kebab mientras editas
        self.btn_save.setVisible(self._edit_mode)
        self.btn_cancel.setVisible(self._edit_mode)

        for w in (self.name_lbl, self.phone_lbl, self.email_lbl, self.ig_lbl, self.artist_lbl,
                  self._pref_city_lbl, self._pref_state_lbl,
                  self._emerg_name, self._emerg_rel, self._emerg_tel):
            w.setVisible(not self._edit_mode)
        for w in (self.name_edit, self.phone_edit, self.email_edit, self.ig_edit, self.artist_combo,
                  self._pref_city_edit, self._pref_state_edit,
                  self._emerg_name_edit, self._emerg_rel_edit, self._emerg_tel_edit):
            w.setVisible(self._edit_mode)

        can_update = self._user_can_update()
        for cb in self._health_checks:
            cb.setEnabled(self._edit_mode and can_update)
        self._health_obs.setReadOnly(not (self._edit_mode and can_update))
        for cb in self._consent_checks:
            cb.setEnabled(self._edit_mode and can_update)

    def _enter_edit_mode(self):
        user = get_current_user() or {}
        role = user.get("role")
        if role == "admin":
            self._edit_mode = True; self._any_dirty = False; self._refresh_edit_buttons(); return
        if role == "assistant":
            if not ensure_permission(self, "clients", "update", owner_id=self._owner_artist_id): return
            self._edit_mode = True; self._any_dirty = False; self._refresh_edit_buttons(); return
        QMessageBox.information(self, "Permisos", "Tu rol no permite editar este cliente.")

    def _exit_edit_mode(self, silent: bool = False):
        self._edit_mode = False
        self._refresh_edit_buttons()
        if not silent:
            self.load_client(self._client)

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
        if role == "admin": return True
        if role == "assistant": return True
        return False

    def _save_changes(self):
        user = get_current_user() or {}
        role = user.get("role")
        if role == "assistant":
            if not ensure_permission(self, "clients", "update", owner_id=self._owner_artist_id): return
        elif role != "admin":
            QMessageBox.information(self, "Permisos", "Tu rol no permite editar este cliente.")
            return

        if not self._client_db: return

        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validación", "El nombre no puede estar vacío."); return
        if not self.phone_edit.text().strip():
            QMessageBox.warning(self, "Validación", "El teléfono no puede estar vacío."); return

        try:
            with SessionLocal() as db:  # type: Session
                obj = db.query(Client).filter(Client.id == getattr(self._client_db, "id")).one_or_none()
                if not obj:
                    QMessageBox.warning(self, "Cliente", "No se encontró el registro en BD."); return

                obj.name = self.name_edit.text().strip()
                obj.phone = self.phone_edit.text().strip()
                obj.email = self.email_edit.text().strip() or None
                ig_text = (self.ig_edit.text() or "").strip()
                obj.instagram = normalize_instagram(ig_text) or None
                obj.city = self._pref_city_edit.text().strip() or None
                obj.state = self._pref_state_edit.text().strip() or None
                obj.preferred_artist_id = self._selected_artist_id()

                flags = [
                    "health_allergies","health_diabetes","health_coagulation","health_epilepsy",
                    "health_cardiac","health_anticoagulants","health_preg_lact","health_substances","health_derm"
                ]
                for cb, attr in zip(self._health_checks, flags):
                    setattr(obj, attr, bool(cb.isChecked()))
                obj.health_obs = self._health_obs.toPlainText().strip() or None

                obj.consent_info  = bool(self._consent_checks[0].isChecked())
                obj.consent_image = bool(self._consent_checks[1].isChecked())
                obj.consent_data  = bool(self._consent_checks[2].isChecked())

                obj.emergency_name     = self._emerg_name_edit.text().strip() or None
                obj.emergency_relation = self._emerg_rel_edit.text().strip() or None
                obj.emergency_phone    = self._emerg_tel_edit.text().strip() or None

                self._save_notes_if_needed(db)
                db.commit()

            QMessageBox.information(self, "Cliente", "Cambios guardados.")
            self._exit_edit_mode()
            self.cliente_cambiado.emit()
            self.back_to_list.emit()
        except Exception as ex:
            QMessageBox.critical(self, "BD", f"No se pudieron guardar los cambios:\n{ex}")

    def _on_delete_clicked(self):
        user = get_current_user() or {}
        role = user.get("role")
        if role == "assistant":
            if not ensure_permission(self, "clients", "delete", owner_id=self._owner_artist_id):
                return
        elif role != "admin":
            QMessageBox.information(self, "Permisos", "Tu rol no permite eliminar clientes."); return

        if not self._client_db: return

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
            if btn == QMessageBox.Cancel: return
            if btn == QMessageBox.Yes: self._archive_client(); return
        else:
            ok = QMessageBox.question(self, "Eliminar cliente",
                                      "Esta acción eliminará al cliente. ¿Continuar?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ok != QMessageBox.Yes: return

        try:
            with SessionLocal() as db:
                obj = db.query(Client).filter(Client.id == self._client_db.id).one_or_none()
                if not obj:
                    QMessageBox.information(self, "Cliente", "El registro ya no existe.")
                    self.cliente_cambiado.emit(); self.back_to_list.emit(); return
                db.delete(obj); db.commit()
            QMessageBox.information(self, "Cliente", "Cliente eliminado.")
            self.cliente_cambiado.emit(); self.back_to_list.emit()
        except IntegrityError:
            self._archive_client()
        except Exception as ex:
            QMessageBox.critical(self, "BD", f"No se pudo eliminar:\n{ex}")

    def _archive_client(self):
        try:
            with SessionLocal() as db:
                obj = db.query(Client).filter(Client.id == self._client_db.id).one_or_none()
                if not obj:
                    QMessageBox.information(self, "Cliente", "El registro ya no existe.")
                    self.cliente_cambiado.emit(); self.back_to_list.emit(); return
                if hasattr(obj, "is_active"):
                    obj.is_active = False
                else:
                    notes = (obj.notes or "").rstrip()
                    obj.notes = (notes + ("\n" if notes else "") + "ARCHIVED: true")
                db.commit()
            QMessageBox.information(self, "Cliente", "Cliente archivado.")
            self.cliente_cambiado.emit(); self.back_to_list.emit()
        except Exception as ex:
            QMessageBox.critical(self, "BD", f"No se pudo archivar:\n{ex}")

    def _on_notes_changed(self):
        self._notes_dirty = True
        self._any_dirty = True

    def eventFilter(self, obj, ev):
        from PyQt5.QtCore import QEvent
        if obj is self.card:
            if ev.type() in (QEvent.Enter, QEvent.HoverEnter, QEvent.MouseMove):
                self.btn_kebab.show()
            elif ev.type() in (QEvent.Leave, QEvent.HoverLeave):
                self.btn_kebab.hide()
        elif obj is self.avatar:
            if ev.type() in (QEvent.Enter, QEvent.HoverEnter):
                self.btn_photo.show() if self.btn_photo.isEnabled() else self.btn_photo.hide()
            elif ev.type() in (QEvent.Leave, QEvent.HoverLeave):
                self.btn_photo.hide()
        return super().eventFilter(obj, ev)
    
    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            # Reusar tu lógica actual de salida/confirmación
            self._on_back_clicked()
        else:
            super().keyPressEvent(ev)

    def _on_back_clicked(self):
        if self._edit_mode and self._any_dirty:
            res = QMessageBox.question(self, "Cambios sin guardar",
                                       "Tienes cambios sin guardar. ¿Salir de todos modos?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if res != QMessageBox.Yes:
                return
        if self._notes_dirty and not self._edit_mode and self._user_can_update():
            try:
                with SessionLocal() as db:
                    self._save_notes_if_needed(db)
                    db.commit()
            except Exception:
                pass
        self.back_to_list.emit()
