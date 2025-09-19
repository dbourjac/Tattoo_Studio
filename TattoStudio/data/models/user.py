from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from data.db.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(60), unique=True)
    role: Mapped[str] = mapped_column(String(20), default="operator")  # 'admin' | 'operator'
    password_hash: Mapped[str] = mapped_column(String(200))
