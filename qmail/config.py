"""
=============================================================================
CONFIGURATION - Application Settings
=============================================================================

This module contains all configuration data classes for Qmail.

CONFIGURATION HIERARCHY:
------------------------
    AppConfig (top-level)
    ├── key_exchange_mode: BB84 or PQC
    ├── interop_mode: QUANTUM_ONLY or HYBRID_FALLBACK
    ├── qrng: QrngConfig
    │   └── base_url: ANU QRNG API URL
    └── server_broker: ServerBrokerConfig (optional)
        ├── base_url: Broker server URL
        └── auth_type: bearer, mtls, api_key

KEY EXCHANGE MODES:
-------------------
- BB84: Simulated quantum key distribution (for development/future QKD hardware)
- PQC: Post-quantum cryptography (ML-KEM-1024) - recommended for production

INTEROP MODES:
--------------
- QUANTUM_ONLY: Only communicate with quantum-capable users
- HYBRID_FALLBACK: Fall back to PQC for non-quantum users

USAGE:
------
    from qmail.config import AppConfig, KeyExchangeMode

    config = AppConfig(
        key_exchange_mode=KeyExchangeMode.PQC,
        interop_mode=InteropMode.QUANTUM_ONLY,
    )
"""

from dataclasses import dataclass, field

from enum import Enum
from typing import Optional
import os


class KeyExchangeMode(str, Enum):
    BB84 = "bb84"
    PQC = "pqc"


class InteropMode(str, Enum):
    QUANTUM_ONLY = "quantum_only"
    HYBRID_FALLBACK = "hybrid_fallback"


@dataclass
class QrngConfig:
    base_url: str = os.environ.get("QRNG_BASE_URL", "https://qrng.anu.edu.au/API/jsonI.php")
    api_key: Optional[str] = os.environ.get("QRNG_API_KEY")  # for future quantumnumbers.anu.edu.au usage


@dataclass
class ServerBrokerConfig:
    """
    Configuration for WhatsApp-style server message broker.
    Handles unified transmission for AES and OTP emails.
    """
    base_url: str  # e.g., "https://broker.qmail.com"
    auth_type: str = "bearer"  # "bearer", "mtls", "api_key"
    auth_token_id: Optional[str] = None  # Keyring entry for bearer token
    client_cert_path: Optional[str] = None  # For mTLS
    client_key_path: Optional[str] = None  # For mTLS
    verify_tls: bool = True


@dataclass
class AppConfig:
    key_exchange_mode: KeyExchangeMode = KeyExchangeMode.PQC
    interop_mode: InteropMode = InteropMode.QUANTUM_ONLY
    qrng: QrngConfig = field(default_factory=QrngConfig)
    server_broker: Optional[ServerBrokerConfig] = None  # WhatsApp-style broker


@dataclass
class QkdConfig:
    """
    Configuration for using an external ETSI GS QKD 014 key manager.
    """

    base_url: Optional[str] = None
    api_key_id: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None
    verify_tls: bool = True


