/// Phone-Verified Signup Screen for Qmail
/// 
/// This is a multi-step signup flow:
/// Step 1: Enter name, DOB, phone → Request OTP
/// Step 2: Enter OTP code → Verify and create account
/// Step 3: Enter username → Choose @qmail username
/// Step 4: Set password → Complete signup
/// Step 5: Login → Redirect to inbox
///

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../services/qmail_auth_service.dart';
import '../../providers/auth_providers.dart';

class QmailSignupScreen extends ConsumerStatefulWidget {
  const QmailSignupScreen({
    Key? key,
    this.onSignupSuccess,
    this.onNavigateToLogin,
  }) : super(key: key);

  final VoidCallback? onSignupSuccess;
  final VoidCallback? onNavigateToLogin;

  @override
  ConsumerState<QmailSignupScreen> createState() => _QmailSignupScreenState();
}

class _QmailSignupScreenState extends ConsumerState<QmailSignupScreen> {
  int _currentStep = 0;
  bool _isLoading = false;
  String _errorMessage = '';

  // Step 1: User Info
  final _nameController = TextEditingController();
  DateTime? _selectedDob;
  final _phoneController = TextEditingController();
  String _selectedCountryCode = 'US';
  
  // Supported countries with their codes and dial codes
  final Map<String, Map<String, String>> _countries = {
    'US': {'name': 'United States', 'dial': '+1', 'flag': '🇺🇸'},
    'IN': {'name': 'India', 'dial': '+91', 'flag': '🇮🇳'},
    'GB': {'name': 'United Kingdom', 'dial': '+44', 'flag': '🇬🇧'},
    'CA': {'name': 'Canada', 'dial': '+1', 'flag': '🇨🇦'},
    'AU': {'name': 'Australia', 'dial': '+61', 'flag': '🇦🇺'},
    'DE': {'name': 'Germany', 'dial': '+49', 'flag': '🇩🇪'},
    'FR': {'name': 'France', 'dial': '+33', 'flag': '🇫🇷'},
    'JP': {'name': 'Japan', 'dial': '+81', 'flag': '🇯🇵'},
    'CN': {'name': 'China', 'dial': '+86', 'flag': '🇨🇳'},
    'BR': {'name': 'Brazil', 'dial': '+55', 'flag': '🇧🇷'},
    'MX': {'name': 'Mexico', 'dial': '+52', 'flag': '🇲🇽'},
  };

  // Step 2: OTP Verification
  String? _otpSessionId;
  String? _maskedPhone;
  int _otpExpiresIn = 0;
  final _otpController = TextEditingController();

  // Step 3: Username Selection
  final _usernameController = TextEditingController();

  // Step 4: Password Setup
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  String? _temporaryAuthToken;
  String? _newQmailAddress;
  bool _passwordVisible = false;
  bool _confirmPasswordVisible = false;

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _otpController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  void _setError(String message) {
    // Clean up error message format
    String cleanMessage = message;
    
    // Remove common prefixes
    final prefixes = [
      'Exception: Failed to request OTP: Exception: ',
      'Exception: Failed to verify OTP: Exception: ',
      'Failed to request OTP: Exception: ',
      'Failed to verify OTP: Exception: ',
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

  /// Calculate age based on date of birth
  int _calculateAge(DateTime dob) {
    final today = DateTime.now();
    int age = today.year - dob.year;
    
    // Check if birthday hasn't occurred this year
    if (today.month < dob.month || (today.month == dob.month && today.day < dob.day)) {
      age--;
    }
    
    return age;
  }

  /// Validate that user is 18+ years old
  bool _isAgeValid(DateTime dob) {
    return _calculateAge(dob) >= 18;
  }

  Future<void> _requestOtp() async {
    if (_nameController.text.isEmpty) {
      _setError('Please enter your name');
      return;
    }
    if (_selectedDob == null) {
      _setError('Please select your date of birth');
      return;
    }
    if (!_isAgeValid(_selectedDob!)) {
      final age = _calculateAge(_selectedDob!);
      _setError('You must be at least 18 years old. You are currently $age years old.');
      return;
    }
    if (_phoneController.text.isEmpty) {
      _setError('Please enter your phone number');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      final authService = QmailAuthService();
      final response = await authService.requestOtp(
        name: _nameController.text,
        dateOfBirth: _selectedDob!,
        phoneNumber: _phoneController.text,
        countryCode: _selectedCountryCode,
      );

      if (mounted) {
        setState(() {
          _otpSessionId = response.otpSessionId;
          _maskedPhone = response.phoneMasked;
          _otpExpiresIn = response.expiresInSeconds;
          _currentStep = 1; // Move to OTP verification
          _isLoading = false;
        });
      }
    } catch (e) {
      _setError('Failed to request OTP: $e');
      setState(() => _isLoading = false);
    }
  }

  Future<void> _verifyOtpAndCreateAccount() async {
    if (_otpController.text.isEmpty || _otpController.text.length != 6) {
      _setError('Please enter a valid 6-digit OTP');
      return;
    }
    if (_usernameController.text.isEmpty) {
      _setError('Please choose a username');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      final authService = QmailAuthService();
      final response = await authService.verifyOtp(
        otpSessionId: _otpSessionId!,
        otpCode: _otpController.text,
        desiredUsername: _usernameController.text,
      );

      if (mounted) {
        setState(() {
          _temporaryAuthToken = response.temporaryAuthToken;
          _newQmailAddress = response.qmailAddress;
          _currentStep = 2; // Move to password setup
          _isLoading = false;
        });
      }
    } catch (e) {
      _setError('OTP verification failed: $e');
      setState(() => _isLoading = false);
    }
  }

  Future<void> _setPasswordAndCompleteSignup() async {
    if (_passwordController.text.isEmpty) {
      _setError('Please enter a password');
      return;
    }
    if (_passwordController.text.length < 8) {
      _setError('Password must be at least 8 characters');
      return;
    }
    if (_passwordController.text != _confirmPasswordController.text) {
      _setError('Passwords do not match');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      final authService = QmailAuthService();

      // Set password
      await authService.setPassword(
        temporaryAuthToken: _temporaryAuthToken!,
        password: _passwordController.text,
        confirmPassword: _confirmPasswordController.text,
      );

      // Auto-login using auth provider to update state
      await ref.read(authStateProvider.notifier).login(
        _newQmailAddress!,
        _passwordController.text,
      );

      if (mounted) {
        // Auth state is now updated, navigate to inbox
        widget.onSignupSuccess?.call();
      }
    } catch (e) {
      _setError('Signup failed: $e');
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Create Your Qumail Account'),
        centerTitle: true,
        elevation: 0,
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

            // Step 1: User Info
            if (_currentStep == 0) ...[
              Text(
                'Step 1 of 3: Your Information',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 24),
              TextField(
                controller: _nameController,
                decoration: InputDecoration(
                  labelText: 'Full Name',
                  prefixIcon: const Icon(Icons.person),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              InkWell(
                onTap: () async {
                  // Calculate date 18 years ago from today
                  final eighteenYearsAgo = DateTime(
                    DateTime.now().year - 18,
                    DateTime.now().month,
                    DateTime.now().day,
                  );
                  
                  final picked = await showDatePicker(
                    context: context,
                    initialDate: eighteenYearsAgo,
                    firstDate: DateTime(1950),
                    lastDate: eighteenYearsAgo,
                  );
                  if (picked != null) {
                    setState(() => _selectedDob = picked);
                  }
                },
                child: InputDecorator(
                  decoration: InputDecoration(
                    labelText: 'Date of Birth',
                    hintText: 'Must be 18+ years old',
                    prefixIcon: const Icon(Icons.calendar_today),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  child: Text(
                    _selectedDob != null
                        ? DateFormat('MMM dd, yyyy').format(_selectedDob!)
                        : 'Select date',
                  ),
                ),
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: _selectedCountryCode,
                decoration: InputDecoration(
                  labelText: 'Country',
                  prefixIcon: const Icon(Icons.flag),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
                items: _countries.entries.map((entry) {
                  return DropdownMenuItem<String>(
                    value: entry.key,
                    child: Row(
                      children: [
                        Text(
                          entry.value['flag']!,
                          style: const TextStyle(fontSize: 20),
                        ),
                        const SizedBox(width: 12),
                        Text('${entry.value['name']} (${entry.value['dial']})',),
                      ],
                    ),
                  );
                }).toList(),
                onChanged: (value) {
                  if (value != null) {
                    setState(() => _selectedCountryCode = value);
                  }
                },
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                decoration: InputDecoration(
                  labelText: 'Phone Number',
                  hintText: 'Enter phone number',
                  helperText: 'Format: ${_countries[_selectedCountryCode]?['dial']} followed by number',
                  prefixIcon: const Icon(Icons.phone),
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
                  onPressed: _isLoading ? null : _requestOtp,
                  icon: _isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.arrow_forward),
                  label: Text(_isLoading ? 'Sending OTP...' : 'Get OTP'),
                ),
              ),
              const SizedBox(height: 16),
              Center(
                child: GestureDetector(
                  onTap: () => widget.onNavigateToLogin?.call(),
                  child: Text.rich(
                    TextSpan(
                      text: 'Already have an account? ',
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

            // Step 2: OTP Verification + Username
            if (_currentStep == 1) ...[
              Text(
                'Step 2 of 3: Verify & Choose Username',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 24),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.blue.shade50,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  'OTP sent to $_maskedPhone\nCode expires in $_otpExpiresIn seconds',
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 12),
                ),
              ),
              const SizedBox(height: 24),
              TextField(
                controller: _otpController,
                keyboardType: TextInputType.number,
                maxLength: 6,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 24, letterSpacing: 16),
                decoration: InputDecoration(
                  labelText: 'Enter 6-digit OTP',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  counterText: '',
                ),
              ),
              const SizedBox(height: 24),
              TextField(
                controller: _usernameController,
                decoration: InputDecoration(
                  labelText: 'Choose Username',
                  hintText: 'john_doe',
                  prefixIcon: const Icon(Icons.alternate_email),
                  suffixText: '@qmail.com',
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
                  onPressed: _isLoading ? null : _verifyOtpAndCreateAccount,
                  icon: _isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.arrow_forward),
                  label: Text(_isLoading ? 'Verifying...' : 'Verify & Create'),
                ),
              ),
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: () => setState(() => _currentStep = 0),
                child: const Text('Back'),
              ),
            ],

            // Step 3: Password Setup
            if (_currentStep == 2) ...[
              Text(
                'Step 3 of 3: Set Your Password',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 24),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.green.shade50,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  'Your account created!\n$_newQmailAddress',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.green.shade700,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              const SizedBox(height: 24),
              TextField(
                controller: _passwordController,
                obscureText: !_passwordVisible,
                decoration: InputDecoration(
                  labelText: 'Password',
                  prefixIcon: const Icon(Icons.lock),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _passwordVisible
                          ? Icons.visibility
                          : Icons.visibility_off,
                    ),
                    onPressed: () {
                      setState(
                        () => _passwordVisible = !_passwordVisible,
                      );
                    },
                  ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Password Requirements:',
                style: Theme.of(context).textTheme.labelLarge,
              ),
              const SizedBox(height: 8),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    PasswordRequirement(
                      text: 'Minimum 8 characters',
                    ),
                    PasswordRequirement(
                      text: 'Uppercase and lowercase letters',
                    ),
                    PasswordRequirement(
                      text: 'At least one number',
                    ),
                    PasswordRequirement(
                      text: 'At least one special character (!@#\$%)',
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _confirmPasswordController,
                obscureText: !_confirmPasswordVisible,
                decoration: InputDecoration(
                  labelText: 'Confirm Password',
                  prefixIcon: const Icon(Icons.lock_outline),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _confirmPasswordVisible
                          ? Icons.visibility
                          : Icons.visibility_off,
                    ),
                    onPressed: () {
                      setState(
                        () =>
                            _confirmPasswordVisible = !_confirmPasswordVisible,
                      );
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
                  onPressed: _isLoading ? null : _setPasswordAndCompleteSignup,
                  icon: _isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.check),
                  label: Text(
                    _isLoading ? 'Completing Signup...' : 'Complete Signup',
                  ),
                ),
              ),
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: () => setState(() => _currentStep = 1),
                child: const Text('Back'),
              ),
            ],

            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }
}

class PasswordRequirement extends StatelessWidget {
  final String text;

  const PasswordRequirement({
    Key? key,
    required this.text,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(Icons.check_circle_outline, size: 16, color: Colors.green[700]),
          const SizedBox(width: 8),
          Text(
            text,
            style: const TextStyle(fontSize: 12),
          ),
        ],
      ),
    );
  }
}
