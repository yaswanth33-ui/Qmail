from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from pqcrypto.sign import falcon_512, ml_dsa_44


DEFAULT_SIG_ALG_DILITHIUM = "Dilithium2"
DEFAULT_SIG_ALG_FALCON = "Falcon-512"


@dataclass
class SignatureKeypair:
    public_key: bytes
    private_key: bytes
    algorithm: str


# Map the algorithm names used in the rest of the codebase
# to the concrete pqcrypto implementations.
_SIG_IMPLS: Dict[str, object] = {
    DEFAULT_SIG_ALG_DILITHIUM: ml_dsa_44,  # NIST ML-DSA level-2 (Dilithium2-equivalent)
    DEFAULT_SIG_ALG_FALCON: falcon_512,
}


def _get_impl(algorithm: str):
    try:
        return _SIG_IMPLS[algorithm]
    except KeyError as exc:
        raise ValueError(f"Unsupported signature algorithm: {algorithm!r}") from exc


def generate_keypair(algorithm: str = DEFAULT_SIG_ALG_DILITHIUM) -> SignatureKeypair:
    """
    Generate a PQC signature keypair (e.g., Dilithium or Falcon) using pqcrypto.
    The external API and algorithm names remain the same as the previous liboqs-based version.
    """
    impl = _get_impl(algorithm)
    public_key, private_key = impl.generate_keypair()
    return SignatureKeypair(public_key=public_key, private_key=private_key, algorithm=algorithm)


def sign_message(message: bytes, private_key: bytes, algorithm: str) -> bytes:
    """
    Sign an arbitrary message (typically the ciphertext) with a PQC signature scheme.
    """
    impl = _get_impl(algorithm)
    # pqcrypto API: sign(secret_key, message) -> signature
    return impl.sign(private_key, message)


def verify_signature(message: bytes, signature: bytes, public_key: bytes, algorithm: str) -> bool:
    """
    Verify a PQC signature on the given message.
    """
    impl = _get_impl(algorithm)
    # pqcrypto API: verify(public_key, message, signature) -> bool
    return impl.verify(public_key, message, signature)

