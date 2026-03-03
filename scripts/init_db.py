#!/usr/bin/env python3
"""
Database initialization script - ensures all tables exist on first deploy.
Run this before the API starts to guarantee schema is ready.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from qmail.storage.db import Storage

def init_database():
    """Initialize the database schema."""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("ERROR: DATABASE_URL env var not set")
        sys.exit(1)
    
    print(f"Initializing database from: {database_url[:50]}...")
    
    try:
        # IMPORTANT: Initialize the broker schema (NOT public!).
        # Previously this created tables in the 'public' schema, which caused
        # user-specific schemas to fall through to public.emails via
        # search_path, breaking per-user data isolation.
        storage = Storage(database_url=database_url, schema="broker")
        print("✓ Broker schema initialized successfully")
        print("  Tables created in 'broker' schema:")
        print("  - pending_messages")
        print("  - users")
        print("  - otp_sessions")
        print("  - password_reset_tokens")
        print("  - signing_keys")
        print("  - kem_keys")
        
        # Drop any tables that were incorrectly created in the public schema
        # (from previous deployments) to prevent search_path leakage
        _cleanup_public_schema(database_url)
        
        return 0
    except Exception as e:
        print(f"ERROR: Failed to initialize database: {e}")
        # Print full traceback for debugging
        import traceback
        traceback.print_exc()
        return 1


def _cleanup_public_schema(database_url: str):
    """
    Drop tables from the 'public' schema that should only exist in
    user-specific or broker schemas. This fixes data leakage caused by
    the old init_db.py which created tables in 'public'.
    """
    from sqlalchemy import create_engine, text
    
    engine = create_engine(database_url)
    tables_to_drop = [
        "emails", "attachments", "signing_keys", "kem_keys",
        "pending_messages", "users", "otp_sessions", "password_reset_tokens",
    ]
    
    with engine.begin() as conn:
        for table in tables_to_drop:
            try:
                # Check if the table exists in 'public' schema specifically
                result = conn.execute(text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :tbl"
                ), {"tbl": table}).first()
                if result:
                    conn.execute(text(f'DROP TABLE IF EXISTS public."{table}" CASCADE'))
                    print(f"  ⚠ Dropped leaked table public.{table}")
            except Exception as e:
                print(f"  Warning: Could not drop public.{table}: {e}")
    
    engine.dispose()

if __name__ == "__main__":
    sys.exit(init_database())
