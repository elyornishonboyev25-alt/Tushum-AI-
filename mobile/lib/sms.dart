import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import 'app.dart' show ContentList;
import 'core.dart';
import 'ui.dart';

String smsStatus(dynamic value) => switch (text(value)) {
  'draft' => 'Narxi hisoblandi',
  'submitting' => 'So‘rov bajarilmoqda',
  'uncertain' || 'unknown' => 'Natija tekshirilmoqda',
  'queued' => 'Navbatda',
  'sent' => 'Operatorga uzatildi',
  'delivered' => 'Yetkazildi',
  'failed' => 'Yetkazilmadi',
  'rejected' => 'Rad etildi',
  _ => 'Holat tekshirilmoqda',
};

class SmsPage extends StatefulWidget {
  const SmsPage({super.key, required this.store, this.customerId});
  final AppStore store;
  final String? customerId;

  @override
  State<SmsPage> createState() => _SmsPageState();
}

class _SmsPageState extends State<SmsPage> {
  Json configuration = {};
  Json account = {};
  List<Json> templates = [];
  List<Json> messages = [];
  final controllers = <String, TextEditingController>{};
  Json? selected;
  Json? preview;
  String? error;
  bool loading = true;
  bool busy = false;
  final formKey = GlobalKey<FormState>();
  AppStore get store => widget.store;
  Json? get customer => store.find('customers', widget.customerId ?? '');

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    for (final controller in controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> load() async {
    try {
      final config = Map<String, dynamic>.from(
        await store.api.request('/api/sms/config') as Map,
      );
      Json details = {};
      List<Json> history = [];
      if (config['enabled'] == true) {
        details = Map<String, dynamic>.from(
          await store.api.request('/api/sms/account') as Map,
        );
        if (widget.customerId != null) {
          final response = await store.api.request(
            '/api/customers/${widget.customerId}/sms',
          ) as Map;
          history = (response['items'] as List)
              .map((row) => Map<String, dynamic>.from(row as Map))
              .toList();
        }
      }
      if (!mounted) return;
      setState(() {
        configuration = config;
        account = details;
        templates = (details['templates'] as List? ?? [])
            .map((row) => Map<String, dynamic>.from(row as Map))
            .toList();
        messages = history;
        error = null;
        loading = false;
      });
    } on ApiError catch (failure) {
      if (mounted) {
        setState(() {
          error = failure.message;
          loading = false;
        });
      }
    }
  }

  void selectTemplate(String? id) {
    final template = templates.firstWhere((row) => text(row['id']) == id);
    for (final controller in controllers.values) {
      controller.dispose();
    }
    controllers.clear();
    final defaults = {
      'name': text(customer?['name']),
      'company': text(store.business['name']),
      'amount': formatMoney(customer?['balance'], unit: false),
      'price': formatMoney(customer?['balance'], unit: false),
      'date': store.currentDay,
      'phone': text(store.business['phone']),
    };
    for (final variable in template['variables'] as List? ?? []) {
      final key = text(variable['key']);
      controllers[key] = TextEditingController(text: defaults[key] ?? '');
    }
    setState(() {
      selected = template;
      preview = null;
      error = null;
    });
  }

  Future<void> calculate() async {
    if (!(formKey.currentState?.validate() ?? false) || selected == null) {
      return;
    }
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() {
      busy = true;
      error = null;
      preview = null;
    });
    try {
      final result = await store.api.request(
        '/api/customers/${widget.customerId}/sms/preview',
        method: 'POST',
        body: {
          'template_id': int.parse(text(selected!['id'])),
          'params': {
            for (final entry in controllers.entries)
              entry.key: entry.value.text.trim(),
          },
        },
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

  Future<void> submit(Json message) async {
    if (busy) return;
    final accepted = await confirm(
      context,
      'SMS yuborishni tasdiqlash',
      '${message['phone']} raqamiga ${formatMoney(message['price'])} qiymatidagi xabar yuboriladi.',
      action: 'Tasdiqlash',
    );
    if (!accepted || !mounted) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final response = await store.api.request(
        '/api/sms/${message['id']}/send',
        method: 'POST',
        body: {},
        operationId: text(message['id']),
      ) as Map;
      if (!mounted) return;
      setState(() => preview = null);
      feedbackMessage(context, smsStatus(response['status']));
      await load();
      await store.refresh();
    } on ApiError catch (failure) {
      if (!mounted) return;
      setState(() {
        error = failure.message;
        preview = null;
      });
      // The server retains the immutable message and provider idempotency key.
      await loadHistory();
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> loadHistory() async {
    if (widget.customerId == null) return;
    try {
      final result = await store.api.request(
        '/api/customers/${widget.customerId}/sms',
      ) as Map;
      if (mounted) {
        setState(
          () => messages = (result['items'] as List)
              .map((row) => Map<String, dynamic>.from(row as Map))
              .toList(),
        );
      }
    } on ApiError catch (failure) {
      if (mounted) setState(() => error = failure.message);
    }
  }

  Future<void> refreshMessage(Json message) async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await store.api.request('/api/sms/${message['id']}');
      await loadHistory();
    } on ApiError catch (failure) {
      if (mounted) setState(() => error = failure.message);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget messageCard(Json message, {bool draft = false}) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Surface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          StatusTag(
            smsStatus(message['status']),
            color: message['status'] == 'delivered'
                ? Palette.green
                : Palette.teal,
          ),
          const SizedBox(height: 12),
          Text(text(message['text']), style: const TextStyle(height: 1.5)),
          const SizedBox(height: 12),
          Text(
            '${message['phone']} · ${message['parts']} qism · ${formatMoney(message['price'])}',
            style: const TextStyle(color: Palette.muted, fontSize: 12),
          ),
          if (text(message['error']).isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Text(
                text(message['error']),
                style: const TextStyle(color: Palette.red),
              ),
            ),
          if (draft)
            Padding(
              padding: const EdgeInsets.only(top: 14),
              child: FilledButton.icon(
                onPressed: busy ? null : () => submit(message),
                icon: const Icon(Icons.send_outlined),
                label: const Text('SMS yuborish'),
              ),
            )
          else if (['uncertain', 'submitting'].contains(message['status']) &&
              text(message['provider_id']).isEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: TextButton(
                onPressed: busy ? null : () => submit(message),
                child: const Text('Shu so‘rovni tekshirish'),
              ),
            )
          else if (![
            'delivered',
            'failed',
            'rejected',
          ].contains(message['status']))
            TextButton(
              onPressed: busy ? null : () => refreshMessage(message),
              child: const Text('Yetkazilish holatini tekshirish'),
            ),
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget.customerId == null ? 'SMS integratsiyasi' : 'SMS eslatma',
      ),
    ),
    body: ContentList(
      onRefresh: load,
      children: [
        if (loading) const Center(child: CircularProgressIndicator()),
        if (error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Surface(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(error!, style: const TextStyle(color: Palette.red)),
                  TextButton(
                    onPressed: busy ? null : load,
                    child: const Text('Qayta tekshirish'),
                  ),
                ],
              ),
            ),
          ),
        if (!loading &&
            configuration.isNotEmpty &&
            configuration['enabled'] != true)
          Surface(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'USMS hisobini biznesga bog‘lash',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                Text(
                  configuration['configured'] == true
                      ? 'Login va maxfiy kalit serverda mavjud. Railway Variables bo‘limiga USMS_BUSINESS_ID ni qo‘shib, quyidagi qiymatni kiriting.'
                      : 'Railway Variables bo‘limida USMS_LOGIN, USMS_SECRET, USMS_SENDER va USMS_BUSINESS_ID ni sozlang.',
                ),
                const SizedBox(height: 12),
                SelectableText(text(configuration['business_id'])),
                const SizedBox(height: 10),
                OutlinedButton.icon(
                  onPressed: () async {
                    await Clipboard.setData(
                      ClipboardData(text: text(configuration['business_id'])),
                    );
                    if (context.mounted) {
                      feedbackMessage(
                        context,
                        'Biznes identifikatori nusxalandi',
                      );
                    }
                  },
                  icon: const Icon(Icons.copy_outlined),
                  label: const Text('Biznes ID ni nusxalash'),
                ),
              ],
            ),
          ),
        if (account.isNotEmpty) ...[
          Surface(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                AmountLabel(
                  label: 'USMS balansi',
                  amount: integer(account['balance']),
                ),
                const SizedBox(height: 10),
                Text(
                  'Jo‘natuvchi ${text(account['sender']).isEmpty ? 'USMS sozlamasi bo‘yicha' : account['sender']}',
                ),
                Text(
                  '${templates.length} ta servis shabloni',
                  style: const TextStyle(color: Palette.muted),
                ),
              ],
            ),
          ),
          if (templates.isEmpty)
            const Padding(
              padding: EdgeInsets.only(top: 16),
              child: Text(
                'USMS kabinetida servis shablonini moderatsiyaga yuboring yoki tayyor shablonlardan tanlang.',
              ),
            ),
          if (widget.customerId != null && templates.isNotEmpty) ...[
            const SectionHeader('Xabar tayyorlash'),
            Surface(
              child: Form(
                key: formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${text(customer?['name'])} · ${text(customer?['phone'])}',
                    ),
                    const SizedBox(height: 16),
                    DropdownButtonFormField<String>(
                      initialValue: selected == null
                          ? null
                          : text(selected!['id']),
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'Servis shabloni',
                      ),
                      items: templates
                          .map(
                            (row) => DropdownMenuItem(
                              value: text(row['id']),
                              child: Text(
                                text(row['title']).isEmpty
                                    ? 'Shablon ${row['id']}'
                                    : text(row['title']),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: busy ? null : selectTemplate,
                    ),
                    if (selected != null) ...[
                      const SizedBox(height: 14),
                      Text(
                        text(selected!['text']),
                        style: const TextStyle(
                          color: Palette.muted,
                          height: 1.5,
                        ),
                      ),
                      for (final entry in controllers.entries)
                        Padding(
                          padding: const EdgeInsets.only(top: 14),
                          child: TextFormField(
                            controller: entry.value,
                            enabled: !busy,
                            maxLength: 80,
                            decoration: InputDecoration(labelText: entry.key),
                            validator: (value) => (value ?? '').trim().isEmpty
                                ? 'Qiymatni kiriting'
                                : null,
                            onChanged: (_) => setState(() => preview = null),
                          ),
                        ),
                      const SizedBox(height: 16),
                      OutlinedButton.icon(
                        onPressed: busy ? null : calculate,
                        icon: const Icon(Icons.calculate_outlined),
                        label: const Text('Matn va narxni tekshirish'),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            if (preview != null)
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: messageCard(preview!, draft: true),
              ),
          ],
          if (busy)
            const Padding(
              padding: EdgeInsets.all(16),
              child: LinearProgressIndicator(),
            ),
          if (widget.customerId != null) ...[
            const SectionHeader('SMS tarixi'),
            if (messages.isEmpty)
              const Text(
                'Yuborilgan SMS tarixi shu yerda ko‘rinadi.',
                style: TextStyle(color: Palette.muted),
              ),
            for (final message in messages) messageCard(message),
          ],
        ],
      ],
    ),
  );
}
