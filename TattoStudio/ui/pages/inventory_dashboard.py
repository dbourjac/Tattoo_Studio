# ui/pages/inventory_dashboard.py
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QSpacerItem, QListWidget, QListWidgetItem
)

class InventoryDashboardPage(QWidget):
    """
    Dashboard de Inventario (cascarón)
    - KPIs: Ítems activos, Bajo stock, Por caducar, Consumo (mock)
    - Alertas: Bajo stock / Caducidad próxima
    - Accesos rápidos: Nuevo ítem / Ver ítems / Movimientos
    Señales: ir_items, ir_movimientos, nuevo_item
    """
    ir_items = None
    ir_movimientos = None
    nuevo_item = None

    def __init__(self):
        super().__init__()
        # señales simples como atributos lambda; MainWindow las conectará
        self.ir_items = lambda: None
        self.ir_movimientos = lambda: None
        self.nuevo_item = lambda: None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        title = QLabel("Inventario")
        title.setObjectName("H1")
        root.addWidget(title)

        # ====== KPIs ======
        kpis = QHBoxLayout(); kpis.setSpacing(12)

        kpis.addWidget(self._kpi("Ítems activos", "128"))
        kpis.addWidget(self._kpi("Bajo stock", "7"))
        kpis.addWidget(self._kpi("Por caducar", "3"))
        kpis.addWidget(self._kpi("Consumo (mes)", "$4,320"))
        root.addLayout(kpis)

        # ====== Accesos rápidos ======
        actions = QHBoxLayout(); actions.setSpacing(8)
        btn_new = QPushButton("Nuevo ítem"); btn_new.setObjectName("CTA")
        btn_list = QPushButton("Ver ítems")
        btn_mov  = QPushButton("Movimientos")
        btn_new.clicked.connect(lambda: self.nuevo_item())
        btn_list.clicked.connect(lambda: self.ir_items())
        btn_mov.clicked.connect(lambda: self.ir_movimientos())
        actions.addWidget(btn_new); actions.addWidget(btn_list); actions.addWidget(btn_mov)
        actions.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        root.addLayout(actions)

        # ====== Alertas ======
        alerts_box = QHBoxLayout(); alerts_box.setSpacing(12)

        # Bajo stock
        low = self._card("Bajo stock")
        low_list = QListWidget()
        for txt in ["Guantes M (stock: 2 / min: 10)", "Cartucho 3RL (stock: 5 / min: 15)", "Gasa estéril (stock: 8 / min: 20)"]:
            QListWidgetItem(txt, low_list)
        low_lay = low.layout(); low_lay.addWidget(low_list)
        alerts_box.addWidget(low)

        # Por caducar
        exp = self._card("Por caducar (≤30 días)")
        exp_list = QListWidget()
        for txt in ["Tinta negra Lote N-22 — 25/09/2025", "Solución salina Lote S-10 — 18/09/2025", "Crema post Lote C-07 — 29/09/2025"]:
            QListWidgetItem(txt, exp_list)
        exp_lay = exp.layout(); exp_lay.addWidget(exp_list)
        alerts_box.addWidget(exp)

        root.addLayout(alerts_box)

    # ---------- helpers ----------
    def _kpi(self, title: str, value: str) -> QFrame:
        card = QFrame(); card.setObjectName("CardKPI")
        lay = QVBoxLayout(card); lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(4)
        t = QLabel(title); t.setStyleSheet("color:#666;")
        v = QLabel(value); v.setStyleSheet("font-weight:800; font-size:18pt;")
        lay.addWidget(t); lay.addWidget(v)
        return card

    def _card(self, title: str) -> QFrame:
        card = QFrame(); card.setObjectName("Card")
        lay = QVBoxLayout(card); lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(8)
        head = QLabel(title); head.setStyleSheet("font-weight:700;")
        lay.addWidget(head)
        return card
