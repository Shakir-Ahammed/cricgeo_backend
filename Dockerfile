# ============================================================================
# PRODUCTION-READY DOCKERFILE FOR FASTAPI BACKEND
# ============================================================================
# This Dockerfile creates an optimized, secure, production-ready container
# for the FastAPI SaaS backend with Google OAuth2 authentication.
#
# Features:
# - Multi-stage build for smaller image size
# - Non-root user for security
# - Gunicorn + Uvicorn workers for production
# - Efficient layer caching
# - Health check included
# - Optimized for both local dev and production deployment
# ============================================================================

# ============================================================================
# STAGE 1: Builder Stage
# ============================================================================
# Use official Python slim image as builder to install dependencies
FROM python:3.11-slim as builder

# Set build-time environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for building Python packages
# - gcc: C compiler for building Python packages with C extensions
# - pkg-config: Helper tool for compiling applications
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file first for better layer caching
# Docker will cache this layer unless requirements.txt changes
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir: Reduces image size by not storing pip cache
# --user: Install packages in user directory for better security
RUN pip install --user --no-cache-dir -r requirements.txt

# ============================================================================
# STAGE 2: Runtime Stage
# ============================================================================
# Use slim Python image for final container (smaller size)
FROM python:3.11-slim

# Set runtime environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # FastAPI/Uvicorn configuration
    HOST=0.0.0.0 \
    PORT=8000 \
    # Gunicorn worker configuration
    WORKERS=4 \
    WORKER_CLASS=uvicorn.workers.UvicornWorker

# Install only runtime dependencies
# - curl: For health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
# Running as non-root reduces security risks
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code
# Copy app/ directory with all modules
COPY --chown=appuser:appuser app/ ./app/

# Copy Alembic configuration and migrations
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser migrations/ ./migrations/

# Copy environment file (optional - can be mounted at runtime or passed as env vars)
# For production, use Docker secrets or environment variables instead
# Comment out this line if .env is in .dockerignore or use --env-file at runtime
# COPY --chown=appuser:appuser .env .env

# Switch to non-root user
USER appuser

# Update PATH to include user's local bin directory
ENV PATH=/home/appuser/.local/bin:$PATH

# Expose port 8000
# This is informational - actual port mapping happens at runtime
EXPOSE 8000

# Add health check
# Docker will check if the container is healthy every 30 seconds
# - interval: Time between checks
# - timeout: Time to wait for response
# - retries: Failed checks before marking unhealthy
# - start-period: Grace period before checking
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
    CMD curl -f http://localhost:8000/health || exit 1

# ============================================================================
# STARTUP COMMAND
# ============================================================================
# Production-ready startup with Gunicorn + Uvicorn workers
#
# Options explained:
# - app.main:app        → FastAPI application instance
# - -w 4                → 4 worker processes (adjust based on CPU cores)
#                         Recommended: (2 x CPU cores) + 1
# - -k uvicorn.workers.UvicornWorker → Use Uvicorn worker class for async
# - -b 0.0.0.0:8000     → Bind to all interfaces on port 8000
# - --access-logfile -  → Log access to stdout
# - --error-logfile -   → Log errors to stdout
# - --log-level info    → Set log level (debug/info/warning/error/critical)
# - --timeout 120       → Worker timeout (seconds)
# - --graceful-timeout 30 → Graceful shutdown timeout
# - --keep-alive 5      → Keep-alive connections timeout
#
# For development (not recommended in Dockerfile):
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
#
# For production with environment-based workers:
CMD gunicorn app.main:app \
    --workers ${WORKERS:-4} \
    --worker-class ${WORKER_CLASS:-uvicorn.workers.UvicornWorker} \
    --bind ${HOST:-0.0.0.0}:${PORT:-8000} \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 5

# ============================================================================
# USAGE INSTRUCTIONS
# ============================================================================
#
# BUILD IMAGE:
# docker build -t fastapi-backend:latest .
#
# RUN CONTAINER (Development):
# docker run -p 8000:8000 --env-file .env fastapi-backend:latest
#
# RUN CONTAINER (Production with custom workers):
# docker run -p 8000:8000 \
#   -e WORKERS=8 \
#   -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db" \
#   -e JWT_SECRET="your-secret" \
#   fastapi-backend:latest
#
# RUN WITH DOCKER COMPOSE:
# See docker-compose.yml for full stack deployment
#
# HEALTH CHECK:
# docker ps  # Check health status in STATUS column
# curl http://localhost:8000/health
#
# VIEW LOGS:
# docker logs <container_id>
#
# EXECUTE SHELL:
# docker exec -it <container_id> /bin/bash
#
# ============================================================================
