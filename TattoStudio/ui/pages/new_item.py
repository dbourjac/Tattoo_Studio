# ui/pages/new_item.py
from typing import Optional
import random

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton,
    QMessageBox, QSizePolicy, QDialog, QDialogButtonBox, QCalendarWidget, QFrame
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
    fechacaducidad: Optional[str] = None,
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
            proveedor=proveedor,              # <- nombre correcto
            activo=activo,
            fechacaducidad=fechacaducidad,    # <- nuevo campo opcional
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
    item_creado = pyqtSignal(str)  # SKU

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Nuevo ítem")
        self.setMinimumWidth(805)
        self.setMinimumHeight(1000)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setObjectName("NewItemPage")

        # QSS liviano: respeta tipografías del theme, mejora inputs y checkboxes
        self.setStyleSheet("""
        #NewItemPage QLabel { background: transparent; color: #E5E7EB; }
        #Card { background: #2A2F34; border: 1px solid #495057; border-radius: 16px; }

        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: #1F2429; color: #E5E7EB;
            border: 1px solid #3B4148; border-radius: 12px;
            padding: 10px 12px; min-height: 44px;
            selection-background-color: #374151;
        }
        QLineEdit::placeholder { color: #9CA3AF; }
        QCheckBox { background: transparent; spacing: 10px; color: #E5E7EB; }

        QPushButton#Primary {
            background: #3B82F6; color: white; border: none;
            border-radius: 10px; padding: 10px 18px; font-weight: 700;
        }
        QPushButton#Primary:hover { background: #2563EB; }
        QPushButton#Ghost {
            background: transparent; color: #E5E7EB;
            border: 1px solid #495057; border-radius: 10px; padding: 10px 18px;
        }
        QPushButton#Ghost:hover { border-color: #7b8190; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(24)

        # ---- Título ----
        title = QLabel("Nuevo ítem")
        title.setAlignment(Qt.AlignHCenter)
        title.setStyleSheet("font-weight: 900; margin: 0 0 12px;")
        root.addWidget(title)

        # ---- Card ----
        card = QFrame()
        card.setObjectName("Card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(24, 22, 24, 22)
        card_lay.setSpacing(18)
        root.addWidget(card)

        # ---- Formulario ----
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(26)
        form.setVerticalSpacing(18)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        card_lay.addLayout(form)

        # SKU
        self.in_sku = QLineEdit()
        self.in_sku.setReadOnly(True)
        form.addRow("SKU:", self.in_sku)

        # Nombre
        self.in_nombre = QLineEdit()
        self.in_nombre.setPlaceholderText("Nombre del producto *")
        form.addRow("Nombre:", self.in_nombre)

        # Categoría
        self.cb_categoria = QComboBox()
        self.cb_categoria.addItems(["Consumibles", "Tintas", "Agujas", "EPP", "Limpieza", "Aftercare"])
        form.addRow("Categoría:", self.cb_categoria)

        # Otra categoría
        self.in_categoria_extra = QLineEdit()
        self.in_categoria_extra.setPlaceholderText("Otra categoría (opcional)")
        form.addRow("Otra categoría:", self.in_categoria_extra)

        # Unidad
        self.cb_unidad = QComboBox()
        self.cb_unidad.addItems(["pz", "ml", "par"])
        form.addRow("Unidad:", self.cb_unidad)

        # Costo
        self.in_costo = QDoubleSpinBox()
        self.in_costo.setRange(0, 1_000_000)
        self.in_costo.setPrefix("$ ")
        self.in_costo.setDecimals(2)
        form.addRow("Costo:", self.in_costo)

        # Stock
        self.in_stock = QSpinBox()
        self.in_stock.setRange(0, 1_000_000)
        self.in_stock.setValue(10)
        form.addRow("Stock:", self.in_stock)

        # Mínimo stock
        self.in_min_stock = QSpinBox()
        self.in_min_stock.setRange(0, 1_000_000)
        self.in_min_stock.setValue(5)
        form.addRow("Mínimo stock:", self.in_min_stock)

        # ¿Caduca?
        self.chk_caduca = QCheckBox("¿Caduca?")
        self.chk_caduca.stateChanged.connect(self._show_calendar_if_checked)
        form.addRow("Caduca:", self.chk_caduca)

        # Fecha de caducidad (solo lectura; se llena desde el calendario)
        self.in_fechacaducidad = QLineEdit()
        self.in_fechacaducidad.setReadOnly(True)
        self.in_fechacaducidad.setPlaceholderText("Selecciona fecha si aplica")
        form.addRow("Fecha caducidad:", self.in_fechacaducidad)

        # Proveedor
        self.in_proveedor = QLineEdit()
        form.addRow("Proveedor:", self.in_proveedor)

        # Activo
        self.chk_activo = QCheckBox("Activo")
        self.chk_activo.setChecked(True)
        form.addRow("Estado:", self.chk_activo)

        # ---- Botones ----
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(12)
        btn_bar.addStretch(1)
        self.btn_cancelar = QPushButton("Cancelar"); self.btn_cancelar.setObjectName("Ghost")
        self.btn_guardar  = QPushButton("Guardar");  self.btn_guardar.setObjectName("Primary")
        self.btn_guardar.setDefault(True)
        btn_bar.addWidget(self.btn_cancelar)
        btn_bar.addWidget(self.btn_guardar)
        root.addLayout(btn_bar)

        # Acciones
        self.btn_guardar.clicked.connect(self._on_guardar)
        self.btn_cancelar.clicked.connect(self.close)

        # Validación + SKU
        self._wire_min_validation()
        self._wire_sku_generation()

        self.in_nombre.setFocus()

        # Anchura flexible (que respiren)
        for w in (
            self.in_sku, self.in_nombre, self.cb_categoria, self.in_categoria_extra,
            self.cb_unidad, self.in_costo, self.in_stock, self.in_min_stock,
            self.in_proveedor, self.in_fechacaducidad
        ):
            w.setMinimumWidth(520)
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # ---------- UX helpers ----------
    def _show_calendar_if_checked(self, state):
        if state == Qt.Checked:
            dlg = QDialog(self)
            dlg.setWindowTitle("Selecciona fecha de caducidad")
            lay = QVBoxLayout(dlg)
            cal = QCalendarWidget()
            cal.setGridVisible(True)
            lay.addWidget(cal)

            btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            lay.addWidget(btns)

            def aceptar():
                fecha = cal.selectedDate().toPyDate()
                self.in_fechacaducidad.setText(fecha.isoformat())
                dlg.accept()

            def cancelar():
                self.chk_caduca.setChecked(False)
                dlg.reject()

            btns.accepted.connect(aceptar)
            btns.rejected.connect(cancelar)
            dlg.exec_()
        else:
            self.in_fechacaducidad.clear()

    def _generate_sku(self) -> str:
        nombre = self.in_nombre.text().strip().upper()[:3] or "XXX"
        categoria = (self.in_categoria_extra.text().strip() or self.cb_categoria.currentText()).upper()[:3] or "XXX"
        rand = random.randint(100, 999)
        return f"{nombre}-{categoria}-{rand}"

    def _wire_min_validation(self):
        def update_enabled():
            ok = bool(self.in_nombre.text().strip())
            self.btn_guardar.setEnabled(ok)
        self.in_nombre.textChanged.connect(update_enabled)
        update_enabled()

    def _wire_sku_generation(self):
        def update_sku():
            self.in_sku.setText(self._generate_sku())
        self.in_nombre.textChanged.connect(update_sku)
        self.in_categoria_extra.textChanged.connect(update_sku)
        self.cb_categoria.currentTextChanged.connect(update_sku)
        update_sku()

    # ---------- Guardar ----------
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
                proveedor=self.in_proveedor.text().strip(),           # <- nombre correcto
                activo=self.chk_activo.isChecked(),
                fechacaducidad=self.in_fechacaducidad.text() or None  # <- opcional
            )
            msg = QMessageBox(self)
            msg.setWindowTitle("Éxito")
            msg.setText("✅ Item creado con exito")
            

             # Aplicar QSS para colores
            msg.setStyleSheet("""
            QLabel { color: #000000; font-size: 12pt; }
            QPushButton { background: #3B82F6; color: white; border-radius: 6px; padding: 4px 12px; }
            QPushButton:hover { background: #2563EB; }
           """)
            msg.exec_()
            self.item_creado.emit(producto.sku)
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Ocurrió un error al guardar: {e}")