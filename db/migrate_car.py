"""Migración del módulo CAR (tablas car_*).

- SQLite local: crea las tablas con SQLAlchemy y siembra áreas iniciales.
- MySQL/RDS: ejecuta db/car_schema.sql con las credenciales admin.

Uso:
    python db/migrate_car.py
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from backend.car.db import AREAS_SEED, Base, engine  # noqa: E402
from backend.car import models  # noqa: E402,F401


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
    (ROOT / "data" / "car_evidencias").mkdir(parents=True, exist_ok=True)

    if engine.url.get_backend_name() == "sqlite":
        from backend.car.db import SessionLocal
        from backend.car.models import CarArea

        Base.metadata.create_all(engine)
        db = SessionLocal()
        try:
            existentes = {a.nombre for a in db.query(CarArea).all()}
            for nombre in AREAS_SEED:
                if nombre not in existentes:
                    db.add(CarArea(nombre=nombre, activo=1))
            db.commit()
        finally:
            db.close()
        print(f"Tablas CAR creadas/verificadas en SQLite: {engine.url.database}")
        return

    import pymysql

    host = os.getenv("DB_HOST")
    port = int(os.getenv("DB_PORT", "3306"))
    name = os.getenv("DB_NAME", "kogn1v1s")
    user = os.getenv("DB_ADMIN_USER") or os.getenv("DB_USER")
    password = os.getenv("DB_ADMIN_PASSWORD") or os.getenv("DB_PASSWORD")
    if not host or not user or not password:
        sys.exit("Faltan datos de conexión en el archivo .env")

    sql_text = (ROOT / "db" / "car_schema.sql").read_text(encoding="utf-8")
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
                print(f"  [!] Omitida (código {e.args[0]}): {first}...")
        cur.execute("SHOW TABLES LIKE 'car_%'")
        print("\nTablas car_:", [r[0] for r in cur.fetchall()])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
