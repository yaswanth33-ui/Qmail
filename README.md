<p align="center">
  <img src="assets/images/qmail_logo.png" alt="Qmail Logo" width="120"/>
</p>

<h1 align="center">Qmail — Quantum-Secure Email Platform</h1>

<p align="center">
  <strong>End-to-end encrypted, quantum-resistant email for the post-quantum era.</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="#deployment">Deployment</a> •
  <a href="#security">Security</a> •
  <a href="#platforms">Platforms</a> •
  <a href="#license">License</a>
</p>

---

## Overview

Qmail is a production-grade, cross-platform email client and backend that enforces **true application-layer end-to-end encryption** using quantum-safe cryptographic primitives. All message content is encrypted on the sender's device and decrypted only on the recipient's device — the server never sees plaintext.

Built with **Flutter** (cross-platform frontend) and **FastAPI** (Python backend), Qmail delivers a modern, responsive email experience with security designed to withstand both classical and quantum computing threats.

---

## Features

- **Quantum-Safe Encryption** — Post-Quantum Cryptography (ML-KEM-1024 / Kyber) for key exchange; AES-256-GCM for symmetric encryption
- **BB84 QKD Simulation** — Pluggable Quantum Key Distribution protocol for shared key derivation
- **One-Time Pad Messages** — One-Time Pad (OTP) encryption using keys from ANU's Quantum Random Number Generator (QRNG)
- **PQC Digital Signatures** — Dilithium2 post-quantum signatures for message authenticity and integrity
- **Phone Authentication** — OTP-based phone verification with rate limiting
- **WhatsApp-Style Messaging** — Real-time message delivery with send/receive/acknowledge flow
- **Argon2id Key Derivation** — Memory-hard KDF for deterministic email key generation
- **Cross-Platform** — Windows, macOS, Linux, Web, Android, and iOS from a single codebase
- **Kubernetes-Ready** — Deployment manifests, ConfigMaps, and Ingress configurations included
- **Docker Support** — Containerized backend with Docker Compose for local development

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FLUTTER FRONTEND                               │
│              Windows · macOS · Linux · Web · Android · iOS              │
│                                                                         │
│   Screens          Services           Providers        Widgets          │
│   ├─ Inbox         ├─ AuthService     ├─ AppState      ├─ Animated     │
│   ├─ Compose       ├─ EmailService    ├─ AuthState     ├─ Attachment   │
│   ├─ MessageView   ├─ CryptoService   └─ Riverpod     └─ Shared       │
│   ├─ Profile       ├─ MessageService                                   │
│   ├─ Login         └─ ApiConfig                                        │
│   └─ Signup                                                            │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ HTTPS / REST
                                 ▼
╔═════════════════════════════════════════════════════════════════════════╗
║                     FASTAPI BACKEND (api.py)                           ║
║                                                                         ║
║  ┌─ Authentication ──┐  ┌─ Email Operations ────┐  ┌─ Key Mgmt ──────┐ ║
║  │ POST /auth/phone  │  │ POST /email/draft     │  │ GET /keys/kem/  │ ║
║  │ GET  /auth/user   │  │ POST /email/send      │  │     {email}     │ ║
║  │ POST /auth/logout │  │ GET  /email/inbox     │  └─────────────────┘ ║
║  └───────────────────┘  │ POST /email/refresh   │                      ║
║                          │ POST /email/sync      │  ┌─ Attachments ──┐ ║
║  ┌─ Messages ────────┐  │ POST /email/trash     │  │ POST upload     │ ║
║  │ POST /msg/send    │  │ POST /email/restore   │  │ GET  list       │ ║
║  │ GET  /msg/pending │  │ GET  /email/{id}/open │  │ GET  download   │ ║
║  │ POST /msg/ack     │  │ DELETE /email/{id}    │  │ DELETE remove   │ ║
║  │ POST /msg/download│  └──────────────────────-┘  └─────────────────┘ ║
║  └───────────────────┘                                                  ║
║  ┌─ View-Once (OTP) ─┐  ┌─ Encrypted Email ────┐  ┌─ System ────────┐ ║
║  │ POST /viewonce/   │  │ POST /encrypted/send │  │ GET /health     │ ║
║  │      send         │  │ GET  /encrypted/     │  └─────────────────┘ ║
║  │ GET  /viewonce/   │  │      pending         │                      ║
║  │      pending      │  │ POST /encrypted/     │                      ║
║  │ POST /viewonce/   │  │      {id}/download   │                      ║
║  │      {id}/download│  │ POST /encrypted/     │                      ║
║  │ POST /viewonce/   │  │      {id}/delete     │                      ║
║  │      mark-viewed  │  └──────────────────────┘                      ║
║  └───────────────────┘                                                  ║
╚════════════════════════════════╤════════════════════════════════════════╝
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
   ┌─────────────┐      ┌──────────────┐      ┌──────────────┐
   │   Crypto    │      │ Key Exchange │      │   Storage    │
   │   Layer 1   │      │   Layer 2    │      │   Layer 4    │
   ├─────────────┤      ├──────────────┤      ├──────────────┤
   │ AES-256-GCM │      │ BB84 (QKD)   │      │ PostgreSQL   │
   │ OTP (QRNG)  │      │ ML-KEM-1024  │      │ Redis        │
   │ Dilithium2  │      │ Pluggable    │      │ SQLite       │
   │ Argon2id    │      │ Interface    │      │ Encrypted DB │
   │ QRNG (ANU)  │      │ QKD Broker   │      │ Key Lifecycle│
   └─────────────┘      └──────────────┘      └──────────────┘
```

### Project Structure

```
qmail/
├── api.py                  # FastAPI REST API (Layer 7)
├── client.py               # CLI client
├── config.py               # Configuration management
├── models.py               # Data models
├── auth/                   # Authentication layer
│   ├── otp_service.py      # OTP generation & verification
│   ├── phone_auth_app.py   # Phone authentication
│   ├── phone_auth_models.py
│   ├── phone_auth_routes.py
│   ├── qkd.py              # Quantum Key Distribution
│   ├── server_broker.py    # Key exchange broker
│   └── token_service.py    # JWT token management
├── crypto/                 # Cryptographic primitives (Layer 1)
│   ├── aes.py              # AES-256-GCM encryption
│   ├── otp.py              # One-Time Pad encryption
│   ├── qrng.py             # ANU Quantum RNG integration
│   └── signatures.py       # PQC digital signatures
├── key_exchange/           # Key exchange protocols (Layer 2)
│   ├── base.py             # Pluggable interface
│   ├── bb84.py             # BB84 QKD simulation
│   └── pqc.py              # Post-quantum KEM (ML-KEM-1024)
├── keys/                   # Key lifecycle management (Layer 3)
│   └── lifecycle.py        # Key rotation, expiry, revocation
├── storage/                # Persistent storage (Layer 4)
│   └── db.py               # Database operations
└── transport/              # Email transport (Layer 6)

lib/                        # Flutter frontend
├── main.dart
├── models/                 # Auth & email data models
├── providers/              # Riverpod state management
├── router/                 # App routing
├── screens/                # UI screens
│   ├── compose_screen.dart
│   ├── inbox_screen.dart
│   ├── message_view_screen.dart
│   ├── profile_screen.dart
│   ├── qmail_login_screen.dart
│   └── qmail_signup_screen.dart
├── services/               # API & crypto services
│   ├── api_config.dart
│   ├── auth_service.dart
│   ├── crypto_service.dart
│   ├── email_service.dart
│   └── message_service.dart
├── theme/                  # Outlook-inspired theme
└── widgets/                # Reusable UI components

k8s/                        # Kubernetes manifests
├── deployment.yaml
├── ingress.yaml
├── postgres.yaml
├── redis.yaml
├── storage.yaml
└── configmap-secrets.yaml

.github/workflows/          # CI/CD pipelines
├── deploy.yml              # Backend: test → build → deploy to GKE
└── flutter-build.yml       # Frontend: build for all 6 platforms
```

---

## Getting Started

### Prerequisites

- **Python 3.12+** (backend)
- **Flutter SDK** (frontend, channel: master)
- **Docker & Docker Compose** (optional, for containerized development)

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/yaswanth33-ui/Qmail.git
cd Qmail

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\Activate.ps1       # Windows PowerShell

# Install dependencies
pip install -r requirements.txt
```

### Environment Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

<details>
<summary><strong>All Environment Variables</strong></summary>

| Variable                      | Description                                               | Default                                       | Required       |
| ----------------------------- | --------------------------------------------------------- | --------------------------------------------- | -------------- |
| **Runtime**                   |                                                           |                                               |                |
| `ENV`                         | Environment mode                                          | `development`                                 | Yes            |
| `ENFORCE_HTTPS`               | Enforce HTTPS connections                                 | `0`                                           | No             |
| `LOG_LEVEL`                   | Logging verbosity                                         | `INFO`                                        | No             |
| **API Server**                |                                                           |                                               |                |
| `API_HOST`                    | Server bind address                                       | `0.0.0.0`                                     | Yes            |
| `API_PORT`                    | Server port                                               | `8000`                                        | Yes            |
| `API_RELOAD`                  | Auto-reload on code change                                | `True`                                        | No             |
| `API_BASE_URL`                | Public URL for Flutter app                                | `http://localhost:5000`                       | Yes            |
| **CORS**                      |                                                           |                                               |                |
| `CORS_ALLOWED_ORIGINS`        | Comma-separated allowed origins                           | `http://localhost:5000,...`                   | Yes            |
| **Database**                  |                                                           |                                               |                |
| `DATABASE_URL`                | PostgreSQL connection string                              | `postgresql://qmail:...@localhost:5432/qmail` | Yes            |
| **Redis**                     |                                                           |                                               |                |
| `REDIS_URL`                   | Redis connection string (token revocation, rate limiting) | _(empty)_                                     | Prod only      |
| **Security & Sessions**       |                                                           |                                               |                |
| `SESSION_TIMEOUT_SECONDS`     | Session TTL in seconds                                    | `3600`                                        | No             |
| `SENSITIVE_OPS_REAUTH_WINDOW` | Re-auth window for sensitive ops (seconds)                | `300`                                         | No             |
| `DB_ENCRYPTION_MASTER_KEY`    | Master key for DB encryption (Docker/Cloud)               | _(empty)_                                     | Prod only      |
| `JWT_SECRET_KEY`              | Secret for signing JWT tokens                             | `your-secret-key-change-in-production`        | Yes            |
| `JWT_ALGORITHM`               | JWT signing algorithm                                     | `HS256`                                       | No             |
| **QRNG**                      |                                                           |                                               |                |
| `QRNG_BASE_URL`               | ANU Quantum RNG API endpoint                              | `https://qrng.anu.edu.au/API/jsonI.php`       | No             |
| `QRNG_API_KEY`                | API key for QRNG (future use)                             | _(empty)_                                     | No             |
| **Phone Auth (Twilio)**       |                                                           |                                               |                |
| `TWILIO_ACCOUNT_SID`          | Twilio account SID                                        | _(empty)_                                     | For phone auth |
| `TWILIO_AUTH_TOKEN`           | Twilio auth token                                         | _(empty)_                                     | For phone auth |
| `TWILIO_PHONE_NUMBER`         | Twilio sender phone number                                | _(empty)_                                     | For phone auth |

</details>

**Development** `.env`:

```env
# Runtime
ENV=development
ENFORCE_HTTPS=0
LOG_LEVEL=INFO

# API Server
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=True
API_BASE_URL=http://localhost:5000

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:5000,http://localhost:3000,http://localhost:8000

# Database (PostgreSQL recommended, SQLite fallback)
DATABASE_URL=postgresql://qmail:qmail_dev_password@localhost:5432/qmail

# Redis (optional for development)
REDIS_URL=

# Session & Security
SESSION_TIMEOUT_SECONDS=3600
SENSITIVE_OPS_REAUTH_WINDOW=300

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256

# QRNG
QRNG_BASE_URL=https://qrng.anu.edu.au/API/jsonI.php
QRNG_API_KEY=

# Database Encryption (Docker/Cloud only)
DB_ENCRYPTION_MASTER_KEY=

# Phone Auth (Twilio)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
```

### Run the Backend

```bash
uvicorn qmail.api:app --reload --host 0.0.0.0 --port 8000
```

API documentation available at: `http://localhost:8000/docs`

### Run the Frontend

```bash
# Get Flutter dependencies
flutter pub get

# Run on your platform
flutter run -d chrome       # Web
flutter run -d windows      # Windows
flutter run -d macos        # macOS
flutter run -d linux        # Linux
```

### Docker (Local Development)

```bash
docker-compose up -d
```

---

## Deployment

### Kubernetes (GKE)

The project includes full Kubernetes manifests in `k8s/` and automated CI/CD via GitHub Actions.

**Automated pipeline** (on push to `main`):

1. Run security tests and smoke checks
2. Build and push Docker image to Google Container Registry
3. Deploy to GKE with rolling updates

```bash
# Manual deployment
kubectl apply -f k8s/
kubectl rollout status deployment/qmail-api -n qmail
```

### Multi-Platform Releases

Push a version tag to trigger automated builds for all platforms:

```bash
git tag v1.0.0
git push origin v1.0.0
```

This creates a [GitHub Release](https://github.com/yaswanth33-ui/Qmail/releases) with downloadable artifacts:

| Platform | Artifact                 |
| -------- | ------------------------ |
| Windows  | `qmail-windows-x64.zip`  |
| macOS    | `qmail-macos.zip`        |
| Linux    | `qmail-linux-x64.tar.gz` |
| Web      | `qmail-web.tar.gz`       |
| Android  | `app-release.apk`        |
| iOS      | `qmail-ios.zip`          |

---

## Security

### Encryption Model

| Layer                    | Component              | Algorithm                      |
| ------------------------ | ---------------------- | ------------------------------ |
| Symmetric Encryption     | Message content        | AES-256-GCM                    |
| One-Time Pad Mails       | One-Time Pad           | XOR with QRNG keys             |
| Key Exchange             | Session keys           | ML-KEM-1024 (Kyber) / BB84 QKD |
| Digital Signatures       | Message authentication | Dilithium2 (PQC)               |
| Key Derivation           | Email keys             | Argon2id (time=2, mem=64 MiB)  |
| Random Number Generation | Key material           | ANU Quantum RNG API            |

### Security Principles

- **Zero-knowledge server** — the backend never sees plaintext message content
- **Forward secrecy** — session keys are derived per-exchange and rotated
- **Quantum resistance** — all asymmetric operations use NIST-approved post-quantum algorithms
- **Defense in depth** — layered architecture isolates cryptographic concerns
- **Credential safety** — OAuth tokens stored in OS keyring; secrets managed via environment variables and secure vaults

### KDF Migration: PBKDF2 → Argon2id

Argon2id is the sole KDF for deterministic email key derivation. For upgrading existing deployments:

1. **Staging** — Install `argon2-cffi` and run full integration tests
2. **Compatibility** — Add `kdf_version` metadata to existing records before switching
3. **Migration** — Re-encrypt affected messages or preserve legacy decryption in a migration tool
4. **Rollout** — Deploy Argon2-enabled binaries to all nodes and monitor

> Argon2 parameters: `time_cost=2`, `memory_cost=64 MiB` — balanced for mobile and server workloads.

### Responsible Disclosure

If you discover a security vulnerability, please report it privately via [GitHub Security Advisories](https://github.com/yaswanth33-ui/Qmail/security/advisories).

---

## Platforms

| Platform | Status       | Build                             |
| -------- | ------------ | --------------------------------- |
| Windows  | ✅ Supported | `flutter build windows --release` |
| macOS    | ✅ Supported | CI/CD via GitHub Actions          |
| Linux    | ✅ Supported | CI/CD via GitHub Actions          |
| Web      | ✅ Supported | `flutter run -d chrome`           |
| Android  | ✅ Supported | `flutter build apk --release`     |
| iOS      | ✅ Supported | CI/CD via GitHub Actions          |

---

## Tech Stack

| Component | Technology                                     |
| --------- | ---------------------------------------------- |
| Frontend  | Flutter / Dart                                 |
| Backend   | FastAPI / Python 3.12                          |
| Database  | PostgreSQL, SQLite                             |
| Cache     | Redis                                          |
| Auth      | Phone OTP, JWT                                 |
| Crypto    | ML-KEM-1024, Dilithium2, AES-256-GCM, Argon2id |
| Quantum   | ANU QRNG, BB84 QKD (simulated)                 |
| Infra     | Docker, Kubernetes (GKE), Nginx                |
| CI/CD     | GitHub Actions                                 |

---

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.

---

<p align="center">
  Built with quantum-grade security by <a href="https://github.com/yaswanth33-ui">Yaswanth Reddy</a>
</p>
