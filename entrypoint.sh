#!/bin/sh
# =============================================================================
# CricGeo Backend — Docker Entrypoint
# 1. Wait for DB to be ready
# 2. Run Alembic migrations
# 3. Start Gunicorn + Uvicorn workers
# =============================================================================
set -e

echo "========================================"
echo "  CricGeo Backend Starting..."
echo "========================================"

# ---------------------------------------------------------------------------
# Wait for PostgreSQL to be reachable (simple TCP check via Python)
# ---------------------------------------------------------------------------
echo "[1/3] Waiting for database..."
python - <<'EOF'
import time, socket, os, sys

url = os.environ.get("DATABASE_URL", "")
# Extract host and port from postgresql+asyncpg://user:pass@host:port/db
try:
    rest = url.split("@", 1)[1]          # host:port/db
    host_port = rest.split("/")[0]       # host:port
    host, port = host_port.rsplit(":", 1) if ":" in host_port else (host_port, "5432")
    port = int(port)
except Exception:
    print("Could not parse DATABASE_URL, skipping DB wait.")
    sys.exit(0)

for attempt in range(30):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"Database is ready ({host}:{port})")
            sys.exit(0)
    except OSError:
        print(f"  Attempt {attempt + 1}/30 — waiting 2s...")
        time.sleep(2)

print("ERROR: Database not reachable after 60 seconds. Exiting.")
sys.exit(1)
EOF

# ---------------------------------------------------------------------------
# Run database migrations
# ---------------------------------------------------------------------------
echo "[2/3] Running Alembic migrations..."
alembic upgrade head
echo "Migrations complete."

# ---------------------------------------------------------------------------
# Start application
# ---------------------------------------------------------------------------
echo "[3/3] Starting Gunicorn + Uvicorn workers..."
exec gunicorn app.main:app \
    --workers "${WORKERS:-4}" \
    --worker-class "${WORKER_CLASS:-uvicorn.workers.UvicornWorker}" \
    --bind "${HOST:-0.0.0.0}:${PORT:-8000}" \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 5
