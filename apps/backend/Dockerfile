FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Build context is monorepo root (see docker-compose.yml).
COPY apps/backend/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY apps/backend/ /app/
# Same catalog JSON as the UI (single source of truth for alignment tests in Docker).
COPY apps/frontend/src/data/rule-catalog.json /app/frontend-data/rule-catalog.json

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
