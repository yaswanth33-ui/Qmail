"""
Crypto primitives for Qmail.

- AES-GCM for standard encrypted emails.
- OTP using QRNG-backed keys for "view once" messages.
- PQC signatures (Dilithium, Falcon) for message authentication.
- QRNG client for ANU Quantum Random Number Generator.
"""

