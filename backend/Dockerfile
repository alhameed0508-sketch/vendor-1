# ── Stage 1: Install dependencies ─────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (avoids pulling 2GB CUDA build)
RUN pip install --no-cache-dir \
    torch==2.11.0 --index-url https://download.pytorch.org/whl/cpu

# Keep the large Torch layer reusable when application requirements change.
COPY backend/requirements.txt ./requirements.txt

# Install remaining dependencies (torch is intentionally absent from this file)
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Production image ────────────────────────────────
FROM python:3.12-slim AS runner

WORKDIR /app

# Install the healthcheck client and LightGBM's OpenMP runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1001 appgroup && useradd -r -u 1001 -g appgroup appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Build context is the repository root so runtime model/data packages are part
# of the immutable image rather than host-only bind mounts.
COPY --chown=appuser:appgroup . .

# Ensure log directory exists and is writable
RUN mkdir -p /app/logs && chown appuser:appgroup /app/logs

ENV PYTHONPATH="/app/backend:/app"
ENV PYTHONUNBUFFERED=1
ENV MPLCONFIGDIR="/tmp/matplotlib"

# Switch to non-root user
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 --start-period=30s \
    CMD curl -f http://localhost:8000/health || exit 1

# --timeout 120: kill workers that hang for >120s
# --graceful-timeout 30: allow 30s for in-flight requests on shutdown
# --access-log: disable access log (nginx handles this upstream)
CMD ["uvicorn", "api.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--timeout-keep-alive", "30", \
     "--limit-concurrency", "100"]
