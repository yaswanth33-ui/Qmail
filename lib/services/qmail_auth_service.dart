/// Qmail Phone-Based Authentication Service
/// 
/// Replaces Firebase with custom @qmail.com account system.
/// 
/// SIGNUP FLOW:
/// 1. Request OTP with name, DOB, phone → returns session_id
/// 2. Verify OTP + create account → returns temp token + @qmail address
/// 3. Set password → account ready for login
/// 4. Login with email/password → returns access & refresh tokens
/// 
/// All communication is with Qmail backend API (not Firebase).

import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:io' show Platform;

import '../models/auth_models.dart';
import 'api_config.dart';

class QmailUser {
  final String userId;
  final String qmailAddress;
  final String username;
  final String name;
  final String dateOfBirth;
  final String phoneNumber; // Masked
  final DateTime accountCreatedAt;
  final DateTime? lastLoginAt;
  final bool isVerified;

  QmailUser({
    required this.userId,
    required this.qmailAddress,
    required this.username,
    required this.name,
    required this.dateOfBirth,
    required this.phoneNumber,
    required this.accountCreatedAt,
    this.lastLoginAt,
    required this.isVerified,
  });

  factory QmailUser.fromJson(Map<String, dynamic> json) => QmailUser(
    userId: json['user_id'] ?? '',
    qmailAddress: json['qmail_address'] ?? '',
    username: json['username'] ?? '',
    name: json['name'] ?? '',
    dateOfBirth: json['date_of_birth'] ?? '',
    phoneNumber: json['phone_number'] ?? '',
    accountCreatedAt: DateTime.parse(json['account_created_at'] ?? DateTime.now().toIso8601String()),
    lastLoginAt: json['last_login_at'] != null ? DateTime.parse(json['last_login_at']) : null,
    isVerified: json['is_verified'] ?? false,
  );

  Map<String, dynamic> toJson() => {
    'user_id': userId,
    'qmail_address': qmailAddress,
    'username': username,
    'name': name,
    'date_of_birth': dateOfBirth,
    'phone_number': phoneNumber,
    'account_created_at': accountCreatedAt.toIso8601String(),
    'last_login_at': lastLoginAt?.toIso8601String(),
    'is_verified': isVerified,
  };
}

class AuthSession {
  final String? accessToken;
  final String? refreshToken;
  final QmailUser? user;
  final int? expiresInSeconds;

  AuthSession({
    this.accessToken,
    this.refreshToken,
    this.user,
    this.expiresInSeconds,
  });

  bool get isValid => accessToken != null && user != null;
}

class OtpRequestResponse {
  final String otpSessionId;
  final String phoneMasked;
  final int expiresInSeconds;

  OtpRequestResponse({
    required this.otpSessionId,
    required this.phoneMasked,
    required this.expiresInSeconds,
  });

  factory OtpRequestResponse.fromJson(Map<String, dynamic> json) => OtpRequestResponse(
    otpSessionId: json['otp_session_id'] ?? '',
    phoneMasked: json['phone_masked'] ?? '',
    expiresInSeconds: json['expires_in_seconds'] ?? 600,
  );
}

class OtpVerifyResponse {
  final String userId;
  final String qmailAddress;
  final String temporaryAuthToken;
  final String name;

  OtpVerifyResponse({
    required this.userId,
    required this.qmailAddress,
    required this.temporaryAuthToken,
    required this.name,
  });

  factory OtpVerifyResponse.fromJson(Map<String, dynamic> json) => OtpVerifyResponse(
    userId: json['user_id'] ?? '',
    qmailAddress: json['qmail_address'] ?? '',
    temporaryAuthToken: json['temporary_auth_token'] ?? '',
    name: json['name'] ?? '',
  );
}

class QmailAuthService {
  static final QmailAuthService _instance = QmailAuthService._internal();

  factory QmailAuthService() {
    return _instance;
  }

  QmailAuthService._internal();

  String? _accessToken;
  String? _refreshToken;
  QmailUser? _currentUser;

  /// Get stored access token
  String? get accessToken => _accessToken;

  /// Get stored refresh token
  String? get refreshToken => _refreshToken;

  /// Get current authenticated user
  QmailUser? get currentUser => _currentUser;

  /// Check if user is authenticated
  bool get isAuthenticated => _accessToken != null && _currentUser != null;

  /// HTTP headers for API calls
  Map<String, String> _getHeaders({bool useAuthToken = false}) {
    final headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };

    if (useAuthToken && _accessToken != null) {
      headers['Authorization'] = 'Bearer $_accessToken';
    }

    return headers;
  }

  /// Format phone number to E.164 format
  /// Input: "1234567890" or "+11234567890" or "1-234-567-8900"
  /// Output: "+11234567890"
  static String formatPhoneE164(String phone, {String dialCode = '+1'}) {
    // Remove all non-digit characters except +
    String cleaned = phone.replaceAll(RegExp(r'[^\d+]'), '');

    // If it already starts with +, keep it as-is (user provided full international format)
    if (cleaned.startsWith('+')) {
      return cleaned;
    }

    // If the dialCode is already in the cleaned number, don't add it again
    String dialCodeDigits = dialCode.replaceAll('+', '');
    if (cleaned.startsWith(dialCodeDigits)) {
      return '+$cleaned';
    }

    // Otherwise, prepend the dial code
    return '$dialCode$cleaned';
  }

  /// Get dial code for country code
  static String getDialCode(String countryCode) {
    const Map<String, String> dialCodes = {
      'US': '+1',
      'CA': '+1',
      'IN': '+91',
      'GB': '+44',
      'AU': '+61',
      'DE': '+49',
      'FR': '+33',
      'JP': '+81',
      'CN': '+86',
      'BR': '+55',
      'MX': '+52',
    };
    return dialCodes[countryCode] ?? '+1';
  }

  /// Error handler for API responses
  String _parseErrorMessage(dynamic error) {
    if (error is String) {
      return error;
    }

    if (error is Map) {
      return error['message'] ?? error['detail'] ?? 'Unknown error occurred';
    }

    return error.toString();
  }

  // ================================================================
  // SIGNUP FLOW METHODS
  // ================================================================

  /// Check if username is available for registration
  /// 
  /// Returns a map with 'available' (bool), 'username' (String),
  /// and optionally 'suggestion' (String) if username is taken
  Future<Map<String, dynamic>> checkUsernameAvailability(String username) async {
    try {
      final response = await http.get(
        Uri.parse('${ApiConfig.authBaseUrl}/phone/check-username/${Uri.encodeComponent(username)}'),
        headers: _getHeaders(),
      ).timeout(
        const Duration(seconds: 10),
        onTimeout: () => throw TimeoutException('Check username timeout'),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else if (response.statusCode == 400) {
        final error = json.decode(response.body);
        throw _parseErrorMessage(error);
      } else {
        throw Exception('Failed to check username availability');
      }
    } catch (e) {
      throw Exception('Failed to check username: $e');
    }
  }

  /// Step 1: Request OTP to phone number
  /// 
  /// Returns OTP session ID needed for verification
  Future<OtpRequestResponse> requestOtp({
    required String name,
    required DateTime dateOfBirth,
    required String phoneNumber,
    String countryCode = 'US',
  }) async {
    try {
      final dialCode = getDialCode(countryCode);
      final formattedPhone = formatPhoneE164(phoneNumber, dialCode: dialCode);

      final response = await http.post(
        Uri.parse('${ApiConfig.authBaseUrl}/phone/request-otp'),
        headers: _getHeaders(),
        body: jsonEncode({
          'name': name,
          'date_of_birth': dateOfBirth.toString().split(' ')[0], // YYYY-MM-DD
          'phone_number': formattedPhone,
          'country_code': countryCode,
        }),
      ).timeout(
        const Duration(seconds: 30),
        onTimeout: () => throw TimeoutException('Request OTP timeout'),
      );

      if (response.statusCode == 200) {
        return OtpRequestResponse.fromJson(json.decode(response.body));
      } else if (response.statusCode == 409) {
        // Phone number already registered
        final error = json.decode(response.body);
        throw _parseErrorMessage(error);
      } else {
        final error = json.decode(response.body);
        throw _parseErrorMessage(error);
      }
    } catch (e) {
      throw Exception('Failed to request OTP: $e');
    }
  }

  /// Step 2: Verify OTP and create account
  /// 
  /// Returns temporary token for setting password
  Future<OtpVerifyResponse> verifyOtp({
    required String otpSessionId,
    required String otpCode,
    required String desiredUsername,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.authBaseUrl}/phone/verify-otp'),
        headers: _getHeaders(),
        body: jsonEncode({
          'otp_session_id': otpSessionId,
          'otp_code': otpCode,
          'desired_username': desiredUsername,
        }),
      ).timeout(
        const Duration(seconds: 30),
        onTimeout: () => throw TimeoutException('Verify OTP timeout'),
      );

      if (response.statusCode == 200) {
        return OtpVerifyResponse.fromJson(json.decode(response.body));
      } else if (response.statusCode == 409) {
        // Username or phone already taken
        final error = json.decode(response.body);
        throw _parseErrorMessage(error);
      } else {
        final error = json.decode(response.body);
        throw _parseErrorMessage(error);
      }
    } catch (e) {
      throw Exception('Failed to verify OTP: $e');
    }
  }

  /// Step 3: Set password for new account
  /// 
  /// Uses temporary token from verifyOtp
  Future<void> setPassword({
    required String temporaryAuthToken,
    required String password,
    required String confirmPassword,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.authBaseUrl}/phone/set-password'),
        headers: _getHeaders(),
        body: jsonEncode({
          'temporary_auth_token': temporaryAuthToken,
          'password': password,
          'confirm_password': confirmPassword,
        }),
      ).timeout(
        const Duration(seconds: 30),
        onTimeout: () => throw TimeoutException('Set password timeout'),
      );

      if (response.statusCode != 200) {
        final error = json.decode(response.body);
        throw _parseErrorMessage(error);
      }
    } catch (e) {
      throw Exception('Failed to set password: $e');
    }
  }

  // ================================================================
  // LOGIN METHODS
  // ================================================================

  /// Login with @qmail.com email and password
  /// 
  /// Email can be either "username@qmail.com" or just "username"
  Future<AuthSession> login({
    required String email,
    required String password,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.authBaseUrl}/phone/login'),
        headers: _getHeaders(),
        body: jsonEncode({
          'email': email,
          'password': password,
        }),
      ).timeout(
        const Duration(seconds: 30),
        onTimeout: () => throw TimeoutException('Login timeout'),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);

        _accessToken = data['access_token'];
        _refreshToken = data['refresh_token'];
        _currentUser = QmailUser.fromJson(data['user']);

        return AuthSession(
          accessToken: _accessToken,
          refreshToken: _refreshToken,
          user: _currentUser,
          expiresInSeconds: data['expires_in_seconds'],
        );
      } else {
        final error = json.decode(response.body);
        throw _parseErrorMessage(error);
      }
    } catch (e) {
      throw Exception('Login failed: $e');
    }
  }

  /// Refresh access token using refresh token
  Future<AuthSession> refreshAccessToken() async {
    if (_refreshToken == null) {
      throw Exception('No refresh token available');
    }

    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.authBaseUrl}/phone/refresh'),
        headers: _getHeaders(),
        body: jsonEncode({
          'refresh_token': _refreshToken,
        }),
      ).timeout(
        const Duration(seconds: 30),
        onTimeout: () => throw TimeoutException('Refresh token timeout'),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);

        _accessToken = data['access_token'];
        _currentUser = QmailUser.fromJson(data['user']);

        return AuthSession(
          accessToken: _accessToken,
          refreshToken: _refreshToken,
          user: _currentUser,
          expiresInSeconds: data['expires_in_seconds'],
        );
      } else {
        throw Exception('Failed to refresh token');
      }
    } catch (e) {
      throw Exception('Refresh failed: $e');
    }
  }

  /// Get current user info
  Future<QmailUser> getCurrentUserInfo() async {
    try {
      final response = await http.get(
        Uri.parse('${ApiConfig.authBaseUrl}/phone/me'),
        headers: _getHeaders(useAuthToken: true),
      ).timeout(
        const Duration(seconds: 30),
        onTimeout: () => throw TimeoutException('Get user timeout'),
      );

      if (response.statusCode == 200) {
        _currentUser = QmailUser.fromJson(json.decode(response.body));
        return _currentUser!;
      } else {
        throw Exception('Failed to fetch user info');
      }
    } catch (e) {
      throw Exception('Get user failed: $e');
    }
  }

  /// Logout
  Future<void> logout() async {
    try {
      await http.post(
        Uri.parse('${ApiConfig.authBaseUrl}/phone/logout'),
        headers: _getHeaders(useAuthToken: true),
      ).timeout(
        const Duration(seconds: 30),
        onTimeout: () => throw TimeoutException('Logout timeout'),
      );
    } finally {
      // Clear local tokens regardless of API response
      _accessToken = null;
      _refreshToken = null;
      _currentUser = null;
    }
  }

  // ================================================================
  // PASSWORD RESET METHODS
  // ================================================================

  /// Request password reset OTP
  /// 
  /// User provides email, username, or phone number
  /// OTP is sent to registered phone number
  Future<Map<String, dynamic>> requestPasswordReset(String identifier) async {
    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.authBaseUrl}/phone/forgot-password'),
        headers: _getHeaders(),
        body: jsonEncode({
          'identifier': identifier,
        }),
      ).timeout(
        const Duration(seconds: 30),
        onTimeout: () => throw TimeoutException('Request timeout'),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else if (response.statusCode == 404) {
        final error = json.decode(response.body);
        throw _parseErrorMessage(error);
      } else {
        final error = json.decode(response.body);
        throw _parseErrorMessage(error);
      }
    } catch (e) {
      throw Exception('Failed to request password reset: $e');
    }
  }

  /// Verify password reset OTP
  /// 
  /// Returns reset token for changing password
  Future<Map<String, dynamic>> verifyResetOtp({
    required String resetSessionId,
    required String otpCode,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.authBaseUrl}/phone/verify-reset-otp'),
        headers: _getHeaders(),
        body: jsonEncode({
          'reset_session_id': resetSessionId,
          'otp_code': otpCode,
        }),
      ).timeout(
        const Duration(seconds: 30),
        onTimeout: () => throw TimeoutException('Verify timeout'),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        final error = json.decode(response.body);
        throw _parseErrorMessage(error);
      }
    } catch (e) {
      throw Exception('Failed to verify reset OTP: $e');
    }
  }

  /// Reset password with verified token
  Future<void> resetPassword({
    required String resetToken,
    required String newPassword,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.authBaseUrl}/phone/reset-password'),
        headers: _getHeaders(),
        body: jsonEncode({
          'reset_token': resetToken,
          'new_password': newPassword,
        }),
      ).timeout(
        const Duration(seconds: 30),
        onTimeout: () => throw TimeoutException('Reset timeout'),
      );

      if (response.statusCode == 200) {
        return; // Success
      } else {
        final error = json.decode(response.body);
        throw _parseErrorMessage(error);
      }
    } catch (e) {
      throw Exception('Failed to reset password: $e');
    }
  }

  /// Clear all stored authentication data
  void clearSession() {
    _accessToken = null;
    _refreshToken = null;
    _currentUser = null;
  }
}

class TimeoutException implements Exception {
  final String message;
  TimeoutException(this.message);

  @override
  String toString() => 'TimeoutException: $message';
}
