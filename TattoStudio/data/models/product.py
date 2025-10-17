from typing import Optional
from sqlalchemy import String, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from data.db.base import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50) )
    name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[Optional[str]] = mapped_column(String(60), default="consumibles")
    unidad: Mapped[str] = mapped_column(String(50) )
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    min_stock: Mapped[int] = mapped_column(Integer, default=0)
    caduca: Mapped[bool] = mapped_column(Boolean, default=False)
    provedor: Mapped[str] = mapped_column(String(50) )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    fechacaducidad: Mapped[str] = mapped_column(String(10) )