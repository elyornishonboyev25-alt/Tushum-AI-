import 'package:file_picker/file_picker.dart';
import 'package:material_ui/material_ui.dart';

import 'core.dart';
import 'ui.dart';
import 'app.dart' show ContentList;
import 'settings.dart' show downloadFile;
import 'spreadsheet_import_guide.dart';

class SpreadsheetImportPage extends StatefulWidget {
  const SpreadsheetImportPage({super.key, required this.store});
  final AppStore store;
  @override
  State<SpreadsheetImportPage> createState() => _SpreadsheetImportPageState();
}

class _SpreadsheetImportPageState extends State<SpreadsheetImportPage> {
  PlatformFile? file;
  Json? preview;
  Json mapping = {};
  final Set<int> selected = {};
  bool busy = false;
  String? error;
  int limit = 50;
  String operationId = uuid.v4();
  String? submittedSelection;
  bool showGuide = true;
  static const fieldNames = {
    'name': 'Mijoz ismi',
    'phone': 'Telefon raqami',
    'telegram_username': 'Telegram username',
    'amount': 'Nasiya summasi',
    'due_on': 'To‘lov muddati',
    'issued_on': 'Savdo sanasi',
    'reference': 'Hujjat raqami',
    'company': 'Korxona',
    'note': 'Izoh',
  };

  Future<void> pickFile() async {
    try {
      final picked = await FilePicker.pickFile(
        type: FileType.custom,
        allowedExtensions: ['xlsx', 'csv'],
      );
      if (picked == null || !mounted) return;
      if ((await picked.length() ?? 0) > 10 * 1024 * 1024) {
        throw const ApiError('Fayl hajmi 10 MB dan oshmasin.');
      }
      setState(() {
        file = picked;
        preview = null;
        mapping = {};
        selected.clear();
        error = null;
        limit = 50;
      });
      await upload();
    } on ApiError catch (failure) {
      if (mounted) setState(() => error = failure.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => error = 'Fayl tanlanmadi. XLSX yoki CSV faylni qayta tanlang.',
        );
      }
    }
  }

  Future<void> upload() async {
    if (file == null || busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = await widget.store.api.upload(file!, mapping: mapping);
      if (!mounted) return;
      setState(() {
        preview = result;
        showGuide = false;
        selected.clear();
        if (result['needs_mapping'] == true) {
          mapping = Map<String, dynamic>.from(result['mapping'] as Map? ?? {});
        } else {
          for (final row in result['rows'] as List) {
            if (text(row['error']).isEmpty && text(row['warning']).isEmpty) {
              selected.add(integer(row['index']));
            }
          }
        }
        operationId = uuid.v4();
        submittedSelection = null;
      });
    } on ApiError catch (failure) {
      if (mounted) setState(() => error = failure.message);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> commit() async {
    if (busy || preview == null || selected.isEmpty) return;
    final indexes = selected.toList()..sort();
    final signature = indexes.join(',');
    if (submittedSelection != null && signature != submittedSelection) {
      operationId = uuid.v4();
    }
    submittedSelection = signature;
    final rows = (preview!['rows'] as List).cast<Map>();
    final warnings = rows
        .where(
          (row) =>
              selected.contains(row['index']) &&
              text(row['warning']).isNotEmpty,
        )
        .map((row) => row['index'])
        .toList();
    final confirmed = await confirm(
      context,
      'Importni tasdiqlash',
      '${selected.length} ta nasiya serverga saqlanadi.${warnings.isNotEmpty ? ' ${warnings.length} ta ogohlantirishli yozuvni ham tanladingiz. Ularni qo‘shishga roziligingizni tasdiqlang.' : ''}',
      action: 'Import qilish',
    );
    if (!confirmed || !mounted) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = await widget.store.mutate(
        '/api/imports/${preview!['id']}/commit',
        {'rows': indexes, 'accept_duplicates': warnings},
        operationId: operationId,
      );
      if (mounted) {
        setState(() {
          preview = {...preview!, 'committed': true, 'result': result};
        });
      }
    } on ApiError catch (failure) {
      if (mounted) setState(() => error = failure.message);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget columnMapping() {
    final headers = (preview!['headers'] as List).map(text).toSet();
    return Surface(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Ustunlarni moslang',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 10),
          const Text(
            'Ism, qarz summasi va qaytarish muddati ustunlarini tanlang. Kontakt uchun Telegram username yoki telefon yetarli.',
            style: TextStyle(color: Palette.muted, height: 1.5),
          ),
          const SizedBox(height: 22),
          for (final entry in fieldNames.entries)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: DropdownButtonFormField<String>(
                initialValue: text(mapping[entry.key]).isEmpty
                    ? ''
                    : text(mapping[entry.key]),
                isExpanded: true,
                decoration: InputDecoration(
                  labelText:
                      '${entry.value}${['name', 'amount', 'due_on'].contains(entry.key) ? ' *' : ''}',
                ),
                items: [
                  const DropdownMenuItem(value: '', child: Text('Tanlanmagan')),
                  for (final header in headers)
                    DropdownMenuItem(
                      value: header,
                      child: Text(header, overflow: TextOverflow.ellipsis),
                    ),
                ],
                onChanged: busy
                    ? null
                    : (value) => setState(() {
                        if (value == null || value.isEmpty) {
                          mapping.remove(entry.key);
                        } else {
                          mapping[entry.key] = value;
                        }
                      }),
              ),
            ),
          FilledButton(
            onPressed:
                busy ||
                    ![
                      'name',
                      'amount',
                      'due_on',
                    ].every((key) => text(mapping[key]).isNotEmpty) ||
                    ![
                      'phone',
                      'telegram_username',
                    ].any((key) => text(mapping[key]).isNotEmpty)
                ? null
                : upload,
            child: const Text('Yozuvlarni tekshirish'),
          ),
        ],
      ),
    );
  }

  Widget previewRows() {
    final rows = (preview!['rows'] as List)
        .map((row) => Map<String, dynamic>.from(row as Map))
        .toList();
    final errors = rows.where((row) => text(row['error']).isNotEmpty).length;
    final warnings = rows
        .where((row) => text(row['warning']).isNotEmpty)
        .length;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Surface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${rows.length} ta yozuv tekshirildi',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 10),
              Text(
                '${selected.length} ta tanlandi · $errors ta xato · $warnings ta ogohlantirish',
                style: const TextStyle(color: Palette.muted),
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 8,
                children: [
                  TextButton(
                    onPressed: busy
                        ? null
                        : () => setState(() {
                            selected.clear();
                            selected.addAll(
                              rows
                                  .where(
                                    (row) =>
                                        text(row['error']).isEmpty &&
                                        text(row['warning']).isEmpty,
                                  )
                                  .map((row) => integer(row['index'])),
                            );
                          }),
                    child: const Text('To‘g‘ri yozuvlarni tanlash'),
                  ),
                  TextButton(
                    onPressed: busy ? null : () => setState(selected.clear),
                    child: const Text('Tanlovni tozalash'),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        for (final row in rows.take(limit)) previewRow(row),
        if (rows.length > limit)
          OutlinedButton(
            onPressed: () => setState(() => limit += 50),
            child: Text('Yana ko‘rsatish (${rows.length - limit})'),
          ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: busy || selected.isEmpty ? null : commit,
          icon: const Icon(Icons.check),
          label: Text('${selected.length} ta nasiyani import qilish'),
        ),
      ],
    );
  }

  Widget previewRow(Json row) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Surface(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        child: CheckboxListTile(
          controlAffinity: ListTileControlAffinity.leading,
          contentPadding: const EdgeInsets.symmetric(horizontal: 4),
          value: selected.contains(integer(row['index'])),
          onChanged: busy || text(row['error']).isNotEmpty
              ? null
              : (value) {
                  setState(() {
                    if (value == true) {
                      selected.add(integer(row['index']));
                    } else {
                      selected.remove(integer(row['index']));
                    }
                  });
                },
          title: Text(
            '${row['line']}-qator · ${text(row['name']).isEmpty ? 'Xatoli yozuv' : row['name']}',
            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
          ),
          subtitle: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 6),
              Text(
                '${[if (text(row['telegram_username']).isNotEmpty) '@${row['telegram_username']}', if (text(row['phone']).isNotEmpty) text(row['phone'])].join(' · ')} · ${text(row['amount'])} so‘m\nQaytarish muddati ${displayDate(row['due_on'])}',
                style: const TextStyle(
                  color: Palette.muted,
                  fontSize: 12,
                  height: 1.5,
                ),
              ),
              if (text(row['error']).isNotEmpty)
                Text(
                  text(row['error']),
                  style: const TextStyle(color: Palette.red, fontSize: 12),
                ),
              if (text(row['warning']).isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 5),
                  child: Text(
                    text(row['warning']),
                    style: const TextStyle(color: Palette.amber, fontSize: 12),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: Scaffold(
      appBar: AppBar(title: const Text('Excel yuklash')),
      body: ContentList(
        children: [
          Text(
            'Mijozlaringizni bir fayldan qo‘shing',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 12),
          const Text(
            'Mijoz ismi, Telegram username, qarz summasi va qaytarish muddatini yozing. Yuklagach, saqlashdan oldin tekshirasiz.',
            style: TextStyle(color: Palette.muted, height: 1.6),
          ),
          const SizedBox(height: 22),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              FilledButton.icon(
                onPressed: busy ? null : pickFile,
                icon: const Icon(Icons.upload_file_outlined),
                label: Text(
                  file == null ? 'Fayl tanlash' : 'Boshqa fayl tanlash',
                ),
              ),
              OutlinedButton.icon(
                onPressed: busy
                    ? null
                    : () => downloadFile(
                        context,
                        widget.store,
                        '/api/imports/template',
                        'tushum-import-namuna.xlsx',
                      ),
                icon: const Icon(Icons.file_download_outlined),
                label: const Text('Shablon yuklash'),
              ),
              TextButton.icon(
                onPressed: () => setState(() => showGuide = !showGuide),
                icon: Icon(
                  showGuide ? Icons.expand_less : Icons.help_outline,
                  size: 19,
                ),
                label: Text(
                  showGuide ? 'Qo‘llanmani yashirish' : 'Qanday tayyorlanadi?',
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          const Text(
            'XLSX yoki UTF-8 CSV · 10 MB gacha · 2 000 ta yozuvgacha',
            style: TextStyle(color: Palette.muted, fontSize: 12),
          ),
          if (showGuide) ...[
            const SizedBox(height: 22),
            SpreadsheetImportGuide(day: widget.store.currentDay),
            const SizedBox(height: 12),
            const Text(
              'Shablondagi namunaviy qatorni o‘z mijozingiz bilan almashtiring. Import qo‘ng‘iroqni avtomatik boshlamaydi.',
              style: TextStyle(color: Palette.muted, fontSize: 12, height: 1.6),
            ),
          ],
          if (file != null)
            Padding(
              padding: const EdgeInsets.only(top: 18),
              child: Text(
                file!.name,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ),
          if (busy)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: LinearProgressIndicator(),
            ),
          if (error != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 16),
              child: Text(
                error!,
                style: const TextStyle(color: Palette.red, height: 1.5),
              ),
            ),
          if (file != null && preview == null && !busy)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: OutlinedButton(
                onPressed: upload,
                child: const Text('Yuklashni qayta urinish'),
              ),
            ),
          const SizedBox(height: 22),
          if (preview?['committed'] == true)
            Surface(
              child: Column(
                children: [
                  const Icon(
                    Icons.check_circle_outline,
                    color: Palette.green,
                    size: 48,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Import saqlandi',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Mijozlar, nasiyalar va qoldiqlar yangilandi.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Palette.muted),
                  ),
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Mijozlarga qaytish'),
                  ),
                ],
              ),
            )
          else if (preview?['needs_mapping'] == true)
            columnMapping()
          else if (preview != null)
            previewRows(),
        ],
      ),
    ),
  );
}
