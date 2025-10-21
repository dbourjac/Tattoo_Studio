from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QSpacerItem, QListWidget, QListWidgetItem
)
from datetime import date, timedelta, datetime

from data.db.session import SessionLocal
from data.models.product import Product


class InventoryDashboardPage(QWidget):
    """
    Dashboard de Inventario
    - KPIs: Ítems activos, Bajo stock, Por caducar, Consumo (mes)
    - Accesos rápidos: Nuevo ítem / Ver ítems / Movimientos
    - Listas: Bajo stock y Por caducar (≤30 días)
    Señales (callables que MainWindow debe asignar):
      ir_items, ir_movimientos, nuevo_item
    """
    ir_items = None
    ir_movimientos = None
    nuevo_item = None

    def __init__(self):
        super().__init__()
        # Señales simples por atributo (MainWindow las conecta)
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

        # Guardamos referencias para actualizarlas
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

        # Al iniciar, refrescamos
        self.refrescar_datos()

    # ---------- UI helpers ----------
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

        # guardamos el label de valor para actualizarlo
        card.value_label = v
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

    # ---------- Datos ----------
    def refrescar_datos(self):
        """Consulta la BD y actualiza KPIs + listas. Tolera ausencia de 'fechacaducidad'."""
        session = SessionLocal()
        try:
            # Ítems activos
            activos = session.query(Product).filter(Product.activo == True).count()

            # Bajo stock (solo activos)
            bajo_stock = session.query(Product).filter(
                Product.activo == True,
                Product.stock < Product.min_stock
            ).count()

            # Por caducar (≤30 días) — solo si el modelo/tabla trae 'fechacaducidad'
            fecha_limite = date.today() + timedelta(days=30)
            por_caducar_list = []
            try:
                productos_caducables = session.query(Product).filter(Product.caduca == True).all()
                for p in productos_caducables:
                    fc = getattr(p, "fechacaducidad", None)
                    if fc and self._esta_por_caducar(fc, fecha_limite):
                        por_caducar_list.append((p.name, fc))
            except Exception:
                # Si no existe la columna o hay error de parseo, dejamos lista vacía
                por_caducar_list = []

            # Consumo (mes) — placeholder hasta que tengamos movimientos
            consumo_mes = 0

            # KPIs
            self.lbl_activos.value_label.setText(str(activos))
            self.lbl_bajo_stock.value_label.setText(str(bajo_stock))
            self.lbl_por_caducar.value_label.setText(str(len(por_caducar_list)))
            self.lbl_consumo.value_label.setText(f"${consumo_mes:,}")

            # Listas
            self.low_list.clear()
            for p in session.query(Product).filter(
                Product.activo == True,
                Product.stock < Product.min_stock
            ).order_by(Product.stock.asc()).all():
                QListWidgetItem(f"{p.name} (stock: {p.stock}/{p.min_stock})", self.low_list)

            self.exp_list.clear()
            for name, fecha_str in sorted(por_caducar_list, key=lambda x: x[1]):
                try:
                    fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                    text = f"{name} — {fecha.strftime('%d/%m/%Y')}"
                except Exception:
                    text = f"{name} — {fecha_str}"
                QListWidgetItem(text, self.exp_list)

        except Exception as e:
            print(f"⚠️ Error al refrescar datos del inventario: {e}")
        finally:
            session.close()

    def _esta_por_caducar(self, fecha_str, fecha_limite):
        """Devuelve True si fecha_str (YYYY-MM-DD) es <= fecha_limite."""
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            return fecha <= fecha_limite
        except Exception:
            return False
