import pytest
from fastapi.testclient import TestClient

import qmail.api as api

client = TestClient(api.app)


class DummyStorage:
    def __init__(self):
        pass

    def save_encrypted_email(self, **kwargs):
        return None


def _fake_get_user_storage(token: str):
    # Return a dummy storage and an example user email (bypass Google calls)
    return (DummyStorage(), "alice@example.com")


def test_keys_kem_requires_auth_header():
    resp = client.get("/keys/kem/alice@example.com")
    assert resp.status_code == 401
    assert "Missing authorization header" in resp.json().get("detail", "")


def test_encrypted_send_rejects_plaintext_sessionkey_for_pqc(monkeypatch):
    # Monkeypatch token validator and storage so request is accepted up to validation
    monkeypatch.setattr(api, "_get_user_storage", lambda token: (DummyStorage(), "sender@example.com"))
    monkeypatch.setattr(api, "_get_storage", lambda: DummyStorage())

    payload = {
        "recipient": "bob@example.com",
        "subject": "test",
        "encrypted_content_hex": "deadbeef",
        # plaintext-looking session key (not KEM_MAGIC) — should be rejected for pqc
        "session_key_hex": "cafebabecafebabecafebabe",
        "key_exchange_algorithm": "pqc",
    }

    headers = {"Authorization": "Bearer faketoken"}
    resp = client.post("/encrypted/send", json=payload, headers=headers)
    assert resp.status_code == 400
    assert "forbidden" in resp.json().get("detail", "").lower()


def test_logout_revokes_token(monkeypatch):
    # Ensure delete_token is a no-op (keyring not required for this unit test)
    monkeypatch.setattr(api, "_OAUTH_STORE", api._OAUTH_STORE)

    headers = {"Authorization": "Bearer faketoken"}
    resp = client.post("/auth/logout", headers=headers)
    assert resp.status_code == 200
    # Token should be in the in-memory revocation list
    assert api._is_token_revoked("faketoken") is True

    # _get_user_storage should now reject the revoked token early
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        api._get_user_storage("faketoken")
    assert exc.value.status_code == 401


def test_derive_email_key_is_deterministic_and_conversation_specific():
    k1 = api._derive_email_key("u@example.com", "alice@example.com", "bob@example.com", "Hello")
    k2 = api._derive_email_key("u@example.com", "alice@example.com", "bob@example.com", "Hello")
    assert k1 == k2

    # Different recipient -> different derived key
    k3 = api._derive_email_key("u@example.com", "alice@example.com", "carol@example.com", "Hello")
    assert k1 != k3


def test_revoke_uses_redis_when_available(monkeypatch):
    calls = {}

    class DummyRedisSync:
        def __init__(self):
            self.store = {}
        def setex(self, key, ttl, val):
            calls['setex'] = (key, ttl, val)
            self.store[key] = val
        def exists(self, key):
            return 1 if key in self.store else 0

    dummy = DummyRedisSync()
    monkeypatch.setattr(api, '_REDIS_SYNC', dummy)

    # Revoke token should call Redis.setex
    api._revoke_token('redis-token', ttl_seconds=60)
    assert 'setex' in calls
    assert calls['setex'][0] == 'revoked:redis-token'

    # _is_token_revoked should query Redis.exists
    assert api._is_token_revoked('redis-token') is True

    # Cleanup: remove monkeypatch
    monkeypatch.setattr(api, '_REDIS_SYNC', None)


def test_derive_email_key_requires_argon2_and_is_deterministic():
    # Module enforces Argon2-only; environment must have argon2-cffi installed.
    assert api._HAS_ARGON2 is True

    k1 = api._derive_email_key("u@example.com", "alice@example.com", "bob@example.com", "Hello")
    k2 = api._derive_email_key("u@example.com", "alice@example.com", "bob@example.com", "Hello")
    assert isinstance(k1, (bytes, bytearray)) and len(k1) == 32
    assert k1 == k2

    # Different recipient -> different derived key
    k3 = api._derive_email_key("u@example.com", "alice@example.com", "carol@example.com", "Hello")
    assert k1 != k3
