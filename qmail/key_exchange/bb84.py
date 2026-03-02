from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple

from qmail.key_exchange.base import KeyExchange, SessionKey


def _random_bits(n: int) -> bytes:
    # n bits -> n bytes where only lowest bit in each byte is used
    return os.urandom(n)


def _parity(bits: bytes) -> int:
    return sum(b & 1 for b in bits) % 2


@dataclass
class Bb84KeyExchange(KeyExchange):
    """
    Simplified, classical simulation of BB84 QKD.

    This does NOT model quantum physics but does:
    - Randomly choose bases and bits.
    - Perform classical sifting.
    - Derive a shared key from matching bases.
    """

    _alice_bits: bytes | None = None
    _alice_bases: bytes | None = None
    _bob_bases: bytes | None = None
    _sifted_key: bytes | None = None

    def initiate(self) -> bytes:
        # Alice chooses random bits and bases
        self._alice_bits = _random_bits(256)
        self._alice_bases = _random_bits(256)
        # In real BB84 we would send qubits; here we send bits + bases as a stand-in
        return self._alice_bits + self._alice_bases

    def respond(self, message: bytes) -> Tuple[bytes, SessionKey]:
        half = len(message) // 2
        alice_bits = message[:half]
        alice_bases = message[half:]
        if len(alice_bits) != len(alice_bases):
            raise ValueError("Malformed BB84 message")
        n = len(alice_bits)
        bob_bases = _random_bits(n)
        # Sifting: for positions where bases match, keep the corresponding bit
        sifted = bytearray()
        for i in range(n):
            if (alice_bases[i] & 1) == (bob_bases[i] & 1):
                sifted.append(alice_bits[i] & 1)

        # Very simple privacy amplification: group bits into bytes
        key_bytes = self._bits_to_bytes(sifted)
        self._bob_bases = bob_bases
        self._sifted_key = key_bytes

        # Bob sends his bases to Alice for sifting
        response = bob_bases
        return response, SessionKey(key_bytes=key_bytes)

    def finalize(self, response: bytes) -> SessionKey:
        if self._alice_bits is None or self._alice_bases is None:
            raise ValueError("BB84 initiate must be called first")

        bob_bases = response
        if len(bob_bases) != len(self._alice_bits):
            raise ValueError("Mismatched BB84 response length")

        sifted = bytearray()
        for i in range(len(self._alice_bits)):
            if (self._alice_bases[i] & 1) == (bob_bases[i] & 1):
                sifted.append(self._alice_bits[i] & 1)

        key_bytes = self._bits_to_bytes(sifted)
        self._sifted_key = key_bytes
        return SessionKey(key_bytes=key_bytes)

    @staticmethod
    def _bits_to_bytes(bits: bytearray) -> bytes:
        if not bits:
            raise ValueError("No key material after BB84 sifting")
        # Pack every 8 bits into one byte
        out = bytearray()
        current = 0
        count = 0
        for b in bits:
            current = (current << 1) | (b & 1)
            count += 1
            if count == 8:
                out.append(current)
                current = 0
                count = 0
        if count > 0:
            current <<= 8 - count
            out.append(current)
        # Optionally hash or truncate to 32 bytes
        return bytes(out[:32])

