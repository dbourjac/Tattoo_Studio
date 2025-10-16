import sqlite3

DB = "dev.db"
TABLE = "portfolio_items"

def has_col(cur, table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1].lower() == col.lower() for r in cur.fetchall())

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    if not has_col(cur, TABLE, "user_id"):
        cur.execute(f"ALTER TABLE {TABLE} ADD COLUMN user_id INTEGER")
        print("Columna user_id agregada.")
    else:
        print("user_id ya existe; no se modifica.")

    # índice útil para filtros
    cur.execute("CREATE INDEX IF NOT EXISTS ix_portfolio_user ON portfolio_items(user_id)")
    con.commit(); con.close()
    print("Listo.")

if __name__ == "__main__":
    main()
