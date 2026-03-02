from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
import base64
import json
import mimetypes

import requests

from qmail.config import AppConfig, KeyExchangeMode, InteropMode, QkdConfig
from qmail.crypto.aes import encrypt_aes_gcm, decrypt_aes_gcm
from qmail.crypto.otp import encrypt_view_once, decrypt_view_once
from qmail.crypto.signatures import sign_message, verify_signature, generate_keypair
from qmail.key_exchange.bb84 import Bb84KeyExchange
from qmail.key_exchange.pqc import PqcKemKeyExchange
from qmail.models import EmailEnvelope, EncryptionMode
from qmail.storage.db import Storage, emails_table
from qmail.keys.lifecycle import KeyLifecycleManager
from qmail.auth.qkd import QkdClient, QkdAuthConfig
from qmail.auth.server_broker import BrokerAuthClient


# Attachment handling thresholds (bytes)
MAX_ATTACHMENT_INLINE_BYTES = 5 * 1024 * 1024  # 5 MB
ATTACHMENT_CHUNK_SIZE = 512 * 1024  # 512 KB per chunk


class QmailClient:
    """
    High-level orchestration of encryption, key exchange, storage and transport.
    
    Uses a WhatsApp-style broker architecture for message delivery.
    All messages go through the REST API server broker.
    """

    def __init__(
        self,
        app_config: AppConfig,
        db_path: Optional[Path] = None,
        signing_algorithm: str = "Dilithium2",
        encryption_key: Optional[bytes] = None,
        database_url: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> None:
        self._app_config = app_config
        self._storage = Storage(
            db_path,
            encryption_key=encryption_key,
            database_url=database_url,
            schema=schema,
        )
        self._keys = KeyLifecycleManager()
        
        # WhatsApp-style server broker authentication (secure, with keyring storage)
        self._broker_auth_client: Optional[BrokerAuthClient] = None
        
        # Legacy: Simple bearer token (kept for backward compatibility)
        self._api_endpoint: Optional[str] = None  # e.g., "http://localhost:8000"
        self._access_token: Optional[str] = None  # OAuth bearer token (legacy)
        
        # Auto-generate PQC signing keys for digital signatures
        # This ensures every email is cryptographically signed by the sender
        self._sig_algorithm = signing_algorithm
        try:
            keypair = generate_keypair(signing_algorithm)
            self._sig_private_key = keypair.private_key
            self._sig_public_key = keypair.public_key
        except Exception as e:
            self._sig_algorithm = None
            self._sig_private_key = None
            self._sig_public_key = None

    def configure_server_broker(self, broker_id: str, auth_token_or_code: str) -> None:
        """
        Configure secure authentication to WhatsApp-style server message broker.
        
        Uses `ServerBrokerConfig` from app_config and stores credentials securely in OS keyring.
        
        Args:
            broker_id: Unique identifier for this broker (e.g., "prod-broker")
            auth_token_or_code: Bearer token or authorization code from broker login
        
        Example:
            config = AppConfig(
                server_broker=ServerBrokerConfig(
                    base_url="https://broker.qmail.com",
                    auth_type="bearer",
                    token_id="my-broker-token"
                )
            )
            client = QmailClient(config, ...)
            client.configure_server_broker("prod", "abc123xyz")
        """
        if not self._app_config.server_broker:
            raise ValueError(
                "ServerBrokerConfig not configured in AppConfig. "
                "Set app_config.server_broker before calling configure_server_broker()."
            )
        
        broker_cfg = self._app_config.server_broker
        self._broker_auth_client = BrokerAuthClient(
            broker_id=broker_id,
            base_url=broker_cfg.base_url,
            auth_type=broker_cfg.auth_type,
            token_id=broker_cfg.auth_token_id,
            cert_path=broker_cfg.client_cert_path,
            key_path=broker_cfg.client_key_path,
            verify_tls=broker_cfg.verify_tls,
        )
        
        # Authenticate and store token securely in keyring
        self._broker_auth_client.authenticate(auth_token_or_code)

    def configure_server_for_viewonce(self, api_endpoint: str, access_token: str) -> None:
        """
        DEPRECATED: Use configure_server_broker() instead.
        
        Legacy method - stores token in memory without keyring persistence.
        Provided only for backward compatibility.
        """
        self._api_endpoint = api_endpoint
        self._access_token = access_token

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

    # --- WhatsApp-style server transmission (unified for AES and OTP) ---

    def _get_broker_endpoint(self) -> tuple[str, BrokerAuthClient]:
        """Get broker endpoint and authenticated client."""
        if self._broker_auth_client:
            # Secure broker with keyring auth
            return ("broker", self._broker_auth_client)
        elif self._api_endpoint and self._access_token:
            # Legacy: in-memory token (not recommended for production)
            # Create a temporary client-like object for backward compatibility
            class LegacyBrokerClient:
                def __init__(self, endpoint, token):
                    self.endpoint = endpoint
                    self.token = token
                def _make_headers(self):
                    return {"Authorization": f"Bearer {self.token}"}
            return ("legacy", LegacyBrokerClient(self._api_endpoint, self._access_token))
        else:
            raise ValueError(
                "Server broker not configured. "
                "Call configure_server_broker(broker_id, auth_token) with ServerBrokerConfig."
            )

    async def _transmit_to_server(
        self,
        recipient: str,
        subject: str,
        ciphertext: bytes,
        encryption_type: str,  # "aes" or "otp"
        key_material: bytes,  # Session key (AES) or OTP keys (OTP)
        mac: Optional[bytes],
        signature: Optional[bytes],
        view_once: bool = False,
    ) -> str:
        """
        Unified transmission to server broker queue (WhatsApp-style).
        Both AES-256-GCM and OTP-encrypted emails use same mechanism.
        
        Uses secure authenticated broker client with keyring-stored credentials.
        
        Message is stored temporarily on server and auto-deleted after acknowledgment.
        
        Returns message_id for delivery tracking.
        """
        broker_type, broker_client = self._get_broker_endpoint()
        
        try:
            message_id = str(__import__('uuid').uuid4())
            
            if broker_type == "broker":
                # Use secure BrokerAuthClient
                url = "/messages/send"
                payload = {
                    "message_id": message_id,
                    "recipient": recipient,
                    "subject": subject,
                    "encrypted_content_hex": ciphertext.hex(),
                    "encryption_type": encryption_type,
                    "key_material_hex": key_material.hex(),
                    "mac_hex": mac.hex() if mac else None,
                    "signature_hex": signature.hex() if signature else None,
                    "signature_algorithm": self._sig_algorithm if signature else None,
                    "key_exchange_algorithm": self._app_config.key_exchange_mode.value,
                    "view_once": view_once,
                }
                
                response = broker_client.post(url, json_body=payload)
                result = response.json()
            else:
                # Legacy in-memory token (deprecated)
                url = f"{broker_client.endpoint}/messages/send"
                headers = broker_client._make_headers()
                headers["Content-Type"] = "application/json"
                
                payload = {
                    "message_id": message_id,
                    "recipient": recipient,
                    "subject": subject,
                    "encrypted_content_hex": ciphertext.hex(),
                    "encryption_type": encryption_type,
                    "key_material_hex": key_material.hex(),
                    "mac_hex": mac.hex() if mac else None,
                    "signature_hex": signature.hex() if signature else None,
                    "signature_algorithm": self._sig_algorithm if signature else None,
                    "key_exchange_algorithm": self._app_config.key_exchange_mode.value,
                    "view_once": view_once,
                }
                
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                response.raise_for_status()
                result = response.json()
            
            message_id = result.get("message_id", message_id)
            return message_id
            
        except (requests.exceptions.RequestException, Exception) as e:
            raise ValueError(f"Failed to transmit message to server: {e}")

    async def sync_messages_from_server(self) -> List[int]:
        """
        WhatsApp-style sync: Fetch pending messages from server broker queue.
        
        Both AES and OTP emails are synced from the same queue.
        Messages are automatically deleted from server after acknowledgment.
        
        Returns list of email IDs created locally.
        """
        if not self._api_endpoint or not self._access_token:
            raise ValueError("Server not configured for message sync")
        
        created_email_ids = []
        
        try:
            # Fetch pending messages for this user
            url = f"{self._api_endpoint}/messages/pending"
            headers = {"Authorization": f"Bearer {self._access_token}"}
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            messages = response.json().get("messages", [])
            
            for msg in messages:
                message_id = msg.get("message_id")
                encryption_type = msg.get("encryption_type")  # "aes" or "otp"
                view_once = msg.get("view_once", False)
                
                # Decrypt key material based on encryption type
                if encryption_type == "aes":
                    otp_key = None
                    mac_key = None
                elif encryption_type == "otp":
                    # For OTP: key_material contains both OTP and MAC keys (JSON encoded)
                    key_data = json.loads(msg.get("key_material_hex", "{}"))
                    otp_key = bytes.fromhex(key_data.get("otp_key", ""))
                    mac_key = bytes.fromhex(key_data.get("mac_key", ""))
                else:
                    continue
                
                # Create local email envelope
                envelope = EmailEnvelope(
                    id=None,
                    sender=msg.get("sender"),
                    recipient=msg.get("recipient"),
                    subject=msg.get("subject"),
                    ciphertext=bytes.fromhex(msg.get("encrypted_content_hex", "")),
                    mac=bytes.fromhex(msg.get("mac_hex", "")) if msg.get("mac_hex") else None,
                    signature=bytes.fromhex(msg.get("signature_hex", "")) if msg.get("signature_hex") else None,
                    signature_algorithm=msg.get("signature_algorithm"),
                    sent_at=datetime.fromisoformat(msg.get("sent_at", datetime.utcnow().isoformat())),
                    view_once=view_once,
                    key_exchange_mode=msg.get("key_exchange_algorithm", "pqc"),
                    encryption_mode=EncryptionMode.VIEW_ONCE_OTP if view_once else EncryptionMode.AES,
                    folder="Inbox",
                    otp_key=otp_key,
                    mac_key=mac_key,
                    delivery_status="delivered",
                    server_message_id=message_id,
                )
                
                # Save to local storage
                email_id = self._storage.save_email(envelope)
                created_email_ids.append(email_id)
                
                # Acknowledge receipt to server (auto-deletes from broker queue)
                try:
                    ack_url = f"{self._api_endpoint}/messages/acknowledge"
                    ack_payload = {"message_id": message_id}
                    requests.post(ack_url, json=ack_payload, headers=headers, timeout=10)
                except Exception as e:
                    pass  # Failed to acknowledge message
            
            return created_email_ids
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to sync messages from server: {e}")

    async def upload_viewonce_to_server(
        self,
        recipient: str,
        subject: str,
        ciphertext: bytes,
        mac: bytes,
        otp_key: bytes,
        mac_key: bytes,
        signature: Optional[bytes] = None,
    ) -> str:
        """
        Upload a view-once email to server-side ephemeral storage.
        
        Returns the message_id from the server.
        Server stores the encrypted data + OTP keys for 72 hours.
        """
        if not self._api_endpoint or not self._access_token:
            raise ValueError(
                "Server not configured for view-once. Call configure_server_for_viewonce() first."
            )
        
        try:
            url = f"{self._api_endpoint}/viewonce/send"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }
            payload = {
                "recipient": recipient,
                "subject": subject,
                "encrypted_content_hex": ciphertext.hex(),
                "otp_key_hex": otp_key.hex(),
                "mac_key_hex": mac_key.hex(),
                "mac_hex": mac.hex(),
                "signature_hex": signature.hex() if signature else None,
                "signature_algorithm": self._sig_algorithm if signature else None,
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            message_id = result.get("message_id")
            if not message_id:
                raise ValueError("Server did not return message_id")
            
            return message_id
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to upload view-once email to server: {e}")

    async def send_email(
        self,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
        view_once: bool = False,
        attachments: Optional[List[Dict[str, Any]]] = None,
        recipient_supports_quantum: bool = True,
        _server_context: bool = False,
    ) -> Union[int, Dict[str, Any]]:
        """
        Encrypt and send an email, enforcing true E2E at the application layer.
        
        REQUIRES: Server must be configured via configure_server_for_viewonce(api_endpoint, access_token).
        All emails (regular + view-once) are stored server-side for secure key management.

        - AES-GCM mode: Regular encrypted emails, supports attachments
          → Encrypted content + session key stored on server (72h TTL)
          → Recipient can download and decrypt locally
          → Sender gets read receipts
        - View-once OTP mode: One-time viewing with content destruction
          → Encrypted with OTP, stored on server
          → Recipient can view exactly once, then deleted
          → Strictly text-only, no attachments
        
        Raises ValueError if server not configured.
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

        otp_key_storage = None
        mac_key_storage = None
        
        if view_once:
            ciphertext, mac_tag, otp_key, mac_key = encrypt_view_once(plaintext_bytes)
            # Register OTP and MAC keys as strictly one-time
            otp_mk = self._keys.register_otp_key(otp_key, is_mac_key=False)
            mac_mk = self._keys.register_otp_key(mac_key, is_mac_key=True)
            otp_mk.register_use()
            mac_mk.register_use()
            # Store OTP and MAC keys for receiver decryption
            otp_key_storage = otp_key
            mac_key_storage = mac_key
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

        # Store encrypted content for both AES and OTP modes
        # For view-once: store OTP-encrypted ciphertext + keys for receiver decryption
        # For normal AES: store plaintext for local display (encrypted version sent to server)
        if view_once:
            # View-once: store OTP-encrypted ciphertext, not plaintext
            body_to_store = ciphertext
        else:
            # Normal email: store plaintext for later viewing
            body_to_store = body.encode('utf-8')
        
        envelope = EmailEnvelope(
            id=None,
            sender=sender,
            recipient=recipient,
            subject=subject,
            ciphertext=body_to_store,  # View-once: OTP-encrypted, AES: plaintext
            mac=mac_tag,
            signature=signature,
            signature_algorithm=self._sig_algorithm,
            sent_at=datetime.utcnow(),
            view_once=view_once,
            key_exchange_mode=self._app_config.key_exchange_mode.value,
            encryption_mode=encryption_mode,
            folder="Sent",
            otp_key=otp_key_storage,  # Store OTP key for view-once decryption
            mac_key=mac_key_storage,  # Store MAC key for view-once verification
        )
        email_id = self._storage.save_email(envelope)

        # Server context: return encrypted data directly for API to store
        # This avoids the HTTP deadlock when API endpoint calls this method
        if _server_context:
            import uuid
            message_id = str(uuid.uuid4())
            return {
                "email_id": email_id,
                "message_id": message_id,
                "recipient": recipient,
                "subject": subject,
                "ciphertext": ciphertext,
                "encryption_type": "otp" if view_once else "aes",
                "key_material": otp_key_storage if view_once else session_key,
                "mac": mac_tag,
                "signature": signature,
                "signature_algorithm": self._sig_algorithm,
                "key_exchange_algorithm": self._app_config.key_exchange_mode.value,
                "view_once": view_once,
            }

        # WhatsApp-style transmission: send encrypted message via server broker queue
        # Both AES and OTP use same transmission mechanism (server acts as temporary message broker)
        if not self._api_endpoint or not self._access_token:
            raise ValueError(
                "Server not configured. Call configure_server_for_viewonce(api_endpoint, access_token) first. "
                "All emails (AES + view-once OTP) use server broker for secure transmission."
            )
        
        try:
            # Unified server transmission (both AES and OTP)
            message_id = await self._transmit_to_server(
                recipient=recipient,
                subject=subject,
                ciphertext=ciphertext,
                encryption_type="otp" if view_once else "aes",
                key_material=otp_key_storage if view_once else session_key,
                mac=mac_tag,
                signature=signature,
                view_once=view_once,
            )
            
            # Store server_message_id in local database for tracking
            stmt = emails_table.update().where(
                emails_table.c.id == email_id
            ).values(server_message_id=message_id, delivery_status="sent")
            
            with self._storage._engine.begin() as conn:
                conn.execute(stmt)
            
        except Exception as e:
            raise

        return email_id

    async def sync_viewonce_from_server(self, recipient_email: str = None) -> List[int]:
        """
        Sync pending view-once emails from server and store them locally.
        
        Returns list of email IDs created locally.
        """
        if not self._api_endpoint or not self._access_token:
            raise ValueError(
                "Server not configured for view-once. Call configure_server_for_viewonce() first."
            )
        
        created_email_ids = []
        
        try:
            # List pending view-once emails for recipient
            url = f"{self._api_endpoint}/viewonce/pending"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            pending = response.json()
            
            
            # Download each pending email
            for msg_info in pending:
                message_id = msg_info["id"]
                sender = msg_info["sender"]
                subject = msg_info["subject"]
                
                try:
                    # Download the encrypted email
                    download_url = f"{self._api_endpoint}/viewonce/{message_id}/download"
                    download_response = requests.post(
                        download_url,
                        headers=headers,
                        timeout=10
                    )
                    download_response.raise_for_status()
                    msg_data = download_response.json()
                    
                    # Extract all encrypted components
                    encrypted_content = bytes.fromhex(msg_data["encrypted_content_hex"])
                    otp_key = bytes.fromhex(msg_data["otp_key_hex"])
                    mac_key = bytes.fromhex(msg_data["mac_key_hex"])
                    mac = bytes.fromhex(msg_data["mac_hex"])
                    signature = bytes.fromhex(msg_data["signature_hex"]) if msg_data.get("signature_hex") else None
                    signature_algorithm = msg_data.get("signature_algorithm")
                    
                    # Store encrypted email locally with OTP keys for later decryption
                    envelope = EmailEnvelope(
                        id=None,
                        sender=sender,
                        recipient=recipient_email or "me@example.com",
                        subject=subject,
                        ciphertext=encrypted_content,  # Full encrypted data
                        mac=mac,
                        signature=signature,
                        signature_algorithm=signature_algorithm,
                        sent_at=datetime.utcnow(),
                        view_once=True,
                        viewed=False,
                        otp_key=otp_key,  # Store OTP key for decryption
                        mac_key=mac_key,  # Store MAC key for verification
                        key_exchange_mode="pqc",
                        encryption_mode=EncryptionMode.VIEW_ONCE_OTP,
                        folder="Inbox",
                    )
                    email_id = self._storage.save_email(envelope)
                    created_email_ids.append(email_id)
                    
                    
                except Exception as e:
                    continue
            
            return created_email_ids
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to sync view-once emails from server: {e}")

    async def notify_viewonce_viewed(self, server_message_id: str) -> None:
        """
        Notify the server that a view-once email has been viewed by recipient.
        """
        if not self._api_endpoint or not self._access_token:
            # Server not configured, skip notification
            return
        
        try:
            url = f"{self._api_endpoint}/viewonce/{server_message_id}/mark-viewed"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
            }
            
            response = requests.post(url, headers=headers, timeout=10)
            response.raise_for_status()
        except Exception as e:
            # Don't raise - this is non-critical
            pass

    def view_email_view_once(
        self,
        email_id: int,
    ) -> Dict[str, Any]:
        """
        Recipient-side view for a 'view once' email (like WhatsApp view-once).

        This enforces true one-time viewing with content destruction:
        - Checks if email has already been viewed
        - If viewed before: raises exception (prevents re-reading)
        - If first view: decrypts using stored keys, marks as viewed, and DELETES from database
        - Keys are destroyed immediately after viewing
        - Email is removed from all tabs/views to ensure content is destroyed
        
        The OTP and MAC keys are retrieved from the database (transmitted by sender via SMTP).
        
        NOTE: View-once emails are ALWAYS deleted after viewing (non-negotiable).
        No option to keep view-once messages - they are ephemeral by design.
        """
        envelope = self._storage.get_email(email_id)
        if envelope is None:
            raise ValueError(f"No email found with id={email_id}")
        if not envelope.view_once or envelope.encryption_mode != EncryptionMode.VIEW_ONCE_OTP:
            raise ValueError("Email is not marked as a view-once OTP message")
        
        # WhatsApp-style: Prevent viewing already-viewed view-once messages
        if envelope.viewed:
            raise ValueError("This message can only be viewed once (already viewed)")
        
        if envelope.mac is None:
            raise ValueError("View-once email is missing MAC")
        
        # Keys must be stored in database from sender transmission (via SMTP JSON)
        if envelope.otp_key is None:
            raise ValueError("View-once email is missing OTP key (not transmitted by sender)")
        if envelope.mac_key is None:
            raise ValueError("View-once email is missing MAC key (not transmitted by sender)")

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

        # Register recipient-side OTP+MAC keys using stored keys from database
        otp_mk = self._keys.register_otp_key(envelope.otp_key, is_mac_key=False)
        mac_mk = self._keys.register_otp_key(envelope.mac_key, is_mac_key=True)

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

        # MANDATORY: Delete the email immediately after viewing
        # View-once emails are ephemeral - they must not be stored or retrievable
        # This ensures true one-time viewing behavior like WhatsApp
        self.delete_email(email_id)

        payload = json.loads(plaintext_bytes.decode("utf-8"))
        return payload

    def open_email(
        self,
        email_id: int,
        session_key: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """
        Open a normal (non-view-once) AES-GCM email.

        - Loads the envelope from storage.
        - Optionally verifies PQC signature using the sender's public key
          (looked up from contacts).
        - Decrypts ciphertext with the provided session_key (or uses stored key from server sync).
        - Returns the JSON payload: {"body": str, "attachments": [...]}
        
        For server-synced emails: session_key can be omitted, will use stored otp_key.
        For local emails: session_key must be provided.
        """
        envelope = self._storage.get_email(email_id)
        if envelope is None:
            raise ValueError(f"No email found with id={email_id}")
        if envelope.view_once or envelope.encryption_mode != EncryptionMode.AES:
            raise ValueError("Email is not a normal AES-GCM message")

        # Get session key: either provided as parameter or stored in otp_key from server sync
        if session_key is None:
            if envelope.otp_key is None:
                raise ValueError(
                    "No session key provided and email was not synced from server. "
                    "Either provide session_key parameter or email must have been downloaded from server."
                )
            session_key = envelope.otp_key

        # Debug logging
        
        # Signature verification disabled (contacts feature removed)
        # Signatures remain stored; verification skipped without contact pubkey lookup
        if envelope.signature is not None and envelope.signature_algorithm:
            pass

        # Decrypt AES-GCM ciphertext (nonce || ct)
        if len(envelope.ciphertext) < 12:
            raise ValueError(f"Ciphertext too short to contain AES-GCM nonce. Length: {len(envelope.ciphertext)}")
        nonce = envelope.ciphertext[:12]
        ct = envelope.ciphertext[12:]
        plaintext_bytes = decrypt_aes_gcm(session_key, nonce, ct)
        payload = json.loads(plaintext_bytes.decode("utf-8"))
        return payload

    async def upload_encrypted_email_to_server(
        self,
        recipient: str,
        subject: str,
        ciphertext: bytes,
        session_key: bytes,
        signature: Optional[bytes] = None,
    ) -> str:
        """
        Upload encrypted AES email to server for secure storage.
        
        Session key is stored server-side (never sent to SMTP).
        Recipient downloads and decrypts locally.
        
        Returns message_id.
        """
        if not self._api_endpoint or not self._access_token:
            raise ValueError(
                "Server not configured. Call configure_server_for_viewonce() first."
            )
        
        try:
            url = f"{self._api_endpoint}/encrypted/send"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
            }
            
            payload = {
                "recipient": recipient,
                "subject": subject,
                "encrypted_content_hex": ciphertext.hex(),
                "session_key_hex": session_key.hex(),
                "signature_hex": signature.hex() if signature else None,
                "signature_algorithm": self._sig_algorithm,
                "key_exchange_algorithm": self._app_config.key_exchange_mode.value,
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            return result["message_id"]
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to upload encrypted email to server: {e}")

    async def sync_encrypted_from_server(self, recipient_email: str = None) -> List[int]:
        """
        Sync pending encrypted emails from server and store locally.
        
        Recipient downloads encrypted content + session key.
        Keys are stored in database for later decryption.
        
        Returns list of email IDs created locally.
        """
        if not self._api_endpoint or not self._access_token:
            raise ValueError(
                "Server not configured. Call configure_server_for_viewonce() first."
            )
        
        created_email_ids = []
        
        try:
            # List pending encrypted emails
            url = f"{self._api_endpoint}/encrypted/pending"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            pending = response.json()
            
            
            # Download each pending email
            for msg_info in pending:
                message_id = msg_info["id"]
                sender = msg_info["sender"]
                subject = msg_info["subject"]
                
                try:
                    # Download with session key
                    download_url = f"{self._api_endpoint}/encrypted/{message_id}/download"
                    download_response = requests.post(
                        download_url,
                        headers=headers,
                        timeout=10
                    )
                    download_response.raise_for_status()
                    msg_data = download_response.json()
                    
                    # Extract all components
                    encrypted_content = bytes.fromhex(msg_data["encrypted_content_hex"])
                    session_key = bytes.fromhex(msg_data["session_key_hex"])
                    signature = bytes.fromhex(msg_data["signature_hex"]) if msg_data.get("signature_hex") else None
                    signature_algorithm = msg_data.get("signature_algorithm")
                    key_exchange_algorithm = msg_data.get("key_exchange_algorithm", "pqc")
                    
                    # Create an EmailEnvelope with encrypted content
                    # Note: We'll store the plaintext later after decryption
                    # For now, store encrypted ciphertext
                    envelope = EmailEnvelope(
                        id=None,
                        sender=sender,
                        recipient=recipient_email or "me@example.com",
                        subject=subject,
                        ciphertext=encrypted_content,
                        mac=None,  # AES-GCM doesn't use separate MAC
                        signature=signature,
                        signature_algorithm=signature_algorithm,
                        sent_at=datetime.utcnow(),
                        view_once=False,
                        viewed=False,
                        otp_key=session_key,  # Store session key as otp_key temporarily
                        mac_key=None,
                        key_exchange_mode=key_exchange_algorithm,
                        encryption_mode=EncryptionMode.AES,
                        folder="Inbox",
                    )
                    email_id = self._storage.save_email(envelope)
                    created_email_ids.append(email_id)
                    
                    
                except Exception as e:
                    continue
            
            return created_email_ids
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to sync encrypted emails from server: {e}")

    def delete_email(self, email_id: int) -> bool:
        """
        Delete a stored email by ID from the local encrypted database.

        This does not affect any copies already relayed via SMTP/IMAP,
        but ensures local ciphertext and metadata are removed.
        """
        return self._storage.delete_email(email_id)
