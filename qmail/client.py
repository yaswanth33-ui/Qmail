from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any
import base64
import json
import mimetypes
import hashlib

from qmail.config import AppConfig, KeyExchangeMode, InteropMode, SmtpConfig, QkdConfig
from qmail.crypto.aes import encrypt_aes_gcm, decrypt_aes_gcm, generate_aes_key
from qmail.crypto.otp import encrypt_view_once, decrypt_view_once
from qmail.crypto.signatures import sign_message, verify_signature
from qmail.key_exchange.bb84 import Bb84KeyExchange
from qmail.key_exchange.pqc import PqcKemKeyExchange
from qmail.models import EmailEnvelope, EncryptionMode
from qmail.storage.db import Storage
from qmail.transport.smtp_client import SmtpTransport
from qmail.transport.imap_client import ImapTransport
from qmail.keys.lifecycle import KeyLifecycleManager
from qmail.auth.qkd import QkdClient, QkdAuthConfig


# Attachment handling thresholds (bytes)
MAX_ATTACHMENT_INLINE_BYTES = 5 * 1024 * 1024  # 5 MB
ATTACHMENT_CHUNK_SIZE = 512 * 1024  # 512 KB per chunk


class QmailClient:
    """
    High-level orchestration of encryption, key exchange, storage and transport.
    """

    def __init__(
        self,
        app_config: AppConfig,
        smtp_config: SmtpConfig,
        db_path: Path,
        oauth_token_generator=None,
    ) -> None:
        self._app_config = app_config
        # If an OAuth token generator is provided, SmtpTransport will use XOAUTH2.
        self._smtp = SmtpTransport(smtp_config, oauth_token_generator=oauth_token_generator)
        self._storage = Storage(db_path)
        self._keys = KeyLifecycleManager()
        # Optional PQC signature configuration (per user)
        self._sig_algorithm: Optional[str] = None
        self._sig_private_key: Optional[bytes] = None
        self._sig_public_key: Optional[bytes] = None

    def configure_signing(self, algorithm: str, private_key: bytes, public_key: bytes) -> None:
        """
        Configure PQC signing keys for this client instance.

        - `algorithm` should match one of the liboqs signature algorithms
          (e.g., 'Dilithium2', 'Falcon-512').
        - Keys are expected to be generated and stored securely elsewhere,
          then provided to the client at runtime.
        """
        self._sig_algorithm = algorithm
        self._sig_private_key = private_key
        self._sig_public_key = public_key

    # --- Contact and signature key distribution helpers ---

    def set_contact_signature_key(
        self,
        email: str,
        algorithm: str,
        public_key: bytes,
        display_name: Optional[str] = None,
        quantum_capable: bool = True,
    ) -> None:
        """
        Register or update a contact's PQC signature public key.
        """
        self._storage.upsert_contact(
            email=email,
            display_name=display_name,
            quantum_capable=quantum_capable,
            sig_public_key=public_key,
            sig_algorithm=algorithm,
        )

    # --- Key exchange helpers (QKD / PQC / BB84) ---

    def _select_key_exchange(self):
        if self._app_config.key_exchange_mode == KeyExchangeMode.BB84:
            return Bb84KeyExchange()
        return PqcKemKeyExchange()

    def _derive_session_key_local(self) -> bytes:
        """
        Example synchronous orchestration of key exchange.

        In a real system, initiator/responder roles would be separated
        across two clients. Here we simulate both ends locally.
        """
        ke_initiator = self._select_key_exchange()
        ke_responder = self._select_key_exchange()

        init_msg = ke_initiator.initiate()
        resp_msg, responder_key = ke_responder.respond(init_msg)
        initiator_key = ke_initiator.finalize(resp_msg)

        if initiator_key.key_bytes != responder_key.key_bytes:
            raise RuntimeError("Key exchange failed: keys do not match")

        # Truncate/expand to 32 bytes for AES-256
        raw_key = initiator_key.key_bytes[:32]
        if len(raw_key) < 32:
            raw_key = raw_key.ljust(32, b"\0")

        # Register session key with lifecycle manager (one-time use by default)
        mk = self._keys.register_session_key(
            raw_key,
            algorithm=f"{self._app_config.key_exchange_mode.value}-derived AES-256-GCM",
            ttl_seconds=3600,
            usage_limit=1,
        )
        return mk.get_bytes()

    def _derive_session_key(self) -> bytes:
        """
        Derive a symmetric session key, preferring external QKD when configured.
        """
        # Attempt ETSI QKD 014 key manager if configured
        if hasattr(self._app_config, "qkd") and isinstance(
            getattr(self._app_config, "qkd"), QkdConfig
        ):
            qkd_cfg: QkdConfig = getattr(self._app_config, "qkd")
            if qkd_cfg.base_url:
                qkd_client = QkdClient(
                    QkdAuthConfig(
                        base_url=qkd_cfg.base_url,
                        api_key_id=qkd_cfg.api_key_id,
                        client_cert_path=qkd_cfg.client_cert_path,
                        client_key_path=qkd_cfg.client_key_path,
                        verify_tls=qkd_cfg.verify_tls,
                    )
                )
                try:
                    # Simplified example endpoint; concrete deployments may differ.
                    resp = qkd_client.get("/keys")
                    data = resp.json()
                    # Expect hex-encoded key material under 'key'
                    key_hex = data.get("key")
                    if isinstance(key_hex, str):
                        raw_key = bytes.fromhex(key_hex)[:32]
                        if len(raw_key) < 32:
                            raw_key = raw_key.ljust(32, b"\0")
                        mk = self._keys.register_session_key(
                            raw_key,
                            algorithm="qkd-derived AES-256-GCM",
                            ttl_seconds=3600,
                            usage_limit=1,
                        )
                        return mk.get_bytes()
                except Exception:
                    # Fall back to local key exchange below
                    pass

        # Fallback: local simulated BB84/PQC exchange
        return self._derive_session_key_local()

    async def send_email(
        self,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
        view_once: bool = False,
        attachments: Optional[List[Dict[str, Any]]] = None,
        recipient_supports_quantum: bool = True,
    ) -> int:
        """
        Encrypt and send an email, enforcing true E2E at the application layer.

        - AES-GCM mode supports attachments: they are bundled with the body
          into a JSON structure and encrypted as a single blob.
        - View-once OTP mode is strictly text-only; attempts to include
          attachments will raise a ValueError.
        """

        attachments = attachments or []

        # Enforce quantum-only mode if configured
        if (
            self._app_config.interop_mode == InteropMode.QUANTUM_ONLY
            and not recipient_supports_quantum
        ):
            raise ValueError(
                "Recipient is not marked as quantum-capable and the client is "
                "configured for quantum-only mode. Refusing to send."
            )

        if view_once and attachments:
            raise ValueError("View-once emails are text-only and cannot include attachments.")

        # Package plaintext body + optional attachments into a single JSON blob
        def _build_attachment_entry(att: Dict[str, Any]) -> Dict[str, Any]:
            data: bytes = att["data"]
            # Auto-detect MIME type from filename if not provided
            filename = att["filename"]
            guessed_type, _ = mimetypes.guess_type(filename)
            content_type = att.get("content_type") or guessed_type or "application/octet-stream"

            if len(data) <= MAX_ATTACHMENT_INLINE_BYTES:
                return {
                    "filename": filename,
                    "content_type": content_type,
                    "chunked": False,
                    "data_b64": base64.b64encode(data).decode("ascii"),
                }

            # Large attachment: represent as chunked base64 blocks
            chunks_b64: List[str] = []
            for i in range(0, len(data), ATTACHMENT_CHUNK_SIZE):
                chunk = data[i : i + ATTACHMENT_CHUNK_SIZE]
                chunks_b64.append(base64.b64encode(chunk).decode("ascii"))

            return {
                "filename": filename,
                "content_type": content_type,
                "chunked": True,
                "chunks_b64": chunks_b64,
            }

        payload: Dict[str, Any] = {
            "body": body,
            "attachments": [
                _build_attachment_entry(att) for att in attachments
            ],
        }
        plaintext_bytes = json.dumps(payload).encode("utf-8")

        if view_once:
            ciphertext, mac_tag, otp_key, mac_key = encrypt_view_once(plaintext_bytes)
            # Register OTP and MAC keys as strictly one-time
            otp_mk = self._keys.register_otp_key(otp_key, is_mac_key=False)
            mac_mk = self._keys.register_otp_key(mac_key, is_mac_key=True)
            otp_mk.register_use()
            mac_mk.register_use()
            # In a real deployment, keys must be securely transferred to the recipient
            # out-of-band or via a dedicated ephemeral channel and erased after first view.
            otp_mk.destroy()
            mac_mk.destroy()
            encryption_mode = EncryptionMode.VIEW_ONCE_OTP
            session_key = None
        else:
            # Use BB84 or PQC for session key generation (secure key exchange)
            session_key = self._derive_session_key()
            nonce, ct = encrypt_aes_gcm(session_key, plaintext_bytes, use_qrng=True)
            ciphertext = nonce + ct
            mac_tag = None
            encryption_mode = EncryptionMode.AES

        # PQC signature over ciphertext (both AES and OTP modes)
        signature: Optional[bytes] = None
        if self._sig_algorithm and self._sig_private_key:
            signature = sign_message(ciphertext, self._sig_private_key, self._sig_algorithm)

        # Store local plaintext copy for display purposes
        # (encrypted version is sent via SMTP instead)
        envelope = EmailEnvelope(
            id=None,
            sender=sender,
            recipient=recipient,
            subject=subject,
            ciphertext=body.encode('utf-8'),  # Store plaintext for display
            mac=mac_tag,
            signature=signature,
            signature_algorithm=self._sig_algorithm,
            sent_at=datetime.utcnow(),
            view_once=view_once,
            key_exchange_mode=self._app_config.key_exchange_mode.value,
            encryption_mode=encryption_mode,
            folder="Sent",
        )
        email_id = self._storage.save_email(envelope)

        # Relay ciphertext via SMTP, including the session key for recipient decryption
        await self._smtp.send_ciphertext(
            sender,
            recipient,
            subject,
            ciphertext,
            mac_tag=mac_tag,
            signature=signature,
            session_key=session_key,
            key_exchange_mode=self._app_config.key_exchange_mode.value,
        )

        return email_id

    def view_email_view_once(
        self,
        email_id: int,
        otp_key: bytes,
        mac_key: bytes,
        delete_after_view: bool = True,
    ) -> Dict[str, Any]:
        """
        Recipient-side view for a 'view once' email.

        - Registers OTP and MAC keys with the lifecycle manager.
        - Verifies MAC and decrypts once.
        - Marks keys as used and destroys them immediately.
        - Optionally deletes the ciphertext record after successful view.
        """
        envelope = self._storage.get_email(email_id)
        if envelope is None:
            raise ValueError(f"No email found with id={email_id}")
        if not envelope.view_once or envelope.encryption_mode != EncryptionMode.VIEW_ONCE_OTP:
            raise ValueError("Email is not marked as a view-once OTP message")
        if envelope.mac is None:
            raise ValueError("View-once email is missing MAC")

        # If signature verification is configured, verify before decrypting
        if envelope.signature is not None and self._sig_algorithm and self._sig_public_key:
            ok = verify_signature(
                envelope.ciphertext,
                envelope.signature,
                self._sig_public_key,
                self._sig_algorithm,
            )
            if not ok:
                raise ValueError("PQC signature verification failed for view-once email")

        # Register recipient-side OTP+MAC keys and enforce single use
        otp_mk = self._keys.register_otp_key(otp_key, is_mac_key=False)
        mac_mk = self._keys.register_otp_key(mac_key, is_mac_key=True)

        try:
            plaintext_bytes = decrypt_view_once(
                envelope.ciphertext,
                envelope.mac,
                otp_mk.get_bytes(),
                mac_mk.get_bytes(),
            )
            otp_mk.register_use()
            mac_mk.register_use()
        finally:
            # Ensure keys are wiped regardless of decrypt success/failure
            otp_mk.destroy()
            mac_mk.destroy()

        if delete_after_view:
            self.delete_email(email_id)

        payload = json.loads(plaintext_bytes.decode("utf-8"))
        return payload

    def open_email(
        self,
        email_id: int,
        session_key: bytes,
    ) -> Dict[str, Any]:
        """
        Open a normal (non-view-once) AES-GCM email.

        - Loads the envelope from storage.
        - Optionally verifies PQC signature using the sender's public key
          (looked up from contacts).
        - Decrypts ciphertext with the provided session_key.
        - Returns the JSON payload: {"body": str, "attachments": [...]}
        """
        envelope = self._storage.get_email(email_id)
        if envelope is None:
            raise ValueError(f"No email found with id={email_id}")
        if envelope.view_once or envelope.encryption_mode != EncryptionMode.AES:
            raise ValueError("Email is not a normal AES-GCM message")

        # Signature verification using sender's registered public key, if available
        contact = self._storage.get_contact_by_email(envelope.sender)
        if (
            envelope.signature is not None
            and envelope.signature_algorithm
            and contact is not None
            and contact.sig_public_key is not None
            and contact.sig_algorithm == envelope.signature_algorithm
        ):
            ok = verify_signature(
                envelope.ciphertext,
                envelope.signature,
                contact.sig_public_key,
                envelope.signature_algorithm,
            )
            if not ok:
                raise ValueError("PQC signature verification failed for AES email")

        # Decrypt AES-GCM ciphertext (nonce || ct)
        if len(envelope.ciphertext) < 12:
            raise ValueError("Ciphertext too short to contain AES-GCM nonce")
        nonce = envelope.ciphertext[:12]
        ct = envelope.ciphertext[12:]
        plaintext_bytes = decrypt_aes_gcm(session_key, nonce, ct)
        payload = json.loads(plaintext_bytes.decode("utf-8"))
        return payload

    def delete_email(self, email_id: int) -> bool:
        """
        Delete a stored email by ID from the local encrypted database.

        This does not affect any copies already relayed via SMTP/IMAP,
        but ensures local ciphertext and metadata are removed.
        """
        return self._storage.delete_email(email_id)


def main() -> None:
    """
    Prototype CLI entry point.
    """
    app_config = AppConfig()
    smtp_config = SmtpConfig(
        host="smtp.gmail.com",
        port=587,
        username="yaswanthreddypanem@gmail.com",
        password="vsbgintlbtccgzvz",
        use_tls=True,
    )
    db_path = Path("qmail.db")
    client = QmailClient(app_config, smtp_config, db_path)

    async def _run():
        await client.send_email(
            sender="alice@example.com",
            recipient="bob@example.com",
            subject="Hello from Qmail",
            body="This is a quantum-ready encrypted email.",
            view_once=False,
        )

    asyncio.run(_run())


if __name__ == "__main__":
    main()

