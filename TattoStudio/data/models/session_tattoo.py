from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, Enum, ForeignKey, Float, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from data.db.base import Base

SessionStatus = ("Activa", "Completada", "En espera", "Cancelada")

class TattooSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="RESTRICT"), index=True)

    start: Mapped[datetime] = mapped_column(DateTime, index=True)
    end: Mapped[datetime] = mapped_column(DateTime, index=True)

    status: Mapped[str] = mapped_column(Enum(*SessionStatus, name="session_status"), default="Activa")
    price: Mapped[float] = mapped_column(Float, default=0.0)  # Sencillo; luego podemos migrar a centavos enteros
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    commission_override: Mapped[Optional[float]] = mapped_column(Float, default=None)

    client = relationship("Client", back_populates="sessions")
    artist = relationship("Artist", back_populates="sessions")
    transaction = relationship("Transaction", back_populates="session", uselist=False)

# Índice útil para detectar choques de horario por artista
Index("ix_sessions_artist_time", TattooSession.artist_id, TattooSession.start, TattooSession.end)
