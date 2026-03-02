"""
=============================================================================
OTP - One-Time Pad Encryption for View-Once Messages
=============================================================================

PURPOSE:
--------
Provides PERFECT SECRECY encryption for "view-once" messages (WhatsApp-style
disappearing messages). Uses the One-Time Pad (OTP) cipher with quantum-random
keys from the ANU QRNG.

WHAT IS A ONE-TIME PAD:
-----------------------
The OTP is the ONLY cipher mathematically proven to be unbreakable:
- The key must be truly random (we use QRNG)
- The key must be at least as long as the message
- The key must NEVER be reused

When these conditions are met, the ciphertext reveals NOTHING about the
plaintext, even to an attacker with infinite computing power.

WHY OTP FOR VIEW-ONCE:
----------------------
View-once messages are sensitive - they should leave no trace. OTP provides:
1. Perfect secrecy: Cannot be decrypted without the exact key
2. Forward secrecy: Key is destroyed after single use
3. No key derivation: No patterns to exploit across messages

The tradeoff is key size (key = message length), which is acceptable for
short, sensitive messages.

SECURITY MODEL:
---------------
    ┌─────────────────────────────────────────────────────────────┐
    │  SENDER                                                      │
    │  1. Generate QRNG key (same length as message)              │
    │  2. Generate QRNG MAC key (32 bytes for HMAC-SHA256)        │
    │  3. XOR message with OTP key → ciphertext                   │
    │  4. HMAC(mac_key, ciphertext) → authentication tag          │
    │  5. Send: {ciphertext, mac_tag} via server                  │
    │  6. Send: {otp_key, mac_key} via secure key exchange        │
    │  7. DESTROY keys immediately after transmission             │
    └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  RECIPIENT                                                   │
    │  1. Receive {otp_key, mac_key} via PQC/BB84 key exchange   │
    │  2. Receive {ciphertext, mac_tag} from server              │
    │  3. Verify HMAC(mac_key, ciphertext) == mac_tag            │
    │  4. XOR ciphertext with OTP key → plaintext                │
    │  5. DESTROY keys immediately after decryption              │
    │  6. Message shown ONCE, then deleted                       │
    └─────────────────────────────────────────────────────────────┘

INTEGRITY PROTECTION:
---------------------
OTP only provides confidentiality, not integrity. An attacker could flip
bits in the ciphertext to flip corresponding bits in the plaintext.

We add HMAC-SHA256 authentication:
- mac_key: 32 bytes of QRNG randomness (separate from OTP key)
- mac_tag = HMAC-SHA256(mac_key, ciphertext)
- Recipient verifies MAC before decryption

USAGE:
------
    from qmail.crypto.otp import encrypt_view_once, decrypt_view_once

    # Encrypt (sender)
    ciphertext, mac_tag, otp_key, mac_key = encrypt_view_once(b"Secret!")
    # Send ciphertext + mac_tag via regular channel
    # Send otp_key + mac_key via secure key exchange

    # Decrypt (recipient)
    plaintext = decrypt_view_once(ciphertext, mac_tag, otp_key, mac_key)
    # Destroy keys immediately after!
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional, Tuple

from qmail.crypto.qrng import QrngClient


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

MAC_KEY_SIZE_BYTES = 32  # HMAC-SHA256 key (256 bits)


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------

class OtpError(Exception):
    """Base exception for OTP operations."""
    pass


class OtpKeyLengthError(OtpError):
    """OTP key length doesn't match ciphertext/plaintext length."""
    pass


class OtpMacVerificationError(OtpError):
    """MAC verification failed - ciphertext may have been tampered with."""
    pass


# -----------------------------------------------------------------------------
# Core XOR Operation
# -----------------------------------------------------------------------------

def _xor_bytes(a: bytes, b: bytes) -> bytes:
    """
    XOR two byte sequences of equal length.

    This is the core OTP operation: ciphertext = plaintext XOR key

    Args:
        a: First byte sequence.
        b: Second byte sequence (must be same length as a).

    Returns:
        XOR of a and b.

    Raises:
        OtpKeyLengthError: If lengths don't match.
    """
    if len(a) != len(b):
        raise OtpKeyLengthError(
            f"OTP requires key and message to be the same length. "
            f"Got {len(a)} and {len(b)} bytes."
        )
    return bytes(x ^ y for x, y in zip(a, b))


# -----------------------------------------------------------------------------
# HMAC for Integrity
# -----------------------------------------------------------------------------

def _compute_mac(key: bytes, data: bytes) -> bytes:
    """
    Compute HMAC-SHA256 authentication tag.

    Args:
        key: 32-byte MAC key.
        data: Data to authenticate.

    Returns:
        32-byte HMAC-SHA256 tag.
    """
    return hmac.new(key, data, hashlib.sha256).digest()


def _verify_mac(key: bytes, data: bytes, expected_tag: bytes) -> bool:
    """
    Verify HMAC-SHA256 tag using constant-time comparison.

    Args:
        key: 32-byte MAC key.
        data: Data that was authenticated.
        expected_tag: Tag to verify against.

    Returns:
        True if tag is valid, False otherwise.
    """
    computed_tag = _compute_mac(key, data)
    return hmac.compare_digest(computed_tag, expected_tag)


# -----------------------------------------------------------------------------
# Encryption
# -----------------------------------------------------------------------------

def encrypt_view_once(
    plaintext: bytes,
    qrng_client: Optional[QrngClient] = None,
) -> Tuple[bytes, bytes, bytes, bytes]:
    """
    Encrypt plaintext using a QRNG-backed One-Time Pad with MAC.

    This provides PERFECT SECRECY for view-once messages. The key material
    is generated using quantum randomness and must be transmitted via a
    separate secure channel (PQC or BB84 key exchange).

    Args:
        plaintext: Message to encrypt (any length).
        qrng_client: Optional pre-initialized QrngClient.

    Returns:
        Tuple of (ciphertext, mac_tag, otp_key, mac_key):
        - ciphertext: XOR of plaintext and otp_key (same length as plaintext)
        - mac_tag: 32-byte HMAC-SHA256 authentication tag
        - otp_key: The one-time pad key (same length as plaintext) - KEEP SECRET
        - mac_key: The MAC key (32 bytes) - KEEP SECRET

    Security Notes:
        - otp_key and mac_key must be transmitted via secure key exchange
        - ciphertext and mac_tag can be sent via regular (untrusted) channel
        - ALL keys must be destroyed after single use
        - NEVER reuse an OTP key - this completely breaks security

    Example:
        >>> ct, mac, otp_key, mac_key = encrypt_view_once(b"Secret message")
        >>> len(otp_key) == len(b"Secret message")
        True
    """
    client = qrng_client or QrngClient()

    # Generate key material:
    # - OTP key: same length as plaintext (for XOR)
    # - MAC key: 32 bytes (for HMAC-SHA256)
    key_material = client.get_bytes(len(plaintext) + MAC_KEY_SIZE_BYTES)

    otp_key = key_material[:len(plaintext)]
    mac_key = key_material[len(plaintext):]

    # Encrypt: XOR plaintext with OTP key
    ciphertext = _xor_bytes(plaintext, otp_key)

    # Authenticate: HMAC over ciphertext (encrypt-then-MAC)
    mac_tag = _compute_mac(mac_key, ciphertext)

    return ciphertext, mac_tag, otp_key, mac_key


# -----------------------------------------------------------------------------
# Decryption
# -----------------------------------------------------------------------------

def decrypt_view_once(
    ciphertext: bytes,
    mac_tag: bytes,
    otp_key: bytes,
    mac_key: bytes,
) -> bytes:
    """
    Decrypt an OTP-encrypted view-once message with MAC verification.

    This function FIRST verifies the MAC, then decrypts. If the MAC
    verification fails, the ciphertext may have been tampered with
    and decryption is aborted.

    Args:
        ciphertext: Encrypted data (from encrypt_view_once).
        mac_tag: 32-byte authentication tag (from encrypt_view_once).
        otp_key: One-time pad key (must match ciphertext length).
        mac_key: 32-byte MAC key.

    Returns:
        Decrypted plaintext.

    Raises:
        OtpKeyLengthError: If otp_key length doesn't match ciphertext.
        OtpMacVerificationError: If MAC verification fails (tampering detected).

    Security Notes:
        - Keys must be destroyed immediately after decryption
        - If MAC fails, treat as a security event - log and alert
        - The message should only be shown ONCE and then deleted

    Example:
        >>> ct, mac, otp_key, mac_key = encrypt_view_once(b"Secret")
        >>> decrypt_view_once(ct, mac, otp_key, mac_key)
        b'Secret'
    """
    # Validate key length before verification
    if len(ciphertext) != len(otp_key):
        raise OtpKeyLengthError(
            f"OTP key length ({len(otp_key)}) must match ciphertext length ({len(ciphertext)})"
        )

    # Verify MAC FIRST (before any decryption)
    if not _verify_mac(mac_key, ciphertext, mac_tag):
        raise OtpMacVerificationError(
            "MAC verification failed. Ciphertext may have been tampered with. "
            "Do NOT attempt to decrypt."
        )

    # Decrypt: XOR ciphertext with OTP key
    return _xor_bytes(ciphertext, otp_key)

