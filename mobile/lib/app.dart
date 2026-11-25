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
import 'executive_dashboard.dart';

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
              const Align(
                alignment: Alignment.centerLeft,
                child: TushumBrand(),
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
    final compact = MediaQuery.sizeOf(context).width < 600;
    final unread = store
        .rows('notifications')
        .where((n) => n['read'] != true)
        .length;
    final pages = [
      HomePage(store: store, showCustomers: () => selectTab(1)),
      CustomersPage(store: store),
      PromisesPage(store: store),
      ActivityPage(store: store),
      ReportsPage(store: store),
    ];
    void voice() => Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => VoicePage(store: store)),
    );
    void upload() => Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => SpreadsheetImportPage(store: store)),
    );
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 74,
        titleSpacing: compact ? 16 : 24,
        shape: const Border(bottom: BorderSide(color: Palette.line)),
        title: Row(
          children: [
            TushumBrand(compact: compact),
            SizedBox(width: compact ? 12 : 40),
            if (!compact) Container(width: 1, height: 25, color: Palette.line),
            if (!compact) const SizedBox(width: 20),
            Flexible(
              child: PopupMenuButton<String>(
                tooltip: 'Biznesni tanlash',
                onSelected: (value) {
                  if (value == 'settings') openSettings();
                },
                itemBuilder: (_) => [
                  PopupMenuItem(
                    value: 'current',
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.check, size: 18, color: Palette.teal),
                        const SizedBox(width: 10),
                        Flexible(child: Text(text(store.business['name']))),
                      ],
                    ),
                  ),
                  const PopupMenuItem(
                    value: 'settings',
                    child: Text('Biznes sozlamalari'),
                  ),
                ],
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (!compact) ...[
                      Container(
                        width: 29,
                        height: 29,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: Palette.line,
                          borderRadius: BorderRadius.circular(7),
                        ),
                        child: Text(
                          initials(text(store.business['name'])),
                          style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                    ],
                    Flexible(
                      child: Text(
                        text(store.business['name']),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: compact ? 12 : 13,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                    const SizedBox(width: 7),
                    const Icon(
                      Icons.keyboard_arrow_down_rounded,
                      size: 17,
                      color: Palette.muted,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
        actions: [
          if (compact)
            IconButton(
              tooltip: 'Excel yuklash',
              onPressed: store.canEdit ? upload : null,
              icon: const Icon(Icons.upload_file_outlined, color: Palette.teal),
            )
          else
            Padding(
              padding: const EdgeInsets.only(right: 18),
              child: FilledButton.icon(
                onPressed: store.canEdit ? upload : null,
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Excel yuklash'),
              ),
            ),
          if (!compact)
            IconButton(
              tooltip: 'Yangilash',
              onPressed: store.refreshing ? null : store.refresh,
              icon: const Icon(Icons.refresh_rounded, size: 20),
            ),
          Badge(
            isLabelVisible: unread > 0,
            label: Text('$unread'),
            child: IconButton(
              tooltip: 'Bildirishnomalar',
              onPressed: openNotifications,
              icon: const Icon(Icons.notifications_none_rounded, size: 21),
            ),
          ),
          Padding(
            padding: EdgeInsets.only(
              right: compact ? 8 : 18,
              left: compact ? 0 : 8,
            ),
            child: IconButton(
              tooltip: 'Sozlamalar',
              onPressed: openSettings,
              icon: PersonAvatar(text(store.me['name']), size: 30),
            ),
          ),
        ],
      ),
      body: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (wide)
            Container(
              width: 208,
              decoration: const BoxDecoration(
                color: Palette.background,
                border: Border(right: BorderSide(color: Palette.line)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Padding(
                    padding: EdgeInsets.fromLTRB(24, 28, 20, 14),
                    child: Text(
                      'ISH MAYDONI',
                      style: TextStyle(
                        fontSize: 9.5,
                        color: Palette.muted,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 1.3,
                      ),
                    ),
                  ),
                  for (var i = 0; i < labels.length; i++)
                    Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 3,
                      ),
                      child: ListTile(
                        dense: true,
                        minLeadingWidth: 22,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                        selected: selected == i,
                        selectedTileColor: Palette.soft,
                        selectedColor: Palette.teal,
                        iconColor: Palette.muted,
                        textColor: Palette.muted,
                        leading: Icon(icons[i], size: 20),
                        title: Text(
                          i == 0 ? 'Boshqaruv paneli' : labels[i],
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        onTap: () => selectTab(i),
                      ),
                    ),
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 22, vertical: 18),
                    child: Divider(),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: ListTile(
                      dense: true,
                      minLeadingWidth: 22,
                      leading: const Icon(
                        Icons.headset_mic_outlined,
                        size: 20,
                        color: Palette.blue,
                      ),
                      title: const Text(
                        'AI suhbatlar',
                        style: TextStyle(fontSize: 12),
                      ),
                      trailing: const Icon(
                        Icons.arrow_outward,
                        size: 13,
                        color: Palette.muted,
                      ),
                      onTap: voice,
                    ),
                  ),
                  const Spacer(),
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Palette.surface,
                        border: Border.all(color: Palette.line),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              const Icon(
                                Icons.verified_user_outlined,
                                color: Palette.teal,
                                size: 15,
                              ),
                              const SizedBox(width: 7),
                              Text(
                                store.business['is_demo'] == 1
                                    ? 'Demo ish maydoni'
                                    : 'Biznes ish maydoni',
                                style: const TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 7),
                          Text(
                            roleLabel(text(store.me['role'])),
                            style: const TextStyle(
                              color: Palette.muted,
                              fontSize: 10.5,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(12, 0, 12, 14),
                    child: ListTile(
                      dense: true,
                      minLeadingWidth: 22,
                      leading: const Icon(
                        Icons.settings_outlined,
                        size: 19,
                        color: Palette.muted,
                      ),
                      title: const Text(
                        'Sozlamalar',
                        style: TextStyle(fontSize: 12, color: Palette.muted),
                      ),
                      onTap: openSettings,
                    ),
                  ),
                ],
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
                    color: Palette.warningSoft,
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
                        fontSize: 12,
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
                  NavigationDestination(
                    icon: Icon(icons[i], size: 21),
                    label: labels[i],
                  ),
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
  Widget build(BuildContext context) =>
      ExecutiveDashboard(store: store, showCustomers: showCustomers);
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
          ? Palette.warningSoft
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
                color: task['read'] == true ? Palette.surface : Palette.soft,
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
