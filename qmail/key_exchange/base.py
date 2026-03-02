"""
=============================================================================
KEY EXCHANGE - Base Classes and Interfaces
=============================================================================

This module defines the abstract interface for key exchange strategies.
All key exchange implementations (BB84, PQC) follow this interface,
allowing them to be used interchangeably.

DESIGN PATTERN:
---------------
This uses the Strategy pattern - different key exchange algorithms
can be swapped without changing the rest of the system.

    KeyExchange (abstract base)
         │
         ├── Bb84KeyExchange  (simulated quantum)
         │
         └── PqcKemKeyExchange (post-quantum crypto)

PROTOCOL FLOW:
--------------
    ┌─────────────────┐                      ┌─────────────────┐
    │    INITIATOR    │                      │    RESPONDER    │
    │   (e.g. Alice)  │                      │   (e.g. Bob)    │
    └────────┬────────┘                      └────────┬────────┘
             │                                        │
             │  1. initiate() → init_message          │
             │═══════════════════════════════════════>│
             │                                        │
             │                    2. respond(init_message)
             │                       → (response_message, session_key)
             │                                        │
             │  3. response_message                   │
             │<═══════════════════════════════════════│
             │                                        │
    4. finalize(response_message)                     │
       → session_key                                  │
             │                                        │
    ═════════════════════════════════════════════════════════════
    BOTH PARTIES NOW SHARE THE SAME SESSION KEY (32 bytes)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------

class KeyExchangeError(Exception):
    """
    Base exception for key exchange operations.

    This exception is raised when key exchange fails due to:
    - Protocol errors (out of order calls)
    - Cryptographic failures (invalid keys, failed decapsulation)
    - Communication errors (malformed messages)
    """
    pass


# -----------------------------------------------------------------------------
# Data Classes
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class SessionKey:
    """
    A symmetric session key derived from key exchange.

    This key is used for AES encryption of the message body.
    The key should be treated as ephemeral and destroyed after use.

    Attributes:
        key_bytes: 32 bytes (256 bits) of key material for AES-256.

    Security Notes:
        - This key is derived from quantum or post-quantum key exchange
        - It should be registered with the KeyLifecycleManager
        - It must be zeroized after the message is encrypted/decrypted
    """
    key_bytes: bytes

    def __post_init__(self) -> None:
        """Validate key size."""
        if len(self.key_bytes) != 32:
            raise ValueError(
                f"Session key must be 32 bytes (256 bits), got {len(self.key_bytes)}"
            )

    def __repr__(self) -> str:
        """Hide key material in repr for security."""
        return f"SessionKey(key_bytes=<{len(self.key_bytes)} bytes hidden>)"


# -----------------------------------------------------------------------------
# Abstract Base Class
# -----------------------------------------------------------------------------

class KeyExchange(ABC):
    """
    Abstract base class for key exchange strategies.

    Implementations must provide three methods:
    1. initiate() - Start key exchange (initiator side)
    2. respond()  - Process initiator's message (responder side)
    3. finalize() - Complete key exchange (initiator side)

    After finalize/respond, both parties have the same SessionKey.

    Example:
        >>> initiator = SomeKeyExchange()
        >>> responder = SomeKeyExchange()
        >>>
        >>> init_msg = initiator.initiate()
        >>> response_msg, responder_key = responder.respond(init_msg)
        >>> initiator_key = initiator.finalize(response_msg)
        >>>
        >>> assert initiator_key.key_bytes == responder_key.key_bytes
    """

    @abstractmethod
    def initiate(self) -> bytes:
        """
        Start the key exchange (INITIATOR side).

        This generates the first message that must be sent to the responder.
        Internal state is stored for use in finalize().

        Returns:
            Bytes to send to the responder (public key or quantum data).

        Raises:
            KeyExchangeError: If initialization fails.
        """

    @abstractmethod
    def respond(self, message: bytes) -> Tuple[bytes, SessionKey]:
        """
        Process the initiator's message (RESPONDER side).

        This receives the initiator's first message, processes it,
        and produces both a response message and the shared session key.

        Args:
            message: The initiate() output from the initiator.

        Returns:
            Tuple of (response_message, session_key):
            - response_message: Bytes to send back to initiator
            - session_key: The derived session key (available immediately)

        Raises:
            KeyExchangeError: If the message is invalid or processing fails.
        """

    @abstractmethod
    def finalize(self, response: bytes) -> SessionKey:
        """
        Complete the key exchange (INITIATOR side).

        This processes the responder's response message and derives
        the same session key that the responder computed in respond().

        Args:
            response: The response_message from responder's respond().

        Returns:
            The derived session key (same as responder's key).

        Raises:
            KeyExchangeError: If initiate() wasn't called first,
                            or if the response is invalid.
        """

