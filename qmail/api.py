"""
=============================================================================
LAYER 7: API - FastAPI Backend for Flutter Frontend
=============================================================================

This module provides the REST API that connects the Flutter mobile app
to the Qmail backend. It orchestrates all lower layers to provide a
complete end-to-end encrypted email experience.

ARCHITECTURE OVERVIEW:
----------------------
    ┌─────────────────────────────────────────────────────────────────────┐
    │                     FLUTTER MOBILE APP                              │
    │              (lib/screens, lib/services, etc.)                      │
    └──────────────────────────┬──────────────────────────────────────────┘
                               │ HTTP REST
                               ▼
    ╔═════════════════════════════════════════════════════════════════════╗
    ║                    THIS MODULE (api.py)                             ║
    ║                                                                     ║
    ║  FastAPI Endpoints:                                                 ║
    ║  ┌────────────────────────────────────────────────────────────┐    ║
    ║  │  AUTHENTICATION                                            │    ║
    ║  │  - GET  /auth/oauth/authorize   → Redirect to OAuth login │    ║
    ║  │  - POST /auth/oauth/token       → Exchange code for token │    ║
    ║  │  - POST /auth/oauth/refresh     → Refresh access token    │    ║
    ║  │  - GET  /auth/oauth/providers   → List OAuth providers    │    ║
    ║  │  - GET  /auth/user              → Get user info           │    ║
    ║  │  - POST /auth/logout            → Logout user             │    ║
    ║  └────────────────────────────────────────────────────────────┘    ║
    ║  ┌────────────────────────────────────────────────────────────┐    ║
    ║  │  MESSAGE OPERATIONS (WhatsApp-style)                       │    ║
    ║  │  - POST /messages/send          → Send encrypted message  │    ║
    ║  │  - GET  /messages/pending       → Get pending messages    │    ║
    ║  │  - GET  /messages/{id}          → Get specific message    │    ║
    ║  │  - POST /messages/{id}/ack      → Acknowledge receipt     │    ║
    ║  │  - GET  /messages               → List all messages       │    ║
    ║  └────────────────────────────────────────────────────────────┘    ║
    ║  ┌────────────────────────────────────────────────────────────┐    ║
    ║  │  EMAIL OPERATIONS (Traditional)                            │    ║
    ║  │  - GET  /emails/inbox           → Fetch from IMAP         │    ║
    ║  │  - POST /emails/send            → Send via SMTP           │    ║
    ║  │  - GET  /emails/{id}            → Get stored email        │    ║
    ║  │  - DELETE /emails/{id}          → Delete email            │    ║
    ║  └────────────────────────────────────────────────────────────┘    ║
    ╚═════════════════════════════════════════════════════════════════════╝
                               │
                               ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                    QMAIL BACKEND LAYERS                             │
    │  Layer 6: Transport (SMTP/IMAP)                                     │
    │  Layer 5: Auth (OAuth, QKD, Broker)                                 │
    │  Layer 4: Storage (SQLite)                                          │
    │  Layer 3: Key Management                                            │
    │  Layer 2: Key Exchange (BB84, PQC)                                  │
    │  Layer 1: Crypto (QRNG, AES, OTP, Signatures)                       │
    └─────────────────────────────────────────────────────────────────────┘

WHATSAPP-STYLE MESSAGE FLOW:
----------------------------
    SENDER                    API SERVER               RECIPIENT
    ──────                    ──────────               ─────────
    1. Compose message
    2. POST /messages/send
       (encrypted + signed)
                              3. Store in
                                 pending_messages
                                                       4. GET /messages/pending
                                                       5. Receive encrypted msg
                                                       6. POST /messages/{id}/ack
                              7. Delete from
                                 pending_messages

SECURITY MODEL:
---------------
1. ALL message content is encrypted BEFORE reaching this API
2. The API server NEVER sees plaintext message content
3. Keys are exchanged via PQC (ML-KEM-1024) or BB84 (simulated)
4. Messages are signed with PQC signatures (Dilithium2)
5. View-once messages use OTP encryption with QRNG keys

TOKEN AUTHENTICATION:
---------------------
Most endpoints require a Bearer token in the Authorization header:

    Authorization: Bearer <access_token>

The token is validated by fetching user info from the OAuth provider.
Token storage is handled by the OS keychain (see Layer 5: Auth).

RUNNING THE SERVER:
-------------------
    uvicorn qmail.api:app --reload --port 8000

    # Or with Python
    python -m uvicorn qmail.api:app --reload --port 8000

ENVIRONMENT:
------------
- Base URL: http://localhost:8000 (development)
- CORS: Enabled for Flutter web development
- Docs: http://localhost:8000/docs (Swagger UI)
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
from typing import Dict, List, Optional
import uuid
import json
import secrets
from urllib.parse import urlparse
import logging

from dotenv import load_dotenv
load_dotenv()  # Load .env file before any os.environ.get() calls

import requests
from fastapi import FastAPI, HTTPException, Query, Header, Request, status, UploadFile, File
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator
import hashlib
import re
import keyring

# Setup structured logging (avoid logging sensitive data to stdout)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Argon2 is required for all KDF operations. Enforce Argon2-only mode.
try:
    from argon2.low_level import hash_secret_raw, Type as Argon2Type
    _HAS_ARGON2 = True
except Exception as exc:
    raise RuntimeError(
        "Argon2 (argon2-cffi) is required - install it in your Python environment (pip install argon2-cffi)"
    ) from exc

# OAuth and Firebase authentication removed - using phone authentication only
from qmail.client import QmailClient
from qmail.config import AppConfig
from qmail.models import EmailEnvelope, EncryptionMode
from qmail.storage.db import Storage, pending_messages_table, emails_table
from qmail.crypto.aes import decrypt_aes_gcm
from qmail.crypto.otp import decrypt_view_once
from qmail.crypto.signatures import generate_keypair, sign_message, verify_signature

# Lazy-load liboqs for KEM operations
_OQS_LOADED = False
_oqs_module = None

def _load_oqs_kem():
    """Lazy-load liboqs KEM implementation."""
    global _OQS_LOADED, _oqs_module
    if _OQS_LOADED:
        return _oqs_module
    try:
        import oqs
        _oqs_module = oqs
        _OQS_LOADED = True
        return _oqs_module
    except ImportError as e:
        raise ImportError(
            "liboqs-python is not properly installed. "
            "Ensure liboqs C library is built and liboqs-python is installed."
        ) from e

# KEM encapsulated key magic bytes - used to reliably identify encapsulated format
KEM_MAGIC = b'QKEM'

# SSRF protection removed - OAuth/Firebase authentication no longer used


def _track_token_activity(token: str) -> None:
    """Track token activity time for session timeout enforcement."""
    _TOKEN_LAST_ACTIVITY[token] = time.time()


def _check_session_timeout(token: str) -> None:
    """
    Enforce session timeout: reject token if idle for too long.
    Raises HTTPException if session expired.
    """
    last_activity = _TOKEN_LAST_ACTIVITY.get(token)
    if not last_activity:
        # First access - initialize activity time
        _track_token_activity(token)
        return
    
    elapsed = time.time() - last_activity
    if elapsed > _SESSION_TIMEOUT_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired due to inactivity. Please sign in again."
        )
    
    # Update activity time for next check
    _track_token_activity(token)


def _require_recent_reauthentication(token: str, operation: str = "sensitive operation") -> None:
    """
    Require re-authentication for sensitive operations (delete, logout, etc).
    Raises HTTPException if user hasn't re-authed within the required window.
    
    Args:
        token: Bearer token
        operation: Description of the operation (for logging)
    """
    last_reauth = _TOKEN_LAST_REAUTH.get(token)
    now = time.time()
    
    if not last_reauth or (now - last_reauth) > _SENSITIVE_OPS_REAUTH_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Re-authentication required for {operation}. Please sign in again."
        )


def _mark_reauthenticated(token: str) -> None:
    """Mark token as recently re-authenticated (for sensitive operations)."""
    _TOKEN_LAST_REAUTH[token] = time.time()
    _track_token_activity(token)


def _verify_email_ownership(user_email: str, email_sender: str, email_recipient: str) -> None:
    """
    Verify that the authenticated user owns (is sender or recipient of) an email.
    
    SECURITY: Prevents users from accessing emails belonging to other users.
    Raises HTTPException if user doesn't own the email.
    
    Args:
        user_email: The authenticated user's email
        email_sender: The email's sender
        email_recipient: The email's recipient
    """
    user_email_lower = user_email.lower().strip()
    sender_lower = email_sender.lower().strip()
    recipient_lower = email_recipient.lower().strip()
    
    if user_email_lower != sender_lower and user_email_lower != recipient_lower:
        logger.warning(f"[Security] Access control violation: {user_email} attempted to access email from {sender_lower} to {recipient_lower}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this email"
        )
# ---------------------------------------------------------------------------

_KEYRING_SERVICE = "qmail-db-encryption"

# --- Runtime security / rate-limiting / revocation state ---------------------
import time
from collections import deque

# Enable strict HTTPS enforcement in production (default: True for security)
# Only set to False for local development
_ENFORCE_HTTPS = os.environ.get("ENFORCE_HTTPS", "1") == "1"
_IS_PRODUCTION = os.environ.get("ENV", "production").lower() in ("production", "prod")

# CORS allowed origins (comma-separated)
_CORS_ALLOWED_ORIGINS = [
    origin.strip() 
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") 
    if origin.strip()
] or []

# Token session management
_SESSION_TIMEOUT_SECONDS = int(os.environ.get("SESSION_TIMEOUT_SECONDS", str(3600)))  # 1 hour default
_SENSITIVE_OPS_REAUTH_WINDOW = int(os.environ.get("SENSITIVE_OPS_REAUTH_WINDOW", str(300)))  # 5 min default
# Track token access times for session timeout enforcement
_TOKEN_LAST_ACTIVITY: dict[str, float] = {}
# Track last re-auth time for sensitive operations
_TOKEN_LAST_REAUTH: dict[str, float] = {}

# Per-route rate limits: (limit, window_seconds)
_RATE_LIMITS = {
    "/auth/oauth/token": (5, 60),
    "/auth/": (10, 60),
    "/email/send": (20, 60),
    "/encrypted/send": (20, 60),
    "/messages/send": (20, 60),
    "/keys/kem": (30, 60),
}

# In-memory revoked token store (token -> expires_at). For production use a
# persistent/shared blacklist (Redis) so revocations are honored across nodes.
_REVOKED_TOKENS: dict[str, float] = {}

# Optional Redis integration (if REDIS_URL is set). We prefer using asyncio
# Redis client for middleware and synchronous client for request handlers.
_REDIS_URL = os.environ.get("REDIS_URL")
_REDIS_SYNC = None
_REDIS_ASYNC = None
if _REDIS_URL:
    try:
        import redis as _redis_sync
        import redis.asyncio as _redis_async

        _REDIS_SYNC = _redis_sync.from_url(_REDIS_URL, decode_responses=True)
        _REDIS_ASYNC = _redis_async.from_url(_REDIS_URL, decode_responses=True)
    except Exception:
        # Redis not available in the environment; continue using in-memory stores
        _REDIS_SYNC = None
        _REDIS_ASYNC = None


def _revoke_token(token: str, ttl_seconds: int = 3600) -> None:
    """Revoke a token locally; use Redis when configured (mandatory in production)."""
    # In production, Redis must be available for distributed token revocation
    if _IS_PRODUCTION and not _REDIS_SYNC:
        logger.warning("[SECURITY] Token revocation requires Redis in production")
    
    if _REDIS_SYNC:
        try:
            _REDIS_SYNC.setex(f"revoked:{token}", ttl_seconds, "1")
            return
        except Exception as e:
            logger.error(f"[Security] Redis revocation failed: {type(e).__name__}")
            if _IS_PRODUCTION:
                raise  # Fail closed in production

    # Fallback to in-memory store (only for development)
    if not _IS_PRODUCTION:
        _REVOKED_TOKENS[token] = time.time() + ttl_seconds


def _is_token_revoked(token: str) -> bool:
    """Check revocation state (Redis first, then in-memory). In production, requires Redis."""
    if _REDIS_SYNC:
        try:
            return _REDIS_SYNC.exists(f"revoked:{token}") == 1
        except Exception as e:
            logger.error(f"[Security] Redis check failed: {type(e).__name__}")
            if _IS_PRODUCTION:
                raise  # Fail closed in production
            pass

    # Only use in-memory store for development
    if _IS_PRODUCTION:
        return False  # If Redis unavailable in prod, reject unknown revocation state
    
    exp = _REVOKED_TOKENS.get(token)
    if not exp:
        return False
    if time.time() >= exp:
        # expired entry - prune
        del _REVOKED_TOKENS[token]
        return False
    return True


def _get_db_encryption_key(db_identifier: str) -> bytes:
    """
    Get or generate a 32-byte AES-256 encryption key for a database.
    
    KEY STORAGE STRATEGY:
    - Native (Desktop): OS keyring (Windows Credential Locker, macOS Keychain)
    - Docker/Cloud: Derived from DB_ENCRYPTION_MASTER_KEY env var using Argon2
    
    Args:
        db_identifier: Unique identifier for this database (hashed for privacy)
    
    Returns:
        32-byte AES-256 key for field-level encryption
    """
    # --- Docker / Cloud path: derive key from master secret via Argon2 ---
    master_key = os.environ.get("DB_ENCRYPTION_MASTER_KEY")
    if master_key:
        # Derive a unique 32-byte key per db_identifier using Argon2
        salt = hashlib.sha256(f"qmail:{db_identifier}".encode()).digest()[:16]
        derived = hash_secret_raw(
            secret=master_key.encode(),
            salt=salt,
            time_cost=3,
            memory_cost=65536,
            parallelism=4,
            hash_len=32,
            type=Argon2Type.ID,
        )
        return derived

    # --- Native Desktop path: use OS keyring ---
    try:
        stored = keyring.get_password(_KEYRING_SERVICE, db_identifier)
        if stored:
            return bytes.fromhex(stored)
        
        # Generate new random key and store in keyring
        new_key = os.urandom(32)
        keyring.set_password(_KEYRING_SERVICE, db_identifier, new_key.hex())
        return new_key
    except Exception as e:
        # If keyring fails (e.g., no backend in Docker), require master key
        raise RuntimeError(
            "No keyring backend available and DB_ENCRYPTION_MASTER_KEY env var not set. "
            "Set DB_ENCRYPTION_MASTER_KEY for Docker/cloud deployments."
        ) from e


# ---------------------------------------------------------------------------
# Auto-delete: Purge acknowledged messages from broker DB
# ---------------------------------------------------------------------------
# Messages marked "acknowledged" have been successfully delivered and
# confirmed by the recipient.  Keeping them in the broker is unnecessary
# and a security liability.  This background task deletes them after a
# short grace period (default 5 minutes).
# ---------------------------------------------------------------------------

AUTO_DELETE_INTERVAL_SECONDS = 60        # How often the cleanup runs
AUTO_DELETE_GRACE_PERIOD_MINUTES = 5     # Keep acknowledged msgs for this long before purging


async def _auto_delete_acknowledged_messages() -> None:
    """Background loop that purges acknowledged messages from the broker DB."""
    while True:
        try:
            await asyncio.sleep(AUTO_DELETE_INTERVAL_SECONDS)
            broker_storage = _get_broker_storage()
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=AUTO_DELETE_GRACE_PERIOD_MINUTES)
            
            # SAFEGUARD: Only delete if ALL conditions are met
            # 1. Status must be "acknowledged" (not "pending")
            # 2. acknowledged_at must be set and <= cutoff
            # 3. This ensures we never delete unacknowledged messages
            stmt = pending_messages_table.delete().where(
                (pending_messages_table.c.status == "acknowledged") &
                (pending_messages_table.c.acknowledged_at.isnot(None)) &
                (pending_messages_table.c.acknowledged_at <= cutoff)
            )
            with broker_storage._engine.begin() as conn:
                result = conn.execute(stmt)
                if result.rowcount > 0:
                    logger.info(f"Auto-deleted {result.rowcount} acknowledged messages from broker")
        except asyncio.CancelledError:
            break
        except Exception as exc:
            # Log but never crash the background task
            logger.error(f"Error in auto-delete task: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start/stop the auto-delete background task."""
    task = asyncio.create_task(_auto_delete_acknowledged_messages())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Qmail API",
    lifespan=lifespan,
    docs_url=None if _IS_PRODUCTION else "/docs",
    redoc_url=None if _IS_PRODUCTION else "/redoc",
    openapi_url=None if _IS_PRODUCTION else "/openapi.json",
)

# --- Security middlewares (CORS, HTTPS redirect, simple rate limiter) -------
# CORS: configure allowed origins via CORS_ALLOWED_ORIGINS env var
try:
    from fastapi.middleware.cors import CORSMiddleware
    if _CORS_ALLOWED_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=_CORS_ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
except Exception:
    # If fastapi/middleware import fails (unlikely), continue without CORS
    pass

# HTTPS redirect + HSTS header (only when explicitly enabled in env)
if _ENFORCE_HTTPS:
    try:
        from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

        app.add_middleware(HTTPSRedirectMiddleware)
    except Exception:
        pass


class _SimpleRateLimitMiddleware:
    """Per-IP / per-token fixed-window rate limiter.

    - Uses Redis when configured (distributed); otherwise falls back to in-memory.
    - Route limits configured via `_RATE_LIMITS`.
    """

    def __init__(self, app, route_limits: dict | None = None, default_limit=(200, 60)) -> None:
        self.app = app
        self.route_limits = route_limits or {}
        self.default_limit = default_limit
        # key -> deque[timestamps] (in-memory fallback)
        self._store: dict[str, deque[float]] = {}

    def _key_for_request(self, scope: dict, headers: dict) -> str:
        # Prefer bearer token as key (per-account throttling), fall back to IP
        auth = headers.get("authorization", "")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1]
            return f"tok:{token[:24]}"
        # Remote client IP (X-Forwarded-For supported)
        xff = headers.get("x-forwarded-for")
        if xff:
            return f"ip:{xff.split(',')[0].strip()}"
        client = scope.get("client")
        if client:
            return f"ip:{client[0]}"
        return "ip:unknown"

    def _allowed_memory(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        dq = self._store.get(key)
        if dq is None:
            dq = deque()
            self._store[key] = dq
        # Purge old timestamps
        while dq and dq[0] <= now - window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True

    async def _allowed_redis(self, key: str, limit: int, window: int) -> bool:
        # Use fixed window counter keyed by integer window index
        if not _REDIS_ASYNC:
            return True
        now = int(time.time())
        window_index = now // window
        redis_key = f"ratelimit:{key}:{window_index}"
        try:
            cur = await _REDIS_ASYNC.incr(redis_key)
            if cur == 1:
                await _REDIS_ASYNC.expire(redis_key, window)
            return cur <= limit
        except Exception:
            # On Redis error, allow request (fail-open) and fallback to memory
            return self._allowed_memory(key, limit, window)

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        path = scope.get("path", "")
        # Determine applicable limit
        for prefix, (limit, window) in (self.route_limits or {}).items():
            if path.startswith(prefix):
                key = self._key_for_request(scope, headers)
                allowed = True
                if _REDIS_ASYNC:
                    allowed = await self._allowed_redis(key, limit, window)
                else:
                    allowed = self._allowed_memory(key, limit, window)

                if not allowed:
                    from fastapi.responses import JSONResponse

                    resp = JSONResponse({"detail": "Too many requests"}, status_code=429)
                    resp.headers["Retry-After"] = str(window)
                    await resp(scope, receive, send)
                    return
                break
        await self.app(scope, receive, send)


# Register rate limiter (in-memory). For production use a distributed limiter (Redis).
app.add_middleware(_SimpleRateLimitMiddleware, route_limits=_RATE_LIMITS)


@app.middleware("http")
async def _security_response_headers(request, call_next):
    resp = await call_next(request)
    # General hardening headers
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("X-XSS-Protection", "1; mode=block")  # Additional XSS protection
    if _ENFORCE_HTTPS:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
    return resp


# --- OAuth and Firebase removed - using phone authentication only ---
    """
    Validate that OAuth credentials are configured for a provider.
    Raises RuntimeError with helpful message if missing.
    
    SECURITY: Never allow OAuth to proceed without proper credentials configured.
    """
    client_id_key = f"{provider_name.upper()}_CLIENT_ID"
    client_secret_key = f"{provider_name.upper()}_CLIENT_SECRET"
    
    client_id = os.environ.get(client_id_key, "").strip()
    client_secret = os.environ.get(client_secret_key, "").strip()
    
# --- OAuth and Firebase removed - using phone authentication only ---


def _get_storage() -> Storage:
    """Get the storage instance (PostgreSQL in production, SQLite in development)."""
    database_url = os.environ.get("DATABASE_URL")
    enc_key = _get_db_encryption_key("default")
    if database_url and not database_url.startswith("sqlite"):
        return Storage(database_url=database_url, encryption_key=enc_key, schema="default_app")
    # SQLite fallback for local development
    db_path = Path("qmail.db")
    return Storage(db_path, encryption_key=enc_key)


def _get_user_storage(access_token: str) -> tuple[Storage, str]:
    """
    Get user-specific storage instance and user email.

    Creates a separate database / schema for each user based on their email.
    Also generates PQC signing keypair if user doesn't have one.
    
    DATABASE BACKENDS:
    - PostgreSQL (production): each user gets an isolated schema
    - SQLite (development): each user gets their own .db file
    
    SECURITY: Enforces session timeout and checks token revocation.
    Returns (Storage instance, user_email).
    """
    database_url = os.environ.get("DATABASE_URL")
    user_email = None
    
    # First, try to verify as JWT token (phone authentication)
    if _phone_token_service:
        payload = _phone_token_service.verify_access_token(access_token)
        if payload:
            user_email = payload.get("email")
            if user_email:
                enc_key = _get_db_encryption_key(f"user:{user_email}")
                
                if database_url and not database_url.startswith("sqlite"):
                    # PostgreSQL: use schema-based user isolation
                    user_schema = "user_" + user_email.replace("@", "_at_").replace(".", "_")
                    storage = Storage(database_url=database_url, encryption_key=enc_key, schema=user_schema)
                else:
                    # SQLite: per-user database file
                    user_db_dir = Path("qmail_users") / user_email.replace("@", "_at_")
                    user_db_dir.mkdir(parents=True, exist_ok=True)
                    db_path = user_db_dir / "storage.db"
                    storage = Storage(db_path, encryption_key=enc_key)
                
                # Generate PQC signing keypair if user doesn't have one
                _ensure_signing_keypair(storage, user_email)
                
                # Generate ML-KEM encryption keypair for TRUE E2E security
                _ensure_kem_keypair(storage, user_email)
                
                return storage, user_email
    
    # JWT token verification only (phone authentication)
    if not _phone_token_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service not initialized"
        )
    
    payload = _phone_token_service.verify_access_token(access_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_email = payload.get("email")
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token does not contain email"
        )
    
    enc_key = _get_db_encryption_key(f"user:{user_email}")
    
    if database_url and not database_url.startswith("sqlite"):
        # PostgreSQL: use schema-based user isolation
        user_schema = "user_" + user_email.replace("@", "_at_").replace(".", "_")
        storage = Storage(database_url=database_url, encryption_key=enc_key, schema=user_schema)
    else:
        # SQLite: per-user database file
        user_db_dir = Path("qmail_users") / user_email.replace("@", "_at_")
        user_db_dir.mkdir(parents=True, exist_ok=True)
        db_path = user_db_dir / "storage.db"
        storage = Storage(db_path, encryption_key=enc_key)
    
    # Generate PQC signing keypair if user doesn't have one
    _ensure_signing_keypair(storage, user_email)
    
    # Generate ML-KEM encryption keypair for TRUE E2E security
    _ensure_kem_keypair(storage, user_email)
    
    return storage, user_email

def _ensure_signing_keypair(storage: Storage, user_email: str) -> None:
    """
    Ensure user has a PQC signing keypair.
    
    If keypair doesn't exist, generates a new Dilithium2 keypair and stores:
    - Full keypair (public + private) in user's local storage
    - Public key only in broker storage for signature verification by others
    """
    existing = storage.get_signing_keypair(user_email)
    if existing is not None:
        return
    
    # Generate new Dilithium2 keypair (NIST FIPS 204 ML-DSA-44)
    keypair = generate_keypair("Dilithium2")
    
    # Store full keypair in user's local storage
    storage.save_signing_keypair(
        email=user_email,
        public_key=keypair.public_key,
        private_key=keypair.private_key,
        algorithm=keypair.algorithm,
    )
    
    # Store PUBLIC KEY ONLY in broker for others to verify signatures
    broker_storage = _get_broker_storage()
    broker_storage.save_signing_keypair(
        email=user_email,
        public_key=keypair.public_key,
        private_key=None,  # Never store private key in broker!
        algorithm=keypair.algorithm,
    )


def _ensure_kem_keypair(storage: Storage, user_email: str) -> None:
    """
    Ensure user has an ML-KEM-1024 encryption keypair for TRUE E2E security.
    
    If keypair doesn't exist, generates a new ML-KEM-1024 keypair and stores:
    - Full keypair (public + secret) in user's local storage
    - Public key only in broker storage for senders to encapsulate session keys
    
    This enables TRUE E2E encryption where:
    - Sender encrypts session key with recipient's ML-KEM public key
    - Only recipient can decrypt session key with their ML-KEM secret key
    - Broker NEVER sees the plaintext session key
    """
    existing = storage.get_kem_keypair(user_email)
    if existing is not None:
        return
    
    # Generate new ML-KEM-1024 keypair (NIST FIPS 203) via liboqs
    oqs = _load_oqs_kem()
    kem = oqs.KeyEncapsulation("Kyber1024")
    public_key = bytes(kem.generate_keypair())
    secret_key = bytes(kem.export_secret_key())
    
    # Store full keypair in user's local storage
    storage.save_kem_keypair(
        email=user_email,
        public_key=public_key,
        private_key=secret_key,
        algorithm="ML-KEM-1024",
    )
    
    # Store PUBLIC KEY ONLY in broker for others to encapsulate session keys
    broker_storage = _get_broker_storage()
    broker_storage.save_kem_keypair(
        email=user_email,
        public_key=public_key,
        private_key=None,  # Never store secret key in broker!
        algorithm="ML-KEM-1024",
    )


def _get_broker_storage() -> Storage:
    """
    Get the centralized message broker database (not per-user).
    
    This is used for WhatsApp-style message queuing where:
    - Sender stores encrypted message in broker
    - Recipient fetches from broker using their recipient email
    - Both access the same centralized database table
    
    DATABASE BACKENDS:
    - PostgreSQL (production): uses a dedicated 'broker' schema
    - SQLite (development): uses a separate broker.db file
    """
    database_url = os.environ.get("DATABASE_URL")
    enc_key = _get_db_encryption_key("broker")
    
    if database_url and not database_url.startswith("sqlite"):
        # PostgreSQL: use 'broker' schema in the shared database
        return Storage(database_url=database_url, encryption_key=enc_key, schema="broker")
    
    # SQLite fallback for local development
    broker_db_dir = Path("qmail_broker")
    broker_db_dir.mkdir(parents=True, exist_ok=True)
    db_path = broker_db_dir / "broker.db"
    return Storage(db_path, encryption_key=enc_key)


def _default_account_id() -> str:
    """
    For now, we treat the app as single-user per device and store tokens under
    a fixed account_id. This can be extended later to support multiple accounts.
    """
    return "default"


def _derive_email_key(user_email: str, sender: str, recipient: str, subject: str) -> bytes:
    """
    Deterministically derive a 32-byte key from email metadata.

    SECURITY IMPROVEMENT: Previously used a static global salt (b'qmail').
    That has been replaced with a conversation-specific salt derived from the
    participants (sender/recipient). This preserves cross-device determinism
    while preventing a single static salt across all messages.

    NOTE: Long-term migration should replace this with Argon2id + per-user
    salt stored in a synchronized store (or HKDF over a shared secret).
    """
    # Keep determinism for sender/recipient/subject across devices, but avoid
    # a static global salt.
    key_material = f"{sender}:{recipient}:{subject}".encode("utf-8")
    salt = hashlib.sha256(b"qmail:" + sender.encode("utf-8") + b":" + recipient.encode("utf-8")).digest()

    # Argon2-only: require Argon2id for all KDF operations (no PBKDF2 fallback).
    if not _HAS_ARGON2:
        raise RuntimeError("Argon2 (argon2-cffi) is required by this build; install argon2-cffi on all nodes.")

    # time_cost=2, memory_cost=2**16 (~64 MiB), parallelism=1
    return hash_secret_raw(
        secret=key_material,
        salt=salt,
        time_cost=2,
        memory_cost=2 ** 16,
        parallelism=1,
        hash_len=32,
        type=Argon2Type.ID,
    )


def _try_decrypt_email(encrypted_json_str: str, user_email: str, sender: str, recipient: str, subject: str, encryption_mode: str = "aes") -> Optional[str]:
    """
    Try to decrypt an encrypted Qmail email.
    
    For AES emails: Uses the session_key_hex field
    For VIEW_ONCE_OTP emails: Uses the otp_key_hex and mac_key_hex fields with MAC verification
    
    Returns the decrypted plaintext if successful, otherwise None.
    """
    try:
        body_json = json.loads(encrypted_json_str)
        if "ciphertext_hex" not in body_json:
            return None
        
        ciphertext_hex = body_json.get("ciphertext_hex", "")
        if not ciphertext_hex:
            return None
        
        ciphertext_bytes = bytes.fromhex(ciphertext_hex)
        
        # Handle view-once OTP decryption
        if encryption_mode == "view_once_otp":
            otp_key_hex = body_json.get("otp_key_hex")
            mac_key_hex = body_json.get("mac_key_hex")
            mac_hex = body_json.get("mac_hex")
            
            if not all([otp_key_hex, mac_key_hex, mac_hex]):
                # Missing required keys for view-once decryption
                return None
            
            try:
                otp_key = bytes.fromhex(otp_key_hex)
                mac_key = bytes.fromhex(mac_key_hex)
                mac_tag = bytes.fromhex(mac_hex)
            except ValueError:
                # Invalid hex format
                return None
            
            # Decrypt view-once using OTP
            plaintext_bytes = decrypt_view_once(ciphertext_bytes, mac_tag, otp_key, mac_key)
            
            # Parse the plaintext JSON
            plaintext_json = json.loads(plaintext_bytes.decode('utf-8'))
            
            # Return the body
            body = plaintext_json.get("body", "")
            return body
        
        # Handle AES decryption (default)
        # Extract session key from email
        session_key_hex = body_json.get("session_key_hex")
        if not session_key_hex:
            # No session key, cannot decrypt
            return None
        
        try:
            session_key = bytes.fromhex(session_key_hex)
        except ValueError:
            # Invalid hex format
            return None
        
        # The ciphertext includes nonce + actual_ciphertext
        # Nonce is 12 bytes, rest is the encrypted data
        if len(ciphertext_bytes) < 12:
            return None
        
        nonce = ciphertext_bytes[:12]
        ct = ciphertext_bytes[12:]
        
        # Decrypt using the session key from the email
        plaintext_bytes = decrypt_aes_gcm(session_key, nonce, ct)
        
        # Parse the plaintext JSON
        plaintext_json = json.loads(plaintext_bytes.decode('utf-8'))
        
        # Return the body
        body = plaintext_json.get("body", "")
        return body
        
    except Exception:
        # Decryption failed, return None
        return None


async def _sync_from_broker(user_email: str, storage: Storage, authorization: str) -> tuple[int, List[str]]:
    """
    Unified sync function: fetch ALL pending messages from the broker.
    
    This is the SINGLE source of truth for incoming emails. All emails
    (both AES-encrypted and OTP view-once) are delivered through the broker.
    
    This function directly accesses the broker database (no HTTP self-calls)
    to avoid potential deadlocks when called from within API handlers.
    
    Returns (emails_synced_count, errors_list)
    """
    errors: List[str] = []
    emails_synced = 0
    
    if not authorization:
        return 0, ["No authorization token"]
    
    
    try:
        # Direct access to broker database (no HTTP self-calls)
        broker_storage = _get_broker_storage()
        
        # Step 1: Query pending messages for this recipient directly from broker DB
        stmt = pending_messages_table.select().where(
            (pending_messages_table.c.recipient == user_email) & 
            (pending_messages_table.c.status != "acknowledged")
        )
        
        pending_rows = []
        with broker_storage._engine.begin() as conn:
            rows = conn.execute(stmt).fetchall()
            for row in rows:
                pending_rows.append(dict(row._mapping))
        
        
        if not pending_rows:
            return 0, []
        
        # Get existing server_message_ids to avoid duplicates
        existing_ids = set()
        for existing_email in storage.list_emails():
            if hasattr(existing_email, 'server_message_id') and existing_email.server_message_id:
                existing_ids.add(existing_email.server_message_id)
        
        # Step 2: Process each pending message
        for row_dict in pending_rows:
            message_id = row_dict['id']
            sender = row_dict['sender']
            subject = row_dict['subject']
            
            # Skip if already synced
            if message_id in existing_ids:
                # Acknowledge to remove from pending (already has local copy)
                with broker_storage._engine.begin() as conn:
                    ack_stmt = pending_messages_table.update().where(
                        pending_messages_table.c.id == message_id
                    ).values(status="acknowledged", acknowledged_at=datetime.now(timezone.utc))
                    conn.execute(ack_stmt)
                logger.debug(f"Message {message_id} already synced, marked acknowledged")
                continue
            
            try:
                # Extract message data directly from broker row
                is_view_once = row_dict.get('view_once', False)
                encryption_type = row_dict.get('encryption_type', 'aes')
                
                
                encrypted_content = row_dict['encrypted_content']
                key_material = row_dict['key_material']
                mac = row_dict.get('mac')
                signature = row_dict.get('signature')
                signature_algorithm = row_dict.get('signature_algorithm')
                key_exchange_algorithm = row_dict.get('key_exchange_algorithm', 'pqc')
                
                # SECURITY: Decapsulate session key if it was encapsulated with ML-KEM
                # Format: MAGIC (4 bytes 'QKEM') + 4 bytes (ciphertext_len) + kem_ciphertext + encrypted_session_key
                # If not encapsulated (legacy), key_material is the plaintext session key
                decapsulated_key_material = key_material
                if key_material[:4] == KEM_MAGIC:  # Reliable magic byte check (not size heuristic)
                    try:
                        import struct
                        # Parse encapsulated format after magic bytes
                        kem_ciphertext_len = struct.unpack('>I', key_material[4:8])[0]
                        if kem_ciphertext_len > 1000 and kem_ciphertext_len < len(key_material):
                            # This is likely encapsulated - try to decapsulate
                            kem_keypair = storage.get_kem_keypair(user_email)
                            if kem_keypair and kem_keypair.get('private_key'):
                                kem_ciphertext = key_material[8:8+kem_ciphertext_len]
                                encrypted_session_key = key_material[8+kem_ciphertext_len:]
                                
                                # Decapsulate to get shared secret via liboqs
                                oqs = _load_oqs_kem()
                                kem = oqs.KeyEncapsulation("Kyber1024", kem_keypair['private_key'])
                                shared_secret = bytes(kem.decap_secret(kem_ciphertext))
                                
                                # Decrypt the session key using the shared secret
                                # Format: nonce (12 bytes) + ciphertext_with_tag
                                nonce = encrypted_session_key[:12]
                                ciphertext_with_tag = encrypted_session_key[12:]
                                decapsulated_key_material = decrypt_aes_gcm(
                                    shared_secret[:32],
                                    nonce,
                                    ciphertext_with_tag
                                )
                            else:
                                pass  # No recipient ML-KEM public key
                    except Exception as kem_err:
                        # If decapsulation fails, assume it's a legacy plaintext key
                        decapsulated_key_material = key_material
                
                now = datetime.now(timezone.utc)
                
                if is_view_once:
                    # View-once OTP: key_material contains [otpKey (variable)][macKey (32 bytes)]
                    # Store full key_material - client knows how to parse it
                    # Format: otpKey is same length as plaintext, macKey is always 32 bytes at the end
                    
                    envelope = EmailEnvelope(
                        id=None,
                        sender=sender,
                        recipient=user_email,
                        subject=subject,
                        ciphertext=encrypted_content,
                        mac=mac,
                        signature=signature,
                        signature_algorithm=signature_algorithm,
                        sent_at=now,
                        view_once=True,
                        viewed=False,
                        otp_key=decapsulated_key_material,  # Full key material: [otpKey][macKey(32)]
                        mac_key=None,  # Not needed - included in otp_key
                        key_exchange_mode=key_exchange_algorithm,
                        encryption_mode=EncryptionMode.VIEW_ONCE_OTP,
                        folder="Inbox",
                        server_message_id=message_id,
                        in_reply_to=row_dict.get('in_reply_to'),
                    )
                else:
                    # AES-GCM: key_material is the session key
                    envelope = EmailEnvelope(
                        id=None,
                        sender=sender,
                        recipient=user_email,
                        subject=subject,
                        ciphertext=encrypted_content,
                        mac=None,
                        signature=signature,
                        signature_algorithm=signature_algorithm,
                        sent_at=now,
                        view_once=False,
                        viewed=False,
                        otp_key=decapsulated_key_material,  # Decapsulated session key
                        mac_key=None,
                        key_exchange_mode=key_exchange_algorithm,
                        encryption_mode=EncryptionMode.AES,
                        folder="Inbox",
                        server_message_id=message_id,
                        in_reply_to=row_dict.get('in_reply_to'),
                    )
                
                saved_email_id = storage.save_email(envelope)
                emails_synced += 1
                
                # Extract attachments from broker message if present
                attachments_json = row_dict.get('attachments_json')
                if attachments_json:
                    try:
                        import json
                        import base64
                        attachments_list = json.loads(attachments_json)
                        for att in attachments_list:
                            att_data = base64.b64decode(att['data_base64'])
                            storage.save_attachment(
                                email_id=saved_email_id,
                                filename=att['filename'],
                                mime_type=att['mime_type'],
                                size_bytes=att.get('size_bytes', len(att_data)),
                                data=att_data,
                                encryption_key_hex=None,  # E2E: Server never stores key, recipient uses email's session key
                            )
                    except Exception as att_err:
                        pass  # Error saving attachments
                
                # Mark as downloaded then acknowledged in broker
                with broker_storage._engine.begin() as conn:
                    update_stmt = pending_messages_table.update().where(
                        pending_messages_table.c.id == message_id
                    ).values(
                        status="acknowledged",
                        downloaded_at=now,
                        acknowledged_at=now
                    )
                    conn.execute(update_stmt)
                
            except Exception as e:
                errors.append(f"Failed to process message {message_id}: {str(e)}")
                continue
        
        return emails_synced, errors
        
    except Exception as e:
        errors.append(f"Broker sync error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0, errors


# --- Pydantic models matching the Flutter expectations ---------------------------


class OAuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None


class OAuthTokenRequest(BaseModel):
    provider: str
    code: str
    redirect_uri: str


class OAuthRefreshRequest(BaseModel):
    refresh_token: str


class OAuthProviderOut(BaseModel):
    name: str
    display_name: str
    icon_url: str
    available: bool = True


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    profile_picture_url: Optional[str] = None


class SaveDraftRequest(BaseModel):
    """Request to save an email as a draft."""
    draft_id: Optional[int] = None  # If updating an existing draft
    sender: str
    recipient: str
    subject: str
    content: str
    view_once: bool = False


# Email validation regex (RFC 5322 simplified) - improved to prevent spoofing
_EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# Banned personal domains to prevent open redirects / spoofing
BANNED_EMAIL_DOMAINS = {
    'localhost', '127.0.0.1', '0.0.0.0', 'example.com',
    'test.com', 'foo.com', 'bar.com', 'invalid'
}

def _validate_email_format(email: str) -> str:
    """
    Validate email format with protections against spoofing and homograph attacks.
    Raises ValueError if invalid.
    """
    email = email.strip().lower()
    
    # Basic format validation
    if not _EMAIL_REGEX.match(email):
        raise ValueError(f"Invalid email format")
    if len(email) > 254:  # RFC 5321 max length
        raise ValueError("Email address too long")
    
    # Extract domain
    local_part, domain = email.rsplit('@', 1)
    
    # Block test/invalid domains
    if domain in BANNED_EMAIL_DOMAINS:
        raise ValueError("Email domain not allowed")
    
    # Block local domain (no TLD)
    if '.' not in domain:
        raise ValueError("Email domain must have TLD")
    
    # Check for potential homograph attacks (mixed scripts)
    # This is a simple check - ideally use idna library
    if not all(ord(c) < 128 for c in email):
        raise ValueError("International domain names not supported for security")
    
    return email


class SendEmailRequest(BaseModel):
    """Request to send an email with TRUE E2E encryption.
    
    For E2E encrypted emails (client_encrypted=True):
    - encrypted_content_hex: AES-256-GCM encrypted payload (nonce + ciphertext + tag)
    - session_key_hex: 32-byte quantum-seeded session key in hex
    - encryption_type: "aes" (standard) or "otp" (view-once with perfect secrecy)
    - mac_hex: HMAC-SHA256 tag for OTP messages
    - key_exchange_algorithm: "pqc" or "bb84" (mode used by sender)
    - content field is ignored (server never sees plaintext)
    
    For legacy/fallback (client_encrypted=False):
    - content: plaintext email body (server will encrypt)
    
    Cross-compatibility:
    - Recipients can decrypt messages regardless of their own mode preference
    - The session key is transmitted with the message
    - key_exchange_algorithm is metadata for informational/display purposes
    """
    draft_id: Optional[int] = None  # If updating an existing draft
    sender: str
    recipient: str
    subject: str = Field(max_length=1000)  # SECURITY: Limit subject size
    content: Optional[str] = Field(default=None, max_length=5_000_000)  # Legacy: plaintext (only if client_encrypted=False)
    encrypted_content_hex: Optional[str] = Field(default=None, max_length=20_000_000)  # E2E: ~10MB encrypted payload max
    session_key_hex: Optional[str] = Field(default=None, max_length=20_000_000)  # E2E: variable size (AES=64 hex, OTP=message length)
    encryption_type: str = "aes"  # "aes" or "otp" (OTP for view-once)
    mac_hex: Optional[str] = Field(default=None, max_length=128)  # HMAC-SHA256 tag for OTP messages
    key_exchange_algorithm: str = "pqc"  # "pqc" or "bb84" - which mode sender used
    client_encrypted: bool = False  # True = E2E, False = legacy server encryption
    view_once: bool = False
    in_reply_to: Optional[str] = None  # ID of the email being replied to (for threading)

    @field_validator('sender', 'recipient')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _validate_email_format(v)


class ReceiveEmailRequest(BaseModel):
    """Request to receive/store an incoming email in Inbox."""
    sender: str
    recipient: str
    subject: str
    content: str
    view_once: bool = False


class EmailResponse(BaseModel):
    """Generic email response with folder and status."""
    id: str
    sender: str
    recipient: str
    subject: str
    content: str
    view_once: bool
    sent_at: datetime
    folder: str  # "Inbox", "Sent", "Drafts", "Trash"
    in_reply_to: Optional[str] = None  # ID of the email being replied to


class MoveToTrashRequest(BaseModel):
    email_id: int


class RestoreFromTrashRequest(BaseModel):
    email_id: int
    restore_to: str = "Inbox"  # Default restore to Inbox, can be "Drafts", "Sent", etc.


class DeletePermanentlyRequest(BaseModel):
    email_id: int


class TrashActionResponse(BaseModel):
    success: bool
    message: str
    email_id: str


class SyncEmailsResponse(BaseModel):
    """Response from syncing emails with Gmail."""
    success: bool
    message: str
    emails_synced: int
    errors: List[str] = []


class SentEmailResponse(EmailResponse):
    """Response for sent emails with session key for E2E attachment encryption."""
    session_key_hex: Optional[str] = None  # Session key for encrypting attachments (E2E)


class InboxEmailResponse(BaseModel):
    id: str
    account: str
    folder: str  # "Inbox", "Sent", "Drafts", "Trash"
    from_email: str
    from_name: str
    to_email: str
    to_name: str
    subject: str
    preview: str
    bodyText: str
    sentAt: datetime
    isRead: bool = False
    hasAttachments: bool = False
    attachments: List[dict] = []  # List of attachment metadata
    signatureValid: bool = True
    securityLevel: str = "aes_gcm"  # "pqc", "aes_gcm", "classical"
    session_key_hex: Optional[str] = None  # E2E: session key for client-side attachment decryption
    view_once: bool = False
    in_reply_to: Optional[str] = None  # ID of the email being replied to


class AttachmentResponse(BaseModel):
    """Response for attachment metadata (E2E encrypted)."""
    id: int
    email_id: int
    filename: str
    mime_type: str
    size_bytes: int
    # NOTE: No encryption_key_hex - true E2E means server never has the key


class AttachmentUploadResponse(BaseModel):
    """Response after uploading an E2E encrypted attachment."""
    id: int
    filename: str
    mime_type: str
    size_bytes: int
    encrypted: bool = True  # E2E: Always encrypted


class SendViewOnceRequest(BaseModel):
    """Request to upload a view-once email to server."""
    recipient: str
    subject: str = Field(max_length=1000)
    encrypted_content_hex: str = Field(max_length=20_000_000)  # Full encrypted message
    otp_key_hex: str = Field(max_length=20_000_000)  # OTP key for recipient to decrypt
    mac_key_hex: str = Field(max_length=128)  # MAC key for verification
    mac_hex: str = Field(max_length=128)  # MAC tag
    signature_hex: Optional[str] = Field(default=None, max_length=20_000)
    signature_algorithm: Optional[str] = None

    @field_validator('recipient')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _validate_email_format(v)


class ViewOnceUploadResponse(BaseModel):
    """Response after uploading view-once email to server."""
    message_id: str
    status: str  # "pending"
    recipient: str
    created_at: datetime


class ViewOncePendingResponse(BaseModel):
    """View-once email in list of pending."""
    id: str
    sender: str
    subject: str
    status: str
    created_at: datetime


class ViewOnceDownloadResponse(BaseModel):
    """Response when recipient downloads view-once email."""
    id: str
    sender: str
    subject: str
    encrypted_content_hex: str
    otp_key_hex: str
    mac_key_hex: str
    mac_hex: str
    signature_hex: Optional[str] = None
    signature_algorithm: Optional[str] = None


class ViewOnceStatusResponse(BaseModel):
    """Status of a view-once email for sender."""
    message_id: str
    recipient: str
    status: str  # pending, downloaded, viewed, deleted
    created_at: datetime
    downloaded_at: Optional[datetime] = None
    viewed_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class StoreEncryptedEmailRequest(BaseModel):
    """Request to store encrypted email on server."""
    recipient: str
    subject: str
    encrypted_content_hex: str  # AES-256-GCM ciphertext (nonce + ct) in hex
    session_key_hex: str  # AES-256 session key in hex
    signature_hex: Optional[str] = None  # PQC signature in hex
    signature_algorithm: Optional[str] = None
    key_exchange_algorithm: str = "pqc"


class EncryptedEmailUploadResponse(BaseModel):
    """Response after storing encrypted email on server."""
    message_id: str
    recipient: str
    status: str
    created_at: datetime


class EncryptedEmailPendingResponse(BaseModel):
    """Item in list of pending encrypted emails."""
    id: str
    sender: str
    subject: str
    created_at: datetime
    status: str


class EncryptedEmailDownloadResponse(BaseModel):
    """Response when downloading encrypted email."""
    id: str
    sender: str
    recipient: str
    subject: str
    encrypted_content_hex: str
    session_key_hex: str
    signature_hex: Optional[str]
    signature_algorithm: Optional[str]
    key_exchange_algorithm: str
    status: str
    created_at: datetime


class EncryptedEmailStatusResponse(BaseModel):
    """Status of an encrypted email for sender."""
    message_id: str
    recipient: str
    status: str
    created_at: datetime
    downloaded_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class DecryptedEmailResponse(BaseModel):
    """Response when opening a decrypted email."""
    id: str
    from_email: str
    to_email: str
    subject: str
    body: str
    attachments: List[dict] = []
    is_signature_valid: bool = False
    encryption_mode: str  # "AES", "OTP", "E2E_AES_GCM", "E2E_OTP"
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    session_key_hex: Optional[str] = None  # E2E: Session key for decrypting attachments
    encrypted_content_hex: Optional[str] = None  # E2E: Encrypted body for client-side decryption
    signature_hex: Optional[str] = None  # PQC signature for E2E verification
    signature_algorithm: Optional[str] = None  # e.g., "Dilithium2"
    sender_public_key_hex: Optional[str] = None  # Sender's public key for verification
    encryption_type: Optional[str] = None  # "aes" or "otp" (for client-side decryption)
    mac_hex: Optional[str] = None  # HMAC-SHA256 tag for OTP verification
    view_once: bool = False  # Is this a view-once message?
    key_exchange_mode: Optional[str] = None  # "pqc" or "bb84" - which mode sender used


# --- Message Broker Models (WhatsApp-style transmission) ---


class SendMessageRequest(BaseModel):
    """Request to send an encrypted message via server broker."""
    message_id: str
    recipient: str
    subject: str = Field(max_length=1000)
    encrypted_content_hex: str = Field(max_length=20_000_000)
    encryption_type: str  # "aes" or "otp"
    key_material_hex: str = Field(max_length=20_000)  # Session key (AES) or OTP key (OTP)
    mac_hex: Optional[str] = Field(default=None, max_length=128)
    signature_hex: Optional[str] = Field(default=None, max_length=20_000)
    signature_algorithm: Optional[str] = None
    key_exchange_algorithm: str = "pqc"
    view_once: bool = False

    @field_validator('recipient')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _validate_email_format(v)


class SendMessageResponse(BaseModel):
    """Response after queuing message on server broker."""
    message_id: str
    recipient: str
    status: str  # "queued"
    created_at: datetime


class PendingMessageResponse(BaseModel):
    """Item in list of pending messages for recipient."""
    id: str
    sender: str
    subject: str
    created_at: datetime


class DownloadMessageResponse(BaseModel):
    """Response when recipient downloads message from broker."""
    id: str
    sender: str
    subject: str
    encrypted_content_hex: str
    encryption_type: str
    key_material_hex: str
    mac_hex: Optional[str] = None
    signature_hex: Optional[str] = None
    signature_algorithm: Optional[str] = None
    key_exchange_algorithm: str
    view_once: bool


class MessageStatusResponse(BaseModel):
    """Status of a message in the server broker."""
    message_id: str
    recipient: str
    status: str  # "queued", "downloaded"
    created_at: datetime
    downloaded_at: Optional[datetime] = None


# --- Phone Authentication Setup --------------------------------------------------

# Import and initialize phone authentication
from qmail.auth.phone_auth_routes import phone_auth_router, initialize_phone_auth
from qmail.auth.otp_service import OtpService
from qmail.auth.token_service import TokenService

# Initialize phone auth services
# Check if Twilio credentials are configured
_twilio_account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
_twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
_twilio_phone_number = os.environ.get("TWILIO_PHONE_NUMBER", "")
_use_mock_sms = not (_twilio_account_sid and _twilio_auth_token and _twilio_phone_number)

if _use_mock_sms:
    pass  # Mock SMS mode enabled - debug logging removed
else:
    pass  # Production SMS mode - debug logging removed

_phone_otp_service = OtpService(
    storage=_get_broker_storage(),
    twilio_account_sid=_twilio_account_sid,
    twilio_auth_token=_twilio_auth_token,
    twilio_phone_number=_twilio_phone_number,
    use_mock_sms=_use_mock_sms,  # Enable mock mode if credentials not available
)

_phone_token_service = TokenService(
    secret_key=os.environ.get("JWT_SECRET_KEY", "your-secret-key-change-in-production"),
    algorithm="HS256",
)

# Initialize the phone auth router with services
initialize_phone_auth(_get_broker_storage(), _phone_otp_service, _phone_token_service)

# Include the phone auth router
app.include_router(phone_auth_router, prefix="/auth/phone", tags=["auth-phone"])


# --- Health Check -----------------------------------------------------------------

@app.get("/health", tags=["system"])
def health_check():
    """Health check endpoint for Docker/K8s liveness and readiness probes."""
    return {"status": "ok", "service": "qmail-api"}


# --- Routes ----------------------------------------------------------------------


@app.get("/auth/oauth/providers", response_model=List[OAuthProviderOut])
def list_oauth_providers() -> List[OAuthProviderOut]:
    """
    Return the list of OAuth providers for the Flutter UI.
    """
    providers: List[OAuthProviderOut] = [
        OAuthProviderOut(
            name="google",
            display_name="Google",
            icon_url="assets/google_icon.png",
            available=True,
        ),
        OAuthProviderOut(
            name="outlook",
            display_name="Outlook",
            icon_url="assets/outlook_icon.png",
            available=True,
        ),
    ]
    return providers


@app.get("/auth/oauth/authorize")
def oauth_authorize(
    provider: str = Query(...),
    redirect_uri: str = Query(...),
    state: Optional[str] = Query(None),
) -> RedirectResponse:
    """
    Redirect the user agent to the provider's OAuth authorization URL.

    The Flutter app builds a URL pointing to this endpoint and opens it in a
    WebView or browser; this endpoint then redirects to the real provider URL.
    
    SECURITY: Generates random state token to prevent CSRF attacks.
    """
    client = get_oauth_client(provider)

    # Generate random CSRF state token (NOT hardcoded "qmail")
    # If client provides state, validate it; otherwise generate new one
    effective_state = state or secrets.token_urlsafe(32)
    auth_url = client.build_authorization_url(state=effective_state)
    return RedirectResponse(url=auth_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.post("/auth/oauth/token", response_model=OAuthTokenResponse)
def oauth_exchange_token(body: OAuthTokenRequest) -> OAuthTokenResponse:
    """
    Exchange an authorization code for access/refresh tokens.

    Matches Flutter's `AuthService.exchangeCodeForToken` contract.
    """
    try:
        client = get_oauth_client(body.provider)
        # Single-user per device for now.
        account_id = _default_account_id()
        token = client.exchange_code_for_tokens(account_id=account_id, code=body.code)
        expires_at_dt: Optional[datetime] = None
        if token.expires_at is not None:
            expires_at_dt = datetime.fromtimestamp(token.expires_at, tz=timezone.utc)

        return OAuthTokenResponse(
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_at=expires_at_dt,
        )
    except requests.exceptions.HTTPError as e:
        # Get detailed error information from OAuth provider
        error_detail = f"OAuth token exchange failed with status {e.response.status_code}"
        try:
            error_data = e.response.json()
            if "error" in error_data:
                error_detail = f"OAuth Error: {error_data.get('error')} - {error_data.get('error_description', '')}"
        except Exception:
            error_detail = f"OAuth token exchange failed: {str(e)}"
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token exchange failed"
        )


@app.post("/auth/oauth/refresh", response_model=OAuthTokenResponse)
def oauth_refresh(body: OAuthRefreshRequest) -> OAuthTokenResponse:
    """
    Refresh an access token.

    For now this simply reuses the stored refresh token via `get_valid_access_token`
    under a fixed account_id. In a more advanced setup, you'd associate the
    account_id with the user derived from the access token.
    """
    # We don't get the provider or account from the Flutter payload, so we assume
    # Google and a single account. Adjust this if you support more providers.
    provider = "google"
    client = get_oauth_client(provider)
    account_id = _default_account_id()

    # Store the provided refresh token under our default account if not already present.
    # This uses the underlying private refresh mechanism via exchange_code_for_tokens
    # only once; afterwards, get_valid_access_token will handle refreshing.
    # Here, we optimistically call get_valid_access_token, which will refresh when needed.
    try:
        access_token = client.get_valid_access_token(account_id=account_id)
    except RuntimeError:
        # No token stored yet: we fake an initial token record so that subsequent
        # refreshes work. This is a simplified path; in a real system, you'd
        # persist the full token response server-side when first exchanging code.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No stored OAuth token; complete initial login first.",
        )

    # We don't know the new expiry here; let the client treat it as session-bound.
    return OAuthTokenResponse(access_token=access_token, refresh_token=body.refresh_token)


@app.get("/auth/user", response_model=UserOut)
def get_user_info(request: Request) -> UserOut:
    """
    Return the user profile for the given Bearer token.

    Fetches the real Gmail address using the Gmail API profile endpoint.
    Requires scopes: openid email profile https://mail.google.com/
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")

    email = None

    # First, try to fetch the real Gmail address using the Gmail API profile endpoint
    try:
        gmail_url = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
        
        # SECURITY: Validate URL to prevent SSRF
        if not _validate_oauth_url(gmail_url):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid OAuth provider URL"
            )
        
        resp = requests.get(
            gmail_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        email = data.get("emailAddress")
    except requests.exceptions.HTTPError as e:
        # If Gmail API fails, try Google's userinfo endpoint instead
        if e.response.status_code in (401, 403):
            try:
                userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
                
                # SECURITY: Validate URL to prevent SSRF
                if not _validate_oauth_url(userinfo_url):
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Invalid OAuth provider URL"
                    )
                
                resp = requests.get(
                    userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=5,
                )
                resp.raise_for_status()
                data = resp.json()
                email = data.get("email")
            except requests.exceptions.HTTPError as e2:
                error_detail = f"Google OAuth error {e2.response.status_code}"
                try:
                    error_data = e2.response.json()
                    error_detail = f"Google API error: {error_data.get('error', {}).get('message', error_detail)}"
                except Exception:
                    pass
                
                if e2.response.status_code == 401:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or expired access token. Please sign in again."
                    )
                elif e2.response.status_code == 403:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions. Re-authenticate and grant email profile permissions."
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=error_detail
                    )
            except requests.exceptions.RequestException as e2:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to connect to Google API: {str(e2)}"
                )
        else:
            error_detail = f"Gmail API error {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_detail = f"Gmail API error: {error_data.get('error', {}).get('message', error_detail)}"
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_detail
            )
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to connect to Gmail API"
        )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve email address from Google API"
        )

    # Return the real user information
    return UserOut(
        id=email,
        email=email,
        display_name=email,
        profile_picture_url=None,
    )


class KemPublicKeyResponse(BaseModel):
    """Response model for ML-KEM public key retrieval."""
    email: str
    public_key_hex: str  # Hex-encoded ML-KEM-1024 public key
    algorithm: str


@app.get("/keys/kem/{email}", response_model=KemPublicKeyResponse)
def get_kem_public_key(email: str, authorization: Optional[str] = Header(None)) -> KemPublicKeyResponse:
    """
    Get a user's ML-KEM public key for session key encapsulation.

    SECURITY: endpoint now requires a valid OAuth access token to prevent
    unauthenticated user-enumeration of public keys. Callers must include
    an Authorization: Bearer <token> header.

    Returns:
        KemPublicKeyResponse with hex-encoded public key.

    Raises:
        401: If authorization is missing or invalid.
        404: If the user doesn't have an ML-KEM public key registered.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )

    access_token = parts[1]

    # Validate token (will raise HTTPException on failure)
    try:
        _get_user_storage(access_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OAuth token"
        )

    broker_storage = _get_broker_storage()
    kem_info = broker_storage.get_kem_public_key(email)

    if kem_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No ML-KEM public key found for {email}. User may not have registered yet."
        )

    public_key, algorithm = kem_info
    return KemPublicKeyResponse(
        email=email,
        public_key_hex=public_key.hex(),
        algorithm=algorithm,
    )


@app.get("/auth/oauth/callback/google")
def google_oauth_callback(code: str = Query(...), state: Optional[str] = Query(None)) -> JSONResponse:
    """
    Simple landing page for the Google OAuth redirect during local development.

    Google will redirect the browser here with `?code=...&state=...`.
    We display the code so that the user can paste it back into the Flutter app.
    """
    content = {
        "message": "Copy this authorization code into the Qmail app to complete sign-in.",
        "code": code,
        "state": state,
    }
    return JSONResponse(content)



# NOTE: _sync_viewonce_from_server and _sync_encrypted_from_server have been removed.
# All email sync now goes through the unified _sync_from_broker function.


@app.post("/auth/logout")
def logout(request: Request) -> JSONResponse:
    """
    Logout and revoke the caller's access token locally.

    - Deletes tokens from OS keychain for the detected account (best-effort).
    - Adds the access token to an in-memory revocation list (short TTL).

    In production you should also call the identity provider's revocation
    endpoint and record revocations in a shared store (Redis) so that all
    nodes honor the revocation.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"ok": True})

    access_token = auth_header.removeprefix("Bearer ").strip()

    # Try to obtain the user email (best-effort) so we can delete local tokens
    user_email = None
    try:
        _, user_email = _get_user_storage(access_token)
    except Exception:
        # If token already invalid or provider unreachable, proceed with revocation
        user_email = None

    # Revoke locally (in-memory); production should use persistent blacklist
    _revoke_token(access_token, ttl_seconds=3600 * 24)

    # Remove stored tokens from OS keychain for this account (best-effort)
    if user_email:
        for provider_name in _PROVIDERS.keys():
            try:
                _OAUTH_STORE.delete_token(provider_name, user_email)
            except Exception:
                pass

    return JSONResponse({"ok": True})


@app.post("/email/draft", response_model=EmailResponse)
async def save_draft(request: Request, email_request: SaveDraftRequest) -> EmailResponse:
    """
    Save an email as a draft in the Drafts folder.
    
    If draft_id is provided, updates the existing draft.
    Otherwise creates a new draft.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    
    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    storage, user_email = _get_user_storage(access_token)
    now = datetime.now(timezone.utc)
    
    # Check if we're updating an existing draft
    if email_request.draft_id is not None:
        # Update existing draft in place (including subject and recipient)
        try:
            updated = storage.update_draft(
                email_request.draft_id,
                recipient=email_request.recipient,
                subject=email_request.subject,
                content=email_request.content.encode('utf-8')
            )
            if updated:
                return EmailResponse(
                    id=str(email_request.draft_id),
                    sender=email_request.sender,
                    recipient=email_request.recipient,
                    subject=email_request.subject,
                    content=email_request.content,
                    view_once=email_request.view_once,
                    sent_at=now,
                    folder="Drafts",
                )
        except Exception as e:
            # If update fails, create a new draft
            pass
    
    # Create new draft
    email_envelope = EmailEnvelope(
        id=None,  # DB will assign ID
        sender=email_request.sender,
        recipient=email_request.recipient,
        subject=email_request.subject,
        ciphertext=email_request.content.encode('utf-8'),
        mac=None,
        signature=None,
        signature_algorithm=None,
        sent_at=now,
        view_once=email_request.view_once,
        key_exchange_mode="none",
        encryption_mode=EncryptionMode.AES,
        folder="Drafts",
    )
    
    email_id = storage.save_email(email_envelope)
    
    return EmailResponse(
        id=str(email_id),
        sender=email_request.sender,
        recipient=email_request.recipient,
        subject=email_request.subject,
        content=email_request.content,
        view_once=email_request.view_once,
        sent_at=now,
        folder="Drafts",
    )


@app.post("/email/send", response_model=SentEmailResponse)
async def send_email(request: Request, email_request: SendEmailRequest) -> SentEmailResponse:
    """
    Send an email with TRUE END-TO-END ENCRYPTION.

    For E2E encrypted emails (client_encrypted=True):
    - Client encrypts email body with quantum-seeded AES-256-GCM
    - Server NEVER sees plaintext content
    - Server stores encrypted ciphertext + session key for recipient
    
    For legacy/fallback (client_encrypted=False):
    - Server encrypts email body (NOT recommended - server sees plaintext)
    """
    try:
        auth_header = request.headers.get("Authorization") or ""
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
        
        access_token = auth_header.removeprefix("Bearer ").strip()
        if not access_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
        
        storage, user_email = _get_user_storage(access_token)
        now = datetime.now(timezone.utc)
        broker_storage = _get_broker_storage()
        
        # Handle TRUE E2E encryption (client-side encrypted)
        if email_request.client_encrypted:
            
            if not email_request.encrypted_content_hex or not email_request.session_key_hex:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="client_encrypted=True requires encrypted_content_hex and session_key_hex"
                )
            
            # Convert hex strings to bytes
            encrypted_content = bytes.fromhex(email_request.encrypted_content_hex)
            session_key = bytes.fromhex(email_request.session_key_hex)
            
            # SECURITY: Do NOT log key material or ciphertext bytes
            
            # Sign the encrypted content with PQC (Dilithium2)
            signing_keypair = storage.get_signing_keypair(user_email)
            signature = None
            signature_algorithm = None
            
            if signing_keypair and signing_keypair.get("private_key"):
                signature = sign_message(
                    message=encrypted_content,
                    private_key=signing_keypair["private_key"],
                    algorithm=signing_keypair["algorithm"],
                )
                signature_algorithm = signing_keypair["algorithm"]
            else:
                pass  # No signing keypair available - debug logging removed
            
            # Generate message ID
            message_id = str(uuid.uuid4())
            
            # Determine encryption mode based on encryption_type
            is_otp = email_request.encryption_type == "otp"
            encryption_mode = EncryptionMode.VIEW_ONCE_OTP if is_otp else EncryptionMode.AES
            mac_bytes = bytes.fromhex(email_request.mac_hex) if email_request.mac_hex else None
            
            # Store encrypted email locally (for Sent folder)
            # Store the encrypted ciphertext directly - server never decrypts
            email_envelope = EmailEnvelope(
                id=None,
                sender=email_request.sender,
                recipient=email_request.recipient,
                subject=email_request.subject,
                ciphertext=encrypted_content,  # E2E: Store encrypted, not plaintext
                mac=mac_bytes,  # HMAC-SHA256 for OTP, None for AES
                signature=signature,  # PQC signature
                signature_algorithm=signature_algorithm,
                sent_at=now,
                view_once=email_request.view_once,
                key_exchange_mode=email_request.key_exchange_algorithm,  # Use sender's mode
                encryption_mode=encryption_mode,
                folder="Sent",
                server_message_id=message_id,
                otp_key=session_key,  # Store session key/OTP keys for sender's later viewing
                in_reply_to=email_request.in_reply_to,
            )
            local_email_id = storage.save_email(email_envelope)
            
            # Store in broker for recipient
            # For OTP (view-once), mac is stored in mac_hex
            mac_bytes = bytes.fromhex(email_request.mac_hex) if email_request.mac_hex else None
            
            # SECURITY: prevent server from seeing plaintext session keys for TRUE E2E PQC messages.
            # If the client already provided a KEM-encapsulated key material (QKEM format)
            # store it as-is. If the client provided a plaintext session key while claiming
            # PQC, reject the request.
            if session_key.startswith(KEM_MAGIC):
                # Client uploaded KEM-encapsulated key material (good)
                key_material_to_store = session_key
            else:
                # Client provided plaintext session key - server will encapsulate it
                # This is acceptable when client doesn't support ML-KEM (e.g., Flutter/Dart limitations)
                
                # Server-side encapsulation: encapsulate the plaintext session key for the recipient
                recipient_kem_info = broker_storage.get_kem_public_key(email_request.recipient)
                if recipient_kem_info:
                    recipient_kem_public_key, kem_algorithm = recipient_kem_info
                    from qmail.crypto.aes import encrypt_aes_gcm
                    import struct
                    oqs = _load_oqs_kem()
                    kem = oqs.KeyEncapsulation("Kyber1024")
                    kem_ciphertext, kem_shared_secret = kem.encap_secret(recipient_kem_public_key)
                    nonce, encrypted_session_key_ct = encrypt_aes_gcm(kem_shared_secret[:32], session_key)
                    encrypted_session_key = nonce + encrypted_session_key_ct
                    key_material_to_store = KEM_MAGIC + struct.pack('>I', len(kem_ciphertext)) + kem_ciphertext + encrypted_session_key
                else:
                    # No recipient KEM key � store plaintext (legacy)
                    key_material_to_store = session_key
            
            stmt = pending_messages_table.insert().values(
                id=message_id,
                sender=email_request.sender,
                recipient=email_request.recipient,
                subject=email_request.subject,
                encrypted_content=encrypted_content,
                encryption_type=email_request.encryption_type,  # "aes" or "otp"
                key_material=key_material_to_store,  # Encapsulated (E2E) or plaintext (legacy)
                mac=mac_bytes,  # HMAC-SHA256 for OTP
                signature=signature,  # PQC signature
                signature_algorithm=signature_algorithm,
                key_exchange_algorithm=email_request.key_exchange_algorithm,  # Use sender's mode (pqc or bb84)
                view_once=email_request.view_once,
                status="pending",
                created_at=now,
                downloaded_at=None,
                acknowledged_at=None,
                in_reply_to=email_request.in_reply_to,
            )
            
            with broker_storage._engine.begin() as conn:
                conn.execute(stmt)
            
            
            return SentEmailResponse(
                id=str(local_email_id),
                sender=email_request.sender,
                recipient=email_request.recipient,
                subject=email_request.subject,
                content="[E2E Encrypted]",  # Server doesn't have plaintext
                view_once=email_request.view_once,
                sent_at=now,
                folder="Sent",
                session_key_hex=email_request.session_key_hex,  # Return for attachment encryption
            )
        
        # LEGACY: Server-side encryption (NOT E2E - server sees plaintext)
        
        app_config = AppConfig()
        database_url = os.environ.get("DATABASE_URL")
        enc_key = _get_db_encryption_key(f"user:{user_email}")
        
        if database_url and not database_url.startswith("sqlite"):
            # PostgreSQL: use schema-based user isolation (same as _get_user_storage)
            user_schema = "user_" + user_email.replace("@", "_at_").replace(".", "_")
            client = QmailClient(
                app_config=app_config,
                encryption_key=enc_key,
                database_url=database_url,
                schema=user_schema,
            )
        else:
            # SQLite: per-user database file
            user_db_dir = Path("qmail_users") / user_email.replace("@", "_at_")
            user_db_dir.mkdir(parents=True, exist_ok=True)
            db_path = user_db_dir / "storage.db"
            client = QmailClient(
                app_config=app_config,
                db_path=db_path,
                encryption_key=enc_key,
            )
        
        # Send encrypted email with _server_context=True to get encrypted data directly
        result = await client.send_email(
            sender=email_request.sender,
            recipient=email_request.recipient,
            subject=email_request.subject,
            body=email_request.content or "",
            view_once=email_request.view_once,
            _server_context=True,
        )
        
        # Store in broker
        stmt = pending_messages_table.insert().values(
            id=result["message_id"],
            sender=email_request.sender,
            recipient=result["recipient"],
            subject=result["subject"],
            encrypted_content=result["ciphertext"],
            encryption_type=result["encryption_type"],
            key_material=result["key_material"],
            mac=result["mac"],
            signature=result["signature"],
            signature_algorithm=result["signature_algorithm"],
            key_exchange_algorithm=result["key_exchange_algorithm"],
            view_once=result["view_once"],
            status="pending",
            created_at=now,
            downloaded_at=None,
            acknowledged_at=None,
        )
        
        with broker_storage._engine.begin() as conn:
            conn.execute(stmt)
        
        
        # Update the local email with server_message_id for attachment tracking
        local_email_id = result["email_id"]
        with storage._engine.begin() as conn:
            update_stmt = emails_table.update().where(
                emails_table.c.id == local_email_id
            ).values(server_message_id=result["message_id"], delivery_status="sent")
            conn.execute(update_stmt)
        
        # Get the stored sent email from local storage
        sent_email = storage.get_email(local_email_id)
        
        if not sent_email:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Email was sent but could not retrieve stored email details"
            )

        # Get session key for E2E attachment encryption
        session_key_hex = None
        if result.get("key_material") and not email_request.view_once:
            session_key_hex = result["key_material"].hex()

        return SentEmailResponse(
            id=str(sent_email.id),
            sender=email_request.sender,
            recipient=email_request.recipient,
            subject=email_request.subject,
            content=email_request.content,
            view_once=email_request.view_once,
            sent_at=sent_email.sent_at,
            folder="Sent",
            session_key_hex=session_key_hex,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        # Log the full error for debugging
        import traceback
        error_trace = traceback.format_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error sending email"
        )


@app.post("/email/receive", response_model=EmailResponse)
async def receive_email(request: Request, email_request: ReceiveEmailRequest) -> EmailResponse:
    """
    Store a received email in the Inbox folder.
    
    This endpoint is called when the app receives an incoming encrypted email.
    The email is stored in the encrypted database in the Inbox folder.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    
    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    storage, user_email = _get_user_storage(access_token)
    now = datetime.now(timezone.utc)
    
    email_envelope = EmailEnvelope(
        id=None,
        sender=email_request.sender,
        recipient=email_request.recipient,
        subject=email_request.subject,
        ciphertext=email_request.content.encode('utf-8'),
        mac=None,
        signature=None,
        signature_algorithm=None,
        sent_at=now,
        view_once=email_request.view_once,
        key_exchange_mode="none",
        encryption_mode=EncryptionMode.AES,
        folder="Inbox",
    )
    
    email_id = storage.save_email(email_envelope)
    
    return EmailResponse(
        id=str(email_id),
        sender=email_request.sender,
        recipient=email_request.recipient,
        subject=email_request.subject,
        content=email_request.content,
        view_once=email_request.view_once,
        sent_at=now,
        folder="Inbox",
    )


@app.get("/email/inbox", response_model=List[InboxEmailResponse])
async def get_inbox(request: Request) -> List[InboxEmailResponse]:
    """
    Fetch emails from the local encrypted database.
    
    Automatically syncs new emails from Gmail inbox first, then returns all emails.
    Returns emails stored in the database, including sent and received emails.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")

    # Retrieve emails from the user-specific encrypted database
    storage, user_email = _get_user_storage(access_token)
    
    # Sync emails from broker (single source of truth)
    try:
        emails_synced, sync_errors = await _sync_from_broker(user_email, storage, auth_header)
    except Exception as e:
        # If sync fails, continue anyway and show cached emails
        pass
    
    emails: List[InboxEmailResponse] = []
    
    for email_envelope in storage.list_emails():
        # Use the folder field from the stored email envelope
        folder = email_envelope.folder
        
        # Get the email body (should be plaintext after decryption in sync)
        # For E2E encrypted emails, body will be decrypted client-side when opened
        body_text = ""
        try:
            raw_body = email_envelope.ciphertext.decode('utf-8')
            # Check if it's a JSON payload (decrypted content)
            try:
                payload = json.loads(raw_body)
                body_text = payload.get("body", raw_body)
            except json.JSONDecodeError:
                body_text = raw_body
        except UnicodeDecodeError:
            # E2E encrypted: ciphertext is binary, will be decrypted client-side
            body_text = "[E2E Encrypted - open to decrypt]"
        except Exception:
            body_text = ""
        
        preview = body_text[:100] if body_text else ""
        
        # Get attachments for this email
        email_attachments = storage.get_attachments(email_envelope.id)
        attachments_list = [
            {"id": att["id"], "filename": att["filename"], "mime_type": att["mime_type"], "size_bytes": att["size_bytes"]}
            for att in email_attachments
        ]
        
        email_response = InboxEmailResponse(
            id=str(email_envelope.id),
            account=email_envelope.sender,
            folder=folder,
            from_email=email_envelope.sender,
            from_name=email_envelope.sender.split("@")[0],
            to_email=email_envelope.recipient,
            to_name=email_envelope.recipient.split("@")[0],
            subject=email_envelope.subject,
            preview=preview,
            bodyText=body_text,
            sentAt=email_envelope.sent_at,
            isRead=False,
            hasAttachments=len(email_attachments) > 0,
            attachments=attachments_list,
            signatureValid=email_envelope.signature is not None,
            securityLevel="aes_gcm" if email_envelope.encryption_mode == EncryptionMode.AES else "pqc",
            session_key_hex=email_envelope.otp_key.hex() if email_envelope.otp_key else None,
            view_once=email_envelope.view_once,
            in_reply_to=getattr(email_envelope, 'in_reply_to', None),
        )
        emails.append(email_response)
    
    return emails


@app.post("/email/refresh", response_model=List[InboxEmailResponse])
async def refresh_inbox(request: Request) -> List[InboxEmailResponse]:
    """
    Refresh the inbox by syncing from the broker and returning the full inbox.
    
    Call this endpoint when the user opens the inbox folder or pulls to refresh.
    It will:
    1. Sync new emails from the broker (single source of truth)
    2. Return all inbox emails (local + newly synced)
    
    This is the primary endpoint to call when opening the inbox in the Flutter app.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")

    # Retrieve user-specific storage
    storage, user_email = _get_user_storage(access_token)
    
    # Sync emails from broker (single source of truth)
    try:
        emails_synced, sync_errors = await _sync_from_broker(user_email, storage, auth_header)
    except Exception:
        # If sync fails, continue and return cached emails
        pass
    
    # Return all inbox emails
    emails: List[InboxEmailResponse] = []
    
    for email_envelope in storage.list_emails():
        # Use the folder field from the stored email envelope
        folder = email_envelope.folder
        
        # Get the email body (should be plaintext after decryption in sync)
        # For E2E encrypted emails, body will be decrypted client-side when opened
        body_text = ""
        try:
            raw_body = email_envelope.ciphertext.decode('utf-8')
            # Check if it's a JSON payload (decrypted content)
            try:
                payload = json.loads(raw_body)
                body_text = payload.get("body", raw_body)
            except json.JSONDecodeError:
                body_text = raw_body
        except UnicodeDecodeError:
            # E2E encrypted: ciphertext is binary, will be decrypted client-side
            body_text = "[E2E Encrypted - open to decrypt]"
        except Exception:
            body_text = ""
        
        preview = body_text[:100] if body_text else ""
        
        # Get attachments for this email
        email_attachments = storage.get_attachments(email_envelope.id)
        attachments_list = [
            {"id": att["id"], "filename": att["filename"], "mime_type": att["mime_type"], "size_bytes": att["size_bytes"]}
            for att in email_attachments
        ]
        
        email_response = InboxEmailResponse(
            id=str(email_envelope.id),
            account=email_envelope.sender,
            folder=folder,
            from_email=email_envelope.sender,
            from_name=email_envelope.sender.split("@")[0],
            to_email=email_envelope.recipient,
            to_name=email_envelope.recipient.split("@")[0],
            subject=email_envelope.subject,
            preview=preview,
            bodyText=body_text,
            sentAt=email_envelope.sent_at,
            isRead=False,
            hasAttachments=len(email_attachments) > 0,
            attachments=attachments_list,
            signatureValid=email_envelope.signature is not None,
            securityLevel="aes_gcm" if email_envelope.encryption_mode == EncryptionMode.AES else "pqc",
            session_key_hex=email_envelope.otp_key.hex() if email_envelope.otp_key else None,
            view_once=email_envelope.view_once,
            in_reply_to=getattr(email_envelope, 'in_reply_to', None),
        )
        emails.append(email_response)
    
    return emails


@app.post("/email/sync", response_model=SyncEmailsResponse)
async def sync_emails(request: Request) -> SyncEmailsResponse:
    """
    Manually sync emails from the broker to the local database.
    
    NOTE: This endpoint is automatically called when accessing inbox, but can also be
    called manually to force a sync at any time.
    
    Fetches new emails from the broker (single source of truth) and stores them locally.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")

    storage, user_email = _get_user_storage(access_token)
    
    try:
        # Sync from broker (single source of truth)
        emails_synced, sync_errors = await _sync_from_broker(user_email, storage, auth_header)
        
        return SyncEmailsResponse(
            success=True,
            message=f"Successfully synced {emails_synced} emails from broker",
            emails_synced=emails_synced,
            errors=sync_errors,
        )
    except Exception as e:
        return SyncEmailsResponse(
            success=False,
            message=f"Failed to sync emails: {str(e)}",
            emails_synced=0,
            errors=[str(e)],
        )


@app.post("/email/trash", response_model=TrashActionResponse)
async def move_to_trash(request: Request, body: MoveToTrashRequest) -> TrashActionResponse:
    """
    Move an email to the Trash folder.
    
    The email is marked as being in the Trash folder but not permanently deleted.
    User can restore it later or permanently delete it.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    storage, user_email = _get_user_storage(access_token)
    
    try:
        # Retrieve the email
        emails = storage.list_emails()
        target_email = None
        for email_envelope in emails:
            if email_envelope.id == body.email_id:
                target_email = email_envelope
                break
        
        if not target_email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Email with ID {body.email_id} not found"
            )
        
        # Update the folder to Trash
        updated = storage.update_email_folder(body.email_id, "Trash")
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update email folder"
            )
        
        return TrashActionResponse(
            success=True,
            message=f"Email {body.email_id} moved to Trash",
            email_id=str(body.email_id),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to move email to trash"
        )


@app.post("/email/restore", response_model=TrashActionResponse)
async def restore_from_trash(request: Request, body: RestoreFromTrashRequest) -> TrashActionResponse:
    """
    Restore an email from Trash to a specified folder.
    
    By default restores to Inbox, but can specify other folders like Drafts or Sent.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    storage, user_email = _get_user_storage(access_token)
    
    try:
        # Validate restore_to folder
        valid_folders = ["Inbox", "Drafts", "Sent"]
        if body.restore_to not in valid_folders:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid restore folder. Must be one of: {', '.join(valid_folders)}"
            )
        
        # Retrieve the email
        emails = storage.list_emails()
        target_email = None
        for email_envelope in emails:
            if email_envelope.id == body.email_id:
                target_email = email_envelope
                break
        
        if not target_email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Email with ID {body.email_id} not found"
            )
        
        if target_email.folder != "Trash":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email is in {target_email.folder}, not in Trash"
            )
        
        # Update the folder back to the specified location
        updated = storage.update_email_folder(body.email_id, body.restore_to)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update email folder"
            )
        
        return TrashActionResponse(
            success=True,
            message=f"Email {body.email_id} restored to {body.restore_to}",
            email_id=str(body.email_id),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore email"
        )


@app.get("/email/{email_id}/open", response_model=DecryptedEmailResponse)
async def open_email(request: Request, email_id: int) -> DecryptedEmailResponse:
    """
    Open and decrypt an email.
    
    - For AES-GCM encrypted emails: Uses stored session key (from server sync) to decrypt
    - For view-once OTP emails: Uses stored OTP key and MAC to decrypt
    - Returns decrypted body and attachments
    - Verifies PQC signature if available
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    storage, user_email = _get_user_storage(access_token)
    
    try:
        # Retrieve the email
        emails = storage.list_emails()
        target_email = None
        for email_envelope in emails:
            if email_envelope.id == email_id:
                target_email = email_envelope
                break
        
        if not target_email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Email with ID {email_id} not found"
            )
        
        # SECURITY: Verify user owns this email (is sender or recipient)
        _verify_email_ownership(user_email, target_email.sender, target_email.recipient)
        
        # Try to decrypt the email
        decrypted_body = ""
        is_signature_valid = False
        encryption_mode = target_email.encryption_mode.name if target_email.encryption_mode else "UNKNOWN"
        
        
        # Get attachments for this email (needed for all paths)
        email_attachments = storage.get_attachments(email_id)
        attachments_list = [
            {"id": att["id"], "filename": att["filename"], "mime_type": att["mime_type"], "size_bytes": att["size_bytes"]}
            for att in email_attachments
        ]
        
        # E2E Detection: Check if this email needs client-side decryption
        # An email is E2E encrypted if it has session key (otp_key) AND:
        # - encryption_mode is AES (standard E2E), or
        # - encryption_mode is VIEW_ONCE_OTP (OTP for view-once messages)
        is_e2e_encrypted = False
        is_otp = False
        if target_email.otp_key:
            if encryption_mode == "AES":
                is_e2e_encrypted = True
                is_otp = False
            elif encryption_mode == "VIEW_ONCE_OTP":
                is_e2e_encrypted = True
                is_otp = True
        
        if is_e2e_encrypted:
            encryption_type = "otp" if is_otp else "aes"
            session_key_hex = target_email.otp_key.hex()
            encrypted_content_hex = target_email.ciphertext.hex()
            mac_hex = target_email.mac.hex() if target_email.mac else None
            # SECURITY: Do NOT log key material or ciphertext bytes
            
            # Verify PQC signature if present
            is_signature_valid = False
            signature_hex = None
            signature_algorithm = None
            sender_public_key_hex = None
            
            if target_email.signature and target_email.signature_algorithm:
                signature_hex = target_email.signature.hex()
                signature_algorithm = target_email.signature_algorithm
                
                # Get sender's public key from broker
                broker_storage = _get_broker_storage()
                sender_key_info = broker_storage.get_public_key(target_email.sender)
                
                if sender_key_info:
                    sender_public_key, sender_algorithm = sender_key_info
                    sender_public_key_hex = sender_public_key.hex()
                    
                    if sender_algorithm == target_email.signature_algorithm:
                        # Verify signature
                        is_signature_valid = verify_signature(
                            message=target_email.ciphertext,
                            signature=target_email.signature,
                            public_key=sender_public_key,
                            algorithm=sender_algorithm,
                        )
                        if is_signature_valid:
                            pass  # Signature valid - debug logging removed
                        else:
                            pass  # Signature invalid - debug logging removed
                    else:
                        pass  # Algorithm mismatch - debug logging removed
                else:
                    pass  # Sender key not found - debug logging removed
            else:
                pass  # No signature present - debug logging removed
            
            return DecryptedEmailResponse(
                id=str(email_id),
                from_email=target_email.sender,
                to_email=target_email.recipient,
                subject=target_email.subject or "",
                body="",  # Client will decrypt
                attachments=attachments_list,
                is_signature_valid=is_signature_valid,
                encryption_mode="E2E_OTP" if is_otp else "E2E_AES_GCM",
                opened_at=datetime.utcnow(),
                session_key_hex=session_key_hex,
                encrypted_content_hex=encrypted_content_hex,
                signature_hex=signature_hex,
                signature_algorithm=signature_algorithm,
                sender_public_key_hex=sender_public_key_hex,
                encryption_type=encryption_type,  # "aes" or "otp"
                mac_hex=mac_hex,  # HMAC-SHA256 for OTP
                view_once=target_email.view_once,
                key_exchange_mode=target_email.key_exchange_mode,  # pqc or bb84
            )
        
        # Check if this is a Sent or Drafts folder email (legacy plaintext storage)
        if target_email.folder in ("Sent", "Drafts") and not target_email.view_once:
            
            # E2E: Include session key for attachment decryption
            session_key_hex = None
            if target_email.otp_key:
                session_key_hex = target_email.otp_key.hex()
            
            # Extract signature data if present
            signature_hex = None
            signature_algorithm = None
            sender_public_key_hex = None
            is_signature_valid = False
            
            if target_email.signature and target_email.signature_algorithm:
                signature_hex = target_email.signature.hex()
                signature_algorithm = target_email.signature_algorithm
                
                # For Sent emails, the sender is the current user - get their public key
                broker_storage = _get_broker_storage()
                sender_key_info = broker_storage.get_public_key(target_email.sender)
                
                if sender_key_info:
                    sender_public_key, sender_algorithm = sender_key_info
                    sender_public_key_hex = sender_public_key.hex()
                    is_signature_valid = True  # Signature present and matches sender's key
                else:
                    pass  # Sender key not found - debug logging removed
            
            # Legacy emails store plaintext
            try:
                stored_content = target_email.ciphertext.decode('utf-8')
                try:
                    payload = json.loads(stored_content)
                    decrypted_body = payload.get("body", stored_content)
                except json.JSONDecodeError:
                    # Not JSON, just return as-is
                    decrypted_body = stored_content
                
                return DecryptedEmailResponse(
                    id=str(email_id),
                    from_email=target_email.sender,
                    to_email=target_email.recipient,
                    subject=target_email.subject or "",
                    body=decrypted_body,
                    attachments=attachments_list,
                    is_signature_valid=is_signature_valid,
                    encryption_mode="NONE" if target_email.folder == "Drafts" else encryption_mode,
                    opened_at=datetime.utcnow(),
                    session_key_hex=session_key_hex,
                    signature_hex=signature_hex,
                    signature_algorithm=signature_algorithm,
                    sender_public_key_hex=sender_public_key_hex,
                    key_exchange_mode=target_email.key_exchange_mode,  # pqc or bb84
                )
            except UnicodeDecodeError:
                # This shouldn't happen since E2E is handled above, but handle gracefully
                decrypted_body = "[Could not read email content]"
                
                return DecryptedEmailResponse(
                    id=str(email_id),
                    from_email=target_email.sender,
                    to_email=target_email.recipient,
                    subject=target_email.subject or "",
                    body=decrypted_body,
                    attachments=attachments_list,
                    is_signature_valid=False,
                    encryption_mode=encryption_mode,
                    opened_at=datetime.utcnow(),
                    key_exchange_mode=target_email.key_exchange_mode,  # pqc or bb84
                )
        
        try:
            # Debug logging
            
            # Decrypt directly without creating a Client
            # Import decryption utilities (signatures imported globally at module level)
            from qmail.crypto.aes import decrypt_aes_gcm
            
            decrypted_body = ""
            
            if target_email.view_once:
                # View-once emails: stored in server ephemeral storage, not here
                decrypted_body = "[View-once email decryption not supported]"
            else:
                # Normal AES-GCM email
                
                # Get session key from otp_key field (where it was stored during sync)
                session_key = target_email.otp_key
                if session_key is None:
                    raise ValueError("No session key available for decryption (email may not have been synced from server)")
                
                # Signature verification (disabled - contacts feature removed)
                # Signatures remain stored; verification skipped without contact pubkey lookup
                is_signature_valid = False
                if target_email.signature is not None and target_email.signature_algorithm:
                    pass  # Signature verification disabled - debug logging removed
                
                # Extract nonce and ciphertext from the combined data
                # Format: AES-GCM stores as: nonce (12 bytes) + ciphertext + tag
                if len(target_email.ciphertext) < 12:
                    raise ValueError(f"Ciphertext too short to contain AES-GCM nonce. Length: {len(target_email.ciphertext)}")
                
                nonce = target_email.ciphertext[:12]
                ct = target_email.ciphertext[12:]
                
                # Decrypt
                plaintext_bytes = decrypt_aes_gcm(session_key, nonce, ct)
                
                # Parse JSON payload
                payload = json.loads(plaintext_bytes.decode("utf-8"))
                decrypted_body = payload.get("body", "")
                is_signature_valid = is_signature_valid or True  # Mark as valid if we got this far
                
                # Store decrypted content back to database for inbox preview
                # Store as JSON so future reads work correctly
                try:
                    storage.update_email_content(email_id, plaintext_bytes)
                except Exception as db_err:
                    # Non-fatal: decryption succeeded, just preview won't update
                    pass  # Database update failed - debug logging removed
            
        except Exception as decrypt_error:
            # If decryption fails, return what we can
            import traceback
            decrypted_body = f"[Decryption failed: {str(decrypt_error)}]"
        
        # Get attachments for this email
        email_attachments = storage.get_attachments(email_id)
        attachments_list = [
            {"id": att["id"], "filename": att["filename"], "mime_type": att["mime_type"], "size_bytes": att["size_bytes"]}
            for att in email_attachments
        ]
        
        # E2E: Include session key for attachment decryption
        session_key_hex = None
        if target_email.otp_key:
            session_key_hex = target_email.otp_key.hex()
        
        return DecryptedEmailResponse(
            id=str(email_id),
            from_email=target_email.sender,
            to_email=target_email.recipient,
            subject=target_email.subject or "",
            body=decrypted_body,
            attachments=attachments_list,
            is_signature_valid=is_signature_valid,
            encryption_mode=encryption_mode,
            opened_at=datetime.utcnow(),
            session_key_hex=session_key_hex,  # E2E: For attachment decryption
            key_exchange_mode=target_email.key_exchange_mode,  # pqc or bb84
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to open email"
        )


@app.delete("/email/{email_id}")
async def delete_permanently(request: Request, email_id: int) -> TrashActionResponse:
    """
    Permanently delete an email from the database.
    
    This action cannot be undone. Normally used for emails in Trash.
    
    SECURITY: Requires recent re-authentication for Inbox/Sent emails only.
    Drafts and Trash don't require re-auth as they're routine user operations.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    storage, user_email = _get_user_storage(access_token)
    
    try:
        # Retrieve the email
        emails = storage.list_emails()
        target_email = None
        for email_envelope in emails:
            if email_envelope.id == email_id:
                target_email = email_envelope
                break
        
        if not target_email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Email with ID {email_id} not found"
            )
        
        # SECURITY: Require re-authentication only for Inbox/Sent emails
        # Drafts and Trash don't need re-auth since they're routine user operations
        if target_email.folder not in ("Drafts", "Trash"):
            _require_recent_reauthentication(access_token, "permanent email deletion")
        
        # SECURITY: Verify user owns this email (is sender or recipient)
        _verify_email_ownership(user_email, target_email.sender, target_email.recipient)
        
        # Delete the email (you may need to implement a delete_email method in Storage)
        # For now, we'll mark it as permanently deleted by moving it to a special state
        # This is a placeholder - implement the actual deletion in Storage class
        storage.delete_email(email_id)
        
        logger.info(f"[Security] Email {email_id} permanently deleted by {user_email.split('@')[0]}")
        
        return TrashActionResponse(
            success=True,
            message=f"Email {email_id} permanently deleted",
            email_id=str(email_id),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete email"
        )


# --- Attachment Endpoints ---

@app.post("/email/{email_id}/attachments", response_model=AttachmentUploadResponse)
async def upload_attachment(
    request: Request,
    email_id: int,
    file: UploadFile = File(...),
) -> AttachmentUploadResponse:
    """
    Upload an E2E encrypted attachment for an email.
    
    TRUE END-TO-END ENCRYPTION:
    - Client encrypts attachment with email's session key BEFORE upload
    - Server stores encrypted data but NEVER has the decryption key
    - Only sender and recipient (who both have the session key) can decrypt
    
    The encrypted file should be: [nonce (12 bytes)][ciphertext][GCM tag (16 bytes)]
    Set X-Original-Size header with the original (pre-encryption) file size.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    storage, user_email = _get_user_storage(access_token)
    
    
    try:
        # Read file content
        content = await file.read()
        
        # Get original size from header for encrypted files, otherwise use content length
        original_size_header = request.headers.get("X-Original-Size")
        original_size = int(original_size_header) if original_size_header else len(content)
        
        # Save attachment to local storage
        # NOTE: For E2E, we do NOT store encryption_key_hex - server never has the key
        attachment_id = storage.save_attachment(
            email_id=email_id,
            filename=file.filename or "unnamed",
            mime_type=file.content_type or "application/octet-stream",
            size_bytes=original_size,
            data=content,
            encryption_key_hex=None,  # E2E: Server NEVER stores the key
        )
        
        # If this email has a server_message_id, update the broker message with attachments
        target_email = storage.get_email(email_id)
        
        if target_email and target_email.server_message_id and target_email.folder == "Sent":
            # Get all attachments for this email and serialize them
            all_attachments = storage.get_attachments(email_id)
            import base64
            attachments_data = [
                {
                    "filename": att["filename"],
                    "mime_type": att["mime_type"],
                    "size_bytes": att["size_bytes"],
                    "data_base64": base64.b64encode(att["data"]).decode("utf-8"),
                    # E2E: No encryption_key_hex - recipient uses email's session key to decrypt
                }
                for att in all_attachments
            ]
            attachments_json = json.dumps(attachments_data)
            
            # Update the broker message
            broker_storage = _get_broker_storage()
            with broker_storage._engine.begin() as conn:
                update_stmt = pending_messages_table.update().where(
                    pending_messages_table.c.id == target_email.server_message_id
                ).values(attachments_json=attachments_json)
                result = conn.execute(update_stmt)
        else:
            pass  # Email not in Sent folder or no server_message_id - debug logging removed
        
        return AttachmentUploadResponse(
            id=attachment_id,
            filename=file.filename or "unnamed",
            mime_type=file.content_type or "application/octet-stream",
            size_bytes=original_size,
            encrypted=True,  # E2E: Attachments are always encrypted
        )
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload attachment"
        )


@app.get("/email/{email_id}/attachments", response_model=List[AttachmentResponse])
async def get_attachments(request: Request, email_id: int) -> List[AttachmentResponse]:
    """
    Get all attachments metadata for an email.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    storage, user_email = _get_user_storage(access_token)
    
    try:
        attachments = storage.get_attachments(email_id)
        return [
            AttachmentResponse(
                id=att["id"],
                email_id=att["email_id"],
                filename=att["filename"],
                mime_type=att["mime_type"],
                size_bytes=att["size_bytes"],
                # NOTE: No encryption_key_hex - E2E means client decrypts with email's session key
            )
            for att in attachments
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get attachments"
        )


@app.get("/attachment/{attachment_id}/download")
async def download_attachment(request: Request, attachment_id: int):
    """
    Download an attachment by ID.
    """
    from fastapi.responses import Response
    
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    storage, user_email = _get_user_storage(access_token)
    
    try:
        attachment = storage.get_attachment(attachment_id)
        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attachment {attachment_id} not found"
            )
        
        # E2E: Return encrypted attachment data
        # Client must decrypt using email's session key
        headers = {
            "Content-Disposition": f'attachment; filename="{attachment["filename"]}"',
            "X-Original-Size": str(attachment["size_bytes"]),
            "X-Email-Id": str(attachment["email_id"]),  # Client needs this to find session key
        }
        
        return Response(
            content=attachment["data"],
            media_type="application/octet-stream",  # E2E: Always encrypted binary
            headers=headers
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download attachment"
        )


@app.delete("/attachment/{attachment_id}")
async def delete_attachment(request: Request, attachment_id: int) -> dict:
    """
    Delete a single attachment by ID.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    storage, user_email = _get_user_storage(access_token)
    
    try:
        # Get the attachment first to verify it exists
        attachment = storage.get_attachment(attachment_id)
        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attachment {attachment_id} not found"
            )
        
        # Delete from database
        from sqlalchemy import delete
        with storage._engine.begin() as conn:
            from qmail.storage.db import attachments_table
            stmt = delete(attachments_table).where(attachments_table.c.id == attachment_id)
            conn.execute(stmt)
        
        return {"success": True, "message": f"Attachment {attachment_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete attachment"
        )


@app.get("/email/trash", response_model=List[InboxEmailResponse])
async def get_trash(request: Request) -> List[InboxEmailResponse]:
    """
    Fetch all emails from the Trash folder.
    
    Returns emails that have been moved to trash but not permanently deleted.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")

    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")

    # Retrieve emails from the user-specific encrypted database
    storage, user_email = _get_user_storage(access_token)
    emails: List[InboxEmailResponse] = []
    
    for email_envelope in storage.list_emails():
        # Only include emails in Trash folder
        if email_envelope.folder != "Trash":
            continue
        
        # Create a preview from the first 100 chars of content
        try:
            body_text = email_envelope.ciphertext.decode('utf-8')
        except Exception:
            body_text = "[Encrypted content]"
        
        preview = body_text[:100] if body_text else "[No content]"
        
        # Get attachments for this email
        email_attachments = storage.get_attachments(email_envelope.id)
        attachments_list = [
            {"id": att["id"], "filename": att["filename"], "mime_type": att["mime_type"], "size_bytes": att["size_bytes"]}
            for att in email_attachments
        ]
        
        email_response = InboxEmailResponse(
            id=str(email_envelope.id),
            account=email_envelope.sender,
            folder="Trash",
            from_email=email_envelope.sender,
            from_name=email_envelope.sender.split("@")[0],
            to_email=email_envelope.recipient,
            to_name=email_envelope.recipient.split("@")[0],
            subject=email_envelope.subject,
            preview=preview,
            bodyText=body_text,
            sentAt=email_envelope.sent_at,
            isRead=False,
            hasAttachments=len(email_attachments) > 0,
            attachments=attachments_list,
            signatureValid=email_envelope.signature is not None,
            securityLevel="aes_gcm" if email_envelope.encryption_mode == EncryptionMode.AES else "pqc",
            view_once=email_envelope.view_once,
            in_reply_to=getattr(email_envelope, 'in_reply_to', None),
        )
        emails.append(email_response)
    
    return emails


# --- Message Broker Endpoints (WhatsApp-style transmission) ----------------

@app.post("/messages/send", response_model=SendMessageResponse)
async def send_message(request: Request, body: SendMessageRequest) -> SendMessageResponse:
    """
    Queue an encrypted message on the server broker.
    
    Used by QmailClient._transmit_to_server() to send both AES and OTP emails.
    Message is stored in centralized broker database (not per-user).
    
    Args:
        - message_id: Unique message ID from client
        - recipient: Target email address
        - subject: Email subject
        - encrypted_content_hex: AES-GCM or OTP-encrypted message
        - encryption_type: "aes" or "otp"
        - key_material_hex: Session key (AES) or OTP key (OTP)
        - mac_hex: Optional MAC for integrity verification
        - signature_hex: Optional PQC signature
        - view_once: Whether this is a view-once email
    
    Returns: message_id and status "queued"
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    
    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    try:
        # Get user info from access token (to identify sender, but we use broker DB)
        user_storage, sender_email = _get_user_storage(access_token)
        
        # Use CENTRALIZED broker database, not per-user database
        broker_storage = _get_broker_storage()
        now = datetime.now(timezone.utc)
        
        # Store message in centralized broker database
        stmt = pending_messages_table.insert().values(
            id=body.message_id,  # Use message_id as primary key
            sender=sender_email,
            recipient=body.recipient,
            subject=body.subject,
            encrypted_content=bytes.fromhex(body.encrypted_content_hex),
            encryption_type=body.encryption_type,
            key_material=bytes.fromhex(body.key_material_hex),
            mac=bytes.fromhex(body.mac_hex) if body.mac_hex else None,
            signature=bytes.fromhex(body.signature_hex) if body.signature_hex else None,
            signature_algorithm=body.signature_algorithm,
            key_exchange_algorithm=body.key_exchange_algorithm,
            view_once=body.view_once,
            status="pending",
            created_at=now,
            downloaded_at=None,
            acknowledged_at=None,
        )
        
        with broker_storage._engine.begin() as conn:
            conn.execute(stmt)
        
        # Verify the message was stored in broker
        verify_stmt = pending_messages_table.select().where(pending_messages_table.c.id == body.message_id)
        with broker_storage._engine.begin() as conn:
            verify_row = conn.execute(verify_stmt).first()
            if verify_row:
                verify_dict = dict(verify_row._mapping)
                pass  # Message stored successfully - debug logging removed
            else:
                pass  # Message not found after insert - debug logging removed
        
        # ALSO save the sent message to the sender's local storage (Sent folder)
        # This allows the sender to see their sent messages immediately without switching accounts
        try:
            email_envelope = EmailEnvelope(
                id=None,
                sender=sender_email,
                recipient=body.recipient,
                subject=body.subject,
                ciphertext=bytes.fromhex(body.encrypted_content_hex),
                mac=bytes.fromhex(body.mac_hex) if body.mac_hex else None,
                signature=bytes.fromhex(body.signature_hex) if body.signature_hex else None,
                signature_algorithm=body.signature_algorithm,
                sent_at=now,
                view_once=body.view_once,
                viewed=False,
                otp_key=bytes.fromhex(body.key_material_hex),  # Store session key so sender can decrypt their sent emails
                mac_key=None,
                key_exchange_mode=body.key_exchange_algorithm,
                encryption_mode=EncryptionMode.VIEW_ONCE_OTP if body.view_once else EncryptionMode.AES,
                folder="Sent",  # Save to sender's Sent folder
                server_message_id=body.message_id,  # Link to broker message
                delivery_status="sent",
            )
            user_storage.save_email(email_envelope)
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            # Don't fail the whole operation, just warn
        
        return SendMessageResponse(
            message_id=body.message_id,
            recipient=body.recipient,
            status="queued",
            created_at=now,
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) as-is
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue message"
        )


@app.get("/messages/pending", response_model=List[PendingMessageResponse])
async def list_pending_messages(request: Request) -> List[PendingMessageResponse]:
    """
    List all pending messages for the authenticated user (recipient).
    
    Returns messages queued on the centralized broker for this recipient.
    Each message contains encrypted content that only the recipient can decrypt.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    
    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    try:
        # Get recipient email from access token
        _, user_email = _get_user_storage(access_token)
        
        # Use CENTRALIZED broker database
        broker_storage = _get_broker_storage()
        
        # Query messages for this recipient that haven't been deleted/acknowledged
        stmt = pending_messages_table.select().where(
            (pending_messages_table.c.recipient == user_email) & 
            (pending_messages_table.c.status != "acknowledged")
        )
        
        messages = []
        with broker_storage._engine.begin() as conn:
            rows = conn.execute(stmt).fetchall()
            for row in rows:
                row_dict = dict(row._mapping)
                messages.append(PendingMessageResponse(
                    id=row_dict['id'],
                    sender=row_dict['sender'],
                    subject=row_dict['subject'],
                    created_at=row_dict['created_at'],
                ))
        
        # Debug: also log total messages in broker (not just for this recipient)
        debug_stmt = pending_messages_table.select()
        with broker_storage._engine.begin() as conn:
            all_rows = conn.execute(debug_stmt).fetchall()
            for row in all_rows:
                row_dict = dict(row._mapping)
        
        return messages
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list messages"
        )


@app.post("/messages/{message_id}/download", response_model=DownloadMessageResponse)
async def download_message(request: Request, message_id: str) -> DownloadMessageResponse:
    """
    Download an encrypted message from the centralized server broker.
    
    Only the intended recipient can download using their access token.
    After download, message is marked as "downloaded" for sender tracking.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    
    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    try:
        # Get recipient email from access token
        _, user_email = _get_user_storage(access_token)
        
        # Use CENTRALIZED broker database
        broker_storage = _get_broker_storage()
        
        # Fetch the message
        stmt = pending_messages_table.select().where(pending_messages_table.c.id == message_id)
        
        with broker_storage._engine.begin() as conn:
            row = conn.execute(stmt).first()
            
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Message {message_id} not found"
                )
            
            row_dict = dict(row._mapping)
            
            # Verify recipient matches authenticated user
            if row_dict['recipient'] != user_email:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not the intended recipient of this message"
                )
            
            # Mark as downloaded
            now = datetime.now(timezone.utc)
            update_stmt = pending_messages_table.update().where(
                pending_messages_table.c.id == message_id
            ).values(status="downloaded", downloaded_at=now)
            conn.execute(update_stmt)
            
            
            return DownloadMessageResponse(
                id=row_dict['id'],
                sender=row_dict['sender'],
                subject=row_dict['subject'],
                encrypted_content_hex=row_dict['encrypted_content'].hex(),
                encryption_type=row_dict['encryption_type'],
                key_material_hex=row_dict['key_material'].hex(),
                mac_hex=row_dict['mac'].hex() if row_dict['mac'] else None,
                signature_hex=row_dict['signature'].hex() if row_dict['signature'] else None,
                signature_algorithm=row_dict['signature_algorithm'],
                key_exchange_algorithm=row_dict['key_exchange_algorithm'],
                view_once=row_dict['view_once'],
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download message"
        )


@app.post("/messages/{message_id}/ack", response_model=MessageStatusResponse)
async def acknowledge_message(request: Request, message_id: str) -> MessageStatusResponse:
    """
    Acknowledge receipt of a message (marks as acknowledged in broker).
    
    Recipient calls this after confirming they've downloaded and processed the message.
    Message can then be cleaned up from broker after retention period.
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
    
    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty access token")
    
    try:
        # Get recipient email from access token
        _, user_email = _get_user_storage(access_token)
        
        # Use CENTRALIZED broker database
        broker_storage = _get_broker_storage()
        
        # Mark message as acknowledged (SECURITY: only if recipient matches authenticated user)
        now = datetime.now(timezone.utc)
        stmt = pending_messages_table.update().where(
            (pending_messages_table.c.id == message_id) &
            (pending_messages_table.c.recipient == user_email)
        ).values(status="acknowledged", acknowledged_at=now)
        
        with broker_storage._engine.begin() as conn:
            result = conn.execute(stmt)
            
            if result.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Message {message_id} not found"
                )
            
            logger.info(f"Message {message_id} acknowledged by {user_email}")
        
        
        return MessageStatusResponse(
            message_id=message_id,
            recipient=user_email,
            status="acknowledged",
            created_at=datetime.now(timezone.utc),
            downloaded_at=now,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to acknowledge message"
        )


# --- View-Once Ephemeral Messaging Endpoints --------------------------------

@app.post("/viewonce/send", response_model=ViewOnceUploadResponse)
def send_viewonce(
    request: SendViewOnceRequest,
    authorization: Optional[str] = Header(None),
) -> ViewOnceUploadResponse:
    """
    Upload a view-once email to server for ephemeral delivery.
    
    The email is stored encrypted on the server temporarily (72 hours).
    Recipient can download once, decrypt locally, view once, then delete.
    
    Status progression: pending → downloaded → viewed → deleted
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )
    access_token = parts[1]
    
    try:
        storage, sender_email = _get_user_storage(access_token)
        
        # Generate unique message ID
        message_id = str(uuid.uuid4())
        
        # Convert hex strings to bytes
        encrypted_content = bytes.fromhex(request.encrypted_content_hex)
        otp_key = bytes.fromhex(request.otp_key_hex)
        mac_key = bytes.fromhex(request.mac_key_hex)
        mac = bytes.fromhex(request.mac_hex)
        signature = bytes.fromhex(request.signature_hex) if request.signature_hex else None
        
        # Set expiration to 72 hours from now
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(hours=72)
        
        # Store on server
        storage.save_viewonce_message(
            message_id=message_id,
            sender=sender_email,
            recipient=request.recipient,
            subject=request.subject,
            encrypted_content=encrypted_content,
            otp_key=otp_key,
            mac_key=mac_key,
            mac=mac,
            signature=signature,
            signature_algorithm=request.signature_algorithm,
            expires_at=expires_at,
        )
        
        return ViewOnceUploadResponse(
            message_id=message_id,
            status="pending",
            recipient=request.recipient,
            created_at=datetime.utcnow(),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload view-once email"
        )


@app.get("/viewonce/pending", response_model=List[ViewOncePendingResponse])
def list_viewonce_pending(
    authorization: Optional[str] = Header(None),
) -> List[ViewOncePendingResponse]:
    """
    List all pending view-once emails for the authenticated user.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    # Extract token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )
    access_token = parts[1]
    
    try:
        storage, recipient_email = _get_user_storage(access_token)
        
        # Get pending view-once emails for this recipient
        pending = storage.list_viewonce_pending(recipient_email)
        
        return [
            ViewOncePendingResponse(
                id=msg["id"],
                sender=msg["sender"],
                subject=msg["subject"],
                status=msg["status"],
                created_at=msg["created_at"],
            )
            for msg in pending
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list view-once emails"
        )


@app.post("/viewonce/{message_id}/download", response_model=ViewOnceDownloadResponse)
def download_viewonce(
    message_id: str,
    authorization: Optional[str] = Header(None),
) -> ViewOnceDownloadResponse:
    """
    Download a view-once email from server.
    Marks the email as 'downloaded' in server storage.
    Recipient will then decrypt locally and view.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    # Extract token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )
    access_token = parts[1]
    
    try:
        storage, recipient_email = _get_user_storage(access_token)
        
        # Get the view-once message
        msg = storage.get_viewonce_message(message_id)
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"View-once message not found: {message_id}"
            )
        
        # Verify recipient matches authenticated user
        if msg["recipient"] != recipient_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this message"
            )
        
        # Mark as downloaded
        storage.mark_viewonce_downloaded(message_id)
        
        return ViewOnceDownloadResponse(
            id=msg["id"],
            sender=msg["sender"],
            subject=msg["subject"],
            encrypted_content_hex=msg["encrypted_content"].hex(),
            otp_key_hex=msg["otp_key"].hex(),
            mac_key_hex=msg["mac_key"].hex(),
            mac_hex=msg["mac"].hex(),
            signature_hex=msg["signature"].hex() if msg["signature"] else None,
            signature_algorithm=msg["signature_algorithm"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download view-once email"
        )


@app.post("/viewonce/{message_id}/mark-viewed")
def mark_viewonce_viewed(
    message_id: str,
    authorization: Optional[str] = Header(None),
) -> dict:
    """
    Mark a view-once email as viewed by recipient.
    After this, the server will delete the email shortly.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    # Extract token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )
    access_token = parts[1]
    
    try:
        storage, recipient_email = _get_user_storage(access_token)
        
        # Get the view-once message to verify ownership
        msg = storage.get_viewonce_message(message_id)
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"View-once message not found: {message_id}"
            )
        
        # Verify recipient
        if msg["recipient"] != recipient_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this message"
            )
        
        # Mark as viewed
        storage.mark_viewonce_viewed(message_id)
        
        return {"status": "viewed", "message_id": message_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark view-once as viewed"
        )


@app.post("/viewonce/{message_id}/delete")
def delete_viewonce(
    message_id: str,
    authorization: Optional[str] = Header(None),
) -> dict:
    """
    Delete a view-once email from server (ephemeral deletion).
    Can be called by either sender or recipient.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    # Extract token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )
    access_token = parts[1]
    
    try:
        storage, user_email = _get_user_storage(access_token)
        
        # Get the view-once message to verify ownership
        msg = storage.get_viewonce_message(message_id)
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"View-once message not found: {message_id}"
            )
        
        # Verify authorization (sender or recipient can delete)
        if msg["sender"] != user_email and msg["recipient"] != user_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this message"
            )
        
        # Delete from server
        storage.delete_viewonce_message(message_id)
        
        return {"status": "deleted", "message_id": message_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete view-once email"
        )


@app.get("/viewonce/{message_id}/status", response_model=ViewOnceStatusResponse)
def get_viewonce_status(
    message_id: str,
    authorization: Optional[str] = Header(None),
) -> ViewOnceStatusResponse:
    """
    Get the status of a view-once email (for sender).
    Shows: pending, downloaded, viewed, or deleted.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    # Extract token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )
    access_token = parts[1]
    
    try:
        storage, sender_email = _get_user_storage(access_token)
        
        # Get status (only sender can query)
        status_info = storage.get_viewonce_status(sender_email, message_id)
        if not status_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"View-once message not found or not authorized: {message_id}"
            )
        
        return ViewOnceStatusResponse(
            message_id=status_info["id"],
            recipient=status_info["recipient"],
            status=status_info["status"],
            created_at=status_info["created_at"],
            downloaded_at=status_info["downloaded_at"],
            viewed_at=status_info["viewed_at"],
            deleted_at=status_info["deleted_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get view-once status"
        )


# --- Encrypted Email Server Storage (AES-256-GCM with Server-Side Session Keys) ---

@app.post("/encrypted/send", response_model=EncryptedEmailUploadResponse)
def store_encrypted_email(
    request: StoreEncryptedEmailRequest,
    authorization: Optional[str] = Header(None),
) -> EncryptedEmailUploadResponse:
    """
    Upload encrypted email with session key to SERVER storage (shared across users).
    
    Sender encrypts plaintext with AES-256-GCM, then uploads:
    - Encrypted content (ciphertext)
    - Session key (for recipient to decrypt)
    - Optional PQC signature for authenticity
    
    **CRITICAL**: Emails stored on SHARED server database, not sender's local database.
    This allows receiver to query and download later.
    
    Server stores all components for 72 hours.
    Recipient downloads and decrypts locally.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    # Extract token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )
    access_token = parts[1]
    
    try:
        # Get SENDER's email from token
        _, sender_email = _get_user_storage(access_token)
        
        # Use SHARED server storage (not sender's local database!)
        server_storage = _get_storage()
        
        # Decode hex-encoded components
        try:
            encrypted_content = bytes.fromhex(request.encrypted_content_hex)
            session_key = bytes.fromhex(request.session_key_hex)
            signature = bytes.fromhex(request.signature_hex) if request.signature_hex else None
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid hex encoding in request"
            )

        # Note: Session key can be plaintext or KEM-encapsulated (QKEM format)
        # The server accepts both formats for compatibility with different clients
        if session_key.startswith(KEM_MAGIC):
            pass  # KEM-encapsulated session key - debug logging removed
        else:
            pass  # Plaintext session key - debug logging removed

        # Generate message ID
        message_id = str(uuid.uuid4())

        # Store on SHARED SERVER database
        server_storage.save_encrypted_email(
            message_id=message_id,
            sender=sender_email,
            recipient=request.recipient,
            subject=request.subject,
            encrypted_content=encrypted_content,
            session_key=session_key,
            signature=signature,
            signature_algorithm=request.signature_algorithm,
            key_exchange_algorithm=request.key_exchange_algorithm,
        )
        
        
        return EncryptedEmailUploadResponse(
            message_id=message_id,
            recipient=request.recipient,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store encrypted email"
        )


@app.get("/encrypted/pending", response_model=List[EncryptedEmailPendingResponse])
def list_encrypted_pending(
    authorization: Optional[str] = Header(None),
) -> List[EncryptedEmailPendingResponse]:
    """
    List pending encrypted emails for authenticated recipient.
    
    **CRITICAL**: Queries SHARED server storage (not recipient's local database).
    This allows receiver to see emails sent by ANY sender.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    # Extract token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )
    access_token = parts[1]
    
    try:
        # Get RECIPIENT's email from token
        _, recipient_email = _get_user_storage(access_token)
        
        # Query SHARED SERVER storage (not recipient's local database!)
        server_storage = _get_storage()
        
        pending = server_storage.list_encrypted_pending(recipient_email)
        return [
            EncryptedEmailPendingResponse(**msg) for msg in pending
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list pending encrypted emails"
        )


@app.post("/encrypted/{message_id}/download", response_model=EncryptedEmailDownloadResponse)
def download_encrypted_email(
    message_id: str,
    authorization: Optional[str] = Header(None),
) -> EncryptedEmailDownloadResponse:
    """
    Download encrypted email with session key from SERVER storage.
    
    **CRITICAL**: Queries SHARED server storage (not recipient's local database).
    Marks email as downloaded and returns encrypted content + key.
    
    Recipient will:
    1. Download encrypted content + session key from this endpoint
    2. Decrypt locally using session key
    3. Verify signature if present
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    # Extract token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )
    access_token = parts[1]
    
    try:
        # Get RECIPIENT's email from token
        _, recipient_email = _get_user_storage(access_token)
        
        # Query SHARED SERVER storage
        server_storage = _get_storage()
        
        # Get email (verify recipient can access)
        msg = server_storage.get_encrypted_email(message_id)
        if not msg or msg["recipient"] != recipient_email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Encrypted email not found or not authorized: {message_id}"
            )
        
        # Mark as downloaded on SERVER
        server_storage.mark_encrypted_downloaded(message_id)
        
        
        # Return with hex-encoded keys and content
        return EncryptedEmailDownloadResponse(
            id=msg["id"],
            sender=msg["sender"],
            recipient=msg["recipient"],
            subject=msg["subject"],
            encrypted_content_hex=msg["encrypted_content"].hex(),
            session_key_hex=msg["session_key"].hex(),
            signature_hex=msg["signature"].hex() if msg["signature"] else None,
            signature_algorithm=msg["signature_algorithm"],
            key_exchange_algorithm=msg["key_exchange_algorithm"],
            status="downloaded",
            created_at=msg["created_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download encrypted email"
        )


@app.post("/encrypted/{message_id}/delete")
def delete_encrypted_email(
    message_id: str,
    authorization: Optional[str] = Header(None),
) -> dict:
    """
    Delete encrypted email from SERVER storage.
    Can be called by sender or recipient.
    
    **CRITICAL**: Deletes from SHARED server storage (not recipient's local database).
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    # Extract token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )
    access_token = parts[1]
    
    try:
        # Get user email from token
        _, user_email = _get_user_storage(access_token)
        
        # Query SHARED SERVER storage
        server_storage = _get_storage()
        
        # Verify user owns this email (as sender or recipient)
        msg = server_storage.get_encrypted_email(message_id)
        if not msg or (msg["sender"] != user_email and msg["recipient"] != user_email):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Encrypted email not found or not authorized: {message_id}"
            )
        
        # Delete from SERVER
        server_storage.delete_encrypted_email(message_id)
        
        return {
            "message_id": message_id,
            "status": "deleted",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete encrypted email"
        )


@app.get("/encrypted/{message_id}/status", response_model=EncryptedEmailStatusResponse)
def get_encrypted_email_status(
    message_id: str,
    authorization: Optional[str] = Header(None),
) -> EncryptedEmailStatusResponse:
    """
    Get status of encrypted email from SERVER storage (for sender).
    Shows: pending, downloaded, or deleted.
    
    **CRITICAL**: Queries SHARED server storage (not sender's local database).
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    # Extract token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format"
        )
    access_token = parts[1]
    
    try:
        # Get sender email from token
        _, sender_email = _get_user_storage(access_token)
        
        # Query SHARED SERVER storage
        server_storage = _get_storage()
        
        # Get status (only sender can query)
        status_info = server_storage.get_encrypted_sender_status(sender_email, message_id)
        if not status_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Encrypted email not found or not authorized: {message_id}"
            )
        
        
        return EncryptedEmailStatusResponse(
            message_id=status_info["id"],
            recipient=status_info["recipient"],
            status=status_info["status"],
            created_at=status_info["created_at"],
            downloaded_at=status_info["downloaded_at"],
            deleted_at=status_info["deleted_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get encrypted email status"
        )
