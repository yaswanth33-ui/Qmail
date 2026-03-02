"""
Key management and lifecycle utilities for Qmail.

Responsibilities:
- Track key metadata (type, algorithm, creation/expiry, usage).
- Enforce usage limits (e.g., one-time OTP keys).
- Provide best-effort in-memory zeroization when keys are destroyed.

Persistent encrypted key storage is intentionally left out of this prototype;
keys are managed in-memory only and should be extended to use an OS keystore
or passphrase-derived master key for production use.
"""

