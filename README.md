# Slyce AI — Nutrition Assistant API
​
A **FastAPI** nutrition-assistant chatbot that wraps an existing meal
**recommendation engine** with a tool-calling LLM orchestration layer. Users chat
in natural language; the assistant calls structured tools over the app's meal
catalog, a curated nutrition knowledge base (RAG), and — only with permission —
the web.
​
## Information Priority
​
The assistant answers from sources in a strict order:
​
```
1. App Database  (meals, ingredients, restaurants, stored profiles)  →
2. RAG Knowledge Base  (curated nutrition facts in Qdrant)           →
3. Web Search  (Tavily, last resort, only when the user opts in)
```
​
## Architecture
​
```
Client → POST /chat → Orchestrator (LLM tool-calling loop)
                          ├── recommendation_engine      (catalog meal recommendations)
                          ├── meal_planner               (multi-day meal plans)
                          ├── meal_search                (search + analyze a meal)
                          ├── restaurant_search          (restaurants & branches)
                          ├── nutrition_knowledge_search (RAG over the KB)
                          ├── allergy_assistant          (allergen checks)
                          └── web_search                 (Tavily, opt-in only)
```
​
- **App DB** (Postgres / Supabase) is used **READ-ONLY** for meals, ingredients,
  restaurants, and stored customer profiles.
- **Session storage** is a *separate* datastore (SQLite by default) for durable
  conversation history.
- **Qdrant** holds the vector knowledge base.
​
## API Endpoints
​
| Method & Path                       | Description                                                        |
| ----------------------------------- | ------------------------------------------------------------------ |
| `POST /chat`                        | Main chat endpoint. Body: `message` (required), `session_id?`, `user_id?`, `profile?`. Returns `reply`, `used_tools`, `citations`, `session_id`. |
| `GET /chat/history/{session_id}`    | Full stored transcript for a session.                              |
| `DELETE /chat/history/{session_id}` | Clears a session's conversation.                                   |
| `POST /recommend`                   | Direct meal recommendations (bypasses the LLM). Body: `user_id?`, `profile?`, `top_n` (default 10). |
| `GET /health`                       | Health check.                                                      |
​
## The Tools
​
| Tool                          | What it does                                                                 |
| ----------------------------- | ---------------------------------------------------------------------------- |
| `recommendation_engine`       | Ranks catalog meals for the user's targets/diet/allergies. Always returns meals. |
| `meal_planner`                | Builds a multi-day plan (1–14 days, 1–6 meals/day) from the ranked pool.     |
| `meal_search`                 | Searches the catalog by name/macros, or auto-analyzes a confidently matched meal. |
| `restaurant_search`           | Finds restaurants and branches by name/city.                                 |
| `nutrition_knowledge_search`  | RAG retrieval over curated, trusted nutrition sources (NIH/ODS, WHO, CDC, USDA…). |
| `allergy_assistant`           | Heuristic allergen detection for a meal/ingredients vs. the user's allergies. |
| `web_search`                  | Tavily web search — **gated**: only runs when the user explicitly opts in.   |
​
## How Recommendations Work
​
The recommender treats **allergens as a hard safety gate** and **diet as a
ranking preference**, using a fallback ladder so the home page is never empty:
​
1. Allergen-safe **and** diet-compatible (if enough meals remain), else
2. Allergen-safe only (diet relaxed, still influences ranking), else
3. The full reviewed catalog ranked by fit.
​
Nutrition math uses **Mifflin–St Jeor** BMR → TDEE (activity multiplier) → goal
adjustment → per-meal calorie/protein targets. Scoring weights calorie fit,
protein fit, and diet fit per goal (`fat_loss` / `muscle_gain` / `maintenance`).
​
## Configuration
​
The app is configured entirely via environment variables. Create a `.env` file:
​
```env
# --- LLM (provider-agnostic, OpenAI-compatible) ---
# Defaults to Google Gemini; works with Groq, Cerebras, OpenRouter, GitHub Models, etc.
LLM_API_KEY=your_api_key            # or GEMINI_API_KEY / GROQ_API_KEY
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-2.0-flash
LLM_TEMPERATURE=0.2
LLM_MAX_RETRIES=3
MAX_TOOL_ITERATIONS=6
​
# --- Application database (Supabase Postgres, READ-ONLY) ---
DB_HOST=your-project.pooler.supabase.com
DB_PORT=6543                        # transaction pooler
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your_password
​
# --- Sessions (conversation history) ---
SESSION_BACKEND=sqlite              # sqlite | postgres | memory
SESSION_DB_URL=sqlite:///./chat_sessions.db
CONTEXT_TURNS=20                    # turns sent to the LLM (full transcript is still stored)
​
# --- RAG knowledge base (Qdrant) ---
QDRANT_URL=http://localhost:6333
KB_COLLECTION=nutrition_kb
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
RUN_INGEST=false                    # set true to (idempotently) ingest the KB on boot
​
# --- Web search ---
TAVILY_API_KEY=your_tavily_key
```
​
> **Note:** earlier docs referenced `cp .env.example .env`, but no `.env.example`
> file ships in the repo yet. Use the template above, and consider committing a
> sanitized `.env.example` so that command works.
​
## Running Locally
​
```bash
git clone https://github.com/F4T00T42/Slyce-Ai.git
cd Slyce-Ai
pip install -r requirements.txt
# create your .env (see above)
uvicorn main:app --reload --port 8000
```
​
You'll need a running Qdrant instance and access to the app's Postgres DB.
​
## Running with Docker
​
`docker-compose.yml` brings up the full stack — the API plus a bundled **Qdrant**
and a **Postgres sessions DB**:
​
```bash
# create your .env first (DB_*, LLM_API_KEY, TAVILY_API_KEY, ...)
docker compose up --build
```
​
- App: `http://localhost:8000`
- Qdrant: `localhost:6333`
- The compose file overrides `QDRANT_URL`, `SESSION_BACKEND=postgres`, and
  `RUN_INGEST=true` to point at the bundled services and seed the KB on first boot.
- Your **application** Postgres (Supabase) stays external and read-only via `DB_*`.
​
## Knowledge Base Ingestion
​
```bash
python -m ai.rag.ingest --docs knowledge_base/docs            # ingest
python -m ai.rag.ingest --docs knowledge_base/docs --recreate # rebuild collection
```
​
Docs are `.md`/`.txt` files (optionally with `title:`/`source:` front matter),
chunked at ~800 words with 150-word overlap, embedded with BGE, and upserted to
Qdrant.
​
## Sessions Model
​
- The **full transcript** is persisted (system of record, unbounded).
- Only the **last `CONTEXT_TURNS` turns** are sent to the LLM to bound prompt size —
  older turns are never deleted, just not re-sent.
- Backends: `sqlite` (default, durable), `postgres` (durable), `memory` (dev only).
​
## Deployment
​
CI/CD via GitHub Actions (`.github/workflows/master_slyce-ai.yml`): on push to
`master`, it builds with Python 3.11 and deploys to **Azure Web App `Slyce-Ai`**
(Production slot).
​
## Project Structure
​
```
main.py                  # FastAPI app, startup wiring, /recommend & /health
ai/
  orchestrator.py        # LLM tool-calling loop
  config.py              # Settings (env-driven)
  prompts.py             # System prompt + tool-routing hint
  api/                   # chat_router.py, schemas.py
  llm/provider.py        # OpenAI-compatible LLM client
  tools/                 # the 7 tools + shared helpers
  rag/                   # embedder, vector_store, retriever, ingest, bootstrap_kb
  sessions/store.py      # in-memory + SQL session stores
db/                      # connection, schema, repositories (read-only)
recommender.py           # recommendation orchestration
scorer.py / nutrition.py # scoring + nutrition math
models.py / filters.py   # data models + diet/allergen filters
docker-compose.yml / Dockerfile / docker/entrypoint.sh
```
​
## License
​
MIT
​
