"""
=============================================================================
LAYER 5: AUTHENTICATION
=============================================================================

This layer handles authentication for:
1. QKD key managers via ETSI GS QKD 014 REST APIs  
2. WhatsApp-style server broker authentication

AUTHENTICATION TYPES:
---------------------

┌─────────────────────────────────────────────────────────────────────────┐
│  QKD Key Manager (ETSI GS QKD 014)                                      │
│  ─────────────────────────────────                                       │
│                                                                          │
│  For production quantum key distribution, we need to authenticate      │
│  with external QKD key managers (KMEs) that control QKD hardware.      │
│                                                                          │
│  Supported auth methods:                                                │
│  - Bearer token / API key                                               │
│  - Client certificate (mTLS)                                            │
│                                                                          │
│  API secrets stored in OS keychain, not on disk.                        │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  Server Broker Auth (WhatsApp-style)                                    │
│  ────────────────────────────────────                                    │
│                                                                          │
│  The message broker server requires authentication for:                 │
│  - Uploading encrypted messages                                         │
│  - Downloading pending messages                                         │
│  - Acknowledging message receipt                                        │
│                                                                          │
│  Supported methods: Bearer token, mTLS, API key                         │
│  Tokens stored securely in OS keychain.                                 │
└─────────────────────────────────────────────────────────────────────────┘

SECURITY PROPERTIES:
--------------------
- SECURE TOKEN STORAGE: All tokens stored in OS keychain (encrypted by OS)
- TOKEN REFRESH: Automatic refresh before expiration

WHY OS KEYCHAIN:
----------------
The OS keychain (Windows Credential Manager, macOS Keychain, Linux Secret
Service) provides:
- Encryption at rest (protected by user login)
- Access control (only your app can read)
- Hardware protection on some systems (TPM, Secure Enclave)

This is much more secure than storing tokens in a config file or database.
"""

from qmail.auth.qkd import (
    QkdClient,
    QkdAuthConfig,
    QkdKeychainStore,
)
from qmail.auth.server_broker import (
    BrokerAuthClient,
    BrokerToken,
    BrokerKeychainStore,
)

__all__ = [
    # QKD
    "QkdClient",
    "QkdAuthConfig",
    "QkdKeychainStore",
    # Broker
    "BrokerAuthClient",
    "BrokerToken",
    "BrokerKeychainStore",
]
