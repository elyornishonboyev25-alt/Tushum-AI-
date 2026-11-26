import 'dart:async';

import 'package:material_ui/material_ui.dart';

import 'core.dart';
import 'forms.dart';
import 'ui.dart';
import 'quick_voice.dart';
import 'voice_dashboard.dart';

const callStates = {
  'queued': 'Navbatda',
  'dialing': 'Qo‘ng‘iroq qilinmoqda',
  'connected': 'Suhbat davom etmoqda',
  'completed': 'Yakunlandi',
  'cancelled': 'To‘xtatildi',
  'failed': 'Ulanmadi',
  'no_answer': 'Javob bo‘lmadi',
};
const outcomes = {
  'promise': 'To‘lov va’dasi tasdiqlandi',
  'payment_claimed': 'To‘lovni tekshirish kerak',
  'disputed': 'Mijoz e’tiroz bildirdi',
  'wrong_person': 'Boshqa odam javob berdi',
  'opt_out': 'Aloqaga rozilik bekor qilindi',
  'callback': 'Qayta bog‘lanish so‘raldi',
  'human_requested': 'Menejer bilan suhbat so‘raldi',
  'no_agreement': 'Kelishuvga erishilmadi',
};
bool activeCall(Json row) =>
    ['queued', 'dialing', 'connected'].contains(row['status']);

String voiceError(dynamic code) => switch (text(code)) {
  'stt_unavailable' => 'Nutqni yozib olish xizmati uzildi. Taxminiy matn asosida davom etilmadi. Qayta urinib ko‘ring.',
  'audio_quality' => 'Ovoz oqimida uzilish bo‘ldi. Noaniq nutq asosida davom etilmadi. Ulanishni tekshiring.',
  'ai_quota' =>
    'AI xizmatining kvotasi tugagan. Google AI hisobidagi limitni tekshiring.',
  'ai_access' => 'AI xizmatiga kirish ruxsatini tekshirish kerak.',
  'server_restarted' || 'server_stopped' => 'Server qayta ishga tushgani uchun suhbat uzildi. Avtomatik qayta terilmadi.',
  'connection_failed' => 'Ovozli aloqa o‘rnatilmadi. Telegram maxfiylik sozlamalari va internetni tekshiring.',
  'no_answer' => 'Mijoz javob bermadi yoki qo‘ng‘iroqni rad etdi.',
  'permission_changed' => 'Mijoz roziligi yoki xodim vakolati o‘zgargani uchun qo‘ng‘iroq boshlanmadi.',
  'target_unavailable' => 'Telegram username topilmadi yoki bu foydalanuvchi akkaunti emas. Username’ni tekshiring.',
  'telegram_privacy' => 'Mijozning Telegram sozlamalari qo‘ng‘iroqqa ruxsat bermadi. Mijoz qo‘ng‘iroqlar maxfiyligini tekshirishi kerak.',
  'self_call' => 'Qo‘ng‘iroq qiluvchi akkauntning o‘ziga qo‘ng‘iroq qilib bo‘lmaydi. Mijoz username’ini kiriting.',
  _ => '',
};

class VoicePage extends StatefulWidget {
  const VoicePage({super.key, required this.store, this.initialCallId});
  final AppStore store;
  final String? initialCallId;
  @override
  State<VoicePage> createState() => _VoicePageState();
}

class _VoicePageState extends State<VoicePage> {
  Json connection = {};
  List<Json> calls = [];
  Json? detail;
  String? selected;
  String? error;
  bool loading = true;
  bool requesting = false;
  Timer? timer;

  @override
  void initState() {
    super.initState();
    selected = widget.initialCallId;
    load();
    timer = Timer.periodic(const Duration(seconds: 1), (_) => load());
  }

  Future<void> load() async {
    if (requesting || !mounted) return;
    requesting = true;
    try {
      final result = await widget.store.api.request('/api/voice') as Map;
      final rows = (result['calls'] as List)
          .map((v) => Map<String, dynamic>.from(v as Map))
          .toList();
      final nextId = selected ?? (rows.isEmpty ? null : text(rows.first['id']));
      Json? nextDetail;
      if (nextId != null) {
        nextDetail = Map<String, dynamic>.from(
          await widget.store.api.request('/api/voice/calls/$nextId') as Map,
        );
      }
      if (!mounted) return;
      final finished =
          detail != null &&
          activeCall(detail!) &&
          nextDetail != null &&
          !activeCall(nextDetail);
      setState(() {
        connection = Map<String, dynamic>.from(result['connection'] as Map);
        calls = rows;
        if (selected == null || selected == nextId) {
          selected = nextId;
          detail = nextDetail;
        }
        error = null;
        loading = false;
      });
      if (finished) await widget.store.refresh();
    } on ApiError catch (failure) {
      if (mounted) {
        setState(() {
          error = failure.message;
          loading = false;
        });
      }
    } finally {
      requesting = false;
    }
  }

  Future<void> linkAccount() async {
    await editForm(
      context,
      widget.store,
      title: 'Telegram akkauntini biznesga ulash',
      description: 'Server uchun berilgan bir martalik ulash kodini kiriting. Telegram paroli yoki API kaliti bu yerga kiritilmaydi.',
      fields: const [
        FieldSpec(
          'code',
          'Ulash kodi',
          kind: FieldKind.password,
          maxLength: 150,
        ),
      ],
      submit: (values, operationId) async {
        await widget.store.api.request(
          '/api/voice/activate',
          method: 'POST',
          body: values,
        );
      },
      button: 'Biznesga ulash',
    );
    await load();
  }

  Future<void> start() async {
    final profile = Map<String, dynamic>.from(
      connection['profile'] as Map? ?? {},
    );
    if (profile['complete'] != true) {
      if (!widget.store.isOwner) {
        feedbackMessage(
          context,
          'Avval biznes egasi qo‘ng‘iroq ma’lumotlarini tasdiqlashi kerak.',
        );
        return;
      }
      if (!await editVoiceProfile(context, widget.store, profile)) return;
      await load();
      if (!mounted) return;
    }
    var result = await showDialog<Json>(
      context: context,
      builder: (_) => connection['custom_targets'] == true
          ? QuickVoiceDialog(store: widget.store)
          : StartVoiceDialog(store: widget.store, connection: connection),
    );
    if (result?['select_existing'] == true && mounted) {
      result = await showDialog<Json>(
        context: context,
        builder: (_) =>
            StartVoiceDialog(store: widget.store, connection: connection),
      );
    }
    final started = result;
    if (started != null && mounted) {
      setState(() => selected = text(started['id']));
      await load();
    }
  }

  Future<void> cancel() async {
    final row = detail;
    if (row == null ||
        !await confirm(
          context,
          'Suhbatni to‘xtatish',
          'Joriy qo‘ng‘iroq tugatiladi. Saqlangan tasdiqlangan va’da saqlanib qoladi.',
          action: 'To‘xtatish',
        )) {
      return;
    }
    try {
      await widget.store.mutate('/api/voice/calls/${row['id']}/cancel', {});
      await load();
    } on ApiError catch (failure) {
      if (mounted) feedbackMessage(context, failure.message);
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ready = connection['ready'] == true;
    final bound = connection['bound'] == true;
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI suhbatlar'),
        actions: [
          IconButton(
            onPressed: load,
            tooltip: 'Yangilash',
            icon: const Icon(Icons.refresh),
          ),
          const SizedBox(width: 12),
        ],
      ),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 1050;
                final list = Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _connectionCard(ready, bound),
                    const SizedBox(height: 20),
                    Text(
                      'Suhbatlar tarixi',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '${calls.length} ta suhbat · so‘nggi 100 ta yozuv',
                      style: const TextStyle(color: Palette.muted),
                    ),
                    const SizedBox(height: 12),
                    if (calls.isEmpty)
                      const Surface(
                        child: Padding(
                          padding: EdgeInsets.all(20),
                          child: Text(
                            'Birinchi suhbatni boshlang. Mijozning javobi, tasdiqlangan va’da va natija shu yerda ko‘rinadi.',
                          ),
                        ),
                      ),
                    for (final row in calls)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Material(
                          color: selected == row['id']
                              ? Palette.soft
                              : Palette.surface,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(14),
                            side: BorderSide(
                              color: selected == row['id']
                                  ? Palette.teal
                                  : Palette.line,
                            ),
                          ),
                          child: ListTile(
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 16,
                              vertical: 7,
                            ),
                            leading: CircleAvatar(
                              backgroundColor: activeCall(row)
                                  ? Palette.teal
                                  : Palette.background,
                              child: Icon(
                                activeCall(row)
                                    ? Icons.graphic_eq
                                    : Icons.call_outlined,
                                color: activeCall(row)
                                    ? Colors.white
                                    : Palette.teal,
                              ),
                            ),
                            title: Text(
                              text(row['customer_name']),
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            subtitle: Text(
                              '${outcomes[row['outcome']] ?? callStates[row['status']] ?? row['status']}\n${displayDate(row['created_at'])} · @${row['target']}',
                            ),
                            isThreeLine: true,
                            onTap: () {
                              setState(() => selected = text(row['id']));
                              load();
                            },
                          ),
                        ),
                      ),
                  ],
                );
                final content = detail == null
                    ? const Surface(
                        child: Padding(
                          padding: EdgeInsets.all(32),
                          child: Column(
                            children: [
                              Icon(
                                Icons.headset_mic_outlined,
                                size: 48,
                                color: Palette.teal,
                              ),
                              SizedBox(height: 16),
                              Text(
                                'Har bir kelishuvning tarixi bor',
                                style: TextStyle(
                                  fontSize: 22,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              SizedBox(height: 12),
                              Text(
                                'Suhbatni tanlang. Aytilgan gaplar va kelishuv natijasi shu yerda ochiladi.',
                                textAlign: TextAlign.center,
                              ),
                            ],
                          ),
                        ),
                      )
                    : _detail(detail!);
                return SingleChildScrollView(
                  padding: EdgeInsets.all(wide ? 28 : 18),
                  child: Align(
                    alignment: Alignment.topCenter,
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 1400),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          if (error != null)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 16),
                              child: Text(
                                error!,
                                style: const TextStyle(color: Palette.red),
                              ),
                            ),
                          if (wide)
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                SizedBox(width: 370, child: list),
                                const SizedBox(width: 24),
                                Expanded(child: content),
                              ],
                            )
                          else ...[
                            list,
                            const SizedBox(height: 24),
                            content,
                          ],
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
    );
  }

  Widget _connectionCard(bool ready, bool bound) => Container(
    padding: const EdgeInsets.all(22),
    decoration: BoxDecoration(
      color: Palette.surface,
      borderRadius: BorderRadius.circular(20),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              ready ? Icons.check_circle : Icons.link,
              color: const Color(0xFF8CE7CB),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                ready
                    ? 'Ovozli yordamchi tayyor'
                    : bound
                    ? 'Ovozli xizmat ulanmoqda'
                    : 'Telegram orqali AI suhbat',
                style: const TextStyle(
                  color: Palette.ink,
                  fontWeight: FontWeight.w700,
                  fontSize: 18,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        Text(
          bound
              ? '${text(connection['caller'])}\nO‘zbekcha ovoz · tasdiqlanadigan kelishuv'
              : 'Mijoz bilan gaplashing, kelishuvni aniqlashtiring va natijani kuzating.',
          style: const TextStyle(color: Color(0xFFCBDFDF), height: 1.6),
        ),
        const SizedBox(height: 16),
        const Text(
          'Telegram orqali ovozli aloqa. Tasdiqlangan kelishuvlar avtomatik saqlanadi.',
          style: TextStyle(color: Color(0xFFCBDFDF), fontSize: 12, height: 1.5),
        ),
        const SizedBox(height: 18),
        if (bound) ...[
          Text(
            connection['profile'] is Map &&
                    connection['profile']['complete'] == true
                ? '${connection['profile']['business_name']}\nMas’ul: ${connection['profile']['manager_name']} · ${connection['profile']['phone']}'
                : 'Boshlashdan oldin do‘kon nomi va mas’ul menejer ma’lumotlarini tasdiqlang.',
            style: const TextStyle(color: Palette.ink, height: 1.6),
          ),
          if (widget.store.isOwner && !calls.any(activeCall))
            TextButton(
              onPressed: () async {
                await editVoiceProfile(
                  context,
                  widget.store,
                  Map<String, dynamic>.from(
                    connection['profile'] as Map? ?? {},
                  ),
                );
                await load();
              },
              child: const Text(
                'Biznes ma’lumotlarini sozlash',
                style: TextStyle(color: Color(0xFF8CE7CB)),
              ),
            ),
          const SizedBox(height: 10),
        ],
        FilledButton.tonalIcon(
          onPressed: widget.store.canEdit && ready && !calls.any(activeCall)
              ? start
              : null,
          icon: const Icon(Icons.add_call),
          label: const Text('AI suhbat boshlash'),
        ),
        if (!bound)
          const Padding(
            padding: EdgeInsets.only(top: 10),
            child: Text(
              'Hozir kirilgan hisob uchun ovozli xizmat ulanmagan. Sozlamalarda kirish raqamingizni tekshiring.',
              style: TextStyle(color: Color(0xFFFFD7AB), fontSize: 13),
            ),
          ),
        if (bound && !widget.store.canEdit)
          const Padding(
            padding: EdgeInsets.only(top: 10),
            child: Text(
              'Qo‘ng‘iroq boshlash uchun biznes egasi yoki menejer huquqi va internet ulanishi kerak.',
              style: TextStyle(color: Color(0xFFFFD7AB), fontSize: 13),
            ),
          ),
        if (calls.any(activeCall))
          const Padding(
            padding: EdgeInsets.only(top: 10),
            child: Text(
              'Hozir suhbat davom etmoqda. Keyingi qo‘ng‘iroqni u tugagach boshlaysiz.',
              style: TextStyle(color: Color(0xFFCBDFDF), fontSize: 13),
            ),
          ),
        if (!bound && widget.store.isOwner)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: FilledButton.tonal(
              onPressed: linkAccount,
              child: const Text('Telegram ulanishini sozlash'),
            ),
          ),
        if (bound && !ready)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Text(switch (text(connection['state'])) {
              'telegram_login_required' =>
                'Telegram sessiyasini yangilash kerak.',
              'caller_mismatch' => 'Ulangan Telegram akkaunti mos kelmadi.',
              'telegram_unavailable' => 'Telegram xizmatiga ulanib bo‘lmadi.',
              _ => 'Serverdagi ovozli xizmat tayyorlanmoqda.',
            }, style: const TextStyle(color: Color(0xFFFFD7AB))),
          ),
      ],
    ),
  );

  Widget _detail(Json row) {
    final brief = Map<String, dynamic>.from(row['brief'] as Map? ?? {});
    final handoff = row['handoff'] is Map
        ? Map<String, dynamic>.from(row['handoff'] as Map)
        : null;
    final transcript = (row['transcript'] as List? ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    final proposal = row['proposal'] is Map
        ? Map<String, dynamic>.from(row['proposal'] as Map)
        : null;
    final live = row['status'] == 'connected';
    final errorText = voiceError(row['error_code']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Surface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      callStates[row['status']] ?? 'Suhbat',
                      style: const TextStyle(
                        fontSize: 23,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  StatusTag(
                    live ? 'JONLI' : 'TELEGRAM',
                    color: live ? Palette.green : Palette.teal,
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                '@${row['target']} · ${displayDate(row['created_at'])}',
                style: const TextStyle(color: Palette.muted),
              ),
              if (row['first_audio_ms'] != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    'Birinchi ovoz ${(integer(row['first_audio_ms']) / 1000).toStringAsFixed(1)} soniyada',
                    style: const TextStyle(color: Palette.muted, fontSize: 12),
                  ),
                ),
              if (activeCall(row) && widget.store.canEdit)
                Padding(
                  padding: const EdgeInsets.only(top: 16),
                  child: OutlinedButton.icon(
                    onPressed: row['cancel_requested'] == 1 ? null : cancel,
                    icon: const Icon(Icons.call_end),
                    label: Text(
                      row['cancel_requested'] == 1
                          ? 'To‘xtatilmoqda…'
                          : 'Suhbatni to‘xtatish',
                    ),
                  ),
                ),
              if (errorText.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 16),
                  child: Text(
                    errorText,
                    style: const TextStyle(color: Palette.red),
                  ),
                ),
            ],
          ),
        ),
        if (brief.isNotEmpty) ...[
          const SizedBox(height: 16),
          Surface(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'AI’ga berilgan ma’lumotlar',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 10),
                Text(
                  '${brief['business']} · ${brief['customer']}',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 6),
                Text('${brief['debt_title']} · ${brief['balance_som']} so‘m'),
                Text('To‘lov muddati: ${displayDate(brief['due_on'])}'),
                Text('Mas’ul menejer: ${brief['manager_name']}'),
              ],
            ),
          ),
        ],
        if (handoff != null) ...[
          const SizedBox(height: 16),
          Surface(
            color: Palette.warningSoft,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  integer(handoff['resolved']) == 1
                      ? 'Murojaat ko‘rib chiqilgan'
                      : 'Menejerga murojaat yuborilgan',
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    color: Palette.amber,
                  ),
                ),
                const SizedBox(height: 8),
                Text(text(handoff['summary'])),
                if (integer(handoff['resolved']) == 1)
                  Text('Natija: ${handoff['resolution']}'),
              ],
            ),
          ),
        ],
        if (proposal != null) ...[
          const SizedBox(height: 16),
          Surface(
            color: row['promise_id'] != null
                ? Palette.soft
                : Palette.warningSoft,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  row['promise_id'] != null
                      ? 'Tasdiqlangan to‘lov va’dasi'
                      : activeCall(row)
                      ? 'Mijoz tasdig‘i kutilmoqda'
                      : 'Tasdiqlanmagan loyiha',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 12),
                Text(
                  formatMoney(proposal['amount']),
                  style: const TextStyle(
                    fontSize: 30,
                    fontWeight: FontWeight.w700,
                    color: Palette.teal,
                  ),
                ),
                for (final part
                    in (proposal['installments'] as List? ?? [proposal]))
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(
                      '${displayDate(part['due_on'])} · ${formatMoney(part['amount'])}',
                      style: const TextStyle(fontSize: 17),
                    ),
                  ),
                const SizedBox(height: 10),
                Text(
                  row['promise_id'] != null
                      ? 'Va’dalar bo‘limiga saqlandi. Qarz qoldig‘i to‘lov qayd etilgach o‘zgaradi.'
                      : 'Bu hali saqlangan va’da emas.',
                  style: const TextStyle(color: Palette.muted, fontSize: 13),
                ),
              ],
            ),
          ),
        ],
        if (text(row['outcome']).isNotEmpty) ...[
          const SizedBox(height: 16),
          Surface(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  outcomes[row['outcome']] ?? 'Suhbat natijasi',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (text(row['summary']).isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 10),
                    child: Text(
                      text(row['summary']),
                      style: const TextStyle(height: 1.6),
                    ),
                  ),
                if ([
                  'payment_claimed',
                  'disputed',
                  'callback',
                  'human_requested',
                ].contains(row['outcome']))
                  const Padding(
                    padding: EdgeInsets.only(top: 10),
                    child: Text(
                      'Keyingi qadam — menejer tekshiruvi va mijoz bilan qayta aloqa.',
                      style: TextStyle(color: Palette.amber),
                    ),
                  ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 16),
        Surface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Suhbat matni',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              const Text(
                'Mijoz va AI gaplari alohida ko‘rsatiladi. Mijoz matni tahrirsiz STT natijasidir; audio yozuvi saqlanmaydi.',
                style: TextStyle(color: Palette.muted, fontSize: 12),
              ),
              const SizedBox(height: 20),
              if (transcript.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 32),
                  child: Text(
                    activeCall(row)
                        ? 'Mijoz javobi kutilmoqda…'
                        : 'Suhbat matni mavjud emas.',
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Palette.muted),
                  ),
                ),
              for (final item in transcript)
                Align(
                  alignment: item['speaker'] == 'ai'
                      ? Alignment.centerLeft
                      : Alignment.centerRight,
                  child: Container(
                    constraints: const BoxConstraints(maxWidth: 600),
                    margin: EdgeInsets.only(
                      bottom: 14,
                      left: item['speaker'] == 'ai' ? 0 : 30,
                      right: item['speaker'] == 'ai' ? 30 : 0,
                    ),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: item['speaker'] == 'ai'
                          ? Palette.background
                          : Palette.soft,
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item['speaker'] == 'ai' ? 'TUSHUM AI' : 'MIJOZ',
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                            color: Palette.teal,
                            letterSpacing: 1,
                          ),
                        ),
                        const SizedBox(height: 6),
                        SelectableText(
                          text(item['text']),
                          style: const TextStyle(height: 1.6),
                        ),
                        if (item['source'] == 'dedicated_stt_verbatim')
                          const Padding(
                            padding: EdgeInsets.only(top: 6),
                            child: Text(
                              'Mijoz nutqi · STT',
                              style: TextStyle(
                                color: Palette.muted,
                                fontSize: 10,
                              ),
                            ),
                          ),
                        if (item['source'] == 'legacy' ||
                            item['source'] == null)
                          const Padding(
                            padding: EdgeInsets.only(top: 6),
                            child: Text(
                              'Avvalgi transkript',
                              style: TextStyle(
                                color: Palette.muted,
                                fontSize: 10,
                              ),
                            ),
                          ),
                        if (item['is_final'] != 1 && live)
                          const Text(
                            'Gap davom etmoqda…',
                            style: TextStyle(
                              color: Palette.muted,
                              fontSize: 11,
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 80),
      ],
    );
  }
}

class StartVoiceDialog extends StatefulWidget {
  const StartVoiceDialog({
    super.key,
    required this.store,
    required this.connection,
    this.initialCustomerId,
  });
  final AppStore store;
  final Json connection;
  final String? initialCustomerId;
  @override
  State<StartVoiceDialog> createState() => _StartVoiceDialogState();
}

class _StartVoiceDialogState extends State<StartVoiceDialog> {
  String? debtId;
  String? target;
  bool consent = false;
  bool busy = false;
  String? error;
  final operationId = uuid.v4();

  @override
  void initState() {
    super.initState();
    final customerId = widget.initialCustomerId;
    if (customerId == null) return;
    final debts = widget.store
        .rows('debts')
        .where(
          (d) =>
              d['customer_id'] == customerId &&
              integer(d['balance']) > 0 &&
              integer(d['archived']) == 0,
        );
    if (debts.isNotEmpty) debtId = text(debts.first['id']);
    target = targetForDebt(debtId);
  }

  String? targetForDebt(String? id) {
    final debt = widget.store.find('debts', id ?? '');
    final username = text(
      widget.store.find(
        'customers',
        text(debt?['customer_id']),
      )?['telegram_username'],
    ).replaceFirst('@', '');
    final targets = (widget.connection['targets'] as List? ?? []).map(text);
    if (username.isNotEmpty &&
        (widget.connection['custom_targets'] == true ||
            targets.contains(username))) {
      return username;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final store = widget.store;
    final debts = store
        .rows('debts')
        .where((d) => integer(d['balance']) > 0 && integer(d['archived']) == 0)
        .toList();
    final targets = (widget.connection['targets'] as List? ?? [])
        .map(text)
        .toList();
    return AlertDialog(
      title: const Text('AI suhbat boshlash'),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Mijoz va nasiya yozuvini tanlang. Telegram orqali ovozli qo‘ng‘iroq boradi.',
              ),
              const SizedBox(height: 12),
              Text(
                'Do‘kon / korxona: ${widget.connection['profile']?['business_name'] ?? ''}',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 20),
              DropdownButtonFormField<String>(
                initialValue: debtId,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Mijoz va nasiya'),
                items: debts
                    .map(
                      (d) => DropdownMenuItem(
                        value: text(d['id']),
                        child: Text(
                          '${text(store.find('customers', text(d['customer_id']))?['name'])} · ${formatMoney(d['balance'])}',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    )
                    .toList(),
                onChanged: busy
                    ? null
                    : (v) => setState(() {
                        debtId = v;
                        target = targetForDebt(v);
                        consent = false;
                      }),
              ),
              const SizedBox(height: 16),
              if (widget.connection['custom_targets'] == true)
                TextFormField(
                  key: ValueKey('target-$debtId'),
                  initialValue: target,
                  autocorrect: false,
                  enableSuggestions: false,
                  maxLength: 33,
                  decoration: const InputDecoration(
                    labelText: 'Telegram username',
                    hintText: '@username',
                  ),
                  onChanged: busy
                      ? null
                      : (v) => setState(() => target = v.trim()),
                )
              else
                DropdownButtonFormField<String>(
                  key: ValueKey('target-$debtId'),
                  initialValue: target,
                  decoration: const InputDecoration(
                    labelText: 'Telegram akkaunti',
                  ),
                  items: targets
                      .map(
                        (t) => DropdownMenuItem(value: t, child: Text('@$t')),
                      )
                      .toList(),
                  onChanged: busy ? null : (v) => setState(() => target = v),
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
                subtitle: const Text('AI suhbat boshida o‘zini tanishtiradi.'),
              ),
              if (error != null)
                Text(error!, style: const TextStyle(color: Palette.red)),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context),
          child: const Text('Qaytish'),
        ),
        FilledButton.icon(
          onPressed:
              busy ||
                  !consent ||
                  debtId == null ||
                  !RegExp(r'^@?[A-Za-z][A-Za-z0-9_]{4,31}$')
                      .hasMatch(target ?? '')
              ? null
              : () async {
                  setState(() {
                    busy = true;
                    error = null;
                  });
                  try {
                    final result = await store.mutate('/api/voice/calls', {
                      'debt_id': debtId,
                      'target': target,
                      'consent': consent,
                    }, operationId: operationId);
                    if (context.mounted) Navigator.pop(context, result);
                  } on ApiError catch (failure) {
                    if (mounted) {
                      setState(() {
                        error = failure.message;
                        busy = false;
                      });
                    }
                  }
                },
          icon: Icon(busy ? Icons.hourglass_top : Icons.call),
          label: Text(busy ? 'Boshlanmoqda…' : 'Qo‘ng‘iroq qilish'),
        ),
      ],
    );
  }
}
