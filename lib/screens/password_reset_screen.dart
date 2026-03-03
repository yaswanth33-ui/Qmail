/// Password Reset Screen for Qmail
/// 
/// This is a multi-step password reset flow:
/// Step 1: Enter email/username/phone → Request OTP
/// Step 2: Enter OTP code → Verify OTP
/// Step 3: Enter new password → Reset password
///

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../services/qmail_auth_service.dart';

class PasswordResetScreen extends ConsumerStatefulWidget {
  const PasswordResetScreen({
    Key? key,
    this.onResetSuccess,
    this.onNavigateToLogin,
  }) : super(key: key);

  final VoidCallback? onResetSuccess;
  final VoidCallback? onNavigateToLogin;

  @override
  ConsumerState<PasswordResetScreen> createState() => _PasswordResetScreenState();
}

class _PasswordResetScreenState extends ConsumerState<PasswordResetScreen> {
  int _currentStep = 0;
  bool _isLoading = false;
  String _errorMessage = '';

  // Step 1: Identifier
  final _identifierController = TextEditingController();

  // Step 2: OTP Verification
  String? _resetSessionId;
  String? _maskedPhone;
  int _otpExpiresIn = 0;
  final _otpController = TextEditingController();

  // Step 3: New Password
  String? _resetToken;
  String? _qmailAddress;
  final _newPasswordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  bool _passwordVisible = false;
  bool _confirmPasswordVisible = false;

  @override
  void dispose() {
    _identifierController.dispose();
    _otpController.dispose();
    _newPasswordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  void _setError(String message) {
    // Clean up error message format
    String cleanMessage = message;
    
    // Remove common prefixes
    final prefixes = [
      'Exception: Failed to request password reset: Exception: ',
      'Exception: Failed to verify reset OTP: Exception: ',
      'Exception: Failed to reset password: Exception: ',
      'Failed to request password reset: Exception: ',
      'Failed to verify reset OTP: Exception: ',
      'Failed to reset password: Exception: ',
      'Exception: ',
    ];
    
    for (final prefix in prefixes) {
      if (cleanMessage.startsWith(prefix)) {
        cleanMessage = cleanMessage.substring(prefix.length);
        break;
      }
    }
    
    setState(() => _errorMessage = cleanMessage);
    Future.delayed(const Duration(seconds: 5), () {
      if (mounted) setState(() => _errorMessage = '');
    });
  }

  Future<void> _requestResetOtp() async {
    if (_identifierController.text.isEmpty) {
      _setError('Please enter your email, username, or phone number');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      final authService = QmailAuthService();
      final identifier = _identifierController.text.trim();
      final response = await authService.requestPasswordReset(
        identifier,
      );

      if (mounted) {
        setState(() {
          _resetSessionId = response['reset_session_id'];
          _maskedPhone = response['phone_masked'];
          _otpExpiresIn = response['expires_in_seconds'];
          _currentStep = 1; // Move to OTP verification
          _isLoading = false;
        });
      }
    } catch (e) {
      _setError('Failed to request reset: $e');
      setState(() => _isLoading = false);
    }
  }

  Future<void> _verifyResetOtp() async {
    if (_otpController.text.isEmpty || _otpController.text.length != 6) {
      _setError('Please enter a valid 6-digit OTP');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      final authService = QmailAuthService();
      final response = await authService.verifyResetOtp(
        resetSessionId: _resetSessionId!,
        otpCode: _otpController.text,
      );

      if (mounted) {
        setState(() {
          _resetToken = response['reset_token'];
          _qmailAddress = response['qmail_address'];
          _currentStep = 2; // Move to new password setup
          _isLoading = false;
        });
      }
    } catch (e) {
      _setError('OTP verification failed: $e');
      setState(() => _isLoading = false);
    }
  }

  Future<void> _resetPassword() async {
    if (_newPasswordController.text.isEmpty) {
      _setError('Please enter a new password');
      return;
    }
    if (_newPasswordController.text.length < 8) {
      _setError('Password must be at least 8 characters');
      return;
    }
    if (_newPasswordController.text != _confirmPasswordController.text) {
      _setError('Passwords do not match');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      final authService = QmailAuthService();
      await authService.resetPassword(
        resetToken: _resetToken!,
        newPassword: _newPasswordController.text,
      );

      if (mounted) {
        // Show success dialog
        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (context) => AlertDialog(
            title: const Text('Password Reset Successful'),
            content: Text(
              'Your password has been reset successfully. You can now login with your new password.\n\nAccount: $_qmailAddress',
            ),
            actions: [
              TextButton(
                onPressed: () {
                  Navigator.of(context).pop();
                  widget.onResetSuccess?.call();
                  widget.onNavigateToLogin?.call();
                },
                child: const Text('Go to Login'),
              ),
            ],
          ),
        );
      }
    } catch (e) {
      _setError('Password reset failed: $e');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Reset Password'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            // Progress indicator
            LinearProgressIndicator(
              value: (_currentStep + 1) / 3,
              minHeight: 4,
              backgroundColor: Colors.grey[300],
              valueColor: AlwaysStoppedAnimation(
                Theme.of(context).primaryColor,
              ),
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

            // Step 1: Enter Identifier
            if (_currentStep == 0) ...[
              Text(
                'Step 1 of 3: Account Identification',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 16),
              Text(
                'Enter your email, username, or phone number',
                style: Theme.of(context).textTheme.bodyMedium,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              TextField(
                controller: _identifierController,
                decoration: InputDecoration(
                  labelText: 'Email / Username / Phone',
                  hintText: 'john@qmail.com or john_doe or +12025551234',
                  prefixIcon: const Icon(Icons.person),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                height: 48,
                child: ElevatedButton.icon(
                  onPressed: _isLoading ? null : _requestResetOtp,
                  icon: _isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.arrow_forward),
                  label: Text(_isLoading ? 'Sending OTP...' : 'Send Reset OTP'),
                ),
              ),
            ],

            // Step 2: Verify OTP
            if (_currentStep == 1) ...[
              Text(
                'Step 2 of 3: Verify OTP',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 16),
              Text(
                'Enter the 6-digit code sent to',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 8),
              Text(
                _maskedPhone ?? '',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: Theme.of(context).primaryColor,
                ),
              ),
              const SizedBox(height: 24),
              TextField(
                controller: _otpController,
                keyboardType: TextInputType.number,
                maxLength: 6,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 24, letterSpacing: 8),
                decoration: InputDecoration(
                  labelText: 'OTP Code',
                  hintText: '000000',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  counterText: '',
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Code expires in ${(_otpExpiresIn / 60).ceil()} minutes',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                height: 48,
                child: ElevatedButton.icon(
                  onPressed: _isLoading ? null : _verifyResetOtp,
                  icon: _isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.check),
                  label: Text(_isLoading ? 'Verifying...' : 'Verify OTP'),
                ),
              ),
              const SizedBox(height: 16),
              TextButton.icon(
                onPressed: _isLoading ? null : _requestResetOtp,
                icon: const Icon(Icons.refresh),
                label: const Text('Resend OTP'),
              ),
            ],

            // Step 3: Set New Password
            if (_currentStep == 2) ...[
              Text(
                'Step 3 of 3: New Password',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 16),
              Text(
                'Set a new password for',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 8),
              Text(
                _qmailAddress ?? '',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: Theme.of(context).primaryColor,
                ),
              ),
              const SizedBox(height: 24),
              TextField(
                controller: _newPasswordController,
                obscureText: !_passwordVisible,
                decoration: InputDecoration(
                  labelText: 'New Password',
                  hintText: 'Minimum 8 characters',
                  prefixIcon: const Icon(Icons.lock),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _passwordVisible ? Icons.visibility_off : Icons.visibility,
                    ),
                    onPressed: () {
                      setState(() => _passwordVisible = !_passwordVisible);
                    },
                  ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _confirmPasswordController,
                obscureText: !_confirmPasswordVisible,
                decoration: InputDecoration(
                  labelText: 'Confirm Password',
                  hintText: 'Re-enter new password',
                  prefixIcon: const Icon(Icons.lock_outline),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _confirmPasswordVisible ? Icons.visibility_off : Icons.visibility,
                    ),
                    onPressed: () {
                      setState(() => _confirmPasswordVisible = !_confirmPasswordVisible);
                    },
                  ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                height: 48,
                child: ElevatedButton.icon(
                  onPressed: _isLoading ? null : _resetPassword,
                  icon: _isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.check_circle),
                  label: Text(_isLoading ? 'Resetting Password...' : 'Reset Password'),
                ),
              ),
            ],

            const SizedBox(height: 24),

            // Back to login link
            Center(
              child: GestureDetector(
                onTap: () => widget.onNavigateToLogin?.call(),
                child: Text.rich(
                  TextSpan(
                    text: 'Remember your password? ',
                    children: [
                      TextSpan(
                        text: 'Login',
                        style: TextStyle(
                          color: Theme.of(context).primaryColor,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
