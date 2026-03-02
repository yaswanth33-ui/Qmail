"""
=============================================================================
QRNG - Quantum Random Number Generator Client
=============================================================================

PURPOSE:
--------
Provides TRUE quantum randomness from the ANU Quantum Random Number Generator.
This is used to seed AES keys and generate OTP keys, ensuring that our
cryptographic keys cannot be predicted even by quantum computers.

WHY QUANTUM RANDOMNESS MATTERS:
-------------------------------
Classical PRNGs (even CSPRNGs) are deterministic - given the internal state,
all future outputs can be predicted. Quantum randomness is fundamentally
unpredictable due to quantum mechanics (measurement of quantum vacuum fluctuations).

For Qmail, this means:
- AES session keys are truly random, not derived from predictable seeds
- OTP keys have maximum entropy (required for perfect secrecy)
- An attacker cannot predict keys even with unlimited compute power

ANU QRNG API:
-------------
Uses the Australian National University's Quantum Random Number Generator:
https://qrng.anu.edu.au/

The API measures quantum vacuum fluctuations using specialized hardware
to generate true random numbers.

FALLBACK STRATEGY:
------------------
If QRNG is unavailable (network issues, rate limits), we fall back to
the OS CSPRNG (secrets.token_bytes). This is still cryptographically
secure but not quantum-random.

USAGE:
------
    from qmail.crypto.qrng import QrngClient

    client = QrngClient()
    random_bytes = client.get_bytes(32)  # 32 bytes of quantum randomness
"""

from __future__ import annotations

import secrets
from typing import List, Optional

import requests

from qmail.config import QrngConfig


class QrngError(Exception):
    """Base exception for QRNG-related errors."""
    pass


class QrngConnectionError(QrngError):
    """Raised when unable to connect to QRNG API."""
    pass


class QrngResponseError(QrngError):
    """Raised when QRNG API returns an unexpected response."""
    pass


class QrngClient:
    """
    Client for the ANU Quantum Random Number Generator API.

    Provides quantum-random bytes for cryptographic key generation.
    Automatically falls back to OS CSPRNG if quantum source is unavailable.

    Attributes:
        _config: Configuration including API URL and optional API key.
        _fallback_count: Number of times fallback was used (for monitoring).
    
    Thread Safety:
        This client is thread-safe. Each call to get_bytes() is independent.
    """

    # API limits
    MAX_BYTES_PER_REQUEST = 1024
    REQUEST_TIMEOUT_SECONDS = 5

    def __init__(self, config: Optional[QrngConfig] = None) -> None:
        """
        Initialize the QRNG client.

        Args:
            config: Optional QrngConfig with API URL and credentials.
                   Uses default ANU endpoint if not provided.
        """
        self._config = config or QrngConfig()
        self._fallback_count = 0

    def get_bytes(self, n: int) -> bytes:
        """
        Get `n` random bytes, preferring quantum randomness.

        This method NEVER fails - if QRNG is unavailable, it falls back
        to the OS CSPRNG (cryptographically secure, but not quantum-random).

        Args:
            n: Number of random bytes to generate (must be > 0).

        Returns:
            `n` bytes of random data.

        Raises:
            ValueError: If n <= 0.

        Example:
            >>> client = QrngClient()
            >>> key = client.get_bytes(32)  # 256-bit key
            >>> len(key)
            32
        """
        if n <= 0:
            raise ValueError(f"Number of bytes must be positive, got {n}")

        try:
            data = self._fetch_quantum_bytes(n)
            return bytes(data)
        except QrngError as e:
            # Fallback to OS CSPRNG (still cryptographically secure)
            self._fallback_count += 1
            return secrets.token_bytes(n)

    def _fetch_quantum_bytes(self, length: int) -> List[int]:
        """
        Fetch quantum-random bytes from ANU QRNG API.

        Handles chunking for requests larger than API limit (1024 bytes).

        Args:
            length: Number of bytes to fetch.

        Returns:
            List of integers (0-255) representing random bytes.

        Raises:
            QrngConnectionError: If unable to reach QRNG API.
            QrngResponseError: If API returns malformed data.
        """
        # Handle requests larger than API limit by chunking
        if length > self.MAX_BYTES_PER_REQUEST:
            result: List[int] = []
            remaining = length
            while remaining > 0:
                chunk_size = min(self.MAX_BYTES_PER_REQUEST, remaining)
                result.extend(self._fetch_single_chunk(chunk_size))
                remaining -= chunk_size
            return result
        
        return self._fetch_single_chunk(length)

    def _fetch_single_chunk(self, length: int) -> List[int]:
        """
        Fetch a single chunk of quantum-random bytes (≤1024 bytes).

        Args:
            length: Number of bytes to fetch (must be ≤ MAX_BYTES_PER_REQUEST).

        Returns:
            List of integers (0-255).

        Raises:
            QrngConnectionError: Network-related errors.
            QrngResponseError: API response errors.
        """
        try:
            params = {"length": length, "type": "uint8"}
            resp = requests.get(
                self._config.base_url,
                params=params,
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            payload = resp.json()

            # Validate response structure
            if "data" not in payload:
                raise QrngResponseError("QRNG response missing 'data' field")

            data = payload["data"]
            if not isinstance(data, list):
                raise QrngResponseError(f"Expected list, got {type(data).__name__}")

            if len(data) != length:
                raise QrngResponseError(
                    f"Expected {length} bytes, got {len(data)}"
                )

            # Validate each byte is in valid range
            result = []
            for i, x in enumerate(data):
                if not isinstance(x, (int, float)) or not (0 <= int(x) <= 255):
                    raise QrngResponseError(f"Invalid byte value at index {i}: {x}")
                result.append(int(x))

            return result

        except requests.Timeout:
            raise QrngConnectionError(
                f"QRNG API timed out after {self.REQUEST_TIMEOUT_SECONDS}s"
            )
        except requests.ConnectionError as e:
            raise QrngConnectionError(f"Failed to connect to QRNG API: {e}")
        except requests.HTTPError as e:
            raise QrngResponseError(f"QRNG API HTTP error: {e.response.status_code}")
        except ValueError as e:
            raise QrngResponseError(f"Failed to parse QRNG response: {e}")

    @property
    def fallback_count(self) -> int:
        """Number of times fallback to OS CSPRNG was used."""
        return self._fallback_count
