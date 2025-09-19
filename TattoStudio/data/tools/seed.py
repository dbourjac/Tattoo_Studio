import os
import random
from datetime import datetime, timedelta
from faker import Faker
from sqlalchemy.orm import Session as SASession
from data.db.session import engine, init_db
from data.models import load_all_models
from data.models.client import Client
from data.models.artist import Artist
from data.models.session_tattoo import TattooSession
from data.models.transaction import Transaction
from data.models.product import Product

fake = Faker("es_MX")

def main():
    load_all_models()
    init_db()
    with SASession(bind=engine) as db:
        db.begin()
        try:
            clients = [Client(name=fake.name(), phone=fake.phone_number(), email=fake.email()) for _ in range(40)]
            db.add_all(clients)

            artists = [
                Artist(name="Dylan Bourjac", rate_commission=0.55, active=True),
                Artist(name="Jesus Esquer", rate_commission=0.50, active=True),
                Artist(name="Pablo Velasquez", rate_commission=0.45, active=True),
                Artist(name="Alex Chavez", rate_commission=0.50, active=True),
            ]
            db.add_all(artists)
            db.flush()  # asegura IDs para relaciones

            products = [
                Product(name="Tinta Negra", category="Tinta", cost=180.0, stock=12, min_stock=5),
                Product(name="Guantes", category="Insumo", cost=90.0, stock=50, min_stock=20),
                Product(name="Agujas 5RL", category="Agujas", cost=150.0, stock=30, min_stock=10),
            ]
            db.add_all(products)

            sessions = []
            transactions = []
            now = datetime.now()
            for _ in range(60):
                c = random.choice(clients)
                a = random.choice(artists)
                start = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 12))
                end = start + timedelta(hours=random.choice([1, 2, 3]))
                price = random.choice([600, 800, 1200, 1400, 2000, 2200])

                status = random.choices(["Activa", "Completada", "En espera"], weights=[2, 5, 1])[0]
                s = TattooSession(
                    client_id=c.id,
                    artist_id=a.id,
                    start=start,
                    end=end,
                    status=status,
                    price=price,
                    notes=fake.sentence(nb_words=6),
                )
                sessions.append(s)

            db.add_all(sessions)
            db.flush()

            for s in sessions:
                if s.status == "Completada":
                    t = Transaction(
                        session_id=s.id,
                        artist_id=s.artist_id,
                        amount=s.price,
                        method=random.choice(["Efectivo", "Tarjeta", "Transferencia"]),
                        date=s.end,
                    )
                    transactions.append(t)

            db.add_all(transactions)
            db.commit()
            print(f"Seed listo: {len(clients)} clientes, {len(artists)} artistas, {len(sessions)} sesiones, {len(transactions)} transacciones.")
        except Exception:
            db.rollback()
            raise

if __name__ == "__main__":
    os.environ.setdefault("DB_PATH", "./dev.db")
    main()
