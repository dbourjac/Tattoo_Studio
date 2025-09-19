"""
Paquete 'data': DB/ORM, modelos y utilidades.
"""

# Carga variables de entorno desde .env si existe, sin romper nada si no.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(override=False)
except Exception:
    pass

__all__ = ["db", "models", "tools"]

def init_db():
    """
    Atajo para inicializar la BD desde 'data'.
    Uso: from data import init_db; init_db()
    (Importa adentro para evitar ciclos de import.)
    """
    from .db.session import init_db as _init
    _init()
