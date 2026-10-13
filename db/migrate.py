"""
Migracion: crea las tablas del test de fatiga en la base kogn1v1s.

Usa las credenciales de ADMIN (DB_ADMIN_USER / DB_ADMIN_PASSWORD del .env),
porque crear tablas requiere permisos DDL.

Uso:
    python db/migrate.py
"""
import os
import re
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

HOST = os.getenv("DB_HOST")
PORT = int(os.getenv("DB_PORT", "3306"))
NAME = os.getenv("DB_NAME", "kogn1v1s")
USER = os.getenv("DB_ADMIN_USER") or os.getenv("DB_USER")
PASSWORD = os.getenv("DB_ADMIN_PASSWORD") or os.getenv("DB_PASSWORD")


def statements(sql_text: str):
    """Separa el script en sentencias, ignorando comentarios."""
    lines = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or stripped == "":
            continue
        lines.append(line)
    clean = "\n".join(lines)
    for stmt in clean.split(";"):
        stmt = stmt.strip()
        if stmt:
            yield stmt


def ensure_column(cur, table: str, column: str, ddl: str):
    """Agrega una columna solo si no existe (MySQL no soporta IF NOT EXISTS)."""
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s AND column_name = %s",
        (NAME, table, column),
    )
    if cur.fetchone()[0] == 0:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        print(f"  + columna {table}.{column} agregada")
    else:
        print(f"  = columna {table}.{column} ya existe")


def main():
    if not HOST or not USER or not PASSWORD:
        sys.exit("Faltan datos de conexion en el archivo .env")

    sql_text = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    print(f"Conectando a {HOST} como {USER} ...")
    conn = pymysql.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD,
        database=NAME, charset="utf8mb4", autocommit=True,
    )
    cur = conn.cursor()
    n = 0
    try:
        for stmt in statements(sql_text):
            first = re.sub(r"\s+", " ", stmt)[:70]
            try:
                cur.execute(stmt)
                n += 1
                print(f"  [{n}] OK  {first}...")
            except pymysql.MySQLError as e:
                print(f"  [!] Omitida (codigo {e.args[0]}): {first}...")
        cur.execute("SELECT COUNT(*) FROM fatiga_preguntas")
        print(f"\nMigracion completa. Preguntas en catalogo: {cur.fetchone()[0]}")
        cur.execute("SHOW TABLES LIKE 'fatiga_%'")
        print("Tablas fatiga_:", [r[0] for r in cur.fetchall()])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
