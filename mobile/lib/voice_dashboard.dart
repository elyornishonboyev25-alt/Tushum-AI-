import 'package:material_ui/material_ui.dart';

import 'core.dart';
import 'forms.dart';
import 'ui.dart';

const handoffLabels = {
  'disputed': 'Qarzga e’tiroz',
  'payment_claimed': 'To‘lovni tekshirish',
  'human_requested': 'Menejer bilan suhbat',
  'callback': 'Qayta bog‘lanish',
  'wrong_person': 'Mijozni tekshirish',
  'opt_out': 'Aloqa to‘xtatildi',
  'no_agreement': 'Kelishuv bo‘lmadi',
};

Future<bool> editVoiceProfile(
  BuildContext context,
  AppStore store,
  Json profile,
) {
  return editForm(
    context,
    store,
    title: 'Qo‘ng‘iroq uchun biznes ma’lumotlari',
    description: 'AI shu nom bilan tanishadi. E’tiroz va savollar mas’ul menejerga dashboard orqali keladi. Faqat haqiqiy ma’lumotlarni kiriting.',
    fields: [
      FieldSpec(
        'business_name',
        'Do‘kon yoki korxona nomi',
        initial: text(profile['business_name']),
      ),
      FieldSpec(
        'manager_name',
        'Mas’ul menejerning ismi',
        initial: text(profile['manager_name']),
        maxLength: 100,
      ),
      FieldSpec(
        'phone',
        'Biznesning aloqa raqami',
        initial: text(profile['phone']),
        kind: FieldKind.phone,
        maxLength: 24,
      ),
    ],
    submit: (values, id) async {
      await store.mutate(
        '/api/voice/profile',
        values,
        method: 'PUT',
        operationId: id,
      );
    },
    button: 'Ma’lumotlarni tasdiqlash',
  );
}

class VoiceDashboard extends StatelessWidget {
  const VoiceDashboard({
    super.key,
    required this.store,
    required this.openCall,
  });
  final AppStore store;
  final void Function(String callId) openCall;

  Future<void> resolve(BuildContext context, Json row) async {
    await editForm(
      context,
      store,
      title: 'Murojaatni ko‘rib chiqish',
      description:
          '${row['customer_name']} · ${row['summary']}\nNatijani yozing. Qarz yoki to‘lov o‘zgartirilmaydi; zarur bo‘lsa mijoz kartasida alohida qayd eting.',
      fields: const [
        FieldSpec(
          'resolution',
          'Tekshiruv natijasi',
          kind: FieldKind.multiline,
          maxLength: 600,
        ),
      ],
      submit: (values, id) async {
        await store.mutate(
          '/api/voice/handoffs/${row['id']}/resolve',
          values,
          operationId: id,
        );
      },
      button: 'Ko‘rib chiqildi',
    );
  }

  @override
  Widget build(BuildContext context) {
    final pending = store
        .rows('voice_handoffs')
        .where((r) => integer(r['resolved']) == 0)
        .toList();
    final promises = store
        .rows('promises')
        .where(
          (r) =>
              text(r['note']).startsWith('Telegram AI suhbati') &&
              !['cancelled', 'fulfilled'].contains(r['status']),
        )
        .toList();
    if (pending.isEmpty && promises.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (pending.isNotEmpty) ...[
            Row(
              children: [
                const Icon(Icons.support_agent, color: Palette.amber),
                const SizedBox(width: 10),
                const Expanded(
                  child: Text(
                    'Menejer e’tibori kerak',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
                  ),
                ),
                StatusTag('${pending.length} ta', color: Palette.amber),
              ],
            ),
            const SizedBox(height: 12),
            for (final row in pending.take(6))
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Surface(
                  color: const Color(0xFFFFF7EB),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Wrap(
                        spacing: 12,
                        runSpacing: 8,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          Text(
                            text(row['customer_name']),
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          StatusTag(
                            handoffLabels[row['kind']] ?? 'Murojaat',
                            color: Palette.amber,
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        text(row['summary']),
                        style: const TextStyle(height: 1.6),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        '@${row['target']} · ${displayDate(row['created_at'])}',
                        style: const TextStyle(
                          color: Palette.muted,
                          fontSize: 12,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 10,
                        runSpacing: 8,
                        children: [
                          OutlinedButton.icon(
                            onPressed: () => openCall(text(row['call_id'])),
                            icon: const Icon(Icons.forum_outlined, size: 18),
                            label: const Text('Suhbatni ko‘rish'),
                          ),
                          if (store.canEdit)
                            FilledButton.tonal(
                              onPressed: () => resolve(context, row),
                              child: const Text('Ko‘rib chiqish'),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            if (pending.length > 6)
              Text(
                'Yana ${pending.length - 6} ta murojaat bor. AI suhbatlarda tarixni oching.',
              ),
            const SizedBox(height: 16),
          ],
          if (promises.isNotEmpty) ...[
            const Text(
              'AI orqali tasdiqlangan va’dalar',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            Surface(
              child: Column(
                children: [
                  for (final row in promises.take(6))
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: const Icon(
                        Icons.event_available,
                        color: Palette.teal,
                      ),
                      title: Text(
                        text(
                          store.find(
                            'customers',
                            text(row['customer_id']),
                          )?['name'],
                        ),
                      ),
                      subtitle: Text(
                        '${displayDate(row['due_on'])} · ${row['status'] == 'fulfilled'
                            ? 'Bajarilgan'
                            : row['status'] == 'broken'
                            ? 'Muddati o‘tgan'
                            : 'Mijoz tasdiqlagan'}',
                      ),
                      trailing: Text(
                        formatMoney(row['amount']),
                        style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          color: Palette.teal,
                        ),
                      ),
                      onTap: () => openCall(
                        text(row['note']).replaceFirst(
                          'Telegram AI suhbati orqali tasdiqlandi. ',
                          '',
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
