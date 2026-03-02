import 'dart:convert';

import 'package:http/http.dart' as http;

class EmailService {
  final String baseUrl;

  EmailService({this.baseUrl = 'http://localhost:5000'});

  Future<void> sendEmail({
    required String accessToken,
    required String sender,
    required String recipient,
    required String subject,
    required String body,
    bool viewOnce = false,
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/email/send'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $accessToken',
          },
          body: json.encode({
            'sender': sender,
            'recipient': recipient,
            'subject': subject,
            'content': body,
            'view_once': viewOnce,
          }),
        )
        .timeout(const Duration(seconds: 30));

    if (response.statusCode != 200) {
      throw Exception('Failed to send email: ${response.body}');
    }

    // Response body contains the sent email details
    // This can be used for UI feedback or caching if needed
    final data = json.decode(response.body) as Map<String, dynamic>;
    print('Email sent successfully: ${data['id']}');
  }

  /// Refresh the inbox by syncing Gmail emails
  Future<void> refreshInbox({
    required String accessToken,
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/email/refresh'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $accessToken',
          },
        )
        .timeout(const Duration(seconds: 30));

    if (response.statusCode != 200) {
      throw Exception('Failed to refresh inbox: ${response.body}');
    }
  }
}

