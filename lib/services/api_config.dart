/// API Configuration for Qmail Backend Connection
///
/// This file centralizes all backend API configuration to ensure
/// consistent connection between Flutter frontend and FastAPI backend.

import 'package:flutter_dotenv/flutter_dotenv.dart';

class ApiConfig {
  /// Base URL for the Qmail API server.
  ///
  /// Development: http://localhost:5000
  /// Production: https://qmail-api.onrender.com
  static String get baseUrl => dotenv.env['API_BASE_URL'] ?? 'https://qmail-api.onrender.com';

  /// Connection timeout for API requests
  static const Duration timeout = Duration(seconds: 30);

  /// Auth endpoints (OAuth - optional)
  static String get authProviders => '$baseUrl/auth/oauth/providers';
  static String get authAuthorize => '$baseUrl/auth/oauth/authorize';
  static String get authToken => '$baseUrl/auth/oauth/token';
  static String get authRefresh => '$baseUrl/auth/oauth/refresh';
  static String get authUser => '$baseUrl/auth/user';
  static String get authLogout => '$baseUrl/auth/logout';

  /// Phone authentication base URL
  static String get authBaseUrl => '$baseUrl/auth';

  /// Firebase auth endpoints
  static String get firebaseConfig => '$baseUrl/auth/firebase/config';
  static String get firebaseVerify => '$baseUrl/auth/firebase/verify';
  static String get firebaseMe => '$baseUrl/auth/me';

  /// Email endpoints
  static String get emailSend => '$baseUrl/email/send';
  static String get emailInbox => '$baseUrl/email/inbox';
  static String get emailSync => '$baseUrl/email/sync';
  static String get emailRefresh => '$baseUrl/email/refresh';
  static String get emailDraft => '$baseUrl/email/draft';
  static String get emailTrash => '$baseUrl/email/trash';
  static String get emailRestore => '$baseUrl/email/restore';
  static String emailOpen(String id) => '$baseUrl/email/$id/open';
  static String emailDelete(String id) => '$baseUrl/email/$id';

  /// Message broker endpoints (WhatsApp-style)
  static String get messagesSend => '$baseUrl/messages/send';
  static String get messagesPending => '$baseUrl/messages/pending';
  static String messageDownload(String id) => '$baseUrl/messages/$id/download';
  static String messageAck(String id) => '$baseUrl/messages/$id/ack';
}
