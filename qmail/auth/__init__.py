"""
Authentication layer for Qmail.

Includes:
- OAuth2 client integrations for email providers (Gmail, Outlook, Yahoo, etc.).
- QKD key manager authentication for ETSI GS QKD 014 REST APIs.

Access/refresh tokens and API secrets are stored in the OS keychain via
the `keyring` library, not in the local database.
"""

