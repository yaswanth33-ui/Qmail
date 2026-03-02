/// Riverpod providers for authentication state management.

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/auth_models.dart';
import '../services/auth_service.dart';

/// Auth service provider
final authServiceProvider =
    Provider<AuthService>((ref) => AuthService());

/// Authentication state provider
final authStateProvider = NotifierProvider<AuthStateNotifier, AuthState>(
  () => AuthStateNotifier(),
);

class AuthStateNotifier extends Notifier<AuthState> {
  late AuthService _authService;

  @override
  AuthState build() {
    _authService = ref.watch(authServiceProvider);
    // Don't auto-authenticate on startup - require explicit login
    return const AuthState(isAuthenticated: false);
  }

  /// Start OAuth login flow
  Future<void> startLoginFlow(String providerId) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final redirectUri = 'qmail://oauth-callback'; // Deep link
      final authUrl = await _authService.buildAuthorizationUrl(
        providerId: providerId,
        redirectUri: redirectUri,
      );
      
      // Launch the OAuth URL in browser
      final launched = await _authService.launchOAuthUrl(authUrl);
      if (!launched) {
        throw Exception('Failed to launch OAuth URL');
      }
      
      state = state.copyWith(isLoading: false);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: e.toString(),
      );
      rethrow;
    }
  }

  /// Complete OAuth login with authorization code
  Future<void> completeLogin(
    String providerId,
    String code,
  ) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final redirectUri = 'qmail://oauth-callback';
      final token = await _authService.exchangeCodeForToken(
        providerId: providerId,
        code: code,
        redirectUri: redirectUri,
      );

      // Fetch user info from backend to get email
      User? userInfo;
      try {
        userInfo = await _authService.getUserInfo(token.accessToken);
      } catch (e) {
        print('Warning: Could not fetch user info: $e');
        userInfo = User(
          id: 'authenticated-user',
          email: 'user@example.com',
          displayName: 'User',
          profilePictureUrl: null,
        );
      }

      state = AuthState(
        user: userInfo,
        token: token,
        isLoading: false,
        isAuthenticated: true,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: e.toString(),
      );
      rethrow;
    }
  }

  /// Logout
  /// Logout - clears local auth state
  Future<void> logout() async {
    try {
      await _authService.logout();
    } catch (e) {
      print('Logout error: $e');
    } finally {
      state = const AuthState(isAuthenticated: false);
    }
  }

  /// Refresh token if expired
  Future<void> refreshTokenIfNeeded() async {
    final token = state.token;
    if (token == null || !token.isExpired) return;

    if (token.refreshToken == null) {
      state = const AuthState(isAuthenticated: false);
      return;
    }

    try {
      final newToken =
          await _authService.refreshToken(token.refreshToken!);
      state = state.copyWith(token: newToken);
    } catch (e) {
      state = state.copyWith(error: e.toString());
      state = const AuthState(isAuthenticated: false);
    }
  }
}

/// Get available OAuth providers
final oauthProvidersProvider =
    FutureProvider<List<OAuthProvider>>((ref) async {
  return ref.watch(authServiceProvider).getAvailableProviders();
});

/// Check if user is authenticated
final isAuthenticatedProvider = Provider<bool>(
  (ref) => ref.watch(authStateProvider).isAuthenticated,
);

/// Get current user
final currentUserProvider = Provider<User?>(
  (ref) => ref.watch(authStateProvider).user,
);
