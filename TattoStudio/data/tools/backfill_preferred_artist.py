# data/tools/backfill_preferred_artist.py
from __future__ import annotations
from pathlib import Path
import sqlite3
from datetime import datetime

DB_PATH = Path("./dev.db")

def table_has_column(cur, table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table});")
    return any(r[1] == col for r in cur.fetchall())

def main():
    if not DB_PATH.exists():
        print(f"[!] No encontré la BD en {DB_PATH.resolve()}")
        return

    con = sqlite3.connect(str(DB_PATH))
    con.execute("PRAGMA foreign_keys=ON;")
    cur = con.cursor()

    if not table_has_column(cur, "clients", "preferred_artist_id"):
        print("[!] clients.preferred_artist_id no existe. Corre primero la migración.")
        con.close()
        return

    now = datetime.now().isoformat(" ")
    # Clientes sin preferencia aún
    cur.execute("SELECT id FROM clients WHERE preferred_artist_id IS NULL;")
    rows = cur.fetchall()
    print(f"[info] clientes sin preferred_artist_id: {len(rows)}")

    updated = 0
    for (cid,) in rows:
        # Próxima cita
        cur.execute("""
          SELECT artist_id, start FROM sessions
          WHERE client_id = ? AND start >= ?
          ORDER BY start ASC LIMIT 1
        """, (cid, now))
        next_row = cur.fetchone()

        artist_id = None
        if next_row:
            artist_id = next_row[0]
        else:
            # Última cita
            cur.execute("""
              SELECT artist_id, start FROM sessions
              WHERE client_id = ? AND start < ?
              ORDER BY start DESC LIMIT 1
            """, (cid, now))
            last_row = cur.fetchone()
            if last_row:
                artist_id = last_row[0]

        if artist_id is not None:
            cur.execute("UPDATE clients SET preferred_artist_id = ? WHERE id = ?", (artist_id, cid))
            updated += 1

    con.commit()
    con.close()
    print(f"[backfill] preferred_artist_id actualizado en {updated} clientes.")

if __name__ == "__main__":
    main()
