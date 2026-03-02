from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol, Tuple


class KeyExchangeError(Exception):
    pass


class SymmetricSessionKey(Protocol):
    key_bytes: bytes


@dataclass
class SessionKey:
    key_bytes: bytes


class KeyExchange(ABC):
    """
    Abstract base for key exchange strategies.
    """

    @abstractmethod
    def initiate(self) -> bytes:
        """
        Initiator side: start the key exchange, returning the message
        that must be sent to the responder.
        """

    @abstractmethod
    def respond(self, message: bytes) -> Tuple[bytes, SessionKey]:
        """
        Responder side: process the initiator message and return
        (response_message, session_key).
        """

    @abstractmethod
    def finalize(self, response: bytes) -> SessionKey:
        """
        Initiator side: finalize the exchange with the responder's response
        and derive the shared session key.
        """

