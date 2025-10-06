from data.db.session import SessionLocal
from data.models.artist import Artist
from data.models.transaction import Transaction
from data.models.session_tattoo import TattooSession
from datetime import datetime

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QDoubleSpinBox, QMessageBox

class CashRegisterDialog(QDialog):
    """Diálogo modal para registrar un pago en caja."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar pago")
        self.setMinimumSize(400, 300)

        layout = QVBoxLayout(self)

        # Concepto o cliente
        layout.addWidget(QLabel("Concepto o cliente:"))
        self.input_concept = QLineEdit()
        layout.addWidget(self.input_concept)

        # Monto
        layout.addWidget(QLabel("Monto:"))
        self.input_amount = QDoubleSpinBox()
        self.input_amount.setPrefix("$ ")
        self.input_amount.setMaximum(99999)
        self.input_amount.setDecimals(2)
        layout.addWidget(self.input_amount)

        # Método de pago
        layout.addWidget(QLabel("Método de pago:"))
        self.input_method = QComboBox()
        self.input_method.addItems(["Efectivo", "Tarjeta", "Transferencia", "Otro"])
        layout.addWidget(self.input_method)

        # Artista
        layout.addWidget(QLabel("Artista:"))
        self.input_artist = QComboBox()
        self.artists = []
        self._load_artists()
        layout.addWidget(self.input_artist)

        # Botones
        btns = QHBoxLayout()
        self.btn_save = QPushButton("Registrar")
        self.btn_cancel = QPushButton("Cancelar")
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_cancel)
        layout.addLayout(btns)

        # Conexiones
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._on_save)

    def _load_artists(self):
        """Carga artistas desde la base de datos en el combobox."""
        session = SessionLocal()
        try:
            self.artists = session.query(Artist).order_by(Artist.name).all()
            self.input_artist.clear()
            for artist in self.artists:
                self.input_artist.addItem(artist.name)
        finally:
            session.close()

    def _on_save(self):
        """Guarda la transacción en la base de datos."""
        concepto = self.input_concept.text().strip()
        monto = self.input_amount.value()
        metodo = self.input_method.currentText()
        artist_index = self.input_artist.currentIndex()

        if not concepto or monto <= 0 or artist_index == -1:
            QMessageBox.warning(self, "Campos incompletos", "Debe ingresar un concepto, un monto válido y seleccionar un artista.")
            return

        selected_artist = self.artists[artist_index]

        session = SessionLocal()
        try:
            # Buscar última sesión del artista
            existing_session = (
                session.query(TattooSession)
                .filter_by(artist_id=selected_artist.id)
                .order_by(TattooSession.id.desc())
                .first()
            )

            if not existing_session:
                QMessageBox.warning(self, "Sin sesión", "El artista no tiene sesiones activas.")
                return

            nueva_transaccion = Transaction(
                session_id=existing_session.id,
                artist_id=selected_artist.id,
                amount=monto,
                method=metodo,
                date=datetime.now(),
            )
            session.add(nueva_transaccion)
            session.commit()

        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"Error al guardar en la base de datos:\n{e}")
            return
        finally:
            session.close()

        QMessageBox.information(self, "Pago registrado", f"Pago registrado con éxito:\n{concepto} - ${monto:.2f}")
        self.accept()
