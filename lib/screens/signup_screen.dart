import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/auth_models.dart';
import '../providers/auth_providers.dart';

class SignupScreen extends ConsumerStatefulWidget {
  const SignupScreen({
    super.key,
    required this.onSignupSuccess,
    required this.onNavigateToLogin,
  });

  final VoidCallback onSignupSuccess;
  final VoidCallback onNavigateToLogin;

  @override
  ConsumerState<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends ConsumerState<SignupScreen> {
  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authStateProvider);
    final providers = ref.watch(oauthProvidersProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Create Account'),
        elevation: 0,
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SizedBox(height: 24),
                    Text(
                      'Get Started with QMail',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Secure email with quantum-safe encryption awaits you',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: Colors.grey[600],
                          ),
                    ),
                    const SizedBox(height: 32),
                    if (authState.error != null)
                      Container(
                        padding: const EdgeInsets.all(12),
                        margin: const EdgeInsets.only(bottom: 24),
                        decoration: BoxDecoration(
                          color: Colors.red.shade50,
                          border: Border.all(color: Colors.red.shade200),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          authState.error!,
                          style: TextStyle(
                            color: Colors.red.shade700,
                            fontSize: 14,
                          ),
                        ),
                      ),
                    Text(
                      'Create account with',
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    const SizedBox(height: 16),
                    providers.when(
                      data: (providerList) {
                        return Column(
                          children: [
                            ...providerList.map((provider) {
                              return Padding(
                                padding: const EdgeInsets.only(bottom: 12),
                                child: OAuthSignupProviderButton(
                                  provider: provider,
                                  isLoading: authState.isLoading,
                                  onPressed: () =>
                                      _handleProviderSignup(
                                        provider.name,
                                      ),
                                ),
                              );
                            }),
                          ],
                        );
                      },
                      loading: () => const Center(
                        child: CircularProgressIndicator(),
                      ),
                      error: (error, _) => Padding(
                        padding:
                            const EdgeInsets.symmetric(vertical: 24),
                        child: Column(
                          children: [
                            // Default providers
                            Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: OAuthSignupProviderButton(
                                provider: OAuthProvider(
                                  name: 'google',
                                  displayName: 'Google',
                                  iconUrl: '',
                                ),
                                isLoading: authState.isLoading &&
                                    false, // TODO: track provider
                                onPressed: () =>
                                    _handleProviderSignup('google'),
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: OAuthSignupProviderButton(
                                provider: OAuthProvider(
                                  name: 'outlook',
                                  displayName: 'Outlook',
                                  iconUrl: '',
                                ),
                                isLoading: authState.isLoading &&
                                    false, // TODO: track provider
                                onPressed: () =>
                                    _handleProviderSignup('outlook'),
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: OAuthSignupProviderButton(
                                provider: OAuthProvider(
                                  name: 'yahoo',
                                  displayName: 'Yahoo Mail',
                                  iconUrl: '',
                                ),
                                isLoading: authState.isLoading &&
                                    false, // TODO: track provider
                                onPressed: () =>
                                    _handleProviderSignup('yahoo'),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 32),
                    GestureDetector(
                      onTap: widget.onNavigateToLogin,
                      child: Center(
                        child: Text.rich(
                          TextSpan(
                            text: 'Already have an account? ',
                            children: [
                              TextSpan(
                                text: 'Sign in',
                                style: TextStyle(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .primary,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(24),
              child: Align(
                alignment: Alignment.bottomCenter,
                child: Text.rich(
                  TextSpan(
                    text: 'By signing up, you agree to our ',
                    children: [
                      TextSpan(
                        text: 'Terms of Service',
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.primary,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const TextSpan(text: ' and '),
                      TextSpan(
                        text: 'Privacy Policy',
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.primary,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _handleProviderSignup(String providerId) async {
    try {
      final authNotifier = ref.read(authStateProvider.notifier);
      await authNotifier.startLoginFlow(providerId);

      // Show a dialog explaining the user should complete the flow in the browser
      if (mounted) {
        _showOAuthWaitingDialog(context, providerId);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Signup failed: $e')),
        );
      }
    }
  }

  void _showOAuthWaitingDialog(
    BuildContext context,
    String providerId,
  ) {
    final codeController = TextEditingController();
    
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => Consumer(
        builder: (context, ref, child) {
          final authState = ref.watch(authStateProvider);
          final isLoading = authState.isLoading;
          final isAuthenticated = authState.isAuthenticated;
          final error = authState.error;
          
          // Listen for authentication success
          ref.listen(authStateProvider, (previous, next) {
            print('Auth state change - authenticated: ${next.isAuthenticated}');
            if (next.isAuthenticated && Navigator.canPop(context)) {
              print('Closing dialog due to successful authentication');
              Navigator.pop(context);
            }
          });
          
          print('Dialog rebuilt: authenticated=$isAuthenticated, loading=$isLoading');
          
          return AlertDialog(
            title: const Text('Complete Sign-Up'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (isAuthenticated)
                  const Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      CircularProgressIndicator(),
                      SizedBox(height: 16),
                      Text('Authentication successful!'),
                      SizedBox(height: 8),
                      Text('Setting up your account...', style: TextStyle(fontSize: 12)),
                    ],
                  )
                else
                  Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.open_in_browser,
                        size: 48,
                        color: Colors.blue,
                      ),
                      const SizedBox(height: 16),
                      const Text(
                        'A browser window has been opened for you to sign up.',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 16),
                      const Text(
                        'Please complete the sign-up process in your browser. After you sign up, you will be redirected back to this app.',
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 16),
                      const Text(
                        'This dialog will close automatically once sign-up is complete.',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 12, color: Colors.grey),
                      ),
                      const SizedBox(height: 24),
                      const CircularProgressIndicator(),
                      const SizedBox(height: 16),
                      const Text(
                        'Waiting for authorization...',
                        style: TextStyle(fontSize: 12),
                      ),
                      if (error != null) ...[
                        const SizedBox(height: 12),
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Colors.red.shade50,
                            border: Border.all(color: Colors.red.shade200),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            error,
                            style: TextStyle(
                              color: Colors.red.shade700,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ],
                      const SizedBox(height: 16),
                      const Divider(),
                      const SizedBox(height: 16),
                      const Text(
                        'Having trouble? Enter the code manually:',
                        style: TextStyle(fontSize: 12),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: codeController,
                        enabled: !isLoading,
                        decoration: const InputDecoration(
                          hintText: 'Authorization Code',
                          border: OutlineInputBorder(),
                        ),
                        onSubmitted: (code) {
                          if (code.isNotEmpty) {
                            print('Submitting code via Enter: $code');
                            _completeSignup(providerId, code);
                          }
                        },
                      ),
                    ],
                  ),
              ],
            ),
            actions: isAuthenticated
                ? []
                : [
                    TextButton(
                      onPressed: isLoading ? null : () => Navigator.pop(context),
                      child: const Text('Cancel'),
                    ),
                    if (codeController.text.isNotEmpty || isLoading) ...[
                      TextButton(
                        onPressed: isLoading
                            ? null
                            : () {
                                final code = codeController.text.trim();
                                if (code.isEmpty) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                        content: Text('Please enter the authorization code')),
                                  );
                                  return;
                                }
                                print('Sign up button clicked with code: $code');
                                _completeSignup(providerId, code);
                              },
                        child: isLoading
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Text('Sign Up'),
                      ),
                    ],
                  ],
          );
        },
      ),
    ).then((_) {
      codeController.dispose();
    });
  }

  Future<void> _completeSignup(String providerId, String code) async {
    try {
      final authNotifier = ref.read(authStateProvider.notifier);
      await authNotifier.completeLogin(providerId, code);
      if (mounted) {
        widget.onSignupSuccess();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Signup failed: $e')),
        );
      }
    }
  }
}

class OAuthSignupProviderButton extends StatelessWidget {
  const OAuthSignupProviderButton({
    super.key,
    required this.provider,
    required this.isLoading,
    required this.onPressed,
  });

  final OAuthProvider provider;
  final bool isLoading;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final displayName = provider.displayName;
    final iconData = provider.name == 'google'
        ? Icons.g_mobiledata
        : provider.name == 'outlook'
            ? Icons.mail_outline
            : Icons.mail_outline;

    return SizedBox(
      width: double.infinity,
      child: OutlinedButton(
        onPressed: isLoading ? null : onPressed,
        style: OutlinedButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
        child: isLoading
            ? SizedBox(
                height: 20,
                width: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(
                    Theme.of(context).colorScheme.primary,
                  ),
                ),
              )
            : Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(iconData),
                  const SizedBox(width: 12),
                  Text(
                    'Sign up with $displayName',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}
