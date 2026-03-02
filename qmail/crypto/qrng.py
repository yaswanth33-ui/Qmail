from __future__ import annotations

import asyncio
import secrets
from typing import List

import requests

from qmail.config import QrngConfig


class QrngClient:
    """
    Client for the ANU Quantum Random Number Generator API.

    Falls back to OS CSPRNG if the QRNG service is unavailable.
    """

    def __init__(self, config: QrngConfig | None = None) -> None:
        self._config = config or QrngConfig()

    def get_bytes(self, n: int) -> bytes:
        """
        Return `n` random bytes, using QRNG when available.
        
        Falls back to os CSPRNG if QRNG service is unavailable.
        """
        try:
            data = self._fetch_uint8_array(n)
            return bytes(data)
        except Exception as e:
            # Fallback to OS CSPRNG (cryptographically secure)
            # Log the fallback for debugging
            print(f"[QRNG] Fallback to OS CSPRNG: {e}")
            return secrets.token_bytes(n)

    def _fetch_uint8_array(self, length: int) -> List[int]:
        """Fetch random bytes from ANU QRNG API."""
        if length <= 0:
            raise ValueError("length must be positive")
        if length > 1024:
            # API limit per call; split requests if needed
            chunks = []
            remaining = length
            while remaining > 0:
                chunk_len = min(1024, remaining)
                chunks.extend(self._fetch_uint8_array(chunk_len))
                remaining -= chunk_len
            return chunks

        try:
            params = {"length": length, "type": "uint8"}
            resp = requests.get(
                self._config.base_url,
                params=params,
                timeout=5  # 5 second timeout
            )
            resp.raise_for_status()
            payload = resp.json()
            
            if "data" not in payload:
                raise RuntimeError("QRNG response missing 'data' field")
            
            data = payload["data"]
            if not isinstance(data, list):
                raise RuntimeError("QRNG 'data' field is not a list")
            
            return [int(x) for x in data]
            
        except requests.Timeout:
            raise TimeoutError("QRNG API request timed out")
        except requests.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to QRNG API: {e}")
        except Exception as e:
            raise RuntimeError(f"QRNG API error: {e}")


