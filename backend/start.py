import os
import sys

# backend/ directory ko Python import path mein ensure karo
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import text

from api import models  # noqa: F401
from api.db import Base, create_tables, engine


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