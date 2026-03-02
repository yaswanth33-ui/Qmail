import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../models/email_models.dart';

/// Modern attachment card with file type visualization and actions
class AttachmentCard extends StatelessWidget {
  const AttachmentCard({
    super.key,
    required this.attachment,
    this.onDownload,
    this.onOpen,
    this.onPreview,
    this.showPreview = false,
    this.previewData,
    this.isDownloading = false,
    this.compact = false,
  });

  final Attachment attachment;
  final VoidCallback? onDownload;
  final VoidCallback? onOpen;
  final VoidCallback? onPreview;
  final bool showPreview;
  final Uint8List? previewData;
  final bool isDownloading;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final typeInfo = _getTypeInfo(attachment.type);

    if (compact) {
      return _buildCompactCard(context, typeInfo, colorScheme);
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: colorScheme.outlineVariant.withOpacity(0.5),
        ),
        boxShadow: [
          BoxShadow(
            color: colorScheme.shadow.withOpacity(0.05),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Preview area for images
          if (showPreview && attachment.canPreview && previewData != null)
            ClipRRect(
              borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
              child: Container(
                constraints: const BoxConstraints(maxHeight: 200),
                width: double.infinity,
                child: Image.memory(
                  previewData!,
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => _buildPreviewPlaceholder(typeInfo, colorScheme),
                ),
              ),
            )
          else if (showPreview && attachment.isMedia)
            _buildMediaPreviewPlaceholder(context, typeInfo, colorScheme),

          // File info and actions
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                // File type icon
                _buildTypeIcon(typeInfo, colorScheme),
                const SizedBox(width: 12),

                // File info
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        attachment.fileName,
                        style: theme.textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          _buildInfoChip(
                            context,
                            attachment.sizeLabel,
                            Icons.data_usage_outlined,
                          ),
                          const SizedBox(width: 8),
                          _buildInfoChip(
                            context,
                            attachment.typeLabel,
                            typeInfo.icon,
                          ),
                          if (attachment.isAesGcmProtected) ...[
                            const SizedBox(width: 8),
                            _buildSecurityBadge(context),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),

                // Actions
                if (isDownloading)
                  const Padding(
                    padding: EdgeInsets.all(8),
                    child: SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                else
                  _buildActions(context, colorScheme),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCompactCard(BuildContext context, _TypeInfo typeInfo, ColorScheme colorScheme) {
    final theme = Theme.of(context);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: colorScheme.outlineVariant.withOpacity(0.3)),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: onDownload,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            child: Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: typeInfo.color.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Icon(typeInfo.icon, color: typeInfo.color, size: 18),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        attachment.fileName,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          fontWeight: FontWeight.w500,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        attachment.sizeLabel,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                if (attachment.isAesGcmProtected)
                  Padding(
                    padding: const EdgeInsets.only(right: 4),
                    child: Icon(
                      Icons.lock_outline,
                      size: 14,
                      color: Colors.green.shade600,
                    ),
                  ),
                Icon(
                  Icons.download_outlined,
                  color: colorScheme.onSurfaceVariant,
                  size: 20,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTypeIcon(_TypeInfo typeInfo, ColorScheme colorScheme) {
    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            typeInfo.color.withOpacity(0.2),
            typeInfo.color.withOpacity(0.1),
          ],
        ),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: typeInfo.color.withOpacity(0.3),
        ),
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          Icon(typeInfo.icon, color: typeInfo.color, size: 26),
          // Extension badge
          Positioned(
            bottom: 2,
            right: 2,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 1),
              decoration: BoxDecoration(
                color: typeInfo.color,
                borderRadius: BorderRadius.circular(3),
              ),
              child: Text(
                attachment.extension.toUpperCase(),
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 7,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoChip(BuildContext context, String label, IconData icon) {
    final theme = Theme.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 12, color: theme.colorScheme.onSurfaceVariant),
        const SizedBox(width: 3),
        Text(
          label,
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }

  Widget _buildSecurityBadge(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.green.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: Colors.green.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.shield_outlined, size: 10, color: Colors.green.shade700),
          const SizedBox(width: 3),
          Text(
            'E2E',
            style: TextStyle(
              fontSize: 9,
              fontWeight: FontWeight.bold,
              color: Colors.green.shade700,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActions(BuildContext context, ColorScheme colorScheme) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (attachment.canPreview && onPreview != null)
          IconButton(
            icon: const Icon(Icons.visibility_outlined),
            onPressed: onPreview,
            tooltip: 'Preview',
            iconSize: 20,
            style: IconButton.styleFrom(
              foregroundColor: colorScheme.primary,
            ),
          ),
        IconButton(
          icon: const Icon(Icons.download_rounded),
          onPressed: onDownload,
          tooltip: 'Download',
          iconSize: 22,
          style: IconButton.styleFrom(
            backgroundColor: colorScheme.primaryContainer,
            foregroundColor: colorScheme.onPrimaryContainer,
          ),
        ),
      ],
    );
  }

  Widget _buildPreviewPlaceholder(_TypeInfo typeInfo, ColorScheme colorScheme) {
    return Container(
      height: 120,
      color: typeInfo.color.withOpacity(0.1),
      child: Center(
        child: Icon(typeInfo.icon, size: 48, color: typeInfo.color.withOpacity(0.5)),
      ),
    );
  }

  Widget _buildMediaPreviewPlaceholder(BuildContext context, _TypeInfo typeInfo, ColorScheme colorScheme) {
    return ClipRRect(
      borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
      child: Container(
        height: 100,
        width: double.infinity,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              typeInfo.color.withOpacity(0.15),
              typeInfo.color.withOpacity(0.05),
            ],
          ),
        ),
        child: Stack(
          alignment: Alignment.center,
          children: [
            // Background pattern
            Positioned.fill(
              child: CustomPaint(
                painter: _GridPatternPainter(color: typeInfo.color.withOpacity(0.1)),
              ),
            ),
            // Icon and label
            Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: colorScheme.surface.withOpacity(0.9),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: typeInfo.color.withOpacity(0.2),
                        blurRadius: 20,
                      ),
                    ],
                  ),
                  child: Icon(typeInfo.icon, size: 32, color: typeInfo.color),
                ),
                const SizedBox(height: 8),
                Text(
                  attachment.type == AttachmentType.video
                      ? 'Video Preview'
                      : attachment.type == AttachmentType.audio
                          ? 'Audio File'
                          : 'Media File',
                  style: TextStyle(
                    fontSize: 12,
                    color: typeInfo.color,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  _TypeInfo _getTypeInfo(AttachmentType type) {
    switch (type) {
      case AttachmentType.image:
        return _TypeInfo(Icons.image_rounded, Colors.blue.shade600);
      case AttachmentType.video:
        return _TypeInfo(Icons.videocam_rounded, Colors.pink.shade600);
      case AttachmentType.audio:
        return _TypeInfo(Icons.audiotrack_rounded, Colors.purple.shade600);
      case AttachmentType.pdf:
        return _TypeInfo(Icons.picture_as_pdf_rounded, Colors.red.shade600);
      case AttachmentType.document:
        return _TypeInfo(Icons.article_rounded, Colors.blue.shade800);
      case AttachmentType.spreadsheet:
        return _TypeInfo(Icons.grid_on_rounded, Colors.green.shade700);
      case AttachmentType.presentation:
        return _TypeInfo(Icons.slideshow_rounded, Colors.orange.shade700);
      case AttachmentType.archive:
        return _TypeInfo(Icons.folder_zip_rounded, Colors.amber.shade700);
      case AttachmentType.code:
        return _TypeInfo(Icons.code_rounded, Colors.cyan.shade700);
      case AttachmentType.executable:
        return _TypeInfo(Icons.terminal_rounded, Colors.grey.shade700);
      case AttachmentType.other:
        return _TypeInfo(Icons.insert_drive_file_rounded, Colors.grey.shade600);
    }
  }
}

class _TypeInfo {
  final IconData icon;
  final Color color;
  const _TypeInfo(this.icon, this.color);
}

/// Grid pattern painter for preview placeholders
class _GridPatternPainter extends CustomPainter {
  final Color color;
  _GridPatternPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1;

    const spacing = 20.0;
    for (var x = 0.0; x < size.width; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (var y = 0.0; y < size.height; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// Attachments grid for compose screen
class AttachmentsGrid extends StatelessWidget {
  const AttachmentsGrid({
    super.key,
    required this.attachments,
    this.onRemove,
    this.isUploading = false,
  });

  final List<AttachmentPreview> attachments;
  final void Function(int index)? onRemove;
  final bool isUploading;

  @override
  Widget build(BuildContext context) {
    if (attachments.isEmpty) return const SizedBox.shrink();

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: List.generate(
        attachments.length,
        (index) => AttachmentChip(
          attachment: attachments[index],
          onRemove: onRemove != null ? () => onRemove!(index) : null,
          isUploading: isUploading,
        ),
      ),
    );
  }
}

/// Simple attachment data for compose screen
class AttachmentPreview {
  final String fileName;
  final int sizeBytes;
  final Uint8List? thumbnail;

  AttachmentPreview({
    required this.fileName,
    required this.sizeBytes,
    this.thumbnail,
  });

  String get sizeLabel {
    if (sizeBytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    var size = sizeBytes.toDouble();
    var unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    return '${size.toStringAsFixed(1)} ${units[unitIndex]}';
  }
}

/// Chip-style attachment for compose screen
class AttachmentChip extends StatelessWidget {
  const AttachmentChip({
    super.key,
    required this.attachment,
    this.onRemove,
    this.isUploading = false,
  });

  final AttachmentPreview attachment;
  final VoidCallback? onRemove;
  final bool isUploading;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final ext = attachment.fileName.split('.').last.toLowerCase();
    final typeInfo = _getTypeInfoForExt(ext);

    return Container(
      constraints: const BoxConstraints(maxWidth: 200),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Material(
        color: Colors.transparent,
        child: Padding(
          padding: const EdgeInsets.only(left: 4, right: 4, top: 4, bottom: 4),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  color: typeInfo.color.withOpacity(0.2),
                  shape: BoxShape.circle,
                ),
                child: Icon(typeInfo.icon, size: 16, color: typeInfo.color),
              ),
              const SizedBox(width: 8),
              Flexible(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      attachment.fileName,
                      style: theme.textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w500,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    Text(
                      attachment.sizeLabel,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                        fontSize: 10,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 4),
              if (isUploading)
                const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else if (onRemove != null)
                InkWell(
                  onTap: onRemove,
                  borderRadius: BorderRadius.circular(12),
                  child: Container(
                    width: 24,
                    height: 24,
                    decoration: BoxDecoration(
                      color: theme.colorScheme.errorContainer.withOpacity(0.5),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      Icons.close,
                      size: 14,
                      color: theme.colorScheme.error,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  _TypeInfo _getTypeInfoForExt(String ext) {
    switch (ext) {
      case 'jpg':
      case 'jpeg':
      case 'png':
      case 'gif':
      case 'bmp':
      case 'webp':
      case 'svg':
      case 'heic':
        return _TypeInfo(Icons.image_rounded, Colors.blue.shade600);
      case 'mp4':
      case 'avi':
      case 'mov':
      case 'mkv':
      case 'wmv':
      case 'webm':
        return _TypeInfo(Icons.videocam_rounded, Colors.pink.shade600);
      case 'mp3':
      case 'wav':
      case 'ogg':
      case 'flac':
      case 'aac':
      case 'm4a':
        return _TypeInfo(Icons.audiotrack_rounded, Colors.purple.shade600);
      case 'pdf':
        return _TypeInfo(Icons.picture_as_pdf_rounded, Colors.red.shade600);
      case 'doc':
      case 'docx':
      case 'odt':
      case 'rtf':
      case 'txt':
        return _TypeInfo(Icons.article_rounded, Colors.blue.shade800);
      case 'xls':
      case 'xlsx':
      case 'ods':
      case 'csv':
        return _TypeInfo(Icons.grid_on_rounded, Colors.green.shade700);
      case 'ppt':
      case 'pptx':
      case 'odp':
        return _TypeInfo(Icons.slideshow_rounded, Colors.orange.shade700);
      case 'zip':
      case 'rar':
      case '7z':
      case 'tar':
      case 'gz':
        return _TypeInfo(Icons.folder_zip_rounded, Colors.amber.shade700);
      case 'js':
      case 'ts':
      case 'py':
      case 'dart':
      case 'java':
      case 'html':
      case 'css':
      case 'json':
        return _TypeInfo(Icons.code_rounded, Colors.cyan.shade700);
      default:
        return _TypeInfo(Icons.insert_drive_file_rounded, Colors.grey.shade600);
    }
  }
}
