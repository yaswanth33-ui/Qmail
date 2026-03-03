#!/bin/bash
set -e

cd /app

echo "🚀 Qmail API Startup"
echo "===================="
echo "📦 Initializing database schema..."

python scripts/init_db.py || {
    echo "❌ Database initialization failed"
    exit 1
}

echo "✅ Database ready"
echo "🌐 Starting Qmail API..."

exec gunicorn qmail.api:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 \
    --preload \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
