"""SQLAlchemy engine for the Postgres app database (used READ-ONLY).

Tuned for a connection pooler (e.g. Supabase Supavisor / pgbouncer on port
6543): NullPool (no client-side pooling), pre-ping to discard dead connections,
a connect timeout, and TCP keepalives. run_with_retry() retries transient
connection errors so a single stale pooler connection doesn't surface as a 500.
"""
import os
import time

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, InterfaceError, DBAPIError
from sqlalchemy.pool import NullPool

# Errors that usually mean "bad/dropped connection" and are safe to retry for
# read-only queries.
_TRANSIENT_ERRORS = (OperationalError, InterfaceError)

def _require(name: str) -> str:
    # Input: name (env var name). Returns its value or raises if unset/empty.
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val

def build_engine() -> Engine:
    # Reads DB_HOST/DB_PORT(6543)/DB_NAME/DB_USER/DB_PASSWORD from env.
    # NullPool + pre-ping + keepalives make pooler connections resilient; SSL required.
    host = _require("DB_HOST")
    port = os.getenv("DB_PORT", "6543")
    name = _require("DB_NAME")
    user = _require("DB_USER")
    password = _require("DB_PASSWORD")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    return create_engine(
        url,
        poolclass=NullPool,
        pool_pre_ping=True,  # validate (and replace) a connection before using it
        connect_args={
            "sslmode": "require",
            "connect_timeout": 10,
            # Keep idle pooler connections alive / detect drops quickly.
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
            "options": "-c search_path=public",
        },
        future=True,
    )

def run_with_retry(fn, attempts: int = 3, base_delay: float = 0.25):
    # Inputs: fn (zero-arg callable performing a read), attempts (max tries),
    # base_delay (seconds; exponential backoff). Retries only transient
    # connection errors; re-raises anything else immediately.
    last_exc = None
    for i in range(attempts):
        try:
            return fn()
        except _TRANSIENT_ERRORS as exc:
            last_exc = exc
            if i < attempts - 1:
                time.sleep(base_delay * (2 ** i))
        except DBAPIError as exc:
            # Retry only if SQLAlchemy flagged the connection as invalidated.
            if getattr(exc, "connection_invalidated", False) and i < attempts - 1:
                last_exc = exc
                time.sleep(base_delay * (2 ** i))
            else:
                raise
    raise last_exc
