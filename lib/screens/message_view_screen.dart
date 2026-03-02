import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';

import '../models/email_models.dart';
import '../providers/app_providers.dart';
import '../providers/auth_providers.dart';
import '../services/email_service.dart';
import '../widgets/animated_widgets.dart';
import '../widgets/attachment_widgets.dart';

class MessageViewScreen extends ConsumerStatefulWidget {
  const MessageViewScreen({
    super.key,
    required this.messageId,
    required this.onReply,
    required this.onForward,
  });

  final String messageId;
  final void Function({required String recipient, required String subject, required String body, required String replyToId}) onReply;
  final void Function({required String subject, required String body}) onForward;

  @override
  ConsumerState<MessageViewScreen> createState() => _MessageViewScreenState();
}

class _MessageViewScreenState extends ConsumerState<MessageViewScreen> {
  Future<void> _handleDelete(BuildContext context, EmailEnvelope email) async {
    final authState = ref.read(authStateProvider);
    if (authState.token == null) return;
    
    final emailService = ref.read(emailServiceProvider);
    final isInTrash = email.folder == 'Trash';
    
    // Show confirmation for permanent delete
    if (isInTrash) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Delete Permanently?'),
          content: const Text('This email will be permanently deleted and cannot be recovered.'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              style: TextButton.styleFrom(foregroundColor: Colors.red),
              child: const Text('Delete'),
            ),
          ],
        ),
      );
      
      if (confirmed != true) return;
    }
    
    try {
      if (isInTrash) {
        // Permanent delete
        await emailService.deleteEmail(
          accessToken: authState.token!.accessToken,
          emailId: email.id,
        );
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Email permanently deleted')),
          );
        }
      } else {
        // Move to trash
        await emailService.trashEmail(
          accessToken: authState.token!.accessToken,
          emailId: email.id,
        );
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Email moved to Trash')),
          );
        }
      }
      
      // Refresh inbox
      ref.invalidate(inboxProvider);
      
      // Navigate back after delete
      if (mounted) {
        Navigator.of(context).pop();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final emailsAsync = ref.watch(inboxProvider);
    final decryptedAsync = ref.watch(openEmailProvider(widget.messageId));

    return emailsAsync.when(
      data: (emails) {
        EmailEnvelope? email;
        try {
          email = emails.firstWhere((e) => e.id == widget.messageId);
        } catch (_) {
          // Email not found
        }

        if (email == null) {
          return Scaffold(
            appBar: AppBar(
              title: const Text('Message'),
            ),
            body: const Center(
              child: Text('Email not found'),
            ),
          );
        }

        // Now decrypt the email if it's encrypted
        // Use non-null assertion since we've already checked above
        return decryptedAsync.when(
          data: (decryptedData) {
            final bodyText = decryptedData != null
              ? decryptedData.body
              : email!.bodyText;
            
            return _buildMessageView(context, email!, decryptedData, bodyText);
          },
          loading: () => _buildMessageView(context, email!, null, email!.bodyText),
          error: (error, stack) => _buildMessageView(context, email!, null, email!.bodyText),
        );
      },
      loading: () => Scaffold(
        appBar: AppBar(
          title: const Text('Message'),
        ),
        body: const Center(
          child: CircularProgressIndicator(),
        ),
      ),
      error: (error, stack) => Scaffold(
        appBar: AppBar(
          title: const Text('Message'),
        ),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.error_outline,
                size: 64,
                color: Theme.of(context).colorScheme.error,
              ),
              const SizedBox(height: 16),
              Text(
                'Error loading message',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(
                error.toString(),
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _downloadAttachment(BuildContext context, Attachment attachment, String? sessionKeyHex) async {
    final authState = ref.read(authStateProvider);
    if (authState.token == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Not authenticated')),
      );
      return;
    }

    try {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Downloading ${attachment.fileName}...')),
      );

      final emailService = ref.read(emailServiceProvider);
      
      if (sessionKeyHex == null) {
        ScaffoldMessenger.of(context).hideCurrentSnackBar();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Cannot decrypt attachment: missing session key')),
        );
        return;
      }
      
      final bytes = await emailService.downloadAttachment(
        accessToken: authState.token!.accessToken,
        attachmentId: int.parse(attachment.id),
        sessionKeyHex: sessionKeyHex,
      );

      final savePath = await FilePicker.platform.saveFile(
        dialogTitle: 'Save ${attachment.fileName}',
        fileName: attachment.fileName,
      );

      if (savePath != null) {
        final file = File(savePath);
        await file.writeAsBytes(bytes);
        
        if (context.mounted) {
          ScaffoldMessenger.of(context).hideCurrentSnackBar();
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Saved to ${file.path}'),
              action: SnackBarAction(
                label: 'Open Folder',
                onPressed: () {
                  Process.run('explorer.exe', ['/select,', file.path]);
                },
              ),
            ),
          );
        }
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).hideCurrentSnackBar();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to download: $e')),
        );
      }
    }
  }

  Widget _buildSignatureStatus(BuildContext context, DecryptedEmailResponse? decryptedData, bool signatureValid) {
    final hasSignature = decryptedData?.hasSignature ?? false;
    final keyExchangeMode = decryptedData?.keyExchangeMode;
    
    final bool showVerified = signatureValid && hasSignature;
    final bool showInvalid = hasSignature && !signatureValid;
    
    final Color statusColor = showVerified
        ? Colors.green.shade700
        : showInvalid
            ? Colors.red.shade700
            : Colors.orange.shade700;
    
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Wrap(
        spacing: 12,
        runSpacing: 4,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                showVerified
                    ? Icons.verified_user
                    : showInvalid
                        ? Icons.gpp_bad
                        : Icons.shield_outlined,
                color: statusColor,
                size: 16,
              ),
              const SizedBox(width: 4),
              Text(
                showVerified
                    ? 'Signature Verified'
                    : showInvalid
                        ? 'Signature Invalid'
                        : 'No Signature',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: statusColor,
                ),
              ),
            ],
          ),
          if (keyExchangeMode != null)
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.key,
                  size: 14,
                  color: Colors.grey.shade600,
                ),
                const SizedBox(width: 4),
                Text(
                  keyExchangeMode == 'bb84' ? 'BB84 (QKD)' : 'PQC (ML-KEM)',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey.shade600,
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }

  Widget _buildMessageView(BuildContext context, EmailEnvelope email, DecryptedEmailResponse? decryptedData, String bodyText) {
    final authState = ref.read(authStateProvider);
    final currentUserEmail = authState.user?.qmailAddress ?? '';
    final isEncrypted = email.securityLevel != SecurityLevel.classical;
    final isDecrypted = decryptedData != null;
    final signatureValid = decryptedData?.isSignatureValid ?? false;
    final isOtp = decryptedData?.encryptionMode == 'E2E_OTP_PERFECT_SECRECY';
    final isViewOnce = email.viewOnce || (decryptedData?.viewOnce ?? false);
    
    // Format From field: show 'me' for sent emails from current user
    final fromDisplay = (email.folder == 'Sent' && email.from.email.toLowerCase() == currentUserEmail.toLowerCase())
        ? 'me <${email.from.email}>'
        : '${email.from.displayName} <${email.from.email}>';
    
    // Format To field: show 'you' for inbox emails to current user
    final toDisplay = (email.folder == 'Inbox' && email.to.any((c) => c.email.toLowerCase() == currentUserEmail.toLowerCase()))
        ? email.to.map((c) => c.email.toLowerCase() == currentUserEmail.toLowerCase() ? 'you' : c.email).join(', ')
        : email.to.map((c) => c.email).join(', ');
    
    return Scaffold(
      appBar: AppBar(
        title: Text(email.subject),
        actions: [
          if (isViewOnce) ...[
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8.0),
              child: Chip(
                avatar: const Icon(Icons.enhanced_encryption, size: 16, color: Colors.purple),
                label: const Text(
                  'One-Time Pad',
                  style: TextStyle(fontSize: 11, color: Colors.purple),
                ),
                backgroundColor: Colors.purple.shade50,
                side: BorderSide.none,
                padding: EdgeInsets.zero,
              ),
            ),
          ],
          if (isEncrypted) ...[
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: Center(
                child: Chip(
                  label: Text(
                    isDecrypted 
                      ? (isOtp 
                          ? '🔐 Perfect Secrecy' 
                          : (signatureValid ? '✓ Verified' : 'Decrypted'))
                      : 'Decrypting...',
                    style: TextStyle(
                      fontSize: 12,
                      color: isDecrypted 
                          ? (isOtp ? Colors.purple : Colors.green) 
                          : Colors.orange,
                    ),
                  ),
                  backgroundColor: Colors.transparent,
                ),
              ),
            ),
          ],
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              FadeInWidget(
                delay: const Duration(milliseconds: 0),
                child: Text(
                  email.subject,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              const SizedBox(height: 10),
              FadeInWidget(
                delay: const Duration(milliseconds: 50),
                child: Text(
                  'From: $fromDisplay',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
              const SizedBox(height: 2),
              FadeInWidget(
                delay: const Duration(milliseconds: 100),
                child: Text(
                  'To: $toDisplay',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
              const SizedBox(height: 12),
              const Divider(height: 1),
              const SizedBox(height: 16),
              FadeInWidget(
                delay: const Duration(milliseconds: 150),
                child: SelectableText(
                  bodyText,
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    height: 1.6,
                  ),
                ),
              ),
              if (isEncrypted && isDecrypted) ...[
                const SizedBox(height: 12),
                _buildSignatureStatus(context, decryptedData, signatureValid),
              ],
              if (email.attachments.isNotEmpty) ...[
                const SizedBox(height: 24),
                const Divider(),
                Row(
                  children: [
                    Icon(
                      Icons.attach_file_rounded,
                      size: 20,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Attachments (${email.attachments.length})',
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                ...email.attachments.map(
                  (a) => AttachmentCard(
                    attachment: a,
                    compact: true,
                    onDownload: () => _downloadAttachment(context, a, decryptedData?.sessionKeyHex),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
      bottomNavigationBar: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (email.folder != 'Drafts') ...[
            const Divider(height: 1),
            SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Row(
                  children: [
                    if (email.folder != 'Sent') ...[
                      FilledButton.icon(
                        onPressed: () {
                          widget.onReply(
                            recipient: email.from.email,
                            subject: '',
                            body: '',
                            replyToId: email.id,
                          );
                        },
                        icon: const Icon(Icons.reply),
                        label: const Text('Reply'),
                      ),
                      const SizedBox(width: 8),
                    ],
                    OutlinedButton.icon(
                      onPressed: () {
                        // Build forward context
                        final fwdSubject = email.subject.startsWith('Fwd: ')
                            ? email.subject
                            : 'Fwd: ${email.subject}';
                        
                        final date = '${email.sentAt.day}/${email.sentAt.month}/${email.sentAt.year}';
                        final fwdBody = '\n\n---------- Forwarded message ----------\nFrom: ${email.from.displayName} <${email.from.email}>\nDate: $date\nSubject: ${email.subject}\n\n$bodyText';
                        
                        widget.onForward(
                          subject: fwdSubject,
                          body: fwdBody,
                        );
                      },
                      icon: const Icon(Icons.forward),
                      label: const Text('Forward'),
                    ),
                    const SizedBox(width: 8),
                    OutlinedButton.icon(
                      onPressed: () => _handleDelete(context, email),
                      icon: const Icon(Icons.delete_outline),
                      label: const Text('Delete'),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}




