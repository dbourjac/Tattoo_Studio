# ui/pages/reports.py
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QComboBox, QDateEdit, QTableWidget, QTableWidgetItem,
    QSizePolicy, QSpacerItem
)

class ReportsPage(QWidget):
    """
    Reportes financieros (mock):
      - Toolbar superior con Exportar (deshabilitado)
      - Rangos rápidos: Hoy / Semana / Mes / Custom (con date edits)
      - Filtros: Artista, Tipo de pago
      - Tarjeta "Ventas" con chips (Sales/Trends/Commissions/Tips/Payouts) + Total
      - Tabla 'Transacciones' con paginación (tamaño de página + prev/next)
    """

    def __init__(self):
        super().__init__()

        # -------- estado/UI --------
        self.period = "today"            # today | week | month | custom
        self.mode = "Sales"              # Sales | Trends | Commissions | Tips | Payouts (mock)
        self.page_size = 10              # tamaño por página por defecto
        self.current_page = 1

        self.filter_artist = "Todos"
        self.filter_payment = "Todos"
        self.custom_from = QDate.currentDate()
        self.custom_to = QDate.currentDate()

        # -------- layout raíz --------
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # Título
        title = QLabel("Reportes financieros")
        title.setObjectName("H1")
        root.addWidget(title)

        # ===================== Toolbar superior =====================
        tb_wrap = QFrame(); tb_wrap.setObjectName("Toolbar")
        toolbar = QHBoxLayout(tb_wrap); toolbar.setSpacing(8); toolbar.setContentsMargins(10, 8, 10, 8)

        # (placeholder) Exportar CSV
        self.btn_export = QPushButton("Exportar CSV")
        self.btn_export.setEnabled(False)  # deshabilitado por ahora
        toolbar.addWidget(self._icon_chip("📁", self.btn_export))

        toolbar.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        root.addWidget(tb_wrap)

        # ===================== Rangos rápidos =====================
        pr_wrap = QFrame(); pr_wrap.setObjectName("Toolbar")
        period_row = QHBoxLayout(pr_wrap); period_row.setSpacing(8); period_row.setContentsMargins(10, 8, 10, 8)

        self.btn_today = self._chip("Hoy", checked=True)
        self.btn_week  = self._chip("Esta semana")
        self.btn_month = self._chip("Este mes")
        self.btn_today.clicked.connect(lambda: self._set_period("today"))
        self.btn_week.clicked.connect(lambda: self._set_period("week"))
        self.btn_month.clicked.connect(lambda: self._set_period("month"))

        period_row.addWidget(self.btn_today)
        period_row.addWidget(self.btn_week)
        period_row.addWidget(self.btn_month)

        # Rango personalizado
        self.btn_custom = self._chip("Seleccionar fechas")
        self.btn_custom.clicked.connect(lambda: self._set_period("custom"))
        period_row.addWidget(self.btn_custom)

        # Controles del rango personalizado (solo visibles en 'custom')
        self.custom_box = QFrame(); cb = QHBoxLayout(self.custom_box)
        cb.setSpacing(6); cb.setContentsMargins(0, 0, 0, 0)
        cb.addWidget(QLabel("De:"))
        self.dt_from = QDateEdit(QDate.currentDate()); self.dt_from.setCalendarPopup(True)
        cb.addWidget(self.dt_from)
        cb.addWidget(QLabel("a:"))
        self.dt_to = QDateEdit(QDate.currentDate()); self.dt_to.setCalendarPopup(True)
        cb.addWidget(self.dt_to)
        self.custom_box.setVisible(False)
        period_row.addWidget(self.custom_box)

        # aplicar cambio de rango
        self.dt_from.dateChanged.connect(self._on_custom_dates)
        self.dt_to.dateChanged.connect(self._on_custom_dates)

        period_row.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        root.addWidget(pr_wrap)

        # ===================== Filtros =====================
        flt_wrap = QFrame(); flt_wrap.setObjectName("Toolbar")
        filters = QHBoxLayout(flt_wrap); filters.setSpacing(8); filters.setContentsMargins(10, 8, 10, 8)

        filters.addWidget(QLabel("Artista:"))
        self.cbo_artist = QComboBox(); self.cbo_artist.addItems(
            ["Todos", "Dylan Bourjac", "Jesus Esquer", "Pablo Velasquez", "Alex Chavez", "Jenni Rivera"]
        )
        self.cbo_artist.currentTextChanged.connect(self._on_filters)
        filters.addWidget(self.cbo_artist)

        filters.addSpacing(12)
        filters.addWidget(QLabel("Tipo de pago:"))
        self.cbo_payment = QComboBox(); self.cbo_payment.addItems(["Todos", "Efectivo", "Tarjeta"])
        self.cbo_payment.currentTextChanged.connect(self._on_filters)
        filters.addWidget(self.cbo_payment)

        filters.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        root.addWidget(flt_wrap)

        # ===================== Tarjeta 'Ventas' =====================
        card = QFrame(); card.setObjectName("Card")
        card_lay = QVBoxLayout(card); card_lay.setContentsMargins(16, 12, 16, 12); card_lay.setSpacing(8)

        # Header de la tarjeta
        hdr = QHBoxLayout(); hdr.setSpacing(8)
        hdr_title = QLabel("Ventas"); hdr_title.setStyleSheet("font-weight:700;")
        self.lbl_date = QLabel(self._period_text())
        self.lbl_total = QLabel(""); self.lbl_total.setStyleSheet("font-weight:800;")
        hdr.addWidget(hdr_title); hdr.addSpacing(12); hdr.addWidget(self.lbl_date)
        hdr.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        hdr.addWidget(QLabel("Total:")); hdr.addWidget(self.lbl_total)
        card_lay.addLayout(hdr)

        # Chips tipo pestañas (mock)
        tabs = QHBoxLayout(); tabs.setSpacing(6)
        self.tab_sales = self._chip("Sales", checked=True)
        self.tab_trend = self._chip("Trends")
        self.tab_comm  = self._chip("Commissions")
        self.tab_tips  = self._chip("Tips")
        self.tab_pay   = self._chip("Payouts")
        self.tab_sales.clicked.connect(lambda: self._set_mode("Sales"))
        self.tab_trend.clicked.connect(lambda: self._set_mode("Trends"))
        self.tab_comm.clicked.connect(lambda: self._set_mode("Commissions"))
        self.tab_tips.clicked.connect(lambda: self._set_mode("Tips"))
        self.tab_pay.clicked.connect(lambda: self._set_mode("Payouts"))
        for b in (self.tab_sales, self.tab_trend, self.tab_comm, self.tab_tips, self.tab_pay):
            tabs.addWidget(b)
        tabs.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        card_lay.addLayout(tabs)

        root.addWidget(card)

        # ===================== Tabla 'Transacciones' =====================
        box = QFrame(); box.setObjectName("Card")
        box_l = QVBoxLayout(box); box_l.setContentsMargins(16, 12, 16, 12); box_l.setSpacing(8)
        box_l.addWidget(QLabel("Transacciones"))

        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Cliente", "Monto", "Pago", "Artista"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        box_l.addWidget(self.tbl)

        # Paginación
        pager = QHBoxLayout(); pager.setSpacing(8)
        pager.addWidget(QLabel("Por página:"))
        self.cbo_page = QComboBox(); self.cbo_page.addItems(["5", "10", "25"])
        self.cbo_page.setCurrentText(str(self.page_size))
        self.cbo_page.currentTextChanged.connect(self._on_page_size)
        pager.addWidget(self.cbo_page)
        pager.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.btn_prev = QPushButton("⟵"); self.btn_next = QPushButton("⟶")
        self.btn_prev.clicked.connect(self._prev_page); self.btn_next.clicked.connect(self._next_page)
        self.lbl_page = QLabel("Página 1/1")
        pager.addWidget(self.btn_prev); pager.addWidget(self.btn_next); pager.addWidget(self.lbl_page)

        box_l.addLayout(pager)
        root.addWidget(box, stretch=1)

        # ======= datos mock y primer render =======
        self._seed_mock()
        self._refresh()

    # ---------------- UI helpers ----------------
    def _chip(self, text: str, checked: bool=False) -> QPushButton:
        """Chip checkeable (estilízalo en QSS con QPushButton#Chip)."""
        b = QPushButton(text); b.setObjectName("Chip"); b.setCheckable(True); b.setChecked(checked)
        b.setMinimumHeight(32)
        return b

    def _icon_chip(self, icon_text: str, btn: QPushButton) -> QWidget:
        """Componente pequeño: icono + botón (visual)."""
        w = QWidget(); box = QHBoxLayout(w); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(6)
        ico = QLabel(icon_text); ico.setStyleSheet("font-size:16px;")
        box.addWidget(ico); box.addWidget(btn)
        return w

    # ---------------- seed / filtros / render ----------------
    def _seed_mock(self):
        """Más dummies repartidos en 2 meses para que se note la paginación/rangos."""
        d = QDate.currentDate()
        base = [
    (-2,  "Valeria Ríos",      1150.0, "Tarjeta",  "Dylan Bourjac"),
    (-4,  "Andrés Salgado",     780.0, "Efectivo", "Jesus Esquer"),
    (-5,  "Camila Herrera",    1650.0, "Tarjeta",  "Pablo Velasquez"),
    (-7,  "Rodrigo Ávila",      600.0, "Efectivo", "Alex Chavez"),
    (-9,  "Fernanda Núñez",    2100.0, "Tarjeta",  "Jenni Rivera"),
    (-11, "Santiago Varela",    920.0, "Efectivo", "Dylan Bourjac"),
    (-17, "Paola Medina",      1400.0, "Tarjeta",  "Jesus Esquer"),
    (-19, "Ricardo Pineda",     890.0, "Efectivo", "Pablo Velasquez"),
    (-21, "Lucía Carrillo",    1750.0, "Tarjeta",  "Alex Chavez"),
    (-22, "Miguel Andrade",     650.0, "Efectivo", "Jenni Rivera"),
    (-24, "Carolina Prieto",   1250.0, "Tarjeta",  "Dylan Bourjac"),
    (-26, "Héctor Lozano",      720.0, "Efectivo", "Jesus Esquer"),
    (-27, "Adriana Rentería",  1850.0, "Tarjeta",  "Pablo Velasquez"),
    (-29, "Noemí Duarte",      1320.0, "Tarjeta",  "Alex Chavez"),
    (-30, "Julián Castaño",     540.0, "Efectivo", "Jenni Rivera"),
    (-31, "Ximena Valdez",     1600.0, "Tarjeta",  "Dylan Bourjac"),
    (-33, "Mauricio Ochoa",     980.0, "Efectivo", "Jesus Esquer"),
    (-34, "Regina Campos",     2200.0, "Tarjeta",  "Pablo Velasquez"),
    (-3,  "Luis Alberto Cano",  870.0, "Efectivo", "Alex Chavez"),
    (-6,  "Arantxa Molina",    1900.0, "Tarjeta",  "Jenni Rivera"),
    (-8,  "Iván Rosales",       560.0, "Efectivo", "Dylan Bourjac"),
    (-10, "Diana Córdova",     1450.0, "Tarjeta",  "Jesus Esquer"),
    (-12, "Emilio Serrano",     990.0, "Efectivo", "Pablo Velasquez"),
    (-13, "Montserrat Lara",   1720.0, "Tarjeta",  "Alex Chavez"),
    (-14, "Brenda Quintero",    640.0, "Efectivo", "Jenni Rivera"),
    (-15, "Gustavo Ibarra",    1550.0, "Tarjeta",  "Dylan Bourjac"),
    (-16, "Melissa Paredes",    700.0, "Efectivo", "Jesus Esquer"),
    (-18, "Sofía Arce",        2000.0, "Tarjeta",  "Pablo Velasquez"),
    (-20, "Diego Zepeda",       590.0, "Efectivo", "Alex Chavez"),
    (-23, "Natalia Jurado",    1380.0, "Tarjeta",  "Jenni Rivera"),
    (-25, "Marcos Benítez",     860.0, "Efectivo", "Dylan Bourjac"),
    (-28, "Elena Porras",      1670.0, "Tarjeta",  "Jesus Esquer"),
    (-32, "Sebastián Rubio",    730.0, "Efectivo", "Pablo Velasquez"),
    (-35, "Teresa Aguilar",    1800.0, "Tarjeta",  "Alex Chavez"),
    (0,   "Fabiola Gálvez",    1200.0, "Tarjeta",  "Jenni Rivera"),
    (-1,  "Óscar Miranda",      650.0, "Efectivo", "Dylan Bourjac"),
    (-2,  "Mariela Cota",      1420.0, "Tarjeta",  "Jesus Esquer"),
    (-4,  "Cristian Beltrán",   780.0, "Efectivo", "Pablo Velasquez"),
    (-7,  "Alejandra Peña",    1950.0, "Tarjeta",  "Alex Chavez"),
    (-9,  "Kevin Lozoya",       520.0, "Efectivo", "Jenni Rivera")
]
        self._rows = [(d.addDays(delta), cli, monto, pay, art) for (delta, cli, monto, pay, art) in base]

    def _period_text(self) -> str:
        if self.period == "today":
            return "Hoy"
        if self.period == "week":
            return "Esta semana"
        if self.period == "month":
            return "Este mes"
        return f"{self.custom_from.toString('dd/MM/yyyy')} — {self.custom_to.toString('dd/MM/yyyy')}"

    def _date_range(self):
        """Devuelve (desde, hasta) como QDate inclusivos según period."""
        today = QDate.currentDate()
        if self.period == "today":
            return today, today
        if self.period == "week":
            # Lunes a domingo (ISO): weekday 1..7
            delta_to_monday = today.dayOfWeek() - 1
            start = today.addDays(-delta_to_monday)
            end = start.addDays(6)
            return start, end
        if self.period == "month":
            start = QDate(today.year(), today.month(), 1)
            end = QDate(today.year(), today.month(), start.daysInMonth())
            return start, end
        # custom
        return min(self.custom_from, self.custom_to), max(self.custom_from, self.custom_to)

    def _apply_filters(self):
        start, end = self._date_range()
        artist = self.filter_artist
        payment = self.filter_payment

        def keep(r):
            date_ok = (start <= r[0] <= end)
            artist_ok = (artist == "Todos" or r[4] == artist)
            pay_ok = (payment == "Todos" or r[3] == payment)
            return date_ok and artist_ok and pay_ok

        rows = [r for r in self._rows if keep(r)]
        rows.sort(key=lambda r: (r[0].toJulianDay(), r[1]), reverse=True)  # fecha desc, luego cliente
        return rows

    def _refresh(self):
        """Recalcula filtros, pagina la tabla y actualiza total."""
        rows = self._apply_filters()

        # paginación
        total_pages = max(1, (len(rows) + self.page_size - 1) // self.page_size)
        self.current_page = min(self.current_page, total_pages)
        start_idx = (self.current_page - 1) * self.page_size
        page = rows[start_idx:start_idx + self.page_size]

        # tabla
        self.tbl.setRowCount(0)
        for r in page:
            row = self.tbl.rowCount(); self.tbl.insertRow(row)
            self.tbl.setItem(row, 0, QTableWidgetItem(r[0].toString("dd/MM/yyyy")))
            self.tbl.setItem(row, 1, QTableWidgetItem(r[1]))
            self.tbl.setItem(row, 2, QTableWidgetItem(f"${r[2]:,.2f}"))
            self.tbl.setItem(row, 3, QTableWidgetItem(r[3]))
            self.tbl.setItem(row, 4, QTableWidgetItem(r[4]))

        # total de la tarjeta (solo 'Sales' suma; las otras pestañas son mock)
        total = sum(r[2] for r in rows) if self.mode == "Sales" else 0.0
        self.lbl_total.setText(f"${total:,.2f}")
        self.lbl_date.setText(self._period_text())

        # UI de paginación
        self.lbl_page.setText(f"Página {self.current_page}/{total_pages}")
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < total_pages)

        # Exclusividad de chips de periodo
        for b in (self.btn_today, self.btn_week, self.btn_month, self.btn_custom):
            b.setChecked(False)
        {"today": self.btn_today, "week": self.btn_week, "month": self.btn_month, "custom": self.btn_custom}[self.period].setChecked(True)

        # Exclusividad de chips de pestañas
        for b in (self.tab_sales, self.tab_trend, self.tab_comm, self.tab_tips, self.tab_pay):
            b.setChecked(False)
        {"Sales": self.tab_sales, "Trends": self.tab_trend, "Commissions": self.tab_comm,
         "Tips": self.tab_tips, "Payouts": self.tab_pay}[self.mode].setChecked(True)

    # ---------------- slots ----------------
    def _set_period(self, p: str):
        self.period = p
        self.custom_box.setVisible(p == "custom")
        self.current_page = 1
        self._refresh()

    def _on_custom_dates(self, _):
        self.custom_from = self.dt_from.date()
        self.custom_to = self.dt_to.date()
        self.current_page = 1
        self._refresh()

    def _on_filters(self, _):
        self.filter_artist = self.cbo_artist.currentText()
        self.filter_payment = self.cbo_payment.currentText()
        self.current_page = 1
        self._refresh()

    def _set_mode(self, m: str):
        self.mode = m
        self._refresh()

    def _on_page_size(self, _):
        try:
            self.page_size = int(self.cbo_page.currentText())
        except Exception:
            self.page_size = 10
        self.current_page = 1
        self._refresh()

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._refresh()

    def _next_page(self):
        self.current_page += 1
        self._refresh()
