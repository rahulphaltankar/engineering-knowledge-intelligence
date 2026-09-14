# Fire Engineering Knowledge Intelligence - container image for Google Cloud Run.
#
# Runs the unchanged FastAPI application (appliance.api.app:app) with uvicorn,
# bound to 0.0.0.0 on $PORT (set by Cloud Run), falling back to 8080.
#
#   docker build -t engineering-knowledge-intelligence .
#   docker run --rm -p 8080:8080 engineering-knowledge-intelligence
#
# Analysis sessions and review decisions are held in process memory, so the
# service runs a single uvicorn worker; see README "Deploy to Google Cloud Run".

FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ---- dependencies ----------------------------------------------------------
FROM base AS deps
WORKDIR /build
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ---- runtime ---------------------------------------------------------------
FROM base AS runtime

# The process never needs root.
RUN groupadd --system --gid 10001 app && \
    useradd --system --uid 10001 --gid app --home-dir /app --no-create-home app

COPY --from=deps /install /usr/local

WORKDIR /app
# Only what the running application needs: code, configuration and the
# knowledge packs (synthetic corpora, specialist profiles, upstream packs).
COPY --chown=app:app appliance/ ./appliance/
COPY --chown=app:app config/ ./config/
COPY --chown=app:app packs/ ./packs/

USER app

ENV PORT=8080
EXPOSE 8080

# Shell form via exec so $PORT is expanded at start-up and uvicorn runs as
# PID 1, receiving Cloud Run's SIGTERM directly for a graceful shutdown.
CMD ["sh", "-c", "exec uvicorn appliance.api.app:app --host 0.0.0.0 --port \"${PORT:-8080}\" --workers 1"]
