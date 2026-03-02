from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional
import secrets


class KeyKind(str, Enum):
    SESSION = "session"
    OTP = "otp"
    OTP_MAC = "otp_mac"


class KeyState(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    DESTROYED = "destroyed"


@dataclass
class ManagedKey:
    """
    Represents a piece of key material under lifecycle management.

    The underlying key bytes are stored in a mutable bytearray so we can
    best-effort overwrite them when calling destroy().
    """

    id: str
    kind: KeyKind
    algorithm: str
    created_at: datetime
    valid_until: Optional[datetime]
    usage_limit: int
    _key: bytearray = field(repr=False)
    usage_count: int = 0
    state: KeyState = KeyState.ACTIVE

    def get_bytes(self) -> bytes:
        if self.state != KeyState.ACTIVE:
            raise ValueError(f"Key {self.id} is not active (state={self.state})")
        return bytes(self._key)

    def register_use(self) -> None:
        if self.state != KeyState.ACTIVE:
            raise ValueError(f"Key {self.id} is not active (state={self.state})")
        self.usage_count += 1
        if self.usage_count >= self.usage_limit:
            self.state = KeyState.EXPIRED

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.utcnow()
        if self.state in (KeyState.EXPIRED, KeyState.DESTROYED):
            return True
        if self.valid_until is not None and now >= self.valid_until:
            self.state = KeyState.EXPIRED
            return True
        return False

    def destroy(self) -> None:
        """
        Best-effort zeroization of key material in memory.
        """
        for i in range(len(self._key)):
            self._key[i] = 0
        self.state = KeyState.DESTROYED


class KeyLifecycleManager:
    """
    In-memory key lifecycle manager.

    This prototype manager:
    - Issues IDs for keys.
    - Tracks usage limits and expiry.
    - Can destroy keys on demand.

    For production, this should be backed by an encrypted key store and
    integrate with OS keychain or a hardware-backed keystore.
    """

    def __init__(self) -> None:
        self._keys: Dict[str, ManagedKey] = {}

    def _new_id(self) -> str:
        return secrets.token_hex(16)

    def register_session_key(
        self,
        key_bytes: bytes,
        algorithm: str,
        ttl_seconds: int = 3600,
        usage_limit: int = 1,
    ) -> ManagedKey:
        key_id = self._new_id()
        mk = ManagedKey(
            id=key_id,
            kind=KeyKind.SESSION,
            algorithm=algorithm,
            created_at=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(seconds=ttl_seconds),
            usage_limit=usage_limit,
            _key=bytearray(key_bytes),
        )
        self._keys[key_id] = mk
        return mk

    def register_otp_key(self, key_bytes: bytes, is_mac_key: bool = False) -> ManagedKey:
        key_id = self._new_id()
        kind = KeyKind.OTP_MAC if is_mac_key else KeyKind.OTP
        mk = ManagedKey(
            id=key_id,
            kind=kind,
            algorithm="OTP",
            created_at=datetime.utcnow(),
            # OTP keys are strictly one-time and short-lived
            valid_until=datetime.utcnow() + timedelta(minutes=5),
            usage_limit=1,
            _key=bytearray(key_bytes),
        )
        self._keys[key_id] = mk
        return mk

    def get(self, key_id: str) -> Optional[ManagedKey]:
        key = self._keys.get(key_id)
        if key is None:
            return None
        key.is_expired()
        return key

    def destroy(self, key_id: str) -> None:
        key = self._keys.get(key_id)
        if key is not None:
            key.destroy()
            # Optionally keep metadata but drop reference; we keep metadata here

    def destroy_all(self) -> None:
        for key in self._keys.values():
            key.destroy()

