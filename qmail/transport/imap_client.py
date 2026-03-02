from __future__ import annotations

import json
from typing import List, Dict, Any

from imapclient import IMAPClient  # type: ignore[import]

from qmail.config import ImapConfig


class ImapTransport:
    """
    IMAP transport for fetching ciphertext emails.

    This prototype assumes that the email body was produced by
    `SmtpTransport.send_ciphertext` and is a JSON object:
    {
      "ciphertext_hex": "...",
      "mac_hex": "... or null",
      "signature_hex": "... or null"
    }
    """

    def __init__(self, config: ImapConfig) -> None:
        self._config = config

    def fetch_ciphertexts(self, folder: str = "INBOX") -> List[Dict[str, Any]]:
        """
        Fetch ciphertext-bearing messages from the given folder.

        Returns a list of dicts:
        {
          "uid": <int>,
          "from": <str>,
          "to": <str>,
          "subject": <str>,
          "ciphertext": <bytes>,
          "mac": <Optional[bytes]>,
          "signature": <Optional[bytes]>,
        }
        """
        results: List[Dict[str, Any]] = []
        with IMAPClient(self._config.host, port=self._config.port, ssl=self._config.use_ssl) as client:
            client.login(self._config.username, self._config.password)
            client.select_folder(folder)
            uids = client.search(["UNSEEN"])
            if not uids:
                return results

            response = client.fetch(uids, ["RFC822", "BODY[TEXT]", "ENVELOPE"])
            for uid, data in response.items():
                envelope = data.get(b"ENVELOPE")
                body_bytes = data.get(b"BODY[TEXT]", b"")
                try:
                    payload = json.loads(body_bytes.decode("utf-8"))
                except Exception:
                    continue

                ct_hex = payload.get("ciphertext_hex")
                mac_hex = payload.get("mac_hex")
                sig_hex = payload.get("signature_hex")
                if not isinstance(ct_hex, str):
                    continue

                ciphertext = bytes.fromhex(ct_hex)
                mac = bytes.fromhex(mac_hex) if isinstance(mac_hex, str) else None
                signature = bytes.fromhex(sig_hex) if isinstance(sig_hex, str) else None

                from_addr = str(envelope.from_[0].mailbox, "utf-8") + "@" + str(
                    envelope.from_[0].host, "utf-8"
                )
                to_addr = str(envelope.to[0].mailbox, "utf-8") + "@" + str(
                    envelope.to[0].host, "utf-8"
                )
                subject = envelope.subject.decode("utf-8") if envelope.subject else ""

                results.append(
                    {
                        "uid": uid,
                        "from": from_addr,
                        "to": to_addr,
                        "subject": subject,
                        "ciphertext": ciphertext,
                        "mac": mac,
                        "signature": signature,
                    }
                )

        return results

