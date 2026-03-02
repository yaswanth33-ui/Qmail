from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from pqcrypto.kem import ml_kem_1024

from qmail.key_exchange.base import KeyExchange, SessionKey, KeyExchangeError


DEFAULT_PQC_ALG = "Kyber1024"  # External name; we map this to ML-KEM-1024 internally.


@dataclass
class PqcKemKeyExchange(KeyExchange):
    """
    PQC key exchange using a KEM (Kyber/ML-KEM via pqcrypto).

    Initiator (client A) creates a KEM keypair and sends the public key.
    Responder (client B) encapsulates to derive a shared secret and sends
    back the ciphertext. Both sides derive the same symmetric session key.
    """

    alg_name: str = DEFAULT_PQC_ALG
    _public_key: bytes | None = None
    _secret_key: bytes | None = None
    _shared_secret: bytes | None = None

    def initiate(self) -> bytes:
        """
        Generate a PQC KEM keypair and return the public key.
        Uses ML-KEM-1024 (Kyber1024-equivalent) via pqcrypto.
        """
        try:
            public_key, secret_key = ml_kem_1024.generate_keypair()
            self._public_key = public_key
            self._secret_key = secret_key
            return public_key
        except Exception as e:  # pragma: no cover - depends on underlying bindings
            raise KeyExchangeError(f"PQC initiate failed: {e}") from e

    def respond(self, message: bytes) -> Tuple[bytes, SessionKey]:
        """
        Given the initiator's public key, encapsulate to derive a shared secret
        and return (ciphertext, session_key).
        """
        public_key = message
        try:
            # pqcrypto KEM API: encrypt(public_key) -> (ciphertext, shared_secret)
            ciphertext, shared_secret = ml_kem_1024.encrypt(public_key)
            self._shared_secret = shared_secret
            return ciphertext, SessionKey(key_bytes=shared_secret[:32])
        except Exception as e:  # pragma: no cover
            raise KeyExchangeError(f"PQC respond failed: {e}") from e

    def finalize(self, response: bytes) -> SessionKey:
        """
        Given the responder's ciphertext, decapsulate using the initiator's
        secret key and return the derived session key.
        """
        if self._secret_key is None:
            raise KeyExchangeError("PQC initiate must be called before finalize")
        ciphertext = response
        try:
            # pqcrypto KEM API: decrypt(secret_key, ciphertext) -> shared_secret
            shared_secret = ml_kem_1024.decrypt(self._secret_key, ciphertext)
            self._shared_secret = shared_secret
            return SessionKey(key_bytes=shared_secret[:32])
        except Exception as e:  # pragma: no cover
            raise KeyExchangeError(f"PQC finalize failed: {e}") from e
