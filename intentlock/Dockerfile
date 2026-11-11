# Netrava IntentLock: one container serving the API and the React build.
# Build from the repository root:  docker build -f intentlock/Dockerfile -t intentlock .

FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps --no-audit --no-fund
COPY frontend/ ./
ENV CI=false GENERATE_SOURCEMAP=false
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    FRONTEND_BUILD_DIR=/app/frontend/build \
    DATABASE_URL=sqlite:////app/data/intentlock.db
WORKDIR /app
COPY intentlock/requirements.txt intentlock/requirements.txt
RUN pip install --no-cache-dir -r intentlock/requirements.txt
RUN useradd -r -u 1001 appuser && mkdir -p /app/data && chown appuser /app/data
COPY intentlock/ intentlock/
COPY --from=web /web/build frontend/build
USER appuser
# DATABASE_URL above is a non-durable fallback. Set DATABASE_URL to PostgreSQL in the hosting platform to replace it.
CMD ["sh", "-c", "exec uvicorn intentlock.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 75"]
