from PyQt5.QtCore import Qt, pyqtSignal, QDate
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton,
    QMessageBox, QSizePolicy, QCalendarWidget, QDialog, QDialogButtonBox
)
import random
from typing import Optional
from data.db.session import SessionLocal
from data.models.product import Product

class NewItemPage(QWidget):
    item_creado = pyqtSignal(str) 

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nuevo item")
        self.setMinimumHeight(860)
        self.setMinimumWidth(560)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setStyleSheet("QLabel { background: transparent; font-size: 11pt;}")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(20)

        # ---- Título ----
        title = QLabel("Nuevo item")
        title.setAlignment(Qt.AlignHCenter)
        title.setStyleSheet("font-size: 22pt; font-weight: bold; margin-bottom: 16px;")
        root.addWidget(title)

        # ---- Formulario ----
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(16)

        self.in_sku = QLineEdit()
        self.in_sku.setReadOnly(True)
        self.in_sku.setMinimumHeight(36)
        form.addRow("SKU:", self.in_sku)

        self.in_nombre = QLineEdit()
        self.in_nombre.setPlaceholderText("Nombre del producto *")
        self.in_nombre.setMinimumHeight(36)
        form.addRow("Nombre:", self.in_nombre)

        self.cb_categoria = QComboBox()
        self.cb_categoria.addItems(["Consumibles","Tintas", "Agujas", "EPP", "Limpieza", "Aftercare"])
        self.cb_categoria.setMinimumHeight(36)
        form.addRow("Categoría:", self.cb_categoria)

        self.in_categoria_extra = QLineEdit()
        self.in_categoria_extra.setPlaceholderText("Otra categoría (opcional)")
        self.in_categoria_extra.setMinimumHeight(36)
        form.addRow("Otra categoría:", self.in_categoria_extra)

        self.cb_unidad = QComboBox()
        self.cb_unidad.addItems(["pz", "ml", "par"])
        self.cb_unidad.setMinimumHeight(36)
        form.addRow("Unidad:", self.cb_unidad)

        self.in_costo = QDoubleSpinBox()
        self.in_costo.setRange(0, 1000000)
        self.in_costo.setPrefix("$ ")
        self.in_costo.setDecimals(2)
        self.in_costo.setMinimumHeight(36)
        form.addRow("Costo:", self.in_costo)

        self.in_stock = QSpinBox()
        self.in_stock.setValue(10)
        self.in_stock.setRange(0, 1000000)
        self.in_stock.setMinimumHeight(36)
        form.addRow("Stock:", self.in_stock)

        self.in_min_stock = QSpinBox()
        self.in_min_stock.setValue(5)
        self.in_min_stock.setRange(0, 1000000)
        self.in_min_stock.setMinimumHeight(36)
        form.addRow("Mínimo stock:", self.in_min_stock)

        # Caduca con calendario
        self.chk_caduca = QCheckBox("¿Caduca?")
        self.chk_caduca.setMinimumHeight(36)
        form.addRow("Caduca:", self.chk_caduca)
        self.chk_caduca.stateChanged.connect(self._show_calendar_if_checked)

        # Campo para fecha de caducidad
        self.in_fechacaducidad = QLineEdit()
        self.in_fechacaducidad.setReadOnly(True)
        self.in_fechacaducidad.setPlaceholderText("Selecciona fecha si aplica")
        self.in_fechacaducidad.setMinimumHeight(36)
        form.addRow("Fecha caducidad:", self.in_fechacaducidad)

        self.in_proveedor = QLineEdit()
        self.in_proveedor.setMinimumHeight(36)
        form.addRow("Proveedor:", self.in_proveedor)

        self.chk_activo = QCheckBox("Activo")
        self.chk_activo.setChecked(True)
        self.chk_activo.setMinimumHeight(36)
        form.addRow("Estado:", self.chk_activo)

        root.addLayout(form)

        # ---- Botones ----
        btn_bar = QHBoxLayout()
        btn_bar.addStretch(1)
        self.btn_guardar = QPushButton("Guardar")
        self.btn_cancelar = QPushButton("Cancelar")
        for b in (self.btn_guardar, self.btn_cancelar):
            b.setMinimumHeight(44)
            b.setStyleSheet("font-size: 11pt; padding: 6px 14px;")
        btn_bar.addWidget(self.btn_guardar)
        btn_bar.addWidget(self.btn_cancelar)
        root.addLayout(btn_bar)

        self.btn_guardar.clicked.connect(self._on_guardar)
        self.btn_cancelar.clicked.connect(self.close)

        self._wire_min_validation()
        self._wire_sku_generation()

    def _show_calendar_if_checked(self, state):
        if state == Qt.Checked:
            dlg = QDialog(self)
            dlg.setWindowTitle("Selecciona fecha de caducidad")
            dlg.setModal(True)
            layout = QVBoxLayout(dlg)
            calendar = QCalendarWidget()
            calendar.setGridVisible(True)
            layout.addWidget(calendar)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            layout.addWidget(buttons)

            def aceptar():
                fecha = calendar.selectedDate().toPyDate()
                self.in_fechacaducidad.setText(fecha.isoformat())
                dlg.accept()

            def cancelar():
                self.chk_caduca.setChecked(False)
                dlg.reject()

            buttons.accepted.connect(aceptar)
            buttons.rejected.connect(cancelar)
            dlg.exec_()
        else:
            self.in_fechacaducidad.clear()

    def _wire_min_validation(self):
        """Validar campos obligatorios: nombre, categoría, unidad, costo"""
        def update_enabled():
            ok =  bool(self.in_nombre.text().strip())  > 0   

            self.btn_guardar.setEnabled(ok)

            # resaltar inválidos
            def mark(widget, condition: bool):
                widget.setProperty("invalid", not condition)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            mark(self.in_nombre, bool(self.in_nombre.text().strip()))
          

        self.in_nombre.textChanged.connect(update_enabled)
        update_enabled()

    def _wire_sku_generation(self):
        def update_sku():
            nombre = self.in_nombre.text().strip().upper()[:3] or "XXX"
            categoria = (self.in_categoria_extra.text().strip() or self.cb_categoria.currentText()).upper()[:3] or "XXX"
            rand = random.randint(100, 999)
            self.in_sku.setText(f"{nombre}-{categoria}-{rand}")
        self.in_nombre.textChanged.connect(update_sku)
        self.in_categoria_extra.textChanged.connect(update_sku)
        self.cb_categoria.currentTextChanged.connect(update_sku)
        update_sku()

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
                provedor=self.in_proveedor.text().strip(),
                activo=self.chk_activo.isChecked(),
                fechacaducidad=self.in_fechacaducidad.text() or None
            )
            QMessageBox.information(self, "Éxito", f"✅ Producto '{producto.name}' creado con SKU: {producto.sku}")
            self.item_creado.emit(producto.sku)
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Ocurrió un error al guardar: {e}")

def crear_producto(
    sku: str,
    name: str,
    category: Optional[str],
    unidad: str,
    cost: float,
    stock: int,
    min_stock: int,
    caduca: bool,
    provedor: str,
    activo: bool,
    fechacaducidad: Optional[str] = None
) -> Product:
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
            provedor=provedor,
            activo=activo,
            fechacaducidad=fechacaducidad
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
