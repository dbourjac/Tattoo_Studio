from sqlalchemy import String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from data.db.base import Base

class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    rate_commission: Mapped[float] = mapped_column(Float, default=0.50)  # 50% por defecto
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    sessions = relationship("TattooSession", back_populates="artist")
    portfolio_items = relationship("PortfolioItem", back_populates="artist", cascade="all, delete-orphan")
