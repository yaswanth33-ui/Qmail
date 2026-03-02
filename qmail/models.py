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


@dataclass
class Contact:
    id: Optional[int]
    email: str
    display_name: Optional[str]
    quantum_capable: bool
    sig_public_key: Optional[bytes]
    sig_algorithm: Optional[str]

