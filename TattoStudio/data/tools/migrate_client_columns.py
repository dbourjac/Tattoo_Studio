# data/tools/migrate_client_columns.py
from __future__ import annotations
from pathlib import Path
import sqlite3

DB_PATH = Path("./dev.db")  # ajusta si tu DB vive en otra ruta
TABLE = "clients"

# Columnas nuevas para reflejar lo que pide new_client.py (todas opcionales/NULL)
CLIENT_COLS = [
    ("instagram", "TEXT"),
    ("city", "TEXT"),
    ("state", "TEXT"),
    ("gender", "TEXT"),
    ("birthdate", "DATE"),
    ("consent_info", "INTEGER"),      # 0/1
    ("consent_image", "INTEGER"),     # 0/1
    ("consent_data", "INTEGER"),      # 0/1
    ("emergency_name", "TEXT"),
    ("emergency_relation", "TEXT"),
    ("emergency_phone", "TEXT"),
    ("preferred_artist_id", "INTEGER"),
    # Salud (checkboxes + observaciones)
    ("health_allergies", "INTEGER"),
    ("health_diabetes", "INTEGER"),
    ("health_coagulation", "INTEGER"),
    ("health_epilepsy", "INTEGER"),
    ("health_cardiac", "INTEGER"),
    ("health_anticoagulants", "INTEGER"),
    ("health_preg_lact", "INTEGER"),
    ("health_substances", "INTEGER"),
    ("health_derm", "INTEGER"),
    ("health_obs", "TEXT"),
]

def column_exists(cur, table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table});")
    return any(row[1] == col for row in cur.fetchall())

def add_column_if_missing(cur, table: str, col: str, sqltype: str) -> None:
    if column_exists(cur, table, col):
        print(f"[=] {table}.{col} ya existe")
        return
    print(f"[+] ALTER TABLE {table} ADD COLUMN {col} {sqltype}")
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {sqltype};")

def main():
    if not DB_PATH.exists():
        print(f"[!] No encontré la BD en {DB_PATH.resolve()}")
        return

    con = sqlite3.connect(str(DB_PATH))
    con.execute("PRAGMA foreign_keys=ON;")
    cur = con.cursor()

    # Agregar columnas que falten
    for col, sqltype in CLIENT_COLS:
        add_column_if_missing(cur, TABLE, col, sqltype)

    # Índice útil para joins por artista preferido (no falla si no existe la col).
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_clients_pref_artist ON clients(preferred_artist_id);")
    except sqlite3.OperationalError:
        # Si la columna no existe aún por algún motivo, no interrumpimos.
        pass

    con.commit()
    con.close()
    print("[migrate] Listo.")

if __name__ == "__main__":
    main()
