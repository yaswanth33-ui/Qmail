"""
=============================================================================
KEY LIFECYCLE - Key Management and Secure Destruction
=============================================================================

This module provides:
1. ManagedKey: A key wrapper that tracks usage, expiration, and state
2. KeyLifecycleManager: A registry for managing multiple keys

SECURITY MODEL:
---------------
Keys in Qmail are ephemeral - they should be:
- Used once (for OTP keys) or limited times (for session keys)
- Destroyed as soon as their purpose is fulfilled
- Never logged or written to disk unencrypted

The lifecycle manager enforces these constraints.

STATE MACHINE:
--------------
    ┌────────┐    register_use()     ┌─────────┐    destroy()   ┌───────────┐
    │ ACTIVE │ ──────────────────────>│ EXPIRED │──────────────>│ DESTROYED │
    └────────┘   (limit hit)          └─────────┘               └───────────┘
         │                                  ▲
         │                                  │
         └───────── is_expired() ───────────┘
                (time expired)

Once DESTROYED:
- Key bytes are overwritten with zeros
- get_bytes() will raise an exception
- State is terminal (cannot return to active)
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------

class KeyKind(str, Enum):
    """
    Types of keys managed by the lifecycle manager.

    Each type has different default behaviors:
    - SESSION: AES encryption keys, typically one-time use
    - OTP: One-time pad keys, strictly single-use
    - OTP_MAC: MAC keys for OTP integrity, strictly single-use
    """
    SESSION = "session"
    OTP = "otp"
    OTP_MAC = "otp_mac"


class KeyState(str, Enum):
    """
    Lifecycle state of a managed key.

    State transitions:
    - ACTIVE → EXPIRED: Usage limit reached or TTL expired
    - EXPIRED → DESTROYED: destroy() called
    - ACTIVE → DESTROYED: destroy() called early (normal cleanup)

    Terminal states: EXPIRED, DESTROYED (cannot return to ACTIVE)
    """
    ACTIVE = "active"
    EXPIRED = "expired"
    DESTROYED = "destroyed"


# -----------------------------------------------------------------------------
# ManagedKey
# -----------------------------------------------------------------------------

@dataclass
class ManagedKey:
    """
    A key with lifecycle management.

    This wrapper around raw key bytes provides:
    - Usage tracking (how many times the key has been used)
    - Usage limits (automatically expire after N uses)
    - Time-based expiration (automatically expire after TTL)
    - Secure destruction (zeroize key bytes)

    Attributes:
        id: Unique identifier for this key (random hex string)
        kind: Type of key (SESSION, OTP, OTP_MAC)
        algorithm: Algorithm name for auditing (e.g., "AES-256-GCM")
        created_at: When the key was registered
        valid_until: When the key expires (None = no time limit)
        usage_limit: Maximum number of uses (e.g., 1 for OTP)
        usage_count: Current number of uses
        state: Current lifecycle state

    Private Attributes:
        _key: The actual key bytes (stored in mutable bytearray for zeroization)

    Security Notes:
        - Always call destroy() when done with a key
        - The key is stored in a bytearray, not bytes, so we can zeroize it
        - Zeroization is best-effort (Python doesn't guarantee memory clearing)
    """

    id: str
    kind: KeyKind
    algorithm: str
    created_at: datetime
    valid_until: Optional[datetime]
    usage_limit: int
    _key: bytearray = field(repr=False)  # Hidden from repr for security
    usage_count: int = 0
    state: KeyState = KeyState.ACTIVE

    def get_bytes(self) -> bytes:
        """
        Get the raw key bytes.

        This is the only way to access the actual key material.
        Raises an exception if the key is not active.

        Returns:
            The key bytes (immutable copy).

        Raises:
            ValueError: If key is EXPIRED or DESTROYED.

        Example:
            >>> key = manager.register_session_key(raw_bytes, "AES-256", 3600, 1)
            >>> aes_key = key.get_bytes()
            >>> encrypt(aes_key, plaintext)
        """
        if self.state != KeyState.ACTIVE:
            raise ValueError(
                f"Key {self.id} is not active (state={self.state.value}). "
                "Cannot retrieve key bytes from expired or destroyed keys."
            )
        return bytes(self._key)

    def register_use(self) -> None:
        """
        Record one use of this key.

        Call this AFTER each use of the key. If the usage limit is reached,
        the key state transitions to EXPIRED.

        Raises:
            ValueError: If key is not ACTIVE.

        Example:
            >>> encrypted = encrypt(key.get_bytes(), plaintext)
            >>> key.register_use()  # May trigger expiration
        """
        if self.state != KeyState.ACTIVE:
            raise ValueError(
                f"Key {self.id} is not active (state={self.state.value}). "
                "Cannot register use on expired or destroyed keys."
            )

        self.usage_count += 1

        if self.usage_count >= self.usage_limit:
            self.state = KeyState.EXPIRED
            # Note: We don't zeroize here - the key might still be needed
            # for in-flight operations. Call destroy() explicitly.

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """
        Check if the key has expired (by time or usage).

        This also UPDATES the state to EXPIRED if the time limit has passed.
        Call this before using a key to ensure it's still valid.

        Args:
            now: Current time (default: UTC now). Useful for testing.

        Returns:
            True if key is expired or destroyed, False if still active.

        Example:
            >>> if not key.is_expired():
            ...     data = encrypt(key.get_bytes(), plaintext)
        """
        # Already in terminal state
        if self.state in (KeyState.EXPIRED, KeyState.DESTROYED):
            return True

        # Check time-based expiration
        now = now or datetime.utcnow()
        if self.valid_until is not None and now >= self.valid_until:
            self.state = KeyState.EXPIRED
            return True

        return False

    def destroy(self) -> None:
        """
        Securely destroy the key material.

        This overwrites the key bytes with zeros (best-effort zeroization)
        and sets the state to DESTROYED.

        This should be called when:
        - The key is no longer needed
        - An error occurred during the operation
        - The key has expired

        Security Notes:
            - Zeroization is best-effort in Python
            - The GC may retain copies of the original bytes
            - For true secure deletion, use OS-level secure memory APIs

        Example:
            >>> try:
            ...     encrypted = encrypt(key.get_bytes(), plaintext)
            ...     key.register_use()
            ... finally:
            ...     key.destroy()
        """
        # Overwrite key material with zeros
        for i in range(len(self._key)):
            self._key[i] = 0

        self.state = KeyState.DESTROYED


# -----------------------------------------------------------------------------
# KeyLifecycleManager
# -----------------------------------------------------------------------------

class KeyLifecycleManager:
    """
    Registry and lifecycle manager for cryptographic keys.

    This class:
    - Issues unique IDs for keys
    - Tracks all registered keys
    - Provides convenience methods for registering different key types
    - Can destroy individual keys or all keys at once

    Usage Pattern:
        1. Create a manager instance (typically one per client/session)
        2. Register keys after key exchange
        3. Access keys via get() when needed
        4. Destroy keys when done (or call destroy_all() on shutdown)

    Thread Safety:
        This implementation is NOT thread-safe. If shared across threads,
        wrap access with appropriate locks.

    Example:
        >>> manager = KeyLifecycleManager()
        >>> 
        >>> # Register a session key
        >>> key = manager.register_session_key(raw_bytes, "AES-256-GCM", 3600, 1)
        >>> 
        >>> # Use the key
        >>> aes_bytes = key.get_bytes()
        >>> encrypted = encrypt(aes_bytes, plaintext)
        >>> key.register_use()
        >>> 
        >>> # Destroy when done
        >>> manager.destroy(key.id)
        >>> 
        >>> # On shutdown
        >>> manager.destroy_all()
    """

    def __init__(self) -> None:
        """Initialize an empty key registry."""
        self._keys: Dict[str, ManagedKey] = {}

    def _generate_key_id(self) -> str:
        """
        Generate a unique key identifier.

        Returns:
            32-character hex string (128 bits of randomness).
        """
        return secrets.token_hex(16)

    def register_session_key(
        self,
        key_bytes: bytes,
        algorithm: str,
        ttl_seconds: int = 3600,
        usage_limit: int = 1,
    ) -> ManagedKey:
        """
        Register an AES session key.

        Session keys are used for standard message encryption.
        Default: 1 hour TTL, single use.

        Args:
            key_bytes: Raw key material (typically 32 bytes for AES-256).
            algorithm: Algorithm name for auditing (e.g., "AES-256-GCM").
            ttl_seconds: Time-to-live in seconds (default: 3600 = 1 hour).
            usage_limit: Maximum uses before expiration (default: 1).

        Returns:
            ManagedKey instance. Store the .id for later retrieval.

        Example:
            >>> from qmail.key_exchange import PqcKemKeyExchange
            >>> kex = PqcKemKeyExchange()
            >>> # ... key exchange ...
            >>> session_key = kex.finalize(response)
            >>> managed = manager.register_session_key(
            ...     session_key.key_bytes,
            ...     "AES-256-GCM",
            ...     ttl_seconds=3600,
            ...     usage_limit=1
            ... )
        """
        key_id = self._generate_key_id()
        now = datetime.utcnow()

        managed_key = ManagedKey(
            id=key_id,
            kind=KeyKind.SESSION,
            algorithm=algorithm,
            created_at=now,
            valid_until=now + timedelta(seconds=ttl_seconds),
            usage_limit=usage_limit,
            _key=bytearray(key_bytes),  # Mutable for zeroization
        )

        self._keys[key_id] = managed_key
        return managed_key

    def register_otp_key(
        self,
        key_bytes: bytes,
        is_mac_key: bool = False,
    ) -> ManagedKey:
        """
        Register an OTP (one-time pad) key.

        OTP keys are strictly single-use and short-lived.
        They're used for "view-once" messages.

        Args:
            key_bytes: Raw OTP key material (same length as message).
            is_mac_key: If True, register as OTP_MAC key instead of OTP.

        Returns:
            ManagedKey instance.

        Security Notes:
            - OTP keys MUST be used exactly once
            - OTP keys have a very short TTL (5 minutes)
            - Destroy OTP keys immediately after decryption

        Example:
            >>> from qmail.crypto import encrypt_view_once
            >>> ct, mac, otp_key, mac_key = encrypt_view_once(plaintext)
            >>> managed_otp = manager.register_otp_key(otp_key, is_mac_key=False)
            >>> managed_mac = manager.register_otp_key(mac_key, is_mac_key=True)
        """
        key_id = self._generate_key_id()
        now = datetime.utcnow()

        kind = KeyKind.OTP_MAC if is_mac_key else KeyKind.OTP

        managed_key = ManagedKey(
            id=key_id,
            kind=kind,
            algorithm="OTP",
            created_at=now,
            valid_until=now + timedelta(minutes=5),  # Short-lived!
            usage_limit=1,  # Strictly single-use!
            _key=bytearray(key_bytes),
        )

        self._keys[key_id] = managed_key
        return managed_key

    def get(self, key_id: str) -> Optional[ManagedKey]:
        """
        Retrieve a key by its ID.

        Also checks and updates expiration status.

        Args:
            key_id: The key's unique identifier.

        Returns:
            ManagedKey if found, None if not found.

        Note:
            This does NOT raise an error for expired keys - it returns
            the key object so you can check its state. Use is_expired()
            before accessing key bytes.
        """
        key = self._keys.get(key_id)
        if key is not None:
            key.is_expired()  # Update expiration status
        return key

    def destroy(self, key_id: str) -> None:
        """
        Destroy a specific key.

        This zeroizes the key material. The metadata is retained
        for auditing purposes.

        Args:
            key_id: The key's unique identifier.

        Note:
            Safe to call even if key doesn't exist or is already destroyed.
        """
        key = self._keys.get(key_id)
        if key is not None:
            key.destroy()

    def destroy_all(self) -> None:
        """
        Destroy all registered keys.

        Call this on application shutdown to ensure no key material
        remains in memory.

        Example:
            >>> try:
            ...     # Application logic
            ...     pass
            ... finally:
            ...     manager.destroy_all()
        """
        for key in self._keys.values():
            key.destroy()

    @property
    def active_key_count(self) -> int:
        """Count of currently active (non-expired, non-destroyed) keys."""
        return sum(1 for k in self._keys.values() if k.state == KeyState.ACTIVE)

    @property
    def total_key_count(self) -> int:
        """Total number of keys ever registered (including destroyed)."""
        return len(self._keys)

