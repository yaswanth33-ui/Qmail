from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
import time

import keyring
import requests


OAUTH_KEYRING_SERVICE = "qmail-oauth"


@dataclass
class OAuthProviderConfig:
    name: str
    client_id: str
    client_secret: str
    auth_url: str
    token_url: str
    redirect_uri: str
    scope: str


@dataclass
class OAuthToken:
    access_token: str
    refresh_token: Optional[str]
    expires_at: Optional[float]

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        # Add small safety margin
        return time.time() >= (self.expires_at - 30)


class OAuthKeychainStore:
    """
    Small helper around `keyring` to store OAuth tokens per provider+account.
    """

    def _key(self, provider_name: str, account_id: str) -> str:
        return f"{provider_name}:{account_id}"

    def save_token(self, provider_name: str, account_id: str, token: OAuthToken) -> None:
        payload = {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "expires_at": token.expires_at,
        }
        keyring.set_password(OAUTH_KEYRING_SERVICE, self._key(provider_name, account_id), repr(payload))

    def load_token(self, provider_name: str, account_id: str) -> Optional[OAuthToken]:
        raw = keyring.get_password(OAUTH_KEYRING_SERVICE, self._key(provider_name, account_id))
        if not raw:
            return None
        try:
            payload: Dict[str, Any] = eval(raw, {"__builtins__": {}})  # simple literal eval
            return OAuthToken(
                access_token=payload["access_token"],
                refresh_token=payload.get("refresh_token"),
                expires_at=payload.get("expires_at"),
            )
        except Exception:
            return None

    def delete_token(self, provider_name: str, account_id: str) -> None:
        try:
            keyring.delete_password(OAUTH_KEYRING_SERVICE, self._key(provider_name, account_id))
        except keyring.errors.PasswordDeleteError:
            pass


class OAuthClient:
    """
    Generic OAuth2 client for email providers.

    This class does not implement the interactive browser UI; instead it
    exposes helper methods you can call from a GUI/CLI to:
    - build the authorization URL
    - exchange the authorization code for tokens
    - refresh access tokens when expired
    """

    def __init__(self, config: OAuthProviderConfig, store: Optional[OAuthKeychainStore] = None) -> None:
        self._config = config
        self._store = store or OAuthKeychainStore()

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "response_type": "code",
            "scope": self._config.scope,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        from urllib.parse import urlencode

        return f"{self._config.auth_url}?{urlencode(params)}"

    def exchange_code_for_tokens(self, account_id: str, code: str) -> OAuthToken:
        data = {
            "code": code,
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret,
            "redirect_uri": self._config.redirect_uri,
            "grant_type": "authorization_code",
        }
        try:
            resp = requests.post(self._config.token_url, data=data, timeout=10)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            # Try to get error details from response
            error_msg = f"Token exchange failed: {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg = f"OAuth Error: {error_data.get('error')} - {error_data.get('error_description')}"
            except Exception:
                try:
                    error_msg = e.response.text
                except Exception:
                    pass
            raise Exception(error_msg) from e
        
        token_data = resp.json()
        token = OAuthToken(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=time.time() + token_data.get("expires_in", 0),
        )
        self._store.save_token(self._config.name, account_id, token)
        return token

    def _refresh_token(self, account_id: str, refresh_token: str) -> OAuthToken:
        data = {
            "refresh_token": refresh_token,
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret,
            "grant_type": "refresh_token",
        }
        resp = requests.post(self._config.token_url, data=data, timeout=10)
        resp.raise_for_status()
        token_data = resp.json()
        token = OAuthToken(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", refresh_token),
            expires_at=time.time() + token_data.get("expires_in", 0),
        )
        self._store.save_token(self._config.name, account_id, token)
        return token

    def get_valid_access_token(self, account_id: str) -> str:
        """
        Load an access token from the OS keychain, refreshing if needed.
        """
        token = self._store.load_token(self._config.name, account_id)
        if token is None:
            raise RuntimeError(f"No OAuth token stored for provider={self._config.name}, account={account_id}")
        if token.is_expired:
            if not token.refresh_token:
                raise RuntimeError("Access token expired and no refresh token available")
            token = self._refresh_token(account_id, token.refresh_token)
        return token.access_token

