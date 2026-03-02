"""
=============================================================================
LAYER 3: KEY MANAGEMENT
=============================================================================

This layer manages the lifecycle of cryptographic keys, ensuring they are
used correctly and securely destroyed when no longer needed.

PURPOSE:
--------
Cryptographic keys have strict requirements:
1. Usage limits: OTP keys must be used exactly ONCE
2. Expiration: Session keys have limited validity periods
3. Zeroization: Keys must be securely erased from memory when done
4. Tracking: Audit trail of key creation, usage, and destruction

This layer enforces these requirements.

KEY LIFECYCLE:
--------------
    ┌─────────────────────────────────────────────────────────────────────┐
    │                        KEY LIFECYCLE                                 │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │   CREATION          ACTIVE            EXPIRED         DESTROYED     │
    │   ────────        ────────          ────────         ──────────     │
    │                                                                      │
    │   Key Exchange  →  Register  →  Use  →  Limit  →  Expire  →  Zero  │
    │   (BB84/PQC)       with        with      hit!       time      fill  │
    │                    manager     count                 up!      memory│
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

KEY TYPES:
----------
┌───────────────┬──────────────┬─────────────┬─────────────────────────────┐
│  Key Type     │  Usage Limit │  Default TTL│  Purpose                    │
├───────────────┼──────────────┼─────────────┼─────────────────────────────┤
│  SESSION      │  1           │  1 hour     │  AES encryption of message  │
│  OTP          │  1           │  5 minutes  │  One-time pad encryption    │
│  OTP_MAC      │  1           │  5 minutes  │  OTP integrity MAC key      │
└───────────────┴──────────────┴─────────────┴─────────────────────────────┘

SECURITY PROPERTIES:
--------------------
- Usage enforcement: Keys cannot exceed their usage limit
- Time enforcement: Time-expired keys are marked and rejected
- Secure destruction: Key bytes are overwritten with zeros
- State tracking: Clear state transitions (ACTIVE → EXPIRED → DESTROYED)

WHY ZEROIZATION:
----------------
When a key is "destroyed", simply freeing memory isn't enough:
- Memory may be swapped to disk
- Memory may be retained in freed pages
- Memory dumps could capture key material

We overwrite key bytes with zeros as a best-effort defense.
(True secure deletion requires OS/hardware support beyond Python's control)

USAGE:
------
    from qmail.keys import KeyLifecycleManager, KeyKind

    manager = KeyLifecycleManager()

    # Register a session key
    managed_key = manager.register_session_key(
        key_bytes=session_key.key_bytes,
        algorithm="AES-256-GCM",
        ttl_seconds=3600,
        usage_limit=1
    )

    # Use the key
    actual_bytes = managed_key.get_bytes()  # Raises if expired/destroyed
    managed_key.register_use()  # Tracks usage, may trigger expiration

    # Destroy when done
    manager.destroy(managed_key.id)  # Zeroizes key material

NOTE:
-----
This is an IN-MEMORY prototype. Production systems should:
- Use OS keychain (Windows Credential Manager, macOS Keychain, etc.)
- Use hardware security modules (HSM) for high-value keys
- Implement key escrow/recovery procedures
"""

from qmail.keys.lifecycle import (
    KeyKind,
    KeyState,
    ManagedKey,
    KeyLifecycleManager,
)

__all__ = [
    "KeyKind",
    "KeyState",
    "ManagedKey",
    "KeyLifecycleManager",
]
