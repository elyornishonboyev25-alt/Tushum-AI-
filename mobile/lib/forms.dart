import 'dart:async';
import 'dart:convert';

import 'package:material_ui/material_ui.dart';

import 'core.dart';
import 'ui.dart';

enum FieldKind { text, phone, money, date, select, multiline, password, toggle }

class FieldSpec {
  const FieldSpec(
    this.key,
    this.label, {
    this.kind = FieldKind.text,
    this.required = true,
    this.initial = '',
    this.options = const {},
    this.hint,
    this.maxLength = 120,
    this.firstDate,
    this.lastDate,
  });
  final String key;
  final String label;
  final FieldKind kind;
  final bool required;
  final String initial;
  final Map<String, String> options;
  final String? hint;
  final int maxLength;
  final DateTime? firstDate;
  final DateTime? lastDate;
}

typedef FormSubmit = Future<void> Function(Json values, String operationId);

Future<bool> editForm(
  BuildContext context,
  AppStore store, {
  required String title,
  String? description,
  required List<FieldSpec> fields,
  required FormSubmit submit,
  String button = 'Saqlash',
  String? draftKey,
}) async {
  FocusManager.instance.primaryFocus?.unfocus();
  return await Navigator.of(context).push<bool>(
        MaterialPageRoute(
          builder: (_) => EditorPage(
            store: store,
            title: title,
            description: description,
            fields: fields,
            submit: submit,
            button: button,
            draftKey: draftKey,
          ),
        ),
      ) ??
      false;
}

class EditorPage extends StatefulWidget {
  const EditorPage({
    super.key,
    required this.store,
    required this.title,
    required this.fields,
    required this.submit,
    required this.button,
    this.description,
    this.draftKey,
  });
  final AppStore store;
  final String title;
  final String? description;
  final List<FieldSpec> fields;
  final FormSubmit submit;
  final String button;
  final String? draftKey;
  @override
  State<EditorPage> createState() => _EditorPageState();
}

class _EditorPageState extends State<EditorPage> {
  final formKey = GlobalKey<FormState>();
  late final Map<String, TextEditingController> controllers;
  final Map<String, String> values = {};
  Timer? draftTimer;
  bool busy = false;
  bool restored = false;
  bool uncertain = false;
  String? error;
  String operationId = uuid.v4();
  String? submittedValues;
  String? get storageKey => widget.draftKey == null
      ? null
      : 'draft:${widget.store.me['id']}:${widget.draftKey}';

  @override
  void initState() {
    super.initState();
    controllers = {
      for (final field in widget.fields)
        field.key: TextEditingController(text: field.initial),
    };
    values.addAll({
      for (final field in widget.fields) field.key: field.initial,
    });
    restoreDraft();
    for (final controller in controllers.values) {
      controller.addListener(queueDraft);
    }
  }

  Future<void> restoreDraft() async {
    if (storageKey == null) return;
    try {
      final saved = await widget.store.storage.read(key: storageKey!);
      if (!mounted || saved == null) return;
      final draft = jsonDecode(saved) as Map;
      if (text(draft['_operation_id']).isNotEmpty) {
        operationId = text(draft['_operation_id']);
      }
      submittedValues = draft['_submitted_values'] as String?;
      uncertain = submittedValues != null;
      for (final field in widget.fields) {
        final value = text(draft[field.key]);
        if (value.isEmpty && field.required) continue;
        if (!uncertain &&
            field.kind == FieldKind.select &&
            !field.options.containsKey(value)) {
          continue;
        }
        controllers[field.key]!.text = value;
        values[field.key] = value;
      }
      setState(() => restored = true);
    } catch (_) {
      // An unreadable draft can be replaced by the next edit.
    }
  }

  void queueDraft() {
    if (storageKey == null || busy || uncertain) return;
    draftTimer?.cancel();
    draftTimer = Timer(const Duration(milliseconds: 400), () async {
      try {
        await widget.store.storage.write(
          key: storageKey!,
          value: jsonEncode({
            ...collect(),
            '_operation_id': operationId,
            '_submitted_values': submittedValues,
          }),
        );
      } catch (_) {
        if (mounted) {
          setState(
            () => error = 'Qoralama qurilmada saqlanmadi. Ma’lumotni serverga saqlashingiz mumkin.',
          );
        }
      }
    });
  }

  Json collect() => {
    for (final field in widget.fields)
      field.key: field.kind == FieldKind.toggle
          ? values[field.key] == 'true'
          : field.kind == FieldKind.select
          ? values[field.key]
          : controllers[field.key]!.text.trim(),
  };

  String? validate(FieldSpec field, String? value) {
    final input = value?.trim() ?? '';
    if (field.required && input.isEmpty) return 'Bu maydonni to‘ldiring';
    if (input.isEmpty) return null;
    if (field.kind == FieldKind.phone &&
        !RegExp(r'^(?:\+?998)?\d{9}$')
            .hasMatch(input.replaceAll(RegExp(r'[\s()\-]'), ''))) {
      return 'O‘zbekiston raqamini kiriting, +998901234567';
    }
    if (field.kind == FieldKind.money &&
        (!RegExp(r'^\d+([.,]\d{1,2})?$').hasMatch(input.replaceAll(' ', '')) ||
            (double.tryParse(input.replaceAll(' ', '').replaceAll(',', '.')) ??
                    0) <=
                0)) {
      return 'Musbat summani kiriting, masalan 150000';
    }
    if (field.kind == FieldKind.password && input.length < 8) {
      return 'Kamida 8 ta belgi kiriting';
    }
    if (field.kind == FieldKind.date && DateTime.tryParse(input) == null) {
      return 'Sanani tanlang';
    }
    return null;
  }

  Future<void> save() async {
    if (busy || !formKey.currentState!.validate()) return;
    FocusManager.instance.primaryFocus?.unfocus();
    final payload = uncertain && submittedValues != null
        ? Map<String, dynamic>.from(jsonDecode(submittedValues!) as Map)
        : collect();
    final serialized = jsonEncode(payload);
    if (submittedValues != null && submittedValues != serialized) {
      operationId = uuid.v4();
    }
    submittedValues = serialized;
    setState(() {
      busy = true;
      error = null;
    });
    draftTimer?.cancel();
    var completed = false;
    try {
      if (storageKey != null) {
        await widget.store.storage.write(
          key: storageKey!,
          value: jsonEncode({
            ...payload,
            '_operation_id': operationId,
            '_submitted_values': submittedValues,
          }),
        );
      }
      await widget.submit(payload, operationId);
      completed = true;
      uncertain = false;
      if (storageKey != null) {
        try {
          await widget.store.storage.delete(key: storageKey!);
        } catch (_) {
          // A retained draft retries this same operation identifier safely.
        }
      }
      if (mounted) Navigator.pop(context, true);
    } catch (failure) {
      if (mounted) {
        setState(() {
          uncertain =
              failure is! ApiError ||
              failure.status == 0 ||
              failure.status >= 500 ||
              (failure.status >= 200 && failure.status < 300);
          if (!uncertain) submittedValues = null;
          error = failure is ApiError
              ? failure.message
              : 'Saqlash yakunlanmadi. Qayta urinib ko‘ring.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => busy = false);
        if (!completed) queueDraft();
      }
    }
  }

  Future<void> pickDate(FieldSpec field) async {
    final first = field.firstDate ?? DateTime(2020);
    final last = field.lastDate ?? DateTime(2100);
    var initial =
        DateTime.tryParse(controllers[field.key]!.text) ?? DateTime.now();
    if (initial.isBefore(first)) initial = first;
    if (initial.isAfter(last)) initial = last;
    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: first,
      lastDate: last,
      helpText: field.label,
      cancelText: 'Qaytish',
      confirmText: 'Tanlash',
    );
    if (picked != null) {
      controllers[field.key]!.text = picked.toIso8601String().substring(0, 10);
    }
  }

  Widget fieldWidget(FieldSpec field) {
    if (field.kind == FieldKind.toggle) {
      return SwitchListTile.adaptive(
        contentPadding: EdgeInsets.zero,
        title: Text(field.label),
        subtitle: field.hint == null ? null : Text(field.hint!),
        value: values[field.key] == 'true',
        onChanged: busy || uncertain
            ? null
            : (value) {
                setState(() => values[field.key] = value.toString());
                queueDraft();
              },
      );
    }
    if (field.kind == FieldKind.select) {
      final options = {...field.options};
      final value = values[field.key];
      if (uncertain &&
          value != null &&
          value.isNotEmpty &&
          !options.containsKey(value)) {
        options[value] =
            text(widget.store.find('debts', value)?['title']).isEmpty
            ? value
            : text(widget.store.find('debts', value)?['title']);
      }
      return DropdownButtonFormField<String>(
        key: ValueKey('${field.key}:${values[field.key]}'),
        initialValue: options.containsKey(values[field.key])
            ? values[field.key]
            : null,
        isExpanded: true,
        decoration: InputDecoration(labelText: field.label),
        items: options.entries
            .map(
              (item) => DropdownMenuItem(
                value: item.key,
                child: Text(item.value, overflow: TextOverflow.ellipsis),
              ),
            )
            .toList(),
        onChanged: busy || uncertain
            ? null
            : (value) {
                setState(() => values[field.key] = value ?? '');
                queueDraft();
              },
        validator: (value) => validate(field, value),
      );
    }
    return TextFormField(
      controller: controllers[field.key],
      enabled: !busy && !uncertain,
      readOnly: field.kind == FieldKind.date,
      onTap: field.kind == FieldKind.date ? () => pickDate(field) : null,
      obscureText: field.kind == FieldKind.password,
      autocorrect:
          field.kind == FieldKind.text || field.kind == FieldKind.multiline,
      enableSuggestions: field.kind != FieldKind.password,
      maxLength: field.maxLength,
      maxLines: field.kind == FieldKind.multiline ? 3 : 1,
      keyboardType: switch (field.kind) {
        FieldKind.phone => TextInputType.phone,
        FieldKind.money => const TextInputType.numberWithOptions(decimal: true),
        FieldKind.multiline => TextInputType.multiline,
        _ => TextInputType.text,
      },
      textInputAction: field.kind == FieldKind.multiline
          ? TextInputAction.newline
          : TextInputAction.next,
      decoration: InputDecoration(
        labelText: field.label,
        helperText: field.hint,
        counterText: '',
        suffixIcon: field.kind == FieldKind.date
            ? const Icon(Icons.calendar_today_outlined, size: 20)
            : null,
        suffixText: field.kind == FieldKind.money ? 'so‘m' : null,
      ),
      validator: (value) => validate(field, value),
    );
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    onPopInvokedWithResult: (didPop, result) {
      if (didPop && uncertain) widget.store.refresh();
    },
    child: Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Form(
              key: formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (widget.description != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 24),
                      child: Text(
                        widget.description!,
                        style: const TextStyle(
                          color: Palette.muted,
                          height: 1.6,
                        ),
                      ),
                    ),
                  if (uncertain)
                    const Padding(
                      padding: EdgeInsets.only(bottom: 18),
                      child: Text(
                        'Amalning javobi kutilmoqda. Pastdagi tugma orqali shu amalni qayta yuboring. Ma’lumotlarni tekshirish uchun mijoz kartasiga qaytishingiz mumkin.',
                        style: TextStyle(color: Palette.amber, height: 1.5),
                      ),
                    ),
                  if (restored)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 16),
                      child: Row(
                        children: [
                          const Expanded(
                            child: Text(
                              'Saqlangan qoralama tiklandi',
                              style: TextStyle(color: Palette.teal),
                            ),
                          ),
                          TextButton(
                            onPressed: busy || uncertain
                                ? null
                                : () {
                                    for (final field in widget.fields) {
                                      controllers[field.key]!.text =
                                          field.initial;
                                      values[field.key] = field.initial;
                                    }
                                    setState(() => restored = false);
                                  },
                            child: const Text('Tozalash'),
                          ),
                        ],
                      ),
                    ),
                  for (final field in widget.fields)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 18),
                      child: fieldWidget(field),
                    ),
                  if (error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 20),
                      child: Text(
                        error!,
                        style: const TextStyle(color: Palette.red, height: 1.5),
                      ),
                    ),
                  FilledButton(
                    onPressed: busy ? null : save,
                    child: busy
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : Text(widget.button),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );

  @override
  void dispose() {
    draftTimer?.cancel();
    for (final controller in controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }
}

Future<bool> customerForm(
  BuildContext context,
  AppStore store, {
  Json? customer,
}) => editForm(
  context,
  store,
  title: customer == null ? 'Yangi mijoz' : 'Mijozni tahrirlash',
  draftKey: customer == null ? 'customer' : null,
  fields: [
    FieldSpec('name', 'Mijozning ismi', initial: text(customer?['name'])),
    FieldSpec(
      'phone',
      'Telefon raqami',
      kind: FieldKind.phone,
      initial: text(customer?['phone']).isEmpty
          ? '+998'
          : text(customer?['phone']),
      maxLength: 24,
    ),
    FieldSpec(
      'company',
      'Korxona yoki do‘kon',
      required: false,
      initial: text(customer?['company']),
    ),
    FieldSpec(
      'note',
      'Izoh',
      kind: FieldKind.multiline,
      required: false,
      initial: text(customer?['note']),
      maxLength: 2000,
    ),
    FieldSpec(
      'contact_allowed',
      'Eslatma uchun bog‘lanishga rozilik',
      kind: FieldKind.toggle,
      initial: customer == null || integer(customer['contact_allowed']) == 1
          ? 'true'
          : 'false',
      hint: 'Mijozning roziligiga muvofiq belgilang.',
    ),
  ],
  submit: (values, id) async {
    await store.mutate(
      customer == null ? '/api/customers' : '/api/customers/${customer['id']}',
      values,
      method: customer == null ? 'POST' : 'PATCH',
      operationId: id,
    );
  },
);

Map<String, String> availableDebts(
  AppStore store,
  String customerId, {
  String? include,
}) => {
  for (final debt
      in store
          .rows('debts')
          .where(
            (debt) =>
                debt['customer_id'] == customerId &&
                (debt['id'] == include ||
                    (integer(debt['balance']) > 0 &&
                        integer(debt['archived']) == 0)),
          ))
    text(debt['id']): '${debt['title']} · ${formatMoney(debt['balance'])}',
};

Future<bool> debtForm(
  BuildContext context,
  AppStore store,
  String customerId, {
  Json? debt,
}) => editForm(
  context,
  store,
  title: debt == null ? 'Nasiya qo‘shish' : 'Nasiyani tahrirlash',
  draftKey: debt == null ? 'debt:$customerId' : null,
  description: debt == null
      ? 'Savdo summasi va kelishilgan to‘lov muddatini kiriting.'
      : 'O‘zgarishlar faoliyat tarixiga yoziladi. Summa o‘zgarsa, sababini kiriting.',
  fields: [
    FieldSpec(
      'title',
      'Nasiya nomi',
      initial: text(debt?['title']),
      maxLength: 160,
    ),
    FieldSpec(
      'amount',
      'Nasiya summasi',
      kind: FieldKind.money,
      initial: debt == null ? '' : inputMoney(debt['amount']),
      maxLength: 30,
    ),
    FieldSpec(
      'issued_on',
      'Berilgan sana',
      kind: FieldKind.date,
      initial: text(debt?['issued_on']).isEmpty
          ? store.currentDay
          : text(debt?['issued_on']),
      lastDate: DateTime.parse(store.currentDay),
    ),
    FieldSpec(
      'due_on',
      'To‘lov muddati',
      kind: FieldKind.date,
      initial: text(debt?['due_on']).isEmpty
          ? store.currentDay
          : text(debt?['due_on']),
    ),
    FieldSpec(
      'reference',
      'Hisob-faktura raqami',
      required: false,
      initial: text(debt?['reference']),
      maxLength: 100,
    ),
    FieldSpec(
      'note',
      'Izoh',
      kind: FieldKind.multiline,
      required: false,
      initial: text(debt?['note']),
      maxLength: 2000,
    ),
    if (debt != null)
      const FieldSpec(
        'reason',
        'O‘zgartirish sababi',
        required: false,
        maxLength: 500,
      ),
  ],
  submit: (values, id) async {
    values['customer_id'] = customerId;
    if (debt != null) values['version'] = debt['version'];
    await store.mutate(
      debt == null ? '/api/debts' : '/api/debts/${debt['id']}',
      values,
      method: debt == null ? 'POST' : 'PATCH',
      operationId: id,
    );
  },
);

Future<bool> paymentForm(
  BuildContext context,
  AppStore store,
  String customerId, {
  Json? debt,
}) async {
  final options = availableDebts(store, customerId);
  if (options.isEmpty) {
    feedbackMessage(context, 'Bu mijozning ochiq nasiya qoldig‘i yo‘q.');
    return false;
  }
  return editForm(
    context,
    store,
    title: 'To‘lovni qayd etish',
    description: 'Qabul qilingan haqiqiy to‘lovni kiriting. Qoldiq va to‘lov va’dalari avtomatik yangilanadi.',
    draftKey: 'payment:$customerId',
    button: 'To‘lovni saqlash',
    fields: [
      FieldSpec(
        'debt_id',
        'Qaysi nasiya uchun',
        kind: FieldKind.select,
        options: options,
        initial: text(debt?['id']).isEmpty
            ? options.keys.first
            : text(debt?['id']),
      ),
      FieldSpec(
        'amount',
        'Qabul qilingan summa',
        kind: FieldKind.money,
        initial: debt == null ? '' : inputMoney(debt['balance']),
        maxLength: 30,
      ),
      FieldSpec(
        'paid_on',
        'To‘lov sanasi',
        kind: FieldKind.date,
        initial: store.currentDay,
        lastDate: DateTime.parse(store.currentDay),
      ),
      const FieldSpec(
        'method',
        'To‘lov usuli',
        kind: FieldKind.select,
        initial: 'cash',
        options: {
          'cash': 'Naqd',
          'transfer': 'Bank o‘tkazmasi',
          'terminal': 'Terminal',
          'other': 'Boshqa',
        },
      ),
      const FieldSpec(
        'note',
        'Izoh yoki tasdiq raqami',
        kind: FieldKind.multiline,
        required: false,
        maxLength: 2000,
      ),
    ],
    submit: (values, id) async {
      await store.mutate('/api/payments', values, operationId: id);
    },
  );
}

Future<bool> promiseForm(
  BuildContext context,
  AppStore store,
  String customerId, {
  Json? debt,
  Json? promise,
}) async {
  final options = availableDebts(
    store,
    customerId,
    include: text(promise?['debt_id']),
  );
  if (options.isEmpty) {
    feedbackMessage(context, 'Va’da kiritish uchun ochiq nasiya kerak.');
    return false;
  }
  return editForm(
    context,
    store,
    title: promise == null ? 'To‘lov va’dasi' : 'Va’dani tahrirlash',
    draftKey: promise == null ? 'promise:$customerId' : null,
    description: 'Mijoz aytgan summa va sanani qayd eting. Qabul qilingan to‘lov va’daga avtomatik taqsimlanadi.',
    fields: [
      FieldSpec(
        'debt_id',
        'Nasiya',
        kind: FieldKind.select,
        options: promise == null
            ? options
            : {
                text(promise['debt_id']):
                    options[text(promise['debt_id'])] ?? 'Nasiya',
              },
        initial: text(promise?['debt_id'] ?? debt?['id']).isEmpty
            ? options.keys.first
            : text(promise?['debt_id'] ?? debt?['id']),
      ),
      FieldSpec(
        'amount',
        'Va’da qilingan summa',
        kind: FieldKind.money,
        initial: promise == null ? '' : inputMoney(promise['amount']),
        maxLength: 30,
      ),
      FieldSpec(
        'due_on',
        'Va’da sanasi',
        kind: FieldKind.date,
        initial: text(promise?['due_on']).isEmpty
            ? store.currentDay
            : text(promise?['due_on']),
        firstDate: DateTime.parse(store.currentDay),
      ),
      FieldSpec(
        'note',
        'Suhbatdan izoh',
        kind: FieldKind.multiline,
        required: false,
        initial: text(promise?['note']),
        maxLength: 2000,
      ),
    ],
    submit: (values, id) async {
      if (promise != null) values['version'] = promise['version'];
      await store.mutate(
        promise == null ? '/api/promises' : '/api/promises/${promise['id']}',
        values,
        method: promise == null ? 'POST' : 'PATCH',
        operationId: id,
      );
    },
  );
}

Future<bool> refundForm(BuildContext context, AppStore store, Json payment) =>
    editForm(
      context,
      store,
      title: 'To‘lov qaytarimi',
      draftKey: 'refund:${payment['id']}',
      description: 'Qaytarim nasiya qoldig‘ini qayta ochadi va bog‘langan va’dalarni yangilaydi. Amal tarixda saqlanadi.',
      button: 'Qaytarimni tasdiqlash',
      fields: [
        FieldSpec(
          'amount',
          'Qaytariladigan summa',
          kind: FieldKind.money,
          initial: inputMoney(
            integer(payment['amount']) - integer(payment['refunded']),
          ),
          maxLength: 30,
        ),
        FieldSpec(
          'refunded_on',
          'Qaytarim sanasi',
          kind: FieldKind.date,
          initial: store.currentDay,
          firstDate: DateTime.parse(text(payment['paid_on'])),
          lastDate: DateTime.parse(store.currentDay),
        ),
        const FieldSpec(
          'reason',
          'Qaytarim sababi',
          kind: FieldKind.multiline,
          maxLength: 1000,
        ),
      ],
      submit: (values, id) async {
        await store.mutate(
          '/api/payments/${payment['id']}/refund',
          values,
          operationId: id,
        );
      },
    );

Future<bool> disputeForm(BuildContext context, AppStore store, Json debt) =>
    editForm(
      context,
      store,
      title: 'E’tirozni qayd etish',
      description: 'Mijozning nasiya bo‘yicha e’tirozini yozing. U hal etilguncha nasiya e’tirozli deb belgilanadi.',
      fields: [
        const FieldSpec(
          'reason',
          'E’tiroz mazmuni',
          kind: FieldKind.multiline,
          maxLength: 2000,
        ),
      ],
      submit: (values, id) async {
        values['debt_id'] = debt['id'];
        await store.mutate('/api/disputes', values, operationId: id);
      },
    );

Future<bool> resolveDisputeForm(
  BuildContext context,
  AppStore store,
  Json dispute,
) => editForm(
  context,
  store,
  title: 'E’tiroz yechimi',
  fields: [
    const FieldSpec(
      'resolution',
      'Kelishilgan yechim',
      kind: FieldKind.multiline,
      maxLength: 2000,
    ),
  ],
  submit: (values, id) async {
    values['version'] = dispute['version'];
    await store.mutate(
      '/api/disputes/${dispute['id']}/resolve',
      values,
      operationId: id,
    );
  },
);

Future<bool> noteForm(
  BuildContext context,
  AppStore store,
  String customerId,
) => editForm(
  context,
  store,
  title: 'Izoh qo‘shish',
  draftKey: 'note:$customerId',
  fields: [
    const FieldSpec(
      'text',
      'Suhbat yoki uchrashuvdan izoh',
      kind: FieldKind.multiline,
      maxLength: 3000,
    ),
  ],
  submit: (values, id) async {
    await store.mutate(
      '/api/customers/$customerId/notes',
      values,
      operationId: id,
    );
  },
);

Future<void> confirmedMutation(
  BuildContext context,
  AppStore store,
  String path,
  Json payload, {
  required String title,
  required String description,
}) async {
  if (!await confirm(context, title, description)) return;
  try {
    await store.mutate(path, payload);
    if (context.mounted) feedbackMessage(context, 'Saqlandi');
  } on ApiError catch (failure) {
    if (context.mounted) feedbackMessage(context, failure.message);
  }
}
