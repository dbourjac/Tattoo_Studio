# ui/pages/inventory_item_detail.py
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTabWidget, QTableWidget, QTableWidgetItem, QFormLayout, QSizePolicy
)

class InventoryItemDetailPage(QWidget):
    """
    Ficha de ítem con estilo consistente:
      - Header tipo 'card' con avatar, nombre, sku y KPIs (stock/mínimo)
      - Botón ← Volver
      - Tabs: Resumen (solo lectura), Movimientos, Proveedores
    API:
      - load_item(dict) -> pinta los datos en header y resumen
    Señales:
      - volver -> para regresar a la lista de ítems
    """
    volver = pyqtSignal()

    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # -------- barra superior --------
        top = QHBoxLayout(); top.setSpacing(8)
        self.btn_back = QPushButton("← Volver a ítems")
        self.btn_back.setObjectName("GhostSmall")
        self.btn_back.setMinimumHeight(32)
        self.btn_back.clicked.connect(self.volver.emit)
        top.addWidget(self.btn_back)
        top.addStretch(1)
        root.addLayout(top)

        # -------- header / card --------
        self.header = QFrame(); self.header.setObjectName("Card")
        h = QHBoxLayout(self.header); h.setContentsMargins(14, 12, 14, 12); h.setSpacing(12)

        # avatar circular con iniciales del ítem
        self.avatar = QLabel(); self.avatar.setFixedSize(56, 56)
        h.addWidget(self.avatar, 0, Qt.AlignTop)

        # columna de info
        info = QVBoxLayout(); info.setSpacing(2)

        self.lbl_name = QLabel("—")
        self.lbl_name.setStyleSheet("font-weight:700; font-size:14pt;")
        info.addWidget(self.lbl_name)

        self.lbl_sku = QLabel("SKU: —")
        self.lbl_sku.setStyleSheet("color:#6C757D;")
        info.addWidget(self.lbl_sku)

        # fila de “badges” ligeros (solo texto, sin fondo sólido)
        badges = QHBoxLayout(); badges.setSpacing(8)
        self.badge_cat   = QLabel("")   # Categoría
        self.badge_unit  = QLabel("")   # Unidad
        self.badge_exp   = QLabel("")   # Caduca Sí/No
        for b in (self.badge_cat, self.badge_unit, self.badge_exp):
            b.setStyleSheet("padding:2px 6px; border:1px solid rgba(0,0,0,0.15); border-radius:8px;")
            badges.addWidget(b)
        badges.addStretch(1)
        info.addLayout(badges)

        h.addLayout(info, 1)

        # KPIs a la derecha
        kpis = QVBoxLayout(); kpis.setSpacing(0)
        self.kpi_stock = QLabel("0")
        self.kpi_stock.setStyleSheet("font-weight:800; font-size:18pt;")
        self.kpi_hint  = QLabel("Stock actual"); self.kpi_hint.setStyleSheet("color:#6C757D;")
        self.kpi_min   = QLabel("Mínimo: —");    self.kpi_min.setStyleSheet("color:#6C757D;")
        kpis.addWidget(self.kpi_stock, 0, Qt.AlignRight)
        kpis.addWidget(self.kpi_hint,  0, Qt.AlignRight)
        kpis.addWidget(self.kpi_min,   0, Qt.AlignRight)
        h.addLayout(kpis, 0)

        root.addWidget(self.header)

        # -------- tabs --------
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, stretch=1)

        # --- Resumen (solo lectura con QLabel, sin fondos) ---
        self.tab_res = QWidget(); self.tabs.addTab(self.tab_res, "Resumen")
        fr = QFormLayout(self.tab_res)
        fr.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.v_sku   = QLabel("—")
        self.v_name  = QLabel("—")
        self.v_cat   = QLabel("—")
        self.v_unit  = QLabel("—")
        self.v_stock = QLabel("—")
        self.v_min   = QLabel("—")
        self.v_exp   = QLabel("—")
        self.v_prov  = QLabel("—")
        for w in (self.v_sku, self.v_name, self.v_cat, self.v_unit,
                  self.v_stock, self.v_min, self.v_exp, self.v_prov):
            w.setTextInteractionFlags(Qt.TextSelectableByMouse)

        fr.addRow("SKU:",           self.v_sku)
        fr.addRow("Nombre:",        self.v_name)
        fr.addRow("Categoría:",     self.v_cat)
        fr.addRow("Unidad:",        self.v_unit)
        fr.addRow("Stock actual:",  self.v_stock)
        fr.addRow("Mínimo:",        self.v_min)
        fr.addRow("Con caducidad:", self.v_exp)
        fr.addRow("Proveedor:",     self.v_prov)

        # --- Movimientos ---
        self.tab_mov = QWidget(); self.tabs.addTab(self.tab_mov, "Movimientos")
        mv = QVBoxLayout(self.tab_mov); mv.setContentsMargins(0, 0, 0, 0); mv.setSpacing(8)

        # acciones (fantasma) arriba de la tabla
        bar = QHBoxLayout(); bar.setSpacing(8)
        self.btn_new_in  = QPushButton("Nueva entrada"); self.btn_new_in.setObjectName("GhostSmall")
        self.btn_new_adj = QPushButton("Ajuste de stock"); self.btn_new_adj.setObjectName("GhostSmall")
        bar.addStretch(1); bar.addWidget(self.btn_new_in); bar.addWidget(self.btn_new_adj)
        mv.addLayout(bar)

        self.tbl_mov = QTableWidget(0, 5)
        self.tbl_mov.setHorizontalHeaderLabels(["Fecha", "Tipo", "Cantidad", "Motivo", "Usuario"])
        self.tbl_mov.horizontalHeader().setStretchLastSection(True)
        self.tbl_mov.setAlternatingRowColors(True)
        mv.addWidget(self.tbl_mov)

        # --- Proveedores ---
        self.tab_prov = QWidget(); self.tabs.addTab(self.tab_prov, "Proveedores")
        pv = QVBoxLayout(self.tab_prov); pv.setContentsMargins(0, 0, 0, 0); pv.setSpacing(8)

        self.tbl_prov = QTableWidget(0, 3)
        self.tbl_prov.setHorizontalHeaderLabels(["Proveedor", "Código", "Precio ref."])
        self.tbl_prov.horizontalHeader().setStretchLastSection(True)
        self.tbl_prov.setAlternatingRowColors(True)
        pv.addWidget(self.tbl_prov)

        self._mock_seeded = False

    # -------- API pública --------
    def load_item(self, it: dict):
        """
        it: dict con campos:
          sku, nombre, categoria, unidad, stock, minimo, caduca(bool), proveedor, activo(bool?)
        """
        name  = it.get("nombre", "—")
        sku   = it.get("sku", "—")
        cat   = it.get("categoria", "—")
        unit  = it.get("unidad", "—")
        stock = it.get("stock", 0)
        minimo= it.get("minimo", 0)
        cad   = bool(it.get("caduca", False))
        prov  = it.get("proveedor", "—")

        # Header
        self.lbl_name.setText(name)
        self.lbl_sku.setText(f"SKU: {sku}")
        self.badge_cat.setText(cat or "—")
        self.badge_unit.setText(unit or "—")
        self.badge_exp.setText("Caduca: Sí" if cad else "Caduca: No")

        self.kpi_stock.setText(str(stock))
        self.kpi_min.setText(f"Mínimo: {minimo}")

        # Si bajo stock, resaltamos el número (sin romper temas)
        if minimo and stock < minimo:
            self.kpi_stock.setStyleSheet("font-weight:800; font-size:18pt; color:#c0392b;")
        else:
            self.kpi_stock.setStyleSheet("font-weight:800; font-size:18pt;")

        # Avatar con iniciales (del nombre o SKU)
        initials_src = (name or sku).strip()
        self.avatar.setPixmap(self._make_circle_avatar(56, self._initials(initials_src)))

        # Resumen (solo lectura)
        self.v_sku.setText(sku)
        self.v_name.setText(name)
        self.v_cat.setText(cat)
        self.v_unit.setText(unit)
        self.v_stock.setText(str(stock))
        self.v_min.setText(str(minimo))
        self.v_exp.setText("Sí" if cad else "No")
        self.v_prov.setText(prov)

        # Datos mock en tablas (solo 1 vez)
        if not self._mock_seeded:
            self._seed_tables()
            self._mock_seeded = True

    # -------- utilidades internas --------
    def _seed_tables(self):
        # Movimientos de demo
        data = [
            ("03/09/2025", "Entrada", "+500", "OC-145", "Sofía"),
            ("05/09/2025", "Salida",  "-30",  "Consumo citas", "Karla"),
            ("06/09/2025", "Ajuste",  "+10",  "Conteo", "Dylan"),
        ]
        for r in data:
            row = self.tbl_mov.rowCount(); self.tbl_mov.insertRow(row)
            for c, v in enumerate(r):
                self.tbl_mov.setItem(row, c, QTableWidgetItem(v))

        # Proveedores de demo
        prov = [("Dynamic", "DN-250", "$320"), ("Proveedor X", "PX-01", "$340")]
        for r in prov:
            row = self.tbl_prov.rowCount(); self.tbl_prov.insertRow(row)
            for c, v in enumerate(r):
                self.tbl_prov.setItem(row, c, QTableWidgetItem(v))

    def _initials(self, text: str) -> str:
        parts = [p for p in text.split() if p]
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return (text[:2] or "IT").upper()

    def _make_circle_avatar(self, size: int, initials: str) -> QPixmap:
        """Avatar circular gris con iniciales (consistente con otras páginas)."""
        pm = QPixmap(size, size); pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#d1d5db"))     # gris claro que funciona en ambos temas
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, size, size)
        p.setPen(QColor("#111111"))
        p.drawText(pm.rect(), Qt.AlignCenter, initials)
        p.end()
        return pm
