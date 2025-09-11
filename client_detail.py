from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTextEdit, QListWidget, QListWidgetItem, QFrame, QGridLayout
)

class ClientDetailPage(QWidget):
    """
    Ficha de cliente (look & feel unificado con StaffDetail):
      - Toolbar superior: ← Volver a clientes
      - Header card: avatar, nombre, badges (estado/etiqueta), contacto
      - Tabs: Perfil | Citas | Archivos/Fotos | Formularios | Notas

    Señales:
      - back_to_list()  -> para regresar a la tabla de clientes
    """
    back_to_list = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setStyleSheet("QLabel { background: transparent; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # ===== Toolbar (volver) =====
        bar = QHBoxLayout(); bar.setSpacing(8)
        self.btn_back = QPushButton("← Volver a clientes")
        self.btn_back.setObjectName("GhostSmall")
        self.btn_back.setMinimumHeight(32)
        self.btn_back.clicked.connect(self.back_to_list.emit)
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

        # Nombre (H1 pequeño)
        self.name_lbl = QLabel("Cliente")
        self.name_lbl.setStyleSheet("font-weight:700; font-size:16pt;")
        info.addWidget(self.name_lbl)

        # Badges (etiqueta + estado)
        badges = QHBoxLayout(); badges.setSpacing(6)
        self.badge_tag = QLabel(" — ")
        self.badge_tag.setObjectName("BadgeRole")      # mismo estilo que en Staff
        self.badge_state = QLabel(" — ")
        self.badge_state.setObjectName("BadgeState")
        badges.addWidget(self.badge_tag)
        badges.addWidget(self.badge_state)
        badges.addStretch(1)
        info.addLayout(badges)

        # Grid de contacto / meta
        grid = QGridLayout(); grid.setHorizontalSpacing(16); grid.setVerticalSpacing(4)

        self.phone_lbl = QLabel("—")
        self.email_lbl = QLabel("—")
        self.ig_lbl    = QLabel("")     # opcional si viene en el dict como "ig"

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

        # ===== Tabs (dentro de card) =====
        tabs_card = QFrame()
        tabs_card.setObjectName("Card")
        tl = QVBoxLayout(tabs_card)
        tl.setContentsMargins(12, 12, 12, 12)
        tl.setSpacing(8)

        self.tabs = QTabWidget()
        tl.addWidget(self.tabs)

        # Pestañas
        self.tab_perfil = QWidget(); self._mk_perfil(self.tab_perfil)
        self.tab_citas  = QWidget(); self._mk_list(self.tab_citas, [])
        self.tab_files  = QWidget(); self._mk_placeholder(self.tab_files, "Galería/Archivos (placeholder)")
        self.tab_forms  = QWidget(); self._mk_placeholder(self.tab_forms, "Formularios asignados/firmados (placeholder)")
        self.tab_notas  = QWidget(); self._mk_text(self.tab_notas, "Notas internas (placeholder)")

        self.tabs.addTab(self.tab_perfil, "Perfil")
        self.tabs.addTab(self.tab_citas,  "Citas")
        self.tabs.addTab(self.tab_files,  "Archivos/Fotos")
        self.tabs.addTab(self.tab_forms,  "Formularios")
        self.tabs.addTab(self.tab_notas,  "Notas")

        root.addWidget(tabs_card, 1)

        # Estado actual
        self._client = None

    # ===== API =====
    def load_client(self, client: dict):
        """
        Recibe el dict emitido desde ClientsPage y pinta:
        - name_lbl, badges (etiquetas/estado)
        - teléfono/email/instagram si vienen
        - artista asignado y próxima cita
        Además, refresca lista de citas de demo si quisieras.
        """
        self._client = client or {}

        name = client.get("nombre", "—")
        self.name_lbl.setText(name)
        self.avatar.setPixmap(self._make_avatar_pixmap(72, name))

        # Badges
        tag = client.get("etiquetas", "") or "—"
        self.badge_tag.setText(f" {tag} ")
        state = client.get("estado", "") or "—"
        self.badge_state.setText(f" {state} ")

        # Contacto
        self.phone_lbl.setText(client.get("tel", "—"))
        self.email_lbl.setText(client.get("email", "—"))
        ig = client.get("ig") or client.get("instagram") or ""
        self.ig_lbl.setText(ig if ig else "—")

        # Meta
        self.artist_lbl.setText(client.get("artista", "—"))
        self.next_lbl.setText(client.get("proxima", "—"))

        # Citas (placeholder: puedes sobrescribir desde fuera si ya tienes la lista)
        self._set_citas_list([
            f'{client.get("proxima","—")} · {client.get("artista","—")}'
        ])

        # Perfil (columna “resumen” básica)
        self._perfil_name.setText(name)
        self._perfil_contact.setText(f'{client.get("tel","—")}  ·  {client.get("email","—")}')
        self._perfil_notes.setPlainText("Notas del perfil (placeholder)")

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

    def _make_avatar_pixmap(self, size: int, nombre: str) -> QPixmap:
        """Avatar circular con iniciales (placeholder), mismo estilo que Staff."""
        initials = "·"
        if nombre:
            parts = [p for p in nombre.split() if p]
            initials = "".join([p[0].upper() for p in parts[:2]]) or "·"

        pm = QPixmap(size, size); pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#d1d5db"))  # gris claro, contrasta bien en ambos temas
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, size, size)
        p.setPen(QColor("#111"))
        p.drawText(pm.rect(), Qt.AlignCenter, initials)
        p.end()
        return pm
