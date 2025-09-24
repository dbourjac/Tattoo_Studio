from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func
from data.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False, index=True)  # "admin" | "assistant" | "artist"
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=True)  # solo si role == "artist"
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_login = Column(DateTime, nullable=True)
