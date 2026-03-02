/// Authentication service for OAuth2 login and user management.

import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:url_launcher/url_launcher.dart';

import '../models/auth_models.dart';
import 'api_config.dart';

class AuthService {
  AuthService();

  /// Build OAuth authorization URL
  Future<String> buildAuthorizationUrl({
    required String providerId,
    required String redirectUri,
    String? state,
  }) async {
    final uri = Uri.parse(ApiConfig.authAuthorize)
        .replace(queryParameters: {
      'provider': providerId,
      'redirect_uri': redirectUri,
      if (state != null) 'state': state,
    });

    return uri.toString();
  }

  /// Launch OAuth authorization URL in browser/WebView
  Future<bool> launchOAuthUrl(String authUrl) async {
    try {
      final uri = Uri.parse(authUrl);
      if (await canLaunchUrl(uri)) {
        await launchUrl(
          uri,
          mode: LaunchMode.externalApplication,
        );
        return true;
      }
    } catch (e) {
    }
    return false;
  }

  /// Exchange authorization code for tokens
  Future<OAuthToken> exchangeCodeForToken({
    required String providerId,
    required String code,
    required String redirectUri,
  }) async {
    final response = await http.post(
      Uri.parse(ApiConfig.authToken),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'provider': providerId,
        'code': code,
        'redirect_uri': redirectUri,
      }),
    ).timeout(ApiConfig.timeout);

    if (response.statusCode == 200) {
      final data = json.decode(response.body) as Map<String, dynamic>;
      return OAuthToken(
        accessToken: data['access_token'] as String,
        refreshToken: data['refresh_token'] as String?,
        expiresAt: data['expires_at'] != null
            ? DateTime.parse(data['expires_at'] as String)
            : null,
      );
    } else {
      throw Exception('Failed to exchange code for token: ${response.body}');
    }
  }

  /// Get user info using access token
  Future<User> getUserInfo(String accessToken) async {
    final response = await http.get(
      Uri.parse(ApiConfig.authUser),
      headers: {
        'Authorization': 'Bearer $accessToken',
        'Content-Type': 'application/json',
      },
    ).timeout(ApiConfig.timeout);

    if (response.statusCode == 200) {
      final data = json.decode(response.body) as Map<String, dynamic>;
      return User(
        id: data['id'] as String,
        email: data['email'] as String,
        displayName: data['display_name'] as String? ?? data['email'] as String,
        profilePictureUrl: data['profile_picture_url'] as String?,
      );
    } else {
      throw Exception('Failed to fetch user info: ${response.body}');
    }
  }

  /// Refresh access token
  Future<OAuthToken> refreshToken(String refreshToken) async {
    final response = await http.post(
      Uri.parse(ApiConfig.authRefresh),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({'refresh_token': refreshToken}),
    ).timeout(ApiConfig.timeout);

    if (response.statusCode == 200) {
      final data = json.decode(response.body) as Map<String, dynamic>;
      return OAuthToken(
        accessToken: data['access_token'] as String,
        refreshToken: data['refresh_token'] as String? ?? refreshToken,
        expiresAt: data['expires_at'] != null
            ? DateTime.parse(data['expires_at'] as String)
            : null,
      );
    } else {
      throw Exception('Failed to refresh token: ${response.body}');
    }
  }

  /// Get available OAuth providers
  Future<List<OAuthProvider>> getAvailableProviders() async {
    final response = await http.get(
      Uri.parse(ApiConfig.authProviders),
      headers: {'Content-Type': 'application/json'},
    ).timeout(ApiConfig.timeout);

    if (response.statusCode == 200) {
      final data = json.decode(response.body) as List<dynamic>;
      return data
          .map((p) => OAuthProvider(
                name: p['name'] as String,
                displayName: p['display_name'] as String,
                iconUrl: p['icon_url'] as String? ?? '',
                isAvailable: p['available'] as bool? ?? true,
              ))
          .toList();
    } else {
      // Default providers if backend not available
      return [
        const OAuthProvider(
          name: 'google',
          displayName: 'Google',
          iconUrl: 'assets/google_icon.png',
        ),
        const OAuthProvider(
          name: 'gmail',
          displayName: 'Gmail',
          iconUrl: 'assets/gmail_icon.png',
        ),
        const OAuthProvider(
          name: 'outlook',
          displayName: 'Outlook',
          iconUrl: 'assets/outlook_icon.png',
        ),
      ];
    }
  }

  /// Logout
  Future<void> logout() async {
    try {
      await http
          .post(
            Uri.parse(ApiConfig.authLogout),
            headers: {
              'Content-Type': 'application/json',
            },
          )
          .timeout(ApiConfig.timeout);
    } catch (e) {
      // Log but don't fail if logout fails
    }
  }
}
