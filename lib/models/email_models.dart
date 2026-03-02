import 'package:flutter/foundation.dart';

/// Security levels supported by QMail.
enum SecurityLevel {
  otp,
  aesGcm,
  pqc,
  classical;

  String get label {
    switch (this) {
      case SecurityLevel.otp:
        return 'OTP';
      case SecurityLevel.aesGcm:
        return 'AES-GCM';
      case SecurityLevel.pqc:
        return 'PQC';
      case SecurityLevel.classical:
        return 'Classical';
    }
  }
}

/// Basic attachment model for decrypted AES-GCM attachments.
@immutable
class Attachment {
  const Attachment({
    required this.id,
    required this.fileName,
    required this.mimeType,
    required this.sizeBytes,
    required this.isAesGcmProtected,
  });

  final String id;
  final String fileName;
  final String mimeType;
  final int sizeBytes;
  final bool isAesGcmProtected;

  String get sizeLabel {
    if (sizeBytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    var size = sizeBytes.toDouble();
    var unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    return '${size.toStringAsFixed(1)} ${units[unitIndex]}';
  }
}

/// Contact with PQC public key information and metadata.
@immutable
class Contact {
  const Contact({
    required this.id,
    required this.displayName,
    required this.email,
    required this.supportsPqc,
    this.pqcPublicKey,
    this.groups = const [],
  });

  final String id;
  final String displayName;
  final String email;
  final bool supportsPqc;
  final String? pqcPublicKey;
  final List<String> groups;
}

/// Envelope for an email item in lists and message view.
@immutable
class EmailEnvelope {
  const EmailEnvelope({
    required this.id,
    required this.account,
    required this.folder,
    required this.from,
    required this.to,
    required this.subject,
    required this.preview,
    required this.bodyText,
    required this.sentAt,
    required this.isRead,
    required this.hasAttachments,
    required this.attachments,
    required this.signatureValid,
    required this.securityLevel,
  });

  final String id;
  final String account;
  final String folder;
  final Contact from;
  final List<Contact> to;
  final String subject;
  final String preview;
  final String bodyText; // Decrypted plain text from backend JSON payload
  final DateTime sentAt;
  final bool isRead;
  final bool hasAttachments;
  final List<Attachment> attachments;
  final bool signatureValid;
  final SecurityLevel securityLevel;
}

/// Simple mock data representing backend integration.
class MockEmailData {
  static final contacts = <Contact>[
    const Contact(
      id: 'c1',
      displayName: 'Alice Quantum',
      email: 'alice@quantum.example',
      supportsPqc: true,
      pqcPublicKey: 'PQX-ALICE-KEY',
      groups: ['Friends'],
    ),
    const Contact(
      id: 'c2',
      displayName: 'Bob Classical',
      email: 'bob@classicmail.example',
      supportsPqc: false,
      pqcPublicKey: null,
      groups: ['Work'],
    ),
    const Contact(
      id: 'c3',
      displayName: 'QSec Ops',
      email: 'security@qmail.example',
      supportsPqc: true,
      pqcPublicKey: 'PQX-SEC-KEY',
      groups: ['Security'],
    ),
  ];

  static final List<EmailEnvelope> emails = [
    EmailEnvelope(
      id: 'e1',
      account: 'alice@quantum.example',
      folder: 'Inbox',
      from: contacts[0],
      to: [contacts[1]],
      subject: 'Welcome to QMail',
      preview: 'This is a simulated encrypted message rendered as plain text...',
      bodyText:
          'Hi Bob,\n\nWelcome to QMail. This message body is decrypted from a JSON payload provided by the backend.\nAll cryptographic operations are handled by the Python service.\n\nBest,\nAlice',
      sentAt: DateTime.now().subtract(const Duration(minutes: 10)),
      isRead: false,
      hasAttachments: true,
      attachments: const [
        Attachment(
          id: 'a1',
          fileName: 'qmail_whitepaper.pdf',
          mimeType: 'application/pdf',
          sizeBytes: 1_048_576,
          isAesGcmProtected: true,
        ),
      ],
      signatureValid: true,
      securityLevel: SecurityLevel.pqc,
    ),
    EmailEnvelope(
      id: 'e2',
      account: 'alice@quantum.example',
      folder: 'Inbox',
      from: contacts[2],
      to: [contacts[0]],
      subject: 'Security scan results',
      preview: 'Periodic verification of signatures and key material...',
      bodyText:
          'Hi Alice,\n\nYour PQC keys are healthy and all recent signatures verify correctly.\n\n— QSec Ops',
      sentAt: DateTime.now().subtract(const Duration(hours: 2)),
      isRead: true,
      hasAttachments: false,
      attachments: const [],
      signatureValid: true,
      securityLevel: SecurityLevel.aesGcm,
    ),
    EmailEnvelope(
      id: 'e3',
      account: 'bob@classicmail.example',
      folder: 'Inbox',
      from: contacts[1],
      to: [contacts[0]],
      subject: 'Legacy system notice',
      preview: 'This account is still using classical crypto only...',
      bodyText:
          'Hi Alice,\n\nOur legacy system only supports classical cryptography. Messages will be marked accordingly in QMail.\n\nRegards,\nBob',
      sentAt: DateTime.now().subtract(const Duration(days: 1)),
      isRead: true,
      hasAttachments: false,
      attachments: const [],
      signatureValid: false,
      securityLevel: SecurityLevel.classical,
    ),
  ];
}

