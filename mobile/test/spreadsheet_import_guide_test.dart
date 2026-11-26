import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:tushum_ai/spreadsheet_import_guide.dart';
import 'package:tushum_ai/ui.dart';

void main() {
  Future<void> openGuide(WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildTheme(),
        home: const Scaffold(
          body: SingleChildScrollView(
            child: SpreadsheetImportGuide(day: '2026-11-26'),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('Example changes update the sheet and explain invalid amounts', (
    tester,
  ) async {
    await openGuide(tester);
    await tester.tap(find.widgetWithText(ChoiceChip, 'Qarz summasi'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '1.5 mln');
    await tester.pump();
    expect(find.text('1.5 mln'), findsWidgets);
    expect(
      find.text('Musbat son kiriting. Masalan: 1500000 yoki 1500000.50.'),
      findsOneWidget,
    );
    await tester.enterText(find.byType(TextField), '1500000');
    await tester.pump();
    expect(
      find.text('Musbat son kiriting. Masalan: 1500000 yoki 1500000.50.'),
      findsNothing,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('Username and date examples reject malformed values', (
    tester,
  ) async {
    await openGuide(tester);
    await tester.tap(find.widgetWithText(ChoiceChip, 'Telegram username'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '@bad');
    await tester.pump();
    expect(
      find.text('@akmal_namuna kabi yozing: 5–32 ta belgi.'),
      findsOneWidget,
    );
    tester.testTextInput.hide();
    await tester.ensureVisible(find.widgetWithText(ChoiceChip, 'Qarz sanasi'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ChoiceChip, 'Qarz sanasi'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '2026-02-31');
    await tester.pump();
    expect(
      find.text('Mavjud sanani kiriting. Oy va kunni tekshiring.'),
      findsOneWidget,
    );
    await tester.enterText(find.byType(TextField), '10.12.2026');
    await tester.pump();
    expect(
      find.text('Mavjud sanani kiriting. Oy va kunni tekshiring.'),
      findsNothing,
    );
  });

  testWidgets('Guide fits a narrow phone with horizontal table scrolling', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await openGuide(tester);
    expect(
      find.text('Qolgan ustunlarni ko‘rish uchun jadvalni yon tomonga suring.'),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
    await tester.drag(
      find.byType(SingleChildScrollView).last,
      const Offset(-500, 0),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
