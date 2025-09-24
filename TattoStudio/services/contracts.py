from datetime import datetime
from typing import TypedDict, Literal, Optional, Dict

_current_user: Optional[Dict] = None

def set_current_user(u: Optional[Dict]):
    global _current_user
    _current_user = u

def get_current_user() -> Optional[Dict]:
    return _current_user


PaymentMethod = Literal["Efectivo", "Tarjeta", "Transferencia"]

class SessionCreate(TypedDict):
    client_id: int
    artist_id: int
    start: datetime
    end: datetime
    price: float
    notes: Optional[str]

class SessionUpdate(TypedDict, total=False):
    start: datetime
    end: datetime
    price: float
    status: Literal["Activa", "Completada", "En espera", "Cancelada"]
    notes: Optional[str]
    commission_override: Optional[float]

class PaymentInput(TypedDict):
    method: PaymentMethod

# Firmas esperadas (implementación real llega en Etapa 1)
def create_session(payload: SessionCreate) -> int: ...
def update_session(session_id: int, payload: SessionUpdate) -> None: ...
def complete_session(session_id: int, payment: PaymentInput) -> int: ...
def list_transactions(filters: dict) -> list[dict]: ...
def compute_commission(transaction_id: int) -> float: ...
