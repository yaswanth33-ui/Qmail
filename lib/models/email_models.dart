import 'package:flutter/foundation.dart';

/// Key exchange modes supported by QMail.
/// 
/// - PQC: Post-Quantum Cryptography using ML-KEM-1024 (recommended for production)
/// - BB84: **SIMULATED** Quantum Key Distribution (software-only, no real quantum hardware)
/// 
/// Both modes generate a session key that is transmitted with the message.
/// Recipients can decrypt messages regardless of their own mode preference.
enum KeyExchangeMode {
  pqc,
  bb84;

  String get value {
    switch (this) {
      case KeyExchangeMode.pqc:
        return 'pqc';
      case KeyExchangeMode.bb84:
        return 'bb84';
    }
  }

  String get label {
    switch (this) {
      case KeyExchangeMode.pqc:
        return 'PQC (ML-KEM-1024)';
      case KeyExchangeMode.bb84:
        return 'BB84 (Simulated QKD)';
    }
  }

  String get description {
    switch (this) {
      case KeyExchangeMode.pqc:
        return 'Post-Quantum Cryptography - NIST standardized, production-ready';
      case KeyExchangeMode.bb84:
        return 'Simulated BB84 QKD - Software simulation, not real quantum hardware';
    }
  }

  static KeyExchangeMode fromString(String? value) {
    switch (value?.toLowerCase()) {
      case 'bb84':
        return KeyExchangeMode.bb84;
      case 'pqc':
      default:
        return KeyExchangeMode.pqc;
    }
  }
}

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

  /// Get file extension (lowercase)
  String get extension => fileName.split('.').last.toLowerCase();

  /// File type category for display purposes
  AttachmentType get type {
    // Check by MIME type first
    if (mimeType.startsWith('image/')) return AttachmentType.image;
    if (mimeType.startsWith('video/')) return AttachmentType.video;
    if (mimeType.startsWith('audio/')) return AttachmentType.audio;
    if (mimeType == 'application/pdf') return AttachmentType.pdf;
    if (mimeType.contains('spreadsheet') || mimeType.contains('excel')) return AttachmentType.spreadsheet;
    if (mimeType.contains('presentation') || mimeType.contains('powerpoint')) return AttachmentType.presentation;
    if (mimeType.contains('document') || mimeType.contains('word') || mimeType.contains('text')) return AttachmentType.document;
    if (mimeType.contains('zip') || mimeType.contains('compressed') || mimeType.contains('archive')) return AttachmentType.archive;
    if (mimeType.contains('javascript') || mimeType.contains('json') || mimeType.contains('xml')) return AttachmentType.code;
    
    // Fallback to extension-based detection
    switch (extension) {
      case 'jpg': case 'jpeg': case 'png': case 'gif': case 'bmp': case 'webp': case 'svg': case 'ico': case 'heic':
        return AttachmentType.image;
      case 'mp4': case 'avi': case 'mov': case 'mkv': case 'wmv': case 'flv': case 'webm': case '3gp':
        return AttachmentType.video;
      case 'mp3': case 'wav': case 'ogg': case 'flac': case 'aac': case 'm4a': case 'wma':
        return AttachmentType.audio;
      case 'pdf':
        return AttachmentType.pdf;
      case 'doc': case 'docx': case 'odt': case 'rtf': case 'txt': case 'md':
        return AttachmentType.document;
      case 'xls': case 'xlsx': case 'ods': case 'csv':
        return AttachmentType.spreadsheet;
      case 'ppt': case 'pptx': case 'odp':
        return AttachmentType.presentation;
      case 'zip': case 'rar': case '7z': case 'tar': case 'gz': case 'bz2':
        return AttachmentType.archive;
      case 'js': case 'ts': case 'py': case 'java': case 'c': case 'cpp': case 'h': case 'cs': case 'dart': case 'html': case 'css': case 'json': case 'xml':
        return AttachmentType.code;
      case 'exe': case 'msi': case 'apk': case 'dmg': case 'app':
        return AttachmentType.executable;
      default:
        return AttachmentType.other;
    }
  }

  /// Whether this attachment can be previewed inline
  bool get canPreview => type == AttachmentType.image;

  /// Whether this is a media file (image, video, audio)
  bool get isMedia => type == AttachmentType.image || type == AttachmentType.video || type == AttachmentType.audio;

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

  /// Get display name for the file type
  String get typeLabel {
    switch (type) {
      case AttachmentType.image: return 'Image';
      case AttachmentType.video: return 'Video';
      case AttachmentType.audio: return 'Audio';
      case AttachmentType.pdf: return 'PDF';
      case AttachmentType.document: return 'Document';
      case AttachmentType.spreadsheet: return 'Spreadsheet';
      case AttachmentType.presentation: return 'Presentation';
      case AttachmentType.archive: return 'Archive';
      case AttachmentType.code: return 'Code';
      case AttachmentType.executable: return 'Executable';
      case AttachmentType.other: return extension.toUpperCase();
    }
  }
}

/// Attachment file type categories
enum AttachmentType {
  image,
  video,
  audio,
  pdf,
  document,
  spreadsheet,
  presentation,
  archive,
  code,
  executable,
  other,
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
    this.sessionKeyHex, // E2E: session key for attachment decryption
    this.viewOnce = false, // View-once (OTP) message
    this.inReplyTo, // ID of the email being replied to (for threading)
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
  final String? sessionKeyHex;
  final bool viewOnce;
  final String? inReplyTo;
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
      subject: 'Welcome to QUMail',
      preview: 'This is a simulated encrypted message rendered as plain text...',
      bodyText:
          'Hi Bob,\n\nWelcome to QUMail. This message body is decrypted from a JSON payload provided by the backend.\nAll cryptographic operations are handled by the Python service.\n\nBest,\nAlice',
      sentAt: DateTime.now().subtract(const Duration(minutes: 10)),
      isRead: false,
      hasAttachments: true,
      attachments: const [
        Attachment(
          id: 'a1',
          fileName: 'qumail_whitepaper.pdf',
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
          'Hi Alice,\n\nOur legacy system only supports classical cryptography. Messages will be marked accordingly in QUMail.\n\nRegards,\nBob',
      sentAt: DateTime.now().subtract(const Duration(days: 1)),
      isRead: true,
      hasAttachments: false,
      attachments: const [],
      signatureValid: false,
      securityLevel: SecurityLevel.classical,
    ),
  ];
}

