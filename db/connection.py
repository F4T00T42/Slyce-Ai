import os
from functools import lru_cache
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


def _build_dsn() -> str:
    # Reads credentials from env and assembles a psycopg2 DSN with SSL.
    required = {
        "DB_HOST":     os.getenv("DB_HOST", ""),
        "DB_PORT":     os.getenv("DB_PORT", "6543"),
        "DB_NAME":     os.getenv("DB_NAME", ""),
        "DB_USER":     os.getenv("DB_USER", ""),
        "DB_PASSWORD": os.getenv("DB_PASSWORD", ""),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variable(s): {', '.join(missing)}\n"
            "Copy .env.example → .env and fill in your Supabase credentials."
        )

    # Strips accidental https:// prefix from host if present.
    host = required["DB_HOST"].removeprefix("https://").removeprefix("http://")

    # URL-encodes password to safely handle special characters.
    password = quote_plus(required["DB_PASSWORD"])

    return (
        f"postgresql+psycopg2://"
        f"{required['DB_USER']}:{password}"
        f"@{host}:{required['DB_PORT']}"
        f"/{required['DB_NAME']}"
        f"?sslmode=require"
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    # Returns a singleton engine. NullPool is used because Supabase's
    # PgBouncer (port 6543) already handles connection pooling.
    dsn = _build_dsn()

    engine = create_engine(
        dsn,
        poolclass=NullPool,
        connect_args={
            "options":             "-c search_path=public",
            "prepare_threshold":   None,   # required by PgBouncer transaction mode
            "keepalives":          1,
            "keepalives_idle":     30,
            "keepalives_interval": 5,
            "keepalives_count":    5,
        },
        echo=False,
    )

    # Validates credentials at startup rather than on the first real query.
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    return engine
