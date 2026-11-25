import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import 'core.dart';
import 'ui.dart';
import 'app.dart' show ContentList;
import 'customers.dart';
import 'settings.dart' show downloadFile;

class ActivityPage extends StatefulWidget {
  const ActivityPage({super.key, required this.store, this.customerId});
  final AppStore store;
  final String? customerId;
  @override
  State<ActivityPage> createState() => _ActivityPageState();
}

class _ActivityPageState extends State<ActivityPage> {
  List<Json> items = [];
  String filter = '';
  String? next;
  bool loading = false;
  String? error;
  int requestVersion = 0;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load({bool more = false}) async {
    if (more && loading) return;
    final version = ++requestVersion;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      if (widget.store.offline) {
        final cached = widget.store
            .rows('events')
            .where(
              (row) =>
                  (filter.isEmpty || row['kind'] == filter) &&
                  (widget.customerId == null ||
                      row['customer_id'] == widget.customerId),
            )
            .toList();
        if (mounted && version == requestVersion) {
          setState(() {
            items = cached;
            next = null;
          });
        }
      } else {
        final uri = Uri(
          path: '/api/activity',
          queryParameters: {
            if (filter.isNotEmpty) 'kind': filter,
            if (widget.customerId != null) 'customer_id': widget.customerId!,
            if (more && next != null) 'before': next!,
          },
        );
        final data = await widget.store.api.request(uri.toString()) as Map;
        if (mounted && version == requestVersion) {
          setState(() {
            final received = (data['items'] as List)
                .map((row) => Map<String, dynamic>.from(row as Map))
                .toList();
            items = more ? [...items, ...received] : received;
            next = data['next'] as String?;
          });
        }
      }
    } on ApiError catch (failure) {
      if (mounted && version == requestVersion) {
        setState(() => error = failure.message);
      }
    } finally {
      if (mounted && version == requestVersion) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final content = ContentList(
      onRefresh: () => load(),
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Faoliyat tarixi',
                style: Theme.of(context).textTheme.headlineLarge,
              ),
            ),
            IconButton(
              tooltip: 'Tarixni yangilash',
              onPressed: loading ? null : () => load(),
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        const SizedBox(height: 8),
        const Text(
          'Kim, qachon va qanday o‘zgartirish kiritganini kuzating.',
          style: TextStyle(color: Palette.muted),
        ),
        const SizedBox(height: 20),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final entry in const {
                '': 'Barchasi',
                'payment': 'To‘lovlar',
                'refund': 'Qaytarimlar',
                'debt': 'Nasiyalar',
                'promise': 'Va’dalar',
                'dispute': 'E’tirozlar',
                'note': 'Izohlar',
                'team': 'Jamoa',
              }.entries)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(entry.value),
                    selected: filter == entry.key,
                    onSelected: (_) {
                      setState(() => filter = entry.key);
                      load();
                    },
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        if (widget.store.offline)
          const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: Text(
              'Qurilmada saqlangan so‘nggi amallar',
              style: TextStyle(color: Palette.amber),
            ),
          ),
        if (error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Text(error!, style: const TextStyle(color: Palette.red)),
          ),
        if (items.isEmpty && !loading)
          const Surface(
            child: EmptyState(
              title: 'Amal topilmadi',
              message: 'Tanlangan turdagi amallar shu yerda ko‘rinadi.',
              icon: Icons.receipt_long_outlined,
            ),
          ),
        if (items.isNotEmpty)
          Surface(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                for (final item in items)
                  ActivityRow(
                    item,
                    onTap: text(item['customer_id']).isEmpty
                        ? null
                        : () => openCustomer(
                            context,
                            widget.store,
                            text(item['customer_id']),
                          ),
                  ),
              ],
            ),
          ),
        if (loading)
          const Padding(
            padding: EdgeInsets.all(24),
            child: Center(child: CircularProgressIndicator()),
          ),
        if (next != null && !loading)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: OutlinedButton(
              onPressed: () => load(more: true),
              child: const Text('Oldingi amallar'),
            ),
          ),
      ],
    );
    return widget.customerId == null
        ? content
        : Scaffold(
            appBar: AppBar(title: const Text('Mijoz tarixi')),
            body: content,
          );
  }
}

class ReportsPage extends StatefulWidget {
  const ReportsPage({super.key, required this.store});
  final AppStore store;
  @override
  State<ReportsPage> createState() => _ReportsPageState();
}

class _ReportsPageState extends State<ReportsPage> {
  Json? report;
  late String start;
  late String end;
  String period = 'month';
  bool loading = false;
  String? error;
  int requestVersion = 0;
  @override
  void initState() {
    super.initState();
    end = widget.store.currentDay;
    start = '${end.substring(0, 7)}-01';
    load();
  }

  String? loadedWorkspaceVersion;

  @override
  void didUpdateWidget(covariant ReportsPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    final version = text(widget.store.data['server_time']);
    if (loadedWorkspaceVersion != version) {
      load();
    }
  }

  Future<void> load() async {
    loadedWorkspaceVersion = text(widget.store.data['server_time']);
    final version = ++requestVersion;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = await widget.store.api.request(
        '/api/reports?start=$start&end=$end',
      ) as Map;
      if (mounted && version == requestVersion) {
        setState(() => report = Map<String, dynamic>.from(result));
      }
    } on ApiError catch (failure) {
      if (mounted && version == requestVersion) {
        setState(() {
          report = null;
          error = failure.message;
        });
      }
    } finally {
      if (mounted && version == requestVersion) setState(() => loading = false);
    }
  }

  Future<void> changePeriod(String value) async {
    final today = DateTime.parse(widget.store.currentDay);
    if (value == 'custom') {
      final selected = await showDateRangePicker(
        context: context,
        firstDate: DateTime(2020),
        lastDate: today,
        initialDateRange: DateTimeRange(
          start: DateTime.parse(start),
          end: DateTime.parse(end),
        ),
        helpText: 'Hisobot davri',
        saveText: 'Tanlash',
      );
      if (selected == null || !mounted) return;
      start = selected.start.toIso8601String().substring(0, 10);
      end = selected.end.toIso8601String().substring(0, 10);
    } else {
      end = widget.store.currentDay;
      start = value == 'week'
          ? today
                .subtract(const Duration(days: 6))
                .toIso8601String()
                .substring(0, 10)
          : '${end.substring(0, 7)}-01';
    }
    setState(() => period = value);
    await load();
  }

  Widget summaryGrid(Json data) => LayoutBuilder(
    builder: (context, constraints) {
      final columns = constraints.maxWidth >= 650 ? 3 : 2;
      final width = (constraints.maxWidth - 12 * (columns - 1)) / columns;
      final values = [
        AmountLabel(
          label: 'Qabul qilingan',
          amount: integer(data['gross_received']),
          color: Palette.green,
        ),
        AmountLabel(
          label: 'Qaytarimlar',
          amount: integer(data['refunded']),
          color: Palette.red,
        ),
        AmountLabel(
          label: 'Sof tushum',
          amount: integer(data['net_received']),
          color: Palette.teal,
        ),
      ];
      return Wrap(
        spacing: 12,
        runSpacing: 12,
        children: [
          for (final value in values)
            SizedBox(
              width: width,
              child: Surface(child: value),
            ),
        ],
      );
    },
  );
  Widget amountBars(Map values, {bool methods = false}) {
    final maximum = values.values.fold<int>(
      1,
      (current, value) => math.max(current, integer(value).abs()),
    );
    return Surface(
      child: Column(
        children: [
          for (final entry in values.entries)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          methods
                              ? methodLabel(text(entry.key))
                              : text(entry.key),
                          style: const TextStyle(fontSize: 13),
                        ),
                      ),
                      Text(
                        formatMoney(entry.value),
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  LayoutBuilder(
                    builder: (context, constraints) => Container(
                      height: 7,
                      width: constraints.maxWidth,
                      decoration: BoxDecoration(
                        color: Palette.line,
                        borderRadius: BorderRadius.circular(5),
                      ),
                      alignment: Alignment.centerLeft,
                      child: FractionallySizedBox(
                        widthFactor: integer(entry.value).abs() / maximum,
                        child: Container(
                          decoration: BoxDecoration(
                            color: integer(entry.value) < 0
                                ? Palette.red
                                : Palette.teal,
                            borderRadius: BorderRadius.circular(5),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget trendChart(List rows) {
    if (rows.isEmpty) {
      return const Surface(
        child: EmptyState(
          title: 'Bu davrda tushum yo‘q',
          message: 'Qayd etilgan to‘lovlar va qaytarimlar grafikda aks etadi.',
          icon: Icons.bar_chart_rounded,
        ),
      );
    }
    final maximum = rows.fold<int>(
      1,
      (current, row) => math.max(current, integer(row['amount']).abs()),
    );
    return Surface(
      child: SizedBox(
        height: 206,
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              for (final row in rows)
                Tooltip(
                  message:
                      '${displayDate(row['date'])} · ${formatMoney(row['amount'])}',
                  child: SizedBox(
                    width: 85,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        FittedBox(
                          child: Text(
                            formatMoney(row['amount'], unit: false),
                            style: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        const SizedBox(height: 8),
                        Container(
                          width: 24,
                          height: math.max(
                            3,
                            132 * integer(row['amount']).abs() / maximum,
                          ),
                          decoration: BoxDecoration(
                            color: integer(row['amount']) < 0
                                ? Palette.red
                                : Palette.teal,
                            borderRadius: const BorderRadius.vertical(
                              top: Radius.circular(5),
                            ),
                          ),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          displayDate(row['date']).split(' ').first,
                          style: const TextStyle(
                            fontSize: 11,
                            color: Palette.muted,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final data = report;
    return ContentList(
      onRefresh: load,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Hisobot',
                style: Theme.of(context).textTheme.headlineLarge,
              ),
            ),
            IconButton(
              tooltip: 'Hisobotni yangilash',
              onPressed: loading ? null : load,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          '${displayDate(start)} — ${displayDate(end)}',
          style: const TextStyle(color: Palette.muted),
        ),
        const SizedBox(height: 20),
        Wrap(
          spacing: 8,
          children: [
            for (final entry in const {
              'week': '7 kun',
              'month': 'Shu oy',
              'custom': 'Davr tanlash',
            }.entries)
              ChoiceChip(
                label: Text(entry.value),
                selected: period == entry.key,
                onSelected: loading ? null : (_) => changePeriod(entry.key),
              ),
          ],
        ),
        const SizedBox(height: 22),
        if (loading) const LinearProgressIndicator(),
        if (error != null)
          Surface(
            child: Column(
              children: [
                Text(error!, style: const TextStyle(color: Palette.red)),
                const SizedBox(height: 12),
                OutlinedButton(
                  onPressed: load,
                  child: const Text('Qayta urinish'),
                ),
              ],
            ),
          ),
        if (data != null) ...[
          summaryGrid(data),
          const SizedBox(height: 16),
          Text(
            '${integer(data['payment_count'])} ta to‘lov · ${integer(data['fulfilled_promises'])}/${integer(data['promise_count'])} ta muddati shu davrga tushgan va’da hozir bajarilgan',
            style: const TextStyle(
              fontSize: 13,
              color: Palette.muted,
              height: 1.5,
            ),
          ),
          const SectionHeader('Kunlik sof tushum'),
          trendChart(data['trend'] as List),
          const SizedBox(height: 8),
          const Text(
            'Yashil ustun — sof tushum. Qizil ustun — qaytarim ustun kelgan kun.',
            style: TextStyle(color: Palette.muted, fontSize: 12),
          ),
          const SectionHeader('To‘lov usullari bo‘yicha sof tushum'),
          amountBars(data['methods'] as Map, methods: true),
          const SectionHeader('Hozirgi nasiya holati'),
          Surface(
            child: Row(
              children: [
                Expanded(
                  child: AmountLabel(
                    label: 'Jami qoldiq',
                    amount: integer(data['current_balance']),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: AmountLabel(
                    label: 'Kechikkan qoldiq',
                    amount: integer(data['current_overdue']),
                    color: Palette.red,
                  ),
                ),
              ],
            ),
          ),
          const SectionHeader('Hozirgi qoldiqning kechikish muddati'),
          amountBars(data['aging'] as Map),
        ],
        const SizedBox(height: 24),
        OutlinedButton.icon(
          onPressed: widget.store.offline
              ? null
              : () => downloadFile(
                  context,
                  widget.store,
                  '/api/export',
                  'tushum-hisobot-${widget.store.currentDay}.xlsx',
                ),
          icon: const Icon(Icons.file_download_outlined),
          label: const Text('Barcha yozuvlarni Excelga yuklash'),
        ),
      ],
    );
  }
}
