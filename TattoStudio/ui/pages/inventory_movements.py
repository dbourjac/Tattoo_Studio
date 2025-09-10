# ui/pages/inventory_movements.py
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDateEdit, QTableWidget, QTableWidgetItem, QSizePolicy, QSpacerItem
)

class InventoryMovementsPage(QWidget):
    """
    Movimientos (cascarón):
    - Filtros: tipo, fechas
    - Botones: Nueva entrada / Salida / Ajuste (placeholders)
    - Tabla mock
    """
    nueva_entrada = None
    nueva_salida = None
    nuevo_ajuste = None

    def __init__(self):
        super().__init__()
        self.nueva_entrada = lambda: None
        self.nueva_salida = lambda: None
        self.nuevo_ajuste = lambda: None

        root = QVBoxLayout(self); root.setContentsMargins(24,24,24,24); root.setSpacing(12)

        title = QLabel("Movimientos"); title.setObjectName("H1"); root.addWidget(title)

        # Toolbar
        tb = QHBoxLayout(); tb.setSpacing(8)
        b_in  = QPushButton("Nueva entrada"); b_out = QPushButton("Nueva salida"); b_adj = QPushButton("Ajuste")
        b_in.clicked.connect(lambda: self.nueva_entrada())
        b_out.clicked.connect(lambda: self.nueva_salida())
        b_adj.clicked.connect(lambda: self.nuevo_ajuste())
        tb.addWidget(b_in); tb.addWidget(b_out); tb.addWidget(b_adj)
        tb.addSpacerItem(QSpacerItem(20,10,QSizePolicy.Expanding,QSizePolicy.Minimum))
        root.addLayout(tb)

        # Filtros
        filters = QHBoxLayout(); filters.setSpacing(8)
        filters.addWidget(QLabel("Tipo:"))
        self.cbo_tipo = QComboBox(); self.cbo_tipo.addItems(["Todos","Entrada","Salida","Ajuste"])
        filters.addWidget(self.cbo_tipo)
        filters.addSpacing(12)
        filters.addWidget(QLabel("De:"))
        self.dt_from = QDateEdit(QDate.currentDate().addDays(-14)); self.dt_from.setCalendarPopup(True)
        filters.addWidget(self.dt_from)
        filters.addWidget(QLabel("a:"))
        self.dt_to   = QDateEdit(QDate.currentDate()); self.dt_to.setCalendarPopup(True)
        filters.addWidget(self.dt_to)
        filters.addSpacerItem(QSpacerItem(20,10,QSizePolicy.Expanding,QSizePolicy.Minimum))
        root.addLayout(filters)

        # Tabla
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["Fecha","Tipo","SKU","Nombre","Cantidad","Usuario"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.tbl, stretch=1)

        self._seed_mock()
        self._refresh()

        # eventos de filtros → refrescar
        self.cbo_tipo.currentTextChanged.connect(lambda _: self._refresh())
        self.dt_from.dateChanged.connect(lambda _: self._refresh())
        self.dt_to.dateChanged.connect(lambda _: self._refresh())

    def _seed_mock(self):
        d = QDate.currentDate()
        self._rows = [
            (d, "Entrada", "TIN-NE-250", "Tinta Negra 250ml", +500, "Sofía"),
            (d.addDays(-1), "Salida", "EPP-GUA-M", "Guantes M", -5, "Karla"),
            (d.addDays(-2), "Ajuste", "AGJ-3RL", "Cartucho 3RL", +10, "Dylan"),
            (d.addDays(-5), "Salida", "TIN-RJ-30", "Tinta Roja 30ml", -20, "Alex"),
        ]

    def _refresh(self):
        tipo = self.cbo_tipo.currentText()
        f, t = self.dt_from.date(), self.dt_to.date()

        def keep(r):
            if not (f <= r[0] <= t): return False
            if tipo != "Todos" and r[1] != tipo: return False
            return True

        rows = [r for r in self._rows if keep(r)]
        rows.sort(key=lambda r: r[0].toJulianDay(), reverse=True)

        self.tbl.setRowCount(0)
        for r in rows:
            row = self.tbl.rowCount(); self.tbl.insertRow(row)
            self.tbl.setItem(row, 0, QTableWidgetItem(r[0].toString("dd/MM/yyyy")))
            self.tbl.setItem(row, 1, QTableWidgetItem(r[1]))
            self.tbl.setItem(row, 2, QTableWidgetItem(r[2]))
            self.tbl.setItem(row, 3, QTableWidgetItem(r[3]))
            self.tbl.setItem(row, 4, QTableWidgetItem(str(r[4])))
            self.tbl.setItem(row, 5, QTableWidgetItem(r[5]))
