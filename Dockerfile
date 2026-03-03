# =============================================================================
# Qmail Backend - Production Dockerfile
# =============================================================================
# Multi-stage build for security and smaller image size
# Stage 1: Build liboqs C library from source
# Stage 2: Build Python dependencies
# Stage 3: Production runtime
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build liboqs C library from source
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS liboqs-builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc g++ make cmake git libssl-dev && \
    rm -rf /var/lib/apt/lists/*

# Clone and build liboqs (Open Quantum Safe) - version must match liboqs-python
RUN git clone --depth 1 --branch main https://github.com/open-quantum-safe/liboqs.git && \
    cd liboqs && \
    mkdir build && cd build && \
    cmake -DCMAKE_INSTALL_PREFIX=/opt/liboqs \
          -DBUILD_SHARED_LIBS=ON \
          -DOQS_BUILD_ONLY_LIB=ON \
          .. && \
    make -j$(nproc) && \
    make install

# ---------------------------------------------------------------------------
# Stage 2: Builder - install Python dependencies
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install system dependencies for building Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc g++ make cmake libffi-dev libssl-dev libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy liboqs from stage 1
COPY --from=liboqs-builder /opt/liboqs /opt/liboqs
ENV LD_LIBRARY_PATH="/opt/liboqs/lib" \
    OQS_INSTALL_PATH="/opt/liboqs"

# Copy only requirements first (Docker layer caching optimization)
COPY requirements.txt .

# Install Python dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Production runtime - minimal image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS production

# Security: run as non-root user
RUN groupadd --gid 1000 qmail && \
    useradd --uid 1000 --gid qmail --shell /bin/bash --create-home qmail

WORKDIR /app

# Install runtime-only system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libffi8 \
        libssl3 \
        libpq5 \
        curl \
        dbus \
        gnome-keyring \
    && rm -rf /var/lib/apt/lists/*

# Copy liboqs shared library from builder
COPY --from=liboqs-builder /opt/liboqs /opt/liboqs
ENV LD_LIBRARY_PATH="/opt/liboqs/lib" \
    OQS_INSTALL_PATH="/opt/liboqs"

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source code (respects .dockerignore)
COPY qmail/ ./qmail/
COPY requirements.txt .
COPY .env.example .

# Create directories for runtime data with proper permissions
RUN mkdir -p /app/qmail_users /app/qmail_broker /app/logs && \
    chown -R qmail:qmail /app

# Switch to non-root user
USER qmail

# Expose the single API port
# The main app (qmail.api:app) serves ALL routes including phone auth
EXPOSE 8000

# Health check - verify the API is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Environment defaults (override via docker run -e or docker-compose)
ENV ENV=production \
    ENFORCE_HTTPS=1 \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create inline Python entrypoint script
RUN cat > /app/entrypoint.py << 'ENTRYPOINT_EOF'
#!/usr/bin/env python3
import subprocess
import sys
import os

os.chdir('/app')
print("📦 Initializing database schema...")

# Initialize database by importing Storage (creates tables on init)
try:
    from qmail.storage.db import Storage
    from dotenv import load_dotenv
    import logging
    
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        print(f"  Connecting to: {database_url[:50]}...")
        Storage(database_url=database_url)
        print("✅ Database tables initialized")
    else:
        print("  (Skipping - DATABASE_URL not set)")
except Exception as e:
    print(f"⚠️ Database init warning: {e}")
    print("  (This is OK if tables already exist)")

print("✅ Startup complete")
print("🌐 Starting Qmail API...")

# Start gunicorn
os.execvp('gunicorn', ['gunicorn', 'qmail.api:app', '--worker-class', 'uvicorn.workers.UvicornWorker', '--workers', '2', '--preload', '--bind', '0.0.0.0:8000', '--timeout', '120', '--graceful-timeout', '30', '--access-logfile', '-', '--error-logfile', '-'])
ENTRYPOINT_EOF

# Production: initialize DB then start API
CMD ["python", "/app/entrypoint.py"]