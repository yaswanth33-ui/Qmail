from __future__ import annotations

from email.message import EmailMessage
import json
from typing import Awaitable, Callable, Optional

import aiosmtplib

from qmail.config import SmtpConfig


OAuthTokenGenerator = Callable[[], Awaitable[str]]


class SmtpTransport:
    """
    SMTP transport for sending ciphertext emails.

    Supports either traditional username/password auth or XOAUTH2 via
    an async `oauth_token_generator` callable.
    """

    def __init__(
        self,
        config: SmtpConfig,
        oauth_token_generator: Optional[OAuthTokenGenerator] = None,
    ) -> None:
        self._config = config
        self._oauth_token_generator = oauth_token_generator

    async def send_ciphertext(
        self,
        sender: str,
        recipient: str,
        subject: str,
        ciphertext: bytes,
        mac_tag: bytes | None = None,
        signature: bytes | None = None,
        session_key: bytes | None = None,
        key_exchange_mode: str = "pqc",
    ) -> None:
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = subject
        # Add Qmail marker headers to identify encrypted emails and key exchange mode
        msg["X-Qmail-Encrypted"] = "true"
        msg["X-Qmail-Key-Exchange"] = key_exchange_mode
        # Represent ciphertext, MAC, signature, and session key in JSON+hex for SMTP-safe transport
        # The session key is needed by the recipient to decrypt the email
        payload_obj = {
            "ciphertext_hex": ciphertext.hex(),
            "mac_hex": mac_tag.hex() if mac_tag is not None else None,
            "signature_hex": signature.hex() if signature is not None else None,
            "session_key_hex": session_key.hex() if session_key is not None else None,
        }
        msg.set_content(json.dumps(payload_obj))

        await aiosmtplib.send(
            msg,
            hostname=self._config.host,
            port=self._config.port,
            username=self._config.username,
            password=None if self._oauth_token_generator is not None else self._config.password,
            start_tls=self._config.use_tls,
            oauth_token_generator=self._oauth_token_generator,
        )

