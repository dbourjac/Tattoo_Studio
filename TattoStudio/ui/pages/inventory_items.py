# ui/pages/inventory_items.py
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QFrame, QSizePolicy, QSpacerItem
)

class InventoryItemsPage(QWidget):
    """
    Lista de ítems (cascarón):
    - Buscar, filtros (Categoría, Estado, Caducidad)
    - Tabla con acciones: Ver (abre ficha), Entrada/Ajuste (placeholders)
    - Paginación simple
    Señales: abrir_item(dict), nuevo_item(), nueva_entrada(dict), nuevo_ajuste(dict)
    """
    abrir_item = None
    nuevo_item = None
    nueva_entrada = None
    nuevo_ajuste = None

    def __init__(self):
        super().__init__()
        self.abrir_item = lambda item: None
        self.nuevo_item = lambda: None
        self.nueva_entrada = lambda item: None
        self.nuevo_ajuste = lambda item: None

        self.page_size = 10
        self.current_page = 1
        self.search_text = ""
        self.f_cat = "Todas"; self.f_state = "Activos"; self.f_exp = "Todos"

        root = QVBoxLayout(self); root.setContentsMargins(24,24,24,24); root.setSpacing(12)

        title = QLabel("Ítems"); title.setObjectName("H1"); root.addWidget(title)

        # Toolbar
        toolbar = QHBoxLayout(); toolbar.setSpacing(8)
        self.btn_new = QPushButton("Nuevo ítem"); self.btn_new.setObjectName("CTA")
        self.btn_new.clicked.connect(lambda: self.nuevo_item())
        toolbar.addWidget(self.btn_new)
        toolbar.addSpacerItem(QSpacerItem(20,10,QSizePolicy.Expanding,QSizePolicy.Minimum))
        root.addLayout(toolbar)

        # Filtros
        filters = QHBoxLayout(); filters.setSpacing(8)
        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar por nombre, SKU o marca…")
        self.search.textChanged.connect(self._on_search)
        filters.addWidget(self.search, stretch=1)

        filters.addWidget(QLabel("Categoría:"))
        self.cbo_cat = QComboBox(); self.cbo_cat.addItems(["Todas","Tintas","Agujas","EPP","Limpieza"])
        self.cbo_cat.currentTextChanged.connect(self._on_filter); filters.addWidget(self.cbo_cat)

        filters.addWidget(QLabel("Estado:"))
        self.cbo_state = QComboBox(); self.cbo_state.addItems(["Activos","Archivados","Todos"])
        self.cbo_state.currentTextChanged.connect(self._on_filter); filters.addWidget(self.cbo_state)

        filters.addWidget(QLabel("Caducidad:"))
        self.cbo_exp = QComboBox(); self.cbo_exp.addItems(["Todos","Con caducidad","Sin caducidad"])
        self.cbo_exp.currentTextChanged.connect(self._on_filter); filters.addWidget(self.cbo_exp)

        root.addLayout(filters)

        # Tabla
        self.tbl = QTableWidget(0, 9)
        self.tbl.setHorizontalHeaderLabels(
            ["SKU","Nombre","Categoría","Unidad","Stock","Mínimo","Caduca","Proveedor","Acciones"]
        )
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        root.addWidget(self.tbl, stretch=1)

        # Paginación simple
        pager = QHBoxLayout(); pager.setSpacing(8)
        self.btn_prev = QPushButton("⟵"); self.btn_next = QPushButton("⟶")
        self.lbl_page = QLabel("Página 1/1")
        self.btn_prev.clicked.connect(self._prev); self.btn_next.clicked.connect(self._next)
        pager.addWidget(self.btn_prev); pager.addWidget(self.btn_next); pager.addWidget(self.lbl_page)
        pager.addSpacerItem(QSpacerItem(20,10,QSizePolicy.Expanding,QSizePolicy.Minimum))
        root.addLayout(pager)

        self._seed_mock()
        self._refresh()

    # ---------- datos mock ----------
    def _seed_mock(self):
        # campos: sku, nombre, cat, unidad, stock, minimo, caduca(bool), proveedor, activo(bool)
        self._all = [
            ("TIN-NE-250", "Tinta Negra 250ml", "Tintas", "ml", 3, 5, True, "Dynamic", True),
            ("AGJ-3RL", "Cartucho 3RL", "Agujas", "pieza", 5, 15, False, "Cheyenne", True),
            ("EPP-GUA-M", "Guantes M", "EPP", "par", 2, 10, False, "Kimberly", True),
            ("LIM-ALC", "Alcohol Isopropílico", "Limpieza", "ml", 900, 500, False, "3M", True),
            ("TIN-RJ-30", "Tinta Roja 30ml", "Tintas", "ml", 10, 6, True, "Eternal", True),
            ("EPP-MASC", "Cubrebocas", "EPP", "pieza", 40, 30, False, "3M", True),
            ("EPP-BATA", "Bata desechable", "EPP", "pieza", 0, 10, False, "MedCare", False),  # Archivado
        ]

    # ---------- lógica UI ----------
    def _apply_filters(self):
        txt = self.search_text.lower().strip()
        def keep(r):
            sku, nombre, cat, _, _, _, caduca, _, activo = r
            if self.f_cat != "Todas" and cat != self.f_cat: return False
            if self.f_state == "Activos" and not activo: return False
            if self.f_state == "Archivados" and activo: return False
            if self.f_exp == "Con caducidad" and not caduca: return False
            if self.f_exp == "Sin caducidad" and caduca: return False
            if txt and txt not in (sku + " " + nombre + " " + cat).lower(): return False
            return True
        rows = [r for r in self._all if keep(r)]
        # ordenar por nombre
        rows.sort(key=lambda x: x[1].lower())
        return rows

    def _refresh(self):
        rows = self._apply_filters()
        total = max(1, (len(rows)+self.page_size-1)//self.page_size)
        self.current_page = min(self.current_page, total)
        start = (self.current_page-1)*self.page_size
        page = rows[start:start+self.page_size]

        self.tbl.setRowCount(0)
        for r in page:
            row = self.tbl.rowCount(); self.tbl.insertRow(row)
            for col, val in enumerate(r[:8]):
                if col == 6:  # caduca bool → Sí/No
                    val = "Sí" if val else "No"
                self.tbl.setItem(row, col, QTableWidgetItem(str(val)))
            # Acciones: Ver | Entrada | Ajuste
            w = QWidget(); box = QHBoxLayout(w); box.setContentsMargins(0,0,0,0); box.setSpacing(6)
            b_ver = QPushButton("Ver"); b_ent = QPushButton("Entrada"); b_adj = QPushButton("Ajuste")
            sku = r[0]
            item_dict = {
                "sku": r[0], "nombre": r[1], "categoria": r[2], "unidad": r[3],
                "stock": r[4], "minimo": r[5], "caduca": r[6], "proveedor": r[7], "activo": r[8]
            }
            b_ver.clicked.connect(lambda _, it=item_dict: self.abrir_item(it))
            b_ent.clicked.connect(lambda _, it=item_dict: self.nueva_entrada(it))
            b_adj.clicked.connect(lambda _, it=item_dict: self.nuevo_ajuste(it))
            for b in (b_ver, b_ent, b_adj):
                b.setMinimumHeight(26); box.addWidget(b)
            self.tbl.setCellWidget(row, 8, w)

        self.lbl_page.setText(f"Página {self.current_page}/{total}")
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < total)

    # ---------- eventos ----------
    def _on_search(self, t): self.search_text = t; self.current_page = 1; self._refresh()
    def _on_filter(self, _): 
        self.f_cat = self.cbo_cat.currentText()
        self.f_state = self.cbo_state.currentText()
        self.f_exp = self.cbo_exp.currentText()
        self.current_page = 1; self._refresh()
    def _prev(self): 
        if self.current_page > 1: self.current_page -= 1; self._refresh()
    def _next(self): self.current_page += 1; self._refresh()
