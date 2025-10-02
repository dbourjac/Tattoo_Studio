from __future__ import annotations

from datetime import datetime, time
from collections import defaultdict

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QComboBox,
    QDateEdit, QTableWidget, QTableWidgetItem, QSizePolicy, QSpacerItem,
    QFileDialog, QMessageBox, QInputDialog, QLineEdit
)
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush

# --------- Gráfica (opcional si está disponible) ---------
try:
    from PyQt5.QtChart import (
        QChart, QChartView, QLineSeries, QCategoryAxis, QValueAxis
    )
    _HAVE_QCHART = True
except Exception:
    _HAVE_QCHART = False

# ---- BD ----
from data.db.session import SessionLocal
from data.models.transaction import Transaction
from data.models.session_tattoo import TattooSession
from data.models.client import Client
from data.models.artist import Artist as DBArtist

# ---- Permisos / sesión ----
from services.permissions import (
    assistant_needs_code, verify_master_code, elevate_for
)
from services.contracts import get_current_user


def _qcolor(c):
    """Acepta '#RRGGBB' o QColor y devuelve QColor."""
    return c if isinstance(c, QColor) else QColor(c)


# Paleta discreta para tema oscuro (líneas)
_LINE_COLORS = [
    "#6ea8fe", "#75b798", "#e685b5", "#ffda6a",
    "#a1c6ff", "#9ec5fe", "#8fd1b8", "#ffb8d2",
    "#ffd166", "#b197fc",
]

# ---------- Helpers de UI ----------

def _transparent(widget):
    """QLabels/controles sin fondo para respetar el tema."""
    try:
        ss = widget.styleSheet() or ""
        if "background" not in ss:
            widget.setStyleSheet(ss + (";" if ss else "") + "background: transparent;")
    except Exception:
        pass


def _chip(texto: str, checked: bool = False, on=None) -> QPushButton:
    """Botón tipo 'chip' (toggle) usado en filtros de periodo."""
    b = QPushButton(texto)
    b.setCheckable(True)
    b.setChecked(checked)
    b.setMinimumHeight(28)
    b.setObjectName("GhostSmall")
    if callable(on):
        b.clicked.connect(on)
    return b


def _icon_chip(prefix: str, btn: QPushButton) -> QPushButton:
    """Prefija un emoji/icono y ajusta tamaños."""
    if prefix:
        btn.setText(f"{prefix}  {btn.text()}")
    btn.setMinimumHeight(32)
    btn.setObjectName("GhostSmall")
    return btn


# ============================== Página ==============================

class ReportsPage(QWidget):
    """
    Reportes financieros con:
      - Periodos: Hoy / Semana / Mes / Rango personalizado (chips)
      - Filtros: Artista, Método de pago
      - Layout lado a lado: izquierda Transacciones (scroll infinito),
        derecha Gráfica + totales (más ancha)
      - Exportar CSV (Admin libre; Assistant con código; Artist no)
    """

    def __init__(self):
        super().__init__()

        # ---- Estado de filtros/UI ----
        self.period = "today"              # today | week | month | custom
        self.filter_artist = "Todos"
        self.filter_payment = "Todos"
        self.custom_from = QDate.currentDate()
        self.custom_to = QDate.currentDate()

        # Usuario actual
        self._user = get_current_user() or {"id": None, "role": "artist", "artist_id": None, "username": ""}
        self._role = self._user.get("role") or "artist"
        self._user_artist_id = self._user.get("artist_id")

        # Artistas para combos
        self._artists = self._fetch_artists()  # [(id, name)]
        self._artist_names = [n for _, n in self._artists]

        # ---------------- Layout raíz ----------------
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # Título
        title = QLabel("Reportes financieros")
        title.setObjectName("H1")
        _transparent(title)
        root.addWidget(title)

        # ---------------- Periodos + Export (misma barra) ----------------
        pr_wrap = QFrame(); pr_wrap.setObjectName("Toolbar")
        period_row = QHBoxLayout(pr_wrap); period_row.setSpacing(8); period_row.setContentsMargins(10, 8, 10, 8)

        self.btn_today  = _chip("Hoy", checked=True, on=lambda: self._set_period("today"))
        self.btn_week   = _chip("Esta semana", on=lambda: self._set_period("week"))
        self.btn_month  = _chip("Este mes", on=lambda: self._set_period("month"))
        self.btn_custom = _chip("Seleccionar fechas", on=lambda: self._set_period("custom"))

        for b in (self.btn_today, self.btn_week, self.btn_month, self.btn_custom):
            period_row.addWidget(b)

        # Rango personalizado
        self.custom_box = QFrame(); cb = QHBoxLayout(self.custom_box)
        cb.setSpacing(6); cb.setContentsMargins(0, 0, 0, 0)
        lde = QLabel("De:"); _transparent(lde); cb.addWidget(lde)
        self.dt_from = QDateEdit(QDate.currentDate()); self.dt_from.setCalendarPopup(True); cb.addWidget(self.dt_from)
        la = QLabel("a:"); _transparent(la); cb.addWidget(la)
        self.dt_to = QDateEdit(QDate.currentDate()); self.dt_to.setCalendarPopup(True); cb.addWidget(self.dt_to)
        self.custom_box.setVisible(False)
        period_row.addWidget(self.custom_box)

        self.dt_from.dateChanged.connect(self._on_custom_dates)
        self.dt_to.dateChanged.connect(self._on_custom_dates)

        # Espaciador y Export a la derecha (misma barra)
        period_row.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.btn_export = QPushButton("Exportar CSV")
        self.btn_export.clicked.connect(self._export_csv)
        period_row.addWidget(_icon_chip("📁", self.btn_export))
        root.addWidget(pr_wrap)

        # Habilitar export conforme permisos
        self._refresh_export_enabled()

        # ---------------- Filtros ----------------
        flt_wrap = QFrame(); flt_wrap.setObjectName("Toolbar")
        filters = QHBoxLayout(flt_wrap); filters.setSpacing(8); filters.setContentsMargins(10, 8, 10, 8)

        la = QLabel("Artista:"); _transparent(la); filters.addWidget(la)
        self.cbo_artist = QComboBox()
        self.cbo_artist.addItems(["Todos"] + self._artist_names)
        self.cbo_artist.currentTextChanged.connect(self._on_filters)
        filters.addWidget(self.cbo_artist)

        filters.addSpacing(12)
        lp = QLabel("Tipo de pago:"); _transparent(lp); filters.addWidget(lp)
        self.cbo_payment = QComboBox()
        self.cbo_payment.addItems(["Todos", "Efectivo", "Tarjeta", "Transferencia"])
        self.cbo_payment.currentTextChanged.connect(self._on_filters)
        filters.addWidget(self.cbo_payment)

        filters.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        root.addWidget(flt_wrap)

        # Si el usuario es ARTIST, forzar su filtro y bloquear combo
        if self._role == "artist" and self._user_artist_id:
            own_name = self._artist_name_by_id(self._user_artist_id)
            if own_name:
                self.filter_artist = own_name
                self.cbo_artist.setCurrentText(own_name)
                self.cbo_artist.setEnabled(False)

        # =================== LADO IZQ (Tabla) + LADO DER (KPI/Gráfica) ===================
        side = QHBoxLayout(); side.setSpacing(12)

        # -------- Izquierda: Transacciones --------
        left_card = QFrame(); left_card.setObjectName("Card")
        left = QVBoxLayout(left_card); left.setContentsMargins(16, 12, 16, 12); left.setSpacing(8)

        lbl_tx = QLabel("Transacciones"); _transparent(lbl_tx); left.addWidget(lbl_tx)

        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Cliente", "Monto", "Pago", "Artista"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        left.addWidget(self.tbl, 1)

        # -------- Derecha: KPI + Gráfica (más ancha) --------
        right_card = QFrame(); right_card.setObjectName("Card")
        right = QVBoxLayout(right_card); right.setContentsMargins(16, 12, 16, 12); right.setSpacing(8)

        hdr = QHBoxLayout(); hdr.setSpacing(8)
        htitle = QLabel("Ventas"); htitle.setStyleSheet("font-weight:700;"); _transparent(htitle)
        self.lbl_date = QLabel(self._period_text()); _transparent(self.lbl_date)
        self.lbl_total = QLabel("$0.00"); self.lbl_total.setStyleSheet("font-weight:800;"); _transparent(self.lbl_total)
        ltot = QLabel("Total:"); _transparent(ltot)

        hdr.addWidget(htitle)
        hdr.addSpacing(12)
        hdr.addWidget(self.lbl_date)
        hdr.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        hdr.addWidget(ltot); hdr.addWidget(self.lbl_total)
        right.addLayout(hdr)

        # Gráfica
        self.chart_box = QFrame()
        if _HAVE_QCHART:
            self.chart = QChart()
            self.chart.setBackgroundVisible(False)
            self.chart.legend().setVisible(True)
            self.chart.legend().setAlignment(Qt.AlignLeft)
            # Legibilidad en tema oscuro
            self.chart.legend().setLabelBrush(QBrush(QColor("#DADDE3")))
            self.chart_view = QChartView(self.chart)
            self.chart_view.setRenderHint(QPainter.Antialiasing)
            cbl = QVBoxLayout(self.chart_box)
            cbl.setContentsMargins(0, 0, 0, 0); cbl.addWidget(self.chart_view)
        else:
            cbl = QVBoxLayout(self.chart_box)
            cbl.setContentsMargins(0, 0, 0, 0)
            nochart = QLabel("La gráfica no está disponible en este entorno.")
            nochart.setStyleSheet("opacity:0.7;")
            nochart.setAlignment(Qt.AlignCenter)
            cbl.addWidget(nochart)
        right.addWidget(self.chart_box, 1)

        # Añadir a layout principal lado a lado (gráfica más ancha)
        side.addWidget(left_card, 1)   # Transacciones
        side.addWidget(right_card, 2)  # Gráfica
        root.addLayout(side, 1)

        # Primera carga
        self._refresh()

    # ---------------- Helpers de datos/consulta ----------------
    def _fetch_artists(self):
        with SessionLocal() as db:
            rows = db.query(DBArtist.id, DBArtist.name).order_by(DBArtist.name.asc()).all()
        return [(r[0], r[1]) for r in rows]

    def _artist_name_by_id(self, a_id):
        for i, n in self._artists:
            if i == a_id:
                return n
        return None

    def _artist_id_by_name(self, name):
        for i, n in self._artists:
            if n == name:
                return i
        return None

    def _period_text(self) -> str:
        if self.period == "today":
            return "Hoy"
        if self.period == "week":
            return "Esta semana"
        if self.period == "month":
            return "Este mes"
        return f"{self.custom_from.toString('dd/MM/yyyy')} — {self.custom_to.toString('dd/MM/yyyy')}"

    def _date_range(self):
        today = QDate.currentDate()
        if self.period == "today":
            return today, today
        if self.period == "week":
            start = today.addDays(-(today.dayOfWeek() - 1))
            end = start.addDays(6)
            return start, end
        if self.period == "month":
            start = QDate(today.year(), today.month(), 1)
            end = QDate(today.year(), today.month(), start.daysInMonth())
            return start, end
        return min(self.custom_from, self.custom_to), max(self.custom_from, self.custom_to)

    def _query_rows(self):
        """Regresa tuplas (QDate, cliente, monto, método, artista) según filtros/periodo/permisos."""
        q_from, q_to = self._date_range()
        start_dt = datetime.combine(q_from.toPyDate(), time(0, 0, 0))
        end_dt = datetime.combine(q_to.toPyDate(), time(23, 59, 59))

        with SessionLocal() as db:
            q = (
                db.query(
                    Transaction.date, Client.name, Transaction.amount,
                    Transaction.method, DBArtist.name, Transaction.artist_id
                )
                .join(TattooSession, TattooSession.id == Transaction.session_id)
                .join(Client, Client.id == TattooSession.client_id)
                .join(DBArtist, DBArtist.id == Transaction.artist_id)
                .filter(Transaction.date >= start_dt, Transaction.date <= end_dt)
            )

            # Permiso: si es ARTIST, solo lo propio
            if self._role == "artist" and self._user_artist_id:
                q = q.filter(Transaction.artist_id == self._user_artist_id)
            else:
                # Filtro combo artista (por nombre) si aplica
                if self.filter_artist != "Todos":
                    a_id = self._artist_id_by_name(self.filter_artist)
                    if a_id:
                        q = q.filter(Transaction.artist_id == a_id)

            # Filtro método de pago
            if self.filter_payment != "Todos":
                q = q.filter(Transaction.method == self.filter_payment)

            q = q.order_by(Transaction.date.asc(), Client.name.asc())
            rows = q.all()

        out = []
        for dt, cli, amount, method, artist_name, _artist_id in rows:
            qd = QDate(dt.year, dt.month, dt.day)
            out.append((qd, cli or "—", float(amount or 0.0), method or "—", artist_name or "—"))
        return out

    # ---------------- Render principal ----------------
    def _refresh(self):
        rows = self._query_rows()

        # Tabla (SIN paginación: todas las transacciones)
        self.tbl.setRowCount(0)
        for r in rows:
            row = self.tbl.rowCount(); self.tbl.insertRow(row)
            self.tbl.setItem(row, 0, QTableWidgetItem(r[0].toString("dd/MM/yyyy")))
            self.tbl.setItem(row, 1, QTableWidgetItem(r[1]))
            self.tbl.setItem(row, 2, QTableWidgetItem(f"${r[2]:,.2f}"))
            self.tbl.setItem(row, 3, QTableWidgetItem(r[3]))
            self.tbl.setItem(row, 4, QTableWidgetItem(r[4]))

        # Total
        total = sum(r[2] for r in rows)
        self.lbl_total.setText(f"${total:,.2f}")
        self.lbl_date.setText(self._period_text())

        # Chips de periodo
        for b in (self.btn_today, self.btn_week, self.btn_month, self.btn_custom):
            b.setChecked(False)
        {"today": self.btn_today, "week": self.btn_week, "month": self.btn_month, "custom": self.btn_custom}[self.period].setChecked(True)

        # Gráfica de líneas (minimal)
        self._render_chart_lines(rows)

        # Export habilitado/visible según permisos
        self._refresh_export_enabled()

    # ---------------- Gráfica de líneas por artista ----------------
    def _render_chart_lines(self, rows):
        if not _HAVE_QCHART:
            return

        # Limpiar
        self.chart.removeAllSeries()
        for ax in list(self.chart.axes()):
            self.chart.removeAxis(ax)
        self.chart.setTitle("")

        if not rows:
            return

        # Armar categorías de días en el rango seleccionado
        q_from, q_to = self._date_range()
        n_days = q_from.daysTo(q_to) + 1
        days = [q_from.addDays(i) for i in range(n_days)]
        categories = [d.toString("dd/MM") for d in days]
        x_index = {d.toString("yyyy-MM-dd"): i for i, d in enumerate(days)}

        # Totales por artista y por día
        by_artist_day = defaultdict(lambda: defaultdict(float))
        for qd, _cli, amount, _pay, artist in rows:
            key = qd.toString("yyyy-MM-dd")
            if key in x_index:
                by_artist_day[artist][key] += amount

        # Crear series
        series_list = []
        for s_idx, (artist, per_day) in enumerate(sorted(by_artist_day.items())):
            line = QLineSeries()
            line.setName(artist)
            pen = QPen(_qcolor(_LINE_COLORS[s_idx % len(_LINE_COLORS)]))
            pen.setWidth(2)
            line.setPen(pen)
            line.setPointsVisible(True)

            for d in days:
                k = d.toString("yyyy-MM-dd")
                x = x_index[k]
                y = per_day.get(k, 0.0)
                line.append(float(x), float(y))

            series_list.append(line)
            self.chart.addSeries(line)

        # Eje X categórico
        axisX = QCategoryAxis()
        for i, label in enumerate(categories):
            axisX.append(label, float(i))
        axisX.setLabelsBrush(QBrush(QColor("#DADDE3")))
        # Minimalismo: sin grid vertical, etiquetas un poco inclinadas si hay muchos días
        axisX.setGridLineVisible(False)
        if len(categories) > 14:
            axisX.setLabelsAngle(-45)

        # Eje Y con formato de moneda
        axisY = QValueAxis()
        axisY.setLabelFormat("$%.0f")
        axisY.applyNiceNumbers()
        axisY.setLabelsBrush(QBrush(QColor("#DADDE3")))
        # Minimalismo: grid suave
        axisY.setMinorGridLineVisible(False)
        axisY.setGridLineColor(QColor(255, 255, 255, 30))

        # Ejes
        self.chart.addAxis(axisX, Qt.AlignBottom)
        self.chart.addAxis(axisY, Qt.AlignLeft)
        for s in series_list:
            s.attachAxis(axisX)
            s.attachAxis(axisY)

    # ---------------- Interacciones ----------------
    def _set_period(self, p: str):
        self.period = p
        self.custom_box.setVisible(p == "custom")
        self._refresh()

    def _on_custom_dates(self, _):
        self.custom_from = self.dt_from.date()
        self.custom_to = self.dt_to.date()
        self._refresh()

    def _on_filters(self, _):
        self.filter_artist = self.cbo_artist.currentText()
        self.filter_payment = self.cbo_payment.currentText()
        self._refresh()

    # ---------------- Exportar ----------------
    def _refresh_export_enabled(self):
        # Admin siempre; Artist nunca; Assistant sólo si puede elevar permisos
        if self._role == "artist":
            self.btn_export.setEnabled(False)
            return
        if self._role == "admin":
            self.btn_export.setEnabled(True)
            return
        # assistant -> habilita botón, validamos en el click
        if self._role == "assistant":
            self.btn_export.setEnabled(True)
            return

    def _ensure_assistant_elevation(self) -> bool:
        """Para assistant: pide código maestro y eleva 5 min."""
        if self._role != "assistant":
            return True
        if not assistant_needs_code("reports", "export"):
            return True

        # Pedir código
        code, ok = QInputDialog.getText(self, "Código maestro", "Ingresa el código para exportar:", echo=QLineEdit.Password)
        if not ok or not code:
            return False

        # Verificar con BD
        with SessionLocal() as db:
            if not verify_master_code(code, db):
                QMessageBox.warning(self, "Permiso denegado", "Código incorrecto.")
                return False

        # Elevar 5 minutos
        elevate_for(self._user.get("id"), minutes=5)
        return True

    def _export_csv(self):
        # Permisos: admin libre; assistant con elevación; artist nunca
        if self._role == "artist":
            QMessageBox.information(self, "Sin permiso", "Tu rol no puede exportar reportes.")
            return

        if self._role == "assistant" and not self._ensure_assistant_elevation():
            return

        # Recolectar datos completos
        rows = self._query_rows()
        if not rows:
            QMessageBox.information(self, "Exportar", "No hay datos para exportar.")
            return

        path, ok = QFileDialog.getSaveFileName(self, "Guardar CSV", "reportes.csv", "CSV (*.csv)")
        if not ok or not path:
            return

        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Fecha", "Cliente", "Monto", "Pago", "Artista"])
                for qd, cli, amt, pay, art in rows:
                    w.writerow([qd.toString("yyyy-MM-dd"), cli, f"{amt:.2f}", pay, art])
            QMessageBox.information(self, "Exportar", "Archivo CSV exportado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error al exportar", f"No se pudo exportar el CSV.\n\n{e}")
