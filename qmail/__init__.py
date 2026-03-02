"""
╔═════════════════════════════════════════════════════════════════════════════╗
║                                                                             ║
║   ██████╗ ███╗   ███╗ █████╗ ██╗██╗                                        ║
║  ██╔═══██╗████╗ ████║██╔══██╗██║██║                                        ║
║  ██║   ██║██╔████╔██║███████║██║██║                                        ║
║  ██║▄▄ ██║██║╚██╔╝██║██╔══██║██║██║                                        ║
║  ╚██████╔╝██║ ╚═╝ ██║██║  ██║██║███████╗                                   ║
║   ╚══▀▀═╝ ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝╚══════╝                                   ║
║                                                                             ║
║  Quantum-Secure Email with WhatsApp-Style Architecture                     ║
║                                                                             ║
╚═════════════════════════════════════════════════════════════════════════════╝

OVERVIEW:
---------
Qmail is a quantum-secure email client that combines:
- Post-Quantum Cryptography (PQC) for key exchange and signatures
- Quantum Random Number Generation (QRNG) for key seeding
- WhatsApp-style end-to-end encryption architecture
- One-Time Pad (OTP) encryption for view-once messages

ARCHITECTURE:
-------------
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FLUTTER FRONTEND                                    │
│                    (lib/screens, lib/services)                              │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ REST API
┌────────────────────────────────▼────────────────────────────────────────────┐
│  LAYER 7: API (api.py)                                                      │
│  FastAPI backend for Flutter - handles OAuth and messaging                 │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│  LAYER 6: TRANSPORT (transport/)                                            │
│  WhatsApp-style broker messaging (SMTP/IMAP removed)                        │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│  LAYER 5: AUTH (auth/)                                                      │
│  OAuth2 (Gmail/Outlook), QKD authentication, broker auth                    │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│  LAYER 4: STORAGE (storage/)                                                │
│  SQLite database for encrypted emails and pending messages                 │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│  LAYER 3: KEY MANAGEMENT (keys/)                                            │
│  Key lifecycle: usage limits, expiration, secure zeroization               │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│  LAYER 2: KEY EXCHANGE (key_exchange/)                                      │
│  BB84 (simulated QKD) and PQC KEM (ML-KEM-1024/Kyber)                       │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│  LAYER 1: CRYPTO PRIMITIVES (crypto/)                                       │
│  QRNG, AES-256-GCM, OTP, PQC Signatures (Dilithium, Falcon)                │
└─────────────────────────────────────────────────────────────────────────────┘

SECURITY MODEL:
---------------
┌────────────────────┬────────────────────────────────────────────────────────┐
│ Feature            │ Implementation                                         │
├────────────────────┼────────────────────────────────────────────────────────┤
│ Key Exchange       │ PQC (ML-KEM-1024) or BB84 simulation                   │
│ Message Encryption │ AES-256-GCM with quantum-seeded keys                   │
│ View-Once Messages │ OTP (One-Time Pad) with QRNG keys                      │
│ Digital Signatures │ PQC signatures (Dilithium2, Falcon-512)                │
│ Random Generation  │ ANU QRNG API with OS CSPRNG fallback                   │
│ Key Lifecycle      │ Usage limits, expiry, secure zeroization               │
│ Token Storage      │ OS keychain (Windows Credential Manager, etc.)         │
│ Message Storage    │ Ciphertext-only (plaintext NEVER stored)               │
└────────────────────┴────────────────────────────────────────────────────────┘

WHATSAPP-STYLE FLOW:
--------------------
    SENDER                    SERVER BROKER              RECIPIENT
    ──────                    ─────────────              ─────────
    1. Compose message
    2. Encrypt with AES/OTP
    3. Sign with PQC
    4. Upload to broker      ──→ Queue in pending_messages
                                                         5. Poll for messages
                             ←──                         6. Download message
                             7. Delete after ACK
                                                         8. Verify signature
                                                         9. Decrypt message
                                                        10. Store locally

QUICK START:
------------
    # Start the API server
    uvicorn qmail.api:app --reload --port 8000

    # Run Flutter app
    flutter run

MODULES:
--------
- qmail.crypto      : QRNG, AES, OTP, PQC signatures
- qmail.key_exchange: BB84, PQC KEM
- qmail.keys        : Key lifecycle management
- qmail.storage     : SQLite database
- qmail.auth        : OAuth, QKD, broker authentication
- qmail.transport   : Broker-based messaging (deprecated)
- qmail.api         : FastAPI REST backend
- qmail.client      : High-level orchestration
- qmail.config      : Configuration classes
- qmail.models      : Data models
"""

