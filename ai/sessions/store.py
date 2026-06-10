"""Conversation session storage.

Two separate concerns:
1. Transcript (system of record) — the FULL conversation, unbounded, persisted
   so the user can scroll back.
2. Context window — only the last N turns, fed to the LLM to bound prompt size.
   The model not seeing older turns does NOT delete them.

Backends (same interface):
- InMemorySessionStore — per-process dict; lost on restart. Dev/testing only.
- SqlSessionStore      — durable; SQLite by default or any SQLAlchemy URL
                         (e.g. Postgres). A SEPARATE datastore; the app DB is
                         never written to.

Use build_session_store() to construct the configured backend.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Optional

from ai.config import settings


def _now() -> datetime:
    # Current UTC timestamp.
    return datetime.now(timezone.utc)


class InMemorySessionStore:
    # Ephemeral per-process store; full transcript kept in memory (unbounded).
    def __init__(self) -> None:
        self._data: dict[str, list[dict]] = {}
        self._lock = threading.Lock()

    def append(
        self,
        session_id: str,
        user_msg: str,
        assistant_msg: str,
        metadata: Optional[dict] = None,
    ) -> None:
        # Inputs: session_id, user_msg, assistant_msg, metadata (assistant-turn extras).
        if not session_id:
            return
        ts = _now().isoformat()
        with self._lock:
            hist = self._data.setdefault(session_id, [])
            hist.append({"role": "user", "content": user_msg, "created_at": ts, "metadata": None})
            hist.append({
                "role": "assistant",
                "content": assistant_msg,
                "created_at": ts,
                "metadata": metadata or None,
            })

    def get_context(self, session_id: str, max_turns: int) -> list[dict]:
        # Inputs: session_id, max_turns (exchanges to return). Returns [{role, content}].
        if not session_id:
            return []
        with self._lock:
            hist = self._data.get(session_id, [])
            tail = hist[-max_turns * 2:] if max_turns > 0 else hist
            return [{"role": m["role"], "content": m["content"]} for m in tail]

    def get_transcript(
        self, session_id: str, limit: Optional[int] = None, offset: int = 0
    ) -> list[dict]:
        # Inputs: session_id, limit (page size; None = all), offset (start index).
        # Returns the full stored transcript (oldest first), optionally paginated.
        if not session_id:
            return []
        with self._lock:
            hist = list(self._data.get(session_id, []))
        if offset:
            hist = hist[offset:]
        if limit is not None:
            hist = hist[:limit]
        return hist

    def reset(self, session_id: str) -> None:
        # Input: session_id. Drops the entire conversation.
        with self._lock:
            self._data.pop(session_id, None)


class SqlSessionStore:
    # Durable store on SQLAlchemy (SQLite default or Postgres). Owns its own
    # chat_messages table; never touches the application's tables.
    def __init__(self, db_url: str) -> None:
        # Input: db_url (SQLAlchemy URL). Creates the engine + chat_messages table.
        from sqlalchemy import (
            create_engine,
            MetaData,
            Table,
            Column,
            BigInteger,
            Integer,
            String,
            Text,
            DateTime,
            Index,
        )

        connect_args = {}
        if db_url.startswith("sqlite"):
            # Allow use across FastAPI's threadpool.
            connect_args = {"check_same_thread": False}

        self._engine = create_engine(db_url, connect_args=connect_args, future=True)
        self._meta = MetaData()
        # Integer PK is portable (autoincrement on SQLite, serial on Postgres).
        self._messages = Table(
            "chat_messages",
            self._meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", String(128), nullable=False),
            Column("role", String(16), nullable=False),
            Column("content", Text, nullable=False),
            Column("metadata_json", Text, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False, default=_now),
            Index("ix_chat_messages_session", "session_id", "id"),
        )
        self._meta.create_all(self._engine)

    def append(
        self,
        session_id: str,
        user_msg: str,
        assistant_msg: str,
        metadata: Optional[dict] = None,
    ) -> None:
        # Inputs: session_id, user_msg, assistant_msg, metadata (assistant-turn extras).
        if not session_id:
            return
        ts = _now()
        from sqlalchemy import insert

        rows = [
            {"session_id": session_id, "role": "user", "content": user_msg,
             "metadata_json": None, "created_at": ts},
            {"session_id": session_id, "role": "assistant", "content": assistant_msg,
             "metadata_json": json.dumps(metadata) if metadata else None, "created_at": ts},
        ]
        with self._engine.begin() as conn:
            conn.execute(insert(self._messages), rows)

    def get_context(self, session_id: str, max_turns: int) -> list[dict]:
        # Inputs: session_id, max_turns. Returns the last turns as [{role, content}].
        if not session_id:
            return []
        from sqlalchemy import select

        t = self._messages
        stmt = select(t.c.role, t.c.content).where(t.c.session_id == session_id).order_by(t.c.id.desc())
        if max_turns > 0:
            stmt = stmt.limit(max_turns * 2)
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).all()
        # Fetched newest-first; reverse to chronological order for the prompt.
        return [{"role": r.role, "content": r.content} for r in reversed(rows)]

    def get_transcript(
        self, session_id: str, limit: Optional[int] = None, offset: int = 0
    ) -> list[dict]:
        # Inputs: session_id, limit (page size; None = all), offset (start index).
        # Returns the full transcript (oldest first) with timestamps + metadata.
        if not session_id:
            return []
        from sqlalchemy import select

        t = self._messages
        stmt = select(t).where(t.c.session_id == session_id).order_by(t.c.id.asc())
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).all()
        out = []
        for r in rows:
            out.append({
                "role": r.role,
                "content": r.content,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "metadata": json.loads(r.metadata_json) if r.metadata_json else None,
            })
        return out

    def reset(self, session_id: str) -> None:
        # Input: session_id. Deletes all rows for that conversation.
        from sqlalchemy import delete

        t = self._messages
        with self._engine.begin() as conn:
            conn.execute(delete(t).where(t.c.session_id == session_id))


def build_session_store():
    # Construct the configured store: SESSION_BACKEND=memory -> InMemory;
    # sqlite/postgres/sql -> SqlSessionStore(SESSION_DB_URL). Falls back to
    # in-memory if the durable backend can't be initialized.
    backend = (settings.session_backend or "sqlite").strip().lower()
    if backend in ("memory", "inmemory", "none"):
        return InMemorySessionStore()
    try:
        return SqlSessionStore(settings.session_db_url)
    except Exception:
        return InMemorySessionStore()


# Backwards-compatible alias.
SessionStore = InMemorySessionStore
