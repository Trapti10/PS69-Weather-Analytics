FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY src ./src

ENV PYTHONPATH=/app/backend:/app/src

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health')" || exit 1

CMD sh -c 'python -c "from api import models; from api.db import Base, create_tables, engine; print(\"MODELS:\", list(Base.metadata.tables.keys()), flush=True); create_tables(); print(\"TABLES CREATED:\", list(Base.metadata.tables.keys()), flush=True); print(\"DB TABLES:\", [r[0] for r in engine.connect().execute(__import__(\"sqlalchemy\").text(\"SELECT tablename FROM pg_tables WHERE schemaname = '\\''public'\\'' ORDER BY tablename\"))], flush=True)" && uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}'