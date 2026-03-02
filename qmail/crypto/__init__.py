"""
=============================================================================
LAYER 1: CRYPTO PRIMITIVES
=============================================================================

This layer provides the foundational cryptographic operations for Qmail.
All higher layers depend on these primitives for security.

COMPONENTS:
-----------
1. QRNG (qrng.py)
   - Quantum Random Number Generator client (ANU QRNG API)
   - Provides true quantum randomness for key generation
   - Falls back to OS CSPRNG when QRNG unavailable

2. AES-GCM (aes.py)
   - AES-256-GCM authenticated encryption
   - Keys seeded with quantum randomness (QRNG)
   - Used for standard email encryption

3. OTP (otp.py)
   - One-Time Pad encryption for "view-once" messages
   - Keys are QRNG-backed, same length as message
   - Information-theoretically secure (perfect secrecy)
   - HMAC-SHA256 for integrity verification

4. PQC Signatures (signatures.py)
   - Post-Quantum Cryptographic signatures
   - Dilithium2 (ML-DSA-44) - NIST standard
   - Falcon-512 - Alternative lattice-based scheme
   - Provides non-repudiation and authenticity

SECURITY GUARANTEES:
--------------------
- Quantum-resistant: All algorithms are post-quantum safe
- Forward secrecy: Keys are ephemeral and destroyed after use
- Authenticity: PQC signatures verify sender identity
- Integrity: AES-GCM and HMAC protect against tampering

USAGE EXAMPLE:
--------------
    from qmail.crypto.aes import encrypt_aes_gcm, generate_aes_key
    from qmail.crypto.otp import encrypt_view_once
    from qmail.crypto.signatures import sign_message, generate_keypair

    # Standard encryption
    key = generate_aes_key(use_qrng=True)
    nonce, ciphertext = encrypt_aes_gcm(key, b"Hello, World!")

    # View-once encryption
    ciphertext, mac, otp_key, mac_key = encrypt_view_once(b"Secret message")

    # Sign message
    keypair = generate_keypair("Dilithium2")
    signature = sign_message(ciphertext, keypair.private_key, "Dilithium2")
"""

# Re-export main components for convenient access
from qmail.crypto.qrng import QrngClient
from qmail.crypto.aes import (
    generate_aes_key,
    encrypt_aes_gcm,
    decrypt_aes_gcm,
    AES_KEY_SIZE_BYTES,
    AES_NONCE_SIZE_BYTES,
)
from qmail.crypto.otp import (
    encrypt_view_once,
    decrypt_view_once,
)
from qmail.crypto.signatures import (
    generate_keypair,
    sign_message,
    verify_signature,
    SignatureKeypair,
)

__all__ = [
    # QRNG
    "QrngClient",
    # AES
    "generate_aes_key",
    "encrypt_aes_gcm",
    "decrypt_aes_gcm",
    "AES_KEY_SIZE_BYTES",
    "AES_NONCE_SIZE_BYTES",
    # OTP
    "encrypt_view_once",
    "decrypt_view_once",
    # Signatures
    "generate_keypair",
    "sign_message",
    "verify_signature",
    "SignatureKeypair",
]
