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

typedef OpenMessageCallback = void Function(String id);
typedef OpenDraftCallback = void Function(String id, String recipient, String subject, String body);
typedef VoidCallback = void Function();

class InboxScreen extends ConsumerStatefulWidget {
  const InboxScreen({
    super.key,
    required this.onCompose,
    required this.onOpenProfile,
    required this.onOpenMessage,
    required this.onOpenDraft,
  });

  final VoidCallback onCompose;
  final VoidCallback onOpenProfile;
  final OpenMessageCallback onOpenMessage;
  final OpenDraftCallback onOpenDraft;

  @override
  ConsumerState<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends ConsumerState<InboxScreen>
    with SingleTickerProviderStateMixin {
  final List<String> _folders = const ['Inbox', 'Sent', 'Drafts', 'Trash'];
  String _selectedFolder = 'Inbox';
  String? _selectedEmailId;
  late AnimationController _fabController;
  late Animation<double> _fabAnimation;
  bool _isRefreshing = false;
  
  // Multi-select state
  bool _isMultiSelectMode = false;
  final Set<String> _selectedEmailIds = {};
  
  // Search state
  final TextEditingController _searchController = TextEditingController();
  String _searchQuery = '';
  
  // Sort state
  String _sortBy = 'date_desc'; // date_desc, date_asc, sender_asc, sender_desc, subject_asc, subject_desc

  @override
  void initState() {
    super.initState();
    _fabController = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );
    _fabAnimation = CurvedAnimation(
      parent: _fabController,
      curve: Curves.elasticOut,
    );
    // Animate FAB in after slight delay
    Future.delayed(const Duration(milliseconds: 300), () {
      if (mounted) _fabController.forward();
    });
  }

  @override
  void dispose() {
    _fabController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  Widget _buildAttachmentCard(BuildContext context, Attachment attachment, String? sessionKeyHex) {
    return AttachmentCard(
      attachment: attachment,
      onDownload: () => _downloadAttachment(context, attachment, sessionKeyHex),
      compact: true,
    );
  }

  Widget _buildCompactSignatureStatus(DecryptedEmailResponse? decryptedData, bool signatureValid) {
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

  Future<void> _downloadAttachment(BuildContext context, Attachment attachment, String? sessionKeyHex) async {
    final authState = ref.read(authStateProvider);
    if (authState.token == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Not authenticated')),
      );
      return;
    }

    try {
      // Show downloading indicator
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

      // Let user choose where to save
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
                  // Open containing folder on Windows
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
      
      // Clear selection if this email was selected
      if (_selectedEmailId == email.id) {
        setState(() => _selectedEmailId = null);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete: $e')),
        );
      }
    }
  }

  void _toggleEmailSelection(String emailId) {
    setState(() {
      if (_selectedEmailIds.contains(emailId)) {
        _selectedEmailIds.remove(emailId);
        if (_selectedEmailIds.isEmpty) {
          _isMultiSelectMode = false;
        }
      } else {
        _selectedEmailIds.add(emailId);
      }
    });
  }

  void _enterMultiSelectMode(String emailId) {
    setState(() {
      _isMultiSelectMode = true;
      _selectedEmailIds.add(emailId);
    });
  }

  void _exitMultiSelectMode() {
    setState(() {
      _isMultiSelectMode = false;
      _selectedEmailIds.clear();
    });
  }

  void _selectAll(List<EmailEnvelope> emails) {
    setState(() {
      _selectedEmailIds.addAll(emails.map((e) => e.id));
    });
  }

  bool _matchesSearch(EmailEnvelope email, String query) {
    if (query.isEmpty) return true;
    
    final lowerQuery = query.toLowerCase();
    
    // Search in sender name and email
    final senderName = email.from.displayName.toLowerCase();
    final senderEmail = email.from.email.toLowerCase();
    if (senderName.contains(lowerQuery) || senderEmail.contains(lowerQuery)) {
      return true;
    }
    
    // Search in recipient (for sent emails)
    for (final recipient in email.to) {
      if (recipient.displayName.toLowerCase().contains(lowerQuery) ||
          recipient.email.toLowerCase().contains(lowerQuery)) {
        return true;
      }
    }
    
    // Search in subject
    if (email.subject.toLowerCase().contains(lowerQuery)) {
      return true;
    }
    
    // Search in date (format: "Jan 15", "2026", etc.)
    final dateStr = _formatEmailDate(email.sentAt).toLowerCase();
    if (dateStr.contains(lowerQuery)) {
      return true;
    }
    
    return false;
  }

  String _formatEmailDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);
    
    if (diff.inDays == 0) {
      return '${date.hour}:${date.minute.toString().padLeft(2, '0')}';
    } else if (diff.inDays < 7) {
      const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
      return days[date.weekday % 7];
    } else if (date.year == now.year) {
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      return '${months[date.month - 1]} ${date.day}';
    } else {
      return '${date.day}/${date.month}/${date.year}';
    }
  }

  Future<void> _handleMultiDelete(BuildContext context, List<EmailEnvelope> allEmails) async {
    final authState = ref.read(authStateProvider);
    if (authState.token == null) return;
    
    final emailService = ref.read(emailServiceProvider);
    final selectedEmails = allEmails.where((e) => _selectedEmailIds.contains(e.id)).toList();
    
    if (selectedEmails.isEmpty) return;
    
    // Check if any are in trash (permanent delete)
    final hasTrashEmails = selectedEmails.any((e) => e.folder == 'Trash');
    
    // Show confirmation dialog
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Delete ${selectedEmails.length} email${selectedEmails.length > 1 ? 's' : ''}?'),
        content: Text(
          hasTrashEmails
              ? 'Some emails are in Trash and will be permanently deleted.'
              : 'Selected emails will be moved to Trash.',
        ),
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
    ) ?? false;
    
    if (!confirmed) return;
    
    int successCount = 0;
    int failCount = 0;
    
    for (final email in selectedEmails) {
      try {
        if (email.folder == 'Trash') {
          await emailService.deleteEmail(
            accessToken: authState.token!.accessToken,
            emailId: email.id,
          );
        } else {
          await emailService.trashEmail(
            accessToken: authState.token!.accessToken,
            emailId: email.id,
          );
        }
        successCount++;
      } catch (e) {
        failCount++;
      }
    }
    
    // Exit multi-select mode
    _exitMultiSelectMode();
    
    // Refresh inbox
    ref.invalidate(inboxProvider);
    
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            failCount == 0
                ? 'Deleted $successCount email${successCount > 1 ? 's' : ''}'
                : 'Deleted $successCount, failed $failCount',
          ),
        ),
      );
    }
  }

  List<EmailEnvelope> _sortEmails(List<EmailEnvelope> emails) {
    final sorted = List<EmailEnvelope>.from(emails);
    
    switch (_sortBy) {
      case 'date_desc':
        sorted.sort((a, b) => b.sentAt.compareTo(a.sentAt));
        break;
      case 'date_asc':
        sorted.sort((a, b) => a.sentAt.compareTo(b.sentAt));
        break;
      case 'sender_asc':
        sorted.sort((a, b) => a.from.displayName.toLowerCase().compareTo(b.from.displayName.toLowerCase()));
        break;
      case 'sender_desc':
        sorted.sort((a, b) => b.from.displayName.toLowerCase().compareTo(a.from.displayName.toLowerCase()));
        break;
      case 'subject_asc':
        sorted.sort((a, b) => a.subject.toLowerCase().compareTo(b.subject.toLowerCase()));
        break;
      case 'subject_desc':
        sorted.sort((a, b) => b.subject.toLowerCase().compareTo(a.subject.toLowerCase()));
        break;
    }
    
    return sorted;
  }

  @override
  Widget build(BuildContext context) {
    final allEmailsAsync = ref.watch(inboxProvider);
    final isWide = MediaQuery.of(context).size.width >= 900;

    return allEmailsAsync.when(
      data: (allEmails) {
        var emails =
            allEmails.where((e) => e.folder == _selectedFolder).toList();
        
        // Apply search filter
        if (_searchQuery.isNotEmpty) {
          emails = emails.where((email) => _matchesSearch(email, _searchQuery)).toList();
        }
        
        // Apply sorting
        emails = _sortEmails(emails);
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
          title: const Text('QUMail'),
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
          title: const Text('QUMail'),
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
                  ref.invalidate(inboxProvider);
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
              'QUMail',
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
                        // Exit multi-select mode when changing folders
                        _isMultiSelectMode = false;
                        _selectedEmailIds.clear();
                        // Clear search when changing folders
                        _searchController.clear();
                        _searchQuery = '';
                      });
                    },
                  ),
                ),
                const Divider(),
                ListTile(
                  leading: const Icon(Icons.person),
                  title: const Text('Profile'),
                  onTap: widget.onOpenProfile,
                ),
                ListTile(
                  leading: const Icon(Icons.logout),
                  title: const Text('Logout'),
                  onTap: () => _handleLogout(context, ref),
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
                    controller: _searchController,
                    decoration: InputDecoration(
                      prefixIcon: const Icon(Icons.search),
                      hintText: 'Search by sender, subject, or date…',
                      border: const OutlineInputBorder(),
                      isDense: true,
                      suffixIcon: _searchQuery.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear),
                              onPressed: () {
                                _searchController.clear();
                                setState(() => _searchQuery = '');
                              },
                            )
                          : null,
                    ),
                    onChanged: (value) {
                      setState(() => _searchQuery = value.trim().toLowerCase());
                    },
                  ),
                ),
                const SizedBox(width: 4),
                TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0.0, end: _isRefreshing ? 1.0 : 0.0),
                  duration: const Duration(milliseconds: 300),
                  builder: (context, value, child) {
                    return Transform.rotate(
                      angle: value * 2 * 3.14159,
                      child: IconButton(
                        icon: const Icon(Icons.refresh),
                        onPressed: _isRefreshing
                            ? null
                            : () => _handleRefresh(context, ref),
                        tooltip: 'Refresh inbox',
                      ),
                    );
                  },
                ),
                const SizedBox(width: 4),
                PopupMenuButton<String>(
                  icon: const Icon(Icons.sort),
                  tooltip: 'Sort emails',
                  onSelected: (value) {
                    setState(() => _sortBy = value);
                  },
                  itemBuilder: (context) => [
                    PopupMenuItem(
                      value: 'date_desc',
                      child: Row(
                        children: [
                          Icon(
                            Icons.arrow_downward,
                            size: 16,
                            color: _sortBy == 'date_desc' ? Theme.of(context).colorScheme.primary : null,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'Date (Newest first)',
                            style: TextStyle(
                              fontWeight: _sortBy == 'date_desc' ? FontWeight.bold : null,
                            ),
                          ),
                        ],
                      ),
                    ),
                    PopupMenuItem(
                      value: 'date_asc',
                      child: Row(
                        children: [
                          Icon(
                            Icons.arrow_upward,
                            size: 16,
                            color: _sortBy == 'date_asc' ? Theme.of(context).colorScheme.primary : null,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'Date (Oldest first)',
                            style: TextStyle(
                              fontWeight: _sortBy == 'date_asc' ? FontWeight.bold : null,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const PopupMenuDivider(),
                    PopupMenuItem(
                      value: 'sender_asc',
                      child: Row(
                        children: [
                          Icon(
                            Icons.sort_by_alpha,
                            size: 16,
                            color: _sortBy == 'sender_asc' ? Theme.of(context).colorScheme.primary : null,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'Sender (A-Z)',
                            style: TextStyle(
                              fontWeight: _sortBy == 'sender_asc' ? FontWeight.bold : null,
                            ),
                          ),
                        ],
                      ),
                    ),
                    PopupMenuItem(
                      value: 'sender_desc',
                      child: Row(
                        children: [
                          Icon(
                            Icons.sort_by_alpha,
                            size: 16,
                            color: _sortBy == 'sender_desc' ? Theme.of(context).colorScheme.primary : null,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'Sender (Z-A)',
                            style: TextStyle(
                              fontWeight: _sortBy == 'sender_desc' ? FontWeight.bold : null,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const PopupMenuDivider(),
                    PopupMenuItem(
                      value: 'subject_asc',
                      child: Row(
                        children: [
                          Icon(
                            Icons.title,
                            size: 16,
                            color: _sortBy == 'subject_asc' ? Theme.of(context).colorScheme.primary : null,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'Subject (A-Z)',
                            style: TextStyle(
                              fontWeight: _sortBy == 'subject_asc' ? FontWeight.bold : null,
                            ),
                          ),
                        ],
                      ),
                    ),
                    PopupMenuItem(
                      value: 'subject_desc',
                      child: Row(
                        children: [
                          Icon(
                            Icons.title,
                            size: 16,
                            color: _sortBy == 'subject_desc' ? Theme.of(context).colorScheme.primary : null,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'Subject (Z-A)',
                            style: TextStyle(
                              fontWeight: _sortBy == 'subject_desc' ? FontWeight.bold : null,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: emails.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.inbox_outlined,
                          size: 64,
                          color: Theme.of(context).colorScheme.outline,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'No emails in $_selectedFolder',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            color: Theme.of(context).colorScheme.outline,
                          ),
                        ),
                      ],
                    ),
                  )
                : ListView.separated(
              itemCount: emails.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final email = emails[index];
                final authState = ref.read(authStateProvider);
                final currentUserEmail = authState.user?.qmailAddress ?? '';
                final isSelected =
                    selectedEmail != null &&
                    selectedEmail.id == email.id;
                final isInTrash = email.folder == 'Trash';
                
                // Format subtitle: show 'me' for sent, 'you' for inbox
                String subtitleText;
                if (_selectedFolder == 'Drafts' || _selectedFolder == 'Sent') {
                  if (email.to.isNotEmpty) {
                    final firstRecipient = email.to.first;
                    if (firstRecipient.email.toLowerCase() == currentUserEmail.toLowerCase()) {
                      subtitleText = 'To: you';
                    } else {
                      subtitleText = 'To: ${firstRecipient.displayName}';
                    }
                  } else {
                    subtitleText = 'To: No recipient';
                  }
                } else {
                  // Inbox/Trash: show sender
                  if (email.from.email.toLowerCase() == currentUserEmail.toLowerCase()) {
                    subtitleText = 'me';
                  } else {
                    subtitleText = email.from.displayName;
                  }
                }
                
                return Dismissible(
                  key: Key('email-${email.id}'),
                  direction: DismissDirection.endToStart,
                  background: Container(
                    color: Colors.red,
                    alignment: Alignment.centerRight,
                    padding: const EdgeInsets.only(right: 20),
                    child: Icon(
                      isInTrash ? Icons.delete_forever : Icons.delete,
                      color: Colors.white,
                    ),
                  ),
                  confirmDismiss: (direction) async {
                    if (isInTrash) {
                      // Confirm permanent delete
                      final confirmed = await showDialog<bool>(
                        context: context,
                        builder: (ctx) => AlertDialog(
                          title: const Text('Delete Permanently?'),
                          content: const Text('This email will be permanently deleted.'),
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
                      ) ?? false;
                      
                      if (!confirmed) return false;
                    }
                    
                    // Actually perform the delete
                    await _handleDelete(context, email);
                    return false; // We handle removal via invalidate, so don't auto-dismiss
                  },
                  child: AnimatedListItem(
                    index: index,
                    child: Container(
                      decoration: BoxDecoration(
                        color: email.isRead 
                            ? null 
                            : Theme.of(context).colorScheme.primaryContainer.withOpacity(0.3),
                        border: Border(
                          left: BorderSide(
                            color: email.isRead 
                                ? Colors.transparent 
                                : Theme.of(context).colorScheme.primary,
                            width: 5,
                          ),
                        ),
                      ),
                      child: ListTile(
                        selected: isSelected || _selectedEmailIds.contains(email.id),
                        tileColor: _selectedEmailIds.contains(email.id)
                            ? Theme.of(context).colorScheme.primaryContainer.withOpacity(0.5)
                            : email.isRead 
                                ? null 
                                : Theme.of(context).colorScheme.primaryContainer.withOpacity(0.1),
                        leading: _isMultiSelectMode
                            ? Checkbox(
                                value: _selectedEmailIds.contains(email.id),
                                onChanged: (_) => _toggleEmailSelection(email.id),
                              )
                            : TweenAnimationBuilder<double>(
                                tween: Tween(begin: 0.0, end: 1.0),
                                duration: Duration(milliseconds: 300 + index * 50),
                                curve: Curves.elasticOut,
                                builder: (context, value, child) {
                                  return Transform.scale(
                                    scale: value,
                                    child: child,
                                  );
                                },
                                child: CircleAvatar(
                                  backgroundColor: email.isRead
                                      ? Theme.of(context).colorScheme.surfaceContainerHighest
                                      : Theme.of(context).colorScheme.primary,
                                  child: Icon(
                                    email.isRead
                                        ? Icons.mail_outline
                                        : Icons.mail,
                                    color: email.isRead
                                        ? Theme.of(context).colorScheme.onSurfaceVariant
                                        : Theme.of(context).colorScheme.onPrimary,
                                    size: 20,
                                  ),
                                ),
                              ),
                        title: Row(
                          children: [
                            Expanded(
                              child: Text(
                                email.subject,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  fontWeight: email.isRead ? FontWeight.normal : FontWeight.bold,
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              TimeOfDay.fromDateTime(email.sentAt)
                                  .format(context),
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                fontWeight: email.isRead ? FontWeight.normal : FontWeight.w600,
                                color: email.isRead 
                                    ? null 
                                    : Theme.of(context).colorScheme.primary,
                              ),
                            ),
                          ],
                        ),
                        subtitle: Text(
                          subtitleText,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontWeight: email.isRead ? FontWeight.normal : FontWeight.w500,
                          ),
                        ),
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (email.hasAttachments)
                            const Icon(Icons.attachment, size: 18),
                          if (!_isMultiSelectMode)
                            IconButton(
                              icon: Icon(
                                isInTrash ? Icons.delete_forever : Icons.delete_outline,
                                size: 20,
                              ),
                              onPressed: () => _handleDelete(context, email),
                              tooltip: isInTrash ? 'Delete permanently' : 'Move to trash',
                            ),
                        ],
                      ),
                      onLongPress: () {
                        if (!_isMultiSelectMode) {
                          _enterMultiSelectMode(email.id);
                        }
                      },
                      onTap: () {
                        // In multi-select mode, toggle selection
                        if (_isMultiSelectMode) {
                          _toggleEmailSelection(email.id);
                          return;
                        }
                        
                        setState(() {
                          _selectedEmailId = email.id;
                        });
                        
                        // If this is a draft, open in compose mode
                        if (email.folder == 'Drafts') {
                          widget.onOpenDraft(
                            email.id,
                            email.to.isNotEmpty ? email.to.first.email : '',
                            email.subject,
                            email.bodyText,
                          );
                          return;
                        }
                        
                        if (!isWide) {
                          widget.onOpenMessage(email.id);
                        }
                      },
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      );
    }

    Widget buildPreviewContent(EmailEnvelope email, String bodyText, bool signatureValid, DecryptedEmailResponse? decryptedData) {
      final authState = ref.read(authStateProvider);
      final currentUserEmail = authState.user?.qmailAddress ?? '';
      final isEncrypted = email.securityLevel != SecurityLevel.classical;
      final isDecrypted = decryptedData != null;
      
      // Format From field: show 'me' for sent emails from current user
      final fromDisplay = (email.folder == 'Sent' && email.from.email.toLowerCase() == currentUserEmail.toLowerCase())
          ? 'me <${email.from.email}>'
          : '${email.from.displayName} <${email.from.email}>';
      
      // Format To field: show 'you' for inbox emails to current user
      final toDisplay = (email.folder == 'Inbox' && email.to.any((c) => c.email.toLowerCase() == currentUserEmail.toLowerCase()))
          ? email.to.map((c) => c.email.toLowerCase() == currentUserEmail.toLowerCase() ? 'you' : c.email).join(', ')
          : email.to.map((c) => c.email).join(', ');
      
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              email.subject,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              'From: $fromDisplay',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              'To: $toDisplay',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 16),
            Expanded(
              child: SizedBox(
                width: double.infinity,
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SelectableText(
                        bodyText,
                        style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          height: 1.6,
                        ),
                      ),
                      if (isEncrypted && isDecrypted) ...[
                        const SizedBox(height: 12),
                        _buildCompactSignatureStatus(decryptedData, signatureValid),
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
                      ...email.attachments.map((a) => _buildAttachmentCard(context, a, email.sessionKeyHex)),
                    ],
                  ],
                ),
              ),
              ),
            ),
          ],
        ),
      );
    }

    Widget buildMessagePreview() {
      final email = selectedEmail;
      if (email == null) {
        return const Center(
          child: Text('Select a message to preview'),
        );
      }
      
      // Use the decrypt provider to get actual content
      final decryptedAsync = ref.watch(openEmailProvider(email.id));
      
      Widget previewWithActions(Widget content, String bodyText) {
        final date = '${email.sentAt.day}/${email.sentAt.month}/${email.sentAt.year}';
        return Column(
          children: [
            Expanded(child: content),
            if (email.folder != 'Drafts') ...[
              const Divider(height: 1),
              SafeArea(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Row(
                    children: [
                      if (email.folder != 'Sent') ...[
                        FilledButton.icon(
                          onPressed: () {
                            widget.onOpenDraft(email.id, email.from.email, '', '');
                          },
                          icon: const Icon(Icons.reply),
                          label: const Text('Reply'),
                        ),
                        const SizedBox(width: 8),
                      ],
                      OutlinedButton.icon(
                        onPressed: () {
                          final fwdSubject = email.subject.startsWith('Fwd: ')
                              ? email.subject
                              : 'Fwd: ${email.subject}';
                          final fwdBody = '\n\n---------- Forwarded message ----------\nFrom: ${email.from.displayName} <${email.from.email}>\nDate: $date\nSubject: ${email.subject}\n\n$bodyText';
                          widget.onOpenDraft('', '', fwdSubject, fwdBody);
                        },
                        icon: const Icon(Icons.forward),
                        label: const Text('Forward'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton.icon(
                        onPressed: () => _handleDelete(context, email),
                        icon: const Icon(Icons.delete_outline),
                        label: Text(
                          email.folder == 'Trash' ? 'Delete Forever' : 'Delete',
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        );
      }
      
      return decryptedAsync.when(
        data: (decryptedData) {
          final bodyText = decryptedData?.body ?? email.bodyText;
          final signatureValid = decryptedData?.isSignatureValid ?? false;
          
          return previewWithActions(
            buildPreviewContent(email, bodyText, signatureValid, decryptedData),
            bodyText,
          );
        },
        loading: () => previewWithActions(
          buildPreviewContent(email, 'Decrypting...', false, null),
          '',
        ),
        error: (error, stack) => previewWithActions(
          buildPreviewContent(email, 'Error: $error', false, null),
          '',
        ),
      );
    }
    if (isWide) {
      return Scaffold(
        appBar: _isMultiSelectMode
            ? AppBar(
                leading: IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: _exitMultiSelectMode,
                  tooltip: 'Cancel selection',
                ),
                title: Text('${_selectedEmailIds.length} selected'),
                actions: [
                  IconButton(
                    icon: const Icon(Icons.select_all),
                    onPressed: () => _selectAll(emails),
                    tooltip: 'Select all',
                  ),
                  IconButton(
                    icon: const Icon(Icons.delete),
                    onPressed: _selectedEmailIds.isNotEmpty
                        ? () => _handleMultiDelete(context, emails)
                        : null,
                    tooltip: 'Delete selected',
                  ),
                ],
              )
            : null,
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
      appBar: _isMultiSelectMode
          ? AppBar(
              leading: IconButton(
                icon: const Icon(Icons.close),
                onPressed: _exitMultiSelectMode,
                tooltip: 'Cancel selection',
              ),
              title: Text('${_selectedEmailIds.length} selected'),
              actions: [
                IconButton(
                  icon: const Icon(Icons.select_all),
                  onPressed: () => _selectAll(emails),
                  tooltip: 'Select all',
                ),
                IconButton(
                  icon: const Icon(Icons.delete),
                  onPressed: _selectedEmailIds.isNotEmpty
                      ? () => _handleMultiDelete(context, emails)
                      : null,
                  tooltip: 'Delete selected',
                ),
              ],
            )
          : AppBar(
              title: Text(_selectedFolder),
              actions: [
                IconButton(
                  icon: const Icon(Icons.person),
                  tooltip: 'Profile',
                  onPressed: widget.onOpenProfile,
                ),
                IconButton(
                  icon: const Icon(Icons.logout),
                  tooltip: 'Logout',
                  onPressed: () => _handleLogout(context, ref),
                ),
              ],
            ),
      drawer: Drawer(
        child: buildFolders(),
      ),
      body: buildInboxList(),
      floatingActionButton: ScaleTransition(
        scale: _fabAnimation,
        child: FloatingActionButton.extended(
          onPressed: widget.onCompose,
          icon: const Icon(Icons.edit),
          label: const Text('Compose'),
        ),
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
    if (_isRefreshing) return;
    
    setState(() => _isRefreshing = true);
    
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
        ref.invalidate(inboxProvider);
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
    } finally {
      if (mounted) {
        setState(() => _isRefreshing = false);
      }
    }
  }
}



