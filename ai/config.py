"""Central configuration loaded from environment variables.

Secrets are never hard-coded; copy .env.example to .env and fill values.
"""
import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv optional at runtime
    pass

@dataclass
class Settings:
    # --- LLM (provider-agnostic, OpenAI-compatible) ---
    # The LLM is reached through any OpenAI-compatible endpoint, so switching
    # providers/models is pure configuration (no code changes). Defaults target
    # Google Gemini's OpenAI-compatible API; point LLM_BASE_URL + LLM_MODEL at
    # Groq, Cerebras, GitHub Models, OpenRouter, a local server, etc. to switch.
    llm_base_url: str = field(
        default_factory=lambda: os.getenv(
            "LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
        )
    )
    # Provider API key. LLM_API_KEY wins; GEMINI_API_KEY / GROQ_API_KEY are
    # accepted as fallbacks so existing deployments keep working.
    llm_api_key: str = field(
        default_factory=lambda: (
            os.getenv("LLM_API_KEY", "")
            or os.getenv("GEMINI_API_KEY", "")
            or os.getenv("GROQ_API_KEY", "")
        )
    )
    llm_model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL", "gemini-2.0-flash")
    )
    llm_temperature: float = field(
        default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.2"))
    )
    max_tool_iterations: int = field(
        default_factory=lambda: int(os.getenv("MAX_TOOL_ITERATIONS", "6"))
    )
    # Transient-error retry policy for LLM calls (rate limits, timeouts, 5xx).
    # llm_max_retries is the number of RETRIES after the first attempt.
    llm_max_retries: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_RETRIES", "3"))
    )
    llm_retry_base_delay: float = field(
        default_factory=lambda: float(os.getenv("LLM_RETRY_BASE_DELAY", "0.5"))
    )
    # Kept for backward compatibility with any external tooling/scripts.
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))

    # --- Embeddings / RAG ---
    hf_token: str = field(default_factory=lambda: os.getenv("HF_TOKEN", ""))
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
    )
    # Qdrant vector store (separate AI datastore; main app DB stays untouched).
    qdrant_url: str = field(default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333"))
    qdrant_api_key: str = field(default_factory=lambda: os.getenv("QDRANT_API_KEY", ""))
    kb_collection: str = field(
        default_factory=lambda: os.getenv("KB_COLLECTION", "nutrition_kb")
    )
    rag_top_k: int = field(default_factory=lambda: int(os.getenv("RAG_TOP_K", "5")))
    rag_min_score: float = field(
        default_factory=lambda: float(os.getenv("RAG_MIN_SCORE", "0.5"))
    )

    # --- Web search (Tavily) ---
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))

    # --- Conversation sessions (separate datastore; app DB never written) ---
    # Backend: "sqlite" (durable, default), "postgres" (via session_db_url), or
    # "memory" (ephemeral, dev only).
    session_backend: str = field(
        default_factory=lambda: os.getenv("SESSION_BACKEND", "sqlite")
    )
    # SQLAlchemy URL for the durable session store (sqlite:/// or postgresql+psycopg2://).
    session_db_url: str = field(
        default_factory=lambda: os.getenv("SESSION_DB_URL", "sqlite:///./chat_sessions.db")
    )
    # Recent turns fed to the LLM. The full transcript is always retained; this
    # only bounds prompt size.
    context_turns: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_TURNS", "20"))
    )

settings = Settings()
