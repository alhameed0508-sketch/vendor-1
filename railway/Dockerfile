# Railway single-service image: the React build and the FastAPI API on one URL.
# Demo mode with in-memory data and no PyTorch, so it fits a small Railway plan.
# Build context is the repository root (see railway.json).

# ── Stage 1: React build ──────────────────────────────────────────────────────
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps --no-audit --no-fund
COPY frontend/ ./
# REACT_APP_EXTRA_PAGES=true ships complaints, analytics, compliance, customer risk and data import.
ARG REACT_APP_EXTRA_PAGES=true
# Empty API URL: the browser calls the API on the same origin.
ENV REACT_APP_EXTRA_PAGES=$REACT_APP_EXTRA_PAGES \
    REACT_APP_API_URL= \
    INLINE_RUNTIME_CHUNK=false \
    GENERATE_SOURCEMAP=false \
    CI=false
RUN npm run build

# ── Stage 2: API + static files ───────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

# The slim dependency set the Vercel function uses, plus an ASGI server.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt "uvicorn[standard]==0.27.0"

RUN useradd -r -u 1001 appuser && mkdir -p /app/logs && chown appuser /app/logs

COPY backend/ backend/
COPY models/ models/
COPY infra/ infra/
COPY railway/ railway/
# Benchmark runs write their results under data/, so the app user owns it.
COPY --chown=appuser data/ data/
COPY --from=web /web/build frontend/build

ENV PYTHONPATH=/app/backend:/app \
    PYTHONUNBUFFERED=1 \
    AUDIT_LOG_PATH=/app/logs/audit.jsonl

USER appuser
EXPOSE 8000

# One worker: demo data is in memory. --proxy-headers so rate limits and audit
# records see the visitor's IP instead of Railway's proxy.
CMD ["sh", "-c", "exec uvicorn railway.serve:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 75"]
