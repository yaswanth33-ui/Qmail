/// Outlook-Style Theme for QMail
/// 
/// This file defines the complete Outlook-inspired design system including:
/// - Color palette (light/dark modes)
/// - Typography scale
/// - Component styles
/// - Spacing and sizing constants
/// - Animation durations

import 'package:flutter/material.dart';

/// ============================================================================
/// COLOR PALETTE - Outlook-Inspired
/// ============================================================================

class QMailColors {
  QMailColors._();

  // Primary brand colors (Outlook Blue)
  static const Color primary = Color(0xFF0078D4);
  static const Color primaryLight = Color(0xFF2B88D8);
  static const Color primaryDark = Color(0xFF004E8C);

  // Accent colors
  static const Color accent = Color(0xFF0078D4);
  static const Color accentLight = Color(0xFF5EB0EF);

  // Security indicator colors
  static const Color securityPqc = Color(0xFF107C10);      // Green - Quantum secure
  static const Color securityAes = Color(0xFF0078D4);      // Blue - AES encrypted
  static const Color securityOtp = Color(0xFF5C2D91);      // Purple - One-Time Pad
  static const Color securityClassical = Color(0xFFF7630C); // Orange - Classical
  static const Color securityWarning = Color(0xFFFFB900);   // Yellow - Warning
  static const Color securityError = Color(0xFFD13438);     // Red - Error

  // Folder colors
  static const Color folderInbox = Color(0xFF0078D4);
  static const Color folderSent = Color(0xFF107C10);
  static const Color folderDrafts = Color(0xFFF7630C);
  static const Color folderTrash = Color(0xFFD13438);
  static const Color folderArchive = Color(0xFF5C2D91);
  static const Color folderSpam = Color(0xFFFFB900);
  static const Color folderFocused = Color(0xFF0078D4);
  static const Color folderOther = Color(0xFF6B6B6B);

  // Light theme colors
  static const Color lightBackground = Color(0xFFF3F3F3);
  static const Color lightSurface = Color(0xFFFFFFFF);
  static const Color lightSurfaceVariant = Color(0xFFF5F5F5);
  static const Color lightNavigation = Color(0xFFE6E6E6);
  static const Color lightDivider = Color(0xFFE1E1E1);
  static const Color lightTextPrimary = Color(0xFF1A1A1A);
  static const Color lightTextSecondary = Color(0xFF616161);
  static const Color lightTextTertiary = Color(0xFF8A8A8A);

  // Dark theme colors
  static const Color darkBackground = Color(0xFF1F1F1F);
  static const Color darkSurface = Color(0xFF2D2D2D);
  static const Color darkSurfaceVariant = Color(0xFF383838);
  static const Color darkNavigation = Color(0xFF252525);
  static const Color darkDivider = Color(0xFF404040);
  static const Color darkTextPrimary = Color(0xFFFFFFFF);
  static const Color darkTextSecondary = Color(0xFFB0B0B0);
  static const Color darkTextTertiary = Color(0xFF808080);

  // Status colors
  static const Color unread = Color(0xFF0078D4);
  static const Color flagged = Color(0xFFD13438);
  static const Color pinned = Color(0xFF5C2D91);
  static const Color important = Color(0xFFFFB900);
}

/// ============================================================================
/// SPACING & SIZING CONSTANTS
/// ============================================================================

class QMailSizes {
  QMailSizes._();

  // Spacing scale
  static const double space2 = 2.0;
  static const double space4 = 4.0;
  static const double space8 = 8.0;
  static const double space12 = 12.0;
  static const double space16 = 16.0;
  static const double space20 = 20.0;
  static const double space24 = 24.0;
  static const double space32 = 32.0;
  static const double space40 = 40.0;
  static const double space48 = 48.0;
  static const double space56 = 56.0;
  static const double space64 = 64.0;

  // Navigation dimensions
  static const double navRailWidthCollapsed = 56.0;
  static const double navRailWidthExpanded = 220.0;
  static const double navPaneWidth = 280.0;
  static const double folderPaneWidth = 72.0;

  // Email list dimensions
  static const double emailListWidth = 360.0;
  static const double emailListItemHeight = 80.0;
  static const double emailListItemCompactHeight = 64.0;

  // Reading pane dimensions
  static const double readingPaneMinWidth = 400.0;

  // Avatar sizes
  static const double avatarSmall = 28.0;
  static const double avatarMedium = 36.0;
  static const double avatarLarge = 48.0;
  static const double avatarXLarge = 72.0;

  // Icon sizes
  static const double iconSmall = 16.0;
  static const double iconMedium = 20.0;
  static const double iconLarge = 24.0;
  static const double iconXLarge = 32.0;

  // Border radius
  static const double radiusSmall = 4.0;
  static const double radiusMedium = 8.0;
  static const double radiusLarge = 12.0;
  static const double radiusXLarge = 16.0;
  static const double radiusCircular = 999.0;

  // Breakpoints for responsive layout
  static const double breakpointMobile = 600.0;
  static const double breakpointTablet = 900.0;
  static const double breakpointDesktop = 1200.0;
  static const double breakpointWide = 1600.0;
}

/// ============================================================================
/// ANIMATION DURATIONS
/// ============================================================================

class QMailAnimations {
  QMailAnimations._();

  static const Duration fast = Duration(milliseconds: 100);
  static const Duration normal = Duration(milliseconds: 200);
  static const Duration slow = Duration(milliseconds: 300);
  static const Duration slower = Duration(milliseconds: 400);

  static const Curve defaultCurve = Curves.easeInOut;
  static const Curve enterCurve = Curves.easeOut;
  static const Curve exitCurve = Curves.easeIn;
}

/// ============================================================================
/// TEXT STYLES
/// ============================================================================

class QMailTextStyles {
  QMailTextStyles._();

  static const String fontFamily = 'Segoe UI';

  // Display styles
  static TextStyle displayLarge(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 32,
    fontWeight: FontWeight.w600,
    color: color,
    letterSpacing: -0.5,
  );

  static TextStyle displayMedium(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 28,
    fontWeight: FontWeight.w600,
    color: color,
    letterSpacing: -0.25,
  );

  // Heading styles
  static TextStyle headlineLarge(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 24,
    fontWeight: FontWeight.w600,
    color: color,
  );

  static TextStyle headlineMedium(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 20,
    fontWeight: FontWeight.w600,
    color: color,
  );

  static TextStyle headlineSmall(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 18,
    fontWeight: FontWeight.w600,
    color: color,
  );

  // Title styles
  static TextStyle titleLarge(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 16,
    fontWeight: FontWeight.w600,
    color: color,
  );

  static TextStyle titleMedium(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 14,
    fontWeight: FontWeight.w600,
    color: color,
  );

  static TextStyle titleSmall(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 12,
    fontWeight: FontWeight.w600,
    color: color,
  );

  // Body styles
  static TextStyle bodyLarge(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 16,
    fontWeight: FontWeight.w400,
    color: color,
  );

  static TextStyle bodyMedium(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 14,
    fontWeight: FontWeight.w400,
    color: color,
  );

  static TextStyle bodySmall(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 12,
    fontWeight: FontWeight.w400,
    color: color,
  );

  // Label styles
  static TextStyle labelLarge(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 14,
    fontWeight: FontWeight.w500,
    color: color,
  );

  static TextStyle labelMedium(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 12,
    fontWeight: FontWeight.w500,
    color: color,
  );

  static TextStyle labelSmall(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 10,
    fontWeight: FontWeight.w500,
    color: color,
    letterSpacing: 0.5,
  );

  // Caption style
  static TextStyle caption(Color color) => TextStyle(
    fontFamily: fontFamily,
    fontSize: 11,
    fontWeight: FontWeight.w400,
    color: color,
  );
}

/// ============================================================================
/// THEME DATA BUILDERS
/// ============================================================================

class QMailTheme {
  QMailTheme._();

  /// Creates the light theme for QMail
  static ThemeData light() {
    final colorScheme = ColorScheme.light(
      primary: QMailColors.primary,
      onPrimary: Colors.white,
      primaryContainer: QMailColors.primaryLight.withOpacity(0.15),
      onPrimaryContainer: QMailColors.primaryDark,
      secondary: QMailColors.accent,
      onSecondary: Colors.white,
      secondaryContainer: QMailColors.accentLight.withOpacity(0.15),
      onSecondaryContainer: QMailColors.primaryDark,
      surface: QMailColors.lightSurface,
      onSurface: QMailColors.lightTextPrimary,
      surfaceContainerHighest: QMailColors.lightSurfaceVariant,
      error: QMailColors.securityError,
      onError: Colors.white,
      outline: QMailColors.lightDivider,
      outlineVariant: QMailColors.lightDivider.withOpacity(0.5),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: QMailColors.lightBackground,
      
      // AppBar theme
      appBarTheme: AppBarTheme(
        backgroundColor: QMailColors.lightSurface,
        foregroundColor: QMailColors.lightTextPrimary,
        elevation: 0,
        scrolledUnderElevation: 1,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: QMailTextStyles.headlineSmall(QMailColors.lightTextPrimary),
      ),

      // Card theme
      cardTheme: CardTheme(
        color: QMailColors.lightSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          side: BorderSide(color: QMailColors.lightDivider),
        ),
      ),

      // Divider theme
      dividerTheme: const DividerThemeData(
        color: QMailColors.lightDivider,
        thickness: 1,
        space: 1,
      ),

      // Dialog theme
      dialogTheme: DialogTheme(
        backgroundColor: QMailColors.lightSurface,
        elevation: 8,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusLarge),
        ),
      ),

      // Input decoration theme
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: QMailColors.lightSurfaceVariant,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          borderSide: const BorderSide(color: QMailColors.primary, width: 2),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: QMailSizes.space16,
          vertical: QMailSizes.space12,
        ),
        hintStyle: QMailTextStyles.bodyMedium(QMailColors.lightTextTertiary),
      ),

      // Elevated button theme
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: QMailColors.primary,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(
            horizontal: QMailSizes.space24,
            vertical: QMailSizes.space12,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          ),
        ),
      ),

      // Text button theme
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: QMailColors.primary,
          padding: const EdgeInsets.symmetric(
            horizontal: QMailSizes.space16,
            vertical: QMailSizes.space8,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          ),
        ),
      ),

      // Filled button theme (primary action)
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: QMailColors.primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(
            horizontal: QMailSizes.space24,
            vertical: QMailSizes.space12,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          ),
        ),
      ),

      // Outlined button theme
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: QMailColors.primary,
          side: const BorderSide(color: QMailColors.primary),
          padding: const EdgeInsets.symmetric(
            horizontal: QMailSizes.space24,
            vertical: QMailSizes.space12,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          ),
        ),
      ),

      // Icon button theme
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          foregroundColor: QMailColors.lightTextSecondary,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          ),
        ),
      ),

      // Floating action button theme
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: QMailColors.primary,
        foregroundColor: Colors.white,
        elevation: 2,
        shape: CircleBorder(),
      ),

      // List tile theme
      listTileTheme: ListTileThemeData(
        contentPadding: const EdgeInsets.symmetric(
          horizontal: QMailSizes.space16,
          vertical: QMailSizes.space4,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
        ),
        selectedTileColor: QMailColors.primary.withOpacity(0.1),
        selectedColor: QMailColors.primary,
      ),

      // Chip theme
      chipTheme: ChipThemeData(
        backgroundColor: QMailColors.lightSurfaceVariant,
        labelStyle: QMailTextStyles.labelMedium(QMailColors.lightTextPrimary),
        side: BorderSide.none,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusCircular),
        ),
      ),

      // Tab bar theme
      tabBarTheme: TabBarTheme(
        labelColor: QMailColors.primary,
        unselectedLabelColor: QMailColors.lightTextSecondary,
        indicatorColor: QMailColors.primary,
        labelStyle: QMailTextStyles.labelLarge(QMailColors.primary),
        unselectedLabelStyle: QMailTextStyles.labelLarge(QMailColors.lightTextSecondary),
      ),

      // Navigation rail theme
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: QMailColors.lightNavigation,
        selectedIconTheme: const IconThemeData(color: QMailColors.primary),
        unselectedIconTheme: IconThemeData(color: QMailColors.lightTextSecondary),
        selectedLabelTextStyle: QMailTextStyles.labelMedium(QMailColors.primary),
        unselectedLabelTextStyle: QMailTextStyles.labelMedium(QMailColors.lightTextSecondary),
      ),

      // Tooltip theme
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: QMailColors.lightTextPrimary,
          borderRadius: BorderRadius.circular(QMailSizes.radiusSmall),
        ),
        textStyle: QMailTextStyles.caption(Colors.white),
      ),

      // Snackbar theme
      snackBarTheme: SnackBarThemeData(
        backgroundColor: QMailColors.lightTextPrimary,
        contentTextStyle: QMailTextStyles.bodyMedium(Colors.white),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
        ),
        behavior: SnackBarBehavior.floating,
      ),

      // Bottom sheet theme
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: QMailColors.lightSurface,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(QMailSizes.radiusLarge),
          ),
        ),
      ),

      // Popup menu theme
      popupMenuTheme: PopupMenuThemeData(
        color: QMailColors.lightSurface,
        elevation: 4,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
        ),
      ),

      // Drawer theme
      drawerTheme: const DrawerThemeData(
        backgroundColor: QMailColors.lightSurface,
        elevation: 0,
      ),

      // Checkbox theme
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return QMailColors.primary;
          }
          return Colors.transparent;
        }),
        checkColor: WidgetStateProperty.all(Colors.white),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusSmall),
        ),
      ),

      // Switch theme
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return Colors.white;
          }
          return QMailColors.lightTextTertiary;
        }),
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return QMailColors.primary;
          }
          return QMailColors.lightDivider;
        }),
      ),

      // Progress indicator theme
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: QMailColors.primary,
        linearTrackColor: QMailColors.lightDivider,
      ),
    );
  }

  /// Creates the dark theme for QMail
  static ThemeData dark() {
    final colorScheme = ColorScheme.dark(
      primary: QMailColors.primary,
      onPrimary: Colors.white,
      primaryContainer: QMailColors.primaryDark,
      onPrimaryContainer: QMailColors.primaryLight,
      secondary: QMailColors.accent,
      onSecondary: Colors.white,
      secondaryContainer: QMailColors.primaryDark,
      onSecondaryContainer: QMailColors.accentLight,
      surface: QMailColors.darkSurface,
      onSurface: QMailColors.darkTextPrimary,
      surfaceContainerHighest: QMailColors.darkSurfaceVariant,
      error: QMailColors.securityError,
      onError: Colors.white,
      outline: QMailColors.darkDivider,
      outlineVariant: QMailColors.darkDivider.withOpacity(0.5),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: QMailColors.darkBackground,
      
      // AppBar theme
      appBarTheme: AppBarTheme(
        backgroundColor: QMailColors.darkSurface,
        foregroundColor: QMailColors.darkTextPrimary,
        elevation: 0,
        scrolledUnderElevation: 1,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: QMailTextStyles.headlineSmall(QMailColors.darkTextPrimary),
      ),

      // Card theme
      cardTheme: CardTheme(
        color: QMailColors.darkSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          side: BorderSide(color: QMailColors.darkDivider),
        ),
      ),

      // Divider theme
      dividerTheme: const DividerThemeData(
        color: QMailColors.darkDivider,
        thickness: 1,
        space: 1,
      ),

      // Dialog theme
      dialogTheme: DialogTheme(
        backgroundColor: QMailColors.darkSurface,
        elevation: 8,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusLarge),
        ),
      ),

      // Input decoration theme
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: QMailColors.darkSurfaceVariant,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          borderSide: const BorderSide(color: QMailColors.primary, width: 2),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: QMailSizes.space16,
          vertical: QMailSizes.space12,
        ),
        hintStyle: QMailTextStyles.bodyMedium(QMailColors.darkTextTertiary),
      ),

      // Elevated button theme
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: QMailColors.primary,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(
            horizontal: QMailSizes.space24,
            vertical: QMailSizes.space12,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          ),
        ),
      ),

      // Text button theme
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: QMailColors.primaryLight,
          padding: const EdgeInsets.symmetric(
            horizontal: QMailSizes.space16,
            vertical: QMailSizes.space8,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          ),
        ),
      ),

      // Filled button theme
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: QMailColors.primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(
            horizontal: QMailSizes.space24,
            vertical: QMailSizes.space12,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          ),
        ),
      ),

      // Outlined button theme
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: QMailColors.primaryLight,
          side: const BorderSide(color: QMailColors.primaryLight),
          padding: const EdgeInsets.symmetric(
            horizontal: QMailSizes.space24,
            vertical: QMailSizes.space12,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          ),
        ),
      ),

      // Icon button theme
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          foregroundColor: QMailColors.darkTextSecondary,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
          ),
        ),
      ),

      // Floating action button theme
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: QMailColors.primary,
        foregroundColor: Colors.white,
        elevation: 2,
        shape: CircleBorder(),
      ),

      // List tile theme
      listTileTheme: ListTileThemeData(
        contentPadding: const EdgeInsets.symmetric(
          horizontal: QMailSizes.space16,
          vertical: QMailSizes.space4,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
        ),
        selectedTileColor: QMailColors.primary.withOpacity(0.2),
        selectedColor: QMailColors.primaryLight,
      ),

      // Chip theme
      chipTheme: ChipThemeData(
        backgroundColor: QMailColors.darkSurfaceVariant,
        labelStyle: QMailTextStyles.labelMedium(QMailColors.darkTextPrimary),
        side: BorderSide.none,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusCircular),
        ),
      ),

      // Tab bar theme
      tabBarTheme: TabBarTheme(
        labelColor: QMailColors.primaryLight,
        unselectedLabelColor: QMailColors.darkTextSecondary,
        indicatorColor: QMailColors.primaryLight,
        labelStyle: QMailTextStyles.labelLarge(QMailColors.primaryLight),
        unselectedLabelStyle: QMailTextStyles.labelLarge(QMailColors.darkTextSecondary),
      ),

      // Navigation rail theme
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: QMailColors.darkNavigation,
        selectedIconTheme: const IconThemeData(color: QMailColors.primaryLight),
        unselectedIconTheme: IconThemeData(color: QMailColors.darkTextSecondary),
        selectedLabelTextStyle: QMailTextStyles.labelMedium(QMailColors.primaryLight),
        unselectedLabelTextStyle: QMailTextStyles.labelMedium(QMailColors.darkTextSecondary),
      ),

      // Tooltip theme
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: QMailColors.lightTextPrimary,
          borderRadius: BorderRadius.circular(QMailSizes.radiusSmall),
        ),
        textStyle: QMailTextStyles.caption(QMailColors.darkTextPrimary),
      ),

      // Snackbar theme
      snackBarTheme: SnackBarThemeData(
        backgroundColor: QMailColors.darkSurfaceVariant,
        contentTextStyle: QMailTextStyles.bodyMedium(QMailColors.darkTextPrimary),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
        ),
        behavior: SnackBarBehavior.floating,
      ),

      // Bottom sheet theme
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: QMailColors.darkSurface,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(QMailSizes.radiusLarge),
          ),
        ),
      ),

      // Popup menu theme
      popupMenuTheme: PopupMenuThemeData(
        color: QMailColors.darkSurface,
        elevation: 4,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusMedium),
        ),
      ),

      // Drawer theme
      drawerTheme: const DrawerThemeData(
        backgroundColor: QMailColors.darkSurface,
        elevation: 0,
      ),

      // Checkbox theme
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return QMailColors.primary;
          }
          return Colors.transparent;
        }),
        checkColor: WidgetStateProperty.all(Colors.white),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(QMailSizes.radiusSmall),
        ),
      ),

      // Switch theme
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return Colors.white;
          }
          return QMailColors.darkTextTertiary;
        }),
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return QMailColors.primary;
          }
          return QMailColors.darkDivider;
        }),
      ),

      // Progress indicator theme
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: QMailColors.primary,
        linearTrackColor: QMailColors.darkDivider,
      ),
    );
  }
}

/// ============================================================================
/// EXTENSIONS FOR CONVENIENCE
/// ============================================================================

extension QMailThemeExtension on BuildContext {
  /// Quick access to theme colors
  ColorScheme get colors => Theme.of(this).colorScheme;
  
  /// Quick access to brightness
  bool get isDarkMode => Theme.of(this).brightness == Brightness.dark;
  
  /// Get text primary color based on theme
  Color get textPrimary => isDarkMode 
    ? QMailColors.darkTextPrimary 
    : QMailColors.lightTextPrimary;
  
  /// Get text secondary color based on theme
  Color get textSecondary => isDarkMode 
    ? QMailColors.darkTextSecondary 
    : QMailColors.lightTextSecondary;
  
  /// Get surface color based on theme
  Color get surfaceColor => isDarkMode 
    ? QMailColors.darkSurface 
    : QMailColors.lightSurface;
  
  /// Get background color based on theme
  Color get backgroundColor => isDarkMode 
    ? QMailColors.darkBackground 
    : QMailColors.lightBackground;
  
  /// Get divider color based on theme
  Color get dividerColor => isDarkMode 
    ? QMailColors.darkDivider 
    : QMailColors.lightDivider;
}
