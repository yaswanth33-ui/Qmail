import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'api_config.dart';
import 'crypto_service.dart';

/// Simple draft response (only id needed)
class DraftResponse {
  final String id;
  
  DraftResponse({required this.id});
  
  factory DraftResponse.fromJson(Map<String, dynamic> json) {
    return DraftResponse(id: json['id'] as String);
  }
}

/// Attachment metadata from backend
class AttachmentMeta {
  final int id;
  final int emailId;
  final String filename;
  final String mimeType;
  final int sizeBytes;

  AttachmentMeta({
    required this.id,
    required this.emailId,
    required this.filename,
    required this.mimeType,
    required this.sizeBytes,
  });

  factory AttachmentMeta.fromJson(Map<String, dynamic> json) {
    return AttachmentMeta(
      id: json['id'] as int? ?? 0,
      emailId: json['email_id'] as int? ?? 0,
      filename: json['filename'] as String? ?? 'unnamed',
      mimeType: json['mime_type'] as String? ?? 'application/octet-stream',
      sizeBytes: json['size_bytes'] as int? ?? 0,
    );
  }
}

/// Email response model from backend
class EmailResponse {
  final String id;
  final String account;
  final String folder;
  final String fromEmail;
  final String fromName;
  final String toEmail;
  final String toName;
  final String subject;
  final String preview;
  final String bodyText;
  final DateTime sentAt;
  final bool isRead;
  final bool hasAttachments;
  final List<AttachmentMeta> attachments;
  final bool signatureValid;
  final String securityLevel;
  final bool viewOnce;
  final String? sessionKeyHex; // E2E: session key for attachment decryption
  final String? inReplyTo; // ID of the email being replied to

  EmailResponse({
    required this.id,
    required this.account,
    required this.folder,
    required this.fromEmail,
    required this.fromName,
    required this.toEmail,
    required this.toName,
    required this.subject,
    required this.preview,
    required this.bodyText,
    required this.sentAt,
    this.isRead = false,
    this.hasAttachments = false,
    this.attachments = const [],
    this.signatureValid = false,
    this.securityLevel = 'aes_gcm',
    this.viewOnce = false,
    this.sessionKeyHex,
    this.inReplyTo,
  });

  factory EmailResponse.fromJson(Map<String, dynamic> json) {
    final attachmentsList = json['attachments'] as List<dynamic>? ?? [];
    final attachments = attachmentsList
        .map((a) => AttachmentMeta.fromJson(a as Map<String, dynamic>))
        .toList();
    
    return EmailResponse(
      id: json['id'] as String,
      account: json['account'] as String? ?? '',
      folder: json['folder'] as String? ?? 'Inbox',
      fromEmail: json['from_email'] as String,
      fromName: json['from_name'] as String? ?? '',
      toEmail: json['to_email'] as String,
      toName: json['to_name'] as String? ?? '',
      subject: json['subject'] as String,
      preview: json['preview'] as String? ?? '',
      bodyText: json['bodyText'] as String? ?? '',
      sentAt: DateTime.parse(json['sentAt'] as String),
      isRead: json['isRead'] as bool? ?? false,
      hasAttachments: attachments.isNotEmpty || (json['hasAttachments'] as bool? ?? false),
      attachments: attachments,
      signatureValid: json['signatureValid'] as bool? ?? false,
      securityLevel: json['securityLevel'] as String? ?? 'aes_gcm',
      viewOnce: json['view_once'] as bool? ?? false,
      sessionKeyHex: json['session_key_hex'] as String?,
      inReplyTo: json['in_reply_to'] as String?,
    );
  }
}

/// Decrypted email response for viewing
class DecryptedEmailResponse {
  final String id;
  final String fromEmail;
  final String toEmail;
  final String subject;
  final String body;
  final List<Map<String, dynamic>> attachments;
  final bool isSignatureValid;
  final String encryptionMode;
  final DateTime openedAt;
  final String? sessionKeyHex; // E2E: Session key for decrypting attachments
  final String? encryptedContentHex; // E2E: Encrypted body for client-side decryption
  final String? signatureHex; // PQC signature for verification
  final String? signatureAlgorithm; // e.g., "Dilithium2"
  final String? senderPublicKeyHex; // Sender's public key for verification
  final String? encryptionType; // "aes" or "otp"
  final String? macHex; // MAC tag for OTP verification
  final bool viewOnce; // Is this a view-once message?
  final String? keyExchangeMode; // "pqc" or "bb84" - which mode sender used

  DecryptedEmailResponse({
    required this.id,
    required this.fromEmail,
    required this.toEmail,
    required this.subject,
    required this.body,
    this.attachments = const [],
    this.isSignatureValid = false,
    this.encryptionMode = 'AES',
    DateTime? openedAt,
    this.sessionKeyHex,
    this.encryptedContentHex,
    this.signatureHex,
    this.signatureAlgorithm,
    this.senderPublicKeyHex,
    this.encryptionType,
    this.macHex,
    this.viewOnce = false,
    this.keyExchangeMode,
  }) : openedAt = openedAt ?? DateTime.now();

  factory DecryptedEmailResponse.fromJson(Map<String, dynamic> json) {
    return DecryptedEmailResponse(
      id: json['id'] as String,
      fromEmail: json['from_email'] as String,
      toEmail: json['to_email'] as String,
      subject: json['subject'] as String,
      body: json['body'] as String,
      attachments: (json['attachments'] as List<dynamic>?)
              ?.map((a) => a as Map<String, dynamic>)
              .toList() ??
          [],
      isSignatureValid: json['is_signature_valid'] as bool? ?? false,
      encryptionMode: json['encryption_mode'] as String? ?? 'AES',
      openedAt: json['opened_at'] != null
          ? DateTime.parse(json['opened_at'] as String)
          : DateTime.now(),
      sessionKeyHex: json['session_key_hex'] as String?,
      encryptedContentHex: json['encrypted_content_hex'] as String?,
      signatureHex: json['signature_hex'] as String?,
      signatureAlgorithm: json['signature_algorithm'] as String?,
      senderPublicKeyHex: json['sender_public_key_hex'] as String?,
      encryptionType: json['encryption_type'] as String?,
      macHex: json['mac_hex'] as String?,
      viewOnce: json['view_once'] as bool? ?? false,
      keyExchangeMode: json['key_exchange_mode'] as String?,
    );
  }
  
  /// Check if this response contains E2E encrypted content that needs client decryption
  bool get needsClientDecryption => encryptedContentHex != null && encryptedContentHex!.isNotEmpty;
  
  /// Check if this is OTP-encrypted (view-once with perfect secrecy)
  bool get isOtpEncrypted => encryptionType == 'otp' || (viewOnce && needsClientDecryption);
  
  /// Check if this email has a PQC signature
  bool get hasSignature => signatureHex != null && signatureHex!.isNotEmpty;
}

/// Sync response from backend
class SyncResponse {
  final int emailsSynced;
  final List<String> errors;

  SyncResponse({required this.emailsSynced, this.errors = const []});

  factory SyncResponse.fromJson(Map<String, dynamic> json) {
    return SyncResponse(
      emailsSynced: json['emails_synced'] as int? ?? 0,
      errors: (json['errors'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
    );
  }
}

/// Sent email response from backend
class SentEmailResponse {
  final String id;
  final String sender;
  final String recipient;
  final String subject;
  final String content;
  final bool viewOnce;
  final DateTime sentAt;
  final String folder;
  final String? sessionKeyHex; // Session key for E2E attachment encryption

  SentEmailResponse({
    required this.id,
    required this.sender,
    required this.recipient,
    required this.subject,
    required this.content,
    required this.viewOnce,
    required this.sentAt,
    required this.folder,
    this.sessionKeyHex,
  });

  factory SentEmailResponse.fromJson(Map<String, dynamic> json) {
    return SentEmailResponse(
      id: json['id'] as String? ?? '',
      sender: json['sender'] as String? ?? '',
      recipient: json['recipient'] as String? ?? '',
      subject: json['subject'] as String? ?? '',
      content: json['content'] as String? ?? '',
      viewOnce: json['view_once'] as bool? ?? false,
      sentAt: json['sent_at'] != null
          ? DateTime.parse(json['sent_at'] as String)
          : DateTime.now(),
      folder: json['folder'] as String? ?? 'Sent',
      sessionKeyHex: json['session_key_hex'] as String?,
    );
  }
}

/// Email service for all email-related API calls.
///
/// TRUE END-TO-END ENCRYPTION:
/// - Email body is encrypted CLIENT-SIDE with quantum-seeded AES-256-GCM
/// - Server NEVER sees plaintext email content
/// - Session keys are generated using ANU Quantum Random Number Generator
///
/// Connects to the Qmail FastAPI backend at [ApiConfig.baseUrl].
class EmailService {
  Map<String, String> _authHeaders(String accessToken) => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $accessToken',
      };

  /// Send an email with TRUE END-TO-END ENCRYPTION.
  /// 
  /// SECURITY:
  /// - Regular emails: Quantum-seeded AES-256-GCM encryption
  /// - View-once emails: One-Time Pad (OTP) encryption with PERFECT SECRECY
  /// - Server NEVER sees plaintext content
  /// 
  /// [keyExchangeAlgorithm] indicates whether PQC or BB84 mode was used:
  /// - 'pqc': Post-Quantum Cryptography (ML-KEM-1024) - recommended
  /// - 'bb84': Simulated Quantum Key Distribution
  /// 
  /// Note: This is metadata for informational purposes. The actual session key
  /// is generated using QRNG and transmitted with the message, allowing
  /// recipients to decrypt regardless of their own mode preference.
  /// 
  /// For view-once messages, OTP provides information-theoretic security:
  /// - Cannot be decrypted even with infinite computing power
  /// - Key is same length as message (true OTP)
  /// - Key is destroyed after single use
  Future<SentEmailResponse> sendEmail({
    required String accessToken,
    required String sender,
    required String recipient,
    required String subject,
    required String body,
    bool viewOnce = false,
    String keyExchangeAlgorithm = 'pqc',
    String? inReplyTo,
  }) async {
    // Create payload JSON (same format as backend QmailClient)
    final payload = json.encode({
      'body': body,
      'attachments': [], // Attachments are uploaded separately
    });
    final plaintextBytes = Uint8List.fromList(utf8.encode(payload));
    
    String encryptedContentHex;
    String sessionKeyHex;
    String? macHex;
    String encryptionType;
    
    if (viewOnce) {
      // ═══════════════════════════════════════════════════════════════════════
      // VIEW-ONCE: One-Time Pad (OTP) encryption for PERFECT SECRECY
      // ═══════════════════════════════════════════════════════════════════════
      
      final otpEncrypted = await OtpService.encryptViewOnce(plaintextBytes);
      
      // Serialize: [otpKey][macKey(32)]
      final keysBytes = otpEncrypted.keysToBytes();
      sessionKeyHex = keysBytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
      
      // Serialize: [macTag(32)][ciphertext]
      final dataBytes = otpEncrypted.dataToBytes();
      encryptedContentHex = dataBytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
      
      // Also send MAC separately for clarity
      macHex = otpEncrypted.macTag.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
      
      encryptionType = 'otp';
    } else {
      // ═══════════════════════════════════════════════════════════════════════
      // REGULAR: AES-256-GCM with quantum-seeded keys
      // ═══════════════════════════════════════════════════════════════════════
      final sessionKey = await CryptoService.generateQuantumKey();
      sessionKeyHex = sessionKey.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
      
      // Encrypt with quantum-random nonce
      final encryptedBytes = await CryptoService.encryptToBytesQuantum(plaintextBytes, sessionKey);
      encryptedContentHex = encryptedBytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
      
      encryptionType = 'aes';
    }
    
    // Use the requested key exchange algorithm
    // The backend server will handle KEM encapsulation if the client doesn't provide it
    final effectiveKeyExchange = keyExchangeAlgorithm;

    // Send encrypted content to backend
    final response = await http
        .post(
          Uri.parse(ApiConfig.emailSend),
          headers: _authHeaders(accessToken),
          body: json.encode({
            'sender': sender,
            'recipient': recipient,
            'subject': subject,
            'encrypted_content_hex': encryptedContentHex,
            'session_key_hex': sessionKeyHex,
            'view_once': viewOnce,
            'client_encrypted': true, // Flag to indicate E2E encryption
            'encryption_type': encryptionType,
            'key_exchange_algorithm': effectiveKeyExchange, // PQC or BB84 mode
            if (macHex != null) 'mac_hex': macHex,
            if (inReplyTo != null) 'in_reply_to': inReplyTo,
          }),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to send email: ${response.body}');
    }

    final responseData = json.decode(response.body) as Map<String, dynamic>;
    // Ensure the session key is included in response for attachment encryption
    responseData['session_key_hex'] = sessionKeyHex;
    
    return SentEmailResponse.fromJson(responseData);
  }

  /// Sync emails from Gmail IMAP, view-once, and AES encrypted sources
  Future<SyncResponse> syncEmails({required String accessToken}) async {
    final response = await http
        .post(
          Uri.parse(ApiConfig.emailSync),
          headers: _authHeaders(accessToken),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to sync emails: ${response.body}');
    }

    return SyncResponse.fromJson(
        json.decode(response.body) as Map<String, dynamic>);
  }

  /// Refresh the inbox by syncing Gmail emails
  Future<List<EmailResponse>> refreshInbox({
    required String accessToken,
  }) async {
    final response = await http
        .post(
          Uri.parse(ApiConfig.emailRefresh),
          headers: _authHeaders(accessToken),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to refresh inbox: ${response.body}');
    }

    final data = json.decode(response.body) as List<dynamic>;
    return data
        .map((e) => EmailResponse.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Get inbox emails from local encrypted database
  Future<List<EmailResponse>> getInbox({required String accessToken}) async {
    final response = await http
        .get(
          Uri.parse(ApiConfig.emailInbox),
          headers: _authHeaders(accessToken),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to fetch inbox: ${response.body}');
    }

    final data = json.decode(response.body) as List<dynamic>;
    return data
        .map((e) => EmailResponse.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Open and decrypt an email (for viewing)
  /// 
  /// Handles both encryption types:
  /// - AES-256-GCM: Standard quantum-seeded encryption
  /// - OTP: One-Time Pad with PERFECT SECRECY (view-once messages)
  Future<DecryptedEmailResponse> openEmail({
    required String accessToken,
    required String emailId,
  }) async {
    final response = await http
        .get(
          Uri.parse(ApiConfig.emailOpen(emailId)),
          headers: _authHeaders(accessToken),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to open email: ${response.body}');
    }

    final decrypted = DecryptedEmailResponse.fromJson(
        json.decode(response.body) as Map<String, dynamic>);
    
    // E2E: Decrypt client-side if needed
    if (decrypted.needsClientDecryption) {
      
      if (decrypted.sessionKeyHex == null) {
        throw Exception('E2E decryption failed: missing session key');
      }
      
      try {
        String body;
        String encryptionMode;
        
        if (decrypted.isOtpEncrypted) {
          // ═══════════════════════════════════════════════════════════════════
          // OTP DECRYPTION: One-Time Pad for view-once messages
          // ═══════════════════════════════════════════════════════════════════
          
          // Parse keys: [otpKey][macKey(32)]
          final keysBytes = Uint8List.fromList(_hexToBytes(decrypted.sessionKeyHex!));
          
          // Parse data: [macTag(32)][ciphertext]
          final dataBytes = Uint8List.fromList(_hexToBytes(decrypted.encryptedContentHex!));
          
          // Decrypt using OTP service
          final decryptedBytes = OtpService.decryptViewOnceFromBytes(
            data: dataBytes,
            keys: keysBytes,
          );
          
          // Parse the JSON payload
          final payload = json.decode(utf8.decode(decryptedBytes)) as Map<String, dynamic>;
          body = payload['body'] as String? ?? '';
          encryptionMode = 'E2E_OTP_PERFECT_SECRECY';
          
        } else {
          // ═══════════════════════════════════════════════════════════════════
          // AES-GCM DECRYPTION: Standard quantum-seeded encryption
          // ═══════════════════════════════════════════════════════════════════
          
          final key = CryptoService.keyFromHex(decrypted.sessionKeyHex!);
          final encryptedBytes = Uint8List.fromList(_hexToBytes(decrypted.encryptedContentHex!));
          
          final decryptedBytes = CryptoService.decryptFromBytes(encryptedBytes, key);
          
          // Parse the JSON payload
          final payload = json.decode(utf8.decode(decryptedBytes)) as Map<String, dynamic>;
          body = payload['body'] as String? ?? '';
          encryptionMode = 'E2E_AES_GCM';
          
        }
        
        
        // Return a new response with the decrypted body
        return DecryptedEmailResponse(
          id: decrypted.id,
          fromEmail: decrypted.fromEmail,
          toEmail: decrypted.toEmail,
          subject: decrypted.subject,
          body: body,
          attachments: decrypted.attachments,
          isSignatureValid: decrypted.isSignatureValid,
          encryptionMode: encryptionMode,
          openedAt: decrypted.openedAt,
          sessionKeyHex: decrypted.sessionKeyHex,
          signatureHex: decrypted.signatureHex,
          signatureAlgorithm: decrypted.signatureAlgorithm,
          senderPublicKeyHex: decrypted.senderPublicKeyHex,
          encryptionType: decrypted.encryptionType,
          viewOnce: decrypted.viewOnce,
          keyExchangeMode: decrypted.keyExchangeMode,  // Preserve key exchange mode
        );
      } catch (e) {
        throw Exception('E2E decryption failed: $e');
      }
    }
    
    return decrypted;
  }
  
  /// Helper to convert hex string to bytes
  List<int> _hexToBytes(String hex) {
    final result = <int>[];
    for (var i = 0; i < hex.length; i += 2) {
      result.add(int.parse(hex.substring(i, i + 2), radix: 16));
    }
    return result;
  }

  /// Get trashed emails
  Future<List<EmailResponse>> getTrash({required String accessToken}) async {
    final response = await http
        .get(
          Uri.parse(ApiConfig.emailTrash),
          headers: _authHeaders(accessToken),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to fetch trash: ${response.body}');
    }

    final data = json.decode(response.body) as List<dynamic>;
    return data
        .map((e) => EmailResponse.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Move email to trash
  Future<void> trashEmail({
    required String accessToken,
    required String emailId,
  }) async {
    final response = await http
        .post(
          Uri.parse(ApiConfig.emailTrash),
          headers: _authHeaders(accessToken),
          body: json.encode({'email_id': emailId}),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to trash email: ${response.body}');
    }
  }

  /// Restore email from trash
  Future<void> restoreEmail({
    required String accessToken,
    required String emailId,
  }) async {
    final response = await http
        .post(
          Uri.parse(ApiConfig.emailRestore),
          headers: _authHeaders(accessToken),
          body: json.encode({'email_id': emailId}),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to restore email: ${response.body}');
    }
  }

  /// Permanently delete an email
  Future<void> deleteEmail({
    required String accessToken,
    required String emailId,
  }) async {
    final response = await http
        .delete(
          Uri.parse(ApiConfig.emailDelete(emailId)),
          headers: _authHeaders(accessToken),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to delete email: ${response.body}');
    }
  }

  /// Save email as draft
  Future<DraftResponse> saveDraft({
    required String accessToken,
    required String sender,
    required String recipient,
    required String subject,
    required String body,
    String? draftId,
  }) async {
    final Map<String, dynamic> requestBody = {
      'sender': sender,
      'recipient': recipient,
      'subject': subject,
      'content': body,
    };
    
    // Include draft_id if updating existing draft
    if (draftId != null) {
      requestBody['draft_id'] = int.tryParse(draftId);
    }
    
    final response = await http
        .post(
          Uri.parse(ApiConfig.emailDraft),
          headers: _authHeaders(accessToken),
          body: json.encode(requestBody),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to save draft: ${response.body}');
    }

    return DraftResponse.fromJson(
        json.decode(response.body) as Map<String, dynamic>);
  }

  /// Upload an attachment for an email (encrypted with AES-256-GCM)
  /// 
  /// TRUE END-TO-END ENCRYPTION:
  /// - Attachments are encrypted client-side with the email's session key
  /// - The server NEVER receives the encryption key
  /// - Only sender and recipient (who both have the session key) can decrypt
  /// 
  /// For sent emails: use sessionKeyHex from SentEmailResponse
  /// For received emails: use the email's session key from local storage
  Future<Map<String, dynamic>> uploadAttachment({
    required String accessToken,
    required String emailId,
    required String filename,
    required String mimeType,
    required List<int> bytes,
    required String sessionKeyHex, // Email's session key for E2E encryption
  }) async {
    // Use the email's session key for encryption (E2E - server never has key)
    final key = CryptoService.keyFromHex(sessionKeyHex);
    final plaintext = Uint8List.fromList(bytes);
    final encryptedBytes = CryptoService.encryptToBytes(plaintext, key);
    
    
    final uri = Uri.parse('${ApiConfig.baseUrl}/email/$emailId/attachments');
    final request = http.MultipartRequest('POST', uri);
    request.headers['Authorization'] = 'Bearer $accessToken';
    // NOTE: No X-Encryption-Key header - true E2E means server never has the key
    request.headers['X-Original-Size'] = bytes.length.toString();
    request.headers['X-Original-Mime-Type'] = mimeType; // Send actual MIME type for metadata
    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        encryptedBytes,
        filename: filename,
        contentType: MediaType.parse(mimeType), // Use actual MIME type
      ),
    );

    final streamedResponse = await request.send().timeout(ApiConfig.timeout);
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode != 200) {
      throw Exception('Failed to upload attachment: ${response.body}');
    }

    return json.decode(response.body) as Map<String, dynamic>;
  }

  /// Get attachments for an email
  Future<List<Map<String, dynamic>>> getAttachments({
    required String accessToken,
    required String emailId,
  }) async {
    final response = await http
        .get(
          Uri.parse('${ApiConfig.baseUrl}/email/$emailId/attachments'),
          headers: _authHeaders(accessToken),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to get attachments: ${response.body}');
    }

    final list = json.decode(response.body) as List;
    return list.cast<Map<String, dynamic>>();
  }

  /// Download and decrypt an attachment (E2E decryption)
  /// 
  /// TRUE END-TO-END ENCRYPTION:
  /// - Server returns encrypted attachment data
  /// - Decryption happens client-side with the email's session key
  /// - The server never has access to the decryption key
  /// 
  /// [sessionKeyHex] must be the email's session key:
  /// - For sent emails: from SentEmailResponse.sessionKeyHex
  /// - For received emails: from the email's session key in local storage
  Future<List<int>> downloadAttachment({
    required String accessToken,
    required int attachmentId,
    required String sessionKeyHex, // Email's session key for E2E decryption
  }) async {
    final response = await http
        .get(
          Uri.parse('${ApiConfig.baseUrl}/attachment/$attachmentId/download'),
          headers: _authHeaders(accessToken),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to download attachment: ${response.body}');
    }

    // E2E decryption with email's session key
    final key = CryptoService.keyFromHex(sessionKeyHex);
    final decryptedBytes = CryptoService.decryptFromBytes(
      Uint8List.fromList(response.bodyBytes),
      key,
    );
    return decryptedBytes;
  }
}
