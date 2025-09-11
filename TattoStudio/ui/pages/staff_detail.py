# ui/pages/staff_detail.py
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTextEdit, QListWidget, QFrame, QLineEdit, QSpacerItem, QSizePolicy
)

class StaffDetailPage(QWidget):
    """
    Ficha de staff (estilo consistente con 'Staff'):
      - Toolbar superior con ← Volver
      - Header en Card con avatar, nombre, rol, estado, especialidades, disponibilidad
      - Tabs: Perfil | Disponibilidad | Portafolio | Citas | Documentos | Comisiones

    Señales:
      - back_requested: para que MainWindow vuelva a la lista de Staff

    API:
      - load_staff(dict)        -> coloca datos en header y perfil
      - go_to_portfolio()       -> selecciona la pestaña Portafolio
    """
    back_requested = pyqtSignal()

    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # ============== Toolbar superior (mismo estilo que Staff) ==============
        topbar = QFrame()
        topbar.setObjectName("Toolbar")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(12, 8, 12, 8)
        tb.setSpacing(8)

        self.btn_back = QPushButton("← Volver")
        self.btn_back.setObjectName("GhostSmall")
        self.btn_back.clicked.connect(self.back_requested.emit)
        tb.addWidget(self.btn_back)

        tb.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # (Placeholders por si luego agregas acciones)
        self.btn_edit = QPushButton("Editar"); self.btn_edit.setObjectName("GhostSmall"); self.btn_edit.setEnabled(False)
        self.btn_del  = QPushButton("Eliminar"); self.btn_del.setObjectName("GhostSmall"); self.btn_del.setEnabled(False)
        tb.addWidget(self.btn_edit); tb.addWidget(self.btn_del)

        root.addWidget(topbar)

        # ============================== Header Card ==============================
        header = QFrame()
        header.setObjectName("Card")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 14, 14, 14)
        hl.setSpacing(14)

        # Avatar circular grande
        self.avatar = QLabel()
        self.avatar.setFixedSize(96, 96)
        hl.addWidget(self.avatar, alignment=Qt.AlignTop)

        # Columna de datos
        col = QVBoxLayout(); col.setSpacing(6)

        self.lbl_name = QLabel("—")
        self.lbl_name.setStyleSheet("font-weight:700; font-size:16pt; background: transparent;")
        col.addWidget(self.lbl_name)

        # Badges (rol/estado) estilo texto plano para no romper tema
        badges = QHBoxLayout(); badges.setSpacing(10)
        self.lbl_role  = QLabel("—");  self.lbl_role.setStyleSheet("color:#6C757D; background: transparent;")
        self.lbl_state = QLabel("—");  self.lbl_state.setStyleSheet("color:#6C757D; background: transparent;")
        badges.addWidget(self.lbl_role); badges.addWidget(self.lbl_state); badges.addStretch(1)
        col.addLayout(badges)

        # Especialidades
        self.lbl_specs = QLabel("—"); self.lbl_specs.setStyleSheet("color:#6C757D; background: transparent;")
        col.addWidget(self.lbl_specs)

        # Disponibilidad
        self.lbl_disp  = QLabel("—"); self.lbl_disp.setStyleSheet("color:#6C757D; background: transparent;")
        col.addWidget(self.lbl_disp)

        hl.addLayout(col, stretch=1)

        # Acciones rápidas (por ahora placeholders)
        actions = QVBoxLayout(); actions.setSpacing(8)
        self.btn_portfolio = QPushButton("Ver portafolio"); self.btn_portfolio.setObjectName("GhostSmall")
        self.btn_portfolio.clicked.connect(self._go_port_action)
        self.btn_new_appt = QPushButton("Nueva cita"); self.btn_new_appt.setObjectName("GhostSmall"); self.btn_new_appt.setEnabled(False)
        actions.addWidget(self.btn_portfolio); actions.addWidget(self.btn_new_appt); actions.addStretch(1)
        hl.addLayout(actions)

        root.addWidget(header)

        # ============================== Tabs ==============================
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, stretch=1)

        # -- Tabs (placeholders “bonitos”) --
        self.tab_perfil = QWidget(); self._mk_perfil(self.tab_perfil)
        self.tab_disp   = QWidget(); self._mk_text(self.tab_disp, "Disponibilidad semanal (placeholder)")
        self.tab_port   = QWidget(); self._mk_list(self.tab_port, ["Diseño_01.png", "Diseño_02.png", "Diseño_03.png"])
        self.tab_citas  = QWidget(); self._mk_list(self.tab_citas, ["10 Sep 12:00 – Ana López", "09 Sep 17:30 – Carla Gómez"])
        self.tab_docs   = QWidget(); self._mk_text(self.tab_docs, "Documentos (contratos, certificados) — placeholder")
        self.tab_comm   = QWidget(); self._mk_text(self.tab_comm, "Comisiones — placeholder")

        self.tabs.addTab(self.tab_perfil, "Perfil")
        self.tabs.addTab(self.tab_disp,   "Disponibilidad")
        self.tabs.addTab(self.tab_port,   "Portafolio")
        self.tabs.addTab(self.tab_citas,  "Citas")
        self.tabs.addTab(self.tab_docs,   "Documentos")
        self.tabs.addTab(self.tab_comm,   "Comisiones")

        self._staff = None

    # ============================ API pública ============================
    def load_staff(self, staff: dict):
        """Pinta encabezado y campos de la pestaña Perfil."""
        self._staff = staff or {}
        nombre = self._staff.get("nombre", "—")
        rol    = self._staff.get("rol", "—")
        estado = self._staff.get("estado", "—")
        specs  = " · ".join(self._staff.get("especialidades", [])) or "—"
        disp   = self._staff.get("disp", "—")

        self.lbl_name.setText(nombre)
        self.lbl_role.setText(rol)
        self.lbl_state.setText(estado)
        self.lbl_specs.setText(specs)
        self.lbl_disp.setText(disp)

        # avatar con iniciales
        self.avatar.setPixmap(self._make_avatar_pixmap(96, nombre))

        # Tab Perfil (edición básica)
        self._name_edit.setText(nombre)
        self._role_edit.setText(rol)
        self._spec_edit.setText(specs if specs != "—" else "")
        self._disp_edit.setText(disp if disp != "—" else "")
        self._bio_te.setPlainText(self._staff.get("bio", ""))

    def go_to_portfolio(self):
        self.tabs.setCurrentWidget(self.tab_port)

    # ============================ Helpers UI ============================
    def _mk_perfil(self, w: QWidget):
        """
        Perfil dentro de una Card:
        - Campos de solo texto (por ahora) para Nombre, Rol, Especialidades, Disponibilidad
        - Bio en QTextEdit
        """
        outer = QVBoxLayout(w); outer.setSpacing(8)

        card = QFrame(); card.setObjectName("Card")
        lay = QVBoxLayout(card); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(8)

        def row(label_txt, editor: QWidget):
            r = QHBoxLayout()
            lbl = QLabel(label_txt + ":")
            lbl.setStyleSheet("background: transparent;")
            r.addWidget(lbl); r.addWidget(editor, stretch=1)
            lay.addLayout(r)

        self._name_edit = QLineEdit();  self._name_edit.setReadOnly(True)
        self._role_edit = QLineEdit();  self._role_edit.setReadOnly(True)
        self._spec_edit = QLineEdit();  self._spec_edit.setReadOnly(True)
        self._disp_edit = QLineEdit();  self._disp_edit.setReadOnly(True)

        row("Nombre",         self._name_edit)
        row("Rol",            self._role_edit)
        row("Especialidades", self._spec_edit)
        row("Disponibilidad", self._disp_edit)

        self._bio_te = QTextEdit()
        self._bio_te.setPlaceholderText("Bio (placeholder)")
        lay.addWidget(self._bio_te)

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

    def _make_avatar_pixmap(self, size: int, nombre: str) -> QPixmap:
        """Círculo con iniciales (se ve bien en ambos temas)."""
        initials = "".join([p[0].upper() for p in nombre.split()[:2]]) or "?"
        pm = QPixmap(size, size); pm.fill(Qt.transparent)
        p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#d1d5db"))
        p.setPen(Qt.NoPen); p.drawEllipse(0, 0, size, size)
        p.setPen(QColor("#111")); p.drawText(pm.rect(), Qt.AlignCenter, initials)
        p.end()
        return pm

    def _go_port_action(self):
        self.go_to_portfolio()
