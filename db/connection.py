"""SQLAlchemy engine for the Supabase Postgres app database (READ-ONLY use).

The AI layer never writes to this database. Credentials come from env. We use
NullPool + pgbouncer-friendly settings, matching the original engine.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def build_engine() -> Engine:
    host = _require("DB_HOST")
    port = os.getenv("DB_PORT", "6543")
    name = _require("DB_NAME")
    user = _require("DB_USER")
    password = _require("DB_PASSWORD")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    return create_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "sslmode": "require",
            "prepare_threshold": None,  # required for pgbouncer transaction mode
            "options": "-c search_path=public",
        },
        future=True,
    )
