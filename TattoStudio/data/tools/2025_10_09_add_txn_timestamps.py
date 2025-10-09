#!/usr/bin/env python3
"""
Migra la tabla 'transactions' para asegurar:
- concept TEXT (si falta)
- created_at TEXT (si falta)
- updated_at TEXT (si falta)
y un trigger para mantener updated_at.

Uso:
  python data/tools/2025_10_09_add_txn_timestamps.py [RUTA_DB]
Si no se pasa ruta, usa ../../dev.db
"""
import os
import sys
import sqlite3

def db_path_from_argv() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dev.db"))

def column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())

def add_text_column(cur: sqlite3.Cursor, table: str, column: str) -> None:
    """Agrega columna TEXT sin default (SQLite no admite default no-const en ALTER)."""
    if not column_exists(cur, table, column):
        cur.execute(f'ALTER TABLE {table} ADD COLUMN {column} TEXT')
        print(f"[OK] Columna agregada: {table}.{column}")
    else:
        print(f"[=] Columna ya existe: {table}.{column}")

def add_concept_column(cur: sqlite3.Cursor) -> None:
    # Si no existe, la creamos con TEXT simple; el default '' no es necesario para ALTER.
    if not column_exists(cur, "transactions", "concept"):
        cur.execute('ALTER TABLE transactions ADD COLUMN concept TEXT')
        print("[OK] Columna agregada: transactions.concept")
    else:
        print("[=] Columna ya existe: transactions.concept")

def main():
    db_path = db_path_from_argv()
    print(f"Usando base de datos: {db_path}")
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = OFF")
    cur = con.cursor()
    try:
        # Validar existencia de tabla
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
        if not cur.fetchone():
            raise SystemExit("ERROR: no existe la tabla 'transactions' en esta DB.")

        # 1) Asegurar columnas
        add_concept_column(cur)
        add_text_column(cur, "transactions", "created_at")
        add_text_column(cur, "transactions", "updated_at")

        # 2) Backfill de timestamps nulos
        cur.execute("UPDATE transactions SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
        cur.execute("UPDATE transactions SET updated_at = COALESCE(updated_at, created_at)")

        # 3) Trigger para mantener updated_at en updates
        cur.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_transactions_updated_at
        AFTER UPDATE ON transactions
        FOR EACH ROW
        BEGIN
            UPDATE transactions SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        """)

        con.commit()
        print("[OK] Migración completada.")
    finally:
        con.close()

if __name__ == "__main__":
    main()
