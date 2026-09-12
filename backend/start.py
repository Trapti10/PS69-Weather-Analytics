import os
import sys

from api import models
from api.db import Base, create_tables, engine
from sqlalchemy import text

print("=== DATABASE INITIALIZATION ===", flush=True)
print("MODELS:", list(Base.metadata.tables.keys()), flush=True)

create_tables()

with engine.connect() as conn:
    tables = [
        row[0]
        for row in conn.execute(
            text(
                "SELECT tablename "
                "FROM pg_tables "
                "WHERE schemaname = 'public' "
                "ORDER BY tablename"
            )
        )
    ]

print("DB TABLES:", tables, flush=True)
print("=== DATABASE INITIALIZATION COMPLETE ===", flush=True)

os.execvp(
    "uvicorn",
    [
        "uvicorn",
        "api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        os.environ.get("PORT", "8000"),
    ],
)