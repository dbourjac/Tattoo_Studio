from __future__ import annotations

from typing import Optional, Dict
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPainterPath
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTextEdit, QListWidget, QFrame, QLineEdit, QSpacerItem, QSizePolicy,
    QComboBox, QCheckBox, QMessageBox, QFileDialog, QGridLayout
)

# BD
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from data.db.session import SessionLocal
from data.models.user import User
from data.models.artist import Artist
from data.models.session_tattoo import TattooSession
from data.models.transaction import Transaction

# Auth/perm
from services.contracts import get_current_user
from services import auth
from services.permissions import can

# Elevación (código maestro) para assistant (cambio de foto ajena)
from ui.pages.common import request_elevation_if_needed


def _role_text(role: str) -> str:
    return {"admin": "Admin", "assistant": "Asistente", "artist": "Tatuador"}.get(role, role)


class StaffDetailPage(QWidget):
    back_requested = pyqtSignal()
    staff_saved = pyqtSignal()
    # staff_deleted = pyqtSignal()  # eliminado de la UX

    def __init__(self):
        super().__init__()

        self._user_id: Optional[int] = None
        self._is_new: bool = False
        self._edit_mode: bool = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # ============== Toolbar superior ==============
        topbar = QFrame()
        topbar.setObjectName("Toolbar")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(12, 8, 12, 8)
        tb.setSpacing(8)

        self.btn_back = QPushButton("← Volver")
        self.btn_back.setObjectName("GhostSmall")
        self.btn_back.clicked.connect(self._on_back_clicked)
        tb.addWidget(self.btn_back)

        tb.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.btn_edit = QPushButton("Editar");     self.btn_edit.setObjectName("GhostSmall")
        self.btn_save = QPushButton("Guardar");    self.btn_save.setObjectName("CTA")
        self.btn_cancel = QPushButton("Cancelar"); self.btn_cancel.setObjectName("GhostSmall")
        self.btn_toggle = QPushButton("Desactivar"); self.btn_toggle.setObjectName("GhostSmall")
        self.btn_password = QPushButton("Cambiar contraseña"); self.btn_password.setObjectName("GhostSmall")

        self.btn_edit.clicked.connect(self._enter_edit)
        self.btn_save.clicked.connect(self._save)
        self.btn_cancel.clicked.connect(self._cancel_edit)
        self.btn_toggle.clicked.connect(self._toggle_active)
        self.btn_password.clicked.connect(self._change_password)

        for b in (self.btn_edit, self.btn_save, self.btn_cancel, self.btn_toggle, self.btn_password):
            tb.addWidget(b)

        root.addWidget(topbar)

        # ============================== Header Card ==============================
        header = QFrame()
        header.setObjectName("Card")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 14, 14, 14)
        hl.setSpacing(14)

        # Columna avatar + acción
        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        self.avatar = QLabel()
        self.avatar.setFixedSize(96, 96)
        self.avatar.setStyleSheet("background: transparent;")
        left_col.addWidget(self.avatar, alignment=Qt.AlignTop)

        self.btn_photo = QPushButton("Cambiar foto")
        self.btn_photo.setObjectName("GhostSmall")
        self.btn_photo.setMinimumHeight(28)
        self.btn_photo.clicked.connect(self._on_change_photo)
        left_col.addWidget(self.btn_photo)

        hl.addLayout(left_col)

        # Columna datos
        col = QVBoxLayout(); col.setSpacing(6)
        self.lbl_name = QLabel("—")
        self.lbl_name.setStyleSheet("font-weight:700; font-size:16pt; background: transparent;")
        col.addWidget(self.lbl_name)

        badges = QHBoxLayout(); badges.setSpacing(10)
        self.lbl_role  = QLabel("—");  self.lbl_role.setStyleSheet("color:#6C757D; background: transparent;")
        self.lbl_state = QLabel("—");  self.lbl_state.setStyleSheet("color:#6C757D; background: transparent;")
        badges.addWidget(self.lbl_role); badges.addWidget(self.lbl_state); badges.addStretch(1)
        col.addLayout(badges)

        hl.addLayout(col, stretch=1)
        root.addWidget(header)

        # ============================== Tabs ==============================
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, stretch=1)

        self.tab_perfil = QWidget(); self._mk_perfil(self.tab_perfil)
        self.tab_disp   = QWidget(); self._mk_text(self.tab_disp, "Disponibilidad semanal (placeholder)")
        self.tab_port   = QWidget(); self._mk_list(self.tab_port, [])
        self.tab_citas  = QWidget(); self._mk_list(self.tab_citas, [])
        self.tab_docs   = QWidget(); self._mk_text(self.tab_docs, "Documentos (placeholder)")
        self.tab_comm   = QWidget(); self._mk_text(self.tab_comm, "Comisiones (placeholder)")

        self.tabs.addTab(self.tab_perfil, "Perfil")
        self.tabs.addTab(self.tab_disp,   "Disponibilidad")
        self.tabs.addTab(self.tab_port,   "Portafolio")
        self.tabs.addTab(self.tab_citas,  "Citas")
        self.tabs.addTab(self.tab_docs,   "Documentos")
        self.tabs.addTab(self.tab_comm,   "Comisiones")

        self._apply_rbac_to_buttons(view_only=True)

    # ============================ API pública ============================
    def load_staff(self, staff: Dict):
        self._is_new = False
        self._user_id = int(staff.get("id"))
        self._edit_mode = False

        with SessionLocal() as db:
            u = db.query(User).get(self._user_id)
            if not u:
                self.lbl_name.setText(staff.get("nombre", "—"))
                self._apply_rbac_to_buttons(view_only=True)
                return
            self._paint_from_user(db, u)

        self._apply_rbac_to_buttons(view_only=True)

    def start_create_mode(self):
        self._is_new = True
        self._user_id = None
        self._edit_mode = True

        self._username.setText("")
        self._role.setCurrentText("assistant")
        self._fill_artists_combo()
        self._artist.setCurrentIndex(0)
        self._active.setChecked(True)

        visible_name = "(nuevo usuario)"
        self.lbl_name.setText(visible_name)
        self.lbl_role.setText("Asistente")
        self.lbl_state.setText("Activo")
        self.avatar.setPixmap(self._make_avatar_pixmap(96, visible_name))

        self._toggle_edit_widgets(True)
        self._apply_rbac_to_buttons(view_only=False)

    # ============================ Helpers UI ============================
    def _mk_perfil(self, w: QWidget):
        outer = QVBoxLayout(w); outer.setSpacing(8)

        card = QFrame(); card.setObjectName("Card")
        lay = QVBoxLayout(card); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)

        # Usuario
        lbl1 = QLabel("Usuario:"); lbl1.setStyleSheet("background: transparent;")
        self._username = QLineEdit(); self._username.setReadOnly(True)
        grid.addWidget(lbl1, 0, 0, Qt.AlignRight)
        grid.addWidget(self._username, 0, 1)

        # Rol
        lbl2 = QLabel("Rol:"); lbl2.setStyleSheet("background: transparent;")
        self._role = QComboBox(); self._role.addItems(["admin", "assistant", "artist"])
        self._role.currentTextChanged.connect(self._on_role_changed)
        self._role.setEnabled(False)
        grid.addWidget(lbl2, 1, 0, Qt.AlignRight)
        grid.addWidget(self._role, 1, 1)

        # Artista (si rol=artist)
        lbl3 = QLabel("Artista:"); lbl3.setStyleSheet("background: transparent;")
        self._artist = QComboBox(); self._artist.setEnabled(False)
        grid.addWidget(lbl3, 2, 0, Qt.AlignRight)
        grid.addWidget(self._artist, 2, 1)

        # Activo (único switch)
        self._active = QCheckBox("Activo")
        self._active.setEnabled(False)
        grid.addWidget(self._active, 3, 1, Qt.AlignLeft)

        lay.addLayout(grid)
        outer.addWidget(card)

    def _mk_text(self, w: QWidget, text: str):
        outer = QVBoxLayout(w); outer.setSpacing(8)
        card = QFrame(); card.setObjectName("Card")
        lay = QVBoxLayout(card); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(8)
        te = QTextEdit(); te.setPlainText(text)
        lay.addWidget(te)
        outer.addWidget(card)

    def _mk_list(self, w: QWidget, items):
        outer = QVBoxLayout(w); outer.setSpacing(8)
        card = QFrame(); card.setObjectName("Card")
        lay = QVBoxLayout(card); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(8)
        lst = QListWidget(); lst.addItems(items)
        lay.addWidget(lst)
        outer.addWidget(card)

    # ============================ Avatar helpers ============================
    def _project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _avatar_dir(self) -> Path:
        p = self._project_root() / "assets" / "avatars"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _avatar_path(self, uid: int) -> Path:
        return self._avatar_dir() / f"{uid}.png"

    def _round_pixmap(self, pm: QPixmap, size: int) -> QPixmap:
        if pm.isNull():
            out = QPixmap(size, size); out.fill(Qt.transparent)
            return out
        pm = pm.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        out = QPixmap(size, size); out.fill(Qt.transparent)
        p = QPainter(out); p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath(); path.addEllipse(0, 0, size, size)
        p.setClipPath(path)
        p.drawPixmap(0, 0, pm)
        p.end()
        return out

    def _make_avatar_pixmap(self, size: int, nombre: str) -> QPixmap:
        initials = "".join([p[0].upper() for p in (nombre or "").split()[:2]]) or "?"
        pm = QPixmap(size, size); pm.fill(Qt.transparent)
        p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#d1d5db"))
        p.setPen(Qt.NoPen); p.drawEllipse(0, 0, size, size)
        p.setPen(QColor("#111")); p.drawText(pm.rect(), Qt.AlignCenter, initials)
        p.end()
        return pm

    def _set_avatar_from_disk_or_placeholder(self, db: Session, u: User, size: int = 96):
        ap = self._avatar_path(u.id)
        if ap.exists():
            pm = QPixmap(str(ap))
            self.avatar.setPixmap(self._round_pixmap(pm, size))
        else:
            artist_name = None
            if u.role == "artist" and u.artist_id:
                a = db.query(Artist).get(u.artist_id)
                artist_name = a.name if a else None
            visible = artist_name or u.username
            self.avatar.setPixmap(self._make_avatar_pixmap(size, visible))

    # ============================ Internos ============================
    def _fill_artists_combo(self):
        self._artist.clear()
        self._artist.addItem("—", None)
        with SessionLocal() as db:
            rows = db.query(Artist.id, Artist.name, Artist.active).order_by(Artist.name.asc()).all()
            for aid, name, active in rows:
                label = name if active else f"{name} (inactivo)"
                self._artist.addItem(label, aid)

    def _paint_from_user(self, db: Session, u: User):
        artist_name = None
        if u.role == "artist" and u.artist_id:
            a = db.query(Artist).get(u.artist_id)
            if a:
                artist_name = a.name
        visible_name = artist_name or u.username

        self.lbl_name.setText(visible_name)
        self.lbl_role.setText(_role_text(u.role))
        self.lbl_state.setText("Activo" if u.is_active else "Inactivo")

        self._set_avatar_from_disk_or_placeholder(db, u, size=96)

        # Perfil
        self._username.setText(u.username)
        self._role.setCurrentText(u.role)
        self._fill_artists_combo()
        if u.role == "artist" and u.artist_id:
            idx = self._artist.findData(u.artist_id)
            self._artist.setCurrentIndex(max(0, idx))
        else:
            self._artist.setCurrentIndex(0)
        self._active.setChecked(bool(u.is_active))

        self._toggle_edit_widgets(False)

    def _toggle_edit_widgets(self, on: bool):
        self._username.setReadOnly(not on)
        self._role.setEnabled(on)
        self._artist.setEnabled(on and (self._role.currentText() == "artist"))
        self._active.setEnabled(on)

    def _on_role_changed(self, role: str):
        self._artist.setEnabled(self._edit_mode and role == "artist")

    def _enter_edit(self):
        self._edit_mode = True
        self._toggle_edit_widgets(True)
        self._apply_rbac_to_buttons(view_only=False)

    def _cancel_edit(self):
        if self._is_new:
            self.back_requested.emit()
            return
        with SessionLocal() as db:
            u = db.query(User).get(self._user_id)
            if u:
                self._paint_from_user(db, u)
        self._edit_mode = False
        self._apply_rbac_to_buttons(view_only=True)

    # ---------- reglas negocio: histórico del artista ----------
    def _artist_has_history(self, db: Session, artist_id: int) -> bool:
        if not artist_id:
            return False
        has_sessions = db.query(TattooSession.id).filter(TattooSession.artist_id == artist_id).limit(1).first() is not None
        has_tx = db.query(Transaction.id).filter(Transaction.artist_id == artist_id).limit(1).first() is not None
        return bool(has_sessions or has_tx)

    # ---------- guardar ----------
    def _save(self):
        cu = get_current_user() or {}
        if not can(cu.get("role", "artist"), "staff", "manage_users", user_id=cu.get("id")):
            QMessageBox.warning(self, "Permisos", "No tienes permisos para guardar cambios.")
            return

        username = self._username.text().strip()
        role = self._role.currentText().strip()
        artist_id = self._artist.currentData()
        is_active = self._active.isChecked()

        if not username or role not in {"admin", "assistant", "artist"}:
            QMessageBox.warning(self, "Validación", "Usuario y rol son obligatorios.")
            return

        with SessionLocal() as db:
            try:
                if self._is_new:
                    # Si es artist y no seleccionó uno, crea automáticamente (activo seg. estado del usuario)
                    new_artist_id = None
                    if role == "artist":
                        if not artist_id:
                            new_artist_id = self._create_artist(db, name=username, active=is_active)
                        else:
                            new_artist_id = artist_id
                            self._set_artist_active(db, new_artist_id, is_active)

                    pwd_hash = auth.hash_password("temporal123")
                    u = User(username=username, role=role, artist_id=new_artist_id, is_active=is_active, password_hash=pwd_hash)
                    db.add(u)
                    db.commit()
                    self._user_id = u.id
                    self._is_new = False
                    self.staff_saved.emit()

                else:
                    u = db.query(User).get(self._user_id)
                    if not u:
                        QMessageBox.warning(self, "Usuario", "El usuario ya no existe.")
                        return

                    old_role = u.role
                    old_artist_id = u.artist_id

                    u.username = username
                    u.role = role
                    u.is_active = is_active

                    if role == "artist":
                        # crear/vincular si no hay
                        if not artist_id:
                            new_artist_id = self._create_artist(db, name=username, active=is_active)
                            u.artist_id = new_artist_id
                        else:
                            # ¿cambio de vínculo? solo si no hay historial del anterior
                            if old_artist_id and artist_id != old_artist_id:
                                if self._artist_has_history(db, old_artist_id):
                                    db.rollback()
                                    QMessageBox.warning(self, "Vínculo",
                                        "Este usuario ya tiene historial como artista. No se puede cambiar "
                                        "la vinculación a otro artista.")
                                    self._paint_from_user(db, u)
                                    return
                            u.artist_id = artist_id
                            self._set_artist_active(db, artist_id, is_active)
                    else:
                        # dejó de ser artist → archivar Artist vinculado y desvincular
                        if old_artist_id:
                            self._set_artist_active(db, old_artist_id, False)
                        u.artist_id = None

                    db.commit()
                    self.staff_saved.emit()

                # Refrescar
                u = db.query(User).get(self._user_id)
                self._paint_from_user(db, u)
                self._edit_mode = False
                self._apply_rbac_to_buttons(view_only=True)
                QMessageBox.information(self, "Staff", "Cambios guardados.")

            except IntegrityError:
                db.rollback()
                QMessageBox.critical(self, "Usuario", "El nombre de usuario ya existe.")
            except Exception as e:
                db.rollback()
                QMessageBox.critical(self, "Error", f"No se pudo guardar: {e}")

    def _create_artist(self, db: Session, name: str, active: bool = True) -> int:
        """Crea un Artist básico y devuelve su id."""
        a = Artist(name=name or "Tatuador", rate_commission=0.0, active=active)
        db.add(a)
        db.flush()  # para obtener a.id sin cerrar transacción
        return int(a.id)

    def _set_artist_active(self, db: Session, artist_id: Optional[int], active: bool):
        if not artist_id:
            return
        a = db.query(Artist).get(int(artist_id))
        if a and bool(a.active) != bool(active):
            a.active = bool(active)

    def _toggle_active(self):
        cu = get_current_user() or {}
        if not can(cu.get("role", "artist"), "staff", "toggle_active", user_id=cu.get("id")):
            QMessageBox.warning(self, "Permisos", "No puedes cambiar el estado de este usuario.")
            return

        with SessionLocal() as db:
            u = db.query(User).get(self._user_id)
            if not u:
                return
            # Alterna usuario
            u.is_active = not u.is_active
            # Y sincroniza Artist si aplica
            if u.role == "artist" and u.artist_id:
                self._set_artist_active(db, u.artist_id, u.is_active)
            db.commit()
            self._paint_from_user(db, u)

        # Actualiza label del botón
        self.btn_toggle.setText("Desactivar" if self._active.isChecked() else "Activar")
        self.staff_saved.emit()

    def _on_back_clicked(self):
        if self._edit_mode:
            res = QMessageBox.question(self, "Cambios sin guardar",
                                       "Tienes cambios sin guardar. ¿Salir de todos modos?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if res != QMessageBox.Yes:
                return
        self.back_requested.emit()

    # ============================ Botones / RBAC ============================
    def _apply_rbac_to_buttons(self, *, view_only: bool):
        cu = get_current_user() or {}
        role = cu.get("role", "artist")
        is_admin = (role == "admin")
        target_id = self._user_id
        own_profile = target_id is not None and cu.get("id") == target_id

        self.btn_edit.setVisible(is_admin and view_only and not self._is_new)
        self.btn_save.setVisible(is_admin and not view_only)
        self.btn_cancel.setVisible(is_admin and not view_only)
        self.btn_toggle.setVisible(is_admin and not self._is_new)
        self.btn_password.setVisible(is_admin and not self._is_new)

        self.btn_edit.setEnabled(is_admin and view_only and not self._is_new)
        self.btn_save.setEnabled(is_admin and not view_only)
        self.btn_cancel.setEnabled(is_admin and not view_only)
        self.btn_toggle.setEnabled(is_admin and not self._is_new)
        self.btn_password.setEnabled(is_admin and not self._is_new)

        # Cambiar foto: admin siempre; assistant la propia (otras con elevación); artist solo propia
        show_photo_btn = False
        if self._is_new or target_id is None:
            show_photo_btn = False
        elif is_admin:
            show_photo_btn = True
        elif role == "assistant":
            show_photo_btn = True  # la suya siempre; otras con elevación dentro de _on_change_photo
        elif role == "artist":
            show_photo_btn = own_profile

        self.btn_photo.setVisible(show_photo_btn)
        self.btn_photo.setEnabled(show_photo_btn)

        # Texto del toggle acorde al estado actual
        self.btn_toggle.setText("Desactivar" if self._active.isChecked() else "Activar")

    # ============================ Acciones especiales ============================
    def _on_change_photo(self):
        if self._user_id is None or self._is_new:
            QMessageBox.information(self, "Foto", "Primero guarda el usuario para poder asignar una foto.")
            return

        cu = get_current_user() or {}
        role = cu.get("role", "artist")
        own_profile = cu.get("id") == self._user_id

        if role == "artist" and not own_profile:
            QMessageBox.warning(self, "Permisos", "No puedes cambiar la foto de otro usuario.")
            return
        if role == "assistant" and not own_profile:
            if not request_elevation_if_needed(self, "staff", "change_photo"):
                return

        fname, _ = QFileDialog.getOpenFileName(self, "Selecciona una imagen",
                                               "", "Imágenes (*.png *.jpg *.jpeg *.bmp)")
        if not fname:
            return

        pm = QPixmap(fname)
        if pm.isNull():
            QMessageBox.warning(self, "Imagen", "No se pudo cargar la imagen seleccionada.")
            return

        out_pm = self._round_pixmap(pm, 256)
        dest = self._avatar_path(self._user_id)
        try:
            out_pm.save(str(dest), "PNG")
        except Exception as e:
            QMessageBox.critical(self, "Imagen", f"No se pudo guardar la imagen: {e}")
            return

        self.avatar.setPixmap(self._round_pixmap(QPixmap(str(dest)), 96))
        QMessageBox.information(self, "Foto", "Foto actualizada.")

    def _change_password(self):
        cu = get_current_user() or {}
        if cu.get("role") != "admin":
            QMessageBox.warning(self, "Permisos", "Solo el administrador puede cambiar contraseñas aquí.")
            return
        if self._user_id is None or self._is_new:
            QMessageBox.information(self, "Contraseña", "Primero guarda el usuario.")
            return

        from PyQt5.QtWidgets import QInputDialog, QLineEdit
        pwd1, ok1 = QInputDialog.getText(self, "Nueva contraseña", "Escribe la nueva contraseña:",
                                         QLineEdit.Password)
        if not ok1 or not pwd1:
            return
        pwd2, ok2 = QInputDialog.getText(self, "Confirmar contraseña", "Confirma la nueva contraseña:",
                                         QLineEdit.Password)
        if not ok2 or not pwd2:
            return
        if pwd1 != pwd2:
            QMessageBox.warning(self, "Contraseña", "Las contraseñas no coinciden.")
            return

        with SessionLocal() as db:
            try:
                u = db.query(User).get(self._user_id)
                if not u:
                    QMessageBox.warning(self, "Usuario", "El usuario ya no existe.")
                    return
                u.password_hash = auth.hash_password(pwd1)
                db.commit()
                QMessageBox.information(self, "Contraseña", "Contraseña actualizada.")
            except Exception as e:
                db.rollback()
                QMessageBox.critical(self, "Error", f"No se pudo actualizar: {e}")
