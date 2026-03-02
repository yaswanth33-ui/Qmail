"""
=============================================================================
QKD Key Manager Authentication (ETSI GS QKD 014)
=============================================================================

This module provides authentication for external QKD (Quantum Key Distribution)
key management systems following the ETSI GS QKD 014 REST API standard.

WHAT IS QKD KEY MANAGEMENT:
---------------------------
In production quantum networks, QKD hardware (single-photon sources, detectors)
is managed by dedicated Key Management Entities (KMEs). These KMEs:
- Control the physical QKD hardware
- Distribute quantum keys to authorized applications
- Track key usage and enforce policies

This module handles authentication TO these KMEs, so our app can request
quantum keys for message encryption.

ETSI GS QKD 014:
----------------
ETSI (European Telecommunications Standards Institute) defines a standard
REST API for QKD key management:
- GET /api/v1/keys/{slave_SAE_ID}/status: Check key availability
- GET /api/v1/keys/{slave_SAE_ID}/enc_keys: Request keys

We implement the authentication layer for accessing these APIs.

AUTHENTICATION METHODS:
-----------------------
1. Bearer Token / API Key
   - Simple token-based auth
   - Token stored in OS keychain

2. Client Certificate (mTLS)
   - Mutual TLS with client certificates
   - Used for high-security deployments
   - Certificates stored as files (paths configured)

USAGE:
------
    from qmail.auth.qkd import QkdClient, QkdAuthConfig, QkdKeychainStore

    # Store API key in keychain
    store = QkdKeychainStore()
    store.save_api_key("my-qkd-key", "secret-api-key-123")

    # Configure client
    config = QkdAuthConfig(
        base_url="https://qkd.example.com/api/v1",
        api_key_id="my-qkd-key",  # References keychain entry
    )

    client = QkdClient(config)

    # Make authenticated requests
    response = client.get("/keys/slave-001/status")
    key_data = client.post("/keys/slave-001/enc_keys", {"number": 1, "size": 256})
"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Optional, Dict, Any

import keyring
import requests


QKD_KEYRING_SERVICE = "qmail-qkd"


@dataclass
class QkdAuthConfig:
    """
    Configuration for ETSI GS QKD 014 key manager authentication.

    This supports two common patterns:
    - API key / bearer token
    - Client certificate authentication (mutual TLS)
    """

    base_url: str
    api_key_id: Optional[str] = None  # keyring entry id for API key / bearer
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None
    verify_tls: bool = True


class QkdKeychainStore:
    """
    Stores QKD API secrets in the OS keychain, not on disk.
    """

    def save_api_key(self, key_id: str, secret: str) -> None:
        keyring.set_password(QKD_KEYRING_SERVICE, key_id, secret)

    def load_api_key(self, key_id: str) -> Optional[str]:
        return keyring.get_password(QKD_KEYRING_SERVICE, key_id)

    def delete_api_key(self, key_id: str) -> None:
        try:
            keyring.delete_password(QKD_KEYRING_SERVICE, key_id)
        except keyring.errors.PasswordDeleteError:
            pass


class QkdClient:
    """
    Minimal ETSI GS QKD 014 REST API client focused on authentication.

    This client prepares authenticated request sessions that other parts
    of the system can use to request keys, check status, etc.
    """

    def __init__(self, config: QkdAuthConfig, store: Optional[QkdKeychainStore] = None) -> None:
        self._config = config
        self._store = store or QkdKeychainStore()

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._config.api_key_id:
            api_key = self._store.load_api_key(self._config.api_key_id)
            if not api_key:
                raise RuntimeError(f"No QKD API key found in keychain for id={self._config.api_key_id}")
            # Depending on QKD deployment, this might be 'X-API-Key' or 'Authorization: Bearer'
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _build_cert(self) -> Optional[tuple[str, str]]:
        if self._config.client_cert_path and self._config.client_key_path:
            return (self._config.client_cert_path, self._config.client_key_path)
        return None

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        url = self._config.base_url.rstrip("/") + "/" + path.lstrip("/")
        headers = self._build_headers()
        headers.update(kwargs.pop("headers", {}))
        cert = self._build_cert()
        resp = requests.get(
            url,
            headers=headers,
            verify=self._config.verify_tls,
            cert=cert,
            timeout=10,
            **kwargs,
        )
        resp.raise_for_status()
        return resp

    def post(self, path: str, json_body: Optional[Dict[str, Any]] = None, **kwargs: Any) -> requests.Response:
        url = self._config.base_url.rstrip("/") + "/" + path.lstrip("/")
        headers = self._build_headers()
        headers.update(kwargs.pop("headers", {}))
        cert = self._build_cert()
        resp = requests.post(
            url,
            json=json_body,
            headers=headers,
            verify=self._config.verify_tls,
            cert=cert,
            timeout=10,
            **kwargs,
        )
        resp.raise_for_status()
        return resp

