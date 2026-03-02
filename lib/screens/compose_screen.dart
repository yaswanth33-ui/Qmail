import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_quill/flutter_quill.dart' hide Text;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';

import '../models/email_models.dart';
import '../providers/app_providers.dart';
import '../providers/auth_providers.dart';
import '../widgets/animated_widgets.dart';

typedef VoidCallback = void Function();

class ComposeScreen extends ConsumerStatefulWidget {
  const ComposeScreen({
    super.key,
    required this.onClose,
    this.draftId,
    this.initialRecipient,
    this.initialSubject,
    this.initialBody,
    this.replyToId,
    this.isForward = false,
  });

  final VoidCallback onClose;
  
  // Draft editing support
  final String? draftId;
  final String? initialRecipient;
  final String? initialSubject;
  final String? initialBody;
  final String? replyToId; // ID of the email being replied to
  final bool isForward; // Whether this is a forwarded email

  @override
  ConsumerState<ComposeScreen> createState() => _ComposeScreenState();
}

class _ComposeScreenState extends ConsumerState<ComposeScreen> {
  final _toController = TextEditingController();
  final _subjectController = TextEditingController();
  late final QuillController _quillController;
  bool _viewOnce = false;
  
  // Draft auto-save state
  String? _draftId;
  Timer? _autoSaveTimer;
  bool _isSaving = false;
  bool _hasUnsavedChanges = false;
  bool _isSending = false;
  
  // Attachments
  List<PlatformFile> _attachments = [];

  FocusNode _subjectFocusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    _quillController = QuillController.basic();
    
    // Initialize from draft if provided
    if (widget.draftId != null) {
      _draftId = widget.draftId;
    }
    if (widget.initialRecipient != null) {
      _toController.text = widget.initialRecipient!;
    }
    if (widget.initialSubject != null) {
      _subjectController.text = widget.initialSubject!;
    }
    if (widget.initialBody != null && widget.initialBody!.isNotEmpty) {
      _quillController.document = Document()..insert(0, widget.initialBody!);
    }
    
    // Listen for changes to auto-save
    _toController.addListener(_onContentChanged);
    _subjectController.addListener(_onContentChanged);
    _subjectFocusNode.addListener(_onContentChanged);
    _quillController.document.changes.listen((_) => _onContentChanged());
  }

  void _onContentChanged() {
    // Only auto-save if subject field is NOT focused
    if (_subjectFocusNode.hasFocus) return;
    _hasUnsavedChanges = true;
    _scheduleAutoSave();
  }
  
  void _scheduleAutoSave() {
    _autoSaveTimer?.cancel();
    _autoSaveTimer = Timer(const Duration(seconds: 2), () {
      _saveDraft();
    });
  }
  
  Future<void> _saveDraft() async {
    if (_isSaving) return;
    
    final authState = ref.read(authStateProvider);
    if (authState.token == null || authState.user?.qmailAddress == null) return;
    
    final to = _toController.text.trim();
    final subject = _subjectController.text.trim();
    final bodyText = _quillController.document.toPlainText().trim();
    
    // Don't save empty drafts
    if (to.isEmpty && subject.isEmpty && bodyText.isEmpty) return;
    
    setState(() => _isSaving = true);
    
    try {
      final emailService = ref.read(emailServiceProvider);
      final result = await emailService.saveDraft(
        accessToken: authState.token!.accessToken,
        sender: authState.user!.qmailAddress,
        recipient: to,
        subject: subject,
        body: bodyText,
        draftId: _draftId,  // Pass existing draft ID if updating
      );
      
      final isNewDraft = _draftId == null;
      _draftId = result.id;
      _hasUnsavedChanges = false;
      
      // Only refresh inbox on first save (new draft creation)
      if (isNewDraft) {
        ref.invalidate(inboxProvider);
      }
    } catch (e) {
      // Silent fail for auto-save
    } finally {
      if (mounted) {
        setState(() => _isSaving = false);
      }
    }
  }
  
  Future<void> _deleteDraft() async {
    if (_draftId == null) return;
    
    final authState = ref.read(authStateProvider);
    if (authState.token == null) return;
    
    try {
      final emailService = ref.read(emailServiceProvider);
      await emailService.deleteEmail(
        accessToken: authState.token!.accessToken,
        emailId: _draftId!,
      );
    } catch (_) {
      // Ignore delete errors
    }
  }

  @override
  void dispose() {
    _autoSaveTimer?.cancel();
    _toController.dispose();
    _subjectController.dispose();
    _quillController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authStateProvider);
    final currentUser = authState.user;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            if (widget.replyToId != null) ...[
              const Icon(Icons.reply, size: 20),
              const SizedBox(width: 4),
              const Text('Reply'),
            ] else if (widget.isForward) ...[
              const Icon(Icons.forward, size: 20),
              const SizedBox(width: 4),
              const Text('Forward'),
            ] else
              const Text('Compose'),
            if (_isSaving) ...[
              const SizedBox(width: 8),
              const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              const SizedBox(width: 4),
              Text(
                'Saving...',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ] else if (_draftId != null && !_hasUnsavedChanges) ...[
              const SizedBox(width: 8),
              Icon(
                Icons.cloud_done,
                size: 16,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(width: 4),
              Text(
                'Draft saved',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ],
        ),
        actions: [
          TextButton.icon(
            onPressed: _isSending ? null : () async {
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

              if (senderUser?.qmailAddress == null) {
                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Error: Could not determine sender email'),
                  ),
                );
                return;
              }

              setState(() => _isSending = true);

              try {
                // Cancel any pending auto-save
                _autoSaveTimer?.cancel();
                
                // Get the user's selected key exchange mode (PQC or BB84)
                final keyExchangeMode = ref.read(keyExchangeModeProvider);
                
                final sentResponse = await emailService.sendEmail(
                  accessToken: authState.token!.accessToken,
                  sender: senderUser!.qmailAddress,
                  recipient: to,
                  subject: subject,
                  body: bodyText,
                  viewOnce: _viewOnce,
                  keyExchangeAlgorithm: keyExchangeMode.value, // Pass selected mode
                  inReplyTo: widget.replyToId,
                );

                // Upload attachments to the sent email (E2E encrypted with session key)
                if (_attachments.isNotEmpty && sentResponse.sessionKeyHex != null) {
                  for (final file in _attachments) {
                    if (file.bytes != null) {
                      await emailService.uploadAttachment(
                        accessToken: authState.token!.accessToken,
                        emailId: sentResponse.id,
                        filename: file.name,
                        mimeType: _getMimeType(file.name),
                        bytes: file.bytes!,
                        sessionKeyHex: sentResponse.sessionKeyHex!, // E2E: encrypt with email's session key
                      );
                    }
                  }
                } else if (_attachments.isNotEmpty) {
                }

                // Delete the draft since email was sent successfully
                await _deleteDraft();
                
                // Refresh inbox to show the sent email
                ref.invalidate(inboxProvider);

                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Message sent via Qumail backend.'),
                  ),
                );
                widget.onClose();
              } catch (e) {
                if (!context.mounted) return;
                setState(() => _isSending = false);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('Failed to send message: $e'),
                  ),
                );
              }
            },
            icon: _isSending 
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.send),
            label: Text(_isSending ? 'Sending...' : 'Send'),
          ),
        ],
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final isWide = constraints.maxWidth > 700;
          final content = _buildForm(context);

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
  ) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SlideInWidget(
            delay: const Duration(milliseconds: 0),
            direction: SlideDirection.bottom,
            child: _RecipientField(
              controller: _toController,
            ),
          ),
          const SizedBox(height: 8),
          SlideInWidget(
            delay: const Duration(milliseconds: 50),
            direction: SlideDirection.bottom,
            child: TextField(
              controller: _subjectController,
              focusNode: _subjectFocusNode,
              decoration: const InputDecoration(
                labelText: 'Subject',
                border: OutlineInputBorder(),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: FadeInWidget(
              delay: const Duration(milliseconds: 100),
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
          ),
          const SizedBox(height: 12),
          // Key Exchange Mode Selection
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
                  Icons.key,
                  size: 20,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Key Exchange:',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
                Consumer(
                  builder: (context, ref, child) {
                    final mode = ref.watch(keyExchangeModeProvider);
                    return DropdownButton<KeyExchangeMode>(
                      value: mode,
                      isDense: true,
                      underline: const SizedBox(),
                      items: KeyExchangeMode.values.map((m) {
                        return DropdownMenuItem<KeyExchangeMode>(
                          value: m,
                          child: Text(
                            m.label,
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        );
                      }).toList(),
                      onChanged: (newMode) {
                        if (newMode != null) {
                          ref.read(keyExchangeModeProvider.notifier).setMode(newMode);
                        }
                      },
                    );
                  },
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
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
                  Icons.enhanced_encryption,
                  size: 20,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'One-Time Pad: Perfect secrecy encryption',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
                Checkbox(
                  value: _viewOnce,
                  onChanged: (value) {
                    setState(() {
                      _viewOnce = value ?? false;
                      // Clear attachments when OTP is enabled (OTP doesn't support attachments)
                      if (_viewOnce && _attachments.isNotEmpty) {
                        _attachments.clear();
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Attachments removed: One-Time Pad encryption does not support attachments'),
                          ),
                        );
                      }
                    });
                  },
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          // Hide attachment bar when OTP is enabled
          if (!_viewOnce)
            _AttachmentBar(
              attachments: _attachments,
              onAdd: _pickAttachments,
              onRemove: _removeAttachment,
            )
          else
            Container(
              decoration: BoxDecoration(
                color: Colors.purple.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Icon(Icons.info_outline, size: 18, color: Colors.purple.shade700),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Attachments not available with One-Time Pad encryption',
                      style: TextStyle(fontSize: 12, color: Colors.purple.shade700),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _pickAttachments() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        allowMultiple: true,
        type: FileType.any,
        withData: true,
      );
      
      if (result != null && result.files.isNotEmpty) {
        for (final f in result.files) {
        }
        setState(() {
          _attachments.addAll(result.files);
          _hasUnsavedChanges = true;
        });
      } else {
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to pick files: $e')),
        );
      }
    }
  }

  String _getMimeType(String filename) {
    final ext = filename.split('.').last.toLowerCase();
    const mimeTypes = {
      // Images
      'jpg': 'image/jpeg',
      'jpeg': 'image/jpeg',
      'png': 'image/png',
      'gif': 'image/gif',
      'bmp': 'image/bmp',
      'webp': 'image/webp',
      'svg': 'image/svg+xml',
      'ico': 'image/x-icon',
      'tiff': 'image/tiff',
      'tif': 'image/tiff',
      // Documents
      'pdf': 'application/pdf',
      'doc': 'application/msword',
      'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'xls': 'application/vnd.ms-excel',
      'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'ppt': 'application/vnd.ms-powerpoint',
      'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'odt': 'application/vnd.oasis.opendocument.text',
      'ods': 'application/vnd.oasis.opendocument.spreadsheet',
      'odp': 'application/vnd.oasis.opendocument.presentation',
      'rtf': 'application/rtf',
      // Text
      'txt': 'text/plain',
      'csv': 'text/csv',
      'html': 'text/html',
      'htm': 'text/html',
      'xml': 'text/xml',
      'json': 'application/json',
      'md': 'text/markdown',
      // Audio
      'mp3': 'audio/mpeg',
      'wav': 'audio/wav',
      'ogg': 'audio/ogg',
      'flac': 'audio/flac',
      'aac': 'audio/aac',
      'm4a': 'audio/mp4',
      'wma': 'audio/x-ms-wma',
      // Video
      'mp4': 'video/mp4',
      'avi': 'video/x-msvideo',
      'mov': 'video/quicktime',
      'mkv': 'video/x-matroska',
      'wmv': 'video/x-ms-wmv',
      'flv': 'video/x-flv',
      'webm': 'video/webm',
      '3gp': 'video/3gpp',
      // Archives
      'zip': 'application/zip',
      'rar': 'application/vnd.rar',
      '7z': 'application/x-7z-compressed',
      'tar': 'application/x-tar',
      'gz': 'application/gzip',
      'bz2': 'application/x-bzip2',
      // Code
      'js': 'application/javascript',
      'ts': 'application/typescript',
      'py': 'text/x-python',
      'java': 'text/x-java-source',
      'c': 'text/x-c',
      'cpp': 'text/x-c++',
      'h': 'text/x-c',
      'cs': 'text/x-csharp',
      'dart': 'application/dart',
      // Other
      'exe': 'application/x-msdownload',
      'dll': 'application/x-msdownload',
      'apk': 'application/vnd.android.package-archive',
      'ipa': 'application/octet-stream',
    };
    return mimeTypes[ext] ?? 'application/octet-stream';
  }

  void _removeAttachment(int index) {
    setState(() {
      _attachments.removeAt(index);
      _hasUnsavedChanges = true;
    });
  }
}

class _RecipientField extends StatelessWidget {
  const _RecipientField({
    required this.controller,
  });

  final TextEditingController controller;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      decoration: const InputDecoration(
        labelText: 'To',
        hintText: 'Enter email address…',
        border: OutlineInputBorder(),
      ),
      keyboardType: TextInputType.emailAddress,
    );
  }
}

class _AttachmentBar extends StatelessWidget {
  const _AttachmentBar({
    required this.attachments,
    required this.onAdd,
    required this.onRemove,
  });

  final List<PlatformFile> attachments;
  final VoidCallback onAdd;
  final void Function(int index) onRemove;

  String _formatSize(int bytes) {
    if (bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    var size = bytes.toDouble();
    var unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    return '${size.toStringAsFixed(1)} ${units[unitIndex]}';
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            OutlinedButton.icon(
              onPressed: onAdd,
              icon: const Icon(Icons.attach_file),
              label: const Text('Add attachment'),
            ),
            const SizedBox(width: 8),
            Text(
              attachments.isEmpty 
                  ? 'No attachments' 
                  : '${attachments.length} attachment${attachments.length > 1 ? 's' : ''}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
        if (attachments.isNotEmpty) ...[
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: [
              for (int i = 0; i < attachments.length; i++)
                Chip(
                  avatar: const Icon(Icons.insert_drive_file, size: 18),
                  label: Text(
                    '${attachments[i].name} (${_formatSize(attachments[i].size)})',
                    style: const TextStyle(fontSize: 12),
                  ),
                  deleteIcon: const Icon(Icons.close, size: 16),
                  onDeleted: () => onRemove(i),
                ),
            ],
          ),
        ],
      ],
    );
  }
}

