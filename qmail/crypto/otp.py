from __future__ import annotations

from typing import Tuple
import hashlib
import hmac

from qmail.crypto.qrng import QrngClient


def xor_bytes(a: bytes, b: bytes) -> bytes:
    if len(a) != len(b):
        raise ValueError("OTP requires key and message to be the same length")
    return bytes(x ^ y for x, y in zip(a, b))


def _hmac_sha256(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


def encrypt_view_once(
    plaintext: bytes,
    qrng_client: QrngClient | None = None,
) -> Tuple[bytes, bytes, bytes, bytes]:
    """
    Encrypt `plaintext` using a QRNG-backed one-time pad with MAC.

    Returns (ciphertext, mac_tag, otp_key, mac_key).

    - `otp_key` is used once for XOR-based encryption.
    - `mac_key` is used once to authenticate the ciphertext via HMAC-SHA256.
    - Callers should persist only (ciphertext, mac_tag) and keep keys
      in volatile memory for first-view decryption.
    """
    qrng_client = qrng_client or QrngClient()
    key_material = qrng_client.get_bytes(len(plaintext) + 32)
    otp_key = key_material[: len(plaintext)]
    mac_key = key_material[len(plaintext) :]
    ciphertext = xor_bytes(plaintext, otp_key)
    mac_tag = _hmac_sha256(mac_key, ciphertext)
    return ciphertext, mac_tag, otp_key, mac_key


def decrypt_view_once(
    ciphertext: bytes,
    mac_tag: bytes,
    otp_key: bytes,
    mac_key: bytes,
) -> bytes:
    """
    Decrypt a QRNG-backed one-time pad ciphertext with MAC verification.

    Raises ValueError if MAC verification fails.
    """
    if len(ciphertext) != len(otp_key):
        raise ValueError("OTP key length must match ciphertext length")
    expected_mac = _hmac_sha256(mac_key, ciphertext)
    if not hmac.compare_digest(expected_mac, mac_tag):
        raise ValueError("OTP MAC verification failed")
    return xor_bytes(ciphertext, otp_key)

