# syntax=docker/dockerfile:1.4

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.12-slim AS builder

# Set build-time environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies if needed (minimal for pure Python packages)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     gcc \
#     && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY app/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.12-slim AS runtime

# OCI Image Labels (Open Container Initiative)
LABEL org.opencontainers.image.title="BucketBridge" \
      org.opencontainers.image.description="Minimal FastAPI bridge to a private MinIO bucket with upload, download, and presigned URL support" \
      org.opencontainers.image.authors="Parham Davari <parhamdavari@users.noreply.github.com>" \
      org.opencontainers.image.vendor="Parham Davari" \
      org.opencontainers.image.source="https://github.com/parhamdavari/bucketbridge" \
      org.opencontainers.image.url="https://github.com/parhamdavari/bucketbridge" \
      org.opencontainers.image.documentation="https://github.com/parhamdavari/bucketbridge/blob/main/README.md" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="1.0.0"

# Set runtime environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/bucketbridge/.local/bin:$PATH"

# Create non-root user and group
RUN groupadd -r bucketbridge -g 1000 && \
    useradd -r -u 1000 -g bucketbridge -m -s /sbin/nologin bucketbridge

# Set working directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder --chown=bucketbridge:bucketbridge /root/.local /home/bucketbridge/.local

# Copy application code
COPY --chown=bucketbridge:bucketbridge app/main.py app/s3wrap.py ./

# Expose application port (configurable via APP_PORT env var, defaults to 8080)
EXPOSE ${APP_PORT:-8080}

# Switch to non-root user
USER bucketbridge

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${APP_PORT:-8080}/health')" || exit 1

# Start uvicorn server (shell form required for env var substitution)
CMD uvicorn main:app --host 0.0.0.0 --port ${APP_PORT:-8080}
