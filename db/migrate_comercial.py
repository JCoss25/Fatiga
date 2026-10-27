"""
Migracion del modulo Comercial (tablas cot_*).

- SQLite local: crea las tablas con SQLAlchemy.
- MySQL/RDS: ejecuta db/comercial_schema.sql con las credenciales admin.

Uso:
    python db/migrate_comercial.py
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from backend.comercial.db import Base, engine  # noqa: E402
from backend.comercial import models  # noqa: E402,F401

SEED = [
    ("tipo_servicio", "Reparación"),
    ("tipo_servicio", "Mantenimiento correctivo"),
    ("tipo_servicio", "Mantenimiento preventivo"),
    ("tipo_servicio", "Suministro"),
    ("tipo_servicio", "Servicio externo"),
    ("ubicacion", "TOT LC"),
    ("ubicacion", "TOT NDVC"),
]


def statements(sql_text: str):
    lines = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or stripped == "":
            continue
        lines.append(line)
    for stmt in "\n".join(lines).split(";"):
        stmt = stmt.strip()
        if stmt:
            yield stmt


def main():
    if engine.url.get_backend_name() == "sqlite":
        from backend.comercial.db import SessionLocal
        from backend.comercial.models import CotCatalogo

        Base.metadata.create_all(engine)
        db = SessionLocal()
        try:
            for tipo, valor in SEED:
                exists = (
                    db.query(CotCatalogo)
                    .filter(CotCatalogo.tipo == tipo, CotCatalogo.valor == valor)
                    .first()
                )
                if not exists:
                    db.add(CotCatalogo(tipo=tipo, valor=valor, activo=1))
            db.commit()
        finally:
            db.close()
        print(f"Tablas creadas/verificadas en SQLite: {engine.url.database}")
        return

    import pymysql

    host = os.getenv("DB_HOST")
    port = int(os.getenv("DB_PORT", "3306"))
    name = os.getenv("DB_NAME", "kogn1v1s")
    user = os.getenv("DB_ADMIN_USER") or os.getenv("DB_USER")
    password = os.getenv("DB_ADMIN_PASSWORD") or os.getenv("DB_PASSWORD")
    if not host or not user or not password:
        sys.exit("Faltan datos de conexion en el archivo .env")

    sql_text = (ROOT / "db" / "comercial_schema.sql").read_text(encoding="utf-8")
    print(f"Conectando a {host} como {user} ...")
    conn = pymysql.connect(
        host=host, port=port, user=user, password=password,
        database=name, charset="utf8mb4", autocommit=True,
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
        cur.execute("SHOW TABLES LIKE 'cot_%'")
        print("\nTablas cot_:", [r[0] for r in cur.fetchall()])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
