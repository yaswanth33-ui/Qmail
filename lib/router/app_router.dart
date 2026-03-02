import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../screens/compose_screen.dart';
import '../screens/contacts_screen.dart';
import '../screens/inbox_screen.dart';
import '../screens/message_view_screen.dart';
import '../screens/security_dashboard_screen.dart';
import '../screens/login_screen.dart';
import '../screens/signup_screen.dart';
import '../providers/auth_providers.dart';

/// Simple route paths for Navigator 2.0 configuration.
class AppRoutePath {
  const AppRoutePath._(this.location, {this.messageId});

  const AppRoutePath.login() : this._('/login');

  const AppRoutePath.signup() : this._('/signup');

  const AppRoutePath.inbox() : this._('/inbox');

  const AppRoutePath.compose() : this._('/compose');

  const AppRoutePath.contacts() : this._('/contacts');

  const AppRoutePath.security() : this._('/security');

  const AppRoutePath.message(String id)
      : this._('/message/$id', messageId: id);

  final String location;
  final String? messageId;

  bool get isLogin => location == '/login';

  bool get isSignup => location == '/signup';

  bool get isInbox => location == '/inbox';

  bool get isCompose => location == '/compose';

  bool get isContacts => location == '/contacts';

  bool get isSecurity => location == '/security';

  bool get isMessage => messageId != null;
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
      case 'compose':
        return const AppRoutePath.compose();
      case 'contacts':
        return const AppRoutePath.contacts();
      case 'security':
        return const AppRoutePath.security();
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

  void goToInbox() => _setPath(const AppRoutePath.inbox());

  void goToCompose() => _setPath(const AppRoutePath.compose());

  void goToContacts() => _setPath(const AppRoutePath.contacts());

  void goToSecurity() => _setPath(const AppRoutePath.security());

  void openMessage(String id) =>
      _setPath(AppRoutePath.message(id));

  @override
  Future<void> setNewRoutePath(AppRoutePath configuration) async {
    _currentPath = configuration;
  }

  @override
  Widget build(BuildContext context) {
    final isAuthenticated = ref.watch(isAuthenticatedProvider);

    // If not authenticated, show login/signup screens
    if (!isAuthenticated) {
      return Navigator(
        key: navigatorKey,
        pages: [
          if (_currentPath.isSignup)
            MaterialPage(
              key: const ValueKey('signup'),
              child: SignupScreen(
                onSignupSuccess: goToInbox,
                onNavigateToLogin: goToLogin,
              ),
            )
          else
            MaterialPage(
              key: const ValueKey('login'),
              child: LoginScreen(
                onLoginSuccess: goToInbox,
                onNavigateToSignup: goToSignup,
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
        MaterialPage(
          key: const ValueKey('inbox'),
          child: InboxScreen(
            onCompose: goToCompose,
            onOpenContacts: goToContacts,
            onOpenSecurity: goToSecurity,
            onOpenMessage: openMessage,
          ),
        ),
        if (_currentPath.isMessage && _currentPath.messageId != null)
          MaterialPage(
            key: ValueKey('message-${_currentPath.messageId}'),
            child: MessageViewScreen(
              messageId: _currentPath.messageId!,
              onReply: goToCompose,
            ),
          ),
        if (_currentPath.isCompose)
          MaterialPage(
            key: const ValueKey('compose'),
            child: ComposeScreen(
              onClose: goToInbox,
            ),
          ),
        if (_currentPath.isContacts)
          MaterialPage(
            key: const ValueKey('contacts'),
            child: ContactsScreen(
              onBack: goToInbox,
            ),
          ),
        if (_currentPath.isSecurity)
          MaterialPage(
            key: const ValueKey('security'),
            child: SecurityDashboardScreen(
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
            _currentPath.isContacts ||
            _currentPath.isSecurity) {
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

