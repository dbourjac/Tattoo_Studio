from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple
from sqlalchemy import func

from PyQt5.QtCore import Qt, QSize, QRect, QPoint
from PyQt5.QtGui import QPixmap, QPainter, QFont, QCursor, QColor
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QLineEdit, QFrame, QScrollArea, QPushButton, QSizePolicy, QLayout, QDialog,
    QSpacerItem, QMessageBox, QGraphicsDropShadowEffect
)

# Data / ORM
from data.db.session import SessionLocal
from data.models.artist import Artist
from data.models.portfolio import PortfolioItem
from data.models.session_tattoo import TattooSession
from data.models.client import Client
from data.models.transaction import Transaction

import shutil
from PyQt5.QtWidgets import QFileDialog, QToolButton, QComboBox
from sqlalchemy.orm import Session
from data.models.user import User
from ui.pages.common import (
    make_styled_menu, role_to_label, load_artist_colors, fallback_color_for, round_pixmap
)


# ----------------------------------------------------------------------
# Pequeño FlowLayout para grid fluido (adaptado del ejemplo oficial Qt)
# ----------------------------------------------------------------------
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, hspacing=10, vspacing=10):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)
        self._h = hspacing
        self._v = vspacing

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, i): return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i): return self._items.pop(i) if 0 <= i < len(self._items) else None
    def expandingDirections(self): return Qt.Orientations(Qt.Orientation(0))
    def hasHeightForWidth(self): return True

    def heightForWidth(self, width):
        h = self.doLayout(QRect(0, 0, width, 0), True)
        return h

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self): return QSize(400, 300)
    def minimumSize(self): return QSize(200, 150)

    def doLayout(self, rect, test_only):
        x = rect.x(); y = rect.y()
        line_height = 0
        for item in self._items:
            wid = item.widget()
            space_x = self._h; space_y = self._v
            next_x = x + wid.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + wid.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), wid.sizeHint()))
            x = next_x
            line_height = max(line_height, wid.sizeHint().height())
        return y + line_height - rect.y()

# ----------------------------------------------------------------------
# Data access (servicio mínimo local, usa SessionLocal)
# ----------------------------------------------------------------------
class PortfolioService:
    @staticmethod
    def users_with_counts() -> List[dict]:
        """
        Devuelve lista de dicts:
        { id, name, role, is_active, artist_id, email, instagram, count }
        Cuenta piezas por user_id si existe, si no, cae al artist_id (para piezas viejas).
        """
        from data.db.session import SessionLocal
        with SessionLocal() as db:  # type: Session
            # base users (cualquier rol)
            rows = (
                db.query(
                    User.id, User.username, User.role, User.is_active, User.artist_id,
                    User.email, User.instagram, Artist.name.label("artist_name")
                )
                .outerjoin(Artist, Artist.id == User.artist_id)
                .order_by(User.role.desc(), User.is_active.desc(), (Artist.name.is_(None)).asc(), Artist.name.asc(), User.username.asc())
                .all()
            )

            # conteos por user_id (si la columna existe en el modelo/tabla)
            counts_user = {}
            try:
                counts_user = dict(
                    db.query(PortfolioItem.user_id, func.count(PortfolioItem.id))
                      .filter(PortfolioItem.user_id.isnot(None))
                      .group_by(PortfolioItem.user_id).all()
                )
            except Exception:
                counts_user = {}

            # conteos por artist_id (para piezas antiguas sin user_id)
            counts_artist = dict(
                db.query(PortfolioItem.artist_id, func.count(PortfolioItem.id))
                  .filter(PortfolioItem.artist_id.isnot(None))
                  .group_by(PortfolioItem.artist_id).all()
            )

            out = []
            for (uid, username, role, is_active, artist_id, email, instagram, artist_name) in rows:
                # nombre mostrado: artista -> nombre de artista; otros -> username
                name = artist_name if (role == "artist" and artist_name) else (username or "")
                # preferimos conteo por user_id; si es cero y hay artist_id, usamos fallback
                c = int(counts_user.get(uid, 0))
                if c == 0 and artist_id is not None:
                    c = int(counts_artist.get(artist_id, 0) or 0)
                out.append({
                    "id": uid, "name": name, "role": role, "is_active": bool(is_active),
                    "artist_id": artist_id, "email": email or "", "instagram": ("@" + (instagram or "").lstrip("@")) if instagram else "",
                    "count": c,
                })
            return out

    @staticmethod
    def portfolio_for_user(user_id: int, artist_id: Optional[int], limit=60, offset=0) -> List[PortfolioItem]:
        """Trae piezas por user_id si existe; si no, cae a artist_id."""
        from data.db.session import SessionLocal
        with SessionLocal() as db:
            q = db.query(PortfolioItem).order_by(PortfolioItem.created_at.desc(), PortfolioItem.id.desc())
            # preferimos user_id si la columna existe en el modelo
            try:
                q_user = q.filter(PortfolioItem.user_id == user_id)
                rows = q_user.limit(limit).offset(offset).all()
                if rows:  # si hay por user_id, devolvemos eso
                    return rows
            except Exception:
                pass
            if artist_id is not None:
                return q.filter(PortfolioItem.artist_id == artist_id).limit(limit).offset(offset).all()
            return []

    @staticmethod
    def add_items_for_user(user: dict, file_paths: List[str], session_id: Optional[int] = None) -> int:
        """
        Copia archivos a assets/uploads/portfolios/<user_id>/ y crea PortfolioItem(s).
        Intenta setear user_id; si no existe la columna, cae a artist_id.
        """
        from pathlib import Path
        from data.db.session import SessionLocal
        saved = 0
        base = Path(__file__).resolve().parents[2] / "assets" / "uploads" / "portfolios" / str(int(user["id"]))
        base.mkdir(parents=True, exist_ok=True)

        with SessionLocal() as db:
            for src in file_paths:
                src = Path(src)
                if not src.exists():
                    continue
                dst = base / src.name
                # Evitar colisiones sencillas
                i = 1
                while dst.exists():
                    dst = base / f"{src.stem}_{i}{src.suffix}"
                    i += 1
                shutil.copy2(str(src), str(dst))

                item = PortfolioItem()
                # preferimos user_id, si está en el modelo
                set_user_ok = False
                try:
                    setattr(item, "user_id", int(user["id"]))
                    set_user_ok = True
                except Exception:
                    set_user_ok = False

                # artist_id como respaldo si no hay user_id en el modelo
                if not set_user_ok and user.get("artist_id") is not None:
                    try:
                        setattr(item, "artist_id", int(user["artist_id"]))
                    except Exception:
                        pass

                # camino de imagen y vínculos opcionales
                item.path = str(dst)
                try:
                    if session_id is not None:
                        setattr(item, "session_id", int(session_id))
                        # Si hay sesión, completa artist_id / client_id desde la sesión
                        try:
                            if session_id is not None:
                                sess = db.query(TattooSession).filter(TattooSession.id == int(session_id)).first()
                                if sess:
                                    if getattr(sess, "artist_id", None) and not getattr(item, "artist_id", None):
                                        item.artist_id = int(sess.artist_id)
                                    if getattr(sess, "client_id", None) and not getattr(item, "client_id", None):
                                        item.client_id = int(sess.client_id)
                        except Exception:
                            pass
                except Exception:
                    pass

                db.add(item)
                saved += 1
            db.commit()
        return saved

    @staticmethod
    def recent_sessions_for_artist(artist_id: int, limit: int = 20) -> List[Tuple[int, str]]:
        """Devuelve [(session_id, label)] para seleccionar rápido en el diálogo de subir."""
        from data.db.session import SessionLocal
        with SessionLocal() as db:
            rows = (
                db.query(TattooSession.id, TattooSession.start, Client.name)
                .outerjoin(Client, Client.id == TattooSession.client_id)
                .filter(TattooSession.artist_id == artist_id)
                .order_by(TattooSession.start.desc(), TattooSession.id.desc())
                .limit(limit).all()
            )
            out = []
            for sid, dt, cname in rows:
                # dt es 'start' (DateTime); puede venir None
                date_txt = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") and dt else ""
                label = f"#{sid} · {date_txt} · {cname or '—'}"
                out.append((sid, label))
            return out


    @staticmethod
    def portfolio_for_artist(artist_id: int, limit=60, offset=0) -> List[PortfolioItem]:
        from data.db.session import SessionLocal
        with SessionLocal() as db:
            return (
                db.query(PortfolioItem)
                  .filter(PortfolioItem.artist_id == artist_id)
                  .order_by(PortfolioItem.created_at.desc(), PortfolioItem.id.desc())
                  .limit(limit).offset(offset)
                  .all()
            )

    @staticmethod
    def item_detail(item_id: int) -> dict:
        from data.db.session import SessionLocal
        with SessionLocal() as db:
            it = db.query(PortfolioItem).filter(PortfolioItem.id == item_id).first()
            if not it:
                return {}
            artist = None
            session = None
            client = None
            tx = None
            try:
                if getattr(it, "artist_id", None):
                    artist = db.query(Artist).filter(Artist.id == it.artist_id).first()
                if getattr(it, "session_id", None):
                    session = db.query(TattooSession).filter(TattooSession.id == it.session_id).first()
                if getattr(it, "client_id", None):
                    client = db.query(Client).filter(Client.id == it.client_id).first()
                if getattr(it, "transaction_id", None):
                    tx = db.query(Transaction).filter(Transaction.id == it.transaction_id).first()
            except Exception:
                pass
            return {"item": it, "artist": artist, "session": session, "client": client, "transaction": tx}
        
    @staticmethod
    def portfolio_for_client(client_id: int, limit=200, offset=0):
        """Trae piezas (PortfolioItem) vinculadas a un cliente específico."""
        from data.db.session import SessionLocal
        with SessionLocal() as db:
            return (
                db.query(PortfolioItem)
                  .filter(PortfolioItem.client_id == client_id)
                  .order_by(PortfolioItem.created_at.desc(), PortfolioItem.id.desc())
                  .limit(limit)
                  .offset(offset)
                  .all()
            )

# ----------------------------------------------------------------------
# Tarjeta de pieza (thumbnail + overlay simple)
# ----------------------------------------------------------------------
class PortfolioCard(QFrame):
    def __init__(self, item: PortfolioItem, on_click, parent=None):
        super().__init__(parent)
        self.setObjectName("portfolioCard")
        self.item = item
        self.on_click = on_click

        self.setStyleSheet("""
        QFrame#portfolioCard {
            background: #151a21;
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
        }
        QFrame#portfolioCard:hover {
            border-color: rgba(255,255,255,0.18);
        }
        """)

        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(14)
        eff.setOffset(0, 2)
        eff.setColor(QColor(0, 0, 0, 120))
        self.setGraphicsEffect(eff)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        lay = QVBoxLayout(self); lay.setContentsMargins(8,8,8,8); lay.setSpacing(6)
        self.lbl_img = QLabel(self); self.lbl_img.setAlignment(Qt.AlignCenter)
        self.lbl_img.setFixedHeight(260)     # altura target de miniatura
        self.lbl_meta = QLabel(self); self.lbl_meta.setStyleSheet("color:#AAB; font-size:11px;")
        self.lbl_meta.setWordWrap(True)
        lay.addWidget(self.lbl_img)
        lay.addWidget(self.lbl_meta)

        self._load_image()
        self._load_meta()

    def sizeHint(self): return QSize(220, 280)

    def _load_image(self):
        path = self.item.path or ""
        if path and Path(path).exists():
            self._pm_base = QPixmap(path)
        else:
            pm = QPixmap(40, 40); pm.fill(Qt.darkGray)
            p = QPainter(pm); p.setPen(Qt.lightGray); p.setFont(QFont("Segoe UI", 10))
            p.drawText(2, 22, "no img"); p.end()
            self._pm_base = pm
        self._apply_scaled()
        
    def _apply_scaled(self):
        if self._pm_base and not self._pm_base.isNull():
            self.lbl_img.setPixmap(self._pm_base.scaledToHeight(260, Qt.SmoothTransformation))


    def resizeEvent(self, ev):
            super().resizeEvent(ev)
            self._apply_scaled()
            
    def _load_meta(self):
        dt = getattr(self.item, "created_at", None)
        when = dt.strftime("%Y-%m-%d") if dt else "¿?"
        self.lbl_meta.setText(f"{when}")

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and callable(self.on_click):
            self.on_click(self.item)
        elif ev.button() == Qt.RightButton:
            m = make_styled_menu(self)
            act = m.addAction("Ver detalles")
            chosen = m.exec_(QCursor.pos())
            if chosen == act and callable(self.on_click):
                self.on_click(self.item)
        super().mousePressEvent(ev)

# ----------------------------------------------------------------------
# Diálogo de detalle
# ----------------------------------------------------------------------
class PortfolioDetailDialog(QDialog):
    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        outer = QFrame(self); outer.setObjectName("outer"); root.addWidget(outer)
        col = QVBoxLayout(outer); col.setContentsMargins(16,16,16,16); col.setSpacing(10)

        item: PortfolioItem = payload["item"]
        artist: Optional[Artist] = payload.get("artist")
        session: Optional[TattooSession] = payload.get("session")
        client: Optional[Client] = payload.get("client")
        tx: Optional[Transaction] = payload.get("transaction")

        title = QLabel(f"Detalle de pieza — {artist.name if artist else 'Artista'}", outer)
        title.setStyleSheet("font-weight:700; font-size:14px;")
        col.addWidget(title)

        body = QHBoxLayout(); body.setSpacing(14)
        # Imagen grande
        img_box = QVBoxLayout()
        lbl_big = QLabel(); lbl_big.setAlignment(Qt.AlignCenter)
        pm = QPixmap(item.path) if item.path and Path(item.path).exists() else QPixmap(80,80)
        if pm.isNull():
            pm = QPixmap(80,80); pm.fill(Qt.darkGray)
        lbl_big.setPixmap(pm.scaledToWidth(640, Qt.SmoothTransformation))
        img_box.addWidget(lbl_big)
        body.addLayout(img_box, 3)

        # Metadatos
        meta = QVBoxLayout(); meta.setSpacing(6)
        def row(k,v):
            lab = QLabel(f"<b>{k}:</b> {v or '-'}"); lab.setTextFormat(Qt.RichText); return lab
        meta.addWidget(row("Fecha", item.created_at.strftime("%Y-%m-%d") if item.created_at else None))
        meta.addWidget(row("Artista", artist.name if artist else None))
        if session:
            meta.addWidget(row("Sesión", f"#{session.id} — {session.status} ${session.price:.2f}"))
        if client:
            meta.addWidget(row("Cliente", client.name))
        if tx:
            meta.addWidget(row("Transacción", f"#{tx.id} ${tx.amount:.2f} {tx.method}"))
        meta.addWidget(row("Notas", getattr(item, "caption", None)))
        meta.addStretch(1)

        # Botones (cerrar)
        btns = QHBoxLayout(); btns.addStretch(1)
        b_close = QPushButton("Cerrar"); b_close.setObjectName("okbtn"); b_close.clicked.connect(self.close)
        btns.addWidget(b_close)
        meta.addLayout(btns)

        body.addLayout(meta, 2)
        col.addLayout(body)

        self.setStyleSheet("""
        QDialog { background: transparent; }
        QFrame#outer { background: #1f242b; border:1px solid rgba(255,255,255,0.14); border-radius: 12px; }
        QLabel { background: transparent; }
        """)

    def show_at_cursor(self):
        self.adjustSize()
        geo = self.frameGeometry()
        geo.moveCenter(QCursor.pos())
        self.move(geo.topLeft())
        self.show()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
            e.accept()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and hasattr(self, "_drag_pos"):
            self.move(e.globalPos() - self._drag_pos)
            e.accept()
        super().mouseMoveEvent(e)


# ----- Mini card de usuario para sidebar -----
class MiniUserItem(QFrame):
    def __init__(self, data: dict, on_click, parent=None):
        super().__init__(parent)
        self.data = data
        self.on_click = on_click
        self.setObjectName("MiniUserItem")
        self.setCursor(Qt.PointingHandCursor)

       # 1) Calcular el color primero (mismo criterio que Staff)
        artist_hex = "#9CA3AF"  # gris neutro por defecto
        try:
            # Solo coloreamos si es tatuador (como Staff)
            if data.get("role") == "artist" and data.get("artist_id"):
                aid = int(data["artist_id"])
                ov = load_artist_colors()
                key = str(aid).lower()               # 🔸 clave string como en Staff
                if key in ov and ov[key]:
                    artist_hex = ov[key]
                else:
                    artist_hex = fallback_color_for(aid % 10)
        except Exception:
            # fallback estable
            if data.get("artist_id"):
                artist_hex = fallback_color_for(int(data["artist_id"]) % 10)

        # 2) Estilo base
        self.setStyleSheet("""
        QFrame#MiniUserItem {
            background: #2A2F34;
            border: 1px solid #495057;
            border-radius: 12px;
        }
        QFrame#MiniUserItem:hover { border-color: #7b8190; }
        """)

        # 3) Layout con barra superior de color
        wrap = QVBoxLayout(self); wrap.setContentsMargins(0,0,0,0); wrap.setSpacing(0)
        topbar = QFrame(); topbar.setFixedHeight(3)
        topbar.setStyleSheet(f"background:{artist_hex}; border-top-left-radius:12px; border-top-right-radius:12px;")
        wrap.addWidget(topbar)

        row = QHBoxLayout(); row.setContentsMargins(12,10,12,12); row.setSpacing(12)
        wrap.addLayout(row)

        # 4) Avatar grande
        AV = 44
        avatar = QLabel(); avatar.setFixedSize(AV, AV)
        ap = Path(__file__).resolve().parents[2] / "assets" / "avatars" / f"{int(data['id'])}.png"
        if ap.exists():
            pm = round_pixmap(QPixmap(str(ap)), AV)
        else:
            pm = QPixmap(AV, AV); pm.fill(Qt.transparent)
            p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QColor("#d1d5db")); p.setPen(Qt.NoPen); p.drawEllipse(0, 0, AV, AV)
            p.setPen(QColor("#111"))
            initial = (data["name"] or data.get("username","") or "?")[:1].upper()
            p.drawText(pm.rect(), Qt.AlignCenter, initial); p.end()
        avatar.setPixmap(pm)
        row.addWidget(avatar, 0, Qt.AlignVCenter)

        # 5) Nombre + chips
        col = QVBoxLayout(); col.setSpacing(2); col.setContentsMargins(0,0,0,0)

        name_row = QHBoxLayout(); name_row.setSpacing(8)
        dot = QLabel(); dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"background:{artist_hex}; border-radius:5px;")
        name_row.addWidget(dot, 0, Qt.AlignVCenter)

        name = QLabel(data["name"] or data.get("username","") or "—")
        name.setStyleSheet("font-weight:700; font-size:13px; background:transparent;")
        name_row.addWidget(name, 1)
        col.addLayout(name_row)

        chips = QHBoxLayout(); chips.setSpacing(6)
        role_lab = QLabel(role_to_label(data["role"]))
        role_lab.setStyleSheet(f"background:transparent; color:{artist_hex}; border:1px solid {artist_hex}; padding:2px 8px; border-radius:8px; font-size:11px;")
        state_lab = QLabel("Activo" if data["is_active"] else "Inactivo")
        if data["is_active"]:
            state_lab.setStyleSheet("background:transparent; color:#86EFAC; border:1px solid #395A46; padding:2px 8px; border-radius:8px; font-size:11px;")
        else:
            state_lab.setStyleSheet("background:transparent; color:#ADB5BD; border:1px solid #495057; padding:2px 8px; border-radius:8px; font-size:11px;")
        chips.addWidget(role_lab)
        chips.addWidget(state_lab)
        chips.addStretch(1)
        col.addLayout(chips)

        row.addLayout(col, 1)

        # 6) Contador a la derecha
        cnt = QLabel(f"{int(data['count'] or 0)}")
        cnt.setFixedHeight(22)
        cnt.setAlignment(Qt.AlignCenter)
        cnt.setStyleSheet("color:#ADB5BD; font-size:12px; border:1px solid #495057; border-radius:11px; padding:0 10px; min-width:26px;")
        row.addWidget(cnt, 0, Qt.AlignVCenter)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and callable(self.on_click):
            self.on_click(self.data)
        super().mouseReleaseEvent(e)

    def set_selected(self, selected: bool):
        self.setStyleSheet("""
        QFrame#MiniUserItem {
            background: #2A2F34;
            border: 2px solid %s;
            border-radius: 12px;
        }
        QFrame#MiniUserItem:hover { border-color: #a8b3c5; }
        """ % ("#ADB5BD" if selected else "#495057"))

# ----------------------------------------------------------------------
# Página principal
# ----------------------------------------------------------------------
class PortfoliosPage(QWidget):
    """
    Sidebar de tatuadores (avatar + nombre + conteo)
    + galería con grid fluido de piezas del tatuador seleccionado.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QHBoxLayout(self); root.setContentsMargins(12,12,12,12); root.setSpacing(12)

        # ---- Sidebar ----
        self.side = QFrame(); self.side.setFixedWidth(340)
        side_l = QVBoxLayout(self.side); side_l.setContentsMargins(8,8,8,8); side_l.setSpacing(8)

        self.side_scroll = QScrollArea(); self.side_scroll.setWidgetResizable(True)
        self.side_host = QWidget(); self.side_v = QVBoxLayout(self.side_host); self.side_v.setContentsMargins(0,0,0,0); self.side_v.setSpacing(6)
        self.side_host.setLayout(self.side_v)
        self.side_scroll.setWidget(self.side_host)
        side_l.addWidget(self.side_scroll, 1)

        # ---- Derecha: toolbar + galería ----
        right = QVBoxLayout(); right.setContentsMargins(0,0,0,0); right.setSpacing(8)

        toolbar = QFrame(); toolbar.setObjectName("Toolbar")
        tb = QHBoxLayout(toolbar); tb.setContentsMargins(8,8,8,8); tb.setSpacing(8)
        self.btn_add = QToolButton()
        self.btn_add.setText("+")
        self.btn_add.setToolTip("Agregar imágenes")
        self.btn_add.setFixedSize(36, 36)
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setStyleSheet("""
        QToolButton {
            background: #2A2F34;
            color: #E5E7EB;
            border: 1px solid #495057;
            border-radius: 18px;
            font-weight: 700;
            font-size: 18px;
        }
        QToolButton:hover { border-color: #7b8190; }
        QToolButton:pressed { background: #262b32; }
        """)
        self.btn_add.clicked.connect(self._on_add_images)
        tb.addWidget(self.btn_add)

        # --- Filtros UI (solo UI, sin tocar DB) ---
        self.cbo_style = QComboBox(); self.cbo_style.setMinimumWidth(120)
        self.cbo_body = QComboBox();  self.cbo_body.setMinimumWidth(120)
        self.cbo_color = QComboBox(); self.cbo_color.setMinimumWidth(110)
        self.cbo_fresh = QComboBox(); self.cbo_fresh.setMinimumWidth(130)
        self.cbo_sort  = QComboBox(); self.cbo_sort.setMinimumWidth(130)

        for w in (self.cbo_style, self.cbo_body, self.cbo_color, self.cbo_fresh, self.cbo_sort):
            w.setEditable(False)

        self.cbo_style.addItem("Estilo: Todos", None)
        self.cbo_body.addItem("Zona: Todas", None)
        self.cbo_color.addItem("Color: Todos", None)      # "color" | "bn"
        self.cbo_fresh.addItem("Estado: Todos", None)     # "fresh" | "healed"
        self.cbo_sort.addItems(["Más recientes", "Más antiguos"])

        tb.addSpacing(8)
        tb.addWidget(self.cbo_style)
        tb.addWidget(self.cbo_body)
        tb.addWidget(self.cbo_color)
        tb.addWidget(self.cbo_fresh)
        tb.addWidget(self.cbo_sort)

        btn_clear = QToolButton(); btn_clear.setText("Limpiar")
        btn_clear.setObjectName("GhostSmall")
        btn_clear.clicked.connect(self._clear_filters)
        tb.addWidget(btn_clear)

        tb.addStretch(1)

        # señales
        self.cbo_style.currentIndexChanged.connect(self._apply_filters_and_render)
        self.cbo_body.currentIndexChanged.connect(self._apply_filters_and_render)
        self.cbo_color.currentIndexChanged.connect(self._apply_filters_and_render)
        self.cbo_fresh.currentIndexChanged.connect(self._apply_filters_and_render)
        self.cbo_sort.currentIndexChanged.connect(self._apply_filters_and_render)

        right.addWidget(toolbar)

        self.gallery_wrap = QScrollArea(); self.gallery_wrap.setWidgetResizable(True)
        self.gallery_host = QWidget(); self.gallery_flow = FlowLayout(self.gallery_host, hspacing=12, vspacing=12)
        self.gallery_host.setLayout(self.gallery_flow)
        self.gallery_wrap.setWidget(self.gallery_host)
        right.addWidget(self.gallery_wrap, 1)

        root.addWidget(self.side)
        root.addLayout(right, 1)

        self._users_cache: List[dict] = []
        self._all_items: List[PortfolioItem] = []
        self._selected_user: Optional[dict] = None
        self._load_users()

    # ---------- Sidebar ----------
    def _load_users(self):
        # limpia
        while self.side_v.count():
            it = self.side_v.takeAt(0)
            w = it.widget()
            if w: w.deleteLater()

        self._users_cache = PortfolioService.users_with_counts()
        for u in self._users_cache:
            item = MiniUserItem(u, on_click=self._on_user_clicked, parent=self.side_host)
            self.side_v.addWidget(item)
        self.side_v.addStretch(1)

    def _on_user_clicked(self, u: dict):
        self._selected_user = u
        # marcar selección visual
        for i in range(self.side_v.count()):
            w = self.side_v.itemAt(i).widget()
            if isinstance(w, MiniUserItem):
                w.set_selected(w.data["id"] == u["id"])
        self._load_gallery_for_user(u)

    def _load_gallery_for_user(self, u: dict):
        self._clear_gallery()
        self._all_items = PortfolioService.portfolio_for_user(int(u["id"]), u.get("artist_id"), limit=200, offset=0)
        self._populate_filter_values(self._all_items)
        self._apply_filters_and_render()

    # ---------- Galería ----------
    def _clear_gallery(self):
        while self.gallery_flow.count():
            self.gallery_flow.takeAt(0).widget().deleteLater()

    def _load_gallery(self, artist_id: int):
        self._clear_gallery()
        items = PortfolioService.portfolio_for_artist(artist_id, limit=80, offset=0)
        if not items:
            emp = QLabel("Este tatuador aún no tiene piezas en portafolio.")
            emp.setStyleSheet("color:#99A;")
            self.gallery_flow.addWidget(emp)
            return
        for it in items:
            card = PortfolioCard(it, on_click=self._open_detail, parent=self.gallery_host)
            self.gallery_flow.addWidget(card)

    # ---------- Detalle ----------
    def _open_detail(self, item: PortfolioItem):
        payload = PortfolioService.item_detail(int(item.id)) or {"item": item, "artist": None, "session": None, "client": None, "transaction": None}
        dlg = PortfolioDetailDialog(payload, self)
        dlg.show_at_cursor()

    def _on_add_images(self):
        if not self._selected_user:
            QMessageBox.information(self, "Portafolios", "Primero elige un usuario en la columna izquierda.")
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Seleccionar imágenes", "", "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not files:
            return

        session_id = None
        if self._selected_user.get("role") == "artist" and self._selected_user.get("artist_id"):
            session_id = self._select_session_for_artist(int(self._selected_user["artist_id"]))

        n = PortfolioService.add_items_for_user(self._selected_user, files, session_id=session_id)

        if n > 0:
            QMessageBox.information(self, "Portafolios", f"Se agregaron {n} imagen(es).")
            self._load_gallery_for_user(self._selected_user)
            self._load_users()  # refresca contadores
        else:
            QMessageBox.warning(self, "Portafolios", "No se agregó ninguna imagen.")


    def _select_session_for_artist(self, artist_id: int) -> Optional[int]:
        # diálogo simple con combo
        rows = PortfolioService.recent_sessions_for_artist(artist_id, limit=30)
        if not rows:
            return None
        dlg = QDialog(self); dlg.setWindowTitle("Vincular a sesión (opcional)")
        col = QVBoxLayout(dlg); col.setContentsMargins(12,12,12,12); col.setSpacing(8)
        lab = QLabel("Selecciona una sesión para vincular las imágenes (opcional)."); col.addWidget(lab)
        cbo = QComboBox(dlg); cbo.addItem("— No vincular —", None)
        for sid, label in rows:
            cbo.addItem(label, int(sid))
        col.addWidget(cbo)
        row = QHBoxLayout(); row.addStretch(1)
        b_cancel = QPushButton("Cancelar"); b_cancel.clicked.connect(dlg.reject)
        b_ok = QPushButton("Continuar"); b_ok.clicked.connect(dlg.accept)
        row.addWidget(b_cancel); row.addWidget(b_ok)
        col.addLayout(row)
        if dlg.exec_() == QDialog.Accepted:
            return cbo.currentData()
        return None
    
    def _clear_filters(self):
        # volver a "Todos"
        def _reset(cb: QComboBox): 
            cb.blockSignals(True); cb.setCurrentIndex(0); cb.blockSignals(False)
        for cb in (self.cbo_style, self.cbo_body, self.cbo_color, self.cbo_fresh, self.cbo_sort):
            _reset(cb)
        self._apply_filters_and_render()

    def _populate_filter_values(self, items: List[PortfolioItem]):
        # llena combos con valores presentes
        def uniques(attr):
            vals = []
            for it in items:
                v = getattr(it, attr, None)
                if v: vals.append(v)
            return sorted(set(vals), key=lambda s: str(s).lower())

        # congelar señales para no disparar render 5 veces
        for cb in (self.cbo_style, self.cbo_body, self.cbo_color, self.cbo_fresh):
            cb.blockSignals(True)

        # reset manteniendo "Todos"
        def refill(cb: QComboBox, label_all: str, values: List[str]):
            cur = cb.currentData()
            cb.clear(); cb.addItem(label_all, None)
            for v in values:
                cb.addItem(str(v), v)
            # intentar mantener selección si existe
            if cur is not None:
                idx = cb.findData(cur)
                if idx >= 0: cb.setCurrentIndex(idx)

        refill(self.cbo_style, "Estilo: Todos", uniques("style"))
        refill(self.cbo_body,  "Zona: Todas",  uniques("body_area"))
        refill(self.cbo_color, "Color: Todos", uniques("color_mode"))
        refill(self.cbo_fresh, "Estado: Todos", uniques("fresh_or_healed"))

        for cb in (self.cbo_style, self.cbo_body, self.cbo_color, self.cbo_fresh):
            cb.blockSignals(False)

    def _apply_filters_and_render(self):
        items = list(self._all_items)

        # filtros
        f_style = self.cbo_style.currentData()
        f_body  = self.cbo_body.currentData()
        f_color = self.cbo_color.currentData()
        f_fresh = self.cbo_fresh.currentData()

        def ok(it: PortfolioItem):
            if f_style and getattr(it, "style", None) != f_style: return False
            if f_body  and getattr(it, "body_area", None) != f_body: return False
            if f_color and getattr(it, "color_mode", None) != f_color: return False
            if f_fresh and getattr(it, "fresh_or_healed", None) != f_fresh: return False
            return True

        items = [it for it in items if ok(it)]

        # ordenar
        if self.cbo_sort.currentText() == "Más antiguos":
            items.sort(key=lambda it: (getattr(it, "created_at", None) or 0, it.id or 0))
        else:
            items.sort(key=lambda it: (getattr(it, "created_at", None) or 0, it.id or 0), reverse=True)

        # render
        self._clear_gallery()
        if not items:
            emp = QLabel("Sin resultados con los filtros actuales.")
            emp.setStyleSheet("color:#99A;")
            self.gallery_flow.addWidget(emp)
            return
        for it in items:
            card = PortfolioCard(it, on_click=self._open_detail, parent=self.gallery_host)
            self.gallery_flow.addWidget(card)