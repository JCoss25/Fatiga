"""Conexion del modulo Comercial (tablas cot_*).

Usa su propia metadata/engine para no mezclarse con las tablas de fatiga/sst.

- Local por defecto: COT_DATABASE_URL=sqlite:///./comercial_local.db
- AWS/produccion: si no existe COT_DATABASE_URL, reutiliza la conexion MySQL
  del proyecto (DB_* o DB_SECRET_ARN).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parents[2]  # app-fatiga/
load_dotenv(ROOT / ".env")

COT_DATABASE_URL = os.getenv("COT_DATABASE_URL", "").strip()


def _database_url() -> str:
    if COT_DATABASE_URL:
        url = COT_DATABASE_URL
        # Normaliza rutas SQLite relativas para que no dependan del cwd.
        if url.startswith("sqlite:///./"):
            url = "sqlite:///" + (ROOT / url[len("sqlite:///./"):]).as_posix()
        return url
    # Produccion: misma base MySQL/RDS del proyecto, tablas cot_*.
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
