from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from data.db.base import Base

class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
