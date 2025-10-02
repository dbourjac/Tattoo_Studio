"""
Migración mínima (idempotente) para añadir campos a 'users' en dev.db:

- name TEXT
- birthdate DATE
- email TEXT
- phone TEXT
- instagram TEXT

Además crea índices (si no existen):
- ix_users_email
- ix_users_instagram

Detecta dev.db en la raíz del repo (dos niveles arriba de data/tools),
o usa la variable de entorno DB_PATH si está definida.
"""

import os
import sqlite3
from pathlib import Path


NEEDED_COLUMNS = {
    "name": "TEXT",
    "birthdate": "DATE",
    "email": "TEXT",
    "phone": "TEXT",
    "instagram": "TEXT",
}

NEEDED_INDEXES = {
    "ix_users_email": "CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)",
    "ix_users_instagram": "CREATE INDEX IF NOT EXISTS ix_users_instagram ON users(instagram)",
}


def _resolve_db_path() -> Path:
    # 1) Si el usuario define DB_PATH, respetarlo
    env_path = os.environ.get("DB_PATH")
    if env_path:
        return Path(env_path).resolve()

    # 2) Ubicar dev.db en la raíz del repo (este archivo está en data/tools)
    here = Path(__file__).resolve()
    # .../data/tools/migrate_users_add_fields.py  → raíz = parents[2]
    repo_root = here.parents[2]
    candidate = repo_root / "dev.db"
    return candidate.resolve()


def _table_exists(cur: sqlite3.Cursor, name: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,))
    return cur.fetchone() is not None


def _existing_columns(cur: sqlite3.Cursor, table: str) -> set:
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1].lower() for row in cur.fetchall()}  # row[1] = column name


def main():
    db_path = _resolve_db_path()
    if not db_path.exists():
        raise SystemExit(f"[x] No se encontró la base de datos en: {db_path}")

    print(f"[i] Conectando a: {db_path}")
    con = sqlite3.connect(str(db_path))
    con.isolation_level = None  # control manual de transacciones
    cur = con.cursor()

    try:
        cur.execute("BEGIN")
        if not _table_exists(cur, "users"):
            raise RuntimeError("La tabla 'users' no existe en esta base de datos.")

        cols = _existing_columns(cur, "users")

        # Añadir columnas faltantes
        added = []
        for col, coltype in NEEDED_COLUMNS.items():
            if col.lower() not in cols:
                sql = f"ALTER TABLE users ADD COLUMN {col} {coltype}"
                print(f"[+] {sql}")
                cur.execute(sql)
                added.append(col)
            else:
                print(f"[=] Columna ya existe: {col}")

        # Índices
        for _, create_sql in NEEDED_INDEXES.items():
            print(f"[~] {create_sql}")
            cur.execute(create_sql)

        cur.execute("COMMIT")
        print("\n[✓] Migración completada.")
        if added:
            print(f"[✓] Columnas añadidas: {', '.join(added)}")
        else:
            print("[=] No había columnas pendientes por añadir.")

        # Verificación
        final_cols = _existing_columns(cur, "users")
        print(f"[i] Columnas actuales en 'users': {', '.join(sorted(final_cols))}")

    except Exception as e:
        try:
            cur.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
