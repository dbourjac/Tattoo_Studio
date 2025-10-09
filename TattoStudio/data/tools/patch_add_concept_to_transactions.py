# data/tools/patch_add_concept_to_transactions.py
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterable, Tuple

# ========== Config ==========
# Ruta por defecto: dev.db en la raíz del repo. Puedes sobreescribir con la env var TATTOO_DB
DB_PATH = Path(os.environ.get("TATTOO_DB", "dev.db"))

TABLE = "transactions"
COLUMN = "concept"
COLUMN_DEF = "TEXT NOT NULL DEFAULT ''"   # estable, no rompe filas existentes


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,)
    )
    return cur.fetchone() is not None


def _columns(conn: sqlite3.Connection, table: str) -> Iterable[Tuple[int, str, str, int, str, int]]:
    # cid, name, type, notnull, dflt_value, pk
    return conn.execute(f"PRAGMA table_info({table});").fetchall()


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(col[1] == column for col in _columns(conn, table))


def apply_patch(conn: sqlite3.Connection) -> str:
    if not _table_exists(conn, TABLE):
        return f"[SKIP] La tabla '{TABLE}' no existe en {DB_PATH.resolve()}"

    if _column_exists(conn, TABLE, COLUMN):
        return f"[OK] La columna '{COLUMN}' ya existe en '{TABLE}'. Nada que hacer."

    # ALTER idempotente: añade la columna con default
    conn.execute(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} {COLUMN_DEF};")
    return f"[DONE] Añadida columna '{COLUMN} {COLUMN_DEF}' a '{TABLE}'."


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"[ERROR] No se encontró la base de datos en: {DB_PATH.resolve()} "
                         f"(puedes definir TATTOO_DB=/ruta/a/tu.db)")

    # Conexión + foreign keys
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        msg = apply_patch(conn)
        conn.commit()
        print(msg)

        # Diagnóstico: lista de columnas tras patch
        cols = [c[1] for c in _columns(conn, TABLE)]
        print(f"[INFO] Columnas actuales en '{TABLE}': {cols}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
