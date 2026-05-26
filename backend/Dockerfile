# Stage 1: Install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.1.2+cpu -f https://download.pytorch.org/whl/torch_stable.html \
    && pip install --no-cache-dir -r requirements.txt

# Stage 2: Production image
FROM python:3.11-slim AS runner

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1001 appgroup && useradd -r -u 1001 -g appgroup appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appgroup . .

# Ensure log directory exists and is writable
RUN mkdir -p /app/logs && chown appuser:appgroup /app/logs

# Set PYTHONPATH so imports resolve for models/, data/, infra/
ENV PYTHONPATH="/app:/app/.."
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 --start-period=30s \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
