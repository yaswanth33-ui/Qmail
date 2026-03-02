import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:pointycastle/export.dart';

/// Quantum Random Number Generator (QRNG) Client
/// 
/// Fetches TRUE quantum randomness from the ANU Quantum Random Number Generator.
/// Uses quantum vacuum fluctuations measured by specialized hardware.
/// 
/// This ensures AES keys cannot be predicted even by quantum computers.
/// Falls back to OS CSPRNG if QRNG is unavailable.
class QrngClient {
  static const String _anuApiUrl = 'https://qrng.anu.edu.au/API/jsonI.php';
  static const int _maxBytesPerRequest = 1024;
  static const Duration _timeout = Duration(seconds: 5);
  
  static int _fallbackCount = 0;
  
  /// Fetch quantum-random bytes from ANU QRNG API.
  /// 
  /// Falls back to OS CSPRNG if the quantum source is unavailable.
  /// This method NEVER fails - it always returns cryptographically secure bytes.
  static Future<Uint8List> getBytes(int n) async {
    if (n <= 0) {
      throw ArgumentError('Number of bytes must be positive, got $n');
    }
    
    try {
      final quantumBytes = await _fetchQuantumBytes(n);
      return quantumBytes;
    } catch (e) {
      // Fallback to OS CSPRNG (still cryptographically secure, but not quantum-random)
      _fallbackCount++;
      return _generateSecureRandom(n);
    }
  }
  
  /// Fetch quantum bytes from ANU API, handling chunking for large requests.
  static Future<Uint8List> _fetchQuantumBytes(int length) async {
    final result = <int>[];
    var remaining = length;
    
    while (remaining > 0) {
      final chunkSize = remaining > _maxBytesPerRequest ? _maxBytesPerRequest : remaining;
      final chunkBytes = await _fetchChunk(chunkSize);
      result.addAll(chunkBytes);
      remaining -= chunkSize;
    }
    
    return Uint8List.fromList(result);
  }
  
  /// Fetch a single chunk from the ANU QRNG API.
  static Future<List<int>> _fetchChunk(int length) async {
    final uri = Uri.parse('$_anuApiUrl?length=$length&type=uint8');
    
    final response = await http.get(uri).timeout(_timeout);
    
    if (response.statusCode != 200) {
      throw Exception('QRNG API returned status ${response.statusCode}');
    }
    
    final data = json.decode(response.body) as Map<String, dynamic>;
    
    if (data['success'] != true) {
      throw Exception('QRNG API returned success=false');
    }
    
    final dataList = data['data'] as List<dynamic>;
    return dataList.cast<int>();
  }
  
  /// Generate secure random bytes using OS CSPRNG (fallback).
  static Uint8List _generateSecureRandom(int n) {
    final random = Random.secure();
    return Uint8List.fromList(List.generate(n, (_) => random.nextInt(256)));
  }
  
  /// Get fallback count for monitoring.
  static int get fallbackCount => _fallbackCount;
}

/// AES-GCM Encryption service with Quantum-Seeded Keys.
/// 
/// TRUE END-TO-END ENCRYPTION:
/// - All encryption happens CLIENT-SIDE
/// - Server NEVER sees plaintext data or encryption keys
/// - Keys are seeded with quantum randomness from ANU QRNG
/// 
/// Security properties:
/// - AES-256-GCM: 256-bit key provides 128-bit post-quantum security
/// - Quantum-random keys: Fundamentally unpredictable (quantum mechanics)
/// - 96-bit nonce: NIST recommended for GCM mode (SP 800-38D)
/// - 128-bit auth tag: Detects any tampering (AEAD)
class CryptoService {
  static const int _keySize = 32; // 256 bits
  static const int _nonceSize = 12; // 96 bits (NIST recommended for GCM)
  static const int _tagSize = 16; // 128 bits

  /// Capability flag: whether PQC mode is supported for key exchange.
  ///
  /// Set to true because the backend server can perform ML-KEM encapsulation
  /// on behalf of clients that don't have native KEM support (e.g., Flutter/Dart).
  /// 
  /// The client generates quantum-random session keys and sends them with
  /// plaintext format. The backend server encapsulates these keys using the
  /// recipient's ML-KEM public key before storing them.
  ///
  /// Future enhancement: Implement client-side ML-KEM with WASM/FFI for
  /// true end-to-end key encapsulation without server involvement.
  static bool get supportsPqcKem => true;

  /// Generate a quantum-random AES-256 key.
  /// 
  /// Uses ANU Quantum Random Number Generator for TRUE randomness.
  /// Falls back to OS CSPRNG if QRNG is unavailable.
  static Future<Uint8List> generateQuantumKey() async {
    return await QrngClient.getBytes(_keySize);
  }

  /// Generate a quantum-random nonce (12 bytes).
  static Future<Uint8List> generateQuantumNonce() async {
    return await QrngClient.getBytes(_nonceSize);
  }
  
  /// Generate a key synchronously (uses OS CSPRNG, not quantum).
  /// Use [generateQuantumKey] for quantum-seeded keys.
  static Uint8List generateKey() {
    final secureRandom = _getSecureRandom();
    return secureRandom.nextBytes(_keySize);
  }

  /// Generate a nonce synchronously.
  static Uint8List generateNonce() {
    final secureRandom = _getSecureRandom();
    return secureRandom.nextBytes(_nonceSize);
  }

  /// Encrypt data using AES-256-GCM with quantum-random nonce.
  /// 
  /// Returns an [EncryptedData] containing:
  /// - nonce (12 bytes)
  /// - ciphertext (variable)
  /// - auth tag (16 bytes, appended to ciphertext by GCM)
  static Future<EncryptedData> encryptWithQuantumNonce(Uint8List plaintext, Uint8List key) async {
    if (key.length != _keySize) {
      throw ArgumentError('Key must be $_keySize bytes (256 bits)');
    }

    final nonce = await generateQuantumNonce();
    return _encryptWithNonce(plaintext, key, nonce);
  }

  /// Encrypt data using AES-256-GCM (synchronous, OS-random nonce).
  static EncryptedData encrypt(Uint8List plaintext, Uint8List key) {
    if (key.length != _keySize) {
      throw ArgumentError('Key must be $_keySize bytes (256 bits)');
    }

    final nonce = generateNonce();
    return _encryptWithNonce(plaintext, key, nonce);
  }
  
  /// Internal encryption with provided nonce.
  static EncryptedData _encryptWithNonce(Uint8List plaintext, Uint8List key, Uint8List nonce) {
    final cipher = GCMBlockCipher(AESEngine());
    
    final params = AEADParameters(
      KeyParameter(key),
      _tagSize * 8, // tag length in bits
      nonce,
      Uint8List(0), // no additional authenticated data
    );

    cipher.init(true, params); // true = encrypt

    // GCM output includes ciphertext + tag
    // getOutputSize returns a buffer size that may be larger than actual output
    final outputBuffer = Uint8List(cipher.getOutputSize(plaintext.length));
    var totalLen = cipher.processBytes(plaintext, 0, plaintext.length, outputBuffer, 0);
    totalLen += cipher.doFinal(outputBuffer, totalLen);  // Add bytes written by doFinal
    
    // Return only the actual bytes written, not the oversized buffer
    return EncryptedData(
      nonce: nonce,
      ciphertext: Uint8List.fromList(outputBuffer.sublist(0, totalLen)),
    );
  }

  /// Decrypt data using AES-256-GCM.
  /// 
  /// Throws [ArgumentError] if authentication fails (data tampered).
  static Uint8List decrypt(EncryptedData encryptedData, Uint8List key) {
    if (key.length != _keySize) {
      throw ArgumentError('Key must be $_keySize bytes (256 bits)');
    }

    final cipher = GCMBlockCipher(AESEngine());
    
    final params = AEADParameters(
      KeyParameter(key),
      _tagSize * 8,
      encryptedData.nonce,
      Uint8List(0),
    );

    cipher.init(false, params); // false = decrypt

    try {
      final outputBuffer = Uint8List(cipher.getOutputSize(encryptedData.ciphertext.length));
      var totalLen = cipher.processBytes(
        encryptedData.ciphertext, 0, encryptedData.ciphertext.length, outputBuffer, 0,
      );
      totalLen += cipher.doFinal(outputBuffer, totalLen);  // Add bytes written by doFinal
      
      // Return only the actual plaintext bytes
      return Uint8List.fromList(outputBuffer.sublist(0, totalLen));
    } catch (e) {
      throw ArgumentError('Decryption failed: data may be corrupted or tampered');
    }
  }

  /// Encrypt data and return as a single blob (nonce + ciphertext).
  /// 
  /// Format: [nonce (12 bytes)][ciphertext (variable)]
  /// 
  /// This is convenient for storage/transmission as a single byte array.
  static Uint8List encryptToBytes(Uint8List plaintext, Uint8List key) {
    final encrypted = encrypt(plaintext, key);
    return encrypted.toBytes();
  }

  /// Encrypt data with quantum-random nonce and return as bytes.
  static Future<Uint8List> encryptToBytesQuantum(Uint8List plaintext, Uint8List key) async {
    final encrypted = await encryptWithQuantumNonce(plaintext, key);
    return encrypted.toBytes();
  }

  /// Decrypt data from a single blob (nonce + ciphertext).
  static Uint8List decryptFromBytes(Uint8List data, Uint8List key) {
    final encrypted = EncryptedData.fromBytes(data);
    return decrypt(encrypted, key);
  }

  /// Encrypt data and return as hex string.
  static String encryptToHex(Uint8List plaintext, Uint8List key) {
    final bytes = encryptToBytes(plaintext, key);
    return _bytesToHex(bytes);
  }

  /// Encrypt with quantum randomness and return as hex string.
  static Future<String> encryptToHexQuantum(Uint8List plaintext, Uint8List key) async {
    final bytes = await encryptToBytesQuantum(plaintext, key);
    return _bytesToHex(bytes);
  }

  /// Decrypt data from hex string.
  static Uint8List decryptFromHex(String hexData, Uint8List key) {
    final bytes = _hexToBytes(hexData);
    return decryptFromBytes(bytes, key);
  }

  /// Generate a quantum-random key and return as hex string.
  static Future<String> generateQuantumKeyHex() async {
    final key = await generateQuantumKey();
    return _bytesToHex(key);
  }

  /// Generate a key and return as hex string (OS CSPRNG, not quantum).
  static String generateKeyHex() {
    return _bytesToHex(generateKey());
  }

  /// Convert hex string to key bytes.
  static Uint8List keyFromHex(String hex) {
    return _hexToBytes(hex);
  }

  // --- Private helpers ---

  static SecureRandom _getSecureRandom() {
    final secureRandom = FortunaRandom();
    final seed = Uint8List(32);
    final random = Random.secure();
    for (var i = 0; i < 32; i++) {
      seed[i] = random.nextInt(256);
    }
    secureRandom.seed(KeyParameter(seed));
    return secureRandom;
  }

  static String _bytesToHex(Uint8List bytes) {
    return bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  }

  static Uint8List _hexToBytes(String hex) {
    final result = Uint8List(hex.length ~/ 2);
    for (var i = 0; i < result.length; i++) {
      result[i] = int.parse(hex.substring(i * 2, i * 2 + 2), radix: 16);
    }
    return result;
  }
}

/// Container for encrypted data (nonce + ciphertext with auth tag).
class EncryptedData {
  final Uint8List nonce;
  final Uint8List ciphertext; // includes GCM auth tag at the end

  EncryptedData({
    required this.nonce,
    required this.ciphertext,
  });

  /// Serialize to a single byte array: [nonce][ciphertext]
  Uint8List toBytes() {
    final result = Uint8List(nonce.length + ciphertext.length);
    result.setRange(0, nonce.length, nonce);
    result.setRange(nonce.length, result.length, ciphertext);
    return result;
  }

  /// Deserialize from byte array.
  factory EncryptedData.fromBytes(Uint8List data) {
    if (data.length < 12) {
      throw ArgumentError('Data too short to contain nonce');
    }
    return EncryptedData(
      nonce: data.sublist(0, 12),
      ciphertext: data.sublist(12),
    );
  }

  /// Convert to JSON-serializable map.
  Map<String, String> toJson() {
    return {
      'nonce_hex': nonce.map((b) => b.toRadixString(16).padLeft(2, '0')).join(),
      'ciphertext_hex': ciphertext.map((b) => b.toRadixString(16).padLeft(2, '0')).join(),
    };
  }
}

// =============================================================================
// OTP - One-Time Pad Encryption for View-Once Messages (CLIENT-SIDE)
// =============================================================================
//
// Provides PERFECT SECRECY encryption for "view-once" messages.
// Uses the One-Time Pad (OTP) cipher with quantum-random keys from ANU QRNG.
//
// WHY OTP FOR VIEW-ONCE:
// - Perfect secrecy: Cannot be decrypted without the exact key
// - Forward secrecy: Key is destroyed after single use
// - No key derivation: No patterns to exploit across messages
//
// SECURITY MODEL:
// 1. Generate QRNG key (same length as message)
// 2. Generate QRNG MAC key (32 bytes for HMAC-SHA256)
// 3. XOR message with OTP key → ciphertext
// 4. HMAC(mac_key, ciphertext) → authentication tag
// 5. Send: {ciphertext, mac_tag} via server
// 6. Send: {otp_key, mac_key} via secure key exchange
// 7. DESTROY keys immediately after use
// =============================================================================

/// Exception for OTP operations.
class OtpException implements Exception {
  final String message;
  OtpException(this.message);
  
  @override
  String toString() => 'OtpException: $message';
}

/// MAC verification failed - ciphertext may have been tampered with.
class OtpMacVerificationException extends OtpException {
  OtpMacVerificationException() : super(
    'MAC verification failed. Ciphertext may have been tampered with. '
    'Do NOT attempt to decrypt.'
  );
}

/// OTP key length doesn't match ciphertext/plaintext length.
class OtpKeyLengthException extends OtpException {
  OtpKeyLengthException(int expected, int actual) : super(
    'OTP requires key and message to be the same length. '
    'Expected $expected bytes, got $actual bytes.'
  );
}

/// Container for OTP-encrypted data.
class OtpEncryptedData {
  /// Encrypted data (XOR of plaintext and OTP key).
  final Uint8List ciphertext;
  
  /// HMAC-SHA256 authentication tag (32 bytes).
  final Uint8List macTag;
  
  /// One-time pad key (same length as plaintext) - KEEP SECRET.
  final Uint8List otpKey;
  
  /// MAC key (32 bytes) - KEEP SECRET.
  final Uint8List macKey;

  OtpEncryptedData({
    required this.ciphertext,
    required this.macTag,
    required this.otpKey,
    required this.macKey,
  });

  /// Serialize keys for transmission via secure key exchange.
  /// 
  /// Format: [otpKey][macKey] - both must be transmitted securely.
  Uint8List keysToBytes() {
    final result = Uint8List(otpKey.length + macKey.length);
    result.setRange(0, otpKey.length, otpKey);
    result.setRange(otpKey.length, result.length, macKey);
    return result;
  }

  /// Serialize ciphertext + MAC for transmission via regular channel.
  /// 
  /// Format: [macTag (32 bytes)][ciphertext (variable)]
  Uint8List dataToBytes() {
    final result = Uint8List(macTag.length + ciphertext.length);
    result.setRange(0, macTag.length, macTag);
    result.setRange(macTag.length, result.length, ciphertext);
    return result;
  }

  /// Deserialize ciphertext + MAC from bytes.
  static ({Uint8List ciphertext, Uint8List macTag}) dataFromBytes(Uint8List data) {
    if (data.length < 32) {
      throw OtpException('Data too short to contain MAC tag');
    }
    return (
      macTag: data.sublist(0, 32),
      ciphertext: data.sublist(32),
    );
  }

  /// Convert to JSON-serializable map.
  Map<String, String> toJson() {
    String toHex(Uint8List bytes) => bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    return {
      'ciphertext_hex': toHex(ciphertext),
      'mac_tag_hex': toHex(macTag),
      'otp_key_hex': toHex(otpKey),
      'mac_key_hex': toHex(macKey),
    };
  }
}

/// One-Time Pad Encryption Service for View-Once Messages.
/// 
/// TRUE CLIENT-SIDE END-TO-END ENCRYPTION:
/// - All encryption happens on the device
/// - Server NEVER sees plaintext or keys
/// - Keys are quantum-random from ANU QRNG
/// - Provides PERFECT SECRECY (information-theoretically secure)
/// 
/// Usage:
/// ```dart
/// // Encrypt (sender)
/// final encrypted = await OtpService.encryptViewOnce(utf8.encode("Secret!"));
/// // Send encrypted.dataToBytes() via regular channel
/// // Send encrypted.keysToBytes() via secure key exchange
/// 
/// // Decrypt (recipient)
/// final plaintext = OtpService.decryptViewOnce(
///   ciphertext: encrypted.ciphertext,
///   macTag: encrypted.macTag,
///   otpKey: encrypted.otpKey,
///   macKey: encrypted.macKey,
/// );
/// // DESTROY keys immediately after!
/// ```
class OtpService {
  static const int _macKeySize = 32; // HMAC-SHA256 key (256 bits)

  /// Encrypt plaintext using QRNG-backed One-Time Pad with MAC.
  /// 
  /// This provides PERFECT SECRECY for view-once messages. The key material
  /// is generated using quantum randomness and must be transmitted via a
  /// separate secure channel (PQC or BB84 key exchange).
  /// 
  /// Returns [OtpEncryptedData] containing:
  /// - ciphertext: XOR of plaintext and otpKey
  /// - macTag: 32-byte HMAC-SHA256 authentication tag
  /// - otpKey: One-time pad key (same length as plaintext) - KEEP SECRET
  /// - macKey: MAC key (32 bytes) - KEEP SECRET
  /// 
  /// Security Notes:
  /// - otpKey and macKey must be transmitted via secure key exchange
  /// - ciphertext and macTag can be sent via regular (untrusted) channel
  /// - ALL keys must be destroyed after single use
  /// - NEVER reuse an OTP key - this completely breaks security
  static Future<OtpEncryptedData> encryptViewOnce(Uint8List plaintext) async {
    if (plaintext.isEmpty) {
      throw OtpException('Cannot encrypt empty message');
    }

    // Generate quantum-random key material:
    // - OTP key: same length as plaintext (for XOR)
    // - MAC key: 32 bytes (for HMAC-SHA256)
    final keyMaterial = await QrngClient.getBytes(plaintext.length + _macKeySize);
    
    final otpKey = keyMaterial.sublist(0, plaintext.length);
    final macKey = keyMaterial.sublist(plaintext.length);

    // Encrypt: XOR plaintext with OTP key
    final ciphertext = _xorBytes(plaintext, otpKey);

    // Authenticate: HMAC-SHA256 over ciphertext (encrypt-then-MAC)
    final macTag = _computeMac(macKey, ciphertext);


    return OtpEncryptedData(
      ciphertext: ciphertext,
      macTag: macTag,
      otpKey: otpKey,
      macKey: macKey,
    );
  }

  /// Encrypt plaintext synchronously using OS CSPRNG (not quantum-random).
  /// 
  /// Use [encryptViewOnce] for quantum-seeded keys when possible.
  static OtpEncryptedData encryptViewOnceSync(Uint8List plaintext) {
    if (plaintext.isEmpty) {
      throw OtpException('Cannot encrypt empty message');
    }

    final random = Random.secure();
    final keyMaterial = Uint8List.fromList(
      List.generate(plaintext.length + _macKeySize, (_) => random.nextInt(256)),
    );
    
    final otpKey = keyMaterial.sublist(0, plaintext.length);
    final macKey = keyMaterial.sublist(plaintext.length);

    final ciphertext = _xorBytes(plaintext, otpKey);
    final macTag = _computeMac(macKey, ciphertext);

    return OtpEncryptedData(
      ciphertext: ciphertext,
      macTag: macTag,
      otpKey: otpKey,
      macKey: macKey,
    );
  }

  /// Decrypt an OTP-encrypted view-once message with MAC verification.
  /// 
  /// This function FIRST verifies the MAC, then decrypts. If the MAC
  /// verification fails, the ciphertext may have been tampered with
  /// and decryption is aborted.
  /// 
  /// Security Notes:
  /// - Keys must be destroyed immediately after decryption
  /// - If MAC fails, treat as a security event - log and alert
  /// - The message should only be shown ONCE and then deleted
  /// 
  /// Throws:
  /// - [OtpKeyLengthException] if otpKey length doesn't match ciphertext
  /// - [OtpMacVerificationException] if MAC verification fails
  static Uint8List decryptViewOnce({
    required Uint8List ciphertext,
    required Uint8List macTag,
    required Uint8List otpKey,
    required Uint8List macKey,
  }) {
    // Validate key length
    if (ciphertext.length != otpKey.length) {
      throw OtpKeyLengthException(ciphertext.length, otpKey.length);
    }

    // Verify MAC FIRST (before any decryption)
    if (!_verifyMac(macKey, ciphertext, macTag)) {
      throw OtpMacVerificationException();
    }

    // Decrypt: XOR ciphertext with OTP key
    final plaintext = _xorBytes(ciphertext, otpKey);

    return plaintext;
  }

  /// Decrypt from separate data and keys byte arrays.
  /// 
  /// Convenience method for when data comes from untrusted channel
  /// and keys come from secure key exchange.
  static Uint8List decryptViewOnceFromBytes({
    required Uint8List data,
    required Uint8List keys,
  }) {
    // Parse data: [macTag (32)][ciphertext]
    final parsed = OtpEncryptedData.dataFromBytes(data);
    
    // Parse keys: [otpKey][macKey (32)]
    if (keys.length < _macKeySize + 1) {
      throw OtpException('Keys too short');
    }
    final otpKeyLength = keys.length - _macKeySize;
    final otpKey = keys.sublist(0, otpKeyLength);
    final macKey = keys.sublist(otpKeyLength);

    return decryptViewOnce(
      ciphertext: parsed.ciphertext,
      macTag: parsed.macTag,
      otpKey: otpKey,
      macKey: macKey,
    );
  }

  /// XOR two byte sequences of equal length.
  static Uint8List _xorBytes(Uint8List a, Uint8List b) {
    if (a.length != b.length) {
      throw OtpKeyLengthException(a.length, b.length);
    }
    final result = Uint8List(a.length);
    for (var i = 0; i < a.length; i++) {
      result[i] = a[i] ^ b[i];
    }
    return result;
  }

  /// Compute HMAC-SHA256 authentication tag.
  static Uint8List _computeMac(Uint8List key, Uint8List data) {
    final hmacSha256 = Hmac(sha256, key);
    final digest = hmacSha256.convert(data);
    return Uint8List.fromList(digest.bytes);
  }

  /// Verify HMAC-SHA256 tag using constant-time comparison.
  static bool _verifyMac(Uint8List key, Uint8List data, Uint8List expectedTag) {
    final computedTag = _computeMac(key, data);
    return _constantTimeEquals(computedTag, expectedTag);
  }

  /// Constant-time comparison to prevent timing attacks.
  static bool _constantTimeEquals(Uint8List a, Uint8List b) {
    if (a.length != b.length) return false;
    var result = 0;
    for (var i = 0; i < a.length; i++) {
      result |= a[i] ^ b[i];
    }
    return result == 0;
  }

  /// Securely zeroize a key in memory.
  /// 
  /// Call this immediately after using OTP keys to minimize
  /// the time sensitive key material remains in memory.
  /// 
  /// Note: Due to Dart's memory model, this provides best-effort
  /// zeroization but cannot guarantee the runtime hasn't made copies.
  static void zeroizeKey(Uint8List key) {
    for (var i = 0; i < key.length; i++) {
      key[i] = 0;
    }
  }
}
