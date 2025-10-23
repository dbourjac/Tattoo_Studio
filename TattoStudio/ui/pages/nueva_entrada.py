from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QMessageBox,
)
from PyQt5.QtCore import pyqtSignal
from data.db.session import SessionLocal
from data.models.product import Product


class EntradaProductoWidget(QWidget):
    """
    Ventana (QWidget) para registrar una nueva entrada de un producto existente.
    Muestra los datos del producto (solo lectura) y permite añadir cantidad.
    """

    entrada_creada = pyqtSignal(str)

    def __init__(self, producto: Product, parent=None):
        super().__init__(parent)
        self.producto = producto
        self.setWindowTitle("Nueva entrada de producto")
        self.setMinimumWidth(400)
        self.setWindowFlag(Qt.Window)  # Permite que se abra como ventana independiente
        self.setStyleSheet(
            """
        QWidget {
            background: #1A1D21;
        }

        QLabel {
            background: transparent;
            color: #E5E7EB;
        }

        #Card {
            background: #2A2F34;
            border: 1px solid #495057;
            border-radius: 16px;
        }

        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: #1F2429;
            color: #E5E7EB;
            border: 1px solid #3B4148;
            border-radius: 12px;
            padding: 10px 12px;
            min-height: 44px;
            selection-background-color: #374151;
        }

        QLineEdit::placeholder {
            color: #9CA3AF;
        }

        QCheckBox {
            background: transparent;
            spacing: 10px;
            color: #E5E7EB;
        }

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
        """
        )

        # ===== Estilo general =====
        fuente_label = QFont("Segoe UI", 11, QFont.Bold)
        fuente_input = QFont("Segoe UI", 11)

        # ===== Layout principal =====
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)

        # ===== Formulario =====
        form = QFormLayout()
        form.setSpacing(18)

        # Campos informativos (no editables)
        self.in_sku = QLineEdit(producto.sku)
        self.in_sku.setReadOnly(True)
        self.in_sku.setFont(fuente_input)

        self.in_nombre = QLineEdit(producto.name)
        self.in_nombre.setReadOnly(True)
        self.in_nombre.setFont(fuente_input)

        self.in_categoria = QLineEdit(producto.category)
        self.in_categoria.setReadOnly(True)
        self.in_categoria.setFont(fuente_input)

        self.in_unidad = QLineEdit(producto.unidad)
        self.in_unidad.setReadOnly(True)
        self.in_unidad.setFont(fuente_input)

        # Campo de entrada de cantidad
        self.in_cantidad = QSpinBox()
        self.in_cantidad.setRange(1, 100000)
        self.in_cantidad.setValue(1)
        self.in_cantidad.setFont(fuente_input)
        self.in_cantidad.setFixedHeight(32)

        # Añadir campos al formulario
        def add_row(label_text, widget):
            label = QLabel(label_text)
            label.setFont(fuente_label)
            form.addRow(label, widget)

        add_row("SKU:", self.in_sku)
        add_row("Nombre:", self.in_nombre)
        add_row("Categoría:", self.in_categoria)
        add_row("Unidad:", self.in_unidad)
        add_row("Cantidad a añadir:", self.in_cantidad)

        layout.addLayout(form)

        # ===== Botones =====
        self.btn_box = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar")
        self.btn_guardar.setObjectName("Primary")
        self.btn_cancelar = QPushButton("Cerrar")
        self.btn_cancelar.setObjectName("Ghost")

        self.btn_guardar.setFont(fuente_label)
        self.btn_cancelar.setFont(fuente_label)
        self.btn_guardar.setFixedHeight(36)
        self.btn_cancelar.setFixedHeight(36)

        self.btn_guardar.clicked.connect(self.guardar)
        self.btn_cancelar.clicked.connect(self.close)

        self.btn_box.addStretch()
        self.btn_box.addWidget(self.btn_guardar)
        self.btn_box.addWidget(self.btn_cancelar)

        layout.addLayout(self.btn_box)

    def guardar(self):
        """Guarda la nueva cantidad en la base de datos."""
        cantidad = self.in_cantidad.value()
        if cantidad <= 0:
            QMessageBox.warning(self, "Cantidad inválida", "La cantidad debe ser mayor que cero.")
            return

        # Actualizar la cantidad en la base de datos
        session = SessionLocal()
        try:
            producto_db = session.query(Product).filter(Product.sku == self.producto.sku).first()
            if producto_db:
                producto_db.stock += cantidad
                session.commit()
                QMessageBox.information(
                    self,
                    "Entrada registrada",
                    f"Se han añadido {cantidad} unidades a '{self.producto.name}'.",
                )
                self.entrada_creada.emit(self.producto.name)
                self.close()
            else:
                QMessageBox.critical(
                    self, "Error", "No se encontró el producto en la base de datos."
                )
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"Ocurrió un error al guardar: {str(e)}")
        finally:
            session.close()
