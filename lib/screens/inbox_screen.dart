import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/email_models.dart';
import '../providers/app_providers.dart';
import '../providers/auth_providers.dart';

typedef OpenMessageCallback = void Function(String id);
typedef VoidCallback = void Function();

class InboxScreen extends ConsumerStatefulWidget {
  const InboxScreen({
    super.key,
    required this.onCompose,
    required this.onOpenContacts,
    required this.onOpenSecurity,
    required this.onOpenMessage,
  });

  final VoidCallback onCompose;
  final VoidCallback onOpenContacts;
  final VoidCallback onOpenSecurity;
  final OpenMessageCallback onOpenMessage;

  @override
  ConsumerState<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends ConsumerState<InboxScreen> {
  final List<String> _folders = const ['Inbox', 'Sent', 'Drafts', 'Trash'];
  String _selectedFolder = 'Inbox';
  String? _selectedEmailId;

  @override
  Widget build(BuildContext context) {
    final allEmailsAsync = ref.watch(inboxProvider);
    final isWide = MediaQuery.of(context).size.width >= 900;

    return allEmailsAsync.when(
      data: (allEmails) {
        final emails =
            allEmails.where((e) => e.folder == _selectedFolder).toList();
        EmailEnvelope? selectedEmail;
        if (_selectedEmailId != null) {
          try {
            selectedEmail =
                emails.firstWhere((e) => e.id == _selectedEmailId);
          } catch (_) {
            selectedEmail = null;
          }
        }

        return _buildScaffold(context, emails, selectedEmail, isWide);
      },
      loading: () => Scaffold(
        appBar: AppBar(
          title: const Text('QMail'),
          actions: [
            IconButton(
              icon: const Icon(Icons.edit),
              onPressed: widget.onCompose,
            ),
          ],
        ),
        body: const Center(
          child: CircularProgressIndicator(),
        ),
      ),
      error: (error, stack) => Scaffold(
        appBar: AppBar(
          title: const Text('QMail'),
          actions: [
            IconButton(
              icon: const Icon(Icons.edit),
              onPressed: widget.onCompose,
            ),
          ],
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
                'Error loading inbox',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(
                error.toString(),
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () {
                  ref.refresh(inboxProvider);
                },
                child: const Text('Try Again'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Scaffold _buildScaffold(
    BuildContext context,
    List<EmailEnvelope> emails,
    EmailEnvelope? selectedEmail,
    bool isWide,
  ) {
    Widget buildFolders() {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Text(
              'QMail',
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          Expanded(
            child: ListView(
              children: [
                ..._folders.map(
                  (f) => ListTile(
                    leading: const Icon(Icons.folder),
                    title: Text(f),
                    selected: _selectedFolder == f,
                    onTap: () {
                      setState(() {
                        _selectedFolder = f;
                        _selectedEmailId = null;
                      });
                    },
                  ),
                ),
                const Divider(),
                ListTile(
                  leading: const Icon(Icons.people_alt),
                  title: const Text('Contacts'),
                  onTap: widget.onOpenContacts,
                ),
                ListTile(
                  leading: const Icon(Icons.security),
                  title: const Text('Security dashboard'),
                  onTap: widget.onOpenSecurity,
                ),
                ListTile(
                  leading: const Icon(Icons.settings),
                  title: const Text('Settings'),
                  onTap: widget.onOpenSecurity,
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: FilledButton.icon(
              onPressed: widget.onCompose,
              icon: const Icon(Icons.edit),
              label: const Text('Compose'),
            ),
          ),
        ],
      );
    }

    Widget buildInboxList() {
      return Column(
        children: [
          Padding(
            padding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    decoration: const InputDecoration(
                      prefixIcon: Icon(Icons.search),
                      hintText:
                          'Search by sender, subject, or date…',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    onChanged: (value) {
                      // In a real app, this would filter via backend.
                    },
                  ),
                ),
                const SizedBox(width: 8),
                PopupMenuButton<String>(
                  icon: const Icon(Icons.filter_list),
                  itemBuilder: (context) => const [
                    PopupMenuItem(
                      value: 'all',
                      child: Text('All'),
                    ),
                    PopupMenuItem(
                      value: 'unread',
                      child: Text('Unread'),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView.separated(
              itemCount: emails.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final email = emails[index];
                final isSelected =
                    selectedEmail != null &&
                    selectedEmail.id == email.id;
                return ListTile(
                  selected: isSelected,
                  leading: Icon(
                    email.isRead
                        ? Icons.mark_email_read_outlined
                        : Icons.mark_email_unread_outlined,
                    color: email.isRead
                        ? null
                        : Theme.of(context).colorScheme.primary,
                  ),
                  title: Row(
                    children: [
                      Expanded(
                        child: Text(
                          email.subject,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        TimeOfDay.fromDateTime(email.sentAt)
                            .format(context),
                        style: Theme.of(context)
                            .textTheme
                            .bodySmall,
                      ),
                    ],
                  ),
                  subtitle: Text(
                    '${email.from.displayName} — ${email.preview}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing: email.hasAttachments
                      ? const Icon(
                          Icons.attachment,
                          size: 18,
                        )
                      : null,
                  onTap: () {
                    setState(() {
                      _selectedEmailId = email.id;
                    });
                    if (!isWide) {
                      widget.onOpenMessage(email.id);
                    }
                  },
                );
              },
            ),
          ),
        ],
      );
    }

    Widget buildMessagePreview() {
      final email = selectedEmail;
      if (email == null) {
        return const Center(
          child: Text('Select a message to preview'),
        );
      }
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              email.subject,
              style: Theme.of(context)
                  .textTheme
                  .titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'From: ${email.from.displayName} <${email.from.email}>',
            ),
            Text(
              'To: ${email.to.map((c) => c.email).join(', ')}',
            ),

            const SizedBox(height: 16),
            Expanded(
              child: SingleChildScrollView(
                child: Text(
                  email.bodyText,
                  style: Theme.of(context)
                      .textTheme
                      .bodyMedium,
                ),
              ),
            ),
            if (email.attachments.isNotEmpty)
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
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
                        // In a real app, this would trigger a backend
                        // download/decrypt call to the Python service.
                      },
                    ),
                  ),
                ],
              ),
          ],
        ),
      );
    }

    if (isWide) {
      return Scaffold(
        body: Row(
          children: [
            SizedBox(
              width: 240,
              child: Material(
                color:
                    Theme.of(context).colorScheme.surfaceContainer,
                child: buildFolders(),
              ),
            ),
            const VerticalDivider(width: 1),
            Expanded(
              flex: 2,
              child: buildInboxList(),
            ),
            const VerticalDivider(width: 1),
            Expanded(
              flex: 3,
              child: buildMessagePreview(),
            ),
          ],
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Inbox'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => _handleRefresh(context, ref),
            tooltip: 'Refresh inbox',
          ),
          IconButton(
            icon: const Icon(Icons.security),
            onPressed: widget.onOpenSecurity,
          ),
          IconButton(
            icon: const Icon(Icons.people_alt),
            onPressed: widget.onOpenContacts,
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => _handleLogout(context, ref),
          ),
        ],
      ),
      drawer: Drawer(
        child: buildFolders(),
      ),
      body: buildInboxList(),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: widget.onCompose,
        icon: const Icon(Icons.edit),
        label: const Text('Compose'),
      ),
    );
  }

  Future<void> _handleLogout(
    BuildContext context,
    WidgetRef ref,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Sign Out'),
        content: const Text('Are you sure you want to sign out?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Sign Out'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      try {
        final authNotifier = ref.read(authStateProvider.notifier);
        await authNotifier.logout();
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Logout error: $e')),
          );
        }
      }
    }
  }

  Future<void> _handleRefresh(
    BuildContext context,
    WidgetRef ref,
  ) async {
    try {
      final authState = ref.read(authStateProvider);
      if (!authState.isAuthenticated || authState.token == null) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Not authenticated')),
          );
        }
        return;
      }

      final emailService = ref.read(emailServiceProvider);
      await emailService.refreshInbox(
        accessToken: authState.token!.accessToken,
      );

      // Refresh the inbox provider to update the UI
      if (mounted) {
        ref.refresh(inboxProvider);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Inbox refreshed'),
            duration: Duration(seconds: 1),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Refresh error: $e')),
        );
      }
    }
  }
}



