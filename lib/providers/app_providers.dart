import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

import '../models/email_models.dart';
import '../services/email_service.dart';
import '../providers/auth_providers.dart';

/// Unified inbox data across all accounts (fetched from backend).
final inboxProvider = FutureProvider<List<EmailEnvelope>>((ref) async {
  final authState = ref.watch(authStateProvider);
  
  // Need authentication to fetch inbox
  if (!authState.isAuthenticated || authState.token == null) {
    return [];
  }

  try {
    final response = await http.get(
      Uri.parse('http://localhost:5000/email/inbox'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${authState.token!.accessToken}',
      },
    ).timeout(const Duration(seconds: 30));

    if (response.statusCode == 200) {
      final data = json.decode(response.body) as List<dynamic>;
      
      // Convert backend response to EmailEnvelope format
      final emails = data.map((e) {
        final email = e as Map<String, dynamic>;
        return EmailEnvelope(
          id: email['id'] as String,
          account: email['account'] as String,
          folder: email['folder'] as String,
          from: Contact(
            id: '${email['from_email']}',
            displayName: email['from_name'] as String? ?? email['from_email'] as String,
            email: email['from_email'] as String,
            supportsPqc: true,
          ),
          to: [
            Contact(
              id: '${email['to_email']}',
              displayName: email['to_name'] as String? ?? email['to_email'] as String,
              email: email['to_email'] as String,
              supportsPqc: true,
            ),
          ],
          subject: email['subject'] as String,
          preview: email['preview'] as String,
          bodyText: email['bodyText'] as String,
          sentAt: DateTime.parse(email['sentAt'] as String),
          isRead: email['isRead'] as bool? ?? false,
          hasAttachments: email['hasAttachments'] as bool? ?? false,
          attachments: const [],
          signatureValid: email['signatureValid'] as bool? ?? false,
          securityLevel: _parseSecurityLevel(email['securityLevel'] as String?),
        );
      }).toList();
      
      return emails;
    }
  } catch (e) {
    print('Error fetching inbox: $e');
  }
  
  return [];
});

SecurityLevel _parseSecurityLevel(String? level) {
  switch (level?.toLowerCase()) {
    case 'pqc':
      return SecurityLevel.pqc;
    case 'classical':
      return SecurityLevel.classical;
    case 'aes_gcm':
    default:
      return SecurityLevel.aesGcm;
  }
}

/// Provider for contacts and address book.
final contactsProvider = Provider<List<Contact>>((ref) {
  // TODO: Implement backend API call to fetch contacts from /contacts
  // For now, returning empty list
  return [];
});

/// Email service provider (talks to Python backend).
final emailServiceProvider =
    Provider<EmailService>((ref) => EmailService());

/// Provider representing aggregated security dashboard data.
class SecurityDashboardState {
  const SecurityDashboardState({
    required this.totalMessages,
    required this.validSignatures,
    required this.failedSignatures,
    required this.pqcContacts,
    required this.classicalOnlyContacts,
  });

  final int totalMessages;
  final int validSignatures;
  final int failedSignatures;
  final int pqcContacts;
  final int classicalOnlyContacts;
}

final securityDashboardProvider =
    Provider<SecurityDashboardState>((ref) {
  // TODO: Fetch real data from backend. Using empty for now.
  return const SecurityDashboardState(
    totalMessages: 0,
    validSignatures: 0,
    failedSignatures: 0,
    pqcContacts: 0,
    classicalOnlyContacts: 0,
  );
});

