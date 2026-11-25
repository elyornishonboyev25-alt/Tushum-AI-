import 'core.dart';

enum DebtStage { waiting, promised, paid, review, active, clear }

enum LedgerFilter { all, waiting, promised, paid }

bool isOpenPromise(Json p) =>
    ['active', 'partial'].contains(p['status']) &&
    p['cancelled'] != true &&
    p['cancelled'] != 1;
int remainingPromise(Json p) =>
    (integer(p['amount']) - integer(p['paid'])).clamp(0, integer(p['amount']));
bool isVoiceActive(Json call) =>
    ['queued', 'dialing', 'connected'].contains(call['status']);

class DebtorEntry {
  const DebtorEntry({
    required this.customer,
    required this.balance,
    required this.overdueDays,
    required this.stage,
    required this.summary,
    this.call,
    this.promise,
  });
  final Json customer;
  final int balance;
  final int overdueDays;
  final DebtStage stage;
  final String summary;
  final Json? call;
  final Json? promise;
  String get id => text(customer['id']);
  String get name => text(customer['name']);
  bool get contactAllowed =>
      customer['contact_allowed'] == true || customer['contact_allowed'] == 1;
  bool matches(LedgerFilter filter, String query) {
    final stageMatches = switch (filter) {
      LedgerFilter.all => true,
      LedgerFilter.promised => stage == DebtStage.promised,
      LedgerFilter.paid => stage == DebtStage.paid,
      LedgerFilter.waiting => [
        DebtStage.waiting,
        DebtStage.review,
        DebtStage.active,
      ].contains(stage),
    };
    final haystack =
        '${customer['name']} ${customer['company']} ${customer['phone']} ${customer['telegram_username']}'
            .toLowerCase();
    return stageMatches && haystack.contains(query.trim().toLowerCase());
  }
}

class ExecutiveLedger {
  ExecutiveLedger(AppStore store, List<Json> calls) {
    final debts = store.rows('debts');
    final promises = store.rows('promises');
    balance = debts.fold<int>(0, (sum, d) => sum + integer(d['balance']));
    overdue = debts
        .where((d) => d['overdue'] == true)
        .fold<int>(0, (sum, d) => sum + integer(d['balance']));
    aiPromised = promises
        .where(
          (p) =>
              isOpenPromise(p) &&
              text(p['note']).startsWith('Telegram AI suhbati'),
        )
        .fold<int>(0, (sum, p) => sum + remainingPromise(p));
    final month = store.currentDay.substring(0, 7);
    received =
        store
            .rows('payments')
            .where((p) => text(p['paid_on']).startsWith(month))
            .fold<int>(0, (sum, p) => sum + integer(p['amount'])) -
        store
            .rows('refunds')
            .where((r) => text(r['refunded_on']).startsWith(month))
            .fold<int>(0, (sum, r) => sum + integer(r['amount']));
    activeCalls = calls.where(isVoiceActive).length;
    final day = DateTime.tryParse('${store.currentDay}T00:00:00Z');
    final recent = [...calls]
      ..sort((a, b) => text(b['created_at']).compareTo(text(a['created_at'])));
    entries =
        store.rows('customers').where((c) => integer(c['archived']) == 0).map((
          customer,
        ) {
          final id = text(customer['id']);
          final customerDebts = debts
              .where((d) => d['customer_id'] == id)
              .toList();
          final customerPromises = promises
              .where((p) => p['customer_id'] == id && isOpenPromise(p))
              .toList();
          final customerCalls = recent
              .where((c) => c['customer_id'] == id)
              .toList();
          final call = customerCalls.isEmpty ? null : customerCalls.first;
          final promise = customerPromises.isEmpty
              ? null
              : customerPromises.first;
          final dueDays = customerDebts
              .where((d) => integer(d['balance']) > 0)
              .map((d) {
                final due = DateTime.tryParse('${text(d['due_on'])}T00:00:00Z');
                return day == null || due == null
                    ? 0
                    : day.difference(due).inDays.clamp(0, 99999);
              })
              .fold<int>(0, (maximum, n) => n > maximum ? n : maximum);
          final amount = integer(customer['balance']);
          final stage = amount == 0
              ? (customerDebts.any((d) => integer(d['paid']) > 0)
                    ? DebtStage.paid
                    : DebtStage.clear)
              : call != null && isVoiceActive(call)
              ? DebtStage.active
              : customer['disputed'] == true ||
                    store
                        .rows('voice_handoffs')
                        .any(
                          (h) =>
                              h['customer_id'] == id &&
                              integer(h['resolved']) == 0,
                        )
              ? DebtStage.review
              : promise != null
              ? DebtStage.promised
              : DebtStage.waiting;
          final summary = text(call?['summary']).isNotEmpty
              ? text(call?['summary'])
              : stage == DebtStage.active
              ? 'Jonli suhbat davom etmoqda'
              : promise != null
              ? '${text(promise['note']).startsWith('Telegram AI suhbati') ? 'AI' : 'Qayd'}: ${displayDate(promise['due_on'])} · ${formatMoney(remainingPromise(promise))} va’da qilingan'
              : stage == DebtStage.paid
              ? 'Qarz qoldig‘i to‘liq yopilgan'
              : stage == DebtStage.clear
              ? 'Ochiq nasiya yo‘q'
              : 'AI suhbat hali boshlanmagan';
          return DebtorEntry(
            customer: customer,
            balance: amount,
            overdueDays: dueDays,
            stage: stage,
            summary: summary,
            call: call,
            promise: promise,
          );
        }).toList()..sort((a, b) => b.balance.compareTo(a.balance));
  }
  late final int balance, overdue, aiPromised, received, activeCalls;
  late final List<DebtorEntry> entries;
  double get promisedShare => balance == 0 ? 0 : aiPromised / balance * 100;
}

String stageLabel(DebtStage stage) => switch (stage) {
  DebtStage.waiting => 'Kutilmoqda',
  DebtStage.promised => 'Va’da berdi',
  DebtStage.paid => 'To‘landi',
  DebtStage.review => 'Tekshiruvda',
  DebtStage.active => 'Suhbatda',
  DebtStage.clear => 'Qoldiqsiz',
};
