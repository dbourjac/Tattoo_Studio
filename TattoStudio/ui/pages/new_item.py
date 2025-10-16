# ui/pages/new_item.py
from typing import Optional
import random

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton,
    QMessageBox, QSizePolicy, QFrame
)

from data.db.session import SessionLocal
from data.models.product import Product


def crear_producto(
    sku: str,
    name: str,
    category: Optional[str],
    unidad: str,
    cost: float,
    stock: int,
    min_stock: int,
    caduca: bool,
    proveedor: str,
    activo: bool,
) -> Product:
    """Inserta un nuevo producto en la base de datos y lo retorna."""
    session = SessionLocal()
    try:
        nuevo = Product(
            sku=sku,
            name=name,
            category=category or "consumibles",
            unidad=unidad,
            cost=cost,
            stock=stock,
            min_stock=min_stock,
            caduca=caduca,
            proveedor=proveedor,
            activo=activo,
        )
        session.add(nuevo)
        session.commit()
        session.refresh(nuevo)
        return nuevo
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class NewItemPage(QWidget):
    # señal que escucha MainWindow para refrescar la tabla
    item_creado = pyqtSignal(str)  # SKU

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Nuevo ítem")
        self.setMinimumWidth(720)
        self.setMinimumHeight(640)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setObjectName("NewItemPage")

        # QSS local (colores coherentes con tu theme; sin forzar tamaños de letra)
        self.setStyleSheet("""
        #NewItemPage QLabel { background: transparent; color: #E5E7EB; }
        #Card { background: #2A2F34; border: 1px solid #495057; border-radius: 16px; }

        /* inputs altos y con padding generoso */
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: #1F2429; color: #E5E7EB;
            border: 1px solid #3B4148; border-radius: 12px;
            padding: 12px 14px;
            min-height: 54px;
            selection-background-color: #374151;
        }
        QLineEdit::placeholder { color: #9CA3AF; }

        /* checkboxes sin fondo */
        QCheckBox { background: transparent; spacing: 10px; color: #E5E7EB; }

        /* botones */
        QPushButton#Primary {
            background: #3B82F6; color: white; border: none;
            border-radius: 12px; padding: 10px 18px; font-weight: 700;
        }
        QPushButton#Primary:hover { background: #2563EB; }
        QPushButton#Ghost {
            background: transparent; color: #E5E7EB;
            border: 1px solid #495057; border-radius: 12px; padding: 10px 18px;
        }
        QPushButton#Ghost:hover { border-color: #7b8190; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 32)
        root.setSpacing(28)

        # ---- Título ----
        title = QLabel("Nuevo ítem")
        title.setAlignment(Qt.AlignHCenter)
        title.setStyleSheet("font-size: 30px; font-weight: 900; margin: 0 0 16px;")
        root.addWidget(title)

        # ---- Card ----
        card = QFrame()
        card.setObjectName("Card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(28, 24, 28, 24)
        card_lay.setSpacing(22)
        root.addWidget(card)

        # ---- Formulario dentro de la card ----
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(32)   # aire label ↔ campo
        form.setVerticalSpacing(24)     # aire entre filas (además del wrapper)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        card_lay.addLayout(form)

        # Wrapper: añade margen vertical por fila para evitar "encimado"
        def wrap(field, min_h=60, top=10, bottom=10):
            box = QWidget()
            box.setMinimumHeight(min_h)
            box.setStyleSheet("background: transparent;")
            lay = QVBoxLayout(box)
            lay.setContentsMargins(0, top, 0, bottom)  # margen POR FILA
            lay.setSpacing(0)
            lay.addWidget(field)
            return box

        # --- Campos ---

        # SKU autogenerado
        self.in_sku = QLineEdit()
        self.in_sku.setReadOnly(True)
        form.addRow("SKU:", wrap(self.in_sku))

        # Nombre
        self.in_nombre = QLineEdit()
        self.in_nombre.setPlaceholderText("Nombre del producto *")
        form.addRow("Nombre:", wrap(self.in_nombre))

        # Categoría
        self.cb_categoria = QComboBox()
        self.cb_categoria.addItems(["Consumibles", "Tintas", "Agujas", "EPP", "Limpieza", "Aftercare"])
        form.addRow("Categoría:", wrap(self.cb_categoria))

        # Otra categoría
        self.in_categoria_extra = QLineEdit()
        self.in_categoria_extra.setPlaceholderText("Otra categoría (opcional)")
        form.addRow("Otra categoría:", wrap(self.in_categoria_extra))

        # Unidad
        self.cb_unidad = QComboBox()
        self.cb_unidad.addItems(["pz", "ml", "par"])
        form.addRow("Unidad:", wrap(self.cb_unidad))

        # Costo
        self.in_costo = QDoubleSpinBox()
        self.in_costo.setRange(0, 1_000_000)
        self.in_costo.setPrefix("$ ")
        self.in_costo.setDecimals(2)
        form.addRow("Costo:", wrap(self.in_costo))

        # Stock
        self.in_stock = QSpinBox()
        self.in_stock.setRange(0, 1_000_000)
        self.in_stock.setValue(10)
        form.addRow("Stock:", wrap(self.in_stock))

        # Mínimo stock
        self.in_min_stock = QSpinBox()
        self.in_min_stock.setRange(0, 1_000_000)
        self.in_min_stock.setValue(5)
        form.addRow("Mínimo stock:", wrap(self.in_min_stock))

        # Caduca
        self.chk_caduca = QCheckBox("¿Caduca?")
        form.addRow("Caduca:", wrap(self.chk_caduca))

        # Proveedor
        self.in_proveedor = QLineEdit()
        form.addRow("Proveedor:", wrap(self.in_proveedor))

        # Activo
        self.chk_activo = QCheckBox("Activo")
        self.chk_activo.setChecked(True)
        form.addRow("Estado:", wrap(self.chk_activo))

        # ---- Botones ----
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(14)
        btn_bar.addStretch(1)
        self.btn_cancelar = QPushButton("Cancelar"); self.btn_cancelar.setObjectName("Ghost")
        self.btn_guardar  = QPushButton("Guardar");  self.btn_guardar.setObjectName("Primary")
        self.btn_guardar.setDefault(True)
        self.btn_cancelar.setAutoDefault(False)
        btn_bar.addWidget(self.btn_cancelar)
        btn_bar.addWidget(self.btn_guardar)
        root.addLayout(btn_bar)

        # Acciones
        self.btn_guardar.clicked.connect(self._on_guardar)
        self.btn_cancelar.clicked.connect(self.close)

        # Validación + SKU en tiempo real
        self._wire_min_validation()
        self._wire_sku_generation()

        self.in_nombre.setFocus()

        # Anchura flexible
        for w in (
            self.in_sku, self.in_nombre, self.cb_categoria, self.in_categoria_extra,
            self.cb_unidad, self.in_costo, self.in_stock, self.in_min_stock,
            self.in_proveedor
        ):
            w.setMinimumWidth(540)
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # ---------- helpers ----------
    def _generate_sku(self) -> str:
        nombre = self.in_nombre.text().strip().upper()[:3] or "XXX"
        categoria = (self.in_categoria_extra.text().strip() or self.cb_categoria.currentText()).upper()[:3] or "XXX"
        rand = random.randint(100, 999)
        return f"{nombre}-{categoria}-{rand}"

    def _wire_min_validation(self):
        def update_enabled():
            ok = bool(self.in_nombre.text().strip())
            self.btn_guardar.setEnabled(ok)

            # resaltar inválidos
            def mark(widget, condition: bool):
                widget.setProperty("invalid", not condition)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            mark(self.in_nombre, ok)

        self.in_nombre.textChanged.connect(update_enabled)
        update_enabled()

    def _wire_sku_generation(self):
        def update_sku():
            self.in_sku.setText(self._generate_sku())
        self.in_nombre.textChanged.connect(update_sku)
        self.in_categoria_extra.textChanged.connect(update_sku)
        self.cb_categoria.currentTextChanged.connect(update_sku)
        update_sku()

    # ---------- guardar ----------
    def _on_guardar(self):
        if not self.btn_guardar.isEnabled():
            QMessageBox.warning(self, "Validación", "Completa los campos obligatorios.")
            return
        try:
            producto = crear_producto(
                sku=self.in_sku.text(),
                name=self.in_nombre.text().strip(),
                category=self.in_categoria_extra.text().strip() or self.cb_categoria.currentText(),
                unidad=self.cb_unidad.currentText(),
                cost=float(self.in_costo.value()),
                stock=int(self.in_stock.value()),
                min_stock=int(self.in_min_stock.value()),
                caduca=self.chk_caduca.isChecked(),
                proveedor=self.in_proveedor.text().strip(),
                activo=self.chk_activo.isChecked(),
            )
            QMessageBox.information(self, "Éxito", f"✅ Producto '{producto.name}' creado con SKU: {producto.sku}")
            self.item_creado.emit(producto.sku)  # notifica a MainWindow
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Ocurrió un error al guardar: {e}")
