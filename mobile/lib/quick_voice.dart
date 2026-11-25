import 'package:material_ui/material_ui.dart';

import 'core.dart';
import 'ui.dart';

class QuickVoiceDialog extends StatefulWidget {
  const QuickVoiceDialog({super.key, required this.store});
  final AppStore store;
  @override
  State<QuickVoiceDialog> createState() => _QuickVoiceDialogState();
}

class _QuickVoiceDialogState extends State<QuickVoiceDialog> {
  final form = GlobalKey<FormState>();
  final name = TextEditingController();
  final username = TextEditingController();
  final amount = TextEditingController();
  late String dueOn;
  String operationId = uuid.v4();
  bool consent = false;
  bool busy = false;
  bool uncertain = false;
  String? error;
  Json? preview;

  @override
  void initState() {
    super.initState();
    dueOn = widget.store.currentDay;
  }

  Json get payload => {
    'name': name.text.trim(),
    'target': username.text.trim(),
    'amount': amount.text.trim(),
    'due_on': dueOn,
    'consent': consent,
  };

  Future<void> review() async {
    if (!form.currentState!.validate() || !consent || busy) return;
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = await widget.store.api.request(
        '/api/voice/quick-preview',
        method: 'POST',
        body: payload,
      );
      if (mounted) {
        setState(() => preview = Map<String, dynamic>.from(result as Map));
      }
    } on ApiError catch (failure) {
      if (mounted) setState(() => error = failure.message);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> call() async {
    if (busy || preview == null) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = await widget.store.mutate(
        '/api/voice/quick-calls',
        payload,
        operationId: operationId,
      );
      if (mounted) Navigator.pop(context, result);
    } on ApiError catch (failure) {
      if (mounted) {
        setState(() {
          error = failure.message;
          uncertain = failure.status == 0;
          busy = false;
        });
      }
    }
  }

  @override
  void dispose() {
    name.dispose();
    username.dispose();
    amount.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(
      preview == null ? 'Mijozga AI qo‘ng‘irog‘i' : 'Qo‘ng‘iroqni boshlash',
    ),
    content: SizedBox(
      width: 520,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (preview == null) ...[
              const Text(
                'Mijozning ismi, Telegram username’i va qarz summasini kiriting.',
              ),
              const SizedBox(height: 20),
              Text(
                'Do‘kon / korxona: ${widget.store.data['voice']?['profile']?['business_name'] ?? ''}',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 12),
              Form(
                key: form,
                child: Column(
                  children: [
                    TextFormField(
                      controller: name,
                      enabled: !busy,
                      maxLength: 100,
                      textCapitalization: TextCapitalization.words,
                      decoration: const InputDecoration(
                        labelText: 'Mijozning ismi',
                        prefixIcon: Icon(Icons.person_outline),
                      ),
                      validator: (v) => (v?.trim().length ?? 0) >= 2
                          ? null
                          : 'Mijoz ismini kiriting',
                    ),
                    const SizedBox(height: 10),
                    TextFormField(
                      controller: username,
                      enabled: !busy,
                      maxLength: 33,
                      autocorrect: false,
                      enableSuggestions: false,
                      decoration: const InputDecoration(
                        labelText: 'Telegram username',
                        hintText: '@username',
                        prefixIcon: Icon(Icons.alternate_email),
                      ),
                      validator: (v) =>
                          RegExp(r'^@?[A-Za-z][A-Za-z0-9_]{4,31}$')
                              .hasMatch(v?.trim() ?? '')
                          ? null
                          : 'Telegram username’ini kiriting, masalan @username',
                    ),
                    const SizedBox(height: 10),
                    TextFormField(
                      controller: amount,
                      enabled: !busy,
                      keyboardType: const TextInputType.numberWithOptions(
                        decimal: true,
                      ),
                      decoration: const InputDecoration(
                        labelText: 'Qarz summasi',
                        suffixText: 'so‘m',
                        prefixIcon: Icon(Icons.account_balance_wallet_outlined),
                      ),
                      validator: (v) {
                        final parsed = double.tryParse(
                          (v ?? '').replaceAll(' ', '').replaceAll(',', '.'),
                        );
                        return parsed != null && parsed.isFinite && parsed > 0
                            ? null
                            : 'Musbat qarz summasini kiriting';
                      },
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      onPressed: busy
                          ? null
                          : () async {
                              final day = DateTime.parse(
                                widget.store.currentDay,
                              );
                              final picked = await showDatePicker(
                                context: context,
                                initialDate: DateTime.parse(dueOn),
                                firstDate: day,
                                lastDate: day.add(const Duration(days: 3650)),
                              );
                              if (picked != null && mounted) {
                                setState(
                                  () => dueOn = picked
                                      .toIso8601String()
                                      .substring(0, 10),
                                );
                              }
                            },
                      icon: const Icon(Icons.calendar_today_outlined, size: 18),
                      label: Text('To‘lov muddati · ${displayDate(dueOn)}'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                value: consent,
                onChanged: busy
                    ? null
                    : (v) => setState(() => consent = v ?? false),
                title: const Text(
                  'Mijoz qo‘ng‘iroq va suhbatni matnga aylantirishga rozi.',
                ),
              ),
              TextButton(
                onPressed: busy
                    ? null
                    : () => Navigator.pop(context, <String, dynamic>{
                        'select_existing': true,
                      }),
                child: const Text('Mavjud nasiyani tanlash'),
              ),
            ] else ...[
              Text(
                'Qo‘ng‘iroq: ${preview!['business']}',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 6),
              Text('Mas’ul menejer: ${preview!['manager_name']}'),
              const SizedBox(height: 16),
              Surface(
                color: Palette.soft,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      text(preview!['name']),
                      style: const TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '@${preview!['target']}',
                      style: const TextStyle(color: Palette.teal, fontSize: 16),
                    ),
                    const SizedBox(height: 20),
                    Text(
                      formatMoney(preview!['amount']),
                      style: const TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.w700,
                        color: Palette.teal,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text('To‘lov muddati · ${displayDate(preview!['due_on'])}'),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              Text(
                preview!['action'] == 'new'
                    ? 'Yangi mijoz va nasiya saqlanadi. AI shu hisob bo‘yicha Telegram orqali qo‘ng‘iroq qiladi.'
                    : 'Mavjud mijoz va nasiya ishlatiladi. AI saqlangan qarz bo‘yicha qo‘ng‘iroq qiladi.',
                style: const TextStyle(height: 1.5),
              ),
              const SizedBox(height: 10),
              const Text(
                'AI suhbat boshida o‘zini tanishtiradi. Tasdiqlangan kelishuv dashboardga yoziladi.',
                style: TextStyle(color: Palette.muted, fontSize: 13),
              ),
            ],
            if (error != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(error!, style: const TextStyle(color: Palette.red)),
              ),
            if (uncertain)
              const Padding(
                padding: EdgeInsets.only(top: 12),
                child: Text(
                  'So‘rov natijasi hali aniq emas. “Natijani tekshirish” aynan shu so‘rovni qayta tekshiradi.',
                  style: TextStyle(color: Palette.amber),
                ),
              ),
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: busy ? null : () => Navigator.pop(context),
        child: const Text('Qaytish'),
      ),
      if (preview != null && !uncertain)
        TextButton(
          onPressed: busy
              ? null
              : () => setState(() {
                  preview = null;
                  error = null;
                  operationId = uuid.v4();
                }),
          child: const Text('Tahrirlash'),
        ),
      FilledButton.icon(
        onPressed: busy || preview == null && !consent
            ? null
            : preview == null
            ? review
            : call,
        icon: Icon(
          busy
              ? Icons.hourglass_top
              : preview == null
              ? Icons.arrow_forward
              : Icons.call,
        ),
        label: Text(
          busy
              ? 'Kutilmoqda…'
              : preview == null
              ? 'Davom etish'
              : uncertain
              ? 'Natijani tekshirish'
              : 'Qo‘ng‘iroq qilish',
        ),
      ),
    ],
  );
}
