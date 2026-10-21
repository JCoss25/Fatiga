"""Autenticacion de los reportes.

- Kiosco / formularios: publicos, sin contrasena.
- Panel de reportes: dos claves.
    * ADMIN_PASSWORD    -> rol "admin"
    * REVIEWER_PASSWORD -> rol "revisor" (solo consulta)
"""
import hmac
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Header, HTTPException

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "cambia_esta_clave")
REVIEWER_PASSWORD = os.getenv("REVIEWER_PASSWORD", "")


def role_for(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    if ADMIN_PASSWORD and hmac.compare_digest(token, ADMIN_PASSWORD):
        return "admin"
    if REVIEWER_PASSWORD and hmac.compare_digest(token, REVIEWER_PASSWORD):
        return "revisor"
    return None


def require_reports(x_admin_token: Optional[str] = Header(default=None)) -> str:
    """Admin o revisor: ambos pueden consultar los dos tipos de reportes."""
    role = role_for(x_admin_token)
    if not role:
        raise HTTPException(status_code=401, detail="Clave de reportes incorrecta")
    return role


def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> str:
    role = role_for(x_admin_token)
    if role != "admin":
        raise HTTPException(status_code=401, detail="Se requiere clave de administrador")
    return role
