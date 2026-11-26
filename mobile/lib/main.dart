// Luna na telefonie (Android, iOS) – prywatna przeglądarka w wyglądzie Luny z komputera.
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';

import 'adblock.dart';
import 'state.dart';
import 'ui/browser.dart';
import 'ui/common.dart';
import 'ui/guide.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final s = LunaState();
  await s.load();
  var ua = '';
  if (Platform.isAndroid) {
    // Google nie pozwala logować się w „osadzonych” przeglądarkach (znacznik „wv”) – Luna przedstawia się jak Chrome
    try {
      ua = (await InAppWebViewController.getDefaultUserAgent()).replaceAll('; wv', '').replaceAll(RegExp(r'Version/\d+(\.\d+)* '), '');
    } catch (_) {}
  }
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
    statusBarBrightness: Brightness.dark,
    systemNavigationBarColor: C.bg,
    systemNavigationBarIconBrightness: Brightness.light,
  ));
  runApp(LunaApp(s: s, userAgent: ua));
  _links(s);
  AdBlock.instance.init().then((_) => blockerVersion.value++);
}

class LunaApp extends StatefulWidget {
  final LunaState s;
  final String userAgent;
  const LunaApp({super.key, required this.s, required this.userAgent});

  @override
  State<LunaApp> createState() => _LunaAppState();
}

class _LunaAppState extends State<LunaApp> with WidgetsBindingObserver {
  late bool _guide = !widget.s.guideDone;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) widget.s.markActive();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Luna',
        debugShowCheckedModeBanner: false,
        theme: lunaTheme(),
        home: _guide
            ? GuideScreen(onDone: () {
                widget.s.guideDone = true;
                widget.s.changed();
                setState(() => _guide = false);
              })
            : BrowserScreen(s: widget.s, userAgent: widget.userAgent, onGuide: () => setState(() => _guide = true)),
      );
}

/// Linki z innych aplikacji (Android): otwierane w nowej karcie.
Future<void> _links(LunaState s) async {
  if (!Platform.isAndroid) return;
  const ch = MethodChannel('luna/links');
  ch.setMethodCallHandler((call) async {
    if (call.method == 'openLink' && call.arguments is String) s.newTab(url: call.arguments as String);
  });
  try {
    final first = await ch.invokeMethod<String>('initialLink');
    if (first != null && first.isNotEmpty) s.newTab(url: first);
  } catch (_) {}
}
