from typing import Optional
from sqlalchemy import String, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column
from data.db.base import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[Optional[str]] = mapped_column(String(60), default=None)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    min_stock: Mapped[int] = mapped_column(Integer, default=0)
