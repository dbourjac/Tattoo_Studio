from data.db.session import init_db, engine
from sqlalchemy import text

def test_db_creates_tables():
    init_db()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = {r[0] for r in rows}
        for t in ["clients","artists","sessions","transactions","products","users","settings","portfolio_items"]:
            assert t in tables
