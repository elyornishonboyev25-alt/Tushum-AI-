import 'dart:async';

import 'package:material_ui/material_ui.dart';

import 'core.dart';
import 'ui.dart';
import 'forms.dart';
import 'customers.dart';
import 'insights.dart';
import 'settings.dart';
import 'spreadsheet_import.dart';
import 'voice.dart';
import 'voice_dashboard.dart';

class AuthPage extends StatefulWidget {
  const AuthPage({super.key, required this.store});
  final AppStore store;
  @override
  State<AuthPage> createState() => _AuthPageState();
}

class _AuthPageState extends State<AuthPage> {
  final form = GlobalKey<FormState>();
  final phone = TextEditingController(text: '+998');
  final password = TextEditingController();
  final name = TextEditingController();
  final business = TextEditingController();
  bool register = false;
  bool busy = false;
  bool showPassword = false;
  String? error;

  Future<void> authenticate({bool demo = false}) async {
    if (busy || (!demo && !form.currentState!.validate())) return;
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.store.authenticate(
        demo
            ? 'demo'
            : register
            ? 'register'
            : 'login',
        demo
            ? {}
            : {
                'phone': phone.text.trim(),
                'password': password.text,
                if (register) 'name': name.text.trim(),
                if (register) 'business_name': business.text.trim(),
              },
      );
    } on ApiError catch (failure) {
      if (mounted) setState(() => error = failure.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => error = 'Qurilmadagi sessiya saqlanmadi. Brauzer yoki qurilma sozlamalarini tekshiring.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> configureServer() async {
    await editForm(
      context,
      widget.store,
      title: 'Server manzili',
      description: 'Telefon va noutbuk bir Wi-Fi tarmog‘ida bo‘lsa, noutbukning mahalliy IP manzilini kiriting.',
      fields: [
        FieldSpec(
          'server',
          'Server manzili',
          initial: widget.store.api.baseUrl,
          maxLength: 250,
        ),
      ],
      submit: (values, _) => widget.store.setServer(text(values['server'])),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 430),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: Palette.teal,
                      borderRadius: BorderRadius.circular(15),
                    ),
                    child: const Icon(
                      Icons.south_west_rounded,
                      color: Colors.white,
                      size: 31,
                    ),
                  ),
                  const SizedBox(width: 12),
                  const Text(
                    'tushum',
                    style: TextStyle(
                      fontSize: 32,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -1,
                    ),
                  ),
                  const SizedBox(width: 6),
                  const StatusTag('AI', color: Palette.teal),
                ],
              ),
              const SizedBox(height: 36),
              Text(
                register ? 'Biznesingizni ulang' : 'Pul oqimi nazoratingizda',
                style: Theme.of(context).textTheme.headlineLarge,
              ),
              const SizedBox(height: 12),
              const Text(
                'Nasiyalar, to‘lovlar va kelishuvlar bir joyda.',
                style: TextStyle(
                  color: Palette.muted,
                  fontSize: 16,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 28),
              Form(
                key: form,
                child: Column(
                  children: [
                    if (register) ...[
                      TextFormField(
                        controller: name,
                        enabled: !busy,
                        decoration: const InputDecoration(
                          labelText: 'Ismingiz',
                        ),
                        maxLength: 100,
                        validator: (value) => (value?.trim().length ?? 0) < 2
                            ? 'Ismingizni kiriting'
                            : null,
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: business,
                        enabled: !busy,
                        decoration: const InputDecoration(
                          labelText: 'Biznes nomi',
                        ),
                        maxLength: 120,
                        validator: (value) => (value?.trim().length ?? 0) < 2
                            ? 'Biznes nomini kiriting'
                            : null,
                      ),
                      const SizedBox(height: 12),
                    ],
                    TextFormField(
                      controller: phone,
                      enabled: !busy,
                      keyboardType: TextInputType.phone,
                      autofillHints: const [AutofillHints.telephoneNumber],
                      decoration: const InputDecoration(
                        labelText: 'Telefon raqami',
                        prefixIcon: Icon(Icons.phone_outlined),
                      ),
                      validator: (value) =>
                          RegExp(r'^(?:\+?998)?\d{9}$').hasMatch(
                            (value ?? '').replaceAll(RegExp(r'[\s()\-]'), ''),
                          )
                          ? null
                          : 'Raqamni kiriting, +998901234567',
                    ),
                    const SizedBox(height: 18),
                    TextFormField(
                      controller: password,
                      enabled: !busy,
                      obscureText: !showPassword,
                      enableSuggestions: false,
                      autocorrect: false,
                      autofillHints: [
                        register
                            ? AutofillHints.newPassword
                            : AutofillHints.password,
                      ],
                      decoration: InputDecoration(
                        labelText: 'Parol',
                        helperText: register ? 'Kamida 8 ta belgi' : null,
                        prefixIcon: const Icon(Icons.lock_outline),
                        suffixIcon: IconButton(
                          tooltip: showPassword
                              ? 'Parolni yashirish'
                              : 'Parolni ko‘rish',
                          onPressed: () =>
                              setState(() => showPassword = !showPassword),
                          icon: Icon(
                            showPassword
                                ? Icons.visibility_off_outlined
                                : Icons.visibility_outlined,
                          ),
                        ),
                      ),
                      validator: (value) => (value?.length ?? 0) < 8
                          ? 'Kamida 8 ta belgi kiriting'
                          : null,
                      onFieldSubmitted: (_) => authenticate(),
                    ),
                  ],
                ),
              ),
              if (error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 18),
                  child: Text(
                    error!,
                    style: const TextStyle(color: Palette.red),
                  ),
                ),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: busy ? null : () => authenticate(),
                child: busy
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(register ? 'Hisob yaratish' : 'Kirish'),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: busy
                    ? null
                    : () => setState(() {
                        register = !register;
                        error = null;
                      }),
                child: Text(
                  register
                      ? 'Hisobim bor — kirish'
                      : 'Yangi biznes uchun ro‘yxatdan o‘tish',
                ),
              ),
              const SizedBox(height: 20),
              const Divider(),
              const SizedBox(height: 20),
              OutlinedButton.icon(
                onPressed: busy ? null : () => authenticate(demo: true),
                icon: const Icon(Icons.play_circle_outline),
                label: const Text('Demo ma’lumotlar bilan sinash'),
              ),
              const SizedBox(height: 8),
              TextButton.icon(
                onPressed: busy ? null : configureServer,
                icon: const Icon(Icons.dns_outlined, size: 18),
                label: const Text('Ulanish sozlamalari'),
              ),
            ],
          ),
        ),
      ),
    ),
  );

  @override
  void dispose() {
    phone.dispose();
    password.dispose();
    name.dispose();
    business.dispose();
    super.dispose();
  }
}

class AppShell extends StatefulWidget {
  const AppShell({
    super.key,
    required this.store,
    this.openVoiceOnStart = false,
  });
  final AppStore store;
  final bool openVoiceOnStart;
  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> with WidgetsBindingObserver {
  int selected = 0;
  Timer? refreshTimer;
  static const labels = [
    'Bugun',
    'Mijozlar',
    'Va’dalar',
    'Faoliyat',
    'Hisobot',
  ];
  static const icons = [
    Icons.space_dashboard_outlined,
    Icons.people_outline,
    Icons.event_available_outlined,
    Icons.receipt_long_outlined,
    Icons.bar_chart_rounded,
  ];
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    if (widget.openVoiceOnStart) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => VoicePage(store: widget.store)),
          );
        }
      });
    }
    refreshTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      if (mounted && ModalRoute.of(context)?.isCurrent == true) {
        widget.store.refresh();
      }
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) widget.store.refresh();
  }

  @override
  void dispose() {
    refreshTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  void selectTab(int index) {
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() => selected = index);
  }

  void openSettings() {
    FocusManager.instance.primaryFocus?.unfocus();
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => SettingsPage(store: widget.store)),
    );
  }

  void openNotifications() {
    FocusManager.instance.primaryFocus?.unfocus();
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => NotificationsPage(store: widget.store)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final store = widget.store;
    final wide = MediaQuery.sizeOf(context).width >= 900;
    final unread = store
        .rows('notifications')
        .where((item) => item['read'] != true)
        .length;
    final pages = [
      HomePage(store: store, showCustomers: () => selectTab(1)),
      CustomersPage(store: store),
      PromisesPage(store: store),
      ActivityPage(store: store),
      ReportsPage(store: store),
    ];
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.south_west_rounded, color: Palette.teal),
            const SizedBox(width: 8),
            const Text(
              'tushum',
              style: TextStyle(fontWeight: FontWeight.w700, letterSpacing: -.7),
            ),
            if (integer(store.business['is_demo']) == 1)
              const Padding(
                padding: EdgeInsets.only(left: 12),
                child: StatusTag('Demo', color: Palette.teal),
              ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'AI suhbatlar',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => VoicePage(store: store)),
            ),
            icon: const Icon(Icons.headset_mic_outlined),
          ),
          IconButton(
            tooltip: 'Yangilash',
            onPressed: store.refreshing ? null : store.refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
          Badge(
            isLabelVisible: unread > 0,
            label: Text('$unread'),
            child: IconButton(
              tooltip: 'Bildirishnomalar',
              onPressed: openNotifications,
              icon: const Icon(Icons.notifications_none_rounded),
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(right: 12, left: 8),
            child: IconButton(
              tooltip: 'Sozlamalar',
              onPressed: openSettings,
              icon: PersonAvatar(text(store.me['name']), size: 34),
            ),
          ),
        ],
      ),
      body: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (wide)
            Container(
              width: 220,
              decoration: const BoxDecoration(
                color: Colors.white,
                border: Border(right: BorderSide(color: Palette.line)),
              ),
              child: Material(
                color: Colors.white,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(22, 28, 20, 24),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            text(store.business['name']),
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 6),
                          Text(
                            roleLabel(text(store.me['role'])),
                            style: const TextStyle(color: Palette.muted),
                          ),
                        ],
                      ),
                    ),
                    for (var i = 0; i < labels.length; i++)
                      Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 3,
                        ),
                        child: ListTile(
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10),
                          ),
                          selected: selected == i,
                          selectedTileColor: Palette.soft,
                          selectedColor: Palette.teal,
                          leading: Icon(icons[i]),
                          title: Text(labels[i]),
                          onTap: () => selectTab(i),
                        ),
                      ),
                    const Spacer(),
                    ListTile(
                      leading: const Icon(
                        Icons.headset_mic_outlined,
                        color: Palette.teal,
                      ),
                      title: const Text('AI suhbatlar'),
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => VoicePage(store: store),
                        ),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: ListTile(
                        leading: const Icon(Icons.settings_outlined),
                        title: const Text('Sozlamalar'),
                        onTap: openSettings,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          Expanded(
            child: Column(
              children: [
                if (store.refreshing)
                  const LinearProgressIndicator(minHeight: 2),
                if (store.error != null)
                  Container(
                    width: double.infinity,
                    color: const Color(0xFFFFF3DE),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 20,
                      vertical: 10,
                    ),
                    child: Text(
                      store.offline
                          ? 'Oflayn rejim. Oxirgi saqlangan ma’lumotlar ko‘rsatilmoqda. ${store.error}'
                          : store.error!,
                      style: const TextStyle(
                        color: Palette.amber,
                        fontSize: 13,
                      ),
                    ),
                  ),
                Expanded(
                  child: KeyedSubtree(
                    key: ValueKey(selected),
                    child: pages[selected],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: wide
          ? null
          : NavigationBar(
              selectedIndex: selected,
              onDestinationSelected: selectTab,
              destinations: [
                for (var i = 0; i < labels.length; i++)
                  NavigationDestination(icon: Icon(icons[i]), label: labels[i]),
              ],
            ),
    );
  }
}

class ContentList extends StatelessWidget {
  const ContentList({super.key, required this.children, this.onRefresh});
  final List<Widget> children;
  final Future<void> Function()? onRefresh;
  @override
  Widget build(BuildContext context) {
    final scroll = ListView(
      padding: EdgeInsets.fromLTRB(
        MediaQuery.sizeOf(context).width < 500 ? 18 : 32,
        28,
        MediaQuery.sizeOf(context).width < 500 ? 18 : 32,
        36,
      ),
      children: children,
    );
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1140),
        child: onRefresh == null
            ? scroll
            : RefreshIndicator(onRefresh: onRefresh!, child: scroll),
      ),
    );
  }
}

class HomePage extends StatelessWidget {
  const HomePage({super.key, required this.store, required this.showCustomers});
  final AppStore store;
  final VoidCallback showCustomers;
  @override
  Widget build(BuildContext context) {
    final customers = store
        .rows('customers')
        .where((row) => integer(row['archived']) == 0)
        .toList();
    final debts = store.rows('debts');
    final balance = debts.fold<int>(
      0,
      (sum, row) => sum + integer(row['balance']),
    );
    final overdue = debts
        .where((row) => row['overdue'] == true)
        .fold<int>(0, (sum, row) => sum + integer(row['balance']));
    final month = store.currentDay.substring(0, 7);
    final gross = store
        .rows('payments')
        .where((row) => text(row['paid_on']).startsWith(month))
        .fold<int>(0, (sum, row) => sum + integer(row['amount']));
    final refunds = store
        .rows('refunds')
        .where((row) => text(row['refunded_on']).startsWith(month))
        .fold<int>(0, (sum, row) => sum + integer(row['amount']));
    final tasks = store.rows('notifications');
    customers.sort(
      (a, b) => integer(b['balance']).compareTo(integer(a['balance'])),
    );
    return ContentList(
      onRefresh: () async {
        await store.refresh();
      },
      children: [
        Text(
          'Assalomu alaykum, ${text(store.me['name']).split(' ').first}',
          style: const TextStyle(color: Palette.muted, fontSize: 14),
        ),
        const SizedBox(height: 6),
        Text(
          'Bugungi nazorat',
          style: Theme.of(context).textTheme.headlineLarge,
        ),
        const SizedBox(height: 6),
        Text(
          '${displayDate(store.currentDay)} · ${text(store.business['name'])}',
          style: const TextStyle(color: Palette.muted),
        ),
        const SizedBox(height: 18),
        Surface(
          color: Palette.soft,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Row(
                children: [
                  Icon(Icons.headset_mic_outlined, color: Palette.teal),
                  SizedBox(width: 10),
                  Text(
                    'AI suhbatlar',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text(
                'Telegram qo‘ng‘iroqlari va mijoz bilan kelishuvlar.',
                style: TextStyle(color: Palette.muted),
              ),
              const SizedBox(height: 14),
              FilledButton.icon(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => VoicePage(store: store)),
                ),
                icon: const Icon(Icons.arrow_forward),
                label: const Text('AI suhbatlarni ochish'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        VoiceDashboard(
          store: store,
          openCall: (id) => Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => VoicePage(store: store, initialCallId: id),
            ),
          ),
        ),
        Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: Palette.teal,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Jami nasiya qoldig‘i',
                style: TextStyle(color: Color(0xFFCBDFDF), fontSize: 14),
              ),
              const SizedBox(height: 10),
              FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  formatMoney(balance),
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 36,
                    fontWeight: FontWeight.w700,
                    letterSpacing: -1.2,
                  ),
                ),
              ),
              const SizedBox(height: 22),
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Shu oy sof tushum',
                          style: TextStyle(
                            color: Color(0xFFCBDFDF),
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(height: 5),
                        FittedBox(
                          child: Text(
                            formatMoney(gross - refunds),
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w700,
                              fontSize: 18,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    height: 36,
                    width: 1,
                    color: Colors.white24,
                    margin: const EdgeInsets.symmetric(horizontal: 20),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Muddati o‘tgan',
                          style: TextStyle(
                            color: Color(0xFFCBDFDF),
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(height: 5),
                        FittedBox(
                          child: Text(
                            formatMoney(overdue),
                            style: const TextStyle(
                              color: Color(0xFFFFD7AB),
                              fontWeight: FontWeight.w700,
                              fontSize: 18,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        if (store.canEdit)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Wrap(
              spacing: 12,
              runSpacing: 10,
              children: [
                FilledButton.icon(
                  onPressed: () => customerForm(context, store),
                  icon: const Icon(Icons.person_add_alt_1_outlined, size: 20),
                  label: const Text('Mijoz qo‘shish'),
                ),
                OutlinedButton.icon(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => SpreadsheetImportPage(store: store),
                    ),
                  ),
                  icon: const Icon(Icons.upload_file_outlined, size: 20),
                  label: const Text('Excel import'),
                ),
                OutlinedButton.icon(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => VoicePage(store: store)),
                  ),
                  icon: const Icon(Icons.headset_mic_outlined, size: 20),
                  label: const Text('AI suhbat'),
                ),
              ],
            ),
          ),
        SectionHeader(
          'E’tibor talab qiladi',
          action: Text(
            '${tasks.length} ta',
            style: const TextStyle(color: Palette.muted),
          ),
        ),
        Surface(
          padding: EdgeInsets.zero,
          child: tasks.isEmpty
              ? const EmptyState(
                  title: 'Bugungi ishlar tartibda',
                  message:
                      'Muddati kelgan nasiya va va’dalar shu yerda ko‘rinadi.',
                  icon: Icons.task_alt,
                )
              : Column(
                  children: [
                    for (final task in tasks.take(6))
                      TaskRow(
                        task: task,
                        onTap: () => openCustomer(
                          context,
                          store,
                          text(task['customer_id']),
                        ),
                      ),
                  ],
                ),
        ),
        SectionHeader(
          'Mijozlar',
          action: TextButton(
            onPressed: showCustomers,
            child: const Text('Barchasi'),
          ),
        ),
        Surface(
          padding: EdgeInsets.zero,
          child: customers.isEmpty
              ? EmptyState(
                  title: 'Birinchi mijozingizni qo‘shing',
                  message:
                      'Nasiya va to‘lovlarni mijoz kartasidan boshqarasiz.',
                  icon: Icons.people_outline,
                  action: store.canEdit
                      ? OutlinedButton(
                          onPressed: () => customerForm(context, store),
                          child: const Text('Mijoz qo‘shish'),
                        )
                      : null,
                )
              : Column(
                  children: [
                    for (final customer in customers.take(4))
                      CustomerRow(
                        customer: customer,
                        onTap: () =>
                            openCustomer(context, store, text(customer['id'])),
                      ),
                  ],
                ),
        ),
        const SectionHeader('So‘nggi amallar'),
        Surface(
          padding: EdgeInsets.zero,
          child: store.rows('events').isEmpty
              ? const EmptyState(
                  title: 'Faoliyat tarixi',
                  message: 'Kiritilgan amallar avtomatik qayd etiladi.',
                )
              : Column(
                  children: [
                    for (final item in store.rows('events').take(4))
                      ActivityRow(
                        item,
                        onTap: text(item['customer_id']).isEmpty
                            ? null
                            : () => openCustomer(
                                context,
                                store,
                                text(item['customer_id']),
                              ),
                      ),
                  ],
                ),
        ),
      ],
    );
  }
}

class TaskRow extends StatelessWidget {
  const TaskRow({super.key, required this.task, required this.onTap});
  final Json task;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => ListTile(
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 7),
    leading: CircleAvatar(
      backgroundColor: task['kind'] == 'promise'
          ? const Color(0xFFFFF1DE)
          : Palette.soft,
      foregroundColor: task['kind'] == 'promise' ? Palette.amber : Palette.teal,
      child: Icon(
        task['kind'] == 'promise'
            ? Icons.event_available_outlined
            : task['kind'] == 'dispute'
            ? Icons.help_outline
            : Icons.schedule_outlined,
      ),
    ),
    title: Text(
      text(task['customer_name']),
      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
    ),
    subtitle: Text(
      '${task['title']}\n${displayDate(task['date'])}',
      style: const TextStyle(color: Palette.muted, fontSize: 12, height: 1.6),
    ),
    trailing: Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Text(
          formatMoney(task['amount'], unit: false),
          style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
        ),
        const Text(
          'so‘m',
          style: TextStyle(color: Palette.muted, fontSize: 12),
        ),
      ],
    ),
    onTap: onTap,
  );
}

class NotificationsPage extends StatelessWidget {
  const NotificationsPage({super.key, required this.store});
  final AppStore store;
  Future<void> markRead(BuildContext context) async {
    try {
      final keys = store
          .rows('notifications')
          .where((row) => row['read'] != true)
          .map((row) => row['key'])
          .toList();
      for (var start = 0; start < keys.length; start += 500) {
        final end = start + 500 < keys.length ? start + 500 : keys.length;
        await store.api.request(
          '/api/notifications/read',
          method: 'POST',
          body: {'keys': keys.sublist(start, end)},
        );
      }
      await store.refresh();
    } on ApiError catch (failure) {
      if (context.mounted) feedbackMessage(context, failure.message);
      await store.refresh();
    }
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: store,
    builder: (context, _) => Scaffold(
      appBar: AppBar(
        title: const Text('Bildirishnomalar'),
        actions: [
          TextButton(
            onPressed: store.offline ? null : () => markRead(context),
            child: const Text('O‘qildi'),
          ),
        ],
      ),
      body: ContentList(
        children: [
          if (store.rows('notifications').isEmpty)
            const EmptyState(
              title: 'Bildirishnoma yo‘q',
              message: 'To‘lov muddatlari va e’tirozlar shu yerda jamlanadi.',
              icon: Icons.notifications_none_outlined,
            ),
          for (final task in store.rows('notifications'))
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Surface(
                color: task['read'] == true
                    ? Colors.white
                    : const Color(0xFFF0F7F6),
                padding: EdgeInsets.zero,
                child: TaskRow(
                  task: task,
                  onTap: () =>
                      openCustomer(context, store, text(task['customer_id'])),
                ),
              ),
            ),
        ],
      ),
    ),
  );
}
