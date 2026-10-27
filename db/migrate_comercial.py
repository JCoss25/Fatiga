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


def ensure_column(cur, database: str, table: str, column: str, ddl: str):
    """Agrega una columna solo si no existe (MySQL no soporta IF NOT EXISTS)."""
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s AND column_name = %s",
        (database, table, column),
    )
    if cur.fetchone()[0] == 0:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        print(f"  + columna {table}.{column} agregada")
    else:
        print(f"  = columna {table}.{column} ya existe")


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
        # Actualiza instalaciones que ya tenian las tablas antes de los
        # estados COMPRADO/CERRADO y de las fechas de seguimiento.
        # Si el usuario no tiene ALTER, se avisa y se continua: en una tabla
        # recien creada las columnas y el enum ya vienen correctos.
        for column, ddl in (
            ("aprobacion_notificada_en", "DATETIME NULL"),
            ("comprado_en", "DATETIME NULL"),
            ("cerrado_en", "DATETIME NULL"),
        ):
            try:
                ensure_column(cur, name, "cot_solicitudes", column, ddl)
            except pymysql.MySQLError as e:
                print(f"  [!] No se pudo asegurar {column} (codigo {e.args[0]}); se requiere admin")
        try:
            cur.execute(
                "ALTER TABLE cot_solicitudes MODIFY estatus "
                "ENUM('BORRADOR','PENDIENTE','APROBADA','COMPRADO','CERRADO','RECHAZADA','CANCELADA') "
                "NOT NULL DEFAULT 'BORRADOR'"
            )
            print("  [ok] estatus con COMPRADO/CERRADO")
        except pymysql.MySQLError as e:
            print(
                f"  [!] No se pudo actualizar el enum de estatus (codigo {e.args[0]}); "
                "si la tabla ya existia, ejecutalo con un usuario admin"
            )

        cur.execute("SHOW TABLES LIKE 'cot_%'")
        print("\nTablas cot_:", [r[0] for r in cur.fetchall()])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
