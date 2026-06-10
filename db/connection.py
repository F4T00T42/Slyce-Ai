"""SQLAlchemy engine for the Postgres app database (used READ-ONLY)."""
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool


def _require(name: str) -> str:
    # Input: name (env var name). Returns its value or raises if unset/empty.
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def build_engine() -> Engine:
    # Reads DB_HOST/DB_PORT(6543)/DB_NAME/DB_USER/DB_PASSWORD from env.
    # NullPool + pgbouncer-friendly connect args; SSL required.
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
