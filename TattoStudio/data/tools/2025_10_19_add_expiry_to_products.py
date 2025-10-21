import sqlite3
con = sqlite3.connect("dev.db")
cur = con.cursor()
cur.execute("PRAGMA table_info(products)")
cols = [r[1] for r in cur.fetchall()]
if "fechacaducidad" not in cols:
    cur.execute("ALTER TABLE products ADD COLUMN fechacaducidad TEXT")  # "YYYY-MM-DD" o NULL
    print("Columna agregada: fechacaducidad TEXT")
con.commit(); con.close()
