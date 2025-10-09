from __future__ import annotations

from typing import Optional, Dict, List
from pathlib import Path
from datetime import date, datetime, timezone

from PyQt5.QtCore import Qt, QDate, pyqtSignal, QEvent, QPoint
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTextEdit, QListWidget, QFrame, QSizePolicy, QComboBox, QFileDialog,
    QGridLayout, QDateEdit, QToolButton, QSpacerItem, QListWidgetItem,
    QColorDialog, QApplication, QDialog, QLineEdit, QPushButton as QBtn, QLabel as QLbl,
    QFormLayout, QHBoxLayout as HBox
)

# BD
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from data.db.session import SessionLocal
from data.models.user import User
from data.models.artist import Artist
from data.models.session_tattoo import TattooSession

# Auth/perm
from services.contracts import get_current_user
from services import auth
from services.permissions import can

# ===== Helpers centralizados (common.py)
from ui.pages.common import (
    NoStatusTipMenu,          # menú que no limpia el status bar al hacer hover
    round_pixmap,             # avatar circular
    role_to_label,            # admin→Admin, assistant→Asistente, artist→Tatuador
    normalize_instagram,      # guarda sin @
    render_instagram,         # muestra con @
    load_artist_colors,       # lee assets/artist_colors.json
    save_artist_color,        # guarda/actualiza color por artista
    fallback_color_for,       # color de respaldo estable
)

# ===== QLineEdit con menú contextual en español (se conserva aquí)
class LocalizedLineEdit(QLineEdit):
    def contextMenuEvent(self, ev):
        menu = self.createStandardContextMenu()
        mapping = {
            "Undo": "Deshacer", "Redo": "Rehacer",
            "Cut": "Cortar", "Copy": "Copiar", "Paste": "Pegar",
            "Delete": "Eliminar", "Select All": "Seleccionar todo"
        }
        for act in menu.actions():
            txt = act.text()
            if txt in mapping:
                act.setText(mapping[txt])
        menu.setStyleSheet("""
            QMenu {
                background: #2b2f36;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item { padding: 6px 12px; border-radius: 6px; color: #e8eaf0; }
            QMenu::item:selected { background: rgba(100,180,255,0.18); color: white; }
        """)
        menu.exec(ev.globalPos())

# ===== Panel frameless/arrastrable para popups (se conserva estilo actual)
class FramelessPanel(QDialog):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self._drag: Optional[QPoint] = None

        self.wrap = QFrame(self)
        self.wrap.setObjectName("Card")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.wrap)

        self.v = QVBoxLayout(self.wrap)
        self.v.setContentsMargins(14, 14, 14, 14)
        self.v.setSpacing(10)

        # todos los textos sin fondo
        self.wrap.setStyleSheet("QLabel{background:transparent;}")

        if title:
            t = QLabel(title)
            t.setStyleSheet("font-weight:700; font-size:12pt; background:transparent;")
            self.v.addWidget(t)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPos() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag and e.buttons() & Qt.LeftButton:
            self.move(e.globalPos() - self._drag)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag = None
        super().mouseReleaseEvent(e)


class StaffDetailPage(QWidget):
    back_requested = pyqtSignal()
    staff_saved = pyqtSignal()

    _ARTIST_PALETTE = ["#7C3AED", "#0EA5E9", "#10B981", "#F59E0B", "#EF4444",
                       "#A855F7", "#06B6D4", "#84CC16", "#EAB308", "#F97316"]

    def __init__(self):
        super().__init__()
        self._user_id: Optional[int] = None
        self._is_new: bool = False
        self._edit_mode: bool = False
        self._current_is_active: bool = True
        self._kebab_allowed: bool = False
        self._block_status_tips: bool = False  # safety extra

        # ===== LAYOUT PRINCIPAL
        root = QHBoxLayout(self); root.setContentsMargins(24, 24, 24, 24); root.setSpacing(16)

        # --------- Izquierda: Tarjeta completa
        self.card = QFrame(); self.card.setObjectName("Card")
        self.card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.card.setAttribute(Qt.WA_Hover, True); self.card.setMouseTracking(True)

        left = QVBoxLayout(self.card); left.setContentsMargins(14, 8, 14, 14); left.setSpacing(12)

        # Barra de color
        self.color_bar = QFrame(); self.color_bar.setFixedHeight(6)
        self.color_bar.setStyleSheet("background: transparent; border-radius: 3px;")
        left.addWidget(self.color_bar)

        # Header
        head = QHBoxLayout(); head.setSpacing(12)

        # Avatar + ✎
        avatar_col = QVBoxLayout(); avatar_col.setSpacing(0); avatar_col.setContentsMargins(0, 0, 0, 0)
        self.avatar = QLabel(); self.avatar.setFixedSize(128, 128)
        self.avatar.setStyleSheet("background: transparent; border-radius:64px;")
        avatar_col.addWidget(self.avatar, alignment=Qt.AlignTop)

        self.btn_photo = QPushButton("✎", self.avatar)
        self.btn_photo.setObjectName("GhostSmall")
        self.btn_photo.setToolTip("Cambiar foto")
        self.btn_photo.setFixedSize(36, 36)
        self.btn_photo.setStyleSheet("border-radius:18px; background: rgba(0,0,0,0.45); color: white; font-weight:700;")
        self.btn_photo.hide()
        self.btn_photo.clicked.connect(self._on_change_photo)
        head.addLayout(avatar_col)

        # Nombre + chips
        name_col = QVBoxLayout(); name_col.setSpacing(6)
        name_row = QHBoxLayout(); name_row.setSpacing(8)

        self.color_dot = QLabel(); self.color_dot.setFixedSize(12, 12)
        self.color_dot.setStyleSheet("border-radius:6px; background: transparent;")
        name_row.addWidget(self.color_dot, alignment=Qt.AlignVCenter)

        self.lbl_name = QLabel("—")
        self.lbl_name.setStyleSheet("font-weight:700; font-size:18pt; background: transparent;")
        name_row.addWidget(self.lbl_name, stretch=1)
        name_col.addLayout(name_row)

        chips = QHBoxLayout(); chips.setSpacing(8)
        self.lbl_role_chip = QLabel("—"); self.lbl_state_chip = QLabel("—")
        for c in (self.lbl_role_chip, self.lbl_state_chip):
            c.setStyleSheet("background: transparent; padding:2px 8px; border-radius:8px;")
        chips.addWidget(self.lbl_role_chip); chips.addWidget(self.lbl_state_chip); chips.addStretch(1)
        name_col.addLayout(chips)
        head.addLayout(name_col, stretch=1)

        # Kebab
        self.btn_kebab = QToolButton(); self.btn_kebab.setText("···"); self.btn_kebab.setObjectName("GhostSmall")
        self.btn_kebab.setStyleSheet("""
            QToolButton { padding: 2px 8px; border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; }
            QToolButton:hover { border-color: rgba(255,255,255,0.18); }
        """)
        self.btn_kebab.setPopupMode(QToolButton.InstantPopup); self.btn_kebab.hide()

        self.menu_kebab = NoStatusTipMenu(self)
        self.menu_kebab.setStyleSheet("""
            QMenu { background:#2b2f36; border:1px solid rgba(255,255,255,0.08); border-radius:8px; padding:4px; }
            QMenu::item { padding:6px 12px; border-radius:6px; color:#e8eaf0; }
            QMenu::item:selected { background:rgba(100,180,255,0.18); color:white; }
        """)
        self.act_edit = self.menu_kebab.addAction("Editar");  self.act_edit.triggered.connect(self._enter_edit)
        self.act_toggle = self.menu_kebab.addAction("Desactivar"); self.act_toggle.triggered.connect(self._toggle_active)
        self.act_password = self.menu_kebab.addAction("Cambiar contraseña"); self.act_password.triggered.connect(self._change_password)
        self.act_color = self.menu_kebab.addAction("Color"); self.act_color.triggered.connect(self._change_color)
        self.menu_kebab.aboutToShow.connect(lambda: setattr(self, "_block_status_tips", True))
        self.menu_kebab.aboutToHide.connect(lambda: setattr(self, "_block_status_tips", False))
        self.btn_kebab.setMenu(self.menu_kebab)

        a_col = QVBoxLayout(); a_col.addWidget(self.btn_kebab, alignment=Qt.AlignRight | Qt.AlignTop)
        head.addLayout(a_col)
        left.addLayout(head)

        # Perfil (card)
        profile_card = QFrame(); profile_card.setObjectName("Card")
        profile_card.setStyleSheet("QLabel{background:transparent;}")
        self._prof = QGridLayout(profile_card); self._prof.setContentsMargins(12, 12, 12, 12)
        self._prof.setHorizontalSpacing(16); self._prof.setVerticalSpacing(8)

        # Usuario
        self.lbl_username_label = QLabel("Usuario:"); self.val_username = QLabel("—")
        self._prof.addWidget(self.lbl_username_label, 0, 0, Qt.AlignRight); self._prof.addWidget(self.val_username, 0, 1)
        self._username = LocalizedLineEdit(); self._prof.addWidget(self._username, 0, 1); self._username.hide()

        # Rol (oculto en vista; editable en edición)
        self.lbl_role_label = QLabel("Rol:"); self.val_role = QLabel("—")
        self._prof.addWidget(self.lbl_role_label, 1, 0, Qt.AlignRight); self._prof.addWidget(self.val_role, 1, 1)
        self._role = QComboBox(); self._role.addItems(["admin", "assistant", "artist"])
        self._role.currentTextChanged.connect(self._on_role_changed)
        self._prof.addWidget(self._role, 1, 1); self._role.hide()

        # Nombre completo
        self.lbl_full_label = QLabel("Nombre completo:"); self.val_full_name = QLabel("—")
        self._prof.addWidget(self.lbl_full_label, 2, 0, Qt.AlignRight); self._prof.addWidget(self.val_full_name, 2, 1)
        self._full_name = LocalizedLineEdit(); self._prof.addWidget(self._full_name, 2, 1); self._full_name.hide()

        # Fecha nacimiento
        self.lbl_birth_label = QLabel("Fecha de nacimiento:"); self.val_birthdate = QLabel("—")
        self._prof.addWidget(self.lbl_birth_label, 3, 0, Qt.AlignRight); self._prof.addWidget(self.val_birthdate, 3, 1)
        self._birthdate = QDateEdit(); self._birthdate.setCalendarPopup(True); self._birthdate.setDisplayFormat("dd/MM/yyyy")
        self._prof.addWidget(self._birthdate, 3, 1); self._birthdate.hide()

        # Email
        self.lbl_email_label = QLabel("Email:"); self.val_email = QLabel("—")
        self._prof.addWidget(self.lbl_email_label, 4, 0, Qt.AlignRight); self._prof.addWidget(self.val_email, 4, 1)
        self._email = LocalizedLineEdit(); self._prof.addWidget(self._email, 4, 1); self._email.hide()

        # Teléfono
        self.lbl_phone_label = QLabel("Teléfono:"); self.val_phone = QLabel("—")
        self._prof.addWidget(self.lbl_phone_label, 5, 0, Qt.AlignRight); self._prof.addWidget(self.val_phone, 5, 1)
        self._phone = LocalizedLineEdit(); self._prof.addWidget(self._phone, 5, 1); self._phone.hide()

        # Instagram
        self.lbl_ig_label = QLabel("Instagram:"); self.val_instagram = QLabel("—")
        self._prof.addWidget(self.lbl_ig_label, 6, 0, Qt.AlignRight); self._prof.addWidget(self.val_instagram, 6, 1)
        self._instagram = LocalizedLineEdit(); self._instagram.setPlaceholderText("@usuario")
        self._instagram.textChanged.connect(self._enforce_instagram_prefix)
        self._prof.addWidget(self._instagram, 6, 1); self._instagram.hide()

        # Nombre de artista
        self.lbl_an_label = QLabel("Nombre de artista:"); self.val_artistname = QLabel("—")
        self._prof.addWidget(self.lbl_an_label, 7, 0, Qt.AlignRight); self._prof.addWidget(self.val_artistname, 7, 1)
        self._artist_name = LocalizedLineEdit(); self._artist_name.setPlaceholderText("Visible en Agenda/Reportes")
        self._prof.addWidget(self._artist_name, 7, 1); self._artist_name.hide()

        left.addWidget(profile_card)

        # Guardar/Cancelar
        actions_edit = QHBoxLayout()
        self.btn_save = QPushButton("Guardar"); self.btn_save.setObjectName("CTA")
        self.btn_cancel = QPushButton("Cancelar"); self.btn_cancel.setObjectName("GhostSmall")
        self.btn_save.clicked.connect(self._save); self.btn_cancel.clicked.connect(self._cancel_edit)
        actions_edit.addStretch(1); actions_edit.addWidget(self.btn_cancel); actions_edit.addWidget(self.btn_save)
        left.addLayout(actions_edit); self.btn_save.hide(); self.btn_cancel.hide()

        # Meta
        left.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self._meta = QLabel("—"); self._meta.setStyleSheet("background: transparent; color:#6C757D;")
        left.addWidget(self._meta)

        root.addWidget(self.card, stretch=0)

        # --------- Derecha: Tabs
        right_wrap = QFrame(); right = QVBoxLayout(right_wrap); right.setContentsMargins(0, 0, 0, 0); right.setSpacing(8)
        self.tabs = QTabWidget(); right.addWidget(self.tabs, stretch=1)
        self.tab_port = QWidget(); self._mk_list(self.tab_port, [])
        self.tab_citas = QWidget(); self._mk_citas_tab(self.tab_citas)
        self.tab_docs = QWidget(); self._mk_text(self.tab_docs, "Documentos (placeholder)")
        self.tabs.addTab(self.tab_port, "Portafolio"); self.tabs.addTab(self.tab_citas, "Citas"); self.tabs.addTab(self.tab_docs, "Documentos")
        root.addWidget(right_wrap, stretch=1)

        # Hovers
        self.card.installEventFilter(self); self.avatar.installEventFilter(self)

        app = QApplication.instance()
        if app: app.installEventFilter(self)  # safety extra

        self._apply_rbac(view_only=True)

    # ===== Helpers UI (derecha)
    def _mk_text(self, w: QWidget, text: str):
        outer = QVBoxLayout(w); card = QFrame(); card.setObjectName("Card")
        lay = QVBoxLayout(card); lay.setContentsMargins(12, 12, 12, 12)
        te = QTextEdit(); te.setPlainText(text); lay.addWidget(te); outer.addWidget(card)

    def _mk_list(self, w: QWidget, items):
        outer = QVBoxLayout(w); card = QFrame(); card.setObjectName("Card")
        lay = QVBoxLayout(card); lay.setContentsMargins(12, 12, 12, 12)
        lst = QListWidget(); lst.addItems(items); lay.addWidget(lst); outer.addWidget(card)

    def _mk_citas_tab(self, w: QWidget):
        outer = QVBoxLayout(w); card = QFrame(); card.setObjectName("Card")
        lay = QVBoxLayout(card); lay.setContentsMargins(12, 12, 12, 12)
        self.lst_citas = QListWidget(); lay.addWidget(self.lst_citas); outer.addWidget(card)

    # ===== Avatars
    def _project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _avatar_dir(self) -> Path:
        p = self._project_root() / "assets" / "avatars"; p.mkdir(parents=True, exist_ok=True); return p

    def _avatar_path(self, uid: int) -> Path:
        return self._avatar_dir() / f"{uid}.png"

    def _make_avatar_pixmap(self, size: int, nombre: str) -> QPixmap:
        initials = "".join([p[0].upper() for p in (nombre or "").split()[:2]]) or "?"
        pm = QPixmap(size, size); pm.fill(Qt.transparent)
        p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#d1d5db")); p.setPen(Qt.NoPen); p.drawEllipse(0, 0, size, size)
        p.setPen(QColor("#111")); p.drawText(pm.rect(), Qt.AlignCenter, initials); p.end()
        return pm

    def _set_avatar_from_disk_or_placeholder(self, db: Session, u: User, size: int = 128):
        ap = self._avatar_path(u.id)
        if ap.exists():
            pm = QPixmap(str(ap)); self.avatar.setPixmap(round_pixmap(pm, size))  # ← common.round_pixmap
        else:
            artist_name = None
            if u.role == "artist" and u.artist_id:
                a = db.query(Artist).get(u.artist_id); artist_name = a.name if a else None
            visible = artist_name or u.username
            self.avatar.setPixmap(self._make_avatar_pixmap(size, visible))
        self._position_photo_btn()

    def _position_photo_btn(self):
        a = self.avatar.size(); b = self.btn_photo.size()
        self.btn_photo.move((a.width()-b.width())//2, (a.height()-b.height())//2)

    # ===== Fechas (UTC -> local SIEMPRE si viene naive)
    def _parse_dt_any(self, dt):
        if isinstance(dt, (int, float)):
            return datetime.fromtimestamp(dt, tz=timezone.utc)
        if isinstance(dt, str):
            s = dt.strip().replace("T", " ")
            try:
                return datetime.fromisoformat(s)
            except Exception:
                for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                    try: return datetime.strptime(s, fmt)
                    except Exception: pass
        return dt

    def _fmt_local(self, dt):
        if not dt: return "—"
        try:
            dt = self._parse_dt_any(dt)
            if not isinstance(dt, datetime): return str(dt)
            local_tz = datetime.now().astimezone().tzinfo
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                dt = dt.replace(tzinfo=timezone.utc)  # << DB guarda UTC naive
            return dt.astimezone(local_tz).strftime("%d/%m/%Y %H:%M")
        except Exception:
            try: return dt.strftime("%d/%m/%Y %H:%M")
            except Exception: return "—"

    # ===== Colores por artista (centralizado con common.py)
    def _artist_color_hex(self, artist_id: Optional[int]) -> str:
        if not artist_id:
            return "#9CA3AF"
        try:
            ov = load_artist_colors()
            key = str(int(artist_id)).lower()
            if key in ov and ov[key]:
                return ov[key]
        except Exception:
            pass
        # fallback estable por índice
        return fallback_color_for(int(artist_id))

    def _apply_artist_color(self, artist_id: Optional[int]):
        hexcol = self._artist_color_hex(artist_id)
        self.color_bar.setStyleSheet(f"background:{hexcol}; border-radius:3px;")
        self.color_dot.setStyleSheet(f"border-radius:6px; background:{hexcol};")
        self._style_chips(hexcol, self._current_is_active)

    def _style_chips(self, artist_hex: str, is_active: bool):
        self.lbl_role_chip.setStyleSheet(
            f"background:transparent; color:{artist_hex}; border:1px solid {artist_hex}; padding:2px 8px; border-radius:8px;"
        )
        if is_active:
            self.lbl_state_chip.setText("Activo")
            self.lbl_state_chip.setStyleSheet(
                f"background:transparent; color:{artist_hex}; border:1px solid {artist_hex}; padding:2px 8px; border-radius:8px;"
            )
        else:
            self.lbl_state_chip.setText("Inactivo")
            self.lbl_state_chip.setStyleSheet(
                "background:transparent; color:#9CA3AF; border:1px solid #555a61; padding:2px 8px; border-radius:8px;"
            )

    # ===== Carga de usuario
    def load_staff(self, staff: Dict):
        self._is_new = False; self._user_id = int(staff.get("id")); self._edit_mode = False
        with SessionLocal() as db:
            u = db.query(User).get(self._user_id)
            if not u:
                self.lbl_name.setText(staff.get("nombre", "—")); self._apply_rbac(view_only=True); return
            self._paint_from_user(db, u); self._load_appointments(db, u)
        self._apply_rbac(view_only=True)

    def start_create_mode(self):
        self._is_new = True; self._user_id = None; self._edit_mode = True
        self._username.setText(""); self._role.setCurrentText("assistant")
        self._full_name.clear(); self._birthdate.setDate(QDate.currentDate())
        self._email.clear(); self._phone.clear(); self._instagram.clear(); self._artist_name.clear()
        visible_name = "(nuevo usuario)"; self.lbl_name.setText(visible_name)
        self.lbl_role_chip.setText("Asistente"); self.lbl_state_chip.setText("Activo")
        self.avatar.setPixmap(self._make_avatar_pixmap(128, visible_name))
        self._current_is_active = True
        self._toggle_edit_widgets(True); self._apply_rbac(view_only=False)

    # ===== Render
    def _paint_from_user(self, db: Session, u: User):
        artist_name = None
        if u.role == "artist" and u.artist_id:
            a = db.query(Artist).get(u.artist_id); artist_name = a.name if a else None

        self._current_is_active = bool(u.is_active)
        self._apply_artist_color(u.artist_id if u.role == "artist" else None)

        visible = artist_name if artist_name else (u.username or u.name or "—")
        self.lbl_name.setText(visible)
        self.lbl_role_chip.setText(role_to_label(u.role))  # ← common.role_to_label
        self._set_avatar_from_disk_or_placeholder(db, u, size=128)

        # Lectura
        self.val_username.setText(u.username or "—")
        self.val_role.setText(role_to_label(u.role))
        self.val_full_name.setText(u.name or "—")
        self.val_birthdate.setText(u.birthdate.strftime("%d/%m/%Y") if u.birthdate else "—")
        self.val_email.setText(u.email or "—")
        self.val_phone.setText(u.phone or "—")
        self.val_instagram.setText(render_instagram(u.instagram) if u.instagram else "—")  # ← display con @
        self.val_artistname.setText(artist_name or "—")

        # Editores
        self._username.setText(u.username or ""); self._role.setCurrentText(u.role or "assistant")
        self._full_name.setText(u.name or "")
        if u.birthdate: self._birthdate.setDate(QDate(u.birthdate.year, u.birthdate.month, u.birthdate.day))
        else: self._birthdate.setDate(QDate.currentDate())
        self._email.setText(u.email or ""); self._phone.setText(u.phone or "")
        self._instagram.setText(render_instagram(u.instagram) if u.instagram else "@")  # ← editor muestra @ fijo
        self._artist_name.setText(artist_name or "")

        created_txt = self._fmt_local(getattr(u, "created_at", None))
        last_login_txt = self._fmt_local(getattr(u, "last_login", None))
        self._meta.setText(f"Creado: {created_txt}  |  Último acceso: {last_login_txt}")

        self._toggle_edit_widgets(False)

    def _toggle_edit_widgets(self, on: bool):
        self._edit_mode = on
        for w in (self.val_username, self.val_full_name, self.val_birthdate, self.val_email,
                  self.val_phone, self.val_instagram, self.val_artistname, self.val_role):
            w.setVisible(not on)
        for w in (self._username, self._role, self._full_name, self._birthdate,
                  self._email, self._phone, self._instagram, self._artist_name):
            w.setVisible(on)
        self.lbl_role_label.setVisible(on)
        self.btn_save.setVisible(on); self.btn_cancel.setVisible(on)
        self._on_role_changed(self._role.currentText())
        self._apply_rbac(view_only=not on)

    def _on_role_changed(self, role: str):
        allowed = (self._edit_mode and role == "artist")
        self._artist_name.setEnabled(allowed); self._artist_name.setVisible(allowed)

    # ===== Edición
    def _enter_edit(self):
        if not self._full_name.text().strip():
            self._full_name.setText(self.val_full_name.text().replace("—", "").strip())
        if not self._email.text().strip():
            self._email.setText(self.val_email.text().replace("—", "").strip())
        if not self._phone.text().strip():
            self._phone.setText(self.val_phone.text().replace("—", "").strip())
        if not self._artist_name.text().strip():
            self._artist_name.setText(self.val_artistname.text().replace("—", "").strip())
        if not self._instagram.text().strip():
            self._instagram.setText(render_instagram(self.val_instagram.text()) if self.val_instagram.text() != "—" else "@")
        self._toggle_edit_widgets(True)

    def _cancel_edit(self):
        if self._is_new: self.back_requested.emit(); return
        with SessionLocal() as db:
            u = db.query(User).get(self._user_id)
            if u: self._paint_from_user(db, u); self._load_appointments(db, u)
        self._toggle_edit_widgets(False)

    # ===== Instagram helpers
    def _enforce_instagram_prefix(self, text: str):
        # En editor siempre mostramos con @, pero guardamos sin @
        if not text:
            self._instagram.blockSignals(True); self._instagram.setText("@"); self._instagram.blockSignals(False); return
        if not text.startswith("@"):
            self._instagram.blockSignals(True); self._instagram.setText("@" + text.replace("@", "")); self._instagram.blockSignals(False)
        else:
            head, tail = text[0], text[1:].replace("@", "")
            fixed = head + tail
            if fixed != text:
                self._instagram.blockSignals(True); self._instagram.setText(fixed); self._instagram.blockSignals(False)

    # ===== Citas
    def _try_get(self, obj, names: List[str]):
        for n in names:
            if hasattr(obj, n):
                v = getattr(obj, n)
                if callable(v):
                    try: v = v()
                    except Exception: continue
                return v
        return None

    def _load_appointments(self, db: Session, u: User):
        self.lst_citas.clear()
        if not u.artist_id: return
        q = db.query(TattooSession).filter(TattooSession.artist_id == u.artist_id)
        order_attr = None
        for cand in ("start_at", "start_time", "scheduled_at", "scheduled_time", "datetime", "date"):
            if hasattr(TattooSession, cand): order_attr = getattr(TattooSession, cand); break
        if order_attr is not None:
            try: q = q.order_by(order_attr.desc())
            except Exception: pass
        for s in q.all():
            dt = self._try_get(s, ["start_at", "start_time", "scheduled_at", "scheduled_time", "datetime", "date"])
            dt_txt = ""
            try:
                if isinstance(dt, datetime): dt_txt = self._fmt_local(dt)
                elif isinstance(dt, date):   dt_txt = QDate(dt.year, dt.month, dt.day).toString("dd/MM/yyyy")
            except Exception: pass
            client_name = ""
            c = self._try_get(s, ["client", "customer"])
            if c:
                nm = self._try_get(c, ["name", "full_name"]); client_name = str(nm) if nm else ""
            else:
                cn = self._try_get(s, ["client_name", "customer_name"]); client_name = str(cn) if cn else ""
            status = self._try_get(s, ["status", "state"]) or ""
            sid = getattr(s, "id", None)
            parts = [p for p in [dt_txt, client_name, status] if p]
            text = " — ".join(parts) if parts else (f"Cita #{sid}" if sid else "Cita")
            self.lst_citas.addItem(QListWidgetItem(text))

    # ===== Guardar
    def _save(self):
        cu = get_current_user() or {}; role = cu.get("role", "artist")
        own_profile = (self._user_id is not None and cu.get("id") == self._user_id)

        if role == "artist" and not own_profile:
            self._toast("Permisos", "No puedes editar el perfil de otro usuario."); return
        if not can(role, "staff", "manage_users", user_id=cu.get("id")) and not own_profile:
            self._toast("Permisos", "No tienes permisos para guardar cambios."); return

        username = self._username.text().strip()
        rol_new  = self._role.currentText().strip()
        full_name = (self._full_name.text() or "").strip()
        email = (self._email.text() or "").strip()
        phone = (self._phone.text() or "").strip()
        ig_text = (self._instagram.text() or "@").strip()
        instagram = normalize_instagram(ig_text)  # ← guardamos sin @
        bq = self._birthdate.date(); birthdate_py = date(bq.year(), bq.month(), bq.day()) if bq.isValid() else None
        artist_name = (self._artist_name.text() or "").strip() if rol_new == "artist" else ""

        if not username or rol_new not in {"admin", "assistant", "artist"}:
            self._toast("Validación", "Usuario y rol son obligatorios."); return
        if rol_new == "artist" and not artist_name:
            self._toast("Validación", "El nombre de artista es obligatorio para el rol Tatuador."); return

        with SessionLocal() as db:
            try:
                if self._is_new:
                    new_artist_id = None
                    if rol_new == "artist": new_artist_id = self._create_artist(db, name=artist_name, active=True)
                    pwd_hash = auth.hash_password("temporal123")
                    u = User(username=username, role=rol_new, artist_id=new_artist_id, is_active=True,
                             name=full_name, birthdate=birthdate_py, email=email, phone=phone,
                             instagram=instagram, password_hash=pwd_hash)
                    db.add(u); db.commit()
                    self._user_id = u.id; self._is_new = False; self.staff_saved.emit()
                else:
                    u = db.query(User).get(self._user_id)
                    if not u: self._toast("Usuario", "El usuario ya no existe."); return
                    old_artist_id = u.artist_id
                    u.username = username; u.role = rol_new
                    u.name = full_name; u.birthdate = birthdate_py
                    u.email = email or None; u.phone = phone or None; u.instagram = (instagram or None)
                    if rol_new == "artist":
                        if old_artist_id:
                            a = db.query(Artist).get(old_artist_id)
                            if a and artist_name: a.name = artist_name
                        else:
                            new_artist_id = self._create_artist(db, name=artist_name, active=u.is_active)
                            u.artist_id = new_artist_id
                    else:
                        if old_artist_id:
                            self._set_artist_active(db, old_artist_id, False); u.artist_id = None
                    db.commit(); self.staff_saved.emit()

                u = db.query(User).get(self._user_id)
                self._paint_from_user(db, u); self._load_appointments(db, u)
                self._toggle_edit_widgets(False)
                self._toast("Staff", "Cambios guardados.")
            except IntegrityError:
                db.rollback(); self._toast("Usuario", "El usuario o email ya existen.", error=True)
            except Exception as e:
                db.rollback(); self._toast("Error", f"No se pudo guardar: {e}", error=True)

    def _create_artist(self, db: Session, name: str, active: bool = True) -> int:
        a = Artist(name=name or "Tatuador", rate_commission=0.0, active=active)
        db.add(a); db.flush(); return int(a.id)

    def _set_artist_active(self, db: Session, artist_id: Optional[int], active: bool):
        if not artist_id: return
        a = db.query(Artist).get(int(artist_id))
        if a and bool(a.active) != bool(active): a.active = bool(active)

    def _toggle_active(self):
        cu = get_current_user() or {}; role = cu.get("role", "artist")
        if role != "admin":
            self._toast("Permisos", "No puedes cambiar el estado de este usuario."); return
        with SessionLocal() as db:
            u = db.query(User).get(self._user_id)
            if not u: return
            u.is_active = not u.is_active
            if u.role == "artist" and u.artist_id:
                self._set_artist_active(db, u.artist_id, u.is_active)
            db.commit()
            self._current_is_active = bool(u.is_active)
            self._apply_artist_color(u.artist_id if u.role == "artist" else None)
            self._paint_from_user(db, u); self._load_appointments(db, u)
        self.staff_saved.emit()

    # ===== Foto / Contraseña / Color
    def _on_change_photo(self):
        if self._user_id is None or self._is_new:
            self._toast("Foto", "Primero guarda el usuario para poder asignar una foto."); return
        cu = get_current_user() or {}; role = cu.get("role", "artist"); own = cu.get("id") == self._user_id
        if role == "artist" and not own:
            self._toast("Permisos", "No puedes cambiar la foto de otro usuario."); return
        if role == "assistant" and not own:
            # elevación ya gestionada desde páginas comunes (si la usas aquí más adelante)
            pass

        fname, _ = QFileDialog.getOpenFileName(self, "Selecciona una imagen", "", "Imágenes (*.png *.jpg *.jpeg *.bmp)")
        if not fname: return
        pm = QPixmap(fname)
        if pm.isNull(): self._toast("Imagen", "No se pudo cargar la imagen seleccionada.", error=True); return
        out_pm = round_pixmap(pm, 256)  # ← common.round_pixmap
        dest = self._avatar_path(self._user_id)
        if not out_pm.save(str(dest), "PNG"): self._toast("Imagen", "No se pudo guardar la imagen.", error=True); return
        self.avatar.setPixmap(round_pixmap(QPixmap(str(dest)), 128)); self._position_photo_btn()
        self._toast("Foto", "Foto actualizada.")

    def _change_password(self):
        if self._user_id is None or self._is_new:
            self._toast("Contraseña", "Primero guarda el usuario."); return
        cu = get_current_user() or {}
        if cu.get("role") != "admin":
            self._toast("Permisos", "Solo el administrador puede cambiar contraseñas aquí."); return

        dlg = FramelessPanel("Cambiar contraseña", self)
        form = QFormLayout(); form.setContentsMargins(0,0,0,0)

        p1 = LocalizedLineEdit(); p1.setEchoMode(QLineEdit.Password); p1.setPlaceholderText("Nueva contraseña")
        p2 = LocalizedLineEdit(); p2.setEchoMode(QLineEdit.Password); p2.setPlaceholderText("Confirmar contraseña")
        form.addRow(p1); form.addRow(p2)

        row = HBox(); row.addStretch(1)
        b_cancel = QPushButton("Cancelar"); b_cancel.setObjectName("GhostSmall")
        b_ok = QPushButton("OK"); b_ok.setObjectName("CTA")
        row.addWidget(b_cancel); row.addWidget(b_ok)

        dlg.v.addLayout(form); dlg.v.addLayout(row)
        b_cancel.clicked.connect(dlg.reject)

        def do_ok():
            if not p1.text() or not p2.text():
                self._toast("Contraseña", "Llena ambos campos.", parent=dlg); return
            if p1.text() != p2.text():
                self._toast("Contraseña", "Las contraseñas no coinciden.", parent=dlg); return
            try:
                with SessionLocal() as db:
                    u = db.query(User).get(self._user_id)
                    if not u: self._toast("Usuario", "El usuario ya no existe.", parent=dlg); return
                    u.password_hash = auth.hash_password(p1.text()); db.commit()
                self._toast("Contraseña", "Contraseña actualizada.", parent=dlg)
                dlg.accept()
            except Exception as e:
                self._toast("Error", f"No se pudo actualizar: {e}", parent=dlg, error=True)

        b_ok.clicked.connect(do_ok)
        dlg.resize(360, 170); dlg.exec_()

    def _localize_color_dialog(self, cd: QColorDialog):
        cd.setOption(QColorDialog.NoButtons, True)
        map_btn = {
            "Pick Screen Color": "Tomar color de pantalla",
            "Add to Custom Colors": "Agregar a mis colores",
            "Add to custom colors": "Agregar a mis colores",
        }
        map_lbl = {
            "Basic colors": "Colores básicos",
            "Custom colors": "Colores personalizados",
            "Hue:": "Tono:", "Sat:": "Saturación:", "Val:": "Valor:",
            "Red:": "Rojo:", "Green:": "Verde:", "Blue:": "Azul:",
            "Alpha channel:": "Canal alfa:", "HTML:": "HTML:",
        }
        for w in cd.findChildren((QBtn, QLbl)):
            try:
                txt = w.text()
                if isinstance(w, QBtn) and txt in map_btn:
                    w.setText(map_btn[txt])
                    w.setStyleSheet("border-radius:8px; padding:6px 10px;")
                elif isinstance(w, QLbl) and txt in map_lbl:
                    w.setText(map_lbl[txt])
            except Exception:
                pass

    def _change_color(self):
        cu = get_current_user() or {}
        if cu.get("role") != "admin":
            self._toast("Permisos", "Solo el administrador puede cambiar el color."); return

        with SessionLocal() as db:
            u = db.query(User).get(self._user_id)
            if not u or not u.artist_id:
                self._toast("Color", "Este usuario no tiene perfil de artista."); return
            current_hex = self._artist_color_hex(u.artist_id)

        dlg = FramelessPanel("Color del artista", self)
        inner = QVBoxLayout(); inner.setSpacing(8)

        cd = QColorDialog(QColor(current_hex))
        cd.setOption(QColorDialog.DontUseNativeDialog, True)
        cd.setWindowFlags(cd.windowFlags() | Qt.FramelessWindowHint)
        cd.setOptions(QColorDialog.ShowAlphaChannel | QColorDialog.DontUseNativeDialog)
        self._localize_color_dialog(cd)
        inner.addWidget(cd)

        btns = QHBoxLayout(); btns.addStretch(1)
        b_cancel = QPushButton("Cancelar"); b_cancel.setObjectName("GhostSmall")
        b_ok = QPushButton("OK"); b_ok.setObjectName("CTA")
        btns.addWidget(b_cancel); btns.addWidget(b_ok); inner.addLayout(btns)
        dlg.v.addLayout(inner)

        def do_save():
            color = cd.currentColor()
            if not color.isValid(): dlg.reject(); return
            hexcol = color.name()
            # Guardar vía common.py
            save_artist_color(str(int(u.artist_id)), hexcol)
            self._apply_artist_color(u.artist_id)
            dlg.accept()

        b_cancel.clicked.connect(dlg.reject); b_ok.clicked.connect(do_save)
        dlg.resize(440, 400); dlg.exec_()

    # ===== RBAC
    def _apply_rbac(self, *, view_only: bool):
        cu = get_current_user() or {}; role = cu.get("role", "artist")
        tgt = self._user_id; own = (tgt is not None and cu.get("id") == tgt)
        show_kebab = (role == "admin") or (role == "assistant") or (role == "artist" and own)
        self._kebab_allowed = (show_kebab and not self._is_new); self.btn_kebab.hide()

        self.act_edit.setVisible(not self._is_new); self.act_edit.setEnabled(not self._edit_mode)
        self.act_toggle.setVisible(role == "admin" and not self._is_new)
        self.act_toggle.setText("Desactivar" if self._current_is_active else "Activar")
        self.act_password.setVisible(role == "admin" and not self._is_new)
        self.act_color.setVisible(role == "admin" and not self._is_new)

        if self._edit_mode:
            self._username.setReadOnly(role != "admin")
            self._role.setEnabled(role == "admin")
        else:
            self._username.setReadOnly(True); self._role.setEnabled(False)

        # Foto
        show_photo = False
        if not self._is_new and tgt is not None:
            if role in ("admin", "assistant"): show_photo = True
            elif role == "artist": show_photo = own
        self._photo_permission = show_photo

    # ===== Eventos de hover/kebab
    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.StatusTip and self._block_status_tips:
            return True
        if obj is self.card:
            if ev.type() in (QEvent.Enter, QEvent.HoverEnter, QEvent.MouseMove):
                if not self._edit_mode and self._kebab_allowed: self.btn_kebab.show()
            elif ev.type() in (QEvent.Leave, QEvent.HoverLeave):
                if not self._edit_mode: self.btn_kebab.hide()
        elif obj is self.avatar:
            if ev.type() in (QEvent.Enter, QEvent.HoverEnter):
                if getattr(self, "_photo_permission", False): self.btn_photo.show()
            elif ev.type() in (QEvent.Leave, QEvent.HoverLeave):
                self.btn_photo.hide()
        return super().eventFilter(obj, ev)

    def enterEvent(self, ev):
        if not self._edit_mode and self._kebab_allowed: self.btn_kebab.show()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        if not self._edit_mode: self.btn_kebab.hide()
        super().leaveEvent(ev)

    # ===== Navegación
    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            if self._edit_mode:
                self._toast("Cambios sin guardar", "Vas a salir sin guardar. Presiona ESC de nuevo para confirmar.")
                if hasattr(self, "_esc_armed") and self._esc_armed:
                    self._esc_armed = False; self.back_requested.emit(); return
                self._esc_armed = True
                return
            self.back_requested.emit()
        else:
            super().keyPressEvent(ev)

    # ===== Toast/alerta mini
    def _toast(self, title: str, text: str, parent: QWidget = None, error: bool = False):
        dlg = FramelessPanel(title, parent or self)
        body = QLabel(text); body.setWordWrap(True)
        dlg.v.addWidget(body)
        row = QHBoxLayout(); row.addStretch(1)
        ok = QPushButton("OK"); ok.setObjectName("CTA" if not error else "Danger")
        row.addWidget(ok); dlg.v.addLayout(row)
        ok.clicked.connect(dlg.accept)
        dlg.resize(360, 140); dlg.exec_()
