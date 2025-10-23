from PyQt5.QtCore import Qt, pyqtSignal
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
    QComboBox
)
from data.db.session import SessionLocal
from data.models.product import Product

class AjusteProductoWidget(QWidget):
    """
    Ventana (QWidget) para realizar ajustes de inventario a un producto existente.
    Permite seleccionar tipo de ajuste (entrada/salida) y la cantidad.
    """

    ajuste_realizado = pyqtSignal(str)

    def __init__(self, producto: Product, parent=None):
        super().__init__(parent)
        self.producto = producto
        self.setWindowTitle("Ajuste de inventario")
        self.setMinimumWidth(400)
        self.setWindowFlag(Qt.Window)
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

            QLineEdit, QComboBox, QSpinBox {
                background: #1F2429;
                color: #E5E7EB;
                border: 1px solid #3B4148;
                border-radius: 12px;
                padding: 10px 12px;
                min-height: 44px;
                selection-background-color: #374151;
            }

            QComboBox::drop-down {
                border: none;
            }

            QComboBox::down-arrow {
                image: none;
                border: none;
            }

            QPushButton#Primary {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 18px;
                font-weight: 700;
            }
            QPushButton#Primary:hover { background: #2563EB; }
            
            QPushButton#Ghost {
                background: transparent;
                color: #E5E7EB;
                border: 1px solid #495057;
                border-radius: 10px;
                padding: 10px 18px;
            }
            QPushButton#Ghost:hover { border-color: #7b8190; }
            """
        )

        # Fuentes
        fuente_label = QFont("Segoe UI", 11, QFont.Bold)
        fuente_input = QFont("Segoe UI", 11)

        # Layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)

        # Formulario
        form = QFormLayout()
        form.setSpacing(18)

        # Campos informativos (no editables)
        self.in_sku = QLineEdit(producto.sku)
        self.in_sku.setReadOnly(True)
        self.in_sku.setFont(fuente_input)

        self.in_nombre = QLineEdit(producto.name)
        self.in_nombre.setReadOnly(True)
        self.in_nombre.setFont(fuente_input)

        self.in_stock = QLineEdit(str(producto.stock))
        self.in_stock.setReadOnly(True)
        self.in_stock.setFont(fuente_input)

        # Tipo de ajuste
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(["Entrada", "Salida"])
        self.combo_tipo.setFont(fuente_input)

        # Cantidad del ajuste
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
        add_row("Stock actual:", self.in_stock)
        add_row("Tipo de ajuste:", self.combo_tipo)
        add_row("Cantidad:", self.in_cantidad)

        layout.addLayout(form)

        # Botones
        self.btn_box = QHBoxLayout()
        self.btn_guardar = QPushButton("Guardar ajuste")
        self.btn_guardar.setObjectName("Primary")
        self.btn_cancelar = QPushButton("Cancelar")
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
        """Guarda el ajuste en la base de datos."""
        cantidad = self.in_cantidad.value()
        tipo_ajuste = self.combo_tipo.currentText()
        
        if cantidad <= 0:
            QMessageBox.warning(self, "Cantidad inválida", 
                              "La cantidad debe ser mayor que cero.")
            return

        # Convertir a número negativo si es una salida
        if tipo_ajuste == "Salida":
            cantidad = -cantidad

        session = SessionLocal()
        try:
            producto_db = session.query(Product).filter(
                Product.sku == self.producto.sku).first()
            
            if producto_db:
                # Verificar que no quede stock negativo
                if producto_db.stock + cantidad < 0:
                    QMessageBox.warning(self, "Error", 
                        "No hay suficiente stock para realizar esta salida.")
                    return
                
                producto_db.stock += cantidad
                session.commit()
                
                msg = "entrada" if tipo_ajuste == "Entrada" else "salida"
                QMessageBox.information(
                    self,
                    "Ajuste registrado",
                    f"Se ha registrado la {msg} de {abs(cantidad)} unidades.",
                )
                self.ajuste_realizado.emit(self.producto.name)
                self.close()
            else:
                QMessageBox.critical(
                    self, "Error", 
                    "No se encontró el producto en la base de datos."
                )
        except Exception as e:
            session.rollback()
            QMessageBox.critical(
                self, "Error", 
                f"Ocurrió un error al guardar: {str(e)}"
            )
        finally:
            session.close()