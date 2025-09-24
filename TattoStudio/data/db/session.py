import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from .base import Base
from data.models import load_all_models
load_all_models()

# Ruta del archivo SQLite. Si no hay variable de entorno, usa ./dev.db
DB_PATH = os.getenv("DB_PATH", "./dev.db")

# Crea el engine (el "conector" a tu archivo .db)
engine = create_engine(f"sqlite:///{DB_PATH}", future=True, echo=False)

# Activa llaves foráneas en SQLite (por defecto están apagadas)
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Crea la fábrica de sesiones (para transacciones)
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
)

def init_db() -> None:
    """Crea tablas si no existen. Útil en desarrollo/pruebas."""
    from data.models import load_all_models  # asegura que todas las tablas se importen
    load_all_models()
    Base.metadata.create_all(bind=engine)
