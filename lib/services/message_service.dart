/// Message service for WhatsApp-style encrypted messaging.
///
/// This service handles the server broker messaging flow:
/// 1. Sender posts encrypted message to broker
/// 2. Recipient polls for pending messages
/// 3. Recipient downloads and decrypts message
/// 4. Message is deleted from broker after download

import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'api_config.dart';

/// Pending message from the server broker
class PendingMessage {
  final String id;
  final String sender;
  final String subject;
  final DateTime createdAt;

  PendingMessage({
    required this.id,
    required this.sender,
    required this.subject,
    required this.createdAt,
  });

  factory PendingMessage.fromJson(Map<String, dynamic> json) {
    return PendingMessage(
      id: json['id'] as String,
      sender: json['sender'] as String,
      subject: json['subject'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

/// Downloaded encrypted message from server broker
class DownloadedMessage {
  final String id;
  final String sender;
  final String subject;
  final String encryptedContentHex;
  final String encryptionType;
  final String keyMaterialHex;
  final String? macHex;
  final String? signatureHex;
  final String? signatureAlgorithm;
  final String keyExchangeAlgorithm;
  final bool viewOnce;

  DownloadedMessage({
    required this.id,
    required this.sender,
    required this.subject,
    required this.encryptedContentHex,
    required this.encryptionType,
    required this.keyMaterialHex,
    this.macHex,
    this.signatureHex,
    this.signatureAlgorithm,
    required this.keyExchangeAlgorithm,
    this.viewOnce = false,
  });

  factory DownloadedMessage.fromJson(Map<String, dynamic> json) {
    return DownloadedMessage(
      id: json['id'] as String,
      sender: json['sender'] as String,
      subject: json['subject'] as String,
      encryptedContentHex: json['encrypted_content_hex'] as String,
      encryptionType: json['encryption_type'] as String,
      keyMaterialHex: json['key_material_hex'] as String,
      macHex: json['mac_hex'] as String?,
      signatureHex: json['signature_hex'] as String?,
      signatureAlgorithm: json['signature_algorithm'] as String?,
      keyExchangeAlgorithm: json['key_exchange_algorithm'] as String,
      viewOnce: json['view_once'] as bool? ?? false,
    );
  }
}

/// Send message response
class SendMessageResponse {
  final String messageId;
  final String recipient;
  final String status;
  final DateTime createdAt;

  SendMessageResponse({
    required this.messageId,
    required this.recipient,
    required this.status,
    required this.createdAt,
  });

  factory SendMessageResponse.fromJson(Map<String, dynamic> json) {
    return SendMessageResponse(
      messageId: json['message_id'] as String,
      recipient: json['recipient'] as String,
      status: json['status'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

/// Message service for WhatsApp-style encrypted messaging
class MessageService {
  Map<String, String> _authHeaders(String accessToken) => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $accessToken',
      };

  /// Send an encrypted message via server broker
  ///
  /// The message is already encrypted client-side using AES-GCM or OTP.
  Future<SendMessageResponse> sendMessage({
    required String accessToken,
    required String messageId,
    required String recipient,
    required String subject,
    required String encryptedContentHex,
    required String encryptionType, // "aes" or "otp"
    required String keyMaterialHex,
    String? macHex,
    String? signatureHex,
    String? signatureAlgorithm,
    String keyExchangeAlgorithm = 'pqc',
    bool viewOnce = false,
  }) async {
    // Use the requested key exchange algorithm directly
    // The backend server will handle KEM encapsulation if needed
    final response = await http
        .post(
          Uri.parse(ApiConfig.messagesSend),
          headers: _authHeaders(accessToken),
          body: json.encode({
            'message_id': messageId,
            'recipient': recipient,
            'subject': subject,
            'encrypted_content_hex': encryptedContentHex,
            'encryption_type': encryptionType,
            'key_material_hex': keyMaterialHex,
            if (macHex != null) 'mac_hex': macHex,
            if (signatureHex != null) 'signature_hex': signatureHex,
            if (signatureAlgorithm != null)
              'signature_algorithm': signatureAlgorithm,
            'key_exchange_algorithm': keyExchangeAlgorithm,
            'view_once': viewOnce,
          }),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to send message: ${response.body}');
    }

    return SendMessageResponse.fromJson(
        json.decode(response.body) as Map<String, dynamic>);
  }

  /// Get pending messages from server broker
  ///
  /// Returns list of messages waiting for this recipient
  Future<List<PendingMessage>> getPendingMessages({
    required String accessToken,
  }) async {
    final response = await http
        .get(
          Uri.parse(ApiConfig.messagesPending),
          headers: _authHeaders(accessToken),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to fetch pending messages: ${response.body}');
    }

    final data = json.decode(response.body) as List<dynamic>;
    return data
        .map((m) => PendingMessage.fromJson(m as Map<String, dynamic>))
        .toList();
  }

  /// Download and decrypt a message from server broker
  ///
  /// After successful download, message is deleted from broker
  Future<DownloadedMessage> downloadMessage({
    required String accessToken,
    required String messageId,
  }) async {
    final response = await http
        .post(
          Uri.parse(ApiConfig.messageDownload(messageId)),
          headers: _authHeaders(accessToken),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to download message: ${response.body}');
    }

    return DownloadedMessage.fromJson(
        json.decode(response.body) as Map<String, dynamic>);
  }

  /// Acknowledge message receipt (optional)
  Future<void> acknowledgeMessage({
    required String accessToken,
    required String messageId,
  }) async {
    final response = await http
        .post(
          Uri.parse(ApiConfig.messageAck(messageId)),
          headers: _authHeaders(accessToken),
        )
        .timeout(ApiConfig.timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to acknowledge message: ${response.body}');
    }
  }
}
