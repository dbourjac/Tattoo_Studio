# data/tools/2025_10_16_sync_products_schema.py
import sqlite3

DB = "dev.db"
TABLE = "products"

COLUMNS = {
    "sku":       "TEXT",      # puedes luego crear UNIQUE si quieres
    "name":      "TEXT",
    "category":  "TEXT",
    "unidad":    "TEXT",
    "cost":      "REAL",
    "stock":     "INTEGER",
    "min_stock": "INTEGER",
    "caduca":    "INTEGER",   # 0/1
    "proveedor": "TEXT",      # OJO: 'proveedor' (con 'e')
    "activo":    "INTEGER"    # 0/1
}

CREATE_SQL = f"""
CREATE TABLE {TABLE} (
    id INTEGER PRIMARY KEY,
    sku TEXT,
    name TEXT,
    category TEXT,
    unidad TEXT,
    cost REAL,
    stock INTEGER,
    min_stock INTEGER,
    caduca INTEGER,
    proveedor TEXT,
    activo INTEGER
);
"""

def table_exists(cur, name):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def col_names(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    if not table_exists(cur, TABLE):
        cur.execute(CREATE_SQL)
        print(f"Tabla {TABLE} creada.")
    else:
        existing = set(col_names(cur, TABLE))
        for col, decl in COLUMNS.items():
            if col not in existing:
                cur.execute(f"ALTER TABLE {TABLE} ADD COLUMN {col} {decl}")
                print(f"Columna agregada: {col} {decl}")

        # Si existe vieja columna 'provedor', copiar a 'proveedor' si esta última está vacía
        try:
            if "proveedor" in existing or "proveedor" in COLUMNS:
                cur.execute("PRAGMA table_info(products)")
                names = [r[1] for r in cur.fetchall()]
                if "provedor" in names:
                    # copiar sólo filas donde proveedor está NULL
                    cur.execute("""
                        UPDATE products
                           SET proveedor = COALESCE(proveedor, provedor)
                         WHERE proveedor IS NULL
                    """)
                    print("Backfill proveedor desde 'provedor'.")
        except Exception as e:
            print("Aviso backfill proveedor:", e)

    # Índices útiles (no-únicos para no romper datos viejos)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_products_sku ON products(sku)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_products_category ON products(category)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_products_activo ON products(activo)")

    con.commit()
    con.close()
    print("Sincronización terminada.")

if __name__ == "__main__":
    main()
