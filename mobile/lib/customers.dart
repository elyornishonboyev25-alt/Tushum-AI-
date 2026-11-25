import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import 'core.dart';
import 'ui.dart';
import 'forms.dart';
import 'app.dart' show ContentList;
import 'spreadsheet_import.dart';
import 'insights.dart' show ActivityPage;
import 'sms.dart';

String customerContact(Json customer) => text(customer['phone']).isNotEmpty
    ? text(customer['phone'])
    : text(customer['telegram_username']).isNotEmpty
    ? '@${text(customer['telegram_username'])}'
    : 'Kontakt kiritilmagan';

void openCustomer(BuildContext context, AppStore store, String id) {
  if (id.isEmpty) return;
  FocusManager.instance.primaryFocus?.unfocus();
  Navigator.push(
    context,
    MaterialPageRoute(
      builder: (_) => CustomerDetailPage(store: store, customerId: id),
    ),
  );
}

class CustomerRow extends StatelessWidget {
  const CustomerRow({super.key, required this.customer, required this.onTap});
  final Json customer;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => ListTile(
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
    leading: PersonAvatar(text(customer['name'])),
    title: Text(
      text(customer['name']),
      maxLines: 2,
      overflow: TextOverflow.ellipsis,
      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
    ),
    subtitle: Text(
      text(customer['company']).isEmpty
          ? customerContact(customer)
          : text(customer['company']),
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: const TextStyle(color: Palette.muted, fontSize: 12),
    ),
    trailing: SizedBox(
      width: 126,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              formatMoney(customer['balance']),
              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
            ),
          ),
          const SizedBox(height: 4),
          if (customer['disputed'] == true)
            const Text(
              'E’tiroz bor',
              style: TextStyle(color: Palette.amber, fontSize: 11),
            )
          else if (integer(customer['overdue']) > 0)
            const Text(
              'Muddati o‘tgan',
              style: TextStyle(color: Palette.red, fontSize: 11),
            )
          else
            Text(
              integer(customer['balance']) == 0
                  ? 'Qoldiq yo‘q'
                  : 'Muddat ichida',
              style: const TextStyle(color: Palette.muted, fontSize: 11),
            ),
        ],
      ),
    ),
    onTap: onTap,
  );
}

class CustomersPage extends StatefulWidget {
  const CustomersPage({super.key, required this.store});
  final AppStore store;
  @override
  State<CustomersPage> createState() => _CustomersPageState();
}

class _CustomersPageState extends State<CustomersPage> {
  String query = '';
  String filter = 'all';
  String sort = 'balance';
  int limit = 50;
  @override
  Widget build(BuildContext context) {
    final rows = widget.store.rows('customers').where((row) {
      final archived = integer(row['archived']) == 1;
      final matches =
          '${row['name']} ${row['phone']} ${row['company']} ${row['telegram_username']}'
              .toLowerCase()
              .contains(query.toLowerCase());
      final statusMatches = switch (filter) {
        'archive' => archived,
        'overdue' => !archived && integer(row['overdue']) > 0,
        'open' => !archived && integer(row['balance']) > 0,
        'clear' => !archived && integer(row['balance']) == 0,
        'dispute' => !archived && row['disputed'] == true,
        _ => !archived,
      };
      return matches && statusMatches;
    }).toList();
    rows.sort(
      (a, b) => sort == 'name'
          ? text(a['name'])
                .toLowerCase()
                .compareTo(text(b['name']).toLowerCase())
          : sort == 'recent'
          ? text(b['created_at']).compareTo(text(a['created_at']))
          : integer(b['balance']).compareTo(integer(a['balance'])),
    );
    return ContentList(
      onRefresh: () async {
        await widget.store.refresh();
      },
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Mijozlar',
                style: Theme.of(context).textTheme.headlineLarge,
              ),
            ),
            if (widget.store.canEdit)
              IconButton.filled(
                tooltip: 'Mijoz qo‘shish',
                onPressed: () => customerForm(context, widget.store),
                icon: const Icon(Icons.add),
              ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          '${rows.length} ta mijoz · ${formatMoney(rows.fold<int>(0, (sum, row) => sum + integer(row['balance'])))} qoldiq',
          style: const TextStyle(color: Palette.muted),
        ),
        const SizedBox(height: 20),
        TextField(
          decoration: const InputDecoration(
            hintText: 'Ism, telefon yoki korxona bo‘yicha qidirish',
            prefixIcon: Icon(Icons.search),
          ),
          onChanged: (value) => setState(() {
            query = value.trim();
            limit = 50;
          }),
        ),
        const SizedBox(height: 14),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final entry in const {
                'all': 'Barchasi',
                'open': 'Nasiya bor',
                'overdue': 'Muddati o‘tgan',
                'dispute': 'E’tirozli',
                'clear': 'Qoldiqsiz',
                'archive': 'Arxiv',
              }.entries)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: Text(entry.value),
                    selected: filter == entry.key,
                    onSelected: (_) => setState(() {
                      filter = entry.key;
                      limit = 50;
                    }),
                  ),
                ),
            ],
          ),
        ),
        Row(
          children: [
            const Expanded(
              child: Text('Saralash', style: TextStyle(color: Palette.muted)),
            ),
            DropdownButton<String>(
              value: sort,
              underline: const SizedBox(),
              items: const [
                DropdownMenuItem(
                  value: 'balance',
                  child: Text('Qoldiq bo‘yicha'),
                ),
                DropdownMenuItem(value: 'name', child: Text('Ism bo‘yicha')),
                DropdownMenuItem(
                  value: 'recent',
                  child: Text('Yangi mijozlar'),
                ),
              ],
              onChanged: (value) => setState(() => sort = value!),
            ),
            if (widget.store.canEdit)
              IconButton(
                tooltip: 'Excel import',
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => SpreadsheetImportPage(store: widget.store),
                  ),
                ),
                icon: const Icon(Icons.upload_file_outlined),
              ),
          ],
        ),
        if (rows.isEmpty)
          const Surface(
            child: EmptyState(
              title: 'Mijoz topilmadi',
              message: 'Qidiruv yoki filtrni o‘zgartiring. Yangi mijozni “+” orqali qo‘shishingiz mumkin.',
              icon: Icons.person_search_outlined,
            ),
          )
        else
          Surface(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                for (final row in rows.take(limit))
                  CustomerRow(
                    customer: row,
                    onTap: () =>
                        openCustomer(context, widget.store, text(row['id'])),
                  ),
              ],
            ),
          ),
        if (rows.length > limit)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: OutlinedButton(
              onPressed: () => setState(() => limit += 50),
              child: Text('Yana ko‘rsatish (${rows.length - limit})'),
            ),
          ),
      ],
    );
  }
}

class CustomerDetailPage extends StatefulWidget {
  const CustomerDetailPage({
    super.key,
    required this.store,
    required this.customerId,
  });
  final AppStore store;
  final String customerId;
  @override
  State<CustomerDetailPage> createState() => _CustomerDetailPageState();
}

class _CustomerDetailPageState extends State<CustomerDetailPage> {
  String section = 'debts';
  bool includeArchive = false;
  AppStore get store => widget.store;

  Future<void> customerAction(String action, Json customer) async {
    switch (action) {
      case 'edit':
        await customerForm(context, store, customer: customer);
      case 'note':
        await noteForm(context, store, widget.customerId);
      case 'archive':
        await confirmedMutation(
          context,
          store,
          '/api/customers/${widget.customerId}/archive',
          {'archived': integer(customer['archived']) == 0},
          title: integer(customer['archived']) == 0
              ? 'Mijozni arxivlash'
              : 'Mijozni tiklash',
          description: 'Mijozning nasiya va to‘lov tarixi saqlanadi. Ochiq qoldiq bo‘lsa, arxivlash uchun avval uni yoping.',
        );
      case 'copy':
        await Clipboard.setData(ClipboardData(text: customerContact(customer)));
        if (mounted) feedbackMessage(context, 'Kontakt nusxalandi');
    }
  }

  Future<void> debtAction(String action, Json debt) async {
    switch (action) {
      case 'edit':
        await debtForm(context, store, widget.customerId, debt: debt);
      case 'payment':
        await paymentForm(context, store, widget.customerId, debt: debt);
      case 'promise':
        await promiseForm(context, store, widget.customerId, debt: debt);
      case 'dispute':
        await disputeForm(context, store, debt);
      case 'archive':
        await confirmedMutation(
          context,
          store,
          '/api/debts/${debt['id']}/archive',
          {'archived': integer(debt['archived']) == 0},
          title: integer(debt['archived']) == 0
              ? 'Nasiyani arxivlash'
              : 'Nasiyani tiklash',
          description: 'Amal faoliyat tarixida saqlanadi. Arxivlash uchun nasiya qoldig‘i nol bo‘lishi kerak.',
        );
    }
  }

  Widget debtCard(Json debt) {
    final closed = integer(debt['balance']) == 0;
    final archived = integer(debt['archived']) == 1;
    final status = archived
        ? 'Arxiv'
        : closed
        ? 'Yopilgan'
        : debt['disputed'] == true
        ? 'E’tirozli'
        : debt['overdue'] == true
        ? 'Muddati o‘tgan'
        : 'Ochiq';
    final color = closed
        ? Palette.green
        : debt['overdue'] == true
        ? Palette.red
        : Palette.amber;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Surface(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    text(debt['title']),
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                if (store.canEdit &&
                    integer(
                          store.find(
                            'customers',
                            widget.customerId,
                          )?['archived'],
                        ) ==
                        0)
                  PopupMenuButton<String>(
                    tooltip: 'Nasiya amallari',
                    onSelected: (action) => debtAction(action, debt),
                    itemBuilder: (_) => [
                      if (!archived && !closed) ...[
                        const PopupMenuItem(
                          value: 'payment',
                          child: Text('To‘lov kiritish'),
                        ),
                        const PopupMenuItem(
                          value: 'promise',
                          child: Text('Va’da qo‘shish'),
                        ),
                        if (debt['disputed'] != true)
                          const PopupMenuItem(
                            value: 'dispute',
                            child: Text('E’tiroz qayd etish'),
                          ),
                      ],
                      if (!archived)
                        const PopupMenuItem(
                          value: 'edit',
                          child: Text('Tahrirlash'),
                        ),
                      if (closed)
                        PopupMenuItem(
                          value: 'archive',
                          child: Text(
                            archived ? 'Arxivdan tiklash' : 'Arxivlash',
                          ),
                        ),
                    ],
                  ),
              ],
            ),
            StatusTag(status, color: color),
            const SizedBox(height: 18),
            AmountLabel(
              label: 'Qolgan summa',
              amount: integer(debt['balance']),
              color: closed ? Palette.green : Palette.ink,
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 24,
              runSpacing: 8,
              children: [
                Text(
                  'Jami ${formatMoney(debt['amount'])}',
                  style: const TextStyle(color: Palette.muted, fontSize: 12),
                ),
                Text(
                  'To‘langan ${formatMoney(debt['paid'])}',
                  style: const TextStyle(color: Palette.green, fontSize: 12),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              'Berilgan ${displayDate(debt['issued_on'])}  ·  Muddat ${displayDate(debt['due_on'])}',
              style: const TextStyle(fontSize: 12, color: Palette.muted),
            ),
            if (text(debt['reference']).isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  'Hisob-faktura ${debt['reference']}',
                  style: const TextStyle(fontSize: 12, color: Palette.muted),
                ),
              ),
            if (text(debt['note']).isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Text(
                  text(debt['note']),
                  style: const TextStyle(fontSize: 13, height: 1.5),
                ),
              ),
            if (!closed && !archived && store.canEdit)
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: OutlinedButton.icon(
                  onPressed: () => paymentForm(
                    context,
                    store,
                    widget.customerId,
                    debt: debt,
                  ),
                  icon: const Icon(Icons.add, size: 18),
                  label: const Text('To‘lov kiritish'),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget paymentCard(Json payment) {
    final debt = store.find('debts', text(payment['debt_id']));
    final refunds = store
        .rows('refunds')
        .where((row) => row['payment_id'] == payment['id']);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Surface(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.south_west_rounded, color: Palette.green),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    formatMoney(payment['amount']),
                    style: const TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 19,
                      color: Palette.green,
                    ),
                  ),
                ),
                if (store.isOwner &&
                    store.canEdit &&
                    integer(payment['refunded']) < integer(payment['amount']))
                  PopupMenuButton<String>(
                    tooltip: 'To‘lov amallari',
                    onSelected: (_) => refundForm(context, store, payment),
                    itemBuilder: (_) => [
                      const PopupMenuItem(
                        value: 'refund',
                        child: Text('Qaytarim kiritish'),
                      ),
                    ],
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              '${methodLabel(text(payment['method']))} · ${displayDate(payment['paid_on'])}',
              style: const TextStyle(color: Palette.muted),
            ),
            const SizedBox(height: 6),
            Text(text(debt?['title']), style: const TextStyle(fontSize: 13)),
            if (text(payment['note']).isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(text(payment['note'])),
              ),
            const SizedBox(height: 6),
            Text(
              'Qayd etgan ${text(payment['recorded_by_name'])}',
              style: const TextStyle(fontSize: 12, color: Palette.muted),
            ),
            for (final refund in refunds)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(
                  'Qaytarim ${formatMoney(refund['amount'])} · ${displayDate(refund['refunded_on'])}\n${refund['reason']}',
                  style: const TextStyle(
                    fontSize: 13,
                    color: Palette.red,
                    height: 1.5,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget disputeCard(Json dispute) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Surface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          StatusTag(
            integer(dispute['resolved']) == 1 ? 'Hal etilgan' : 'Ochiq e’tiroz',
            color: integer(dispute['resolved']) == 1
                ? Palette.green
                : Palette.amber,
          ),
          const SizedBox(height: 12),
          Text(text(dispute['reason']), style: const TextStyle(height: 1.5)),
          const SizedBox(height: 8),
          Text(
            text(store.find('debts', text(dispute['debt_id']))?['title']),
            style: const TextStyle(color: Palette.muted, fontSize: 12),
          ),
          if (text(dispute['resolution']).isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(
                'Yechim — ${dispute['resolution']}',
                style: const TextStyle(color: Palette.green),
              ),
            ),
          if (integer(dispute['resolved']) == 0 && store.canEdit)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: OutlinedButton(
                onPressed: () => resolveDisputeForm(context, store, dispute),
                child: const Text('Yechimni qayd etish'),
              ),
            ),
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: store,
    builder: (context, _) {
      final customer = store.find('customers', widget.customerId);
      if (customer == null) {
        return Scaffold(
          appBar: AppBar(),
          body: const EmptyState(
            title: 'Mijoz ochilmadi',
            message: 'Ish maydoniga qaytib, ma’lumotlarni yangilang.',
          ),
        );
      }
      final debts = store
          .rows('debts')
          .where((row) => row['customer_id'] == widget.customerId)
          .toList();
      final debtIds = debts.map((row) => row['id']).toSet();
      final payments = store
          .rows('payments')
          .where((row) => debtIds.contains(row['debt_id']))
          .toList();
      final promises = store
          .rows('promises')
          .where((row) => row['customer_id'] == widget.customerId)
          .toList();
      final disputes = store
          .rows('disputes')
          .where((row) => debtIds.contains(row['debt_id']))
          .toList();
      final events = store
          .rows('events')
          .where((row) => row['customer_id'] == widget.customerId)
          .toList();
      final archived = integer(customer['archived']) == 1;
      return Scaffold(
        appBar: AppBar(
          title: const Text('Mijoz kartasi'),
          actions: [
            PopupMenuButton<String>(
              tooltip: 'Mijoz amallari',
              onSelected: (action) => customerAction(action, customer),
              itemBuilder: (_) => [
                const PopupMenuItem(
                  value: 'copy',
                  child: Text('Kontaktni nusxalash'),
                ),
                if (store.canEdit) ...[
                  const PopupMenuItem(
                    value: 'edit',
                    child: Text('Ma’lumotlarni tahrirlash'),
                  ),
                  const PopupMenuItem(
                    value: 'note',
                    child: Text('Izoh qo‘shish'),
                  ),
                  PopupMenuItem(
                    value: 'archive',
                    child: Text(
                      archived ? 'Arxivdan tiklash' : 'Mijozni arxivlash',
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
        body: ContentList(
          onRefresh: () async {
            await store.refresh();
          },
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                PersonAvatar(text(customer['name']), size: 56),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        text(customer['name']),
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 5),
                      Text(
                        customerContact(customer),
                        style: const TextStyle(color: Palette.muted),
                      ),
                      if (text(customer['company']).isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 5),
                          child: Text(
                            text(customer['company']),
                            style: const TextStyle(color: Palette.muted),
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 22),
            Surface(
              child: Row(
                children: [
                  Expanded(
                    child: AmountLabel(
                      label: 'Jami qoldiq',
                      amount: integer(customer['balance']),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: AmountLabel(
                      label: 'Muddati o‘tgan',
                      amount: integer(customer['overdue']),
                      color: Palette.red,
                    ),
                  ),
                ],
              ),
            ),
            if (archived)
              const Padding(
                padding: EdgeInsets.only(top: 14),
                child: StatusTag('Arxivdagi mijoz'),
              ),
            if (text(customer['note']).isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: Text(
                  text(customer['note']),
                  style: const TextStyle(color: Palette.muted, height: 1.5),
                ),
              ),
            const SizedBox(height: 12),
            Text(
              integer(customer['contact_allowed']) == 1
                  ? 'Eslatma uchun bog‘lanishga rozilik qayd etilgan'
                  : 'Bog‘lanishga rozilik berilmagan',
              style: const TextStyle(fontSize: 12, color: Palette.muted),
            ),
            if (store.canEdit && !archived)
              Padding(
                padding: const EdgeInsets.only(top: 20),
                child: Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    FilledButton.icon(
                      onPressed: () =>
                          paymentForm(context, store, widget.customerId),
                      icon: const Icon(Icons.add, size: 18),
                      label: const Text('To‘lov'),
                    ),
                    OutlinedButton.icon(
                      onPressed: () =>
                          debtForm(context, store, widget.customerId),
                      icon: const Icon(Icons.receipt_long_outlined, size: 18),
                      label: const Text('Nasiya'),
                    ),
                    OutlinedButton.icon(
                      onPressed: () =>
                          promiseForm(context, store, widget.customerId),
                      icon: const Icon(
                        Icons.event_available_outlined,
                        size: 18,
                      ),
                      label: const Text('Va’da'),
                    ),
                    if (store.isOwner)
                      OutlinedButton.icon(
                        onPressed:
                            integer(customer['contact_allowed']) == 1 &&
                                text(customer['phone']).isNotEmpty
                            ? () => Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => SmsPage(
                                    store: store,
                                    customerId: widget.customerId,
                                  ),
                                ),
                              )
                            : null,
                        icon: const Icon(Icons.sms_outlined, size: 18),
                        label: const Text('SMS eslatma'),
                      ),
                  ],
                ),
              ),
            const SizedBox(height: 24),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  for (final entry in {
                    'debts': 'Nasiyalar (${debts.length})',
                    'payments': 'To‘lovlar (${payments.length})',
                    'promises': 'Va’dalar (${promises.length})',
                    'disputes': 'E’tirozlar (${disputes.length})',
                    'history': 'Tarix',
                  }.entries)
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: ChoiceChip(
                        label: Text(entry.value),
                        selected: section == entry.key,
                        onSelected: (_) => setState(() => section = entry.key),
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            if (section == 'debts') ...[
              if (debts.any((row) => integer(row['archived']) == 1))
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: includeArchive,
                  onChanged: (value) => setState(() => includeArchive = value!),
                  title: const Text('Arxivdagi nasiyalarni ko‘rsatish'),
                ),
              if (debts
                  .where(
                    (row) => includeArchive || integer(row['archived']) == 0,
                  )
                  .isEmpty)
                const EmptyState(
                  title: 'Nasiya yozuvi yo‘q',
                  message:
                      'Yangi nasiya qo‘shib, kelishilgan muddatni belgilang.',
                  icon: Icons.receipt_long_outlined,
                ),
              for (final debt in debts.where(
                (row) => includeArchive || integer(row['archived']) == 0,
              ))
                debtCard(debt),
            ],
            if (section == 'payments') ...[
              if (payments.isEmpty)
                const EmptyState(
                  title: 'To‘lov kiritilmagan',
                  message:
                      'Qabul qilingan to‘lovni yuqoridagi tugmadan kiriting.',
                ),
              for (final payment in payments) paymentCard(payment),
            ],
            if (section == 'promises') ...[
              if (promises.isEmpty)
                const EmptyState(
                  title: 'To‘lov va’dasi yo‘q',
                  message:
                      'Mijoz bilan kelishilgan summa va muddatni qayd eting.',
                  icon: Icons.event_available_outlined,
                ),
              for (final promise in promises)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: PromiseCard(store: store, promise: promise),
                ),
            ],
            if (section == 'disputes') ...[
              if (disputes.isEmpty)
                const EmptyState(
                  title: 'E’tiroz qayd etilmagan',
                  message: 'Nasiya menyusi orqali mijoz e’tirozini kiritishingiz mumkin.',
                  icon: Icons.task_alt,
                ),
              for (final dispute in disputes) disputeCard(dispute),
            ],
            if (section == 'history') ...[
              OutlinedButton(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => ActivityPage(
                      store: store,
                      customerId: widget.customerId,
                    ),
                  ),
                ),
                child: const Text('To‘liq tarixni ochish'),
              ),
              const SizedBox(height: 16),
              if (events.isEmpty)
                const EmptyState(
                  title: 'Tarix bo‘sh',
                  message: 'Mijoz bilan bog‘liq amallar shu yerda ko‘rinadi.',
                ),
              Surface(
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    for (final event in events.take(30)) ActivityRow(event),
                  ],
                ),
              ),
            ],
          ],
        ),
      );
    },
  );
}

class PromiseCard extends StatelessWidget {
  const PromiseCard({
    super.key,
    required this.store,
    required this.promise,
    this.showCustomer = false,
  });
  final AppStore store;
  final Json promise;
  final bool showCustomer;
  @override
  Widget build(BuildContext context) {
    final customerId = text(promise['customer_id']);
    final customer = store.find('customers', customerId);
    final active = !['fulfilled', 'cancelled'].contains(promise['status']);
    final amount = integer(promise['amount']);
    final paid = integer(promise['paid']);
    return Surface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: StatusTag(
                  promiseLabel(promise),
                  color: promiseColor(promise),
                ),
              ),
              if (active && store.canEdit)
                PopupMenuButton<String>(
                  tooltip: 'Va’da amallari',
                  onSelected: (action) async {
                    if (action == 'edit') {
                      await promiseForm(
                        context,
                        store,
                        customerId,
                        promise: promise,
                      );
                    } else {
                      await confirmedMutation(
                        context,
                        store,
                        '/api/promises/${promise['id']}/cancel',
                        {'version': promise['version']},
                        title: 'Va’dani bekor qilish',
                        description: 'Va’da tarixi saqlanadi. Nasiya qoldig‘i o‘zgarishsiz saqlanadi.',
                      );
                    }
                  },
                  itemBuilder: (_) => [
                    const PopupMenuItem(
                      value: 'edit',
                      child: Text('Tahrirlash'),
                    ),
                    const PopupMenuItem(
                      value: 'cancel',
                      child: Text('Va’dani bekor qilish'),
                    ),
                  ],
                ),
            ],
          ),
          if (showCustomer)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: TextButton(
                style: TextButton.styleFrom(
                  padding: EdgeInsets.zero,
                  alignment: Alignment.centerLeft,
                ),
                onPressed: () => openCustomer(context, store, customerId),
                child: Text(
                  text(customer?['name']),
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 16,
                  ),
                ),
              ),
            ),
          const SizedBox(height: 12),
          Text(
            formatMoney(amount),
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text(
            'Kelishilgan sana ${displayDate(promise['due_on'])}',
            style: const TextStyle(color: Palette.muted, fontSize: 13),
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: amount > 0 ? (paid / amount).clamp(0, 1) : 0,
              minHeight: 6,
              backgroundColor: Palette.line,
              color: promiseColor(promise),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '${formatMoney(paid)} bajarildi',
            style: const TextStyle(fontSize: 12, color: Palette.muted),
          ),
          if (text(promise['note']).isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(
                text(promise['note']),
                style: const TextStyle(height: 1.5, fontSize: 13),
              ),
            ),
          if (active && store.canEdit)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: OutlinedButton(
                onPressed: () => paymentForm(
                  context,
                  store,
                  customerId,
                  debt: store.find('debts', text(promise['debt_id'])),
                ),
                child: const Text('To‘lovni qayd etish'),
              ),
            ),
        ],
      ),
    );
  }
}

class PromisesPage extends StatefulWidget {
  const PromisesPage({super.key, required this.store});
  final AppStore store;
  @override
  State<PromisesPage> createState() => _PromisesPageState();
}

class _PromisesPageState extends State<PromisesPage> {
  String filter = 'active';
  int limit = 40;
  @override
  Widget build(BuildContext context) {
    final rows = widget.store
        .rows('promises')
        .where(
          (row) => switch (filter) {
            'active' => ['active', 'partial', 'broken'].contains(row['status']),
            'today' =>
              ['active', 'partial', 'broken'].contains(row['status']) &&
                  row['due_on'] == widget.store.currentDay,
            'all' => true,
            _ => row['status'] == filter,
          },
        )
        .toList();
    rows.sort((a, b) => text(a['due_on']).compareTo(text(b['due_on'])));
    return ContentList(
      children: [
        Text(
          'To‘lov va’dalari',
          style: Theme.of(context).textTheme.headlineLarge,
        ),
        const SizedBox(height: 8),
        const Text(
          'Kelishuvlar va ularning bajarilish holati.',
          style: TextStyle(color: Palette.muted),
        ),
        const SizedBox(height: 20),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final entry in const {
                'active': 'Ochiq',
                'today': 'Bugun',
                'broken': 'Kechikkan',
                'fulfilled': 'Bajarilgan',
                'cancelled': 'Bekor qilingan',
                'all': 'Barchasi',
              }.entries)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: Text(entry.value),
                    selected: filter == entry.key,
                    onSelected: (_) => setState(() {
                      filter = entry.key;
                      limit = 40;
                    }),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        if (rows.isEmpty)
          const Surface(
            child: EmptyState(
              title: 'Bu holatda va’da yo‘q',
              message: 'Va’dani mijoz kartasidan qo‘shishingiz mumkin.',
              icon: Icons.event_available_outlined,
            ),
          ),
        for (final row in rows.take(limit))
          Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: PromiseCard(
              store: widget.store,
              promise: row,
              showCustomer: true,
            ),
          ),
        if (rows.length > limit)
          OutlinedButton(
            onPressed: () => setState(() => limit += 40),
            child: const Text('Yana ko‘rsatish'),
          ),
      ],
    );
  }
}
