# imports recomendados arriba del archivo
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from data.db.base import Base

class PortfolioItem(Base):
    __tablename__ = "portfolio_items"

    id = Column(Integer, primary_key=True)
    # ahora NULLABLE (ya migrado en la BD)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=True)

    # NUEVOS CAMPOS (mapeados)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)

    path = Column(String, nullable=False)
    thumb_path = Column(String, nullable=True)
    caption = Column(Text, nullable=True)

    style = Column(String, nullable=True)
    body_area = Column(String, nullable=True)
    color_mode = Column(String, nullable=True)        # "color" | "bn"
    fresh_or_healed = Column(String, nullable=True)   # "fresh" | "healed"

    is_public = Column(Boolean, nullable=False, default=True)
    is_cover = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # (opcionales, pero útiles)
    artist = relationship("Artist", foreign_keys=[artist_id], lazy="joined")
    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    client = relationship("Client", foreign_keys=[client_id], lazy="joined")
    session = relationship("TattooSession", foreign_keys=[session_id], lazy="joined")
    transaction = relationship("Transaction", foreign_keys=[transaction_id], lazy="joined")
