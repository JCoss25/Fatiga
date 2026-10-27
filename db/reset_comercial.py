"""
Borra todos los registros del modulo Comercial (solicitudes, comentarios,
adjuntos y correos). Conserva los catalogos base para que el formulario
siga funcionando.

Uso:
    python db/reset_comercial.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.comercial.db import SessionLocal  # noqa: E402
from backend.comercial.models import (  # noqa: E402
    CotAdjunto,
    CotComentario,
    CotCorreo,
    CotSolicitud,
)


def main():
    db = SessionLocal()
    try:
        # Orden por llaves foraneas: primero los hijos.
        for model in (CotCorreo, CotAdjunto, CotComentario, CotSolicitud):
            n = db.query(model).delete()
            print(f"  {model.__tablename__}: {n} registro(s) borrado(s)")
        db.commit()
        print("Modulo Comercial vacio. Catalogos conservados.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
