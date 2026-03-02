"""
=============================================================================
LAYER 4: STORAGE
=============================================================================

This layer provides persistent storage for encrypted messages.
Messages are stored as CIPHERTEXT ONLY - plaintext never touches disk.

PURPOSE:
--------
Store and retrieve:
1. Encrypted email messages (local mailbox)
2. Pending messages for the WhatsApp-style broker queue

WHATSAPP-STYLE ARCHITECTURE:
----------------------------
    ┌─────────────────────────────────────────────────────────────────────┐
    │                MESSAGE FLOW (WhatsApp-style)                        │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   SENDER                    SERVER BROKER              RECIPIENT    │
    │   ──────                    ─────────────              ─────────    │
    │                                                                      │
    │   1. Encrypt message                                                │
    │   2. Upload to broker      ──→ Queue message                       │
    │                                (pending_messages)                   │
    │                                                                      │
    │                                              3. Poll for messages  │
    │                            ←──               4. Download message   │
    │                                                                      │
    │                            5. Delete message                        │
    │                               on acknowledgment                     │
    │                                                                      │
    │                                              6. Store in local     │
    │                                                 inbox (emails)     │
    └─────────────────────────────────────────────────────────────────────┘

DATABASE TABLES:
----------------
1. emails
   - Local mailbox (Inbox, Sent, Drafts, Trash)
   - Stores ciphertext, signatures, delivery status
   - Supports view-once (OTP) and standard (AES) messages

2. pending_messages
   - Server-side message broker queue
   - Transient storage (deleted after delivery)
   - WhatsApp-style: sender uploads → recipient downloads → delete

SECURITY PROPERTIES:
--------------------
- Ciphertext-only storage: Plaintext never written to disk
- OTP key storage: For view-once messages, OTP keys are temporarily stored
  until first viewing, then destroyed
- Signature storage: PQC signatures preserved for non-repudiation

USAGE:
------
    from qmail.storage import Storage

    # Production: PostgreSQL with schema-based user isolation
    storage = Storage(database_url="postgresql://user:pass@host/qmail", schema="broker")

    # Development: SQLite fallback
    storage = Storage(db_path=Path("user_mailbox.db"))

    # Save an encrypted email
    email_id = storage.save_email(encrypted_envelope)

    # List emails
    for email in storage.list_emails():

    # Server broker operations
    storage.save_pending_message(...)
    pending = storage.list_pending_messages(recipient_email)
    storage.delete_pending_message(message_id)
"""

from qmail.storage.db import Storage

__all__ = ["Storage"]
