from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class KeyExchangeMode(str, Enum):
    BB84 = "bb84"
    PQC = "pqc"


class InteropMode(str, Enum):
    QUANTUM_ONLY = "quantum_only"
    HYBRID_FALLBACK = "hybrid_fallback"


@dataclass
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True


@dataclass
class ImapConfig:
    host: str
    port: int
    username: str
    password: str
    use_ssl: bool = True


@dataclass
class QrngConfig:
    base_url: str = "https://qrng.anu.edu.au/API/jsonI.php"
    api_key: Optional[str] = None  # for future quantumnumbers.anu.edu.au usage


@dataclass
class AppConfig:
    key_exchange_mode: KeyExchangeMode = KeyExchangeMode.PQC
    interop_mode: InteropMode = InteropMode.QUANTUM_ONLY
    qrng: QrngConfig = field(default_factory=QrngConfig)


@dataclass
class QkdConfig:
    """
    Configuration for using an external ETSI GS QKD 014 key manager.
    """

    base_url: Optional[str] = None
    api_key_id: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None
    verify_tls: bool = True


