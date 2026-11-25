import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:tushum_ai/app.dart';
import 'package:tushum_ai/core.dart';
import 'package:tushum_ai/forms.dart';
import 'package:tushum_ai/ui.dart';

void main() {
  testWidgets('Unconfirmed save keeps its payload and operation identifier', (
    tester,
  ) async {
    final store = AppStore();
    final ids = <String>[];
    await tester.pumpWidget(
      MaterialApp(
        theme: buildTheme(),
        home: Builder(
          builder: (context) => Scaffold(
            body: FilledButton(
              onPressed: () => editForm(
                context,
                store,
                title: 'Sinov to‘lovi',
                fields: const [
                  FieldSpec(
                    'amount',
                    'Summa',
                    kind: FieldKind.money,
                    initial: '100',
                  ),
                ],
                submit: (values, id) async {
                  ids.add(id);
                  expect(values['amount'], '100');
                  if (ids.length == 1) throw const ApiError('Ulanish uzildi');
                },
              ),
              child: const Text('Ochish'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Ochish'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Saqlash'));
    await tester.pumpAndSettle();
    expect(
      tester.widget<TextFormField>(find.byType(TextFormField)).enabled,
      false,
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Saqlash'));
    await tester.pumpAndSettle();
    expect(ids, hasLength(2));
    expect(ids.first, ids.last);
    expect(find.text('Ochish'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    store.dispose();
  });

  test('Money display preserves fractional UZS', () {
    expect(formatMoney(123456789), '1 234 567.89 so‘m');
    expect(inputMoney(1050), '10.50');
    expect(inputMoney(1000), '10');
    expect(formatMoney(-15000), '-150 so‘m');
    expect(initials('Akmal Rahimov'), 'AR');
  });

  testWidgets('Sign in validates phone and password before sending', (
    tester,
  ) async {
    final store = AppStore();
    await tester.pumpWidget(
      MaterialApp(
        theme: buildTheme(),
        home: AuthPage(store: store),
      ),
    );
    await tester.ensureVisible(find.widgetWithText(FilledButton, 'Kirish'));
    await tester.tap(find.widgetWithText(FilledButton, 'Kirish'));
    await tester.pump();
    expect(find.text('Raqamni kiriting, +998901234567'), findsOneWidget);
    expect(find.text('Kamida 8 ta belgi kiriting'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    store.dispose();
  });

  testWidgets('Customer row fits a small phone with a large balance', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 780);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final store = AppStore();
    store.data = {
      'me': {'id': 'owner', 'name': 'Jasur', 'role': 'owner'},
      'business': {'name': 'Baraka'},
      'today': '2026-11-16',
      'customers': [
        {
          'id': 'customer',
          'name': 'Akmal Rahimov',
          'phone': '+998901234567',
          'company': 'Baraka Savdo',
          'balance': 99999999999999,
          'overdue': 100,
          'archived': 0,
        },
      ],
    };
    await tester.pumpWidget(
      MaterialApp(
        theme: buildTheme(),
        home: Scaffold(
          body: HomePage(store: store, showCustomers: () {}),
        ),
      ),
    );
    await tester.pump();
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    store.dispose();
  });
}
