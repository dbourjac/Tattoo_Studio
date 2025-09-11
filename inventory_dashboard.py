# ui/pages/inventory_dashboard.py
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QSpacerItem, QListWidget, QListWidgetItem
)

class InventoryDashboardPage(QWidget):
    """
    Dashboard de Inventario (mock)
    - KPIs: Ítems activos, Bajo stock, Por caducar, Consumo (mes)
    - Toolbar con accesos rápidos: Nuevo ítem / Ver ítems / Movimientos
    - Alertas: Bajo stock, Por caducar (≤30 días)
    Señales (se exponen como callables para que MainWindow las conecte):
      ir_items, ir_movimientos, nuevo_item
    """
    ir_items = None
    ir_movimientos = None
    nuevo_item = None

    def __init__(self):
        super().__init__()

        # señales simples como atributos; MainWindow las asigna
        self.ir_items = lambda: None
        self.ir_movimientos = lambda: None
        self.nuevo_item = lambda: None

        # Todos los textos sin “bloque” de fondo
        self.setStyleSheet("QLabel { background: transparent; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # ===== Título =====
        title = QLabel("Inventario")
        title.setObjectName("H1")
        root.addWidget(title)

        # ===== KPIs =====
        kpis = QHBoxLayout()
        kpis.setSpacing(12)
        kpis.addWidget(self._kpi("Ítems activos", "128"))
        kpis.addWidget(self._kpi("Bajo stock", "7"))
        kpis.addWidget(self._kpi("Por caducar", "3"))
        kpis.addWidget(self._kpi("Consumo (mes)", "$4,320"))
        root.addLayout(kpis)

        # ===== Toolbar de acciones (estilo pastilla) =====
        toolbar = QFrame()
        toolbar.setObjectName("Toolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(10, 8, 10, 8)
        tb.setSpacing(8)

        btn_new = QPushButton("Nuevo ítem"); btn_new.setObjectName("CTA")
        btn_list = QPushButton("Ver ítems");  btn_list.setObjectName("GhostSmall")
        btn_mov  = QPushButton("Movimientos"); btn_mov.setObjectName("GhostSmall")

        btn_new.setMinimumHeight(34)
        btn_list.setMinimumHeight(34)
        btn_mov.setMinimumHeight(34)

        btn_new.clicked.connect(lambda: self.nuevo_item())
        btn_list.clicked.connect(lambda: self.ir_items())
        btn_mov.clicked.connect(lambda: self.ir_movimientos())

        tb.addWidget(btn_new)
        tb.addWidget(btn_list)
        tb.addWidget(btn_mov)
        tb.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        root.addWidget(toolbar)

        # ===== Alertas =====
        alerts_box = QHBoxLayout()
        alerts_box.setSpacing(12)

        # Bajo stock
        low = self._card("Bajo stock")
        low_list = self._clean_list()
        for txt in [
            "Guantes M (stock: 2 / min: 10)",
            "Cartucho 3RL (stock: 5 / min: 15)",
            "Gasa estéril (stock: 8 / min: 20)",
        ]:
            QListWidgetItem(txt, low_list)
        low.layout().addWidget(low_list)
        alerts_box.addWidget(low)

        # Por caducar
        exp = self._card("Por caducar (≤30 días)")
        exp_list = self._clean_list()
        for txt in [
            "Tinta negra Lote N-22 — 25/09/2025",
            "Solución salina Lote S-10 — 18/09/2025",
            "Crema post Lote C-07 — 29/09/2025",
        ]:
            QListWidgetItem(txt, exp_list)
        exp.layout().addWidget(exp_list)
        alerts_box.addWidget(exp)

        root.addLayout(alerts_box)

    # ---------- helpers ----------
    def _kpi(self, title: str, value: str) -> QFrame:
        """Card KPI con título fino y valor destacado."""
        card = QFrame()
        card.setObjectName("CardKPI")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(4)

        t = QLabel(title)
        t.setStyleSheet("color:#666;")
        v = QLabel(value)
        v.setStyleSheet("font-weight:800; font-size:18pt;")

        lay.addWidget(t)
        lay.addWidget(v)
        return card

    def _card(self, title: str) -> QFrame:
        """Card genérica para secciones."""
        card = QFrame()
        card.setObjectName("Card")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        head = QLabel(title)
        head.setStyleSheet("font-weight:700;")
        lay.addWidget(head)

        return card

    def _clean_list(self) -> QListWidget:
        """Lista sin bordes ni fondo sólido; ítems con alto cómodo."""
        lst = QListWidget()
        lst.setFrameShape(QFrame.NoFrame)
        lst.setUniformItemSizes(True)
        lst.setStyleSheet(
            "QListWidget { background: transparent; border: none; }"
            "QListWidget::item { padding: 6px 2px; }"
            "QListWidget::item:selected { background: rgba(0,0,0,0.07); }"
        )
        return lst
