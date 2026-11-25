import 'dart:async';
import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import 'core.dart';
import 'customers.dart';
import 'executive_data.dart';
import 'ui.dart';
import 'voice.dart';
import 'voice_dashboard.dart';

class TushumBrand extends StatelessWidget {
  const TushumBrand({super.key, this.compact = false});
  final bool compact;
  @override
  Widget build(BuildContext context) => Semantics(
    label: 'Tushum AI',
    excludeSemantics: true,
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        const CustomPaint(size: Size(30, 32), painter: _BrandPainter()),
        if (!compact) ...[
          const SizedBox(width: 10),
          const Text(
            'Tushum',
            style: TextStyle(
              fontSize: 21,
              fontWeight: FontWeight.w700,
              letterSpacing: -.8,
            ),
          ),
          const Text(
            ' AI',
            style: TextStyle(
              fontSize: 21,
              fontWeight: FontWeight.w600,
              color: Palette.teal,
              letterSpacing: -.8,
            ),
          ),
        ],
      ],
    ),
  );
}

class _BrandPainter extends CustomPainter {
  const _BrandPainter();
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = Palette.teal
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    for (var i = 0; i < 4; i++) {
      final h = [9.0, 18.0, 12.0, 23.0][i];
      canvas.drawLine(Offset(3 + i * 7, 27), Offset(3 + i * 7, 27 - h), p);
    }
    canvas.drawPath(
      Path()
        ..moveTo(17, 7)
        ..lineTo(24, 3)
        ..lineTo(29, 6),
      p,
    );
  }

  @override
  bool shouldRepaint(covariant _BrandPainter oldDelegate) => false;
}

class ExecutiveDashboard extends StatefulWidget {
  const ExecutiveDashboard({
    super.key,
    required this.store,
    required this.showCustomers,
  });
  final AppStore store;
  final VoidCallback showCustomers;
  @override
  State<ExecutiveDashboard> createState() => _ExecutiveDashboardState();
}

class _ExecutiveDashboardState extends State<ExecutiveDashboard> {
  final search = TextEditingController();
  List<Json> calls = [];
  Json? detail;
  Timer? poll, demoTimer;
  bool requesting = false,
      voiceLoaded = false,
      paused = false,
      finished = false;
  String? voiceError;
  LedgerFilter filter = LedgerFilter.all;
  int page = 0, step = 0;
  bool descending = true;
  DebtorEntry? demo;
  static const script = [
    (
      true,
      'Assalomu alaykum! Men Tushum AI yordamchisiman. Nasiya to‘lovi bo‘yicha gaplashishga qulaymi?',
    ),
    (false, 'Va alaykum assalom. Ha, eshitaman.'),
    (true, 'To‘lovning yarmini ertaga amalga oshirish imkoningiz bormi?'),
    (false, 'Ha, ertaga soat 14:00 gacha yarmini to‘layman.'),
    (true, 'Rahmat. Ertaga 14:00 gacha 50% to‘lov bo‘yicha kelishdik.'),
    (false, 'To‘g‘ri. Kelishdik.'),
    (true, 'Va’dangizni qayd etdim. Ishlaringizga omad!'),
  ];
  Json get connection =>
      Map<String, dynamic>.from(widget.store.data['voice'] as Map? ?? {});
  bool get demoBusiness => widget.store.business['is_demo'] == 1;

  @override
  void initState() {
    super.initState();
    if (widget.store.signedIn) {
      WidgetsBinding.instance.addPostFrameCallback((_) => loadVoice());
      poll = Timer.periodic(const Duration(seconds: 2), (_) => loadVoice());
    }
  }

  Future<void> loadVoice() async {
    if (!mounted ||
        requesting ||
        !widget.store.signedIn ||
        widget.store.offline ||
        ModalRoute.of(context)?.isCurrent != true) {
      return;
    }
    requesting = true;
    try {
      final result = await widget.store.api.request('/api/voice') as Map;
      final loaded = (result['calls'] as List? ?? [])
          .map((c) => Map<String, dynamic>.from(c as Map))
          .toList();
      final active = loaded.where(isVoiceActive).toList();
      Json? next;
      final id = active.isNotEmpty
          ? text(active.first['id'])
          : text(detail?['id']);
      if (id.isNotEmpty) {
        next = Map<String, dynamic>.from(
          await widget.store.api.request('/api/voice/calls/$id') as Map,
        );
      }
      final justFinished =
          detail != null &&
          isVoiceActive(detail!) &&
          next != null &&
          !isVoiceActive(next);
      if (mounted) {
        setState(() {
          calls = loaded;
          detail = next;
          voiceLoaded = true;
          voiceError = null;
        });
        if (justFinished) await widget.store.refresh();
      }
    } on ApiError catch (e) {
      if (mounted) setState(() => voiceError = e.message);
    } finally {
      requesting = false;
    }
  }

  Future<void> openVoice([String? id]) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => VoicePage(store: widget.store, initialCallId: id),
      ),
    );
    if (mounted) {
      await widget.store.refresh();
      await loadVoice();
    }
  }

  Future<void> reviewCall(DebtorEntry row) async {
    if (demoBusiness) {
      startDemo(row);
      return;
    }
    if (row.stage == DebtStage.active) {
      await openVoice(text(row.call?['id']));
      return;
    }
    if (!row.contactAllowed) {
      feedbackMessage(
        context,
        'Mijoz bilan bog‘lanish roziligini uning kartasida tekshiring.',
      );
      return;
    }
    final profile = Map<String, dynamic>.from(
      connection['profile'] as Map? ?? {},
    );
    if (profile['complete'] != true) {
      if (!widget.store.isOwner) {
        feedbackMessage(
          context,
          'AI profilini biznes egasi to‘ldirishi kerak.',
        );
        return;
      }
      if (!await editVoiceProfile(context, widget.store, profile) || !mounted) {
        return;
      }
      await widget.store.refresh();
      if (!mounted) return;
    }
    final result = await showDialog<Json>(
      context: context,
      builder: (_) => StartVoiceDialog(
        store: widget.store,
        connection: connection,
        initialCustomerId: row.id,
      ),
    );
    if (result != null && mounted) await openVoice(text(result['id']));
  }

  void tick() {
    demoTimer?.cancel();
    demoTimer = Timer.periodic(const Duration(seconds: 3), (_) {
      if (!mounted) return;
      setState(() {
        if (step < script.length) {
          step++;
        } else {
          finished = true;
          demoTimer?.cancel();
        }
      });
    });
  }

  void startDemo([DebtorEntry? target]) {
    final eligible = ExecutiveLedger(
      widget.store,
      calls,
    ).entries.where((e) => e.balance > 0).toList();
    if (target == null && eligible.isEmpty) return;
    setState(() {
      demo = target ?? eligible.first;
      step = 1;
      paused = false;
      finished = false;
      filter = LedgerFilter.all;
      search.clear();
      page = 0;
    });
    tick();
  }

  void closeDemo() {
    demoTimer?.cancel();
    setState(() {
      demo = null;
      step = 0;
      paused = false;
      finished = false;
    });
  }

  DebtorEntry overlay(DebtorEntry e) => demo?.id != e.id
      ? e
      : DebtorEntry(
          customer: e.customer,
          balance: e.balance,
          overdueDays: e.overdueDays,
          stage: step >= 5 ? DebtStage.promised : DebtStage.active,
          summary: step >= 5
              ? 'Demo: ertaga 14:00 gacha 50% to‘lashga va’da berdi'
              : 'Demo: AI muzokara olib bormoqda',
          call: e.call,
          promise: e.promise,
        );
  @override
  void dispose() {
    search.dispose();
    poll?.cancel();
    demoTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.store,
    builder: (context, _) {
      final store = widget.store;
      final ledger = ExecutiveLedger(store, calls);
      final entries =
          ledger.entries
              .map(overlay)
              .where((e) => e.matches(filter, search.text))
              .toList()
            ..sort(
              (a, b) => descending
                  ? b.balance.compareTo(a.balance)
                  : a.balance.compareTo(b.balance),
            );
      const size = 5;
      final pages = math.max(1, (entries.length / size).ceil());
      final selectedPage = page.clamp(0, pages - 1);
      final visible = entries.skip(selectedPage * size).take(size).toList();
      final ready = connection['ready'] == true;
      return LayoutBuilder(
        builder: (context, bounds) {
          final mobile = bounds.maxWidth < 840;
          final padding = bounds.maxWidth < 600 ? 16.0 : 28.0;
          final width = bounds.maxWidth - padding * 2;
          return RefreshIndicator(
            onRefresh: () async {
              await store.refresh();
              await loadVoice();
            },
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: EdgeInsets.all(padding),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1600),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Boshqaruv paneli',
                                  style: TextStyle(
                                    fontSize: mobile ? 25 : 29,
                                    fontWeight: FontWeight.w700,
                                    letterSpacing: -.9,
                                  ),
                                ),
                                const SizedBox(height: 6),
                                const Text(
                                  'Nasiyalarni tushumga aylantiring.',
                                  style: TextStyle(
                                    color: Palette.muted,
                                    fontSize: 13,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          if (!mobile)
                            Padding(
                              padding: const EdgeInsets.only(top: 10),
                              child: Text(
                                displayDate(store.currentDay),
                                style: const TextStyle(
                                  color: Palette.muted,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 24),
                      Wrap(
                        spacing: 16,
                        runSpacing: 12,
                        children: [
                          _KpiCard(
                            width: mobile ? width : (width - 32) / 3,
                            label: 'Jami debitorlik qarzi',
                            value: formatMoney(ledger.balance, unit: false),
                            unit: 'so‘m',
                            icon: Icons.account_balance_wallet_outlined,
                            footer:
                                '${formatMoney(ledger.overdue)} muddati o‘tgan',
                            footerColor: ledger.overdue > 0
                                ? Palette.red
                                : Palette.muted,
                          ),
                          _KpiCard(
                            width: mobile ? width : (width - 32) / 3,
                            label: 'AI orqali olingan va’dalar',
                            value: formatMoney(ledger.aiPromised, unit: false),
                            unit: 'so‘m',
                            icon: Icons.trending_up_rounded,
                            accent: Palette.teal,
                            footer:
                                '${ledger.promisedShare.toStringAsFixed(1)}% · ochiq qarzga nisbatan',
                            footerColor: Palette.teal,
                            tooltip: 'Faqat faol AI va’dalarining to‘lanmagan qismi. Va’da — tushum emas.',
                          ),
                          _KpiCard(
                            width: mobile ? width : (width - 32) / 3,
                            label: 'Faol AI qo‘ng‘iroqlar',
                            value: voiceLoaded
                                ? '${ledger.activeCalls}'.padLeft(2, '0')
                                : '—',
                            icon: Icons.graphic_eq_rounded,
                            accent: Palette.blue,
                            footer: ready
                                ? 'Telegram AI · ulanish tayyor'
                                : demoBusiness
                                ? 'Demo muhiti · simulyatsiya tayyor'
                                : 'Telegram ulanishini tekshiring',
                            footerColor: ready ? Palette.blue : Palette.muted,
                            live: ledger.activeCalls > 0,
                          ),
                        ],
                      ),
                      const SizedBox(height: 22),
                      Wrap(
                        alignment: WrapAlignment.spaceBetween,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        spacing: 16,
                        runSpacing: 12,
                        children: [
                          Wrap(
                            spacing: 10,
                            runSpacing: 10,
                            children: [
                              DecoratedBox(
                                decoration: BoxDecoration(
                                  boxShadow: [
                                    BoxShadow(
                                      color: Palette.teal.withValues(
                                        alpha: .12,
                                      ),
                                      blurRadius: 24,
                                    ),
                                  ],
                                ),
                                child: FilledButton.icon(
                                  onPressed:
                                      store.canEdit && (ready || demoBusiness)
                                      ? () {
                                          if (demoBusiness) {
                                            startDemo();
                                          } else {
                                            openVoice();
                                          }
                                        }
                                      : null,
                                  icon: const Icon(
                                    Icons.play_arrow_rounded,
                                    size: 19,
                                  ),
                                  label: const Text(
                                    'AI qo‘ng‘iroqlarni boshlash',
                                  ),
                                ),
                              ),
                              OutlinedButton.icon(
                                onPressed:
                                    ledger.entries.any((e) => e.balance > 0)
                                    ? () => startDemo()
                                    : null,
                                icon: const Icon(
                                  Icons.graphic_eq_rounded,
                                  size: 18,
                                ),
                                label: const Text('Demo suhbat'),
                              ),
                            ],
                          ),
                          Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              _Dot(
                                color: store.offline
                                    ? Palette.amber
                                    : Palette.teal,
                              ),
                              const SizedBox(width: 7),
                              Flexible(
                                child: Text(
                                  store.offline
                                      ? 'Oflayn rejim'
                                      : 'Ma’lumotlar yangilanib turadi',
                                  style: const TextStyle(
                                    fontSize: 11,
                                    color: Palette.muted,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                      if (voiceError != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 12),
                          child: Row(
                            children: [
                              const Icon(
                                Icons.info_outline,
                                size: 16,
                                color: Palette.amber,
                              ),
                              const SizedBox(width: 8),
                              const Expanded(
                                child: Text(
                                  'AI holatini olishda uzilish. Moliyaviy ma’lumotlar alohida yangilanadi.',
                                  style: TextStyle(
                                    color: Palette.muted,
                                    fontSize: 12,
                                  ),
                                ),
                              ),
                              TextButton(
                                onPressed: loadVoice,
                                child: const Text('Qayta urinish'),
                              ),
                            ],
                          ),
                        ),
                      if (demo != null || detail != null) ...[
                        const SizedBox(height: 18),
                        livePanel(mobile),
                      ],
                      const SizedBox(height: 24),
                      Container(
                        decoration: BoxDecoration(
                          color: Palette.surface,
                          borderRadius: BorderRadius.circular(13),
                          border: Border.all(color: Palette.line),
                        ),
                        clipBehavior: Clip.antiAlias,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Padding(
                              padding: const EdgeInsets.fromLTRB(
                                18,
                                18,
                                18,
                                14,
                              ),
                              child: Wrap(
                                alignment: WrapAlignment.spaceBetween,
                                crossAxisAlignment: WrapCrossAlignment.center,
                                spacing: 16,
                                runSpacing: 14,
                                children: [
                                  Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      const Flexible(
                                        child: Text(
                                          'Mijozlar va nasiyalar',
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: TextStyle(
                                            fontWeight: FontWeight.w600,
                                            fontSize: 15,
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 9),
                                      Container(
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 7,
                                          vertical: 3,
                                        ),
                                        decoration: BoxDecoration(
                                          color: Palette.line,
                                          borderRadius: BorderRadius.circular(
                                            5,
                                          ),
                                        ),
                                        child: Text(
                                          '${ledger.entries.length}',
                                          style: const TextStyle(
                                            color: Palette.muted,
                                            fontSize: 11,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  SizedBox(
                                    width: math.min(270, width - 36),
                                    height: 38,
                                    child: TextField(
                                      controller: search,
                                      onChanged: (_) =>
                                          setState(() => page = 0),
                                      style: const TextStyle(fontSize: 12),
                                      decoration: InputDecoration(
                                        hintText: 'Mijoz yoki raqamni qidirish',
                                        prefixIcon: const Icon(
                                          Icons.search_rounded,
                                          size: 18,
                                        ),
                                        contentPadding:
                                            const EdgeInsets.symmetric(
                                              horizontal: 12,
                                            ),
                                        suffixIcon: search.text.isEmpty
                                            ? null
                                            : IconButton(
                                                tooltip: 'Qidiruvni tozalash',
                                                icon: const Icon(
                                                  Icons.close,
                                                  size: 16,
                                                ),
                                                onPressed: () => setState(() {
                                                  search.clear();
                                                  page = 0;
                                                }),
                                              ),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            SingleChildScrollView(
                              scrollDirection: Axis.horizontal,
                              padding: const EdgeInsets.fromLTRB(18, 0, 18, 14),
                              child: Row(
                                children: [
                                  for (final f in LedgerFilter.values)
                                    Padding(
                                      padding: const EdgeInsets.only(right: 6),
                                      child: _FilterTab(
                                        label: switch (f) {
                                          LedgerFilter.all => 'Barchasi',
                                          LedgerFilter.waiting => 'Kutilmoqda',
                                          LedgerFilter.promised =>
                                            'Va’da berdi',
                                          LedgerFilter.paid => 'To‘landi',
                                        },
                                        count: ledger.entries
                                            .map(overlay)
                                            .where((e) => e.matches(f, ''))
                                            .length,
                                        selected: f == filter,
                                        onTap: () => setState(() {
                                          filter = f;
                                          page = 0;
                                        }),
                                      ),
                                    ),
                                ],
                              ),
                            ),
                            const Divider(),
                            if (visible.isEmpty)
                              Padding(
                                padding: const EdgeInsets.all(32),
                                child: Column(
                                  children: [
                                    const Icon(
                                      Icons.manage_search_outlined,
                                      size: 32,
                                      color: Palette.muted,
                                    ),
                                    const SizedBox(height: 12),
                                    Text(
                                      search.text.isNotEmpty
                                          ? 'Qidiruv bo‘yicha mijoz topilmadi'
                                          : 'Bu holatdagi mijozlar hozircha yo‘q',
                                    ),
                                    const SizedBox(height: 5),
                                    const Text(
                                      'Filtrni o‘zgartiring yoki yangi mijoz qo‘shing.',
                                      style: TextStyle(
                                        color: Palette.muted,
                                        fontSize: 12,
                                      ),
                                    ),
                                  ],
                                ),
                              )
                            else if (mobile)
                              ...visible.map(mobileRow)
                            else
                              SingleChildScrollView(
                                scrollDirection: Axis.horizontal,
                                child: SizedBox(
                                  width: math.max(width - 2, 1060),
                                  child: Column(
                                    children: [
                                      tableHeader(),
                                      ...visible.map(desktopRow),
                                    ],
                                  ),
                                ),
                              ),
                            const Divider(),
                            Padding(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 16,
                                vertical: 9,
                              ),
                              child: Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      entries.isEmpty
                                          ? '0 ta mijoz'
                                          : '${selectedPage * size + 1}–${math.min((selectedPage + 1) * size, entries.length)} / ${entries.length} ta mijoz',
                                      style: const TextStyle(
                                        fontSize: 11,
                                        color: Palette.muted,
                                      ),
                                    ),
                                  ),
                                  if (!mobile)
                                    TextButton(
                                      onPressed: widget.showCustomers,
                                      child: const Text(
                                        'To‘liq ro‘yxat',
                                        style: TextStyle(fontSize: 12),
                                      ),
                                    ),
                                  IconButton(
                                    tooltip: 'Oldingi sahifa',
                                    onPressed: selectedPage > 0
                                        ? () => setState(
                                            () => page = selectedPage - 1,
                                          )
                                        : null,
                                    icon: const Icon(
                                      Icons.chevron_left_rounded,
                                      size: 20,
                                    ),
                                  ),
                                  Text(
                                    '${selectedPage + 1} / $pages',
                                    style: const TextStyle(
                                      fontSize: 11,
                                      color: Palette.muted,
                                    ),
                                  ),
                                  IconButton(
                                    tooltip: 'Keyingi sahifa',
                                    onPressed: selectedPage + 1 < pages
                                        ? () => setState(
                                            () => page = selectedPage + 1,
                                          )
                                        : null,
                                    icon: const Icon(
                                      Icons.chevron_right_rounded,
                                      size: 20,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.only(top: 14),
                        child: Text(
                          'Shu oy tasdiqlangan sof tushum: ${formatMoney(ledger.received)}',
                          style: const TextStyle(
                            fontSize: 11,
                            color: Palette.muted,
                          ),
                        ),
                      ),
                      if (store
                              .rows('voice_handoffs')
                              .any((r) => integer(r['resolved']) == 0) ||
                          store
                              .rows('promises')
                              .any(
                                (r) =>
                                    text(r['note'])
                                        .startsWith('Telegram AI suhbati') &&
                                    ![
                                      'cancelled',
                                      'fulfilled',
                                    ].contains(r['status']),
                              ))
                        Padding(
                          padding: const EdgeInsets.only(top: 20),
                          child: ExpansionTile(
                            title: const Text(
                              'AI vazifalari va kelishuvlar',
                              style: TextStyle(fontSize: 14),
                            ),
                            initiallyExpanded: store
                                .rows('voice_handoffs')
                                .any((r) => integer(r['resolved']) == 0),
                            children: [
                              Padding(
                                padding: const EdgeInsets.all(16),
                                child: VoiceDashboard(
                                  store: store,
                                  openCall: (id) => openVoice(id),
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      );
    },
  );

  Widget cell(int flex, Widget child) => Expanded(
    flex: flex,
    child: Padding(padding: const EdgeInsets.only(right: 12), child: child),
  );
  Widget tableHeader() => Container(
    color: Palette.background.withValues(alpha: .45),
    padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
    child: DefaultTextStyle(
      style: const TextStyle(
        fontFamily: 'Inter',
        color: Palette.muted,
        fontSize: 10.5,
        fontWeight: FontWeight.w500,
      ),
      child: Row(
        children: [
          cell(23, const Text('Mijoz / kompaniya')),
          cell(18, const Text('Telefon / Telegram')),
          cell(
            18,
            InkWell(
              onTap: () => setState(() => descending = !descending),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  const Flexible(
                    child: Text(
                      'Qarz summasi (UZS)',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Icon(
                    descending ? Icons.arrow_downward : Icons.arrow_upward,
                    size: 12,
                    color: Palette.muted,
                  ),
                ],
              ),
            ),
          ),
          cell(10, const Text('Kechikish')),
          cell(28, const Text('AI suhbat xulosasi')),
          cell(16, const Text('Status')),
          cell(10, const Text('Amal')),
        ],
      ),
    ),
  );
  Widget desktopRow(DebtorEntry row) => _StatusRow(
    key: ValueKey(row.id),
    stage: row.stage,
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 17),
      child: Row(
        children: [
          cell(
            23,
            InkWell(
              onTap: () => openCustomer(context, widget.store, row.id),
              child: Row(
                children: [
                  PersonAvatar(row.name, size: 33),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          row.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          text(row.customer['company']).isEmpty
                              ? 'Jismoniy shaxs'
                              : text(row.customer['company']),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Palette.muted,
                            fontSize: 10.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          cell(
            18,
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  prettyPhone(text(row.customer['phone'])),
                  style: const TextStyle(fontSize: 11.5),
                ),
                const SizedBox(height: 4),
                Text(
                  text(row.customer['telegram_username']).isEmpty
                      ? 'Telegram ulanmagan'
                      : '@${text(row.customer['telegram_username']).replaceFirst('@', '')}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Palette.muted, fontSize: 10.5),
                ),
              ],
            ),
          ),
          cell(
            18,
            Text(
              formatMoney(row.balance, unit: false),
              textAlign: TextAlign.right,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
            ),
          ),
          cell(
            10,
            Text(
              row.overdueDays > 0 ? '${row.overdueDays} kun' : '—',
              style: TextStyle(
                color: row.overdueDays > 0 ? Palette.red : Palette.muted,
                fontSize: 11.5,
              ),
            ),
          ),
          cell(
            28,
            Tooltip(
              message: row.summary,
              child: Text(
                row.summary,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 11.5,
                  height: 1.5,
                  color: Palette.muted,
                ),
              ),
            ),
          ),
          cell(
            16,
            Align(
              alignment: Alignment.centerLeft,
              child: _StageBadge(stage: row.stage, demo: demo?.id == row.id),
            ),
          ),
          cell(10, actions(row)),
        ],
      ),
    ),
  );
  Widget actions(DebtorEntry row) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      SizedBox(
        width: 30,
        height: 32,
        child: IconButton(
          padding: EdgeInsets.zero,
          tooltip: demoBusiness ? 'Demo qo‘ng‘iroq' : 'Qo‘ng‘iroqni tayyorlash',
          onPressed:
              widget.store.canEdit &&
                  row.balance > 0 &&
                  (connection['ready'] == true || demoBusiness)
              ? () => reviewCall(row)
              : null,
          icon: const Icon(Icons.call_outlined, size: 16),
        ),
      ),
      const Tooltip(
        message: 'Click / Payme integratsiyasi rejada',
        child: SizedBox(
          width: 26,
          height: 32,
          child: Icon(Icons.link_off_rounded, size: 16, color: Palette.muted),
        ),
      ),
    ],
  );
  Widget mobileRow(DebtorEntry row) => _StatusRow(
    key: ValueKey(row.id),
    stage: row.stage,
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              PersonAvatar(row.name, size: 34),
              const SizedBox(width: 10),
              Expanded(
                child: InkWell(
                  onTap: () => openCustomer(context, widget.store, row.id),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        row.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      Text(
                        prettyPhone(text(row.customer['phone'])),
                        style: const TextStyle(
                          fontSize: 11,
                          color: Palette.muted,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              actions(row),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    child: Text(
                      formatMoney(row.balance),
                      style: const TextStyle(
                        fontSize: 21,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              _StageBadge(stage: row.stage, demo: demo?.id == row.id),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            row.summary,
            style: const TextStyle(
              color: Palette.muted,
              fontSize: 12,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 16,
            runSpacing: 6,
            children: [
              Text(
                row.overdueDays > 0
                    ? '${row.overdueDays} kun kechikkan'
                    : 'Muddati o‘tmagan',
                style: TextStyle(
                  fontSize: 10.5,
                  color: row.overdueDays > 0 ? Palette.red : Palette.muted,
                ),
              ),
              const Text(
                'Click / Payme · Rejada',
                style: TextStyle(fontSize: 10.5, color: Palette.muted),
              ),
            ],
          ),
        ],
      ),
    ),
  );

  Widget livePanel(bool mobile) {
    final simulated = demo != null;
    final active = simulated ? !paused && !finished : isVoiceActive(detail!);
    final name = simulated
        ? demo!.name
        : text((detail?['brief'] as Map?)?['customer']);
    final phone = simulated
        ? text(demo!.customer['phone'])
        : text(
            widget.store.find(
              'customers',
              text(detail?['customer_id']),
            )?['phone'],
          ).isNotEmpty
        ? text(
            widget.store.find(
              'customers',
              text(detail?['customer_id']),
            )?['phone'],
          )
        : '@${text(detail?['target'])}';
    final amount = simulated
        ? demo!.balance
        : widget.store
              .rows('debts')
              .where((d) => d['id'] == detail?['debt_id'])
              .fold<int>(0, (sum, d) => sum + integer(d['balance']));
    final transcript = simulated
        ? script
              .take(step)
              .map(
                (m) => <String, dynamic>{
                  'role': m.$1 ? 'assistant' : 'user',
                  'text': m.$2,
                },
              )
              .toList()
        : (detail?['transcript'] as List? ?? [])
              .map((m) => Map<String, dynamic>.from(m as Map))
              .toList();
    final messages = transcript
        .skip(math.max(0, transcript.length - 2))
        .toList();
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Palette.blueSoft,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Palette.blue.withValues(alpha: .35)),
        boxShadow: [
          BoxShadow(color: Palette.blue.withValues(alpha: .06), blurRadius: 28),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: Palette.blue.withValues(alpha: .16),
                  borderRadius: BorderRadius.circular(9),
                ),
                child: const Icon(
                  Icons.graphic_eq_rounded,
                  color: Palette.blue,
                  size: 21,
                ),
              ),
              const SizedBox(width: 11),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      simulated
                          ? 'Demo simulyatsiya · ${finished
                                ? 'yakunlandi'
                                : paused
                                ? 'pauza'
                                : 'AI gaplashmoqda'}'
                          : active
                          ? 'Jonli suhbat · AI gaplashmoqda'
                          : 'AI suhbat yakunlandi',
                      style: const TextStyle(
                        color: Palette.blue,
                        fontSize: 11.5,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      '$name · ${prettyPhone(phone)}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
              if (!mobile)
                SizedBox(
                  width: 120,
                  height: 34,
                  child: _VoiceWave(active: active),
                ),
              if (simulated)
                IconButton(
                  tooltip: finished
                      ? 'Demoni qayta boshlash'
                      : paused
                      ? 'Demoni davom ettirish'
                      : 'Demoni pauza qilish',
                  onPressed: () {
                    if (finished) {
                      startDemo(demo);
                    } else {
                      setState(() => paused = !paused);
                      if (paused) {
                        demoTimer?.cancel();
                      } else {
                        tick();
                      }
                    }
                  },
                  icon: Icon(
                    finished
                        ? Icons.replay_rounded
                        : paused
                        ? Icons.play_arrow_rounded
                        : Icons.pause_rounded,
                    size: 19,
                  ),
                ),
              IconButton(
                tooltip: simulated ? 'Demoni yopish' : 'Suhbat panelini yopish',
                onPressed: simulated
                    ? closeDemo
                    : active
                    ? null
                    : () => setState(() => detail = null),
                icon: const Icon(Icons.close_rounded, size: 19),
              ),
            ],
          ),
          const SizedBox(height: 11),
          Text(
            simulated
                ? 'Qarz: ${formatMoney(amount)} · Demo hisob-kitoblarni o‘zgartirmaydi'
                : 'Qarz: ${formatMoney(amount)} · Suhbat matni avtomatik yangilanadi',
            style: const TextStyle(fontSize: 10.5, color: Palette.muted),
          ),
          if (messages.isNotEmpty) ...[
            const SizedBox(height: 14),
            if (mobile)
              ...messages.map(
                (m) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _TranscriptBubble(message: m),
                ),
              )
            else
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (var i = 0; i < messages.length; i++) ...[
                    if (i > 0) const SizedBox(width: 12),
                    Expanded(child: _TranscriptBubble(message: messages[i])),
                  ],
                ],
              ),
          ],
          if (simulated && step >= 5)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(
                'Demo natijasi: ${formatMoney(amount ~/ 2)} · ertaga 14:00 gacha va’da',
                style: const TextStyle(color: Palette.teal, fontSize: 12),
              ),
            ),
          if (!simulated)
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: () => openVoice(text(detail?['id'])),
                child: const Text('Suhbatni to‘liq ko‘rish'),
              ),
            ),
        ],
      ),
    );
  }
}

String prettyPhone(String phone) {
  final digits = phone.replaceAll(RegExp(r'\D'), '');
  if (digits.length != 12 || !digits.startsWith('998')) return phone;
  return '+998 ${digits.substring(3, 5)} ${digits.substring(5, 8)}-${digits.substring(8, 10)}-${digits.substring(10)}';
}

Color stageColor(DebtStage s) => switch (s) {
  DebtStage.active || DebtStage.promised => Palette.blue,
  DebtStage.paid => Palette.teal,
  DebtStage.review => Palette.amber,
  _ => Palette.muted,
};

class _KpiCard extends StatelessWidget {
  const _KpiCard({
    required this.width,
    required this.label,
    required this.value,
    required this.icon,
    required this.footer,
    this.unit,
    this.accent = Palette.ink,
    this.footerColor = Palette.muted,
    this.tooltip,
    this.live = false,
  });
  final double width;
  final String label, value, footer;
  final String? unit, tooltip;
  final Color accent, footerColor;
  final IconData icon;
  final bool live;
  @override
  Widget build(BuildContext context) => Container(
    width: width,
    height: 137,
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: Palette.surface,
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: Palette.line),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 11.5, color: Palette.muted),
              ),
            ),
            if (tooltip != null)
              Tooltip(
                message: tooltip,
                child: const Icon(
                  Icons.info_outline,
                  size: 14,
                  color: Palette.muted,
                ),
              )
            else
              Icon(icon, size: 17, color: accent.withValues(alpha: .75)),
          ],
        ),
        const SizedBox(height: 13),
        Expanded(
          child: Align(
            alignment: Alignment.centerLeft,
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.baseline,
                textBaseline: TextBaseline.alphabetic,
                children: [
                  Text(
                    value,
                    style: TextStyle(
                      fontSize: 30,
                      fontWeight: FontWeight.w600,
                      color: accent,
                      letterSpacing: -1,
                    ),
                  ),
                  if (unit != null)
                    Text(
                      ' $unit',
                      style: const TextStyle(
                        color: Palette.muted,
                        fontSize: 13,
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            if (live) ...[
              const SizedBox(
                width: 18,
                height: 14,
                child: _VoiceWave(active: true),
              ),
              const SizedBox(width: 6),
            ],
            Expanded(
              child: Text(
                footer,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: footerColor, fontSize: 10.5),
              ),
            ),
          ],
        ),
      ],
    ),
  );
}

class _Dot extends StatelessWidget {
  const _Dot({required this.color});
  final Color color;
  @override
  Widget build(BuildContext context) => Container(
    width: 6,
    height: 6,
    decoration: BoxDecoration(color: color, shape: BoxShape.circle),
  );
}

class _FilterTab extends StatelessWidget {
  const _FilterTab({
    required this.label,
    required this.count,
    required this.selected,
    required this.onTap,
  });
  final String label;
  final int count;
  final bool selected;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Semantics(
    selected: selected,
    button: true,
    child: Material(
      color: selected ? const Color(0xFF253044) : Colors.transparent,
      borderRadius: BorderRadius.circular(7),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(7),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
          child: Row(
            children: [
              Text(
                label,
                style: TextStyle(
                  fontSize: 11.5,
                  color: selected ? Palette.ink : Palette.muted,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                ),
              ),
              const SizedBox(width: 6),
              Text(
                '$count',
                style: const TextStyle(fontSize: 10, color: Palette.muted),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

class _StageBadge extends StatelessWidget {
  const _StageBadge({required this.stage, required this.demo});
  final DebtStage stage;
  final bool demo;
  @override
  Widget build(BuildContext context) {
    final color = stageColor(stage);
    return AnimatedSwitcher(
      duration: MediaQuery.disableAnimationsOf(context)
          ? Duration.zero
          : const Duration(milliseconds: 240),
      child: Container(
        key: ValueKey('$stage$demo'),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        decoration: BoxDecoration(
          color: color.withValues(alpha: .1),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: color.withValues(alpha: .15)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _Dot(color: color),
            const SizedBox(width: 5),
            Flexible(
              child: Text(
                '${demo ? 'Demo · ' : ''}${stageLabel(stage)}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 10,
                  color: color,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatusRow extends StatefulWidget {
  const _StatusRow({super.key, required this.stage, required this.child});
  final DebtStage stage;
  final Widget child;
  @override
  State<_StatusRow> createState() => _StatusRowState();
}

class _StatusRowState extends State<_StatusRow> {
  bool highlight = false;
  Timer? timer;
  @override
  void didUpdateWidget(covariant _StatusRow oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.stage != widget.stage) {
      highlight = true;
      timer?.cancel();
      timer = Timer(const Duration(milliseconds: 1500), () {
        if (mounted) setState(() => highlight = false);
      });
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedContainer(
    duration: MediaQuery.disableAnimationsOf(context)
        ? Duration.zero
        : const Duration(milliseconds: 450),
    decoration: BoxDecoration(
      color: highlight
          ? stageColor(widget.stage).withValues(alpha: .09)
          : Colors.transparent,
      border: const Border(bottom: BorderSide(color: Palette.line, width: .6)),
    ),
    child: widget.child,
  );
}

class _TranscriptBubble extends StatelessWidget {
  const _TranscriptBubble({required this.message});
  final Json message;
  @override
  Widget build(BuildContext context) {
    final ai = [
      'assistant',
      'ai',
      'model',
      'agent',
    ].contains(message['role'] ?? message['speaker']);
    return AnimatedSize(
      duration: MediaQuery.disableAnimationsOf(context)
          ? Duration.zero
          : const Duration(milliseconds: 240),
      alignment: Alignment.topLeft,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: ai
              ? Palette.blue.withValues(alpha: .1)
              : Palette.background.withValues(alpha: .55),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              ai ? 'Tushum AI' : 'Mijoz',
              style: TextStyle(
                fontSize: 10,
                color: ai ? Palette.blue : Palette.muted,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 5),
            Text(
              text(message['text']),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 11.5, height: 1.5),
            ),
          ],
        ),
      ),
    );
  }
}

class _VoiceWave extends StatefulWidget {
  const _VoiceWave({required this.active});
  final bool active;
  @override
  State<_VoiceWave> createState() => _VoiceWaveState();
}

class _VoiceWaveState extends State<_VoiceWave>
    with SingleTickerProviderStateMixin {
  late final controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  );
  void update() {
    if (widget.active && !MediaQuery.disableAnimationsOf(context)) {
      if (!controller.isAnimating) controller.repeat();
    } else {
      controller.stop();
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    update();
  }

  @override
  void didUpdateWidget(covariant _VoiceWave oldWidget) {
    super.didUpdateWidget(oldWidget);
    update();
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: AnimatedBuilder(
      animation: controller,
      builder: (_, _) =>
          CustomPaint(painter: _WavePainter(controller.value, widget.active)),
    ),
  );
}

class _WavePainter extends CustomPainter {
  _WavePainter(this.phase, this.active);
  final double phase;
  final bool active;
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = Palette.blue
      ..strokeWidth = math.max(1, size.width / 45)
      ..strokeCap = StrokeCap.round;
    for (var i = 0; i < 20; i++) {
      final h = active
          ? 3 +
                (math.sin(i * .83 + phase * math.pi * 2).abs() * .72 +
                        math.sin(i * .4).abs() * .28) *
                    (size.height - 5)
          : 3.0;
      final x = (i + .5) * size.width / 20;
      canvas.drawLine(
        Offset(x, (size.height - h) / 2),
        Offset(x, (size.height + h) / 2),
        p,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _WavePainter oldDelegate) =>
      phase != oldDelegate.phase || active != oldDelegate.active;
}
