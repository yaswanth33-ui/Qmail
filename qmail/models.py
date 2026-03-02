"""
=============================================================================
DATA MODELS - Core Data Structures
=============================================================================

This module defines the core data structures used throughout Qmail.

EMAIL ENVELOPE:
---------------
The EmailEnvelope is the primary data structure for encrypted messages.
It contains all the information needed to:
- Identify sender and recipient
- Store encrypted content (ciphertext, MAC, signature)
- Track encryption method used (AES or OTP)
- Implement view-once messages
- Track delivery status (WhatsApp-style)

    EmailEnvelope
    ├── id: Database primary key
    ├── sender, recipient, subject
    ├── ciphertext: Encrypted message body
    ├── mac: Optional MAC tag (for OTP messages)
    ├── signature: PQC digital signature
    ├── signature_algorithm: "Dilithium2" or "Falcon-512"
    ├── sent_at: Timestamp
    ├── view_once: Is this a self-destructing message?
    ├── viewed: Has it been viewed? (for view-once)
    ├── otp_key, mac_key: Keys for OTP decryption
    ├── key_exchange_mode: "pqc" or "bb84"
    ├── encryption_mode: "aes" or "view_once_otp"
    ├── folder: "Inbox", "Sent", "Drafts", "Trash"
    └── delivery_status: "sent", "delivered", "read"

ENCRYPTION MODES:
-----------------
- AES: Standard AES-256-GCM encryption
  - Keys seeded with QRNG
  - Good for normal messages

- VIEW_ONCE_OTP: One-Time Pad encryption
  - Perfect secrecy (information-theoretically secure)
  - Message can only be viewed once
  - Key destroyed after viewing
"""

from __future__ import annotations


from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class EncryptionMode(str, Enum):
    AES = "aes"
    VIEW_ONCE_OTP = "view_once_otp"


@dataclass
class EmailEnvelope:
    id: Optional[int]
    sender: str
    recipient: str
    subject: str
    ciphertext: bytes
    mac: Optional[bytes]
    signature: Optional[bytes]
    signature_algorithm: Optional[str]
    sent_at: datetime
    view_once: bool
    key_exchange_mode: str
    encryption_mode: EncryptionMode
    folder: str = "Drafts"  # "Inbox", "Sent", "Drafts", "Trash"
    viewed: bool = False  # For view-once emails: True after first view
    otp_key: Optional[bytes] = None  # For view-once OTP decryption (receiver side)
    mac_key: Optional[bytes] = None  # For view-once MAC verification (receiver side)
    # WhatsApp-style delivery tracking
    delivery_status: str = "sent"  # sent, delivered, read
    delivered_at: Optional[datetime] = None  # When recipient downloaded
    read_at: Optional[datetime] = None  # When recipient read
    server_message_id: Optional[str] = None  # UUID for server-side temporary storage
    in_reply_to: Optional[str] = None  # ID of the email being replied to (for threading)
