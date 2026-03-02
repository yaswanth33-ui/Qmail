"""
=============================================================================
LAYER 2: KEY EXCHANGE
=============================================================================

This layer handles secure key establishment between sender and recipient.
The derived session keys are used by Layer 1 (Crypto Primitives) for
message encryption.

PURPOSE:
--------
Before two parties can exchange encrypted messages, they need a SHARED SECRET
KEY. This layer provides two methods for establishing that shared key:

1. BB84 (Quantum Key Distribution - Simulated)
2. PQC KEM (Post-Quantum Cryptography Key Encapsulation)

Both methods are POST-QUANTUM SECURE, meaning they remain secure even
against attacks from quantum computers.

KEY EXCHANGE PROTOCOL:
----------------------
    INITIATOR (Sender)                  RESPONDER (Recipient)
    ------------------                  ---------------------
    1. initiate() → init_message
                                        2. respond(init_message)
                                           → (response_message, session_key)
    3. finalize(response_message)
       → session_key
    
    Both parties now share the same session_key for encryption.

STRATEGIES:
-----------

┌─────────────────────────────────────────────────────────────────────────┐
│  BB84 (Quantum Key Distribution)                                        │
│  ────────────────────────────────                                        │
│  • Based on quantum mechanics (photon polarization)                      │
│  • Information-theoretically secure (laws of physics)                    │
│  • Requires quantum hardware (this is a SIMULATION for development)     │
│  • Any eavesdropping is detectable                                       │
│                                                                          │
│  In production: Would use real QKD hardware or QKD network              │
│  In simulation: Uses classical simulation with same protocol            │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  PQC KEM (Post-Quantum Key Encapsulation Mechanism)                     │
│  ───────────────────────────────────────────────────                     │
│  • Uses ML-KEM-1024 (formerly Kyber1024)                                │
│  • NIST standardized (FIPS 203)                                         │
│  • Computationally secure (lattice problems)                            │
│  • Works over classical networks                                         │
│  • Recommended for production deployment                                 │
└─────────────────────────────────────────────────────────────────────────┘

CHOOSING A STRATEGY:
--------------------
- Use PQC (ML-KEM) for production over classical networks
- Use BB84 when quantum hardware/network is available
- Both can be swapped transparently (same interface)

USAGE:
------
    from qmail.key_exchange import PqcKemKeyExchange, Bb84KeyExchange

    # Using PQC (recommended for production)
    initiator = PqcKemKeyExchange()
    responder = PqcKemKeyExchange()

    init_msg = initiator.initiate()
    response_msg, responder_key = responder.respond(init_msg)
    initiator_key = initiator.finalize(response_msg)

    assert initiator_key.key_bytes == responder_key.key_bytes
    # Both parties now have the same 256-bit session key!
"""

# Re-export main components
from qmail.key_exchange.base import (
    KeyExchange,
    SessionKey,
    KeyExchangeError,
)
from qmail.key_exchange.bb84 import Bb84KeyExchange
from qmail.key_exchange.pqc import PqcKemKeyExchange

__all__ = [
    "KeyExchange",
    "SessionKey",
    "KeyExchangeError",
    "Bb84KeyExchange",
    "PqcKemKeyExchange",
]
