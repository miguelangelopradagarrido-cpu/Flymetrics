FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    PYTHONPATH="/app:/app/backend"

WORKDIR /app

# Instalar certificados y dependencias mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Instalar librerías usando ruedas binarias precompiladas (evita compilar Rust/C en CPU limitada)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copiar el código del proyecto (optimizado por .dockerignore)
COPY . .

# Exponer puerto estándar de Hostless
EXPOSE 8000

# Iniciar la aplicación
CMD ["sh", "-c", "cd /app/backend && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
