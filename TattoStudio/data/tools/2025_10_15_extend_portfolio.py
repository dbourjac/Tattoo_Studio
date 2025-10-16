import sqlite3

DB = "dev.db"

COLS = [
    ("client_id", "INTEGER"),
    ("session_id", "INTEGER"),
    ("transaction_id", "INTEGER"),
    ("is_public", "INTEGER NOT NULL DEFAULT 1"),
    ("is_cover", "INTEGER NOT NULL DEFAULT 0"),
    ("style", "TEXT"),
    ("body_area", "TEXT"),
    ("color_mode", "TEXT"),
    ("fresh_or_healed", "TEXT"),
    ("thumb_path", "TEXT"),
]

INDEXES = [
    ("ix_portfolio_artist", "artist_id"),
    ("ix_portfolio_client", "client_id"),
    ("ix_portfolio_session", "session_id"),
    ("ix_portfolio_created", "created_at"),
    ("ix_portfolio_public", "is_public"),
    ("ix_portfolio_style", "style"),
    ("ix_portfolio_body_area", "body_area"),
    ("ix_portfolio_color_mode", "color_mode"),
    ("ix_portfolio_fresh_healed", "fresh_or_healed"),
]

def has_column(cur, table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1].lower() == col.lower() for r in cur.fetchall())

def has_index(cur, name):
    cur.execute("PRAGMA index_list(portfolio_items)")
    return any(r[1].lower() == name.lower() for r in cur.fetchall())

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    for col, decl in COLS:
        if not has_column(cur, "portfolio_items", col):
            cur.execute(f"ALTER TABLE portfolio_items ADD COLUMN {col} {decl}")
    for ix, col in INDEXES:
        if not has_index(cur, ix):
            cur.execute(f"CREATE INDEX {ix} ON portfolio_items({col})")
    con.commit()
    con.close()

if __name__ == "__main__":
    main()
