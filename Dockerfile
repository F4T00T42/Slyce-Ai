# Slyce AI — Nutrition Assistant API
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/root/.cache/huggingface

WORKDIR /app

# Minimal system deps. psycopg2-binary ships its own libpq, so no extra libs
# are needed; curl is handy for debugging/health probes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App source.
COPY . .

RUN chmod +x docker/entrypoint.sh

EXPOSE 8000

# The entrypoint waits for Qdrant + the sessions DB, ingests the KB if empty,
# then launches uvicorn.
ENTRYPOINT ["/app/docker/entrypoint.sh"]
