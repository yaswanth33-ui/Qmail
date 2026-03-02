"""
=============================================================================
PQC KEM - Post-Quantum Key Encapsulation Mechanism
=============================================================================

PURPOSE:
--------
Provides PRODUCTION-READY post-quantum key exchange using ML-KEM-1024
(formerly known as Kyber1024). This is the RECOMMENDED key exchange
method for Qmail when real quantum hardware is not available.

WHAT IS ML-KEM:
---------------
ML-KEM (Module Lattice Key Encapsulation Mechanism) is the NIST-standardized
post-quantum key exchange algorithm (FIPS 203). It's based on the hardness
of the Module Learning With Errors (M-LWE) problem.

Security levels:
- ML-KEM-512:  Roughly equivalent to AES-128 security
- ML-KEM-768:  Roughly equivalent to AES-192 security
- ML-KEM-1024: Roughly equivalent to AES-256 security ← WE USE THIS

We use ML-KEM-1024 for maximum security margin against quantum computers.

HOW KEM WORKS:
--------------
A Key Encapsulation Mechanism (KEM) is different from traditional
key exchange (like Diffie-Hellman):

    INITIATOR                           RESPONDER
    ---------                           ---------
    1. Generate keypair:
       (public_key, secret_key)
    2. Send public_key
    ─────────────────────────────────>
                                        3. Encapsulate:
                                           (ciphertext, shared_secret)
                                           = Encaps(public_key)
    <─────────────────────────────────
                                        4. Send ciphertext
    5. Decapsulate:
       shared_secret = Decaps(secret_key, ciphertext)
    
    BOTH HAVE SAME shared_secret (32 bytes)

SECURITY PROPERTIES:
--------------------
- IND-CCA2 secure: Resistant to adaptive chosen-ciphertext attacks
- Post-quantum: Secure against Shor's algorithm (quantum factoring)
- NIST standardized: Extensively analyzed by cryptographers
- No setup required: Unlike BB84, works over classical networks

COMPARISON WITH BB84:
---------------------
┌────────────────────┬────────────────────┬────────────────────┐
│     Property       │      BB84          │     PQC KEM        │
├────────────────────┼────────────────────┼────────────────────┤
│ Security basis     │ Laws of physics    │ Math hardness      │
│ Infrastructure     │ Quantum hardware   │ Classical network  │
│ Ready for prod?    │ No (simulation)    │ YES                │
│ Key size           │ Variable           │ 32 bytes           │
│ Message sizes      │ 512 bytes          │ ~1.5 KB + 1.5 KB   │
└────────────────────┴────────────────────┴────────────────────┘

USAGE:
------
    from qmail.key_exchange import PqcKemKeyExchange

    # Initiator (sender)
    initiator = PqcKemKeyExchange()
    public_key = initiator.initiate()

    # Responder (recipient) - could be on different machine
    responder = PqcKemKeyExchange()
    ciphertext, responder_key = responder.respond(public_key)

    # Initiator finalizes
    initiator_key = initiator.finalize(ciphertext)

    # Both have the same 256-bit key!
    assert initiator_key.key_bytes == responder_key.key_bytes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple, Any

from qmail.key_exchange.base import KeyExchange, SessionKey, KeyExchangeError


# -----------------------------------------------------------------------------
# Lazy Loading for liboqs
# -----------------------------------------------------------------------------

_OQS_LOADED = False
_oqs: Optional[Any] = None


def _load_oqs():
    """Lazy-load liboqs-python KEM implementation."""
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

# Algorithm identifier for external APIs and storage
ALGORITHM_NAME = "ML-KEM-1024"

# liboqs algorithm name for ML-KEM-1024 (Kyber1024)
OQS_KEM_ALG = "Kyber1024"

# Session key size in bytes (truncate shared secret to this)
SESSION_KEY_BYTES = 32


# -----------------------------------------------------------------------------
# PQC KEM Implementation
# -----------------------------------------------------------------------------

@dataclass
class PqcKemKeyExchange(KeyExchange):
    """
    Post-Quantum key exchange using ML-KEM-1024 (Kyber1024).

    This is the RECOMMENDED key exchange for production use.
    It provides IND-CCA2 security and is NIST-standardized.

    Protocol:
        1. Initiator generates ML-KEM keypair, sends public key
        2. Responder encapsulates using public key → ciphertext + shared secret
        3. Responder sends ciphertext back
        4. Initiator decapsulates using secret key → same shared secret

    Message Sizes:
        - Public key:  ~1,568 bytes
        - Ciphertext:  ~1,568 bytes
        - Shared secret: 32 bytes (used as session key)

    Attributes:
        alg_name: Algorithm identifier for logging/storage
        _public_key: Initiator's public key (sent to responder)
        _secret_key: Initiator's secret key (used in finalize)
        _shared_secret: The derived shared secret (after respond/finalize)

    Thread Safety:
        A single instance should only be used for ONE key exchange.
        Create a new instance for each key exchange.
    """

    # Algorithm name for logging and storage
    alg_name: str = ALGORITHM_NAME

    # Initiator state
    _public_key: Optional[bytes] = field(default=None, repr=False)
    _secret_key: Optional[bytes] = field(default=None, repr=False)

    # Shared secret (available after respond or finalize)
    _shared_secret: Optional[bytes] = field(default=None, repr=False)

    def initiate(self) -> bytes:
        """
        Generate ML-KEM keypair and return public key.

        This starts the key exchange. The public key should be sent
        to the responder who will encapsulate a shared secret.

        Returns:
            Public key bytes (~1,568 bytes for ML-KEM-1024).

        Raises:
            KeyExchangeError: If keypair generation fails.

        Example:
            >>> kex = PqcKemKeyExchange()
            >>> public_key = kex.initiate()
            >>> len(public_key)  # ~1568 bytes
            1568
        """
        try:
            # Lazy-load liboqs
            _load_oqs()
            
            # liboqs API: KeyEncapsulation(alg) -> generate_keypair() returns public_key
            kem = _oqs.KeyEncapsulation(OQS_KEM_ALG)
            public_key = kem.generate_keypair()
            secret_key = kem.export_secret_key()
            self._public_key = bytes(public_key)
            self._secret_key = bytes(secret_key)
            return self._public_key
        except Exception as e:
            raise KeyExchangeError(f"ML-KEM keypair generation failed: {e}") from e

    def respond(self, message: bytes) -> Tuple[bytes, SessionKey]:
        """
        Encapsulate a shared secret using initiator's public key.

        This is called by the RESPONDER with the initiator's public key.
        It generates a random shared secret, encapsulates it with the
        public key, and returns both the ciphertext and the shared secret.

        Args:
            message: The initiator's public key (from initiate()).

        Returns:
            Tuple of (ciphertext, session_key):
            - ciphertext: Send this back to the initiator (~1,568 bytes)
            - session_key: The 256-bit session key (keep this!)

        Raises:
            KeyExchangeError: If encapsulation fails (invalid public key).

        Example:
            >>> responder = PqcKemKeyExchange()
            >>> ciphertext, key = responder.respond(initiator_public_key)
            >>> len(key.key_bytes)
            32
        """
        public_key = message

        try:
            # Lazy-load liboqs
            _load_oqs()
            
            # liboqs API: KeyEncapsulation(alg) -> encap_secret(public_key) -> (ciphertext, shared_secret)
            kem = _oqs.KeyEncapsulation(OQS_KEM_ALG)
            ciphertext, shared_secret = kem.encap_secret(public_key)
            self._shared_secret = bytes(shared_secret)

            # Truncate to 32 bytes for our session key
            session_key = SessionKey(key_bytes=shared_secret[:SESSION_KEY_BYTES])

            return ciphertext, session_key

        except Exception as e:
            raise KeyExchangeError(
                f"ML-KEM encapsulation failed: {e}. "
                "The public key may be invalid or corrupted."
            ) from e

    def finalize(self, response: bytes) -> SessionKey:
        """
        Decapsulate the shared secret using the ciphertext.

        This is called by the INITIATOR with the responder's ciphertext.
        It uses the secret key (from initiate()) to recover the same
        shared secret that the responder generated.

        Args:
            response: The ciphertext from responder's respond().

        Returns:
            The session key (identical to responder's session key).

        Raises:
            KeyExchangeError: If initiate() wasn't called first.
            KeyExchangeError: If decapsulation fails.

        Example:
            >>> initiator = PqcKemKeyExchange()
            >>> pub_key = initiator.initiate()
            >>> # ... send to responder, get ciphertext back ...
            >>> session_key = initiator.finalize(ciphertext)
        """
        if self._secret_key is None:
            raise KeyExchangeError(
                "PQC initiate() must be called before finalize(). "
                "The secret key is not available."
            )

        ciphertext = response

        try:
            # Lazy-load liboqs
            _load_oqs()
            
            # liboqs API: KeyEncapsulation(alg, secret_key) -> decap_secret(ciphertext) -> shared_secret
            kem = _oqs.KeyEncapsulation(OQS_KEM_ALG, self._secret_key)
            shared_secret = kem.decap_secret(ciphertext)
            self._shared_secret = bytes(shared_secret)

            return SessionKey(key_bytes=shared_secret[:SESSION_KEY_BYTES])

        except Exception as e:
            raise KeyExchangeError(
                f"ML-KEM decapsulation failed: {e}. "
                "The ciphertext may be invalid or corrupted."
            ) from e

    @property
    def algorithm(self) -> str:
        """Get the algorithm name for logging/storage."""
        return self.alg_name
