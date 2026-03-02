/// Authentication models for OAuth2 login and signup.

class OAuthToken {
  const OAuthToken({
    required this.accessToken,
    this.refreshToken,
    this.expiresAt,
  });

  final String accessToken;
  final String? refreshToken;
  final DateTime? expiresAt;

  bool get isExpired {
    if (expiresAt == null) return false;
    return DateTime.now().add(const Duration(seconds: 30)).isAfter(expiresAt!);
  }
}

class User {
  const User({
    required this.id,
    required this.email,
    required this.displayName,
    this.profilePictureUrl,
  });

  final String id;
  final String email;
  final String displayName;
  final String? profilePictureUrl;
}

class OAuthProvider {
  const OAuthProvider({
    required this.name,
    required this.displayName,
    required this.iconUrl,
    this.isAvailable = true,
  });

  final String name;
  final String displayName;
  final String iconUrl;
  final bool isAvailable;
}

class AuthState {
  const AuthState({
    this.user,
    this.token,
    this.isLoading = false,
    this.error,
    this.isAuthenticated = false,
  });

  final User? user;
  final OAuthToken? token;
  final bool isLoading;
  final String? error;
  final bool isAuthenticated;

  AuthState copyWith({
    User? user,
    OAuthToken? token,
    bool? isLoading,
    String? error,
    bool? isAuthenticated,
  }) {
    return AuthState(
      user: user ?? this.user,
      token: token ?? this.token,
      isLoading: isLoading ?? this.isLoading,
      error: error,
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
    );
  }
}
