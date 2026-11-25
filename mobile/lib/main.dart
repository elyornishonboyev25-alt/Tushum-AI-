import 'package:flutter/semantics.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:material_ui/material_ui.dart';

import 'app.dart';
import 'core.dart';
import 'ui.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SemanticsBinding.instance.ensureSemantics();
  runApp(const TushumApp());
}

class TushumApp extends StatefulWidget {
  const TushumApp({super.key});
  @override
  State<TushumApp> createState() => _TushumAppState();
}

class _TushumAppState extends State<TushumApp> {
  final store = AppStore();
  final openVoice =
      kIsWeb && Uri.base.queryParameters['sahifa'] == 'ai-suhbatlar';
  @override
  void initState() {
    super.initState();
    store.initialize();
  }

  @override
  void dispose() {
    store.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Tushum AI',
    debugShowCheckedModeBanner: false,
    initialRoute: '/',
    theme: buildTheme(),
    locale: const Locale('uz'),
    supportedLocales: const [Locale('uz'), Locale('en')],
    localizationsDelegates: GlobalMaterialLocalizations.delegates,
    home: AnimatedBuilder(
      animation: store,
      builder: (context, _) {
        if (store.booting) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        if (!store.signedIn) return AuthPage(store: store);
        if (!store.hasWorkspace) {
          return Scaffold(
            body: Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.cloud_off_outlined,
                      size: 42,
                      color: Palette.teal,
                    ),
                    const SizedBox(height: 16),
                    Text(
                      store.error ?? 'Ish maydoni yuklanmoqda…',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 20),
                    FilledButton(
                      onPressed: store.refreshing ? null : store.refresh,
                      child: const Text('Qayta yuklash'),
                    ),
                    TextButton(
                      onPressed: store.logout,
                      child: const Text('Hisobdan chiqish'),
                    ),
                  ],
                ),
              ),
            ),
          );
        }
        return AppShell(store: store, openVoiceOnStart: openVoice);
      },
    ),
  );
}
