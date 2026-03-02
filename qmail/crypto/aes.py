from __future__ import annotations

import os
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from qmail.crypto.qrng import QrngClient


AES_KEY_SIZE_BYTES = 32  # 256-bit
AES_NONCE_SIZE_BYTES = 12  # recommended for AES-GCM


def generate_aes_key(use_qrng: bool = True, qrng_client: QrngClient | None = None) -> bytes:
    """
    Generate a fresh 256-bit AES key using QRNG by default.

    Args:
        use_qrng: If True, use quantum random number generator (ANU QRNG API).
                 If False, fall back to OS CSPRNG.
        qrng_client: Optional QrngClient instance (created if not provided).

    Returns:
        256-bit random key for AES-GCM encryption.
    """
    if use_qrng:
        qrng = qrng_client or QrngClient()
        return qrng.get_bytes(AES_KEY_SIZE_BYTES)
    else:
        return os.urandom(AES_KEY_SIZE_BYTES)


def encrypt_aes_gcm(
    key: bytes,
    plaintext: bytes,
    associated_data: bytes | None = None,
    use_qrng: bool = True,
    qrng_client: QrngClient | None = None,
) -> Tuple[bytes, bytes]:
    """
    Encrypt plaintext using AES-GCM with QRNG-seeded nonce.

    Args:
        key: AES key (16, 24, or 32 bytes).
        plaintext: Data to encrypt.
        associated_data: Optional authenticated data.
        use_qrng: If True, use QRNG for nonce generation (default: True).
        qrng_client: Optional QrngClient instance.

    Returns:
        (nonce, ciphertext_with_tag) tuple.
    """
    if len(key) not in (16, 24, 32):
        raise ValueError("AES key must be 128, 192, or 256 bits")
    
    # Generate nonce with quantum randomness
    if use_qrng:
        qrng = qrng_client or QrngClient()
        nonce = qrng.get_bytes(AES_NONCE_SIZE_BYTES)
    else:
        nonce = os.urandom(AES_NONCE_SIZE_BYTES)
    
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
    return nonce, ciphertext


def decrypt_aes_gcm(key: bytes, nonce: bytes, ciphertext: bytes, associated_data: bytes | None = None) -> bytes:
    """
    Decrypt AES-GCM ciphertext.
    """
    if len(key) not in (16, 24, 32):
        raise ValueError("AES key must be 128, 192, or 256 bits")
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, associated_data)

