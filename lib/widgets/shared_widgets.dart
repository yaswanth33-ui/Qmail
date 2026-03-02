/// Shared Widgets for QMail Outlook-Style UI
/// 
/// Reusable components following Outlook design patterns:
/// - Avatars with initials
/// - Security badges
/// - Email list items
/// - Action buttons
/// - Search bars
/// - Folder items

import 'package:flutter/material.dart';
import '../theme/outlook_theme.dart';
import '../models/email_models.dart';

/// ============================================================================
/// AVATAR WIDGET
/// ============================================================================

class QMailAvatar extends StatelessWidget {
  const QMailAvatar({
    super.key,
    required this.displayName,
    this.imageUrl,
    this.size = QMailSizes.avatarMedium,
    this.backgroundColor,
  });

  final String displayName;
  final String? imageUrl;
  final double size;
  final Color? backgroundColor;

  String get _initials {
    if (displayName.isEmpty) return '?';
    final parts = displayName.trim().split(' ');
    if (parts.length >= 2) {
      return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
    }
    return displayName[0].toUpperCase();
  }

  Color _getColor(BuildContext context) {
    if (backgroundColor != null) return backgroundColor!;
    // Generate consistent color based on name
    final hash = displayName.hashCode;
    final colors = [
      QMailColors.primary,
      QMailColors.securityPqc,
      QMailColors.securityOtp,
      QMailColors.folderSent,
      QMailColors.folderDrafts,
      const Color(0xFF00B7C3),
      const Color(0xFF8764B8),
      const Color(0xFF498205),
    ];
    return colors[hash.abs() % colors.length];
  }

  @override
  Widget build(BuildContext context) {
    if (imageUrl != null && imageUrl!.isNotEmpty) {
      return CircleAvatar(
        radius: size / 2,
        backgroundImage: NetworkImage(imageUrl!),
        backgroundColor: _getColor(context),
        onBackgroundImageError: (_, __) {},
        child: Text(
          _initials,
          style: TextStyle(
            fontSize: size * 0.4,
            fontWeight: FontWeight.w600,
            color: Colors.white,
          ),
        ),
      );
    }

    return CircleAvatar(
      radius: size / 2,
      backgroundColor: _getColor(context),
      child: Text(
        _initials,
        style: TextStyle(
          fontSize: size * 0.4,
          fontWeight: FontWeight.w600,
          color: Colors.white,
        ),
      ),
    );
  }
}

/// ============================================================================
/// SECURITY BADGE WIDGET
/// ============================================================================

class SecurityBadge extends StatelessWidget {
  const SecurityBadge({
    super.key,
    required this.level,
    this.showLabel = true,
    this.size = 14,
  });

  final SecurityLevel level;
  final bool showLabel;
  final double size;

  IconData get _icon {
    switch (level) {
      case SecurityLevel.otp:
        return Icons.enhanced_encryption;
      case SecurityLevel.aesGcm:
        return Icons.lock;
      case SecurityLevel.pqc:
        return Icons.shield;
      case SecurityLevel.classical:
        return Icons.lock_open;
    }
  }

  Color get _color {
    switch (level) {
      case SecurityLevel.otp:
        return QMailColors.securityOtp;
      case SecurityLevel.aesGcm:
        return QMailColors.securityAes;
      case SecurityLevel.pqc:
        return QMailColors.securityPqc;
      case SecurityLevel.classical:
        return QMailColors.securityClassical;
    }
  }

  String get _label {
    switch (level) {
      case SecurityLevel.otp:
        return 'One-Time Pad';
      case SecurityLevel.aesGcm:
        return 'AES-GCM';
      case SecurityLevel.pqc:
        return 'Quantum Safe';
      case SecurityLevel.classical:
        return 'Standard';
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!showLabel) {
      return Tooltip(
        message: _label,
        child: Icon(_icon, size: size, color: _color),
      );
    }

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: QMailSizes.space8,
        vertical: QMailSizes.space4,
      ),
      decoration: BoxDecoration(
        color: _color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(QMailSizes.radiusCircular),
        border: Border.all(color: _color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(_icon, size: size, color: _color),
          const SizedBox(width: QMailSizes.space4),
          Text(
            _label,
            style: QMailTextStyles.labelSmall(_color),
          ),
        ],
      ),
    );
  }
}

/// ============================================================================
/// FOLDER ITEM WIDGET
/// ============================================================================

class FolderItem extends StatelessWidget {
  const FolderItem({
    super.key,
    required this.icon,
    required this.label,
    this.count,
    this.isSelected = false,
    this.color,
    this.onTap,
  });

  final IconData icon;
  final String label;
  final int? count;
  final bool isSelected;
  final Color? color;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final effectiveColor = color ?? (isSelected ? QMailColors.primary : context.textSecondary);

    return Material(
      color: isSelected 
        ? QMailColors.primary.withOpacity(0.1) 
        : Colors.transparent,
      borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: QMailSizes.space12,
            vertical: QMailSizes.space8,
          ),
          child: Row(
            children: [
              Icon(
                icon,
                size: QMailSizes.iconMedium,
                color: effectiveColor,
              ),
              const SizedBox(width: QMailSizes.space12),
              Expanded(
                child: Text(
                  label,
                  style: QMailTextStyles.bodyMedium(
                    isSelected ? QMailColors.primary : context.textPrimary,
                  ).copyWith(
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                  ),
                ),
              ),
              if (count != null && count! > 0)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: QMailSizes.space8,
                    vertical: QMailSizes.space2,
                  ),
                  decoration: BoxDecoration(
                    color: isSelected 
                      ? QMailColors.primary 
                      : context.dividerColor,
                    borderRadius: BorderRadius.circular(QMailSizes.radiusCircular),
                  ),
                  child: Text(
                    count.toString(),
                    style: QMailTextStyles.labelSmall(
                      isSelected ? Colors.white : context.textSecondary,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// ============================================================================
/// EMAIL LIST ITEM WIDGET
/// ============================================================================

class EmailListItem extends StatelessWidget {
  const EmailListItem({
    super.key,
    required this.email,
    this.isSelected = false,
    this.isCompact = false,
    this.onTap,
    this.onLongPress,
    this.onFlag,
    this.onDelete,
  });

  final EmailEnvelope email;
  final bool isSelected;
  final bool isCompact;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;
  final VoidCallback? onFlag;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: isSelected 
        ? QMailColors.primary.withOpacity(0.08) 
        : Colors.transparent,
      child: InkWell(
        onTap: onTap,
        onLongPress: onLongPress,
        child: Container(
          padding: EdgeInsets.symmetric(
            horizontal: QMailSizes.space16,
            vertical: isCompact ? QMailSizes.space8 : QMailSizes.space12,
          ),
          decoration: BoxDecoration(
            border: Border(
              left: isSelected 
                ? const BorderSide(color: QMailColors.primary, width: 3)
                : BorderSide.none,
              bottom: BorderSide(color: context.dividerColor, width: 0.5),
            ),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Unread indicator & Avatar
              Stack(
                children: [
                  QMailAvatar(
                    displayName: email.from.displayName,
                    size: isCompact ? QMailSizes.avatarSmall : QMailSizes.avatarMedium,
                  ),
                  if (!email.isRead)
                    Positioned(
                      right: 0,
                      top: 0,
                      child: Container(
                        width: 10,
                        height: 10,
                        decoration: BoxDecoration(
                          color: QMailColors.unread,
                          shape: BoxShape.circle,
                          border: Border.all(color: context.surfaceColor, width: 2),
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(width: QMailSizes.space12),
              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // From & Time row
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            email.from.displayName,
                            style: QMailTextStyles.titleMedium(context.textPrimary).copyWith(
                              fontWeight: email.isRead ? FontWeight.w400 : FontWeight.w600,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: QMailSizes.space8),
                        Text(
                          _formatTime(email.sentAt),
                          style: QMailTextStyles.caption(
                            email.isRead ? context.textSecondary : QMailColors.primary,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: QMailSizes.space2),
                    // Subject
                    Row(
                      children: [
                        if (email.hasAttachments) ...[
                          Icon(
                            Icons.attach_file,
                            size: 14,
                            color: context.textSecondary,
                          ),
                          const SizedBox(width: QMailSizes.space4),
                        ],
                        Expanded(
                          child: Text(
                            email.subject,
                            style: QMailTextStyles.bodyMedium(context.textPrimary).copyWith(
                              fontWeight: email.isRead ? FontWeight.w400 : FontWeight.w500,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                    if (!isCompact) ...[
                      const SizedBox(height: QMailSizes.space4),
                      // Preview
                      Row(
                        children: [
                          SecurityBadge(
                            level: email.securityLevel,
                            showLabel: false,
                            size: 12,
                          ),
                          const SizedBox(width: QMailSizes.space8),
                          Expanded(
                            child: Text(
                              email.preview,
                              style: QMailTextStyles.bodySmall(context.textSecondary),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
              // Actions
              if (onFlag != null || onDelete != null)
                Column(
                  children: [
                    if (onFlag != null)
                      IconButton(
                        icon: Icon(
                          email.signatureValid ? Icons.flag : Icons.flag_outlined,
                          size: QMailSizes.iconSmall,
                          color: email.signatureValid ? QMailColors.flagged : context.textTertiary,
                        ),
                        onPressed: onFlag,
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                      ),
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatTime(DateTime time) {
    final now = DateTime.now();
    final diff = now.difference(time);

    if (diff.inDays == 0) {
      return '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';
    } else if (diff.inDays == 1) {
      return 'Yesterday';
    } else if (diff.inDays < 7) {
      const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      return days[time.weekday - 1];
    } else {
      return '${time.day}/${time.month}';
    }
  }
}

extension on BuildContext {
  Color get textTertiary => isDarkMode 
    ? QMailColors.darkTextTertiary 
    : QMailColors.lightTextTertiary;
}

/// ============================================================================
/// SEARCH BAR WIDGET
/// ============================================================================

class QMailSearchBar extends StatelessWidget {
  const QMailSearchBar({
    super.key,
    this.controller,
    this.onChanged,
    this.onSubmitted,
    this.onClear,
    this.hintText = 'Search mail',
    this.autofocus = false,
    this.showFilterButton = true,
    this.onFilterTap,
  });

  final TextEditingController? controller;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final VoidCallback? onClear;
  final String hintText;
  final bool autofocus;
  final bool showFilterButton;
  final VoidCallback? onFilterTap;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 40,
      decoration: BoxDecoration(
        color: context.isDarkMode 
          ? QMailColors.darkSurfaceVariant 
          : QMailColors.lightSurfaceVariant,
        borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
      ),
      child: Row(
        children: [
          const SizedBox(width: QMailSizes.space12),
          Icon(
            Icons.search,
            size: QMailSizes.iconMedium,
            color: context.textSecondary,
          ),
          const SizedBox(width: QMailSizes.space8),
          Expanded(
            child: TextField(
              controller: controller,
              autofocus: autofocus,
              onChanged: onChanged,
              onSubmitted: onSubmitted,
              style: QMailTextStyles.bodyMedium(context.textPrimary),
              decoration: InputDecoration(
                hintText: hintText,
                hintStyle: QMailTextStyles.bodyMedium(context.textSecondary),
                border: InputBorder.none,
                contentPadding: EdgeInsets.zero,
                isDense: true,
              ),
            ),
          ),
          if (controller?.text.isNotEmpty ?? false)
            IconButton(
              icon: Icon(
                Icons.close,
                size: QMailSizes.iconSmall,
                color: context.textSecondary,
              ),
              onPressed: () {
                controller?.clear();
                onClear?.call();
              },
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
            ),
          if (showFilterButton) ...[
            Container(
              height: 24,
              width: 1,
              color: context.dividerColor,
            ),
            IconButton(
              icon: Icon(
                Icons.tune,
                size: QMailSizes.iconMedium,
                color: context.textSecondary,
              ),
              onPressed: onFilterTap,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 40, minHeight: 40),
            ),
          ] else
            const SizedBox(width: QMailSizes.space8),
        ],
      ),
    );
  }
}

/// ============================================================================
/// ACTION TOOLBAR BUTTON
/// ============================================================================

class ActionToolbarButton extends StatelessWidget {
  const ActionToolbarButton({
    super.key,
    required this.icon,
    required this.label,
    this.onPressed,
    this.isDestructive = false,
    this.showLabel = true,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onPressed;
  final bool isDestructive;
  final bool showLabel;

  @override
  Widget build(BuildContext context) {
    final color = isDestructive 
      ? QMailColors.securityError 
      : context.textSecondary;

    if (!showLabel) {
      return Tooltip(
        message: label,
        child: IconButton(
          icon: Icon(icon, size: QMailSizes.iconMedium, color: color),
          onPressed: onPressed,
        ),
      );
    }

    return TextButton.icon(
      onPressed: onPressed,
      icon: Icon(icon, size: QMailSizes.iconSmall, color: color),
      label: Text(
        label,
        style: QMailTextStyles.labelMedium(color),
      ),
      style: TextButton.styleFrom(
        padding: const EdgeInsets.symmetric(
          horizontal: QMailSizes.space12,
          vertical: QMailSizes.space8,
        ),
      ),
    );
  }
}

/// ============================================================================
/// EMPTY STATE WIDGET
/// ============================================================================

class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    this.action,
    this.actionLabel,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final VoidCallback? action;
  final String? actionLabel;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(QMailSizes.space32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: context.dividerColor,
                shape: BoxShape.circle,
              ),
              child: Icon(
                icon,
                size: QMailSizes.iconXLarge,
                color: context.textSecondary,
              ),
            ),
            const SizedBox(height: QMailSizes.space24),
            Text(
              title,
              style: QMailTextStyles.headlineMedium(context.textPrimary),
              textAlign: TextAlign.center,
            ),
            if (subtitle != null) ...[
              const SizedBox(height: QMailSizes.space8),
              Text(
                subtitle!,
                style: QMailTextStyles.bodyMedium(context.textSecondary),
                textAlign: TextAlign.center,
              ),
            ],
            if (action != null && actionLabel != null) ...[
              const SizedBox(height: QMailSizes.space24),
              FilledButton.icon(
                onPressed: action,
                icon: const Icon(Icons.add),
                label: Text(actionLabel!),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// ============================================================================
/// LOADING SKELETON FOR EMAIL LIST
/// ============================================================================

class EmailListSkeleton extends StatelessWidget {
  const EmailListSkeleton({
    super.key,
    this.itemCount = 5,
  });

  final int itemCount;

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      itemCount: itemCount,
      itemBuilder: (context, index) => const _SkeletonEmailItem(),
    );
  }
}

class _SkeletonEmailItem extends StatelessWidget {
  const _SkeletonEmailItem();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: QMailSizes.space16,
        vertical: QMailSizes.space12,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Avatar skeleton
          Container(
            width: QMailSizes.avatarMedium,
            height: QMailSizes.avatarMedium,
            decoration: BoxDecoration(
              color: context.dividerColor,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: QMailSizes.space12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 120,
                      height: 14,
                      decoration: BoxDecoration(
                        color: context.dividerColor,
                        borderRadius: BorderRadius.circular(QMailSizes.radiusSmall),
                      ),
                    ),
                    const Spacer(),
                    Container(
                      width: 40,
                      height: 12,
                      decoration: BoxDecoration(
                        color: context.dividerColor,
                        borderRadius: BorderRadius.circular(QMailSizes.radiusSmall),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: QMailSizes.space8),
                Container(
                  width: double.infinity,
                  height: 14,
                  decoration: BoxDecoration(
                    color: context.dividerColor,
                    borderRadius: BorderRadius.circular(QMailSizes.radiusSmall),
                  ),
                ),
                const SizedBox(height: QMailSizes.space8),
                Container(
                  width: 200,
                  height: 12,
                  decoration: BoxDecoration(
                    color: context.dividerColor,
                    borderRadius: BorderRadius.circular(QMailSizes.radiusSmall),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// ============================================================================
/// CONFIRMATION DIALOG
/// ============================================================================

Future<bool?> showQMailConfirmDialog({
  required BuildContext context,
  required String title,
  required String message,
  String confirmLabel = 'Confirm',
  String cancelLabel = 'Cancel',
  bool isDestructive = false,
}) {
  return showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: Text(cancelLabel),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(true),
          style: isDestructive
            ? FilledButton.styleFrom(
                backgroundColor: QMailColors.securityError,
              )
            : null,
          child: Text(confirmLabel),
        ),
      ],
    ),
  );
}
