# data/tools/2025_10_17_add_client_is_active.py
from sqlalchemy import text
from data.db.session import SessionLocal

def main():
    s = SessionLocal()
    engine = s.bind
    print("Usando DB:", engine.url)
    try:
        with engine.connect() as conn:
            # ¿existe la tabla?
            tables = [r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))]
            if "clients" not in tables:
                print("ERROR: no existe la tabla 'clients'. Revisa tu SessionLocal / ruta de la BD.")
                return

            # ¿existe ya la columna?
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info(clients)"))]
            if "is_active" in cols:
                print("OK: 'is_active' ya existe. Nada que hacer.")
                return

            print("Agregando columna 'is_active'…")
            conn.execute(text("ALTER TABLE clients ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"))
            print("Listo ✅")

    finally:
        s.close()

if __name__ == "__main__":
    main()
