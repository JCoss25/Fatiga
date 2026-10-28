"""Zona horaria oficial de la aplicacion: America/Monterrey (UTC-6)."""
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Monterrey")


def ahora() -> datetime:
    """Fecha/hora local de Monterrey, sin tzinfo (para guardar en MySQL DATETIME)."""
    return datetime.now(TZ).replace(tzinfo=None)


def hoy():
    """Fecha local de Monterrey."""
    return datetime.now(TZ).date()
