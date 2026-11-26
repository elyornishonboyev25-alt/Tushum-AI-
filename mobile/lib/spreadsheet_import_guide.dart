import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import 'ui.dart';

/// An editable example only; the guide never creates customer or debt records.
class SpreadsheetImportGuide extends StatefulWidget {
  const SpreadsheetImportGuide({super.key, required this.day});
  final String day;

  static const headers = [
    'Mijoz ismi',
    'Telegram username',
    'Qarz summasi',
    'Qarz sanasi',
  ];

  @override
  State<SpreadsheetImportGuide> createState() => _SpreadsheetImportGuideState();
}

class _SpreadsheetImportGuideState extends State<SpreadsheetImportGuide> {
  int selected = 0;
  late final List<TextEditingController> examples;
  static const icons = [
    Icons.person_outline,
    Icons.alternate_email,
    Icons.payments_outlined,
    Icons.event_outlined,
  ];
  static const explanations = [
    'Mijozning ismi va familiyasini yozing. Bir mijozning boshqa qarzida ham shu ismni ishlating.',
    'Mijozning Telegram’dagi username’ini yozing: @ bilan yoki usiz. Ism yoki telefon raqamini bu ustunga yozmang.',
    'Qarz summasini so‘mda kiriting. Masalan, 1500000 — bir million besh yuz ming so‘m. «mln» yoki «so‘m» qo‘shmang.',
    'Bu — qarzni qaytarish kerak bo‘lgan sana. YYYY-MM-DD yoki DD.MM.YYYY formatidan foydalaning.',
  ];

  @override
  void initState() {
    super.initState();
    final day = DateTime.tryParse(widget.day) ?? DateTime.now();
    final due = day
        .add(const Duration(days: 7))
        .toIso8601String()
        .substring(0, 10);
    examples = [
      'Akmal Karimov',
      '@akmal_namuna',
      '1500000',
      due,
    ].map((value) => TextEditingController(text: value)).toList();
  }

  String? validateExample() {
    final value = examples[selected].text.trim();
    switch (selected) {
      case 0:
        if (value.length < 2 || value.length > 120) {
          return 'Ism 2–120 ta belgidan iborat bo‘lsin.';
        }
      case 1:
        if (!RegExp(r'^@?[A-Za-z][A-Za-z0-9_]{4,31}$').hasMatch(value)) {
          return '@akmal_namuna kabi yozing: 5–32 ta belgi.';
        }
      case 2:
        final amount = num.tryParse(
          value.replaceAll(RegExp(r'[ \u00a0]'), '').replaceAll(',', '.'),
        );
        if (amount == null ||
            !amount.isFinite ||
            amount <= 0 ||
            amount > 1000000000000 ||
            !RegExp(r'^\d+(?:[.,]\d{1,2})?$')
                .hasMatch(value.replaceAll(RegExp(r'[ \u00a0]'), ''))) {
          return 'Musbat son kiriting. Masalan: 1500000 yoki 1500000.50.';
        }
      case 3:
        final iso = RegExp(r'^(\d{4})-(\d{2})-(\d{2})$').firstMatch(value);
        final local = RegExp(r'^(\d{2})\.(\d{2})\.(\d{4})$').firstMatch(value);
        final match = iso ?? local;
        if (match == null) {
          return 'Sanani 2026-12-10 yoki 10.12.2026 kabi yozing.';
        }
        final year = int.parse(match[iso != null ? 1 : 3]!);
        final month = int.parse(match[2]!);
        final day = int.parse(match[iso != null ? 3 : 1]!);
        final date = DateTime(year, month, day);
        if (year < 1 ||
            date.year != year ||
            date.month != month ||
            date.day != day) {
          return 'Mavjud sanani kiriting. Oy va kunni tekshiring.';
        }
    }
    return null;
  }

  @override
  void dispose() {
    for (final controller in examples) {
      controller.dispose();
    }
    super.dispose();
  }

  void selectColumn(int column) {
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() => selected = column);
  }

  Widget exampleCell(
    String value,
    int column, {
    bool heading = false,
    double scale = 1,
  }) {
    final active = selected == column;
    return SizedBox(
      width: [205.0, 225.0, 180.0, 190.0][column] * scale,
      child: Material(
        color: active ? Palette.soft : Colors.transparent,
        child: InkWell(
          onTap: () => selectColumn(column),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 17),
            child: Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: heading && active ? Palette.teal : Palette.ink,
                fontWeight: heading ? FontWeight.w700 : FontWeight.w400,
                fontSize: 13,
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final failure = validateExample();
    return LayoutBuilder(
      builder: (context, constraints) {
        final tableScale = ((constraints.maxWidth - 42) / 800)
            .clamp(1.0, 2.0)
            .toDouble();
        return Surface(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Wrap(
                alignment: WrapAlignment.spaceBetween,
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 12,
                runSpacing: 6,
                children: [
                  const Text(
                    'Excel faylida 4 ta ustun bo‘lsin',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
                  ),
                  TextButton.icon(
                    onPressed: () async {
                      await Clipboard.setData(
                        ClipboardData(
                          text: SpreadsheetImportGuide.headers.join('\t'),
                        ),
                      );
                      if (context.mounted) {
                        feedbackMessage(
                          context,
                          'Sarlavhalar nusxalandi. Excel’ning A1 katagiga joylashtiring.',
                        );
                      }
                    },
                    icon: const Icon(Icons.copy_outlined, size: 17),
                    label: const Text('Sarlavhalarni nusxalash'),
                  ),
                ],
              ),
              const SizedBox(height: 5),
              const Text(
                'Ustunni bosing, so‘ng namunani o‘zgartirib formatini sinang. Har bir qator — bitta qarz.',
                style: TextStyle(color: Palette.muted, height: 1.6),
              ),
              const SizedBox(height: 18),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  for (
                    var i = 0;
                    i < SpreadsheetImportGuide.headers.length;
                    i++
                  )
                    ChoiceChip(
                      selected: selected == i,
                      showCheckmark: false,
                      selectedColor: Palette.soft,
                      backgroundColor: Palette.background,
                      side: BorderSide(
                        color: selected == i ? Palette.teal : Palette.line,
                      ),
                      avatar: Icon(icons[i], size: 17),
                      label: Text(SpreadsheetImportGuide.headers[i]),
                      onSelected: (_) => selectColumn(i),
                    ),
                ],
              ),
              const SizedBox(height: 16),
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: Container(
                  decoration: BoxDecoration(
                    border: Border.all(color: Palette.line),
                  ),
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            for (var i = 0; i < 4; i++)
                              exampleCell(
                                SpreadsheetImportGuide.headers[i],
                                i,
                                heading: true,
                                scale: tableScale,
                              ),
                          ],
                        ),
                        SizedBox(
                          width: 800 * tableScale,
                          child: const Divider(),
                        ),
                        Row(
                          children: [
                            for (var i = 0; i < 4; i++)
                              exampleCell(
                                examples[i].text,
                                i,
                                scale: tableScale,
                              ),
                          ],
                        ),
                        SizedBox(
                          width: 800 * tableScale,
                          child: const Divider(),
                        ),
                        Row(
                          children: [
                            for (var i = 0; i < 4; i++)
                              exampleCell(
                                [
                                  'Nodira Aliyeva',
                                  '@nodira_namuna',
                                  '850000',
                                  examples[3].text,
                                ][i],
                                i,
                                scale: tableScale,
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              if (MediaQuery.sizeOf(context).width < 900)
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: Text(
                    'Qolgan ustunlarni ko‘rish uchun jadvalni yon tomonga suring.',
                    style: TextStyle(fontSize: 12, color: Palette.muted),
                  ),
                ),
              const SizedBox(height: 20),
              Text(explanations[selected], style: const TextStyle(height: 1.6)),
              const SizedBox(height: 13),
              TextField(
                key: ValueKey('import-example-$selected'),
                controller: examples[selected],
                onChanged: (_) => setState(() {}),
                maxLength: selected == 0 ? 120 : 40,
                decoration: InputDecoration(
                  labelText:
                      '${SpreadsheetImportGuide.headers[selected]} — namuna',
                  helperText: 'Sinov uchun. Mijozlar ro‘yxatiga saqlanmaydi.',
                  helperMaxLines: 2,
                  errorText: failure,
                  errorMaxLines: 2,
                  counterText: '',
                  prefixIcon: Icon(icons[selected], size: 21),
                  suffixIcon: Icon(
                    failure == null
                        ? Icons.check_circle_outline
                        : Icons.error_outline,
                    color: failure == null ? Palette.teal : Palette.red,
                    size: 20,
                  ),
                ),
              ),
              const SizedBox(height: 14),
              const ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: Text(
                  'Telefon va qo‘shimcha ustunlar',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                ),
                children: [
                  Padding(
                    padding: EdgeInsets.only(bottom: 12),
                    child: Text(
                      'Telegram username o‘rniga «Telefon» ustunini ishlatish ham mumkin: +998901234567. '
                      'Ikkalasini ham kiritsangiz, bir mijozga tegishli bo‘lsin.\n\n'
                      '«Savdo sanasi» — qarz berilgan sana. Bo‘sh qolsa, bugungi sana olinadi. '
                      'Oldin berilgan qarzlar uchun shu ustunni ham kiriting. Qaytarish muddati savdo sanasidan oldin bo‘lmasin.\n\n'
                      '«Hujjat», «Korxona» va «Izoh» ixtiyoriy. Hujjat raqami takrorlanmasin. '
                      'Bitta mijozning bir nechta qarzi bo‘lsa, alohida qatorlarda bir xil username yoki telefonni yozing.',
                      style: TextStyle(
                        color: Palette.muted,
                        fontSize: 13,
                        height: 1.7,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}
