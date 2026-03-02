"""
=============================================================================
AES-GCM - Authenticated Encryption with Quantum-Seeded Keys
=============================================================================

PURPOSE:
--------
Provides AES-256-GCM authenticated encryption for standard email messages.
Keys are seeded with quantum randomness (QRNG) for maximum security.

WHY AES-GCM:
------------
- AES-256: 256-bit key provides 128-bit post-quantum security
- GCM mode: Provides both confidentiality AND integrity (AEAD)
- NIST approved: Widely audited and trusted standard
- Fast: Hardware acceleration (AES-NI) on modern CPUs

QUANTUM-SEEDED KEYS:
--------------------
Unlike classical key generation that relies on pseudo-random number
generators, our keys are seeded with TRUE quantum randomness from the
ANU Quantum Random Number Generator. This means:
- Keys are fundamentally unpredictable (not just computationally hard)
- Even a quantum computer cannot predict the key from observations
- Maximum entropy guaranteed by quantum mechanics

MESSAGE FLOW:
-------------
    Sender                                  Recipient
    ------                                  ---------
    1. Generate quantum-random key (QRNG)
    2. Generate quantum-random nonce (QRNG)
    3. Encrypt plaintext with AES-GCM
    4. Send (nonce, ciphertext) + key via secure key exchange
                                            5. Receive key via PQC/BB84
                                            6. Decrypt with AES-GCM

SECURITY PROPERTIES:
--------------------
- Confidentiality: Only key holder can decrypt
- Integrity: Any tampering is detected (GCM auth tag)
- Authenticity: Combined with PQC signatures in higher layers

USAGE:
------
    from qmail.crypto.aes import generate_aes_key, encrypt_aes_gcm, decrypt_aes_gcm

    # Generate key with quantum randomness
    key = generate_aes_key(use_qrng=True)

    # Encrypt
    nonce, ciphertext = encrypt_aes_gcm(key, b"Secret message")

    # Decrypt
    plaintext = decrypt_aes_gcm(key, nonce, ciphertext)
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from qmail.crypto.qrng import QrngClient


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

AES_KEY_SIZE_BYTES = 32   # 256 bits - provides 128-bit post-quantum security
AES_NONCE_SIZE_BYTES = 12  # 96 bits - recommended for AES-GCM (NIST SP 800-38D)


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------

class AesError(Exception):
    """Base exception for AES operations."""
    pass


class AesKeyError(AesError):
    """Invalid AES key (wrong size, corrupted)."""
    pass


class AesDecryptionError(AesError):
    """Decryption failed (wrong key, tampered ciphertext, or corrupted data)."""
    pass


# -----------------------------------------------------------------------------
# Key Generation
# -----------------------------------------------------------------------------

def generate_aes_key(
    use_qrng: bool = True,
    qrng_client: Optional[QrngClient] = None,
) -> bytes:
    """
    Generate a 256-bit AES key with quantum randomness.

    By default, uses the ANU Quantum Random Number Generator for true
    quantum randomness. Falls back to OS CSPRNG if QRNG is unavailable.

    Args:
        use_qrng: If True (default), use quantum random number generator.
                 If False, use OS CSPRNG directly.
        qrng_client: Optional pre-initialized QrngClient instance.
                    Created automatically if not provided.

    Returns:
        32 bytes (256 bits) of random key material.

    Security Note:
        These keys should be ephemeral - used for a single message and
        then securely destroyed. The higher-level key lifecycle manager
        handles key zeroization.

    Example:
        >>> key = generate_aes_key()
        >>> len(key)
        32
    """
    if use_qrng:
        client = qrng_client or QrngClient()
        return client.get_bytes(AES_KEY_SIZE_BYTES)
    else:
        return os.urandom(AES_KEY_SIZE_BYTES)


# -----------------------------------------------------------------------------
# Encryption
# -----------------------------------------------------------------------------

def encrypt_aes_gcm(
    key: bytes,
    plaintext: bytes,
    associated_data: Optional[bytes] = None,
    use_qrng: bool = True,
    qrng_client: Optional[QrngClient] = None,
) -> Tuple[bytes, bytes]:
    """
    Encrypt plaintext using AES-256-GCM with a quantum-random nonce.

    AES-GCM provides authenticated encryption: the ciphertext includes
    a 16-byte authentication tag that detects any tampering.

    Args:
        key: AES key (must be 16, 24, or 32 bytes for AES-128/192/256).
        plaintext: Data to encrypt (can be any length).
        associated_data: Optional additional authenticated data (AAD).
                        This data is authenticated but NOT encrypted.
                        Useful for headers, metadata, etc.
        use_qrng: If True, use quantum randomness for nonce generation.
        qrng_client: Optional pre-initialized QrngClient.

    Returns:
        Tuple of (nonce, ciphertext_with_tag):
        - nonce: 12 bytes, must be sent with ciphertext for decryption
        - ciphertext_with_tag: encrypted data + 16-byte GCM auth tag

    Raises:
        AesKeyError: If key has invalid length.

    Security Notes:
        - NEVER reuse a (key, nonce) pair - this completely breaks security
        - Quantum-random nonces ensure uniqueness without coordination
        - The GCM tag provides integrity - any tampering is detected

    Example:
        >>> key = generate_aes_key()
        >>> nonce, ciphertext = encrypt_aes_gcm(key, b"Hello, World!")
        >>> len(nonce)
        12
    """
    _validate_key(key)

    # Generate nonce with quantum randomness for maximum entropy
    if use_qrng:
        client = qrng_client or QrngClient()
        nonce = client.get_bytes(AES_NONCE_SIZE_BYTES)
    else:
        nonce = os.urandom(AES_NONCE_SIZE_BYTES)

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)

    return nonce, ciphertext


# -----------------------------------------------------------------------------
# Decryption
# -----------------------------------------------------------------------------

def decrypt_aes_gcm(
    key: bytes,
    nonce: bytes,
    ciphertext: bytes,
    associated_data: Optional[bytes] = None,
) -> bytes:
    """
    Decrypt AES-GCM ciphertext and verify integrity.

    This function verifies the GCM authentication tag before returning
    the plaintext. If the ciphertext has been tampered with, or if the
    wrong key/nonce is used, decryption will fail.

    Args:
        key: AES key (must match the key used for encryption).
        nonce: 12-byte nonce from encryption.
        ciphertext: Encrypted data with GCM auth tag.
        associated_data: Optional AAD (must match what was used in encryption).

    Returns:
        Decrypted plaintext bytes.

    Raises:
        AesKeyError: If key has invalid length.
        AesDecryptionError: If decryption fails (wrong key, tampered data, etc.)

    Security Note:
        Decryption failure could mean:
        - Wrong key provided
        - Ciphertext was tampered with
        - Wrong associated_data provided
        - Wrong nonce provided
        All of these are treated the same way for security (no oracle attacks).

    Example:
        >>> key = generate_aes_key()
        >>> nonce, ct = encrypt_aes_gcm(key, b"Secret")
        >>> decrypt_aes_gcm(key, nonce, ct)
        b'Secret'
    """
    _validate_key(key)

    try:
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, associated_data)
    except InvalidTag as e:
        raise AesDecryptionError(
            "Decryption failed: authentication tag invalid. "
            "Possible causes: wrong key, tampered ciphertext, or wrong AAD."
        ) from e
    except Exception as e:
        raise AesDecryptionError(f"Decryption failed: {e}") from e


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _validate_key(key: bytes) -> None:
    """Validate AES key length."""
    valid_lengths = (16, 24, 32)  # AES-128, AES-192, AES-256
    if len(key) not in valid_lengths:
        raise AesKeyError(
            f"Invalid AES key length: {len(key)} bytes. "
            f"Expected one of {valid_lengths} bytes (128/192/256 bits)."
        )

