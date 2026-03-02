import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/email_models.dart';
import '../services/email_service.dart';
import '../services/message_service.dart';
import '../providers/auth_providers.dart';

// =============================================================================
// SERVICE PROVIDERS
// =============================================================================

/// Email service provider (talks to Python backend).
final emailServiceProvider = Provider<EmailService>((ref) => EmailService());

/// Message service provider (WhatsApp-style messaging).
final messageServiceProvider =
    Provider<MessageService>((ref) => MessageService());

// =============================================================================
// KEY EXCHANGE MODE PROVIDER
// =============================================================================

/// Provider for the user's selected key exchange mode (PQC or BB84).
/// 
/// - PQC: Post-Quantum Cryptography using ML-KEM-1024 (recommended)
/// - BB84: Simulated Quantum Key Distribution
/// 
/// This affects how outgoing emails are encrypted. Incoming emails can be
/// decrypted regardless of mode since the session key is transmitted with
/// the message.
class KeyExchangeModeNotifier extends Notifier<KeyExchangeMode> {
  @override
  KeyExchangeMode build() {
    return KeyExchangeMode.pqc; // Default to PQC (production-ready)
  }
  
  void setMode(KeyExchangeMode mode) {
    state = mode;
  }
}

final keyExchangeModeProvider = NotifierProvider<KeyExchangeModeNotifier, KeyExchangeMode>(
  () => KeyExchangeModeNotifier(),
);

// =============================================================================
// EMAIL PROVIDERS
// =============================================================================

/// Unified inbox data across all accounts (fetched from backend).
final inboxProvider = FutureProvider<List<EmailEnvelope>>((ref) async {
  final authState = ref.watch(authStateProvider);

  // Need authentication to fetch inbox
  if (!authState.isAuthenticated || authState.token == null) {
    return [];
  }

  final emailService = ref.read(emailServiceProvider);
  final accessToken = authState.token!.accessToken;

  try {
    // STEP 1: Sync emails from server (downloads encrypted emails + view-once)
    await emailService.syncEmails(accessToken: accessToken);

    // STEP 2: Fetch inbox after sync
    final emails = await emailService.getInbox(accessToken: accessToken);

    // Convert backend response to EmailEnvelope format
    return emails.map((e) {
      return EmailEnvelope(
        id: e.id,
        account: e.account,
        folder: e.folder,
        from: Contact(
          id: e.fromEmail,
          displayName: e.fromName.isNotEmpty ? e.fromName : e.fromEmail,
          email: e.fromEmail,
          supportsPqc: true,
        ),
        to: [
          Contact(
            id: e.toEmail,
            displayName: e.toName.isNotEmpty ? e.toName : e.toEmail,
            email: e.toEmail,
            supportsPqc: true,
          ),
        ],
        subject: e.subject,
        preview: e.preview,
        bodyText: e.bodyText,
        sentAt: e.sentAt,
        isRead: e.isRead,
        hasAttachments: e.hasAttachments,
        attachments: e.attachments.map((a) => Attachment(
          id: a.id.toString(),
          fileName: a.filename,
          mimeType: a.mimeType,
          sizeBytes: a.sizeBytes,
          isAesGcmProtected: true,
        )).toList(),
        signatureValid: e.signatureValid,
        securityLevel: _parseSecurityLevel(e.securityLevel),
        sessionKeyHex: e.sessionKeyHex,
        viewOnce: e.viewOnce,
      );
    }).toList();
  } catch (e) {
    return [];
  }
});

/// Trash folder provider
final trashProvider = FutureProvider<List<EmailEnvelope>>((ref) async {
  final authState = ref.watch(authStateProvider);

  if (!authState.isAuthenticated || authState.token == null) {
    return [];
  }

  final emailService = ref.read(emailServiceProvider);
  final accessToken = authState.token!.accessToken;

  try {
    final emails = await emailService.getTrash(accessToken: accessToken);

    return emails.map((e) {
      return EmailEnvelope(
        id: e.id,
        account: e.account,
        folder: 'Trash',
        from: Contact(
          id: e.fromEmail,
          displayName: e.fromName.isNotEmpty ? e.fromName : e.fromEmail,
          email: e.fromEmail,
          supportsPqc: true,
        ),
        to: [
          Contact(
            id: e.toEmail,
            displayName: e.toName.isNotEmpty ? e.toName : e.toEmail,
            email: e.toEmail,
            supportsPqc: true,
          ),
        ],
        subject: e.subject,
        preview: e.preview,
        bodyText: e.bodyText,
        sentAt: e.sentAt,
        isRead: e.isRead,
        hasAttachments: e.hasAttachments,
        attachments: e.attachments.map((a) => Attachment(
          id: a.id.toString(),
          fileName: a.filename,
          mimeType: a.mimeType,
          sizeBytes: a.sizeBytes,
          isAesGcmProtected: true,
        )).toList(),
        signatureValid: e.signatureValid,
        securityLevel: _parseSecurityLevel(e.securityLevel),
        sessionKeyHex: e.sessionKeyHex,
        viewOnce: e.viewOnce,
      );
    }).toList();
  } catch (e) {
    return [];
  }
});

SecurityLevel _parseSecurityLevel(String? level) {
  switch (level?.toLowerCase()) {
    case 'pqc':
      return SecurityLevel.pqc;
    case 'classical':
      return SecurityLevel.classical;
    case 'otp':
      return SecurityLevel.otp;
    case 'aes_gcm':
    default:
      return SecurityLevel.aesGcm;
  }
}

// =============================================================================
// MESSAGE PROVIDERS (WhatsApp-style)
// =============================================================================

/// Pending messages from server broker
final pendingMessagesProvider =
    FutureProvider<List<PendingMessage>>((ref) async {
  final authState = ref.watch(authStateProvider);

  if (!authState.isAuthenticated || authState.token == null) {
    return [];
  }

  final messageService = ref.read(messageServiceProvider);
  final accessToken = authState.token!.accessToken;

  try {
    return await messageService.getPendingMessages(accessToken: accessToken);
  } catch (e) {
    return [];
  }
});

// =============================================================================
// EMAIL ACTIONS
// =============================================================================

/// Provider to decrypt a single email by ID (calls /email/{id}/open)
final openEmailProvider =
    FutureProvider.family<DecryptedEmailResponse?, String>(
  (ref, emailId) async {
    final authState = ref.watch(authStateProvider);
    if (!authState.isAuthenticated || authState.token == null) {
      return null;
    }

    final emailService = ref.read(emailServiceProvider);
    final accessToken = authState.token!.accessToken;

    try {
      return await emailService.openEmail(
        accessToken: accessToken,
        emailId: emailId,
      );
    } catch (e) {
      return null;
    }
  },
);
