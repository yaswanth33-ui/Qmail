/// Authentication Providers for Qmail Phone Authentication
/// 
/// Provides authentication state management for phone-verified accounts
/// with @qmail.com addresses.

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/qmail_auth_service.dart';

/// Token information for authenticated sessions
class AuthToken {
  final String accessToken;
  final String? refreshToken;
  
  const AuthToken({
    required this.accessToken,
    this.refreshToken,
  });
}

/// Authentication state
class AuthState {
  final bool isAuthenticated;
  final QmailUser? user;
  final AuthToken? token;
  
  const AuthState({
    required this.isAuthenticated,
    this.user,
    this.token,
  });
  
  const AuthState.unauthenticated() : isAuthenticated = false, user = null, token = null;
  
  const AuthState.authenticated(this.user, this.token) : isAuthenticated = true;
}

/// Auth service provider
final qmailAuthServiceProvider = Provider<QmailAuthService>((ref) {
  return QmailAuthService();
});

/// Notifier for managing auth state
class AuthStateNotifier extends Notifier<AuthState> {
  final _authService = QmailAuthService();
  
  @override
  AuthState build() {
    // Initialize with unauthenticated state
    // Check auth status asynchronously
    _checkAuthStatus();
    return const AuthState.unauthenticated();
  }
  
  Future<void> _checkAuthStatus() async {
    // Check if user has stored tokens
    if (_authService.isAuthenticated && _authService.currentUser != null) {
      final user = _authService.currentUser!;
      final token = AuthToken(
        accessToken: _authService.accessToken!,
        refreshToken: _authService.refreshToken,
      );
      state = AuthState.authenticated(user, token);
    }
  }
  
  Future<void> login(String email, String password) async {
    final session = await _authService.login(email: email, password: password);
    final token = AuthToken(
      accessToken: session.accessToken ?? '',
      refreshToken: session.refreshToken,
    );
    state = AuthState.authenticated(session.user, token);
  }
  
  Future<void> logout() async {
    await _authService.logout();
    state = const AuthState.unauthenticated();
  }
  
  void setUser(QmailUser user) {
    final token = _authService.accessToken != null
        ? AuthToken(
            accessToken: _authService.accessToken!,
            refreshToken: _authService.refreshToken,
          )
        : null;
    state = AuthState.authenticated(user, token);
  }
}

/// Provider for auth state
final authStateProvider = NotifierProvider<AuthStateNotifier, AuthState>(() {
  return AuthStateNotifier();
});

