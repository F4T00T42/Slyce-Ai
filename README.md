# Slyce AI — Nutrition Assistant Chatbot

An orchestration layer added on top of the existing Slyce meal recommender. It
exposes a single conversational endpoint (`POST /chat`) backed by a tool-using
LLM that reuses the app's data and the existing recommendation engine.

The assistant does **not** replace the recommender — it wraps and extends it.

## Capabilities

1. Personalized meal recommendations (`recommendation_engine`)
2. Multi-day diet/meal plans (`meal_planner`)
3. Nutrition guidance / education (`nutrition_knowledge_search` + LLM)
4. Allergy assistance (`allergy_assistant`)
5. Meal analysis — ingredients + macros (`meal_search` with `meal_id`)
6. Restaurant & meal discovery (`restaurant_search`, `meal_search`)
7. General nutrition Q&A via RAG (`nutrition_knowledge_search`)
8. Web-search fallback (`web_search`, last resort)

## Architecture

```
User  ->  /chat  ->  Orchestrator  ->  LLM (Groq, tool calling)
                          |
                          v  tool selection + execution
        +------------------+--------------------------------+
        | recommendation_engine  meal_planner  meal_search  |
        | restaurant_search  allergy_assistant              |
        | nutrition_knowledge_search (RAG)   web_search      |
        +------------------+--------------------------------+
                          |                         |
          App Postgres (READ-ONLY)          Qdrant KB + Tavily
```

**Information priority:** App database → Nutrition knowledge base → Web (last
resort). Enforced via the system prompt and tool descriptions.

## Data model mapping (real schema)

- **Meals** = `menus.MealSizes` (nutrition is denormalized here) joined to
  `menus.MenuMeals` for name/description/restaurant. `MealSizes.Id` is the id
  the app orders by, and is the `meal_id` used throughout the AI layer.
- **Ingredients**: `MenuMeals` → `menus.MealIngredient` (PK `MealId,FoodId`) →
  `Food.Foods` (per-100g nutrition). Per-size quantities in
  `menus.IngredientQuantities` (`MealIngredientId` == `Food.Foods.Id`).
- **Allergens** (`Food.Allergens`) and **diet preferences**
  (`Food.FoodPreferences`) are reference tables. There is no explicit
  food→allergen mapping, so allergens are detected heuristically from
  ingredient names (see `db/ingredient_repository.py`).
- **Customer profile** = `customers.Customers` (Height, Weight, Gender, Bday,
  ActivityRate, `allergen_ids[]`, `diet_preference_ids[]`). The DB stores **no
  fitness goal**, so `goal` defaults to `maintenance` unless supplied.

## Profile contract

`POST /chat` accepts any of:
- `user_id` — the AI layer fetches the stored profile from the app DB.
- `profile` — explicit fields (`weight`, `height`, `age`, `gender`,
  `activity_level`, `goal`, `diet`, `allergies`, `diet_preferences`).
- Neither — the assistant asks a concise follow-up if it needs profile data.

Explicit fields override stored values (useful when a user describes a friend).

## Conversation history

Two separate concerns:

- **Transcript (system of record):** the FULL conversation is stored durably so
  the user can scroll back through it — **no turn limit**.
- **Context window:** only the last `CONTEXT_TURNS` turns (default 20) are sent
  to the LLM, to bound prompt size/cost. Older turns still exist in the
  transcript even after the model stops "remembering" them.

Storage is a **separate datastore** (the main app DB is never written to):

- `SESSION_BACKEND=sqlite` (default) — durable single-file store, survives
  restarts. Good for a single instance.
- `SESSION_BACKEND=postgres` + `SESSION_DB_URL=postgresql+psycopg2://...` — use
  for multi-worker / multi-replica deployments so all workers share history.
- `SESSION_BACKEND=memory` — ephemeral, dev only (lost on restart).

`session_id` is supplied and owned by the **backend** (mint a UUID per
conversation, reuse it across messages). Endpoints:

```
POST   /chat                      # send a message; pass session_id to persist
GET    /chat/history/{session_id} # full transcript for display (optional ?limit=&offset=)
DELETE /chat/history/{session_id} # clear a conversation (e.g. "New chat")
```

## Quick start with Docker (one command)

Brings up the API plus a bundled Qdrant (knowledge base) and Postgres (sessions):

```bash
cp .env.example .env          # fill GROQ_API_KEY, HF_TOKEN, TAVILY_API_KEY, DB_* (Supabase)
docker compose up --build
```

Then open http://localhost:8000/health and POST to http://localhost:8000/chat.

What happens on startup:

- Compose points the app at the bundled services (`QDRANT_URL`, `SESSION_BACKEND=postgres`,
  `SESSION_DB_URL`) — you only fill in secrets and the Supabase `DB_*` values.
- The entrypoint waits for Qdrant + the sessions DB, then **ingests the knowledge
  base only if it's empty** (idempotent — safe to restart).
- The embedding model is cached in a volume, so it downloads only once.
- Conversation history persists in the `sessions_data` volume; the KB persists in
  `qdrant_data`. The main Supabase DB is used **read-only**.

> First build is large (it installs PyTorch for the embedding model) and the first
> boot downloads the BGE model, so it needs internet access once.

Useful commands:

```bash
docker compose up -d --build     # run in the background
docker compose logs -f app       # follow API logs
docker compose down              # stop (keeps volumes/history)
docker compose down -v           # stop and wipe KB + session history
```

## Manual setup (without Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in the values
```

### Ingest the knowledge base (one-time, needs Qdrant running)

```bash
python -m ai.rag.ingest --docs knowledge_base/docs
```

### Run

```bash
uvicorn main:app --reload
```

## Models

- LLM: Groq free hosted inference — `llama-3.3-70b-versatile` (primary),
  `llama-3.1-8b-instant` (fast). Both support tool calling.
- Embeddings: `BAAI/bge-base-en-v1.5` (English; Arabic not supported yet).
- Vector DB: Qdrant (separate datastore; the main app DB is never written to).
- Web search: Tavily.

## Secrets

All secrets live in `.env` (git-ignored). Never commit real keys. `.env.example`
contains only placeholders.
