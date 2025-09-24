from __future__ import annotations

# ============================================================
# common.py — Helpers de UI compartidos
# - make_simple_page: placeholder con título centrado
# - request_elevation_if_needed: pide código maestro al assistant (si 🔒)
# - ensure_permission: pide elevación si aplica + valida permiso RBAC
#
# Notas:
# * ELEVATION_MINUTES controla la ventana de elevación (default 5 min).
# * Para acciones "👤 solo propias" debes pasar owner_id en ensure_permission,
#   típicamente el artist_id dueño del recurso (cita/portafolio).
# ============================================================

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QInputDialog, QLineEdit, QMessageBox
)

from sqlalchemy.orm import Session

# Ajusta este import si tu factoría tiene otro nombre o ruta.
from data.db.session import SessionLocal

# RBAC & sesión actual
from services.permissions import (
    assistant_needs_code,
    verify_master_code,
    elevate_for,
    can,
)
from services.contracts import get_current_user


# Ventana de elevación por defecto (minutos)
ELEVATION_MINUTES: int = 5


# ------------------------------------------------------------
# Placeholder simple para páginas aún no implementadas
# ------------------------------------------------------------
def make_simple_page(nombre: str) -> QWidget:
    """
    Crea una página placeholder con un título centrado.
    Útil mientras no implementamos la lógica real.
    """
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(40, 40, 40, 40)
    title = QLabel(nombre)
    title.setObjectName("H1")
    lay.addWidget(title, alignment=Qt.AlignCenter)
    return w


# ------------------------------------------------------------
# Elevación: solicitar código maestro SOLO si es necesario
# (assistant intentando una acción marcada como 🔒 en la matriz)
# ------------------------------------------------------------
def request_elevation_if_needed(parent: QWidget, resource: str, action: str) -> bool:
    """
    Si el usuario actual es assistant y la acción es 🔒, solicita código maestro,
    valida contra MASTER_CODE_HASH y eleva permisos por ELEVATION_MINUTES.
    Devuelve True cuando:
      - No se requiere elevación (no es assistant o la acción no es 🔒), o
      - El código es correcto y se elevó; False en caso contrario.
    """
    user = get_current_user()
    if not user:
        QMessageBox.warning(parent, "Sesión", "No hay usuario activo.")
        return False

    role = user.get("role")
    if role != "assistant" or not assistant_needs_code(resource, action):
        # No requiere elevación para esta combinación rol/acción.
        return True

    # Pedimos el código maestro de forma discreta (input tipo password).
    code, ok = QInputDialog.getText(
        parent,
        "Código maestro",
        "Ingresa el código maestro:",
        QLineEdit.Password
    )
    if not ok:
        # Usuario canceló el diálogo.
        return False

    code = (code or "").strip()
    if not code:
        QMessageBox.warning(parent, "Código maestro", "El código no puede estar vacío.")
        return False

    # Verificamos contra el hash guardado en settings.
    with SessionLocal() as db:  # type: Session
        if verify_master_code(code, db):
            elevate_for(user.get("id"), minutes=ELEVATION_MINUTES)
            QMessageBox.information(
                parent,
                "Permiso concedido",
                f"Permisos elevados por {ELEVATION_MINUTES} minutos."
            )
            return True

    QMessageBox.critical(parent, "Código inválido", "El código maestro no es correcto.")
    return False


# ------------------------------------------------------------
# Helper integral: pide elevación si aplica y luego valida permiso RBAC.
# Úsalo en tus handlers de botones/acciones para centralizar todo.
# ------------------------------------------------------------
def ensure_permission(
    parent: QWidget,
    resource: str,
    action: str,
    *,
    owner_id: Optional[int] = None,
) -> bool:
    """
    1) Resuelve elevación si es assistant y acción 🔒.
    2) Valida permiso con matriz RBAC (soporta casos '👤 solo propias').

    Parámetros:
      - resource: p.ej. "clients", "reports", "inventory", "agenda", etc.
      - action:   p.ej. "edit", "delete", "export", "create", etc.
      - owner_id: cuando la política es 'own' (👤), pasa aquí el artist_id
                  dueño del recurso que se intenta manipular.

    Retorna True si la acción puede continuar, False si no tiene permiso.
    """
    user = get_current_user()
    if not user:
        QMessageBox.warning(parent, "Sesión", "No hay usuario activo.")
        return False

    # 1) Si la acción requiere elevación para assistant, la gestionamos aquí.
    if not request_elevation_if_needed(parent, resource, action):
        return False

    # 2) Validamos permiso con la matriz RBAC ya centralizada.
    allowed = can(
        user.get("role"),
        resource,
        action,
        owner_id=owner_id,                     # necesario para políticas 'own'
        user_artist_id=user.get("artist_id"),  # artist_id del usuario actual
        user_id=user.get("id"),                # para validar elevación vigente
    )

    if not allowed:
        QMessageBox.warning(parent, "Permisos", "No tienes permiso para esta acción.")
        return False

    return True
