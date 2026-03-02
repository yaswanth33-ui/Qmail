import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../screens/compose_screen.dart';
import '../screens/inbox_screen.dart';
import '../screens/message_view_screen.dart';
import '../screens/profile_screen.dart';
import '../screens/qmail_signup_screen.dart';
import '../screens/qmail_login_screen.dart';
import '../screens/password_reset_screen.dart';
import '../providers/auth_providers.dart';

/// Custom page with fade-slide transition animation
class AnimatedPage<T> extends Page<T> {
  const AnimatedPage({
    required this.child,
    super.key,
    super.name,
  });

  final Widget child;

  @override
  Route<T> createRoute(BuildContext context) {
    return PageRouteBuilder<T>(
      settings: this,
      pageBuilder: (context, animation, secondaryAnimation) => child,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        const curve = Curves.easeOutCubic;
        final curvedAnimation = CurvedAnimation(
          parent: animation,
          curve: curve,
        );
        
        return FadeTransition(
          opacity: curvedAnimation,
          child: SlideTransition(
            position: Tween<Offset>(
              begin: const Offset(0.05, 0),
              end: Offset.zero,
            ).animate(curvedAnimation),
            child: child,
          ),
        );
      },
      transitionDuration: const Duration(milliseconds: 300),
      reverseTransitionDuration: const Duration(milliseconds: 250),
    );
  }
}

/// Simple route paths for Navigator 2.0 configuration.
class AppRoutePath {
  const AppRoutePath._(this.location, {this.messageId, this.draftId, this.draftRecipient, this.draftSubject, this.draftBody, this.replyToId, this.isForward = false});

  const AppRoutePath.login() : this._('/login');

  const AppRoutePath.signup() : this._('/signup');

  const AppRoutePath.passwordReset() : this._('/password-reset');

  const AppRoutePath.inbox() : this._('/inbox');

  const AppRoutePath.compose() : this._('/compose');
  
  const AppRoutePath.composeWithDraft(String id, String recipient, String subject, String body)
      : this._('/compose', draftId: id, draftRecipient: recipient, draftSubject: subject, draftBody: body);

  const AppRoutePath.composeReply({required String recipient, required String subject, required String body, required String replyToId})
      : this._('/compose', draftRecipient: recipient, draftSubject: subject, draftBody: body, replyToId: replyToId);

  const AppRoutePath.composeForward({required String subject, required String body})
      : this._('/compose', draftSubject: subject, draftBody: body, isForward: true);

  const AppRoutePath.profile() : this._('/profile');

  const AppRoutePath.message(String id)
      : this._('/message/$id', messageId: id);

  final String location;
  final String? messageId;
  final String? draftId;
  final String? draftRecipient;
  final String? draftSubject;
  final String? draftBody;
  final String? replyToId;
  final bool isForward;

  bool get isLogin => location == '/login';

  bool get isSignup => location == '/signup';

  bool get isPasswordReset => location == '/password-reset';

  bool get isInbox => location == '/inbox';

  bool get isCompose => location == '/compose';

  bool get isProfile => location == '/profile';

  bool get isMessage => messageId != null;
  
  bool get isDraftEdit => draftId != null;
  
  bool get isReply => replyToId != null;
}

class AppRouteInformationParser
    extends RouteInformationParser<AppRoutePath> {
  @override
  Future<AppRoutePath> parseRouteInformation(
      RouteInformation routeInformation) async {
    final uri = Uri.parse(routeInformation.location ?? '/inbox');
    if (uri.pathSegments.isEmpty) {
      return const AppRoutePath.inbox();
    }

    switch (uri.pathSegments.first) {
      case 'login':
        return const AppRoutePath.login();
      case 'signup':
        return const AppRoutePath.signup();
      case 'password-reset':
        return const AppRoutePath.passwordReset();
      case 'compose':
        return const AppRoutePath.compose();
      case 'profile':
        return const AppRoutePath.profile();
      case 'message':
        if (uri.pathSegments.length >= 2) {
          return AppRoutePath.message(uri.pathSegments[1]);
        }
        return const AppRoutePath.inbox();
      case 'inbox':
      default:
        return const AppRoutePath.inbox();
    }
  }

  @override
  RouteInformation? restoreRouteInformation(AppRoutePath configuration) {
    return RouteInformation(location: configuration.location);
  }
}

class AppRouterDelegate extends RouterDelegate<AppRoutePath>
    with ChangeNotifier, PopNavigatorRouterDelegateMixin<AppRoutePath> {
  AppRouterDelegate(this.ref);

  final Ref ref;

  @override
  final GlobalKey<NavigatorState> navigatorKey =
      GlobalKey<NavigatorState>();

  AppRoutePath _currentPath = const AppRoutePath.login();

  @override
  AppRoutePath get currentConfiguration => _currentPath;

  void _setPath(AppRoutePath path) {
    _currentPath = path;
    notifyListeners();
  }

  void goToLogin() => _setPath(const AppRoutePath.login());

  void goToSignup() => _setPath(const AppRoutePath.signup());

  void goToPasswordReset() => _setPath(const AppRoutePath.passwordReset());

  void goToInbox() => _setPath(const AppRoutePath.inbox());

  void goToCompose() => _setPath(const AppRoutePath.compose());
  
  void goToComposeWithDraft(String id, String recipient, String subject, String body) =>
      _setPath(AppRoutePath.composeWithDraft(id, recipient, subject, body));

  void goToReply({required String recipient, required String subject, required String body, required String replyToId}) =>
      _setPath(AppRoutePath.composeReply(recipient: recipient, subject: subject, body: body, replyToId: replyToId));

  void goToForward({required String subject, required String body}) =>
      _setPath(AppRoutePath.composeForward(subject: subject, body: body));

  void goToProfile() => _setPath(const AppRoutePath.profile());

  void openMessage(String id) =>
      _setPath(AppRoutePath.message(id));

  @override
  Future<void> setNewRoutePath(AppRoutePath configuration) async {
    _currentPath = configuration;
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authStateProvider);
    final isAuthenticated = authState.isAuthenticated;

    // If not authenticated, show login/signup screens
    if (!isAuthenticated) {
      return Navigator(
        key: navigatorKey,
        pages: [
          if (_currentPath.isPasswordReset)
            AnimatedPage(
              key: const ValueKey('password-reset'),
              child: PasswordResetScreen(
                onResetSuccess: goToLogin,
                onNavigateToLogin: goToLogin,
              ),
            )
          else if (_currentPath.isSignup)
            AnimatedPage(
              key: const ValueKey('signup'),
              child: QmailSignupScreen(
                onSignupSuccess: goToInbox,
                onNavigateToLogin: goToLogin,
              ),
            )
          else
            AnimatedPage(
              key: const ValueKey('login'),
              child: QmailLoginScreen(
                onLoginSuccess: goToInbox,
                onNavigateToSignup: goToSignup,
                onNavigateToPasswordReset: goToPasswordReset,
              ),
            ),
        ],
        onPopPage: (route, result) {
          return route.didPop(result);
        },
      );
    }

    // If authenticated, show app screens
    return Navigator(
      key: navigatorKey,
      pages: [
        AnimatedPage(
          key: const ValueKey('inbox'),
          child: InboxScreen(
            onCompose: goToCompose,
            onOpenProfile: goToProfile,
            onOpenMessage: openMessage,
            onOpenDraft: goToComposeWithDraft,
          ),
        ),
        if (_currentPath.isMessage && _currentPath.messageId != null)
          AnimatedPage(
            key: ValueKey('message-${_currentPath.messageId}'),
            child: MessageViewScreen(
              messageId: _currentPath.messageId!,
              onReply: ({required String recipient, required String subject, required String body, required String replyToId}) =>
                  goToReply(recipient: recipient, subject: subject, body: body, replyToId: replyToId),
              onForward: ({required String subject, required String body}) =>
                  goToForward(subject: subject, body: body),
            ),
          ),
        if (_currentPath.isCompose)
          AnimatedPage(
            key: ValueKey('compose-${_currentPath.draftId ?? "new"}'),
            child: ComposeScreen(
              onClose: goToInbox,
              draftId: _currentPath.draftId,
              initialRecipient: _currentPath.draftRecipient,
              initialSubject: _currentPath.draftSubject,
              initialBody: _currentPath.draftBody,
              replyToId: _currentPath.replyToId,
              isForward: _currentPath.isForward,
            ),
          ),
        if (_currentPath.isProfile)
          AnimatedPage(
            key: const ValueKey('profile'),
            child: ProfileScreen(
              onBack: goToInbox,
            ),
          ),
      ],
      onPopPage: (route, result) {
        if (!route.didPop(result)) {
          return false;
        }
        if (_currentPath.isMessage ||
            _currentPath.isCompose ||
            _currentPath.isProfile) {
          _setPath(const AppRoutePath.inbox());
        }
        return true;
      },
    );
  }
}

/// Riverpod provider that exposes a RouterConfig using Navigator 2.0.
final appRouterProvider = Provider<RouterConfig<AppRoutePath>>((ref) {
  final delegate = AppRouterDelegate(ref);
  return RouterConfig<AppRoutePath>(
    routerDelegate: delegate,
    routeInformationProvider: PlatformRouteInformationProvider(
      initialRouteInformation: const RouteInformation(location: '/inbox'),
    ),
    routeInformationParser: AppRouteInformationParser(),
  );
});

