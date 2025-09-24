# services/permissions.py
"""
Capa de permisos centralizada (RBAC) + elevación temporal con código maestro.

- can(role, resource, action, *, owner_id=None, user_artist_id=None) -> bool
- assistant_needs_code(resource, action) -> bool
- is_elevated_now(user_id) -> bool
- elevate_for(user_id, minutes: int) -> None
- verify_master_code(plain: str, db: Session) -> bool

Recursos clave: "agenda", "clients", "staff", "reports", "inventory", "security".
Acciones: usar strings simples ("view", "create", "edit", "delete", etc.).

Estados en matriz:
  - "allow": permiso total
  - "own": permitido sólo para el propio (artist)
  - "locked": permitido al assistant sólo si está elevado (código maestro)
  - "deny": bloqueado

NOTA: Mantener esta matriz como única fuente de verdad.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Tuple, Literal, Optional

from sqlalchemy.orm import Session

# Dependencias del proyecto
from services.contracts import get_current_user
from services import auth  # para hash/verify del código maestro
from data.models.setting import Setting

PolicyValue = Literal["allow", "own", "locked", "deny"]

# ------------------ Matriz RBAC (extraída del brief) ------------------
# Formato: (resource, action): {role: policy}
RBAC: Dict[Tuple[str, str], Dict[str, PolicyValue]] = {
    # 1) Agenda
    ("agenda", "view"):     {"admin": "allow", "assistant": "allow", "artist": "allow"},
    ("agenda", "create"):   {"admin": "allow", "assistant": "allow", "artist": "own"},
    ("agenda", "edit"):     {"admin": "allow", "assistant": "allow", "artist": "own"},
    ("agenda", "cancel"):   {"admin": "allow", "assistant": "allow", "artist": "own"},
    ("agenda", "complete"): {"admin": "allow", "assistant": "allow", "artist": "own"},
    ("agenda", "no_show"):  {"admin": "allow", "assistant": "allow", "artist": "own"},
    ("agenda", "block"):    {"admin": "allow", "assistant": "allow", "artist": "own"},
    ("agenda", "export"):   {"admin": "allow", "assistant": "allow", "artist": "own"},

    # 2) Clientes
    ("clients", "view"):    {"admin": "allow", "assistant": "allow", "artist": "allow"},
    ("clients", "create"):  {"admin": "allow", "assistant": "allow", "artist": "allow"},
    ("clients", "edit"):    {"admin": "allow", "assistant": "locked", "artist": "deny"},
    ("clients", "delete"):  {"admin": "allow", "assistant": "locked", "artist": "deny"},
    ("clients", "consent"): {"admin": "allow", "assistant": "allow", "artist": "own"},  # ver/adjuntar
    ("clients", "notes"):   {"admin": "allow", "assistant": "allow", "artist": "own"},
    ("clients", "export"):  {"admin": "allow", "assistant": "locked", "artist": "deny"},

    # 3) Staff
    ("staff", "view"):            {"admin": "allow", "assistant": "allow", "artist": "allow"},
    ("staff", "manage_users"):    {"admin": "allow", "assistant": "deny",  "artist": "deny"},
    ("staff", "toggle_active"):   {"admin": "allow", "assistant": "deny",  "artist": "deny"},
    ("portfolio", "view"):        {"admin": "allow", "assistant": "allow", "artist": "allow"},
    ("portfolio", "edit"):        {"admin": "allow", "assistant": "deny",  "artist": "own"},
    ("portfolio", "upload"):      {"admin": "allow", "assistant": "deny",  "artist": "own"},

    # 4) Reportes / Caja
    ("reports", "view"):          {"admin": "allow", "assistant": "allow", "artist": "own"},
    ("reports", "export"):        {"admin": "allow", "assistant": "locked", "artist": "deny"},
    ("reports", "view_tx"):       {"admin": "allow", "assistant": "allow", "artist": "own"},
    ("reports", "refund_void"):   {"admin": "allow", "assistant": "locked", "artist": "deny"},
    ("reports", "cash_close"):    {"admin": "allow", "assistant": "locked", "artist": "deny"},

    # 5) Inventario
    ("inventory", "view"):        {"admin": "allow", "assistant": "allow", "artist": "allow"},
    ("inventory", "create_item"): {"admin": "allow", "assistant": "locked", "artist": "deny"},
    ("inventory", "edit_item"):   {"admin": "allow", "assistant": "locked", "artist": "deny"},
    ("inventory", "stock_in"):    {"admin": "allow", "assistant": "locked", "artist": "deny"},
    ("inventory", "stock_adj"):   {"admin": "allow", "assistant": "locked", "artist": "deny"},
    ("inventory", "cycle_count"): {"admin": "allow", "assistant": "locked", "artist": "deny"},
    ("inventory", "export"):      {"admin": "allow", "assistant": "locked", "artist": "deny"},

    # 6) Configuración / Seguridad
    ("security", "settings"):      {"admin": "allow", "assistant": "deny",  "artist": "deny"},
    ("security", "audit"):         {"admin": "allow", "assistant": "deny",  "artist": "deny"},
    ("security", "backup"):        {"admin": "allow", "assistant": "deny",  "artist": "deny"},
    ("security", "rotate_code"):   {"admin": "allow", "assistant": "deny",  "artist": "deny"},
}

# ------------------ Ventanas de elevación en memoria ------------------
# Mapa: user_id -> datetime (expiración de elevación)
_elevations: Dict[int, datetime] = {}


def _policy_for(role: str, resource: str, action: str) -> PolicyValue:
    entry = RBAC.get((resource, action))
    if not entry:
        # Por defecto, si no está definido, negamos (fail-safe)
        return "deny"
    return entry.get(role, "deny")


def assistant_needs_code(resource: str, action: str) -> bool:
    return _policy_for("assistant", resource, action) == "locked"


def is_elevated_now(user_id: int) -> bool:
    exp = _elevations.get(user_id)
    return bool(exp and datetime.now() <= exp)


def elevate_for(user_id: int, minutes: int = 5) -> None:
    _elevations[user_id] = datetime.now() + timedelta(minutes=minutes)


def can(
    role: str,
    resource: str,
    action: str,
    *,
    owner_id: Optional[int] = None,         # id del recurso (artist_id dueño)
    user_artist_id: Optional[int] = None,   # artist_id del usuario actual
    user_id: Optional[int] = None,          # para validar elevación si assistant
) -> bool:
    policy = _policy_for(role, resource, action)

    if policy == "deny":
        return False

    if policy == "allow":
        if role == "assistant" and assistant_needs_code(resource, action):
            # Si es acción "locked" y assistant, sólo con elevación vigente
            return bool(user_id and is_elevated_now(user_id))
        return True

    if policy == "own":
        # Sólo artistas sobre "lo propio"
        return role == "artist" and owner_id is not None and user_artist_id == owner_id

    if policy == "locked":
        # Para admin nunca se marca locked; para assistant, requiere elevación
        if role == "assistant" and user_id is not None:
            return is_elevated_now(user_id)
        return False

    return False


# ------------------ Código maestro en settings ------------------
SETTING_KEY = "MASTER_CODE_HASH"


def verify_master_code(plain: str, db: Session) -> bool:
    row = db.query(Setting).filter(Setting.key == SETTING_KEY).one_or_none()
    if not row or not row.value:
        return False
    try:
        return auth.verify_password(plain, row.value)
    except Exception:
        return False


# ------------------ Helper de "defensa en profundidad" ------------------
class PermissionError(Exception):
    pass


def enforce(
    *,
    resource: str,
    action: str,
    owner_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> None:
    """Usar dentro de servicios antes de escribir en BD.
    Lanza PermissionError si no procede.
    """
    user = get_current_user()  # {id, username, role, artist_id}
    if not user:
        raise PermissionError("No hay sesión activa.")

    allowed = can(
        user.get("role"), resource, action,
        owner_id=owner_id,
        user_artist_id=user.get("artist_id"),
        user_id=user.get("id"),
    )
    if not allowed:
        raise PermissionError(f"Acción no permitida: {resource}.{action}")


# ------------------ Opcional: reset/clear elevación al cambiar usuario --

def clear_elevation(user_id: int) -> None:
    _elevations.pop(user_id, None)
