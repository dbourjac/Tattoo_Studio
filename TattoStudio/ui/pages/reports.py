from __future__ import annotations

from datetime import datetime, time
from collections import defaultdict

from PyQt5.QtCore import Qt, QDate, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QComboBox,
    QDateEdit, QTableWidget, QTableWidgetItem, QSizePolicy, QSpacerItem,
    QFileDialog, QMessageBox, QInputDialog, QLineEdit
)
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush

# --------- Gráfica (si está disponible) ---------
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
from services.permissions import assistant_needs_code, verify_master_code, elevate_for
from services.contracts import get_current_user

# ---- Helpers centralizados (common.py) ----
from ui.pages.common import load_artist_colors, fallback_color_for


# ================= utilidades visuales =================

def _qcolor(c):
    return c if isinstance(c, QColor) else QColor(c)

def _transparent(widget):
    """Aplica fondo transparente sin romper QSS actual."""
    try:
        ss = widget.styleSheet() or ""
        if "background" not in ss and "background-color" not in ss:
            widget.setStyleSheet(ss + (";" if ss else "") + "background: transparent;")
    except Exception:
        pass


# ============================== Página ==============================

class ReportsPage(QWidget):
    """
    Reportes financieros con:
      - Filtros por periodo, tatuador, método de pago
      - Tabla + Gráfica (colores = JSON por ID/nombre, fallback paleta)
      - Export CSV (permisos)
      - Auto-refresh (transacciones, artistas y JSON de colores)
    """

    def __init__(self):
        super().__init__()

        # ---- Estado global ----
        self.period = "today"              # today | week | month | custom
        self.filter_artist = "Todos"
        self.filter_payment = "Todos"
        self.custom_from = QDate.currentDate()
        self.custom_to = QDate.currentDate()

        # Usuario actual
        self._user = get_current_user() or {"id": None, "role": "artist", "artist_id": None, "username": ""}
        self._role = self._user.get("role") or "artist"
        self._user_artist_id = self._user.get("artist_id")

        # Artistas (activos) para combos y series
        self._artists: list[tuple[int, str]] = self._fetch_artists(active_only=True)
        self._artist_names = [n for _, n in self._artists]

        # Colores desde JSON (centralizado en common.py)
        self._colors_json: dict[str, str] = load_artist_colors()

        # ---------------- Layout raíz ----------------
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # Título
        title = QLabel("Reportes financieros")
        title.setObjectName("H1")
        _transparent(title)
        root.addWidget(title)

        # ---------------- Periodos + Export ----------------
        pr_wrap = QFrame(); pr_wrap.setObjectName("Toolbar")
        period_row = QHBoxLayout(pr_wrap); period_row.setSpacing(8); period_row.setContentsMargins(10, 8, 10, 8)

        self.btn_today  = self._chip("Hoy", checked=True, on=lambda: self._set_period("today"))
        self.btn_week   = self._chip("Esta semana", on=lambda: self._set_period("week"))
        self.btn_month  = self._chip("Este mes", on=lambda: self._set_period("month"))
        self.btn_custom = self._chip("Seleccionar fechas", on=lambda: self._set_period("custom"))
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

        period_row.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.btn_export = QPushButton("Exportar CSV")
        self.btn_export.clicked.connect(self._export_csv)
        period_row.addWidget(self._icon_chip("📁", self.btn_export))
        root.addWidget(pr_wrap)

        self._refresh_export_enabled()

        # ---------------- Filtros ----------------
        flt_wrap = QFrame(); flt_wrap.setObjectName("Toolbar")
        filters = QHBoxLayout(flt_wrap); filters.setSpacing(8); filters.setContentsMargins(10, 8, 10, 8)

        lt = QLabel("Tatuador:"); _transparent(lt); filters.addWidget(lt)
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

        # =================== LADO IZQ (Tabla) + LADO DER (Gráfica) ===================
        side = QHBoxLayout(); side.setSpacing(12)

        # -------- Izquierda: Transacciones --------
        left_card = QFrame(); left_card.setObjectName("Card")
        left = QVBoxLayout(left_card); left.setContentsMargins(16, 12, 16, 12); left.setSpacing(8)

        lbl_tx = QLabel("Transacciones"); _transparent(lbl_tx); left.addWidget(lbl_tx)

        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Cliente", "Monto", "Pago", "Tatuador"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        self.tbl.setSelectionBehavior(self.tbl.SelectRows)
        left.addWidget(self.tbl, 1)

        # -------- Derecha: KPI + Gráfica --------
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
            self.chart.legend().setAlignment(Qt.AlignBottom)  # leyenda abajo, horizontal
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
            _transparent(nochart)
            cbl.addWidget(nochart)
        right.addWidget(self.chart_box, 1)

        # Añadir a layout principal
        side.addWidget(left_card, 1)   # Transacciones
        side.addWidget(right_card, 2)  # Gráfica
        root.addLayout(side, 1)

        # Timers de auto-refresh
        self._data_timer = QTimer(self)
        self._data_timer.setInterval(6000)         # cada 6s: reconsulta y repinta
        self._data_timer.timeout.connect(self._tick_auto_refresh)
        self._data_timer.start()

        self._colors_timer = QTimer(self)
        self._colors_timer.setInterval(2500)       # detecta cambios en JSON de colores
        self._colors_timer.timeout.connect(self._reload_colors_if_changed)
        self._colors_timer.start()

        # Primera carga
        self._refresh()

    # ---------------- Helpers de UI ----------------

    def _chip(self, texto: str, checked: bool = False, on=None) -> QPushButton:
        b = QPushButton(texto)
        b.setCheckable(True)
        b.setChecked(checked)
        b.setMinimumHeight(28)
        b.setObjectName("GhostSmall")
        if callable(on):
            b.clicked.connect(on)
        return b

    def _icon_chip(self, prefix: str, btn: QPushButton) -> QPushButton:
        if prefix:
            btn.setText(f"{prefix}  {btn.text()}")
        btn.setMinimumHeight(32)
        btn.setObjectName("GhostSmall")
        return btn

    # ---------------- Helpers de datos/consulta ----------------

    def _fetch_artists(self, active_only: bool = True):
        """[(id, name)] desde la BD (por defecto solo activos)."""
        with SessionLocal() as db:
            q = db.query(DBArtist.id, DBArtist.name)
            if active_only:
                q = q.filter(DBArtist.active == True)  # noqa: E712
            rows = q.order_by(DBArtist.name.asc()).all()
        return [(int(r[0]), str(r[1])) for r in rows]

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

    def _artist_color(self, artist_id: int, artist_name: str, idx_fallback: int) -> str:
        """
        Color del artista priorizando JSON (common.load_artist_colors):
          1) JSON por id (str)
          2) JSON por nombre
          3) fallback_color_for(idx)
        """
        c = self._colors_json.get(str(artist_id))
        if c:
            return c
        c = self._colors_json.get(artist_name)
        if c:
            return c
        return fallback_color_for(idx_fallback)

    def _period_text(self) -> str:
        return {
            "today": "Hoy",
            "week": "Esta semana",
            "month": "Este mes",
        }.get(self.period, f"{self.custom_from.toString('dd/MM/yyyy')} — {self.custom_to.toString('dd/MM/yyyy')}")

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
        """Tuplas (QDate, cliente, monto, método, artista_name, artista_id)."""
        q_from, q_to = self._date_range()
        start_dt = datetime.combine(q_from.toPyDate(), time(0, 0, 0))
        end_dt = datetime.combine(q_to.toPyDate(), time(23, 59, 59))

        with SessionLocal() as db:
            q = (
                db.query(
                    Transaction.date,
                    Client.name,
                    Transaction.amount,
                    Transaction.method,
                    DBArtist.name,
                    Transaction.artist_id,
                )
                .join(TattooSession, TattooSession.id == Transaction.session_id)
                .join(Client, Client.id == TattooSession.client_id)
                .join(DBArtist, DBArtist.id == Transaction.artist_id)
                .filter(Transaction.date >= start_dt, Transaction.date <= end_dt)
            )

            # ARTIST -> sólo lo propio
            if self._role == "artist" and self._user_artist_id:
                q = q.filter(Transaction.artist_id == self._user_artist_id)
            else:
                # filtro por tatuador (combo)
                if self.filter_artist != "Todos":
                    a_id = self._artist_id_by_name(self.filter_artist)
                    if a_id is not None:
                        q = q.filter(Transaction.artist_id == a_id)

            # filtro por tipo de pago
            if self.filter_payment != "Todos":
                q = q.filter(Transaction.method == self.filter_payment)

            q = q.order_by(Transaction.date.asc(), Client.name.asc())
            rows = q.all()

        out = []
        for dt, cli, amount, method, artist_name, artist_id in rows:
            qd = QDate(dt.year, dt.month, dt.day)
            out.append((qd, cli or "—", float(amount or 0.0), method or "—", artist_name or "—", int(artist_id or 0)))
        return out

    # ---------------- Render principal ----------------

    def _refresh(self):
        rows = self._query_rows()

        # Tabla
        self.tbl.setRowCount(0)
        for qd, cli, amt, pay, art_name, _art_id in rows:
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(qd.toString("dd/MM/yyyy")))
            self.tbl.setItem(r, 1, QTableWidgetItem(cli))
            self.tbl.setItem(r, 2, QTableWidgetItem(f"${amt:,.2f}"))
            self.tbl.setItem(r, 3, QTableWidgetItem(pay))
            self.tbl.setItem(r, 4, QTableWidgetItem(art_name))

        # Total y periodo
        total = sum(r[2] for r in rows)
        self.lbl_total.setText(f"${total:,.2f}")
        self.lbl_date.setText(self._period_text())

        # Chips de periodo
        for b in (self.btn_today, self.btn_week, self.btn_month, self.btn_custom):
            b.setChecked(False)
        {"today": self.btn_today, "week": self.btn_week, "month": self.btn_month, "custom": self.btn_custom}[self.period].setChecked(True)

        # Gráfica
        self._render_chart_lines(rows)

        # Permisos export
        self._refresh_export_enabled()

    # ---------------- Gráfica de líneas por tatuador ----------------

    def _render_chart_lines(self, rows):
        if not _HAVE_QCHART:
            return

        # Limpiar
        self.chart.removeAllSeries()
        for ax in list(self.chart.axes()):
            self.chart.removeAxis(ax)
        self.chart.setTitle("")

        # Armar categorías de días en el rango
        q_from, q_to = self._date_range()
        n_days = max(1, q_from.daysTo(q_to) + 1)
        days = [q_from.addDays(i) for i in range(n_days)]
        categories = [d.toString("dd/MM") for d in days]
        x_index = {d.toString("yyyy-MM-dd"): i for i, d in enumerate(days)}

        # Totales por artista_id/día (y nombre para leyenda)
        by_artist_day = defaultdict(lambda: defaultdict(float))
        for qd, _cli, amount, _pay, artist_name, artist_id in rows:
            key = qd.toString("yyyy-MM-dd")
            if key in x_index:
                by_artist_day[artist_id][key] += amount

        # ¿filtrar a un solo tatuador?
        include_only = None
        if self.filter_artist != "Todos":
            include_only = self._artist_id_by_name(self.filter_artist)

        # Usar SOLO artistas activos
        self._artists = self._fetch_artists(active_only=True)

        # Orden por nombre para leyenda estable
        ordered_artists = sorted(self._artists, key=lambda t: t[1])

        series_list = []
        for s_idx, (artist_id, name) in enumerate(ordered_artists):
            if include_only is not None and artist_id != include_only:
                continue

            per_day = by_artist_day.get(artist_id, {})

            # Si no hay datos (>0) en el rango, no lo muestres (evita líneas planas),
            # salvo que esté filtrado explícitamente
            if not any(v > 0 for v in per_day.values()) and include_only is None:
                continue

            line = QLineSeries()
            line.setName(name)

            # Color desde JSON (id -> nombre -> fallback)
            col_hex = self._artist_color(artist_id, name, s_idx)
            pen = QPen(_qcolor(col_hex)); pen.setWidth(2)
            line.setPen(pen)
            line.setPointsVisible(True)

            # Puntos para todos los días (cero si no hay)
            for d in days:
                k = d.toString("yyyy-MM-dd")
                x = x_index[k]
                y = per_day.get(k, 0.0)
                line.append(float(x), float(y))

            series_list.append(line)
            self.chart.addSeries(line)

        # Eje X categórico — evitar '...' mostrando etiquetas espaciadas
        axisX = QCategoryAxis()
        step = max(1, len(categories) // 10)  # ~10 etiquetas visibles
        for i, label in enumerate(categories):
            if i % step == 0 or i == len(categories) - 1:
                axisX.append(label, float(i))
        axisX.setLabelsBrush(QBrush(QColor("#DADDE3")))
        axisX.setGridLineVisible(False)
        if len(categories) > 14:
            axisX.setLabelsAngle(-45)

        # Eje Y con formato de moneda
        axisY = QValueAxis()
        axisY.setLabelFormat("$%.0f")
        axisY.applyNiceNumbers()
        axisY.setLabelsBrush(QBrush(QColor("#DADDE3")))
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

    # ---------------- Auto-refresh & eventos ----------------

    def showEvent(self, e):
        """Al volver a la pestaña recargamos artistas, colores y datos."""
        super().showEvent(e)
        self._reload_artists_combo()
        self._reload_colors_if_changed()
        self._refresh()

    def _tick_auto_refresh(self):
        """
        Pulso cada 6s:
          - refresca artistas (altas/bajas)
          - reconsulta transacciones (pagos nuevos)
          - repinta gráfica con colores actuales del JSON/paleta
        """
        self._reload_artists_combo()
        self._refresh()

    def _reload_colors_if_changed(self):
        """Si cambió el JSON de colores, recarga y repinta."""
        new_map = load_artist_colors()
        if new_map != self._colors_json:
            self._colors_json = new_map
            self._refresh()

    def _reload_artists_combo(self):
        """Sincroniza el combo de Tatuador con la BD preservando selección actual (solo activos)."""
        prev = self.cbo_artist.currentText() if self.cbo_artist.count() else "Todos"
        self._artists = self._fetch_artists(active_only=True)
        names = [n for _, n in self._artists]
        self.cbo_artist.blockSignals(True)
        self.cbo_artist.clear()
        self.cbo_artist.addItems(["Todos"] + names)
        if self._role == "artist" and self._user_artist_id:
            # Los artistas ven solo su propio nombre (combo bloqueado)
            own_name = self._artist_name_by_id(self._user_artist_id)
            if own_name:
                self.cbo_artist.setCurrentText(own_name)
        else:
            if prev in names or prev == "Todos":
                self.cbo_artist.setCurrentText(prev)
        self.cbo_artist.blockSignals(False)

    # ---------------- Exportar ----------------

    def _refresh_export_enabled(self):
        # Admin siempre; Artist nunca; Assistant con elevación
        if self._role == "artist":
            self.btn_export.setEnabled(False)
            return
        if self._role == "admin":
            self.btn_export.setEnabled(True)
            return
        if self._role == "assistant":
            self.btn_export.setEnabled(True)
            return

    def _ensure_assistant_elevation(self) -> bool:
        """Para assistant: pide código maestro y eleva 5 min."""
        if self._role != "assistant":
            return True
        if not assistant_needs_code("reports", "export"):
            return True

        code, ok = QInputDialog.getText(self, "Código maestro", "Ingresa el código para exportar:", echo=QLineEdit.Password)
        if not ok or not code:
            return False

        with SessionLocal() as db:
            if not verify_master_code(code, db):
                QMessageBox.warning(self, "Permiso denegado", "Código incorrecto.")
                return False

        elevate_for(self._user.get("id"), minutes=5)
        return True

    def _export_csv(self):
        if self._role == "artist":
            QMessageBox.information(self, "Sin permiso", "Tu rol no puede exportar reportes.")
            return
        if self._role == "assistant" and not self._ensure_assistant_elevation():
            return

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
                w.writerow(["Fecha", "Cliente", "Monto", "Pago", "Tatuador"])
                for qd, cli, amt, pay, art, _aid in rows:
                    w.writerow([qd.toString("yyyy-MM-dd"), cli, f"{amt:.2f}", pay, art])
            QMessageBox.information(self, "Exportar", "Archivo CSV exportado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error al exportar", f"No se pudo exportar el CSV.\n\n{e}")
