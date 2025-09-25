from datetime import datetime
from typing import Optional

# Asegura que TODOS los modelos estén registrados (evita errores de mapeo diferido)
from data.models import load_all_models
load_all_models()

from data.db.session import SessionLocal
from data.models.session_tattoo import TattooSession
from data.models.transaction import Transaction
from data.models.artist import Artist


ALLOWED_METHODS = {"Efectivo", "Tarjeta", "Transferencia"}
ALLOWED_STATUS = {"Activa", "Completada", "En espera", "Cancelada"}


# ---------- Utilidad: detectar choque de horarios ----------
def _check_overlap(db, artist_id: int, start: datetime, end: datetime, exclude_session_id: Optional[int] = None):
    """
    Lanza ValueError si existe otra sesión del mismo artista que se traslapa con [start, end).
    Regla: new_start < existing_end  y  new_end > existing_start
    Ignora sesiones Canceladas. Puede excluir una sesión (cuando es edición).
    """
    if start >= end:
        raise ValueError("El inicio debe ser anterior al fin de la sesión.")

    q = (
        db.query(TattooSession)
        .filter(
            TattooSession.artist_id == artist_id,
            TattooSession.status != "Cancelada",
            TattooSession.start < end,
            TattooSession.end > start,
        )
    )
    if exclude_session_id is not None:
        q = q.filter(TattooSession.id != exclude_session_id)

    if db.query(q.exists()).scalar():
        raise ValueError("Choque de horario: el artista ya tiene una sesión en ese intervalo.")


# ---------- API: crear sesión ----------
def create_session(payload: dict) -> int:
    """
    payload esperado:
      { 'client_id': int, 'artist_id': int,
        'start': datetime, 'end': datetime,
        'price': float, 'notes': Optional[str] }
    Devuelve el ID de la sesión creada.
    """
    with SessionLocal() as db:
        with db.begin():
            _check_overlap(db, payload["artist_id"], payload["start"], payload["end"])

            s = TattooSession(
                client_id=payload["client_id"],
                artist_id=payload["artist_id"],
                start=payload["start"],
                end=payload["end"],
                price=payload.get("price", 0.0),
                notes=payload.get("notes"),
                status="Activa",
            )
            db.add(s)
            db.flush()  # asigna s.id
            return s.id
def cancel_session(session_id: int, as_no_show: bool = False) -> None:
    """
    Marca la sesión como 'Cancelada'. Si as_no_show=True, antepone una nota para indicarlo.
    NOTA: El esquema actual no tiene estado 'No-show'; lo representamos como Cancelada + nota.
    """
    with SessionLocal() as db:
        with db.begin():
            s = db.get(TattooSession, session_id)
            if not s:
                raise ValueError("Sesión no encontrada.")
            if s.status == "Completada":
                raise ValueError("No puedes cancelar una sesión completada.")

            # Marcar cancelada
            s.status = "Cancelada"
            note_tag = "[No-show] " if as_no_show else ""
            if note_tag:
                s.notes = (note_tag + (s.notes or "")).strip()
            db.add(s)


# ---------- API: actualizar sesión ----------
def update_session(session_id: int, payload: dict) -> None:
    """
    Permite cambiar horarios, precio, notas y estado (excepto 'Completada', usar complete_session()).
    Si cambian start/end/artist_id, valida choques.
    """
    with SessionLocal() as db:
        with db.begin():
            s = db.get(TattooSession, session_id)
            if not s:
                raise ValueError("Sesión no encontrada.")

            # No permitir completar aquí (flujo controlado desde complete_session)
            new_status = payload.get("status")
            if new_status:
                if new_status not in ALLOWED_STATUS:
                    raise ValueError("Estado inválido.")
                if new_status == "Completada":
                    raise ValueError("Usa complete_session(session_id, payment) para completar y crear transacción.")

            # Cambios propuestos
            new_start = payload.get("start", s.start)
            new_end = payload.get("end", s.end)
            new_artist_id = payload.get("artist_id", s.artist_id)

            # Validación de choques si se mueven datos de agenda
            if (new_start != s.start) or (new_end != s.end) or (new_artist_id != s.artist_id):
                _check_overlap(db, new_artist_id, new_start, new_end, exclude_session_id=s.id)

            # Asignar cambios simples
            for k in ("start", "end", "price", "notes", "status", "artist_id", "commission_override"):
                if k in payload:
                    setattr(s, k, payload[k])

            db.add(s)  # commit del contexto guarda cambios


# ---------- API: completar sesión (crea Transaction) ----------
def complete_session(session_id: int, payment: dict) -> int:
    """
    Marca la sesión como 'Completada' y crea una Transaction asociada.
    payment esperado: {'method': 'Efectivo'|'Tarjeta'|'Transferencia'}
    Devuelve el id de la Transaction creada.
    """
    method = payment.get("method")
    if method not in ALLOWED_METHODS:
        raise ValueError("Método de pago inválido.")

    with SessionLocal() as db:
        with db.begin():
            s = db.get(TattooSession, session_id)
            if not s:
                raise ValueError("Sesión no encontrada.")
            if s.status == "Cancelada":
                raise ValueError("No puedes completar una sesión cancelada.")
            if s.transaction is not None:
                raise ValueError("Esta sesión ya tiene transacción.")

            if s.price is None:
                s.price = 0.0

            # Determinar comisión
            artist = db.get(Artist, s.artist_id)
            if s.commission_override is not None:
                rate = s.commission_override
            else:
                rate = artist.rate_commission if artist and (artist.rate_commission is not None) else 0.5

            commission_amount = round((s.price or 0.0) * rate, 2)

            # Marcar completada y crear transacción
            s.status = "Completada"
            t = Transaction(
                session_id=s.id,
                artist_id=s.artist_id,
                amount=s.price,
                method=method,
                date=s.end or datetime.utcnow(),
                commission_amount=commission_amount,
            )
            db.add(s)
            db.add(t)
            db.flush()
            return t.id


# ---------- (Opcional) listar sesiones para Agenda ----------
def list_sessions(filters: dict) -> list[dict]:
    """
    Devuelve sesiones como dicts para poblar la Agenda.
    filters soporta: from (datetime), to (datetime), artist_id (int), status (str|list)
    """
    with SessionLocal() as db:
        q = db.query(TattooSession)

        f_from = filters.get("from")
        f_to = filters.get("to")
        if f_from:
            q = q.filter(TattooSession.start >= f_from)
        if f_to:
            q = q.filter(TattooSession.start < f_to)

        if "artist_id" in filters:
            q = q.filter(TattooSession.artist_id == filters["artist_id"])

        if "status" in filters:
            st = filters["status"]
            if isinstance(st, (list, tuple, set)):
                q = q.filter(TattooSession.status.in_(list(st)))
            else:
                q = q.filter(TattooSession.status == st)

        q = q.order_by(TattooSession.start.asc())
        out = []
        for s in q.all():
            out.append({
                "id": s.id,
                "client_id": s.client_id,
                "artist_id": s.artist_id,
                "start": s.start,
                "end": s.end,
                "status": s.status,
                "price": s.price,
                "notes": s.notes,
            })
        return out
