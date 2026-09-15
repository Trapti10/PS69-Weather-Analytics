import os
import sys

# Ensure the backend directory is importable as the root for the `api` package.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Ensure the Uvicorn process inherits the same import path.
existing_pythonpath = os.environ.get("PYTHONPATH", "")
paths = [BACKEND_DIR]

if existing_pythonpath:
    paths.append(existing_pythonpath)

os.environ["PYTHONPATH"] = os.pathsep.join(paths)

from sqlalchemy import text

from api import models  # noqa: F401
from api.db import Base, create_tables, engine


print("=== DATABASE INITIALIZATION ===", flush=True)

print("BACKEND_DIR:", BACKEND_DIR, flush=True)
print("PYTHONPATH:", os.environ.get("PYTHONPATH"), flush=True)
print("API IMPORT:", __import__("api").__file__, flush=True)
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