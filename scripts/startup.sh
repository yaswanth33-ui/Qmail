#!/bin/bash
# Production startup script - initialize DB then start API

set -e  # Exit on error

echo "🚀 Qmail API Startup"
echo "===================="

# Initialize database schema
echo "📦 Initializing database schema..."
python /app/scripts/init_db.py

if [ $? -ne 0 ]; then
    echo "❌ Database initialization failed"
    exit 1
fi

echo "✅ Database ready"
echo ""

# Start API server
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
