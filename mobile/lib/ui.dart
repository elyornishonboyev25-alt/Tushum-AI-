import 'package:material_ui/material_ui.dart';

import 'core.dart';

abstract final class Palette {
  static const ink = Color(0xFFF9FAFB);
  static const muted = Color(0xFF9CA3AF);
  static const teal = Color(0xFF10B981);
  static const blue = Color(0xFF3B82F6);
  static const background = Color(0xFF0B0F19);
  static const surface = Color(0xFF111827);
  static const line = Color(0xFF1F2937);
  static const soft = Color(0xFF12352D);
  static const blueSoft = Color(0xFF101F39);
  static const warningSoft = Color(0xFF31271A);
  static const green = Color(0xFF10B981);
  static const amber = Color(0xFFF59E0B);
  static const red = Color(0xFFEF4444);
}

ThemeData buildTheme() {
  final colors =
      ColorScheme.fromSeed(
        seedColor: Palette.teal,
        brightness: Brightness.dark,
        surface: Palette.surface,
      ).copyWith(
        primary: Palette.teal,
        onPrimary: const Color(0xFF062A20),
        secondary: Palette.blue,
        onSurface: Palette.ink,
        error: Palette.red,
        outline: Palette.line,
      );
  const numbers = [FontFeature.tabularFigures()];
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: colors,
    scaffoldBackgroundColor: Palette.background,
    fontFamily: 'Inter',
    textTheme: const TextTheme(
      headlineLarge: TextStyle(
        fontSize: 30,
        fontWeight: FontWeight.w700,
        letterSpacing: -1,
        color: Palette.ink,
        fontFeatures: numbers,
      ),
      headlineMedium: TextStyle(
        fontSize: 25,
        fontWeight: FontWeight.w700,
        letterSpacing: -.7,
        color: Palette.ink,
        fontFeatures: numbers,
      ),
      titleLarge: TextStyle(
        fontSize: 20,
        fontWeight: FontWeight.w600,
        color: Palette.ink,
        fontFeatures: numbers,
      ),
      titleMedium: TextStyle(
        fontSize: 15,
        fontWeight: FontWeight.w600,
        color: Palette.ink,
        fontFeatures: numbers,
      ),
      bodyLarge: TextStyle(
        fontSize: 16,
        color: Palette.ink,
        fontFeatures: numbers,
      ),
      bodyMedium: TextStyle(
        fontSize: 14,
        color: Palette.ink,
        fontFeatures: numbers,
      ),
      bodySmall: TextStyle(
        fontSize: 12,
        color: Palette.muted,
        fontFeatures: numbers,
      ),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: Palette.background,
      foregroundColor: Palette.ink,
      surfaceTintColor: Colors.transparent,
      centerTitle: false,
      elevation: 0,
    ),
    dividerTheme: const DividerThemeData(
      color: Palette.line,
      thickness: 1,
      space: 1,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: Palette.teal,
        overlayColor: const Color(0xFF059669),
        foregroundColor: const Color(0xFF062A20),
        minimumSize: const Size(44, 44),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9)),
        textStyle: const TextStyle(
          fontFamily: 'Inter',
          fontWeight: FontWeight.w600,
          fontSize: 14,
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: Palette.ink,
        minimumSize: const Size(44, 44),
        side: const BorderSide(color: Palette.line),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Palette.background,
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(9),
        borderSide: const BorderSide(color: Palette.line),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(9),
        borderSide: const BorderSide(color: Palette.line),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(9),
        borderSide: const BorderSide(color: Palette.teal),
      ),
      floatingLabelStyle: const TextStyle(color: Palette.teal),
    ),
    navigationBarTheme: const NavigationBarThemeData(
      backgroundColor: Palette.surface,
      indicatorColor: Palette.soft,
      height: 70,
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: const Color(0xFF243247),
      contentTextStyle: const TextStyle(color: Palette.ink),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: Palette.teal,
    ),
    tooltipTheme: const TooltipThemeData(
      waitDuration: Duration(milliseconds: 350),
    ),
  );
}

void feedbackMessage(BuildContext context, String message) {
  if (!context.mounted) return;
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
}

Future<bool> confirm(
  BuildContext context,
  String title,
  String message, {
  String action = 'Tasdiqlash',
}) async {
  return await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(title),
          content: Text(message),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Qaytish'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: Text(action),
            ),
          ],
        ),
      ) ??
      false;
}

class Surface extends StatelessWidget {
  const Surface({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(18),
    this.color = Palette.surface,
  });
  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color color;
  @override
  Widget build(BuildContext context) => Material(
    color: color,
    clipBehavior: Clip.antiAlias,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: const BorderSide(color: Palette.line),
    ),
    child: Padding(padding: padding, child: child),
  );
}

class SectionHeader extends StatelessWidget {
  const SectionHeader(this.title, {super.key, this.action});
  final String title;
  final Widget? action;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 24, bottom: 12),
    child: Row(
      children: [
        Expanded(
          child: Text(title, style: Theme.of(context).textTheme.titleLarge),
        ),
        ?action,
      ],
    ),
  );
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.title,
    required this.message,
    this.icon = Icons.inbox_outlined,
    this.action,
  });
  final String title;
  final String message;
  final IconData icon;
  final Widget? action;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 36, horizontal: 20),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 42, color: Palette.teal),
        const SizedBox(height: 16),
        Text(
          title,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        Text(
          message,
          textAlign: TextAlign.center,
          style: const TextStyle(color: Palette.muted),
        ),
        if (action != null)
          Padding(padding: const EdgeInsets.only(top: 20), child: action),
      ],
    ),
  );
}

class StatusTag extends StatelessWidget {
  const StatusTag(this.label, {super.key, this.color = Palette.muted});
  final String label;
  final Color color;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
    decoration: BoxDecoration(
      color: color.withValues(alpha: .09),
      borderRadius: BorderRadius.circular(6),
    ),
    child: Text(
      label,
      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color),
    ),
  );
}

class PersonAvatar extends StatelessWidget {
  const PersonAvatar(this.name, {super.key, this.size = 44});
  final String name;
  final double size;
  @override
  Widget build(BuildContext context) => Container(
    width: size,
    height: size,
    alignment: Alignment.center,
    decoration: BoxDecoration(
      color: Palette.soft,
      borderRadius: BorderRadius.circular(12),
    ),
    child: Text(
      initials(name),
      style: const TextStyle(color: Palette.teal, fontWeight: FontWeight.w700),
    ),
  );
}

class AmountLabel extends StatelessWidget {
  const AmountLabel({
    super.key,
    required this.label,
    required this.amount,
    this.color = Palette.ink,
  });
  final String label;
  final int amount;
  final Color color;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label, style: const TextStyle(color: Palette.muted, fontSize: 13)),
      const SizedBox(height: 6),
      FittedBox(
        fit: BoxFit.scaleDown,
        alignment: Alignment.centerLeft,
        child: Text(
          formatMoney(amount),
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: color,
          ),
        ),
      ),
    ],
  );
}

String promiseLabel(Json promise) => switch (promise['status']) {
  'fulfilled' => 'Bajarilgan',
  'broken' => 'Muddati o‘tgan',
  'partial' => 'Qisman bajarilgan',
  'cancelled' => 'Bekor qilingan',
  _ => 'Va’da bor',
};
Color promiseColor(Json promise) => switch (promise['status']) {
  'fulfilled' => Palette.green,
  'broken' => Palette.red,
  'cancelled' => Palette.muted,
  _ => Palette.amber,
};
String methodLabel(String method) => switch (method) {
  'cash' => 'Naqd',
  'transfer' => 'O‘tkazma',
  'terminal' => 'Terminal',
  _ => 'Boshqa',
};

class ActivityRow extends StatelessWidget {
  const ActivityRow(this.item, {super.key, this.onTap});
  final Json item;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) {
    final kind = text(item['kind']);
    final icon = switch (kind) {
      'payment' => Icons.south_west_rounded,
      'refund' => Icons.north_east_rounded,
      'promise' => Icons.event_available_outlined,
      'dispute' => Icons.help_outline_rounded,
      'note' => Icons.notes_rounded,
      'customer' => Icons.person_outline,
      'import' => Icons.file_download_outlined,
      _ => Icons.receipt_long_outlined,
    };
    final amount = item['amount'];
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
      leading: CircleAvatar(
        backgroundColor: Palette.soft,
        foregroundColor: Palette.teal,
        child: Icon(icon, size: 21),
      ),
      title: Text(
        text(item['title']),
        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
      ),
      subtitle: Text(
        [
          text(item['customer_name']),
          text(item['details']),
          '${displayDate(item['created_at'])} · ${text(item['actor_name'])}',
        ].where((part) => part.isNotEmpty).join('\n'),
        style: const TextStyle(fontSize: 12, height: 1.5, color: Palette.muted),
      ),
      trailing: amount != null && integer(amount) != 0
          ? Text(
              formatMoney(amount, unit: false),
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: kind == 'payment' ? Palette.green : Palette.ink,
              ),
            )
          : null,
      onTap: onTap,
    );
  }
}
