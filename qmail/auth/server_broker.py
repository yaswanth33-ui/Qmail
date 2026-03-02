"""
=============================================================================
Server Broker Authentication (WhatsApp-style Message Queuing)
=============================================================================

This module handles authentication to the centralized message broker server
that implements WhatsApp-style message delivery.

WHY A MESSAGE BROKER:
---------------------
Unlike traditional email (store-and-forward on mail servers), Qmail uses
a WhatsApp-style architecture:

    SENDER                BROKER SERVER              RECIPIENT
    ──────                ─────────────              ─────────
    1. Encrypt message
    2. Upload to broker   ──→ Queue message
                              (pending_messages)
                                                     3. Poll for messages
                          ←──                        4. Download message
                          5. Delete on               
                             acknowledgment
                                                     6. Store locally

Benefits:
- End-to-end encryption (server never sees plaintext)
- Simple delivery confirmation (sent → delivered → read)
- Real-time delivery without polling mail servers
- Works across different email providers

AUTHENTICATION:
---------------
The broker requires authentication for all operations:
- Uploading messages
- Downloading messages
- Acknowledging receipt

Supported methods:
1. Bearer Token (OAuth2-style)
2. Client Certificate (mTLS)
3. API Key

All credentials stored in OS keychain (not config files).

USAGE:
------
    from qmail.auth.server_broker import BrokerAuthClient, BrokerKeychainStore

    # Initialize client
    client = BrokerAuthClient(
        broker_id="prod-broker",
        base_url="https://broker.qmail.com",
        auth_type="bearer",
    )

    # Authenticate with token
    client.set_token("access-token-from-login")

    # Make authenticated requests
    response = client.post("/messages", json={"recipient": "...", ...})
    pending = client.get("/messages/pending")
"""


from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Optional, Dict, Any
import time

import keyring
import requests


BROKER_KEYRING_SERVICE = "qmail-broker"


@dataclass
class BrokerToken:
    """Represents an authenticated session token."""
    access_token: str
    token_type: str = "Bearer"
    expires_at: Optional[float] = None
    refresh_token: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 30s safety margin)."""
        if self.expires_at is None:
            return False
        return time.time() >= (self.expires_at - 30)


class BrokerKeychainStore:
    """Secure storage for server broker credentials in OS keyring."""

    def save_token(self, broker_id: str, token: BrokerToken) -> None:
        """Store broker authentication token securely."""
        payload = {
            "access_token": token.access_token,
            "token_type": token.token_type,
            "expires_at": token.expires_at,
            "refresh_token": token.refresh_token,
        }
        keyring.set_password(
            BROKER_KEYRING_SERVICE,
            broker_id,
            repr(payload)
        )

    def load_token(self, broker_id: str) -> Optional[BrokerToken]:
        """Retrieve broker authentication token from keyring."""
        raw = keyring.get_password(BROKER_KEYRING_SERVICE, broker_id)
        if not raw:
            return None
        try:
            payload: Dict[str, Any] = ast.literal_eval(raw)
            return BrokerToken(
                access_token=payload["access_token"],
                token_type=payload.get("token_type", "Bearer"),
                expires_at=payload.get("expires_at"),
                refresh_token=payload.get("refresh_token"),
            )
        except Exception:
            return None

    def delete_token(self, broker_id: str) -> None:
        """Remove broker token from keyring."""
        try:
            keyring.delete_password(BROKER_KEYRING_SERVICE, broker_id)
        except keyring.errors.PasswordDeleteError:
            pass


class BrokerAuthClient:
    """
    Authenticated client for WhatsApp-style server message broker.
    
    Handles:
    - Token persistence in OS keyring
    - Token refresh (if supported by broker)
    - Multiple authentication methods (Bearer, mTLS, API key)
    """

    def __init__(
        self,
        broker_id: str,
        base_url: str,
        auth_type: str = "bearer",
        token_id: Optional[str] = None,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
        verify_tls: bool = True,
        store: Optional[BrokerKeychainStore] = None,
    ) -> None:
        self._broker_id = broker_id  # Unique identifier for this broker
        self._base_url = base_url.rstrip("/")
        self._auth_type = auth_type
        self._token_id = token_id  # Keyring key for bearer token
        self._cert_path = cert_path
        self._key_path = key_path
        self._verify_tls = verify_tls
        self._store = store or BrokerKeychainStore()
        self._token: Optional[BrokerToken] = None

    def authenticate(self, auth_code: str) -> BrokerToken:
        """
        Exchange auth code for access token.
        
        Args:
            auth_code: Authorization code from broker login
            
        Returns:
            BrokerToken with access_token and expiry
        """
        if self._auth_type == "bearer" and self._token_id:
            # For bearer token, we assume the auth_code IS the token
            # In production, exchange auth_code at broker's /auth endpoint
            self._token = BrokerToken(
                access_token=auth_code,
                expires_at=time.time() + 3600,  # 1 hour default
            )
            self._store.save_token(self._broker_id, self._token)
            return self._token
        else:
            raise NotImplementedError(f"Authentication method {self._auth_type} not implemented")

    def refresh_token(self) -> Optional[BrokerToken]:
        """
        Attempt to refresh expired token.
        
        Returns:
            New BrokerToken if successful, None if not supported
        """
        current_token = self._store.load_token(self._broker_id)
        if not current_token or not current_token.refresh_token:
            return None
        
        try:
            url = f"{self._base_url}/auth/refresh"
            response = requests.post(
                url,
                json={"refresh_token": current_token.refresh_token},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            new_token = BrokerToken(
                access_token=data["access_token"],
                token_type=data.get("token_type", "Bearer"),
                expires_at=time.time() + data.get("expires_in", 3600),
                refresh_token=data.get("refresh_token", current_token.refresh_token),
            )
            self._store.save_token(self._broker_id, new_token)
            self._token = new_token
            return new_token
        except Exception as e:
            return None

    def get_token(self) -> str:
        """Get valid access token, refreshing if needed."""
        # Try loading from cache first
        if self._token and not self._token.is_expired:
            return self._token.access_token
        
        # Try loading from keyring
        self._token = self._store.load_token(self._broker_id)
        if self._token and not self._token.is_expired:
            return self._token.access_token
        
        # Try refreshing
        if self._token and self._token.refresh_token:
            refreshed = self.refresh_token()
            if refreshed:
                return refreshed.access_token
        
        raise RuntimeError(
            f"No valid token for broker {self._broker_id}. "
            "Call authenticate() or configure broker credentials in keyring."
        )

    def _build_headers(self) -> Dict[str, str]:
        """Build headers with authentication."""
        headers: Dict[str, str] = {}
        
        if self._auth_type == "bearer":
            token = self.get_token()
            headers["Authorization"] = f"Bearer {token}"
        
        return headers

    def _build_cert(self) -> Optional[tuple[str, str]]:
        """Build mTLS certificate tuple if configured."""
        if self._cert_path and self._key_path:
            return (self._cert_path, self._key_path)
        return None

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        """Make authenticated GET request to broker."""
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = self._build_headers()
        headers.update(kwargs.pop("headers", {}))
        cert = self._build_cert()
        
        response = requests.get(
            url,
            headers=headers,
            verify=self._verify_tls,
            cert=cert,
            timeout=10,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def post(self, path: str, json_body: Optional[Dict[str, Any]] = None, **kwargs: Any) -> requests.Response:
        """Make authenticated POST request to broker."""
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = self._build_headers()
        headers.update(kwargs.pop("headers", {}))
        cert = self._build_cert()
        
        response = requests.post(
            url,
            json=json_body,
            headers=headers,
            verify=self._verify_tls,
            cert=cert,
            timeout=10,
            **kwargs,
        )
        response.raise_for_status()
        return response
