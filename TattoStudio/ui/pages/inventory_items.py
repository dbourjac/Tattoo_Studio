from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QFrame, QSizePolicy, QSpacerItem, QMessageBox
)
from sqlalchemy.orm import Session

from data.db.session import SessionLocal
from data.models.product import Product
from typing import List

class InventoryItemsPage(QWidget):
    """
    Lista de ítems (mock):
    - CTA "Nuevo ítem"
    - Toolbar (pastilla) con Buscar + Filtros (Categoría, Estado, Caducidad)
    - Tabla con acciones: Ver | Entrada | Ajuste
    - Paginación simple
    Señales: abrir_item(dict), nuevo_item(), nueva_entrada(dict), nuevo_ajuste(dict)
    """
    abrir_item = None
    nuevo_item = None
    nueva_entrada = None
    nuevo_ajuste = None

    def __init__(self):
        super().__init__()
        # Callbacks que MainWindow reemplaza
        self.abrir_item = lambda item: None
        self.nuevo_item = lambda: None
        self.nueva_entrada = lambda: None
        self.nuevo_ajuste = lambda item: None

        # Estado de filtros/paginación
        self.page_size = 20
        self.current_page = 1
        self.search_text = ""
        self.f_cat = "Todas"; self.f_state = "Activos"; self.f_exp = "Todos"

        # Fondo transparente para labels/headers
        self.setStyleSheet(
            "QLabel { background: transparent; }"
            "QHeaderView::section { background: transparent; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # ===== Título =====
        title = QLabel("Ítems")
        title.setObjectName("H1")
        root.addWidget(title)

        # ===== Fila CTA =====
        row_cta = QHBoxLayout(); row_cta.setSpacing(8)
        self.btn_new = QPushButton("Nuevo ítem"); self.btn_new.setObjectName("CTA")
        self.btn_new.setMinimumHeight(34)
        self.btn_new.clicked.connect(lambda: self.nuevo_item())
        row_cta.addWidget(self.btn_new)
        row_cta.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        root.addLayout(row_cta)

        # ===== Toolbar (pastilla) Buscar + Filtros =====
        tb_frame = QFrame(); tb_frame.setObjectName("Toolbar")
        tb = QHBoxLayout(tb_frame); tb.setContentsMargins(10, 8, 10, 8); tb.setSpacing(8)

        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar por nombre, SKU o marca…")
        self.search.textChanged.connect(self._on_search)
        tb.addWidget(self.search, stretch=1)

        tb.addWidget(QLabel("Categoría:"))
        self.cbo_cat = QComboBox(); self.cbo_cat.addItems(["Todas", "Tintas", "Agujas", "EPP", "Limpieza", "Aftercare", "Consumibles"])
        self.cbo_cat.currentTextChanged.connect(self._on_filter); tb.addWidget(self.cbo_cat)

        tb.addWidget(QLabel("Estado:"))
        self.cbo_state = QComboBox(); self.cbo_state.addItems(["Activos", "Archivados", "Todos"])
        self.cbo_state.currentTextChanged.connect(self._on_filter); tb.addWidget(self.cbo_state)

        tb.addWidget(QLabel("Caducidad:"))
        self.cbo_exp = QComboBox(); self.cbo_exp.addItems(["Todos", "Con caducidad", "Sin caducidad"])
        self.cbo_exp.currentTextChanged.connect(self._on_filter); tb.addWidget(self.cbo_exp)

        root.addWidget(tb_frame)

        # ===== Tabla =====
        self.tbl = QTableWidget(0, 9)
        self.tbl.setHorizontalHeaderLabels(
            ["SKU", "Nombre", "Categoría", "Unidad", "Stock", "Mínimo", "Caduca", "Proveedor", "Acciones"]
        )
        self.tbl.horizontalHeader().setStretchLastSection(True)
        # Tamaños/legibilidad
        self.tbl.verticalHeader().setDefaultSectionSize(30)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionMode(self.tbl.NoSelection)
        # Ajustes de columnas
        self.tbl.horizontalHeader().setDefaultSectionSize(140)
        self.tbl.horizontalHeader().setMinimumSectionSize(80)
        self.tbl.horizontalHeader().resizeSection(0, 120)  # SKU
        self.tbl.horizontalHeader().resizeSection(1, 280)  # Nombre (un poco más ancho)
        self.tbl.horizontalHeader().resizeSection(4, 80)   # Stock
        self.tbl.horizontalHeader().resizeSection(5, 80)   # Mínimo
        self.tbl.horizontalHeader().resizeSection(6, 90)   # Caduca
        self.tbl.horizontalHeader().resizeSection(8, 220)  # Acciones
        root.addWidget(self.tbl, stretch=1)

        # ===== Paginación =====
        pager = QHBoxLayout(); pager.setSpacing(8)
        self.btn_prev = QPushButton("⟵"); self.btn_next = QPushButton("⟶")
        self.lbl_page = QLabel("Página 1/1")
        for b in (self.btn_prev, self.btn_next):
            b.setObjectName("GhostSmall"); b.setMinimumHeight(28)
        self.btn_prev.clicked.connect(self._prev); self.btn_next.clicked.connect(self._next)
        pager.addWidget(self.btn_prev); pager.addWidget(self.btn_next); pager.addWidget(self.lbl_page)
        pager.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        root.addLayout(pager)

        # Datos mock + render
        self._seed_mock()
        self._refresh()

    # ---------- datos mock ----------
    def _seed_mock(self):
        # (sku, nombre, cat, unidad, stock, minimo, caduca(bool), proveedor, activo(bool))
        self._all = []
        try:
            with SessionLocal() as db:
                products: List[Product] = (
                    db.query(Product)
                    .all()
                )
                for p in products:
                    self._all.append((
                        p.sku,
                        p.name,
                        p.category ,
                        p.unidad,
                        p.stock,
                        p.min_stock,
                        p.caduca,
                        p.proveedor,
                        p.activo
                    ))
        except Exception as ex:
            QMessageBox.critical(self, "BD", f"Error al cargar productos: {ex}")
            self._all = []


    # ---------- lógica UI ----------
    def _apply_filters(self):
        txt = self.search_text.lower().strip()

        def keep(r):
            sku, nombre, cat, _, _, _, caduca, _,activo= r
            if self.f_cat != "Todas" and cat != self.f_cat: return False
            if self.f_state == "Activos" and not activo: return False
            if self.f_state == "Archivados" and activo: return False
            if self.f_exp == "Con caducidad" and not caduca: return False
            if self.f_exp == "Sin caducidad" and caduca: return False
            if txt and txt not in (sku + " " + nombre + " " + cat).lower(): return False
            return True

        rows = [r for r in self._all if keep(r)]
        rows.sort(key=lambda x: x[1].lower())  # por nombre
        return rows

    def _refresh(self):
        rows = self._apply_filters()
        total = max(1, (len(rows) + self.page_size - 1) // self.page_size)
        self.current_page = min(self.current_page, total)
        start = (self.current_page - 1) * self.page_size
        page = rows[start:start + self.page_size]

        self.tbl.setRowCount(0)
        for r in page:
            row = self.tbl.rowCount(); self.tbl.insertRow(row)
            for col, val in enumerate(r[:8]):
                if col == 6:  # caduca bool → Sí/No
                    val = "Sí" if val else "No"
                item = QTableWidgetItem(str(val))
                # Alineaciones útiles
                if col in (4, 5):  # Stock / Mínimo
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tbl.setItem(row, col, item)

            # Señal de bajo stock: Stock < Mínimo → rojo
            stock_item = self.tbl.item(row, 4)
            min_item   = self.tbl.item(row, 5)
            try:
                stk = int(stock_item.text()); mn = int(min_item.text())
                if stk < mn:
                    stock_item.setForeground(QBrush(QColor("#b91c1c")))  # rojo oscuro
            except Exception:
                pass

            # Acciones
            w = QWidget(); box = QHBoxLayout(w); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(6)
            b_ver = QPushButton("Ver"); b_ent = QPushButton("Entrada"); b_adj = QPushButton("Ajuste")
            for b in (b_ver, b_ent, b_adj):
                b.setObjectName("GhostSmall"); b.setMinimumHeight(26)
                box.addWidget(b)

            item_dict = {
                "sku": r[0], "nombre": r[1], "categoria": r[2], "unidad": r[3],
                "stock": r[4], "minimo": r[5], "caduca": r[6], "proveedor": r[7], "activo": r[8]
            }
            b_ver.clicked.connect(lambda _, it=item_dict: self.abrir_item(it))
            b_ent.clicked.connect(lambda _, it=item_dict: self.nueva_entrada(it))
            b_adj.clicked.connect(lambda _, it=item_dict: self.nuevo_ajuste(it))

            self.tbl.setCellWidget(row, 8, w)

        self.lbl_page.setText(f"Página {self.current_page}/{total}")
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < total)

    # ---------- eventos ----------
    def _on_search(self, t):
        self.search_text = t
        self.current_page = 1
        self._refresh()

    def _on_filter(self, _):
        self.f_cat = self.cbo_cat.currentText()
        self.f_state = self.cbo_state.currentText()
        self.f_exp = self.cbo_exp.currentText()
        self.current_page = 1
        self._refresh()

    def _prev(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._refresh()

    def _next(self):
        self.current_page += 1
        self._refresh()