import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:tushum_ai/app.dart';
import 'package:tushum_ai/core.dart';
import 'package:tushum_ai/executive_data.dart';
import 'package:tushum_ai/ui.dart';
import 'package:tushum_ai/voice.dart';

AppStore fixture() => AppStore()
  ..data = {
    'today': '2026-11-25',
    'business': {'name': 'Baraka Stroy Ulgurji', 'is_demo': 1},
    'me': {'role': 'owner', 'name': 'Jasur'},
    'voice': {'ready': true, 'custom_targets': true},
    'customers': [
      {
        'id': 'a',
        'name': 'Akmal Karimov',
        'phone': '+998901234567',
        'telegram_username': 'akmal_test',
        'balance': 300000000,
        'archived': 0,
        'contact_allowed': true,
      },
      {'id': 'b', 'name': 'Madina Savdo', 'balance': 0, 'archived': 0},
      {'id': 'c', 'name': 'Yangi mijoz', 'balance': 0, 'archived': 0},
    ],
    'debts': [
      {
        'id': 'd',
        'customer_id': 'a',
        'balance': 300000000,
        'paid': 0,
        'amount': 300000000,
        'due_on': '2026-11-15',
        'overdue': true,
        'archived': 0,
      },
      {
        'id': 'e',
        'customer_id': 'b',
        'balance': 0,
        'paid': 10000000,
        'amount': 10000000,
        'due_on': '2026-11-15',
        'archived': 0,
      },
    ],
    'payments': [
      {'amount': 10000000, 'paid_on': '2026-11-20'},
    ],
    'refunds': [
      {'amount': 2000000, 'refunded_on': '2026-11-21'},
    ],
  };

void main() {
  test(
    'Only outstanding confirmed AI promises count; cash remains separate',
    () {
      final store = fixture();
      store.data['promises'] = [
        {
          'customer_id': 'a',
          'status': 'partial',
          'amount': 100000000,
          'paid': 20000000,
          'note': 'Telegram AI suhbati orqali tasdiqlandi.',
          'cancelled': 0,
        },
        {
          'customer_id': 'a',
          'status': 'active',
          'amount': 90000000,
          'paid': 0,
          'note': 'Menejer va’dasi',
          'cancelled': 0,
        },
        for (final status in ['cancelled', 'broken', 'fulfilled'])
          {
            'status': status,
            'amount': 999999999,
            'note': 'Telegram AI suhbati',
            'cancelled': 0,
          },
        {
          'status': 'active',
          'amount': 999999999,
          'note': 'Telegram AI suhbati',
          'cancelled': true,
        },
      ];
      final ledger = ExecutiveLedger(store, []);
      expect(ledger.balance, 300000000);
      expect(ledger.overdue, 300000000);
      expect(ledger.aiPromised, 80000000);
      expect(ledger.received, 8000000);
      expect(ledger.entries.first.overdueDays, 10);
      expect(ledger.entries.first.stage, DebtStage.promised);
      expect(ledger.entries.first.contactAllowed, true);
      expect(
        ledger.entries.first.matches(LedgerFilter.promised, 'AKMAL'),
        true,
      );
      expect(ledger.entries.first.matches(LedgerFilter.paid, ''), false);
      store.dispose();
    },
  );

  test('Paid and new customers differ; an active call takes precedence', () {
    final store = fixture();
    var ledger = ExecutiveLedger(store, [
      {'customer_id': 'a', 'status': 'connected', 'created_at': '2026-11-25'},
    ]);
    expect(ledger.activeCalls, 1);
    expect(ledger.entries.first.stage, DebtStage.active);
    expect(
      ledger.entries.singleWhere((e) => e.id == 'b').stage,
      DebtStage.paid,
    );
    expect(
      ledger.entries.singleWhere((e) => e.id == 'c').stage,
      DebtStage.clear,
    );
    (store.data['customers'] as List)[1]['balance'] = 1000000;
    ledger = ExecutiveLedger(store, []);
    expect(
      ledger.entries.singleWhere((e) => e.id == 'b').stage,
      DebtStage.waiting,
    );
    store.dispose();
  });

  testWidgets(
    'Demo is local, can pause and close, and never changes ledger data',
    (tester) async {
      tester.view.physicalSize = const Size(1440, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final store = fixture();
      final before = jsonEncode(store.data);
      await tester.pumpWidget(
        MaterialApp(
          theme: buildTheme(),
          home: Scaffold(
            body: HomePage(store: store, showCustomers: () {}),
          ),
        ),
      );
      await tester.tap(find.text('Demo suhbat'));
      await tester.pump();
      expect(find.text('Demo simulyatsiya · AI gaplashmoqda'), findsOneWidget);
      await tester.tap(find.byTooltip('Demoni pauza qilish'));
      await tester.pump(const Duration(seconds: 15));
      expect(find.text('Demo simulyatsiya · pauza'), findsOneWidget);
      expect(find.textContaining('Demo natijasi:'), findsNothing);
      await tester.tap(find.byTooltip('Demoni davom ettirish'));
      for (var i = 0; i < 7; i++) {
        await tester.pump(const Duration(seconds: 3));
      }
      expect(find.textContaining('Demo natijasi: 1 500 000'), findsOneWidget);
      expect(jsonEncode(store.data), before);
      expect(tester.takeException(), isNull);
      await tester.tap(find.byTooltip('Demoni yopish'));
      await tester.pump(const Duration(seconds: 2));
      expect(find.textContaining('Demo simulyatsiya'), findsNothing);
      expect(jsonEncode(store.data), before);
      await tester.pumpWidget(const SizedBox());
      store.dispose();
    },
  );

  testWidgets(
    'Call preparation preselects customer but requires explicit consent',
    (tester) async {
      final store = fixture();
      await tester.pumpWidget(
        MaterialApp(
          theme: buildTheme(),
          home: StartVoiceDialog(
            store: store,
            connection: const {'custom_targets': true},
            initialCustomerId: 'a',
          ),
        ),
      );
      await tester.pump();
      expect(
        tester.widget<TextFormField>(find.byType(TextFormField)).initialValue,
        'akmal_test',
      );
      expect(
        tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,
        false,
      );
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Qo‘ng‘iroq qilish'),
            )
            .onPressed,
        isNull,
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      store.dispose();
    },
  );

  testWidgets('Small-screen viewer cannot start real calls or import data', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 780);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final store = fixture();
    store.data['me'] = {'name': 'Kuzatuvchi', 'role': 'viewer'};
    store.data['business'] = {'name': 'Uzoq nomli savdo korxonasi'};
    await tester.pumpWidget(
      MaterialApp(
        theme: buildTheme(),
        home: AppShell(store: store),
      ),
    );
    await tester.pump();
    expect(
      tester
          .widget<IconButton>(
            find.byWidgetPredicate(
              (w) => w is IconButton && w.tooltip == 'Excel yuklash',
            ),
          )
          .onPressed,
      isNull,
    );
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'AI qo‘ng‘iroqlarni boshlash'),
          )
          .onPressed,
      isNull,
    );
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    store.dispose();
  });
}
