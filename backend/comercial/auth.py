"""Autenticacion del modulo de Cotizacion de danos.

Dos roles con clave propia (definidas en .env):
    * SOLICITANTE_PASSWORD -> rol "solicitante"
    * APROBADOR_PASSWORD   -> rol "aprobador"

La identidad (nombre y correo) tambien se configura en .env. La clave viaja
en el header `X-Cot-Token`, igual que el panel de fatiga usa `X-Admin-Token`.
"""
import hmac
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Header, HTTPException

ROOT = Path(__file__).resolve().parents[2]  # app-fatiga/
load_dotenv(ROOT / ".env")

SOLICITANTE_PASSWORD = os.getenv("SOLICITANTE_PASSWORD", "")
APROBADOR_PASSWORD = os.getenv("APROBADOR_PASSWORD", "")

IDENTIDAD = {
    "solicitante": {
        "rol": "solicitante",
        "nombre": os.getenv("SOLICITANTE_NOMBRE", "Solicitante"),
        "email": os.getenv("SOLICITANTE_EMAIL", ""),
    },
    "aprobador": {
        "rol": "aprobador",
        "nombre": os.getenv("APROBADOR_NOMBRE", "Aprobador"),
        "email": os.getenv("APROBADOR_EMAIL", ""),
    },
}


def role_for(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    if SOLICITANTE_PASSWORD and hmac.compare_digest(token, SOLICITANTE_PASSWORD):
        return "solicitante"
    if APROBADOR_PASSWORD and hmac.compare_digest(token, APROBADOR_PASSWORD):
        return "aprobador"
    return None


def identidad(role: str) -> dict:
    return dict(IDENTIDAD.get(role, {"rol": role, "nombre": "", "email": ""}))


def require_any(x_cot_token: Optional[str] = Header(default=None)) -> str:
    role = role_for(x_cot_token)
    if not role:
        raise HTTPException(status_code=401, detail="Clave incorrecta")
    return role


def require_solicitante(x_cot_token: Optional[str] = Header(default=None)) -> str:
    role = role_for(x_cot_token)
    if role != "solicitante":
        raise HTTPException(status_code=401, detail="Se requiere la clave de solicitante")
    return role


def require_aprobador(x_cot_token: Optional[str] = Header(default=None)) -> str:
    role = role_for(x_cot_token)
    if role != "aprobador":
        raise HTTPException(status_code=401, detail="Se requiere la clave de aprobador")
    return role
