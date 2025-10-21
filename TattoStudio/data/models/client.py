# data/models/client.py
from __future__ import annotations

from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey, func, text
)
from sqlalchemy.orm import relationship

from data.db.base import Base  # asegura que Base apunte a tu declarative_base()

class Client(Base):
    __tablename__ = "clients"  # coincide con la BD

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(40))
    email = Column(String(120))
    notes = Column(Text)
    is_active = Column(Boolean, nullable=False, server_default="1")

    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # ---- Campos nuevos / opcionales ----
    instagram = Column(Text)
    city = Column(Text)
    state = Column(Text)
    gender = Column(Text)
    birthdate = Column(Date)

    # Consentimientos
    consent_info = Column(Boolean)
    consent_image = Column(Boolean)
    consent_data = Column(Boolean)

    # Emergencia
    emergency_name = Column(Text)
    emergency_relation = Column(Text)
    emergency_phone = Column(Text)

    # Preferencias
    preferred_artist_id = Column(Integer, ForeignKey("artists.id"))
    preferred_artist = relationship(
        "Artist",
        backref="preferred_clients",
        foreign_keys=[preferred_artist_id],
    )

    # Salud
    health_allergies = Column(Boolean)
    health_diabetes = Column(Boolean)
    health_coagulation = Column(Boolean)
    health_epilepsy = Column(Boolean)
    health_cardiac = Column(Boolean)
    health_anticoagulants = Column(Boolean)
    health_preg_lact = Column(Boolean)
    health_substances = Column(Boolean)
    health_derm = Column(Boolean)
    health_obs = Column(Text)

    # 🔧 IMPORTANTE: contraparte requerida por TattooSession.client(back_populates="sessions")
    sessions = relationship(
        "TattooSession",
        back_populates="client",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
