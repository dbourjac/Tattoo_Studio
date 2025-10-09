from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Float,
    Boolean,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from data.db.base import Base

class Transaction(Base):

    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_tx_date", "date"),
        Index("ix_tx_artist_date", "artist_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    amount: Mapped[float] = mapped_column(Float, nullable=False)  # total cobrado
    method: Mapped[str] = mapped_column(String(30), nullable=False)  # 'Efectivo', 'Tarjeta', etc.
    concept: Mapped[str] = mapped_column(String(200), default="", nullable=False)  # concepto/nota libre

    # Cuando ocurrió el cobro (para reportes/agrupación)
    date: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)

    # Monto de comisión (si aplica). Puede ser None.
    commission_amount: Mapped[Optional[float]] = mapped_column(Float, default=None)

    # Soft delete
    deleted_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps de auditoría
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relaciones
    # Importante: usamos 'transactions' (plural) en la sesión. Lo ajustaremos en session_tattoo.py.
    session = relationship("TattooSession", back_populates="transactions", lazy="joined")
    artist = relationship("Artist", lazy="joined")
