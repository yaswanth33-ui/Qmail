"""
=============================================================================
BB84 - Quantum Key Distribution (Simulated)
=============================================================================

PURPOSE:
--------
Implements the BB84 Quantum Key Distribution protocol for establishing
a shared secret key between two parties. This is a SIMULATION of quantum
mechanics for development purposes.

WHAT IS BB84:
-------------
BB84 (Bennett-Brassard 1984) is the first quantum key distribution protocol.
It uses the quantum mechanical properties of photons to establish a secure key:

1. Quantum bits (qubits) are encoded in photon polarization
2. Measuring a qubit disturbs it (Heisenberg uncertainty)
3. Any eavesdropper necessarily introduces detectable errors
4. Alice and Bob can detect if their channel was compromised

This provides INFORMATION-THEORETIC SECURITY - security based on the laws
of physics, not computational assumptions.

PROTOCOL OVERVIEW:
------------------
    ALICE (Initiator)                    BOB (Responder)
    -----------------                    ---------------
    1. Generate random bits
    2. Choose random bases (⊕ or ⊗)
    3. "Send" polarized photons
    ────────────────────────────────────>
                                         4. Choose random bases
                                         5. Measure photons in chosen bases
    
    <────────────────────────────────────
                                         6. Send Bob's bases (classical)
    
    7. Sift: Keep bits where bases matched
    8. Error estimation (detect eavesdropping)
    9. Privacy amplification → final key

WHY SIMULATION:
---------------
Real BB84 requires:
- Single-photon sources
- Polarization rotators
- Single-photon detectors
- Quantum channel (fiber optic or free space)

For software development, we SIMULATE the quantum protocol:
- Same message flows as real BB84
- Same sifting and key derivation logic
- No actual quantum mechanics (random bits instead of qubits)

When real QKD hardware is available, this simulation can be replaced
with calls to the hardware's API (ETSI QKD 014 standard).

SECURITY NOTE:
--------------
The SIMULATION does NOT provide quantum security guarantees.
It's for development and testing only. In production, use:
- Real QKD hardware, OR
- PQC KEM (PqcKemKeyExchange) which IS cryptographically secure

USAGE:
------
    from qmail.key_exchange import Bb84KeyExchange

    alice = Bb84KeyExchange()
    bob = Bb84KeyExchange()

    # Alice starts
    alice_msg = alice.initiate()

    # Bob responds
    bob_response, bob_key = bob.respond(alice_msg)

    # Alice finalizes
    alice_key = alice.finalize(bob_response)

    # Both have the same key!
    assert alice_key.key_bytes == bob_key.key_bytes
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Tuple

from qmail.key_exchange.base import KeyExchange, SessionKey, KeyExchangeError


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# Number of raw bits to exchange (before sifting ~50% survive)
RAW_BIT_COUNT = 256

# Target session key size in bytes
SESSION_KEY_BYTES = 32


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _generate_random_bits(n: int) -> bytes:
    """
    Generate n random bits (stored as bytes, lowest bit of each byte is the bit).

    In real BB84, these would be quantum-random values that determine
    photon polarization.

    Args:
        n: Number of random bits to generate.

    Returns:
        n bytes, each with random bit in lowest position.
    """
    return os.urandom(n)


def _count_matching_bases(bases_a: bytes, bases_b: bytes) -> int:
    """Count how many bases match between Alice and Bob."""
    return sum(1 for a, b in zip(bases_a, bases_b) if (a & 1) == (b & 1))


# -----------------------------------------------------------------------------
# BB84 Implementation
# -----------------------------------------------------------------------------

@dataclass
class Bb84KeyExchange(KeyExchange):
    """
    Simulated BB84 Quantum Key Distribution.

    This implements the BB84 protocol flow without actual quantum mechanics.
    Use for development/testing or when paired with real QKD hardware.

    Protocol Steps:
        1. Alice generates random bits and bases
        2. Alice sends "qubits" (bits + bases in simulation)
        3. Bob chooses random bases and measures
        4. Bob sends his bases back (classical channel)
        5. Both keep bits where bases matched (sifting)
        6. Both derive session key from sifted bits

    Attributes:
        _alice_bits: Alice's random bits (initiator state)
        _alice_bases: Alice's random bases (initiator state)
        _bob_bases: Bob's random bases (responder state)
        _sifted_key: Final key after sifting

    Thread Safety:
        A single instance should only be used for ONE key exchange.
        Create a new instance for each key exchange.
    """

    # Initiator (Alice) state
    _alice_bits: Optional[bytes] = field(default=None, repr=False)
    _alice_bases: Optional[bytes] = field(default=None, repr=False)

    # Responder (Bob) state
    _bob_bases: Optional[bytes] = field(default=None, repr=False)

    # Final key
    _sifted_key: Optional[bytes] = field(default=None, repr=False)

    def initiate(self) -> bytes:
        """
        Start BB84 key exchange (Alice's side).

        Alice:
        1. Generates random bits (the actual key material)
        2. Generates random bases (⊕ rectilinear or ⊗ diagonal)
        3. In real BB84: Encodes bits as photon polarizations
        4. Sends to Bob (in simulation: bits + bases)

        Returns:
            Message containing Alice's bits and bases.
            Format: [bits (256 bytes) | bases (256 bytes)]

        Raises:
            KeyExchangeError: If already initiated.
        """
        if self._alice_bits is not None:
            raise KeyExchangeError("BB84 already initiated")

        # Generate Alice's random bits and bases
        self._alice_bits = _generate_random_bits(RAW_BIT_COUNT)
        self._alice_bases = _generate_random_bits(RAW_BIT_COUNT)

        # In real BB84: Would send polarized photons (quantum channel)
        # In simulation: Send bits + bases (INSECURE without quantum channel)
        return self._alice_bits + self._alice_bases

    def respond(self, message: bytes) -> Tuple[bytes, SessionKey]:
        """
        Process Alice's message (Bob's side).

        Bob:
        1. Receives Alice's "qubits" (bits + bases in simulation)
        2. Chooses random measurement bases
        3. In real BB84: Measures photons, gets results
        4. Performs sifting: keeps bits where bases matched
        5. Returns his bases so Alice can sift too

        Args:
            message: Alice's initiate() output (bits + bases).

        Returns:
            Tuple of (bob_bases, session_key):
            - bob_bases: Bob's measurement bases (Alice needs for sifting)
            - session_key: The derived 256-bit session key

        Raises:
            KeyExchangeError: If message is malformed.
        """
        # Parse Alice's message
        if len(message) % 2 != 0:
            raise KeyExchangeError("Malformed BB84 message: odd length")

        half = len(message) // 2
        alice_bits = message[:half]
        alice_bases = message[half:]

        if len(alice_bits) < RAW_BIT_COUNT:
            raise KeyExchangeError(
                f"BB84 message too short: expected {RAW_BIT_COUNT} bits"
            )

        # Bob chooses random bases
        bob_bases = _generate_random_bits(len(alice_bits))
        self._bob_bases = bob_bases

        # Sifting: Keep bits where bases match
        sifted_bits = self._sift_bits(alice_bits, alice_bases, bob_bases)

        # Privacy amplification: Compress to 32-byte key
        session_key_bytes = self._amplify_to_key(sifted_bits)
        self._sifted_key = session_key_bytes

        # Return Bob's bases so Alice can perform same sifting
        return bob_bases, SessionKey(key_bytes=session_key_bytes)

    def finalize(self, response: bytes) -> SessionKey:
        """
        Complete BB84 key exchange (Alice's side).

        Alice:
        1. Receives Bob's measurement bases
        2. Performs same sifting as Bob (keep matching bases)
        3. Both now have the same sifted bits
        4. Privacy amplification produces same session key

        Args:
            response: Bob's respond() bases output.

        Returns:
            The session key (identical to Bob's).

        Raises:
            KeyExchangeError: If initiate() wasn't called first.
        """
        if self._alice_bits is None or self._alice_bases is None:
            raise KeyExchangeError("BB84 initiate() must be called first")

        bob_bases = response
        if len(bob_bases) != len(self._alice_bits):
            raise KeyExchangeError(
                f"BB84 response length mismatch: expected {len(self._alice_bits)}, "
                f"got {len(bob_bases)}"
            )

        # Same sifting as Bob
        sifted_bits = self._sift_bits(self._alice_bits, self._alice_bases, bob_bases)

        # Same privacy amplification
        session_key_bytes = self._amplify_to_key(sifted_bits)
        self._sifted_key = session_key_bytes

        return SessionKey(key_bytes=session_key_bytes)

    @staticmethod
    def _sift_bits(bits: bytes, bases_a: bytes, bases_b: bytes) -> bytearray:
        """
        Perform basis sifting: keep bits where measurement bases matched.

        In real BB84, this step discards ~50% of bits on average
        (random basis choices match 50% of the time).

        Args:
            bits: The actual bit values (Alice's)
            bases_a: Alice's basis choices
            bases_b: Bob's basis choices

        Returns:
            Sifted bit array (variable length, ~50% of input)
        """
        sifted = bytearray()
        for i in range(len(bits)):
            # Keep bit only if bases match (lowest bit of each byte)
            if (bases_a[i] & 1) == (bases_b[i] & 1):
                sifted.append(bits[i] & 1)
        return sifted

    @staticmethod
    def _amplify_to_key(sifted_bits: bytearray) -> bytes:
        """
        Privacy amplification: Compress sifted bits to 256-bit key.

        This step compresses the sifted bits and removes any partial
        information an eavesdropper might have obtained.

        In production, this would use a universal hash function.
        Here we use simple bit packing for simulation.

        Args:
            sifted_bits: Sifted bit array from _sift_bits()

        Returns:
            32 bytes (256 bits) of key material

        Raises:
            KeyExchangeError: If not enough sifted bits for a key.
        """
        if len(sifted_bits) < 8:  # Need at least 1 byte
            raise KeyExchangeError(
                f"BB84 sifting produced only {len(sifted_bits)} bits - "
                "not enough for key derivation"
            )

        # Pack bits into bytes
        key_bytes = bytearray()
        current_byte = 0
        bit_count = 0

        for bit in sifted_bits:
            current_byte = (current_byte << 1) | (bit & 1)
            bit_count += 1
            if bit_count == 8:
                key_bytes.append(current_byte)
                current_byte = 0
                bit_count = 0

        # Handle remaining bits
        if bit_count > 0:
            current_byte <<= (8 - bit_count)
            key_bytes.append(current_byte)

        # Truncate or pad to exactly 32 bytes
        if len(key_bytes) >= SESSION_KEY_BYTES:
            return bytes(key_bytes[:SESSION_KEY_BYTES])
        else:
            # Pad with zeros (in production: use key derivation function)
            return bytes(key_bytes) + bytes(SESSION_KEY_BYTES - len(key_bytes))

