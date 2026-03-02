/// Qmail @qmail.com Login Screen
/// 
/// This screen handles login for users with existing @qmail.com accounts
/// created through the phone-verified signup flow.
///

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../services/qmail_auth_service.dart';
import '../../providers/auth_providers.dart';

class QmailLoginScreen extends ConsumerStatefulWidget {
  const QmailLoginScreen({
    Key? key,
    this.onLoginSuccess,
    this.onNavigateToSignup,
    this.onNavigateToPasswordReset,
  }) : super(key: key);

  final VoidCallback? onLoginSuccess;
  final VoidCallback? onNavigateToSignup;
  final VoidCallback? onNavigateToPasswordReset;

  @override
  ConsumerState<QmailLoginScreen> createState() => _QmailLoginScreenState();
}

class _QmailLoginScreenState extends ConsumerState<QmailLoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isLoading = false;
  bool _passwordVisible = false;
  String _errorMessage = '';

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _setError(String message) {
    setState(() => _errorMessage = message);
    Future.delayed(const Duration(seconds: 5), () {
      if (mounted) setState(() => _errorMessage = '');
    });
  }

  Future<void> _handleLogin() async {
    if (_emailController.text.isEmpty) {
      _setError('Please enter your email or username');
      return;
    }
    if (_passwordController.text.isEmpty) {
      _setError('Please enter your password');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      // Use the auth provider's login method to update state
      await ref.read(authStateProvider.notifier).login(
        _emailController.text,
        _passwordController.text,
      );

      if (mounted) {
        // Auth state is now updated, navigate to inbox
        widget.onLoginSuccess?.call();
      }
    } catch (e) {
      _setError('Login failed: $e');
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Qumail Login'),
        centerTitle: true,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            const SizedBox(height: 32),

            // Qmail logo/branding
            ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: Image.asset(
                'assets/images/qumail_logo.png',
                width: 120,
                height: 120,
                fit: BoxFit.contain,
              ),
            ),

            const SizedBox(height: 24),

            Text(
              'Welcome Back',
              style: Theme.of(context).textTheme.headlineSmall,
              textAlign: TextAlign.center,
            ),

            const SizedBox(height: 8),

            Text(
              'Login to your @qmail.com account',
              style: Theme.of(context).textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ),

            const SizedBox(height: 32),

            // Error message
            if (_errorMessage.isNotEmpty)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.red.shade100,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.red.shade400),
                ),
                child: Row(
                  children: [
                    Icon(Icons.error_outline, color: Colors.red.shade700),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        _errorMessage,
                        style: TextStyle(color: Colors.red.shade700),
                      ),
                    ),
                  ],
                ),
              ),

            const SizedBox(height: 24),

            // Email/Username field
            TextField(
              controller: _emailController,
              decoration: InputDecoration(
                labelText: 'Email or Username',
                hintText: 'username@qmail.com or just username',
                prefixIcon: const Icon(Icons.email),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                suffixText: '@qmail.com',
              ),
              enabled: !_isLoading,
            ),

            const SizedBox(height: 16),

            // Password field
            TextField(
              controller: _passwordController,
              obscureText: !_passwordVisible,
              decoration: InputDecoration(
                labelText: 'Password',
                hintText: 'Enter your password',
                prefixIcon: const Icon(Icons.lock),
                suffixIcon: IconButton(
                  icon: Icon(
                    _passwordVisible ? Icons.visibility : Icons.visibility_off,
                  ),
                  onPressed: () {
                    setState(() => _passwordVisible = !_passwordVisible);
                  },
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              enabled: !_isLoading,
            ),

            const SizedBox(height: 24),

            // Login button
            SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton.icon(
                onPressed: _isLoading ? null : _handleLogin,
                icon: _isLoading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.login),
                label: Text(_isLoading ? 'Logging in...' : 'Login'),
              ),
            ),

            const SizedBox(height: 16),

            // Forgot password button
            TextButton(
              onPressed: _isLoading
                  ? null
                  : () {
                      widget.onNavigateToPasswordReset?.call();
                    },
              child: const Text('Forgot Password?'),
            ),

            const SizedBox(height: 32),

            // Divider
            Row(
              children: [
                Expanded(child: Divider()),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Text(
                    'New to Qumail?',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
                Expanded(child: Divider()),
              ],
            ),

            const SizedBox(height: 16),

            // Signup button
            SizedBox(
              width: double.infinity,
              height: 48,
              child: OutlinedButton.icon(
                onPressed: _isLoading
                    ? null
                    : () {
                        widget.onNavigateToSignup?.call();
                      },
                icon: const Icon(Icons.person_add),
                label: const Text('Create New Account'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
