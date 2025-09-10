# ui/pages/staff_detail.py
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QTextEdit, QListWidget, QHBoxLayout
)

class StaffDetailPage(QWidget):
    """
    Ficha de staff (cascarón con tabs):
      - Perfil | Disponibilidad | Portafolio | Citas | Documentos | Comisiones
    Métodos:
      - load_staff(dict)        -> actualiza encabezado con el nombre
      - go_to_portfolio()       -> selecciona la pestaña Portafolio
    """
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        self.title = QLabel("Ficha del staff")
        self.title.setObjectName("H1")
        root.addWidget(self.title)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, stretch=1)

        # ----- Tabs (placeholders) -----
        self.tab_perfil = QWidget(); self._mk_perfil(self.tab_perfil)
        self.tab_disp   = QWidget(); self._mk_text(self.tab_disp, "Disponibilidad semanal (placeholder)")
        self.tab_port   = QWidget(); self._mk_list(self.tab_port, ["Diseño_01.png", "Diseño_02.png", "Diseño_03.png"])
        self.tab_citas  = QWidget(); self._mk_list(self.tab_citas, ["10 Sep 12:00 (Ana López)", "09 Sep 17:30 (Carla Gómez)"])
        self.tab_docs   = QWidget(); self._mk_text(self.tab_docs, "Documentos (contratos, certificados) — placeholder")
        self.tab_comm   = QWidget(); self._mk_text(self.tab_comm, "Comisiones — placeholder")

        self.tabs.addTab(self.tab_perfil, "Perfil")
        self.tabs.addTab(self.tab_disp,   "Disponibilidad")
        self.tabs.addTab(self.tab_port,   "Portafolio")
        self.tabs.addTab(self.tab_citas,  "Citas")
        self.tabs.addTab(self.tab_docs,   "Documentos")
        self.tabs.addTab(self.tab_comm,   "Comisiones")

        self._staff = None

    # -------- API pública --------
    def load_staff(self, staff: dict):
        self._staff = staff
        self.title.setText(f"Staff: {staff.get('nombre','')}")
        # Actualiza placeholders en Perfil
        self._name_lbl.setText(staff.get("nombre","—"))
        self._role_lbl.setText(staff.get("rol","—"))
        self._spec_lbl.setText(" · ".join(staff.get("especialidades", [])) or "—")
        self._disp_lbl.setText(staff.get("disp","—"))
        self._bio_te.setPlainText(staff.get("bio",""))

    def go_to_portfolio(self):
        self.tabs.setCurrentWidget(self.tab_port)

    # -------- helpers de UI --------
    def _mk_perfil(self, w: QWidget):
        lay = QVBoxLayout(w); lay.setSpacing(6)
        self._name_lbl = QLabel("—"); self._name_lbl.setStyleSheet("font-weight:700; font-size:16pt;")
        self._role_lbl = QLabel("—"); self._spec_lbl = QLabel("—"); self._disp_lbl = QLabel("—")
        lbls = [("Nombre", self._name_lbl), ("Rol", self._role_lbl),
                ("Especialidades", self._spec_lbl), ("Disponibilidad", self._disp_lbl)]
        for t, v in lbls:
            row = QHBoxLayout(); row.addWidget(QLabel(f"{t}:")); row.addWidget(v); row.addStretch(1); lay.addLayout(row)
        self._bio_te = QTextEdit(); self._bio_te.setPlainText("Bio (placeholder)"); lay.addWidget(self._bio_te)

    def _mk_text(self, w: QWidget, text: str):
        lay = QVBoxLayout(w); te = QTextEdit(); te.setPlainText(text); lay.addWidget(te)

    def _mk_list(self, w: QWidget, items):
        lay = QVBoxLayout(w); lst = QListWidget(); lst.addItems(items); lay.addWidget(lst)
