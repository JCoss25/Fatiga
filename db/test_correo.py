"""
Prueba de envio de correo del modulo Comercial.

Uso:
    python db/test_correo.py
    python db/test_correo.py destinatario@gmail.com

Si CORREO_SIMULADO=1, solo imprime el correo en consola.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from backend.comercial.correo import APP_URL, SMTP_FROM, SMTP_HOST, enviar  # noqa: E402


def main():
    destinatario = sys.argv[1] if len(sys.argv) > 1 else os.getenv("APROBADOR_EMAIL", "")
    if not destinatario:
        sys.exit("Indica un destinatario o define APROBADOR_EMAIL en .env")

    print(f"SMTP_HOST: {SMTP_HOST or '(vacio)'}")
    print(f"SMTP_FROM: {SMTP_FROM or '(vacio)'}")
    print(f"APP_URL:   {APP_URL}")
    print(f"Para:      {destinatario}")
    estado, error = enviar(
        destinatario,
        "Prueba de correo · Modulo Comercial",
        "Este es un correo de prueba del modulo Comercial (Cotizacion de danos).\n\n"
        f"Portal: {APP_URL}\n",
    )
    print(f"Resultado: {estado}")
    if error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()
