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
        # Create a Storage instance - this will auto-create all tables
        storage = Storage(database_url=database_url)
        print("✓ Database schema initialized successfully")
        print("  Tables created:")
        print("  - emails")
        print("  - pending_messages")
        print("  - attachments")
        print("  - signing_keys")
        print("  - kem_keys")
        print("  - users")
        print("  - otp_sessions")
        print("  - password_reset_tokens")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to initialize database: {e}")
        # Print full traceback for debugging
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(init_database())
