from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QComboBox, QDateEdit, QTableWidget, QTableWidgetItem,
    QSizePolicy, QSpacerItem
)

# === NUEVO: imports para leer datos reales desde la BD ===
from datetime import datetime, time
from data.db.session import SessionLocal
from data.models.transaction import Transaction
from data.models.session_tattoo import TattooSession
from data.models.client import Client
from data.models.artist import Artist as DBArtist


class ReportsPage(QWidget):
    """
    Reportes financieros (con BD):
      - Toolbar superior con Exportar (deshabilitado)
      - Rangos rápidos: Hoy / Semana / Mes / Custom (con date edits)
      - Filtros: Artista (desde BD), Tipo de pago
      - Tarjeta con chips (Ventas/Tendencias/Comisiones/Propinas/Liquidaciones) + Total
      - Tabla 'Transacciones' con paginación
    """

    # ---- CLAVES INTERNAS ESTABLES (no cambian aunque traduzcas la UI) ----
    MODES = {
        "sales": "Ventas",
        "trends": "Tendencias",
        "commissions": "Comisiones",
        "tips": "Propinas",
        "payouts": "Liquidaciones",
    }

    def __init__(self):
        super().__init__()

        # -------- estado/UI --------
        self.period = "today"          # today | week | month | custom
        self.mode = "sales"            # CLAVES internas: 'sales' | 'trends' | 'commissions' | 'tips' | 'payouts'
        self.page_size = 10
        self.current_page = 1

        self.filter_artist = "Todos"
        self.filter_payment = "Todos"
        self.custom_from = QDate.currentDate()
        self.custom_to = QDate.currentDate()

        # Data interna de la tabla (cada r = (QDate, cliente, monto, pago, artista))
        self._rows = []

        # Pre-cargar nombres de artistas desde BD para el combo
        self._artist_names = self._fetch_artist_names()

        # -------- layout raíz --------
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # Título
        title = QLabel("Reportes financieros")
        title.setObjectName("H1")
        self._transparent(title)  # <-- fondo transparente
        root.addWidget(title)

        # ===================== Toolbar superior =====================
        tb_wrap = QFrame(); tb_wrap.setObjectName("Toolbar")
        toolbar = QHBoxLayout(tb_wrap); toolbar.setSpacing(8); toolbar.setContentsMargins(10, 8, 10, 8)

        # (placeholder) Exportar CSV
        self.btn_export = QPushButton("Exportar CSV")
        self.btn_export.setEnabled(False)
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

        lbl_de = QLabel("De:"); self._transparent(lbl_de)
        cb.addWidget(lbl_de)
        self.dt_from = QDateEdit(QDate.currentDate()); self.dt_from.setCalendarPopup(True)
        cb.addWidget(self.dt_from)

        lbl_a = QLabel("a:"); self._transparent(lbl_a)
        cb.addWidget(lbl_a)
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

        lbl_artist = QLabel("Artista:"); self._transparent(lbl_artist)
        filters.addWidget(lbl_artist)

        self.cbo_artist = QComboBox()
        # Poblar desde BD: "Todos" + nombres
        self.cbo_artist.addItems(["Todos"] + self._artist_names)
        self.cbo_artist.currentTextChanged.connect(self._on_filters)
        filters.addWidget(self.cbo_artist)

        filters.addSpacing(12)
        lbl_pay = QLabel("Tipo de pago:"); self._transparent(lbl_pay)
        filters.addWidget(lbl_pay)

        self.cbo_payment = QComboBox()
        self.cbo_payment.addItems(["Todos", "Efectivo", "Tarjeta", "Transferencia"])
        self.cbo_payment.currentTextChanged.connect(self._on_filters)
        filters.addWidget(self.cbo_payment)

        filters.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        root.addWidget(flt_wrap)

        # ===================== Tarjeta 'Ventas' =====================
        card = QFrame(); card.setObjectName("Card")
        card_lay = QVBoxLayout(card); card_lay.setContentsMargins(16, 12, 16, 12); card_lay.setSpacing(8)

        # Header de la tarjeta
        hdr = QHBoxLayout(); hdr.setSpacing(8)
        hdr_title = QLabel(self.MODES[self.mode]); hdr_title.setStyleSheet("font-weight:700;")
        self._transparent(hdr_title)

        self.lbl_date = QLabel(self._period_text()); self._transparent(self.lbl_date)
        self.lbl_total = QLabel(""); self.lbl_total.setStyleSheet("font-weight:800;"); self._transparent(self.lbl_total)
        lbl_total_cap = QLabel("Total:"); self._transparent(lbl_total_cap)

        hdr.addWidget(hdr_title); hdr.addSpacing(12); hdr.addWidget(self.lbl_date)
        hdr.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        hdr.addWidget(lbl_total_cap); hdr.addWidget(self.lbl_total)
        card_lay.addLayout(hdr)

        # Chips tipo pestañas (botones checkeables)
        tabs = QHBoxLayout(); tabs.setSpacing(6)
        self.tab_buttons = {
            "sales": self._chip(self.MODES["sales"], checked=True),
            "trends": self._chip(self.MODES["trends"]),
            "commissions": self._chip(self.MODES["commissions"]),
            "tips": self._chip(self.MODES["tips"]),
            "payouts": self._chip(self.MODES["payouts"]),
        }
        self.tab_buttons["sales"].clicked.connect(lambda: self._set_mode("sales"))
        self.tab_buttons["trends"].clicked.connect(lambda: self._set_mode("trends"))
        self.tab_buttons["commissions"].clicked.connect(lambda: self._set_mode("commissions"))
        self.tab_buttons["tips"].clicked.connect(lambda: self._set_mode("tips"))
        self.tab_buttons["payouts"].clicked.connect(lambda: self._set_mode("payouts"))

        for b in self.tab_buttons.values():
            tabs.addWidget(b)
        tabs.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        card_lay.addLayout(tabs)

        root.addWidget(card)

        # ===================== Tabla 'Transacciones' =====================
        box = QFrame(); box.setObjectName("Card")
        box_l = QVBoxLayout(box); box_l.setContentsMargins(16, 12, 16, 12); box_l.setSpacing(8)

        lbl_tx = QLabel("Transacciones"); self._transparent(lbl_tx)
        box_l.addWidget(lbl_tx)

        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Cliente", "Monto", "Pago", "Artista"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        box_l.addWidget(self.tbl)

        # Paginación
        pager = QHBoxLayout(); pager.setSpacing(8)
        lbl_pp = QLabel("Por página:"); self._transparent(lbl_pp)
        pager.addWidget(lbl_pp)
        self.cbo_page = QComboBox(); self.cbo_page.addItems(["5", "10", "25"])
        self.cbo_page.setCurrentText(str(self.page_size))
        self.cbo_page.currentTextChanged.connect(self._on_page_size)
        pager.addWidget(self.cbo_page)
        pager.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.btn_prev = QPushButton("⟵"); self.btn_next = QPushButton("⟶")
        self.btn_prev.clicked.connect(self._prev_page); self.btn_next.clicked.connect(self._next_page)
        self.lbl_page = QLabel("Página 1/1"); self._transparent(self.lbl_page)
        pager.addWidget(self.btn_prev); pager.addWidget(self.btn_next); pager.addWidget(self.lbl_page)

        box_l.addLayout(pager)
        root.addWidget(box, stretch=1)

        # ======= primer render (YA SIN MOCKS) =======
        self._rows = self._query_rows()   # lee desde BD según filtros/rango actuales
        self._refresh()

    # ---------------- UI helpers ----------------
    def _transparent(self, *widgets):
        """Fondo completamente transparente para etiquetas (texto)."""
        for w in widgets:
            w.setAttribute(Qt.WA_StyledBackground, False)
            w.setStyleSheet((w.styleSheet() or "") + ";\nbackground: transparent;")

    def _chip(self, text: str, checked: bool=False) -> QPushButton:
        """Chip checkeable (estilízalo en QSS con QPushButton#Chip)."""
        b = QPushButton(text); b.setObjectName("Chip"); b.setCheckable(True); b.setChecked(checked)
        b.setMinimumHeight(32)
        return b

    def _icon_chip(self, icon_text: str, btn: QPushButton) -> QWidget:
        """Componente pequeño: icono + botón (visual)."""
        w = QWidget(); box = QHBoxLayout(w); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(6)
        ico = QLabel(icon_text); ico.setStyleSheet("font-size:16px;"); self._transparent(ico)
        box.addWidget(ico); box.addWidget(btn)
        return w

    # ---------------- Carga de datos (BD) ----------------
    def _fetch_artist_names(self):
        """Regresa la lista de nombres de artistas (ordenados) para el combo."""
        with SessionLocal() as db:
            rows = db.query(DBArtist.name).order_by(DBArtist.name.asc()).all()
        return [r[0] for r in rows]

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

    def _query_rows(self):
        """
        Lee transacciones reales de la BD aplicando los filtros/rango actuales.
        Devuelve lista de tuplas: (QDate, cliente, monto, pago, artista) ya ordenada por fecha desc.
        """
        q_from, q_to = self._date_range()

        # Convertir QDate → datetime (inicio/fin del día)
        start_dt = datetime.combine(q_from.toPyDate(), time(0, 0, 0))
        end_dt   = datetime.combine(q_to.toPyDate(),   time(23, 59, 59))

        with SessionLocal() as db:
            q = (
                db.query(
                    Transaction.date,     # datetime
                    Client.name,          # cliente
                    Transaction.amount,   # monto
                    Transaction.method,   # pago
                    DBArtist.name,        # artista
                )
                .join(TattooSession, TattooSession.id == Transaction.session_id)
                .join(Client, Client.id == TattooSession.client_id)
                .join(DBArtist, DBArtist.id == Transaction.artist_id)
                .filter(Transaction.date >= start_dt, Transaction.date <= end_dt)
            )

            # Filtro de artista por nombre (si no es "Todos")
            if self.filter_artist != "Todos":
                q = q.filter(DBArtist.name == self.filter_artist)

            # Filtro de método de pago (si no es "Todos")
            if self.filter_payment != "Todos":
                q = q.filter(Transaction.method == self.filter_payment)

            # Orden por fecha desc, luego cliente (como antes)
            q = q.order_by(Transaction.date.desc(), Client.name.asc())
            rows = q.all()

        # Adaptar a formato de tabla: (QDate, str, float, str, str)
        out = []
        for dt, cli, amount, method, artist in rows:
            qd = QDate(dt.year, dt.month, dt.day)
            out.append((qd, cli, float(amount or 0.0), method, artist))
        return out

    def _apply_filters(self):
        """
        Antes filtraba una lista mock. Ahora delega la ‘consulta’ a la BD
        aplicando filtros/rango, y solo devuelve la lista ordenada.
        """
        rows = self._query_rows()
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
            self.tbl.setItem(row, 0, QTableWidgetItem(r[0].toString("dd/MM/yyyy")))  # fecha (QDate)
            self.tbl.setItem(row, 1, QTableWidgetItem(r[1]))                          # cliente
            self.tbl.setItem(row, 2, QTableWidgetItem(f"${r[2]:,.2f}"))               # monto
            self.tbl.setItem(row, 3, QTableWidgetItem(r[3]))                          # método
            self.tbl.setItem(row, 4, QTableWidgetItem(r[4]))                          # artista

        # total según modo (por ahora solo 'sales' suma)
        total = sum(r[2] for r in rows) if self.mode == "sales" else 0.0
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

        # Exclusividad de pestañas por CLAVE, no por texto (evita crash al traducir)
        for key, btn in self.tab_buttons.items():
            btn.setChecked(key == self.mode)

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

    def _set_mode(self, key: str):
        """key es una CLAVE interna ('sales', 'trends', ...), no el texto traducido."""
        if key not in self.MODES:
            return
        self.mode = key
        self.current_page = 1
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
