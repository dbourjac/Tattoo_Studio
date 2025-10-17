from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QSpacerItem, QListWidget, QListWidgetItem
)
from data.db.session import SessionLocal
from data.models.product import Product
from datetime import date, timedelta, datetime


class InventoryDashboardPage(QWidget):
    ir_items = None
    ir_movimientos = None
    nuevo_item = None

    def __init__(self):
        super().__init__()
        self.ir_items = lambda: None
        self.ir_movimientos = lambda: None
        self.nuevo_item = lambda: None

        self.setStyleSheet("QLabel { background: transparent; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # ===== Título =====
        title = QLabel("Inventario")
        title.setObjectName("H1")
        root.addWidget(title)

        # ===== KPIs =====
        self.kpi_layout = QHBoxLayout()
        self.kpi_layout.setSpacing(12)
        root.addLayout(self.kpi_layout)

        # Guardamos referencias para actualizarlas después
        self.lbl_activos = self._kpi("Ítems activos", "0")
        self.lbl_bajo_stock = self._kpi("Bajo stock", "0")
        self.lbl_por_caducar = self._kpi("Por caducar", "0")
        self.lbl_consumo = self._kpi("Consumo (mes)", "$0")

        self.kpi_layout.addWidget(self.lbl_activos)
        self.kpi_layout.addWidget(self.lbl_bajo_stock)
        self.kpi_layout.addWidget(self.lbl_por_caducar)
        self.kpi_layout.addWidget(self.lbl_consumo)

        # ===== Toolbar =====
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
        self.low_list = self._clean_list()
        low.layout().addWidget(self.low_list)
        alerts_box.addWidget(low)

        # Por caducar
        exp = self._card("Por caducar (≤30 días)")
        self.exp_list = self._clean_list()
        exp.layout().addWidget(self.exp_list)
        alerts_box.addWidget(exp)

        root.addLayout(alerts_box)

        # 🔹 Llamar a refrescar datos al iniciar
        self.refrescar_datos()

    # ---------- helpers ----------
    def _kpi(self, title: str, value: str) -> QFrame:
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

        card.value_label = v  # Guardamos referencia al QLabel de valor
        return card

    def _card(self, title: str) -> QFrame:
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
        lst = QListWidget()
        lst.setFrameShape(QFrame.NoFrame)
        lst.setUniformItemSizes(True)
        lst.setStyleSheet(
            "QListWidget { background: transparent; border: none; }"
            "QListWidget::item { padding: 6px 2px; }"
            "QListWidget::item:selected { background: rgba(0,0,0,0.07); }"
        )
        return lst

    # ---------- nueva función ----------
    def refrescar_datos(self):
        """Actualiza KPIs y listas desde la base de datos."""
        session = SessionLocal()
        try:
            # 🔹 Ítems activos
            activos = session.query(Product).filter(Product.activo == True).count()

            # 🔹 Bajo stock
            bajo_stock = session.query(Product).filter(
                Product.activo == True, Product.stock < Product.min_stock
            ).count()

            # 🔹 Por caducar
            fecha_limite = date.today() + timedelta(days=30)
            productos_caducables = session.query(Product).filter(Product.caduca == True).all()
            por_caducar = [
                p for p in productos_caducables
                if p.fechacaducidad and self._esta_por_caducar(p.fechacaducidad, fecha_limite)
            ]

            # 🔹 Consumo (mes) → puedes reemplazarlo con una consulta real si tienes tabla de movimientos
            consumo_mes = 0  

            # 🔹 Actualizar KPIs
            self.lbl_activos.value_label.setText(str(activos))
            self.lbl_bajo_stock.value_label.setText(str(bajo_stock))
            self.lbl_por_caducar.value_label.setText(str(len(por_caducar)))
            self.lbl_consumo.value_label.setText(f"${consumo_mes:,}")

            # 🔹 Actualizar listas
            self.low_list.clear()
            for p in session.query(Product).filter(Product.stock < Product.min_stock, Product.activo == True).all():
                QListWidgetItem(f"{p.name} (stock: {p.stock}/{p.min_stock})", self.low_list)

            self.exp_list.clear()
            for p in por_caducar:
                fecha = datetime.strptime(p.fechacaducidad, "%Y-%m-%d").date()
                QListWidgetItem(f"{p.name} — {fecha.strftime('%d/%m/%Y')}", self.exp_list)

        except Exception as e:
            print(f"⚠️ Error al refrescar datos del inventario: {e}")
        finally:
            session.close()

    def _esta_por_caducar(self, fecha_str, fecha_limite):
        """Convierte el string y verifica si está dentro del rango."""
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            return fecha <= fecha_limite
        except ValueError:
            return False
