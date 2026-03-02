Qmail – Quantum-Ready Secure Email Client
=========================================

Qmail is a prototype end-to-end encrypted email client designed to be **quantum-safe** and to enforce **true application-layer E2E encryption**. All email content is encrypted on the client before transport and decrypted only on the recipient’s client.

### Core Architecture

- **Encryption Layer**
  - Normal emails: AES-GCM using high-entropy keys (optionally seeded with quantum randomness).
  - "View Once" emails: One-Time Pad (OTP) with keys sourced from ANU’s Quantum Random Number Generator (QRNG) API.
- **Key Exchange Layer (Modular)**
  - Option A: Simulated BB84 QKD between sender/receiver to derive a shared symmetric session key.
  - Option B: Post-Quantum Cryptography (PQC), e.g. lattice-based KEM (via liboqs / similar).
  - Pluggable interface so key exchange strategy can be swapped without affecting the rest of the pipeline.
- **Storage Layer**
  - Local encrypted SQLite database for mail and metadata.
  - Optional encrypted backups controlled by the user.
- **Transport Layer**
  - Uses standard email protocols (SMTP/IMAP/POP3).
  - Servers only see ciphertext; no plaintext leaves the client.

### Security Goals

- Stronger than typical ECC-based messengers by avoiding long-term dependence on elliptic-curve assumptions.
- Stronger than provider-based webmail by enforcing **true end-to-end encryption** at the application layer.
- Uses quantum randomness (ANU QRNG) to maximise entropy for keys, especially for OTP "view once" messages.

### Project Layout

```text
qmail/
  __init__.py
  config.py
  models.py
  crypto/
    __init__.py
    aes.py
    otp.py
    qrng.py
  key_exchange/
    __init__.py
    base.py
    bb84.py
    pqc.py
  storage/
    __init__.py
    db.py
    backup.py
  transport/
    __init__.py
    smtp_client.py
    imap_client.py
  client.py
requirements.txt
README.md
```

### Running (Prototype CLI)

1. **Create a virtual environment (recommended).**
2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

3. **Run the prototype client (to be extended with UI):**

```bash
python -m qmail.client
```

### ANU QRNG for OTP / Quantum-Seeding

Qmail uses the ANU Quantum Random Number Generator API (`jsonI.php`) to fetch quantum-generated random bytes:

- Endpoint: `https://qrng.anu.edu.au/API/jsonI.php?length=[n]&type=uint8`
- Response: JSON with `data` array containing random integers in the range 0–255.

For "view once" messages we:

- Request enough random bytes to cover the plaintext length.
- XOR plaintext with the QRNG key to generate ciphertext.
- Store only the ciphertext; the key is held in memory for a single viewing and then securely erased.

### Disclaimer

This is a **research/prototype client**. It demonstrates architecture and integration of crypto primitives and quantum randomness but is **not audited** and should not be used to protect life-critical data without professional review.

