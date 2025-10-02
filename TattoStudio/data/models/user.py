from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, func
from data.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    # Cuenta / rol
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False, index=True)  # "admin" | "assistant" | "artist"
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=True)  # solo si role == "artist"
    is_active = Column(Boolean, default=True, nullable=False)

    # Datos personales mínimos
    name = Column(String(120), nullable=True)          # Nombre completo (no confundir con nombre artístico)
    birthdate = Column(Date, nullable=True)
    email = Column(String(120), nullable=True, index=True)   # unique opcional (ver migración con índice único condicional)
    phone = Column(String(32), nullable=True)
    instagram = Column(String(64), nullable=True, index=True)  # guardar sin "@"

    # Metadatos
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_login = Column(DateTime, nullable=True)
