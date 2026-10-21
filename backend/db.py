"""Configuracion de la base de datos (SQLAlchemy + MySQL/RDS).

Local:    toma los datos del archivo .env
En AWS:   si existe la variable DB_SECRET_ARN, toma usuario/contraseña/host
          desde AWS Secrets Manager (recomendado en produccion).
"""
import json
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _load_secret() -> dict:
    """Lee el secreto de AWS Secrets Manager si DB_SECRET_ARN esta definido."""
    arn = os.getenv("DB_SECRET_ARN")
    if not arn:
        return {}
    try:
        import boto3  # solo disponible/necesario en AWS
    except ImportError:
        return {}
    client = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION"))
    value = client.get_secret_value(SecretId=arn)["SecretString"]
    return json.loads(value)


_SECRET = _load_secret()


def _cfg(env_key: str, secret_keys, default: str = "") -> str:
    """Prioriza el secreto de AWS, luego el .env, luego el default."""
    for k in secret_keys:
        if _SECRET.get(k):
            return str(_SECRET[k])
    return os.getenv(env_key, default)


DB_HOST = _cfg("DB_HOST", ["DB_HOST", "host"])
DB_PORT = _cfg("DB_PORT", ["DB_PORT", "port"], "3306")
DB_NAME = _cfg("DB_NAME", ["DB_NAME", "dbname", "database"], "kogn1v1s")
DB_USER = _cfg("DB_USER", ["DB_USER", "username", "user"], "kogn_rw")
DB_PASSWORD = _cfg("DB_PASSWORD", ["DB_PASSWORD", "password"])
DB_SSL = _cfg("DB_SSL", ["DB_SSL"], "disabled").lower()


def build_url() -> str:
    pwd = quote_plus(DB_PASSWORD)
    return (
        f"mysql+pymysql://{DB_USER}:{pwd}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        f"?charset=utf8mb4"
    )


connect_args = {
    # La app debe fallar rapido si RDS/la red no responden; el default de
    # PyMySQL puede dejar la peticion colgada mas de 10 s.
    "connect_timeout": 5,
    "read_timeout": 15,
    "write_timeout": 15,
}
if DB_SSL == "required":
    # TLS habilitado (sin verificacion estricta de CA).
    connect_args["ssl"] = {"check_hostname": False}

engine = create_engine(
    build_url(),
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args=connect_args,
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
