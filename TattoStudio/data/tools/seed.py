"""
Seeder de la base de datos para TattooStudio.

Qué hace (en este orden):
1) Carga modelos y asegura que existan las tablas (init_db).
2) Crea clientes, artistas y productos si no existen.
3) Genera sesiones (citas) y transacciones dummy.
4) Crea 3 usuarios de prueba (admin / assistant / artist ligado).

El seeder es **idempotente** a nivel de colecciones: si ya hay filas,
no vuelve a insertar ese bloque (evita duplicados al correr varias veces).
"""

import os
import random
from datetime import datetime, timedelta
from typing import List

from faker import Faker
from sqlalchemy.orm import Session

from data.db.session import SessionLocal, init_db
from data.models import load_all_models
from data.models.client import Client
from data.models.artist import Artist
from data.models.product import Product
from data.models.session_tattoo import TattooSession
from data.models.transaction import Transaction

# Usuarios
from services.auth import hash_password
from data.models.user import User

fake = Faker("es_MX")
random.seed(42)  # reproducible


# ----------------------------
#  BLOQUES DE SEED
# ----------------------------

def seed_clients_artists_products(db: Session) -> None:
    """Crea clientes, artistas y productos si la tabla está vacía."""
    # --- Clientes ---
    if db.query(Client).count() == 0:
        clients: List[Client] = [
            Client(name=fake.name(), phone=fake.phone_number(), email=fake.email())
            for _ in range(40)
        ]
        db.add_all(clients)

    # --- Artistas ---
    if db.query(Artist).count() == 0:
        artists = [
            Artist(name="Dylan Bourjac", rate_commission=0.55, active=True),
            Artist(name="Jesus Esquer", rate_commission=0.50, active=True),
            Artist(name="Pablo Velasquez", rate_commission=0.45, active=True),
            Artist(name="Alex Chavez", rate_commission=0.50, active=True),
        ]
        db.add_all(artists)

    db.flush()  # asegura IDs para relaciones en pasos siguientes

    # --- Productos (si no existen por nombre) ---
    defaults = [
        ("Tinta Negra", "Tinta", 180.0, 12, 5),
        ("Guantes", "Insumo", 90.0, 50, 20),
        ("Agujas 5RL", "Agujas", 150.0, 30, 10),
    ]
    existing = {name for (name,) in db.query(Product.name).all()}
    to_add = [
        Product(name=n, category=c, cost=cost, stock=stock, min_stock=min_s)
        for (n, c, cost, stock, min_s) in defaults
        if n not in existing
    ]
    if to_add:
        db.add_all(to_add)


def seed_sessions_and_transactions(db: Session, n_sessions: int = 60) -> None:
    """
    Genera sesiones en los últimos ~30 días (y algunas de hoy) y
    crea transacciones SOLO para sesiones 'Completada'.
    """
    if db.query(TattooSession).count() > 0:
        return  # ya hay sesiones → no duplicamos

    clients = db.query(Client).all()
    artists = db.query(Artist).all()
    if not clients or not artists:
        return

    sessions: List[TattooSession] = []
    now = datetime.now()

    for _ in range(n_sessions):
        c = random.choice(clients)
        a = random.choice(artists)

        # inicio en las últimas 0..30 días, con hora aleatoria
        start = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 12))
        end = start + timedelta(hours=random.choice([1, 2, 3]))
        price = random.choice([600, 800, 1200, 1400, 2000, 2200])

        status = random.choices(
            ["Activa", "Completada", "En espera"],
            weights=[2, 5, 1],
        )[0]

        sessions.append(
            TattooSession(
                client_id=c.id,
                artist_id=a.id,
                start=start,
                end=end,
                status=status,
                price=price,
                notes=fake.sentence(nb_words=6),
            )
        )

    db.add_all(sessions)
    db.flush()  # IDs de sesiones listos

    # Transacciones para las completadas
    txs: List[Transaction] = []
    for s in sessions:
        if s.status == "Completada":
            txs.append(
                Transaction(
                    session_id=s.id,
                    artist_id=s.artist_id,
                    amount=s.price,
                    method=random.choice(["Efectivo", "Tarjeta", "Transferencia"]),
                    date=s.end,
                )
            )
    if txs:
        db.add_all(txs)


def seed_users(db: Session) -> None:
    """
    Crea 3 usuarios básicos si no existen:
      - admin / admin123 (admin)
      - assistant / assistant123 (assistant)
      - jesus / tattoo123 (artist → ligado a un artista existente)
    """
    existing = {u for (u,) in db.query(User.username).all()}

    # Admin
    if "admin" not in existing:
        db.add(User(
            username="admin",
            password_hash=hash_password("admin123"),
            role="admin",
            is_active=True,
        ))

    # Assistant
    if "assistant" not in existing:
        db.add(User(
            username="assistant",
            password_hash=hash_password("assistant123"),
            role="assistant",
            is_active=True,
        ))

    # Artist (preferimos ligar a "Jesus Esquer"; si no existe, al primero)
    if "jesus" not in existing:
        artist = db.query(Artist).filter(Artist.name == "Jesus Esquer").first() or db.query(Artist).first()
        db.add(User(
            username="jesus",
            password_hash=hash_password("tattoo123"),
            role="artist",
            artist_id=artist.id if artist else None,
            is_active=True,
        ))


# ----------------------------
#  ENTRYPOINT
# ----------------------------

def main():
    """
    Punto de entrada del seeder:
      - Carga modelos y crea tablas.
      - Ejecuta cada bloque de seed (idempotentes).
      - Commit/rollback seguro.
    """
    # Para dev: usa dev.db en la raíz si no se ha configurado DB_PATH
    os.environ.setdefault("DB_PATH", "./dev.db")

    load_all_models()
    init_db()

    with SessionLocal() as db:
        db.begin()
        try:
            seed_clients_artists_products(db)
            seed_sessions_and_transactions(db, n_sessions=60)
            seed_users(db)

            db.commit()

            print(
                "Seed listo:",
                f"{db.query(Client).count()} clientes,",
                f"{db.query(Artist).count()} artistas,",
                f"{db.query(TattooSession).count()} sesiones,",
                f"{db.query(Transaction).count()} transacciones,",
                f"{db.query(Product).count()} productos,",
                f"{db.query(User).count()} usuarios."
            )
        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()
