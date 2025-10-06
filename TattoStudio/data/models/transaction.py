from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from data.db.base import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Eliminamos unique=True para permitir múltiples transacciones por sesión
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="RESTRICT"), index=True)

    amount: Mapped[float] = mapped_column(Float)  # total cobrado
    method: Mapped[str] = mapped_column(String(30))  # 'Efectivo', 'Tarjeta', 'Transferencia', etc.
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    commission_amount: Mapped[Optional[float]] = mapped_column(Float, default=None)
    deleted_flag: Mapped[bool] = mapped_column(Boolean, default=False)  # soft delete

    # data/models/transaction.py
    session = relationship("TattooSession", back_populates="transaction")

    artist = relationship("Artist")
