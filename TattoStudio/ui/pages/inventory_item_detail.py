# ui/pages/inventory_item_detail.py
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QPushButton, QFormLayout, QLineEdit, QCheckBox
)

class InventoryItemDetailPage(QWidget):
    """
    Ficha del ítem (cascarón con tabs):
    - Resumen (solo lectura ahora)
    - Movimientos (tabla mock)
    - Proveedores (lista simple)
    API:
      - load_item(dict)  -> llena encabezado/campos
    """
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self); root.setContentsMargins(24,24,24,24); root.setSpacing(12)

        self.title = QLabel("Ítem"); self.title.setObjectName("H1")
        root.addWidget(self.title)

        self.tabs = QTabWidget(); root.addWidget(self.tabs, stretch=1)

        # --- Resumen ---
        self.tab_res = QWidget(); self.tabs.addTab(self.tab_res, "Resumen")
        fr = QFormLayout(self.tab_res); fr.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.tx_sku   = QLineEdit(); self.tx_sku.setReadOnly(True)
        self.tx_name  = QLineEdit(); self.tx_name.setReadOnly(True)
        self.tx_cat   = QLineEdit(); self.tx_cat.setReadOnly(True)
        self.tx_unit  = QLineEdit(); self.tx_unit.setReadOnly(True)
        self.tx_stock = QLineEdit(); self.tx_stock.setReadOnly(True)
        self.tx_min   = QLineEdit(); self.tx_min.setReadOnly(True)
        self.chk_exp  = QCheckBox(); self.chk_exp.setDisabled(True)
        self.tx_prov  = QLineEdit(); self.tx_prov.setReadOnly(True)

        fr.addRow("SKU:", self.tx_sku)
        fr.addRow("Nombre:", self.tx_name)
        fr.addRow("Categoría:", self.tx_cat)
        fr.addRow("Unidad:", self.tx_unit)
        fr.addRow("Stock actual:", self.tx_stock)
        fr.addRow("Mínimo:", self.tx_min)
        fr.addRow("Con caducidad:", self.chk_exp)
        fr.addRow("Proveedor:", self.tx_prov)

        # --- Movimientos ---
        self.tab_mov = QWidget(); self.tabs.addTab(self.tab_mov, "Movimientos")
        self.tbl_mov = QTableWidget(0, 5)
        self.tbl_mov.setHorizontalHeaderLabels(["Fecha","Tipo","Cantidad","Motivo","Usuario"])
        lay_mov = QVBoxLayout(self.tab_mov); lay_mov.addWidget(self.tbl_mov)

        # --- Proveedores ---
        self.tab_prov = QWidget(); self.tabs.addTab(self.tab_prov, "Proveedores")
        self.tbl_prov = QTableWidget(0, 3)
        self.tbl_prov.setHorizontalHeaderLabels(["Proveedor","Código","Precio ref."])
        lay_p = QVBoxLayout(self.tab_prov); lay_p.addWidget(self.tbl_prov)

        self._mock_loaded = False

    # ---------- API ----------
    def load_item(self, it: dict):
        self.title.setText(f"Ítem: {it.get('nombre','')}")
        self.tx_sku.setText(it.get("sku",""))
        self.tx_name.setText(it.get("nombre",""))
        self.tx_cat.setText(it.get("categoria",""))
        self.tx_unit.setText(it.get("unidad",""))
        self.tx_stock.setText(str(it.get("stock","")))
        self.tx_min.setText(str(it.get("minimo","")))
        self.chk_exp.setChecked(bool(it.get("caduca", False)))
        self.tx_prov.setText(it.get("proveedor",""))

        # cargar tablas mock una sola vez (demostración)
        if not self._mock_loaded:
            self._seed_tables()
            self._mock_loaded = True

    # ---------- mock interno ----------
    def _seed_tables(self):
        # Movimientos de demo
        data = [
            ("03/09/2025", "Entrada", "+500", "OC-145", "Sofía"),
            ("05/09/2025", "Salida",  "-30", "Consumo citas", "Karla"),
            ("06/09/2025", "Ajuste",  "+10", "Conteo", "Dylan"),
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
