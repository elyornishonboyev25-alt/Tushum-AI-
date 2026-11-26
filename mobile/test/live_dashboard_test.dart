import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:tushum_ai/core.dart';
import 'package:tushum_ai/executive_dashboard.dart';
import 'package:tushum_ai/ui.dart';

class VoiceApi extends ApiClient {
  VoiceApi() : super('http://test.invalid') {
    token = 'test-session';
  }
  bool ended = false;
  final methods = <String>[];
  @override
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Json? body,
    String? operationId,
  }) async {
    methods.add(method);
    final call = <String, dynamic>{
      'id': 'call',
      'customer_id': 'a',
      'debt_id': 'd',
      'status': ended ? 'completed' : 'connected',
      'created_at': '2026-11-25',
      'target': 'akmal_test',
    };
    if (path == '/api/voice') {
      return {
        'connection': {'ready': true},
        'calls': [call],
      };
    }
    return {
      ...call,
      'brief': {'customer': 'Akmal Karimov'},
      'transcript': [
        {'speaker': 'ai', 'text': 'Tushundim.', 'source': 'agent_output'},
        {
          'speaker': 'customer',
          'text': 'Ha, ertaga to‘layman.',
          'source': 'dedicated_stt_verbatim',
        },
      ],
    };
  }
}

class VoiceStore extends AppStore {
  final fakeApi = VoiceApi();
  @override
  VoiceApi get api => fakeApi;
  int refreshCount = 0;
  @override
  Future<bool> refresh() async {
    refreshCount++;
    return true;
  }
}

void main() {
  testWidgets(
    'Real API transcript contract renders both speakers; ending refreshes the ledger',
    (tester) async {
      tester.view.physicalSize = const Size(1440, 1100);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final store = VoiceStore()
        ..data = {
          'today': '2026-11-25',
          'voice': {'ready': true},
          'me': {'role': 'owner'},
          'customers': [
            {
              'id': 'a',
              'name': 'Akmal Karimov',
              'phone': '+998901234567',
              'balance': 300000000,
            },
          ],
          'debts': [
            {'id': 'd', 'customer_id': 'a', 'balance': 300000000},
          ],
        };
      await tester.pumpWidget(
        MaterialApp(
          theme: buildTheme(),
          home: Scaffold(
            body: ExecutiveDashboard(store: store, showCustomers: () {}),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 250));
      expect(find.text('Jonli suhbat · AI gaplashmoqda'), findsOneWidget);
      expect(find.text('Akmal Karimov · +998 90 123-45-67'), findsOneWidget);
      expect(find.text('Tushum AI javobi'), findsOneWidget);
      expect(find.text('Mijoz nutqi · STT'), findsOneWidget);
      expect(find.text('Tushundim.'), findsOneWidget);
      expect(find.text('Ha, ertaga to‘layman.'), findsOneWidget);
      expect(find.textContaining('Qarz: 3 000 000'), findsOneWidget);
      store.api.ended = true;
      await tester.pump(const Duration(seconds: 2));
      await tester.pump();
      expect(find.text('AI suhbat yakunlandi'), findsOneWidget);
      expect(store.refreshCount, 1);
      expect(store.api.methods.every((m) => m == 'GET'), true);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      store.dispose();
    },
  );
}
