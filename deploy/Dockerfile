# Imagen de la aplicacion del Test de Fatiga Laboral
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias primero (mejor cache de capas)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Codigo de la aplicacion
COPY backend ./backend
COPY frontend ./frontend
COPY db ./db

EXPOSE 8000

# AWS App Runner / ECS inyectan la variable PORT
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
