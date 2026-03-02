from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import (
    BLOB,
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    select,
    insert,
    delete,
)
from sqlalchemy.engine import Engine

from qmail.models import EmailEnvelope, EncryptionMode, Contact


metadata = MetaData()

emails_table = Table(
    "emails",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("sender", String, nullable=False),
    Column("recipient", String, nullable=False),
    Column("subject", String, nullable=False),
    Column("ciphertext", BLOB, nullable=False),
    Column("mac", BLOB, nullable=True),
    Column("signature", BLOB, nullable=True),
    Column("signature_algorithm", String, nullable=True),
    Column("sent_at", DateTime, nullable=False),
    Column("view_once", Boolean, nullable=False, default=False),
    Column("key_exchange_mode", String, nullable=False),
    Column("encryption_mode", String, nullable=False),
    Column("folder", String, nullable=False, default="Inbox"),  # "Inbox", "Sent", "Drafts", "Trash"
)

contacts_table = Table(
    "contacts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String, unique=True, nullable=False),
    Column("display_name", String, nullable=True),
    Column("quantum_capable", Boolean, nullable=False, default=True),
    Column("sig_public_key", BLOB, nullable=True),
    Column("sig_algorithm", String, nullable=True),
)


class Storage:
    """
    Encrypted local storage abstraction.

    NOTE: This stores ciphertext only; key material must be handled separately.
    """

    def __init__(self, db_path: Path) -> None:
        self._engine: Engine = create_engine(f"sqlite:///{db_path}")
        metadata.create_all(self._engine)

    def save_email(self, email: EmailEnvelope) -> int:
        with self._engine.begin() as conn:
            stmt = (
                insert(emails_table)
                .values(
                    sender=email.sender,
                    recipient=email.recipient,
                    subject=email.subject,
                    ciphertext=email.ciphertext,
                    mac=email.mac,
                    signature=email.signature,
                    signature_algorithm=email.signature_algorithm,
                    sent_at=email.sent_at,
                    view_once=email.view_once,
                    key_exchange_mode=email.key_exchange_mode,
                    encryption_mode=email.encryption_mode.value,
                    folder=email.folder,
                )
            )
            result = conn.execute(stmt)
            return int(result.inserted_primary_key[0])

    def list_emails(self) -> Iterable[EmailEnvelope]:
        with self._engine.connect() as conn:
            stmt = select(emails_table).order_by(emails_table.c.sent_at.desc())
            rows = conn.execute(stmt)
            for row in rows:
                yield EmailEnvelope(
                    id=row.id,
                    sender=row.sender,
                    recipient=row.recipient,
                    subject=row.subject,
                    ciphertext=row.ciphertext,
                    mac=row.mac,
                    signature=row.signature,
                    signature_algorithm=row.signature_algorithm,
                    sent_at=row.sent_at,
                    view_once=row.view_once,
                    key_exchange_mode=row.key_exchange_mode,
                    encryption_mode=EncryptionMode(row.encryption_mode),
                    folder=row.folder,
                )

    def get_email(self, email_id: int) -> Optional[EmailEnvelope]:
        with self._engine.connect() as conn:
            stmt = select(emails_table).where(emails_table.c.id == email_id)
            row = conn.execute(stmt).fetchone()
            if row is None:
                return None
            return EmailEnvelope(
                id=row.id,
                sender=row.sender,
                recipient=row.recipient,
                subject=row.subject,
                ciphertext=row.ciphertext,
                mac=row.mac,
                signature=row.signature,
                signature_algorithm=row.signature_algorithm,
                sent_at=row.sent_at,
                view_once=row.view_once,
                key_exchange_mode=row.key_exchange_mode,
                encryption_mode=EncryptionMode(row.encryption_mode),
                folder=row.folder,
            )

    def delete_email(self, email_id: int) -> bool:
        """
        Permanently delete an email row by ID.

        Returns True if a row was deleted, False if no such ID existed.
        """
        with self._engine.begin() as conn:
            stmt = delete(emails_table).where(emails_table.c.id == email_id)
            result = conn.execute(stmt)
            return result.rowcount > 0

    # Contact / signature key management

    def upsert_contact(
        self,
        email: str,
        display_name: Optional[str],
        quantum_capable: bool,
        sig_public_key: Optional[bytes],
        sig_algorithm: Optional[str],
    ) -> int:
        """
        Create or update a contact record and return its ID.
        """
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(contacts_table).where(contacts_table.c.email == email)
            ).fetchone()
            if existing:
                conn.execute(
                    contacts_table.update()
                    .where(contacts_table.c.id == existing.id)
                    .values(
                        display_name=display_name,
                        quantum_capable=quantum_capable,
                        sig_public_key=sig_public_key,
                        sig_algorithm=sig_algorithm,
                    )
                )
                return int(existing.id)

            result = conn.execute(
                contacts_table.insert().values(
                    email=email,
                    display_name=display_name,
                    quantum_capable=quantum_capable,
                    sig_public_key=sig_public_key,
                    sig_algorithm=sig_algorithm,
                )
            )
            return int(result.inserted_primary_key[0])

    def get_contact_by_email(self, email: str) -> Optional[Contact]:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(contacts_table).where(contacts_table.c.email == email)
            ).fetchone()
            if not row:
                return None
            return Contact(
                id=row.id,
                email=row.email,
                display_name=row.display_name,
                quantum_capable=row.quantum_capable,
                sig_public_key=row.sig_public_key,
                sig_algorithm=row.sig_algorithm,
            )

