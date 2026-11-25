import 'package:material_ui/material_ui.dart';

import 'core.dart';
import 'ui.dart';
import 'forms.dart';
import 'app.dart' show ContentList;
import 'sms.dart';

String roleLabel(String role) => switch (role) {
  'owner' => 'Biznes egasi',
  'manager' => 'Menejer',
  _ => 'Kuzatuvchi',
};

Future<void> downloadFile(
  BuildContext context,
  AppStore store,
  String path,
  String filename,
) async {
  try {
    final saved = await store.saveFile(path, filename);
    if (context.mounted && saved) feedbackMessage(context, 'Fayl yuklandi');
  } on ApiError catch (failure) {
    if (context.mounted) feedbackMessage(context, failure.message);
  } catch (_) {
    if (context.mounted) {
      feedbackMessage(
        context,
        'Fayl saqlanmadi. Qurilmadagi ruxsatlarni tekshiring.',
      );
    }
  }
}

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key, required this.store});
  final AppStore store;
  Future<void> editBusiness(BuildContext context) async {
    final business = store.business;
    await editForm(
      context,
      store,
      title: 'Biznes ma’lumotlari',
      fields: [
        FieldSpec('name', 'Biznes nomi', initial: text(business['name'])),
        FieldSpec(
          'phone',
          'Biznes telefoni',
          kind: FieldKind.phone,
          initial: text(business['phone']),
          maxLength: 24,
        ),
        FieldSpec(
          'sector',
          'Faoliyat sohasi',
          required: false,
          initial: text(business['sector']),
        ),
        FieldSpec(
          'address',
          'Manzil',
          kind: FieldKind.multiline,
          required: false,
          initial: text(business['address']),
          maxLength: 300,
        ),
      ],
      submit: (values, id) async {
        await store.mutate(
          '/api/business',
          values,
          method: 'PATCH',
          operationId: id,
        );
      },
    );
  }

  Future<void> changePassword(BuildContext context) async {
    await editForm(
      context,
      store,
      title: 'Parolni almashtirish',
      description:
          'Parol yangilangach, boshqa qurilmalardagi sessiyalar yakunlanadi.',
      fields: [
        const FieldSpec(
          'current_password',
          'Hozirgi parol',
          kind: FieldKind.password,
          maxLength: 128,
        ),
        const FieldSpec(
          'new_password',
          'Yangi parol',
          kind: FieldKind.password,
          maxLength: 128,
        ),
      ],
      submit: (values, id) async {
        await store.mutate('/api/auth/password', values, operationId: id);
      },
    );
  }

  Future<void> signOut(BuildContext context) async {
    if (!await confirm(
      context,
      'Hisobdan chiqish',
      'Bu qurilmadagi sessiya yakunlanadi. Davom etish uchun qayta kirishingiz mumkin.',
      action: 'Chiqish',
    )) {
      return;
    }
    if (!context.mounted) return;
    Navigator.popUntil(context, (route) => route.isFirst);
    await store.logout();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: store,
    builder: (context, _) => Scaffold(
      appBar: AppBar(title: const Text('Sozlamalar')),
      body: ContentList(
        children: [
          Surface(
            child: Row(
              children: [
                PersonAvatar(text(store.me['name']), size: 56),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        text(store.me['name']),
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 6),
                      Text(
                        text(store.me['phone']),
                        style: const TextStyle(color: Palette.muted),
                      ),
                      const SizedBox(height: 8),
                      StatusTag(
                        roleLabel(text(store.me['role'])),
                        color: Palette.teal,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SectionHeader('Biznes'),
          Surface(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                ListTile(
                  contentPadding: const EdgeInsets.all(18),
                  leading: const Icon(Icons.storefront_outlined),
                  title: Text(
                    text(store.business['name']),
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  subtitle: Text(
                    [
                      text(store.business['sector']),
                      text(store.business['address']),
                    ].where((item) => item.isNotEmpty).join('\n'),
                  ),
                  trailing: store.isOwner
                      ? const Icon(Icons.chevron_right)
                      : null,
                  onTap: store.isOwner && store.canEdit
                      ? () => editBusiness(context)
                      : null,
                ),
                if (store.isOwner)
                  ListTile(
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 18,
                      vertical: 8,
                    ),
                    leading: const Icon(Icons.group_outlined),
                    title: const Text('Jamoa va huquqlar'),
                    subtitle: const Text('Menejer va kuzatuvchi hisoblari'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: store.offline
                        ? null
                        : () => Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => TeamPage(store: store),
                            ),
                          ),
                  ),
              ],
            ),
          ),
          const SectionHeader('Ma’lumotlar'),
          Surface(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.file_download_outlined),
                  title: const Text('Excel hisobotni yuklash'),
                  subtitle: const Text(
                    'Mijozlar, nasiyalar, to‘lovlar va qaytarimlar',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: store.offline
                      ? null
                      : () => downloadFile(
                          context,
                          store,
                          '/api/export',
                          'tushum-hisobot-${store.currentDay}.xlsx',
                        ),
                ),
                if (store.isOwner)
                  ListTile(
                    leading: const Icon(Icons.data_object_outlined),
                    title: const Text('JSON ma’lumot nusxasi'),
                    subtitle: const Text('Biznes yozuvlarini faylga saqlash'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: store.offline
                        ? null
                        : () => downloadFile(
                            context,
                            store,
                            '/api/backup',
                            'tushum-malumot-${store.currentDay}.json',
                          ),
                  ),
              ],
            ),
          ),
          const SectionHeader('Hisob va ulanish'),
          Surface(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.lock_outline),
                  title: const Text('Parolni almashtirish'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: store.offline ? null : () => changePassword(context),
                ),
                ListTile(
                  leading: const Icon(Icons.dns_outlined),
                  title: const Text('Ulangan server'),
                  subtitle: SelectableText(
                    store.api.baseUrl,
                    style: const TextStyle(color: Palette.muted, fontSize: 13),
                  ),
                ),
                ListTile(
                  leading: Icon(
                    store.offline
                        ? Icons.cloud_off_outlined
                        : Icons.cloud_done_outlined,
                    color: store.offline ? Palette.amber : Palette.green,
                  ),
                  title: Text(
                    store.offline ? 'Oflayn' : 'Server bilan ulangan',
                  ),
                  subtitle: Text(
                    'So‘nggi yangilanish ${displayDate(store.data['server_time'])}',
                  ),
                ),
                ListTile(
                  leading: const Icon(Icons.logout_rounded, color: Palette.red),
                  title: const Text(
                    'Hisobdan chiqish',
                    style: TextStyle(color: Palette.red),
                  ),
                  onTap: () => signOut(context),
                ),
              ],
            ),
          ),
          if (store.isOwner) ...[
            const SectionHeader('SMS'),
            Surface(
              padding: EdgeInsets.zero,
              child: ListTile(
                leading: const Icon(Icons.sms_outlined),
                title: const Text('SMS integratsiyasi'),
                subtitle: const Text('USMS balansi va servis shablonlari'),
                trailing: const Icon(Icons.chevron_right),
                onTap: store.offline
                    ? null
                    : () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => SmsPage(store: store),
                        ),
                      ),
              ),
            ),
          ],
          const SectionHeader('Keyingi integratsiyalar'),
          const Surface(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'AI qo‘ng‘iroq · Onlayn to‘lov',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
                SizedBox(height: 8),
                Text(
                  'Integratsiya bosqichi kutilmoqda.',
                  style: TextStyle(color: Palette.muted),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          const Text(
            'Tushum AI · 1.0.0',
            textAlign: TextAlign.center,
            style: TextStyle(color: Palette.muted, fontSize: 12),
          ),
        ],
      ),
    ),
  );
}

class TeamPage extends StatefulWidget {
  const TeamPage({super.key, required this.store});
  final AppStore store;
  @override
  State<TeamPage> createState() => _TeamPageState();
}

class _TeamPageState extends State<TeamPage> {
  List<Json> members = [];
  bool loading = true;
  String? error;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final response = await widget.store.api.request('/api/team') as List;
      if (mounted) {
        setState(
          () => members = response
              .map((row) => Map<String, dynamic>.from(row as Map))
              .toList(),
        );
      }
    } on ApiError catch (failure) {
      if (mounted) setState(() => error = failure.message);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> memberForm({Json? member}) async {
    final saved = await editForm(
      context,
      widget.store,
      title: member == null ? 'Jamoaga xodim qo‘shish' : 'Xodim huquqlari',
      description: 'Menejer mijozlar, nasiyalar va to‘lovlarni boshqaradi. Kuzatuvchi ma’lumotlarni ko‘radi va hisobot yuklaydi. Qaytarim va jamoa boshqaruvi biznes egasiga berilgan.',
      fields: [
        if (member == null) ...[
          const FieldSpec('name', 'Xodim ismi', maxLength: 100),
          const FieldSpec(
            'phone',
            'Telefon raqami',
            kind: FieldKind.phone,
            initial: '+998',
            maxLength: 24,
          ),
          const FieldSpec(
            'password',
            'Boshlang‘ich parol',
            kind: FieldKind.password,
            maxLength: 128,
          ),
        ],
        FieldSpec(
          'role',
          'Huquqi',
          kind: FieldKind.select,
          options: const {'manager': 'Menejer', 'viewer': 'Kuzatuvchi'},
          initial: text(member?['role']).isEmpty
              ? 'manager'
              : text(member?['role']),
        ),
        if (member != null)
          FieldSpec(
            'active',
            'Hisob faol',
            kind: FieldKind.toggle,
            initial: integer(member['active']) == 1 ? 'true' : 'false',
            hint: 'O‘chirilsa, xodimning joriy sessiyalari yakunlanadi.',
          ),
      ],
      submit: (values, id) async {
        await widget.store.mutate(
          member == null ? '/api/team' : '/api/team/${member['id']}',
          values,
          method: member == null ? 'POST' : 'PATCH',
          operationId: id,
        );
      },
    );
    if (saved && mounted) await load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Jamoa'),
      actions: [
        IconButton(
          tooltip: 'Yangilash',
          onPressed: loading ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ContentList(
      children: [
        FilledButton.icon(
          onPressed: loading ? null : () => memberForm(),
          icon: const Icon(Icons.person_add_alt),
          label: const Text('Xodim qo‘shish'),
        ),
        const SizedBox(height: 20),
        if (loading) const Center(child: CircularProgressIndicator()),
        if (error != null)
          Text(error!, style: const TextStyle(color: Palette.red)),
        for (final member in members)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Surface(
              padding: EdgeInsets.zero,
              child: ListTile(
                contentPadding: const EdgeInsets.all(16),
                leading: PersonAvatar(text(member['name'])),
                title: Text(
                  text(member['name']),
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                subtitle: Text(
                  '${member['phone']}\n${roleLabel(text(member['role']))} · ${integer(member['active']) == 1 ? 'Faol' : 'O‘chirilgan'}',
                ),
                trailing: member['role'] == 'owner'
                    ? null
                    : const Icon(Icons.edit_outlined),
                onTap: member['role'] == 'owner'
                    ? null
                    : () => memberForm(member: member),
              ),
            ),
          ),
      ],
    ),
  );
}
