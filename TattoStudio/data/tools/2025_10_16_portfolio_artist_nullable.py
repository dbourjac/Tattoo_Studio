import sqlite3
DB = "dev.db"; TABLE = "portfolio_items"

def main():
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute(f"PRAGMA table_info({TABLE})")
    cols = cur.fetchall()
    artist = [c for c in cols if c[1].lower() == "artist_id"]
    if artist and artist[0][3] == 0:
        print("artist_id ya es nullable."); return

    cur.execute(f"PRAGMA index_list({TABLE})")
    idx_sql = []
    for _, name, *_ in cur.fetchall():
        cur.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (name,))
        row = cur.fetchone()
        if row and row[0]: idx_sql.append(row[0])

    def col_sql(c):
        _, name, typ, notnull, dflt, pk = c
        if name.lower() == "artist_id": notnull = 0
        parts = [name] + ([typ] if typ else [])
        if pk: parts.append("PRIMARY KEY")
        if not pk and notnull: parts.append("NOT NULL")
        if dflt is not None: parts.append(f"DEFAULT {dflt}")
        return " ".join(parts)

    cols_sql = ", ".join(col_sql(c) for c in cols)
    cur.execute(f"CREATE TABLE {TABLE}__new ({cols_sql})")
    names = ", ".join(c[1] for c in cols)
    cur.execute(f"INSERT INTO {TABLE}__new ({names}) SELECT {names} FROM {TABLE}")
    cur.execute("PRAGMA foreign_keys=off")
    cur.execute(f"DROP TABLE {TABLE}")
    cur.execute(f"ALTER TABLE {TABLE}__new RENAME TO {TABLE}")
    cur.execute("PRAGMA foreign_keys=on")
    for sql in idx_sql:
        try: cur.execute(sql)
        except: pass
    con.commit(); con.close(); print("artist_id ahora es NULLABLE.")

if __name__ == "__main__":
    main()
