"""Conexion del modulo CAR (tablas car_*).

- Local por defecto: `CAR_DATABASE_URL=sqlite:///./car_local.db`
- Produccion: si no existe `CAR_DATABASE_URL`, reutiliza la conexion MySQL/RDS
  del proyecto (DB_* o DB_SECRET_ARN).

La base local permite revisar y probar el flujo completo sin RDS. En produccion
las tablas se crean con `python db/migrate_car.py`.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parents[2]  # app-fatiga/
load_dotenv(ROOT / ".env")

CAR_DATABASE_URL = os.getenv("CAR_DATABASE_URL", "").strip()


def _database_url() -> str:
    if CAR_DATABASE_URL:
        url = CAR_DATABASE_URL
        if url.startswith("sqlite:///./"):
            url = "sqlite:///" + (ROOT / url[len("sqlite:///./"):]).as_posix()
        return url
    from ..db import build_url

    return build_url()


URL = _database_url()

if URL.startswith("sqlite"):
    engine = create_engine(
        URL,
        connect_args={"check_same_thread": False},
        future=True,
    )
else:
    engine = create_engine(
        URL,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"connect_timeout": 5, "read_timeout": 15, "write_timeout": 15},
        future=True,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_local_schema() -> None:
    """Crea las tablas cuando se usa SQLite local.

    No siembra áreas: el administrador las captura desde
    Panel → Catálogos → Áreas / departamentos CAR.

    En MySQL/RDS no se ejecuta: las tablas se crean con db/migrate_car.py.
    """
    if engine.url.get_backend_name() != "sqlite":
        return

    from . import models  # registra las tablas en Base.metadata

    Base.metadata.create_all(engine)
