# Multi-stage Dockerfile for Hostel Management System Web Application
# Course: BBAT104 Fundamentals of Total Quality Management (TQM)
# Quality Goal: Q05 - Response Time < 10ms SLA

# Stage 1: Build & Dependency Resolution
FROM python:3.11-slim as builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Hardened Lean Runtime
FROM python:3.11-slim as runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PORT=8000 \
    HOST=0.0.0.0 \
    PATH=/home/appuser/.local/bin:$PATH

WORKDIR /app

# Install minimal runtime dependencies (curl for health check, sqlite3 for inspection)
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -s /bin/bash appuser

# Copy installed python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application source code
COPY --chown=appuser:appgroup backend/ ./backend/
COPY --chown=appuser:appgroup frontend/ ./frontend/
COPY --chown=appuser:appgroup scripts/ ./scripts/
COPY --chown=appuser:appgroup run.py .

# Create volume directories with proper ownership for non-root user
RUN mkdir -p data data/backups data/uploads && \
    chown -R appuser:appgroup /app /home/appuser

USER appuser

# Expose web service port
EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Launch production server via Uvicorn with single worker to preserve in-memory cache and SQLite WAL locking
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
