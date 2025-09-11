# ui/pages/inventory_movements.py
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDateEdit, QTableWidget, QTableWidgetItem, QSizePolicy, QSpacerItem,
    QFrame
)

class InventoryMovementsPage(QWidget):
    """
    Movimientos de inventario (estilo unificado):
      - Acciones: Nueva entrada / Nueva salida / Ajuste
      - Filtros en una tira (tipo toolbar): Tipo y rango de fechas
      - Tabla con filas alternadas y datos mock suficientes para que luzca
    Señales/Callbacks:
      - volver (opcional) para regresar al dashboard si lo conectas
      - nueva_entrada(), nueva_salida(), nuevo_ajuste() -> placeholders
    """
    volver = pyqtSignal()

    # callbacks (asignadas desde MainWindow)
    nueva_entrada = None
    nueva_salida  = None
    nuevo_ajuste  = None

    def __init__(self):
        super().__init__()
        # Callbacks por defecto (no hacen nada)
        self.nueva_entrada = lambda: None
        self.nueva_salida  = lambda: None
        self.nuevo_ajuste  = lambda: None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # ====== Barra superior (volver + acciones) ======
        top = QHBoxLayout(); top.setSpacing(8)

        self.btn_back = QPushButton("← Volver")
        self.btn_back.setObjectName("GhostSmall")
        self.btn_back.setMinimumHeight(32)
        self.btn_back.clicked.connect(self.volver.emit)
        top.addWidget(self.btn_back)

        top.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        btn_in  = QPushButton("Nueva entrada"); btn_in.setObjectName("CTA")
        btn_out = QPushButton("Nueva salida");  btn_out.setObjectName("GhostSmall")
        btn_adj = QPushButton("Ajuste");        btn_adj.setObjectName("GhostSmall")
        for b in (btn_in, btn_out, btn_adj):
            b.setMinimumHeight(32)

        btn_in.clicked.connect(lambda: self.nueva_entrada())
        btn_out.clicked.connect(lambda: self.nueva_salida())
        btn_adj.clicked.connect(lambda: self.nuevo_ajuste())

        top.addWidget(btn_in); top.addWidget(btn_out); top.addWidget(btn_adj)
        root.addLayout(top)

        # ====== Filtros (tira estilizada) ======
        filt_box = QFrame(); filt_box.setObjectName("Toolbar")
        fb = QHBoxLayout(filt_box); fb.setContentsMargins(10, 8, 10, 8); fb.setSpacing(8)

        fb.addWidget(QLabel("Tipo:"))
        self.cbo_tipo = QComboBox(); self.cbo_tipo.addItems(["Todos", "Entrada", "Salida", "Ajuste"])
        fb.addWidget(self.cbo_tipo)

        fb.addSpacing(12)
        fb.addWidget(QLabel("De:"))
        self.dt_from = QDateEdit(QDate.currentDate().addMonths(-1))
        self.dt_from.setCalendarPopup(True); fb.addWidget(self.dt_from)

        fb.addWidget(QLabel("a:"))
        self.dt_to = QDateEdit(QDate.currentDate())
        self.dt_to.setCalendarPopup(True); fb.addWidget(self.dt_to)

        fb.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        root.addWidget(filt_box)

        # ====== Tabla ======
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Tipo", "SKU", "Nombre", "Cantidad", "Usuario"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.tbl, stretch=1)

        # ====== Pie (contador compacto) ======
        bottom = QHBoxLayout(); bottom.setSpacing(8)
        self.lbl_count = QLabel("Mostrando 0 movimientos"); self.lbl_count.setStyleSheet("color:#6C757D;")
        bottom.addWidget(self.lbl_count); bottom.addStretch(1)
        root.addLayout(bottom)

        # Datos y wiring
        self._seed_mock()
        self._refresh()
        self.cbo_tipo.currentTextChanged.connect(lambda _: self._refresh())
        self.dt_from.dateChanged.connect(lambda _: self._refresh())
        self.dt_to.dateChanged.connect(lambda _: self._refresh())

    # ---------- Mock data ----------
    def _seed_mock(self):
        """Genera ~30 movimientos variados en el último mes para que la vista luzca llena."""
        base = QDate.currentDate()
        rows = []
        users = ["Pablo", "Dylan", "Alex", "Jesus"]
        items = [
            ("TIN-NE-250", "Tinta Negra 250ml"),
            ("TIN-RJ-30",  "Tinta Roja 30ml"),
            ("AGJ-3RL",    "Cartucho 3RL"),
            ("EPP-GUA-M",  "Guantes M"),
            ("LIM-ALC",    "Alcohol Isopropílico"),
        ]
        # alternamos tipos y cantidades
        for i in range(30):
            d = base.addDays(-i)
            sku, nom = items[i % len(items)]
            t = ["Entrada", "Salida", "Ajuste"][i % 3]
            qty = (50 + (i % 5) * 10) if t == "Entrada" else (-(i % 7 + 1) * 3 if t == "Salida" else ((-1) ** i) * 5)
            user = users[i % len(users)]
            rows.append((d, t, sku, nom, qty, user))
        self._rows = rows

    # ---------- Render ----------
    def _refresh(self):
        tipo = self.cbo_tipo.currentText()
        d_from, d_to = self.dt_from.date(), self.dt_to.date()

        def keep(r):
            if not (d_from <= r[0] <= d_to): return False
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
            # Cantidad: ponemos signo visible y alineamos al centro
            qty_item = QTableWidgetItem(("{:+d}".format(int(r[4]))))
            qty_item.setTextAlignment(Qt.AlignCenter)
            self.tbl.setItem(row, 4, qty_item)
            self.tbl.setItem(row, 5, QTableWidgetItem(r[5]))

        self.lbl_count.setText(f"Mostrando {len(rows)} movimientos")
