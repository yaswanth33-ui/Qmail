"""
=============================================================================
PQC SIGNATURES - Post-Quantum Digital Signatures
=============================================================================

PURPOSE:
--------
Provides digital signatures using Post-Quantum Cryptography (PQC) algorithms.
These signatures are secure against both classical AND quantum computers.

WHY POST-QUANTUM SIGNATURES:
----------------------------
Current signature schemes (RSA, ECDSA) can be broken by quantum computers
running Shor's algorithm. PQC signatures are based on mathematical problems
believed to be hard even for quantum computers:
- Lattice problems (Dilithium/ML-DSA)
- Hash-based constructions (SPHINCS+)
- Code-based problems
- Multivariate polynomials

SUPPORTED ALGORITHMS:
---------------------
1. Dilithium2 (ML-DSA-44)
   - NIST standardized (FIPS 204)
   - Based on Module Learning with Errors (M-LWE)
   - Fast verification, compact signatures
   - Recommended for most use cases

2. Falcon-512
   - Alternative NIST finalist
   - Based on NTRU lattices
   - Smaller signatures than Dilithium
   - More complex implementation

SIGNATURE PROPERTIES:
---------------------
- Authenticity: Only the key holder can create valid signatures
- Integrity: Any modification to the message invalidates the signature
- Non-repudiation: Sender cannot deny sending (they have the private key)
- Post-quantum security: Secure against Shor's algorithm

MESSAGE FLOW:
-------------
    SENDER                                  RECIPIENT
    ------                                  ---------
    1. Generate PQC keypair (once)
    2. Share public key with recipient
    3. Encrypt message → ciphertext
    4. Sign ciphertext with private key
    5. Send {ciphertext, signature}
                                            6. Retrieve sender's public key
                                            7. Verify signature
                                            8. Decrypt message

USAGE:
------
    from qmail.crypto.signatures import generate_keypair, sign_message, verify_signature

    # Generate keypair (typically done once per user)
    keypair = generate_keypair("Dilithium2")
    # Store keypair.private_key securely
    # Share keypair.public_key with contacts

    # Sign a message
    signature = sign_message(ciphertext, keypair.private_key, "Dilithium2")

    # Verify (recipient side)
    is_valid = verify_signature(ciphertext, signature, sender_public_key, "Dilithium2")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional


# Lazy imports to avoid loading oqs unless actually used
_OQS_LOADED = False
_oqs: Optional[Any] = None


def _load_oqs():
    """Lazy-load liboqs-python (Open Quantum Safe) implementations."""
    global _OQS_LOADED, _oqs
    
    if _OQS_LOADED:
        return
    
    try:
        import oqs
        _oqs = oqs
        _OQS_LOADED = True
    except ImportError as e:
        raise ImportError(
            "liboqs-python is not properly installed. "
            "Ensure liboqs C library is built and liboqs-python is installed."
        ) from e


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

ALGORITHM_DILITHIUM = "Dilithium2"  # Maps to ML-DSA-44 (NIST FIPS 204)
ALGORITHM_FALCON = "Falcon-512"     # Falcon-512 variant

# Map our algorithm names to liboqs algorithm names
# liboqs 0.15+ renamed Dilithium2 → ML-DSA-44 (NIST FIPS 204)
_OQS_ALGORITHM_MAP = {
    "Dilithium2": "ML-DSA-44",
    "Falcon-512": "Falcon-512",
}

DEFAULT_ALGORITHM = ALGORITHM_DILITHIUM


# -----------------------------------------------------------------------------
# Algorithm Registry
# -----------------------------------------------------------------------------

# Supported algorithm names
_SUPPORTED_ALGORITHMS = [ALGORITHM_DILITHIUM, ALGORITHM_FALCON]


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------

class SignatureError(Exception):
    """Base exception for signature operations."""
    pass


class UnsupportedAlgorithmError(SignatureError):
    """Requested algorithm is not supported."""
    pass


class SignatureVerificationError(SignatureError):
    """Signature verification failed."""
    pass


# -----------------------------------------------------------------------------
# Data Classes
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class SignatureKeypair:
    """
    A PQC signature keypair.

    Attributes:
        public_key: Public key bytes (safe to share).
        private_key: Private key bytes (KEEP SECRET).
        algorithm: Algorithm name used to generate this keypair.

    Security Note:
        The private_key must be stored securely (e.g., OS keychain).
        Loss of the private key means loss of signing capability.
        Compromise of private key means signatures can be forged.
    """
    public_key: bytes
    private_key: bytes
    algorithm: str


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _get_oqs_alg_name(algorithm: str) -> str:
    """
    Get the liboqs algorithm name for a given algorithm.

    Args:
        algorithm: Algorithm name (e.g., "Dilithium2", "Falcon-512").

    Returns:
        liboqs algorithm name string.

    Raises:
        UnsupportedAlgorithmError: If algorithm is not supported.
    """
    _load_oqs()
    
    if algorithm not in _OQS_ALGORITHM_MAP:
        supported = ", ".join(_OQS_ALGORITHM_MAP.keys())
        raise UnsupportedAlgorithmError(
            f"Unsupported signature algorithm: {algorithm!r}. "
            f"Supported: {supported}"
        )
    return _OQS_ALGORITHM_MAP[algorithm]


def get_supported_algorithms() -> list[str]:
    """
    Get list of supported signature algorithms.

    Returns:
        List of algorithm name strings.
    """
    return list(_OQS_ALGORITHM_MAP.keys())


# -----------------------------------------------------------------------------
# Key Generation
# -----------------------------------------------------------------------------

def generate_keypair(algorithm: str = DEFAULT_ALGORITHM) -> SignatureKeypair:
    """
    Generate a new PQC signature keypair.

    This should typically be done ONCE per user and the private key
    stored securely in the OS keychain or hardware security module.

    Args:
        algorithm: Signature algorithm to use.
                  Default: "Dilithium2" (ML-DSA-44, NIST standardized).
                  Alternative: "Falcon-512".

    Returns:
        SignatureKeypair with public and private keys.

    Raises:
        UnsupportedAlgorithmError: If algorithm is not supported.

    Example:
        >>> keypair = generate_keypair("Dilithium2")
        >>> len(keypair.public_key) > 0
        True
    """
    oqs_alg = _get_oqs_alg_name(algorithm)

    # liboqs API: Signature(alg) -> generate_keypair() returns public_key
    # secret key is stored internally and exported via export_secret_key()
    sig = _oqs.Signature(oqs_alg)
    public_key = sig.generate_keypair()
    private_key = sig.export_secret_key()

    return SignatureKeypair(
        public_key=bytes(public_key),
        private_key=bytes(private_key),
        algorithm=algorithm,
    )


# -----------------------------------------------------------------------------
# Signing
# -----------------------------------------------------------------------------

def sign_message(
    message: bytes,
    private_key: bytes,
    algorithm: str,
) -> bytes:
    """
    Sign a message using a PQC signature scheme.

    Typically, you sign the CIPHERTEXT (not plaintext) to provide
    authentication of the encrypted data without revealing the content.

    Args:
        message: Data to sign (typically ciphertext).
        private_key: Signer's private key.
        algorithm: Signature algorithm (must match key's algorithm).

    Returns:
        Digital signature bytes.

    Raises:
        UnsupportedAlgorithmError: If algorithm is not supported.
        SignatureError: If signing fails.

    Example:
        >>> keypair = generate_keypair("Dilithium2")
        >>> signature = sign_message(b"Hello", keypair.private_key, "Dilithium2")
        >>> len(signature) > 0
        True
    """
    oqs_alg = _get_oqs_alg_name(algorithm)

    try:
        # liboqs API: Signature(alg, secret_key) -> sign(message) -> signature
        sig = _oqs.Signature(oqs_alg, private_key)
        return bytes(sig.sign(message))
    except Exception as e:
        raise SignatureError(f"Failed to sign message: {e}") from e


# -----------------------------------------------------------------------------
# Verification
# -----------------------------------------------------------------------------

def verify_signature(
    message: bytes,
    signature: bytes,
    public_key: bytes,
    algorithm: str,
) -> bool:
    """
    Verify a PQC digital signature.

    This should be called BEFORE processing a message to ensure
    it actually came from the claimed sender.

    Args:
        message: Original data that was signed.
        signature: Signature to verify.
        public_key: Signer's public key.
        algorithm: Signature algorithm (must match key's algorithm).

    Returns:
        True if signature is valid, False otherwise.

    Raises:
        UnsupportedAlgorithmError: If algorithm is not supported.

    Security Note:
        If verification fails, treat the message as potentially malicious.
        Do NOT process or display the message content.

    Example:
        >>> keypair = generate_keypair("Dilithium2")
        >>> sig = sign_message(b"Hello", keypair.private_key, "Dilithium2")
        >>> verify_signature(b"Hello", sig, keypair.public_key, "Dilithium2")
        True
        >>> verify_signature(b"Tampered", sig, keypair.public_key, "Dilithium2")
        False
    """
    oqs_alg = _get_oqs_alg_name(algorithm)

    try:
        # liboqs API: Signature(alg) -> verify(message, signature, public_key) -> bool
        sig = _oqs.Signature(oqs_alg)
        return sig.verify(message, signature, public_key)
    except Exception:
        # Verification failure or malformed input
        return False

