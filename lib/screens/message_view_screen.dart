import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/email_models.dart';
import '../providers/app_providers.dart';

class MessageViewScreen extends ConsumerWidget {
  const MessageViewScreen({
    super.key,
    required this.messageId,
    required this.onReply,
  });

  final String messageId;
  final VoidCallback onReply;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final emailsAsync = ref.watch(inboxProvider);

    return emailsAsync.when(
      data: (emails) {
        EmailEnvelope? email;
        try {
          email = emails.firstWhere((e) => e.id == messageId);
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

        return _buildMessageView(context, email);
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

  Widget _buildMessageView(BuildContext context, EmailEnvelope email) {
    return Scaffold(
      appBar: AppBar(
        title: Text(email.subject),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                email.subject,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(
                'From: ${email.from.displayName} <${email.from.email}>',
              ),
              Text(
                'To: ${email.to.map((c) => c.email).join(', ')}',
              ),
              const SizedBox(height: 16),
              Text(
                email.bodyText,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              if (email.attachments.isNotEmpty) ...[
                const SizedBox(height: 16),
                const Divider(),
                const Text(
                  'Attachments',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                ...email.attachments.map(
                  (a) => ListTile(
                    dense: true,
                    leading: const Icon(Icons.attach_file),
                    title: Text(a.fileName),
                    subtitle: Text(
                      '${a.mimeType} • ${a.sizeLabel}',
                    ),
                    trailing: a.isAesGcmProtected
                        ? const Text(
                            'AES-GCM',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                            ),
                          )
                        : null,
                    onTap: () {
                      // TODO: integrate with backend Python service
                      // to download and open attachment.
                    },
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Row(
            children: [
              FilledButton.icon(
                onPressed: onReply,
                icon: const Icon(Icons.reply),
                label: const Text('Reply'),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                onPressed: () {
                  // Placeholder for delete / move actions.
                },
                icon: const Icon(Icons.delete_outline),
                label: const Text('Delete'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}




