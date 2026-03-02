"""
=============================================================================
LAYER 6: TRANSPORT (Deprecated - Broker-Only Architecture)
=============================================================================

This layer previously handled SMTP/IMAP for traditional email protocols.

Qmail now uses a WhatsApp-style broker architecture exclusively:
- All messages go through the REST API server broker
- Real-time delivery with delivery confirmations
- End-to-end encrypted (server never sees plaintext)
- Handled by Layer 7 (API) and client.py

The server broker approach provides:
1. Better real-time delivery guarantees
2. Simpler key management
3. No dependency on external email providers
4. Built-in delivery tracking and read receipts

SMTP/IMAP support has been removed. All transport is now handled by:
- qmail.client.QmailClient._transmit_to_server() for sending
- qmail.api endpoints (/messages/send, /messages/pending) for broker
"""

__all__ = []
