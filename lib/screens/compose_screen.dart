import 'package:flutter/material.dart';
import 'package:flutter_quill/flutter_quill.dart' hide Text;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/email_models.dart';
import '../providers/app_providers.dart';
import '../providers/auth_providers.dart';

typedef VoidCallback = void Function();

class ComposeScreen extends ConsumerStatefulWidget {
  const ComposeScreen({
    super.key,
    required this.onClose,
  });

  final VoidCallback onClose;

  @override
  ConsumerState<ComposeScreen> createState() => _ComposeScreenState();
}

class _ComposeScreenState extends ConsumerState<ComposeScreen> {
  final _toController = TextEditingController();
  final _subjectController = TextEditingController();
  late final QuillController _quillController;
  bool _viewOnce = false;

  @override
  void initState() {
    super.initState();
    _quillController = QuillController.basic();
  }

  @override
  void dispose() {
    _toController.dispose();
    _subjectController.dispose();
    _quillController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final contacts = ref.watch(contactsProvider);
    final currentUser = ref.watch(currentUserProvider);
    final authState = ref.watch(authStateProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Compose'),
        actions: [
          TextButton.icon(
            onPressed: () async {
              if (currentUser == null) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('You must be logged in to send email.'),
                  ),
                );
                return;
              }

              if (authState.token == null) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('No valid authentication token. Please log in again.'),
                  ),
                );
                return;
              }

              final to = _toController.text.trim();
              final subject = _subjectController.text.trim();
              final bodyText = _quillController.document.toPlainText().trim();

              if (to.isEmpty || subject.isEmpty || bodyText.isEmpty) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('To, subject, and body are required.'),
                  ),
                );
                return;
              }

              final emailService = ref.read(emailServiceProvider);
              final senderUser = authState.user;

              if (senderUser?.email == null) {
                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Error: Could not determine sender email'),
                  ),
                );
                return;
              }

              try {
                await emailService.sendEmail(
                  accessToken: authState.token!.accessToken,
                  sender: senderUser!.email,
                  recipient: to,
                  subject: subject,
                  body: bodyText,
                  viewOnce: _viewOnce,
                );

                // Refresh inbox to show the sent email
                ref.refresh(inboxProvider);

                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Message sent via Qmail backend.'),
                  ),
                );
                widget.onClose();
              } catch (e) {
                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('Failed to send message: $e'),
                  ),
                );
              }
            },
            icon: const Icon(Icons.send),
            label: const Text('Send'),
          ),
        ],
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final isWide = constraints.maxWidth > 700;
          final content = _buildForm(context, contacts);

          if (isWide) {
            return Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 900),
                child: content,
              ),
            );
          }
          return content;
        },
      ),
    );
  }

  Widget _buildForm(
    BuildContext context,
    List<Contact> contacts,
  ) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _RecipientField(
            controller: _toController,
            contacts: contacts,
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _subjectController,
            decoration: const InputDecoration(
              labelText: 'Subject',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: Theme.of(context)
                      .colorScheme
                      .outlineVariant,
                ),
              ),
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: QuillEditor.basic(
                  controller: _quillController,
                  config: const QuillEditorConfig(),
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Container(
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainer,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: Theme.of(context).colorScheme.outlineVariant,
              ),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            child: Row(
              children: [
                Icon(
                  Icons.visibility_off,
                  size: 20,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'View Once: Email will auto-delete after first read',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
                Checkbox(
                  value: _viewOnce,
                  onChanged: (value) {
                    setState(() {
                      _viewOnce = value ?? false;
                    });
                  },
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          _AttachmentBar(),
        ],
      ),
    );
  }
}

class _RecipientField extends StatefulWidget {
  const _RecipientField({
    required this.controller,
    required this.contacts,
  });

  final TextEditingController controller;
  final List<Contact> contacts;

  @override
  State<_RecipientField> createState() => _RecipientFieldState();
}

class _RecipientFieldState extends State<_RecipientField> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final suggestions = widget.contacts
        .where((c) =>
            c.displayName
                .toLowerCase()
                .contains(_query.toLowerCase()) ||
            c.email
                .toLowerCase()
                .contains(_query.toLowerCase()))
        .toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: widget.controller,
          decoration: const InputDecoration(
            labelText: 'To',
            hintText: 'Type a name or email…',
            border: OutlineInputBorder(),
          ),
          onChanged: (value) {
            setState(() => _query = value);
          },
        ),
        if (_query.isNotEmpty && suggestions.isNotEmpty)
          Container(
            margin: const EdgeInsets.only(top: 4),
            decoration: BoxDecoration(
              color:
                  Theme.of(context).colorScheme.surfaceContainer,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: Theme.of(context)
                    .colorScheme
                    .outlineVariant,
              ),
            ),
            constraints: const BoxConstraints(maxHeight: 150),
            child: ListView.builder(
              shrinkWrap: true,
              itemCount: suggestions.length,
              itemBuilder: (context, index) {
                final contact = suggestions[index];
                return ListTile(
                  dense: true,
                  title: Text(contact.displayName),
                  subtitle: Text(contact.email),
                  trailing: Icon(contact.supportsPqc
                      ? Icons.shield
                      : Icons.shield_outlined),
                  onTap: () {
                    widget.controller.text = contact.email;
                    setState(() => _query = '');
                  },
                );
              },
            ),
          ),
      ],
    );
  }
}

class _AttachmentBar extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    // This is a UI-only mock; in a full app, this would open
    // a platform file picker and show selected files with size/MIME.
    return Row(
      children: [
        OutlinedButton.icon(
          onPressed: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text(
                  'Attachment picker is mocked. Integrate with file picker and backend.',
                ),
              ),
            );
          },
          icon: const Icon(Icons.attach_file),
          label: const Text('Add attachment'),
        ),
        const SizedBox(width: 8),
        Text(
          'No attachments',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }
}

