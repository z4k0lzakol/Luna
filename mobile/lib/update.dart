// Aktualizacje Luny na Androida: sprawdza najnowsze wydanie na GitHubie, pobiera Luna-Android.apk i otwiera systemowe
// okno instalacji (Android zawsze pyta – aplikacja spoza Sklepu Play nie może aktualizować się po cichu).
// Android przyjmie nową wersję tylko z tym samym podpisem co zainstalowana – to on sprawdza, że plik jest od Luny.
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';

import 'ui/common.dart';

/// Wersja tej Luny – nadawana przy budowaniu (--dart-define=LUNA_VERSION=1.0.12); pusta przy budowaniu u siebie.
const kVersion = String.fromEnvironment('LUNA_VERSION');

/// Do komunikatów o aktualizacji spoza konkretnego ekranu (MaterialApp.scaffoldMessengerKey).
final messengerKey = GlobalKey<ScaffoldMessengerState>();

const _api = 'https://api.github.com/repos/z4k0lzakol/Luna/releases/latest';
const _apk = 'Luna-Android.apk';
const _channel = MethodChannel('luna/update');

List<int> _parts(String v) => RegExp(r'\d+').allMatches(v).take(3).map((m) => int.parse(m[0]!)).toList();

bool newer(String a, String b) {
  final x = _parts(a), y = _parts(b);
  for (var i = 0; i < 3; i++) {
    final p = i < x.length ? x[i] : 0, q = i < y.length ? y[i] : 0;
    if (p != q) return p > q;
  }
  return false;
}

class Updater {
  Updater._();
  static final instance = Updater._();

  bool get supported => Platform.isAndroid && kVersion.isNotEmpty;
  bool _busy = false;

  /// Po starcie (cicho): gdy jest nowsza wersja – komunikat z przyciskiem „Zainstaluj”.
  void checkLater() {
    if (!supported) return;
    Future.delayed(const Duration(seconds: 20), () => check());
  }

  /// [interactive] – z Ustawień: mówi też „Masz najnowszą wersję” i o błędach.
  Future<void> check({bool interactive = false}) async {
    if (!supported || _busy) return;
    try {
      final rel = await _latest();
      if (rel == null) {
        if (interactive) _say('Masz najnowszą wersję Luny ($kVersion)');
        return;
      }
      _say('Dostępna nowa wersja Luny – ${rel.$1}', action: SnackBarAction(label: 'Zainstaluj', onPressed: () => install(rel.$1, rel.$2)), long: true);
    } catch (_) {
      if (interactive) _say('Nie udało się sprawdzić aktualizacji – sprawdź połączenie');
    }
  }

  /// (wersja, adres APK) najnowszego wydania, jeśli jest nowsze od tej Luny.
  Future<(String, String)?> _latest() async {
    final c = HttpClient()..connectionTimeout = const Duration(seconds: 15);
    try {
      final req = await c.getUrl(Uri.parse(_api));
      req.headers.set('Accept', 'application/vnd.github+json');
      req.headers.set('User-Agent', 'Luna-browser');
      final res = await req.close().timeout(const Duration(seconds: 20));
      if (res.statusCode != 200) throw HttpException('HTTP ${res.statusCode}');
      final d = jsonDecode(await res.transform(utf8.decoder).join()) as Map<String, dynamic>;
      final tag = (d['tag_name'] as String? ?? '').replaceFirst(RegExp('^[vV]'), '');
      if (tag.isEmpty || !newer(tag, kVersion)) return null;
      for (final a in (d['assets'] as List? ?? const [])) {
        if (a is Map && a['name'] == _apk) return (tag, a['browser_download_url'] as String);
      }
      return null;   // wydanie bez APK (np. jeszcze się buduje) – spróbujemy następnym razem
    } finally {
      c.close();
    }
  }

  Future<void> install(String ver, String url) async {
    if (_busy) return;
    _busy = true;
    try {
      _say('Pobieranie Luny $ver…', long: true);
      final dir = Directory('${(await getTemporaryDirectory()).path}/aktualizacje');
      if (await dir.exists()) await dir.delete(recursive: true);
      await dir.create(recursive: true);
      final file = File('${dir.path}/Luna-$ver.apk');
      final c = HttpClient()..connectionTimeout = const Duration(seconds: 20);
      try {
        final req = await c.getUrl(Uri.parse(url));
        req.headers.set('User-Agent', 'Luna-browser');
        final res = await req.close();
        if (res.statusCode != 200) throw HttpException('HTTP ${res.statusCode}');
        final total = res.contentLength;
        var got = 0, last = -1;
        final sink = file.openWrite();
        await for (final chunk in res) {
          sink.add(chunk);
          got += chunk.length;
          final pc = total > 0 ? got * 100 ~/ total : -1;
          if (pc >= 0 && pc ~/ 10 != last) {
            last = pc ~/ 10;
            _say('Pobieranie Luny $ver… $pc%', long: true);
          }
        }
        await sink.close();
        if (total > 0 && got != total) throw const HttpException('plik pobrany tylko częściowo');
      } finally {
        c.close();
      }
      messengerKey.currentState?.hideCurrentSnackBar();
      final r = await _channel.invokeMethod<String>('install', {'path': file.path});
      if (r == 'settings') {
        _say('Zezwól Lunie na instalowanie aplikacji, wróć i kliknij „Zainstaluj” jeszcze raz',
            action: SnackBarAction(label: 'Zainstaluj', onPressed: () => _installFile(file)), long: true);
      }
    } catch (e) {
      _say('Nie udało się pobrać aktualizacji – spróbuj później');
    } finally {
      _busy = false;
    }
  }

  Future<void> _installFile(File f) async {
    try {
      await _channel.invokeMethod<String>('install', {'path': f.path});
    } catch (_) {}
  }

  void _say(String text, {SnackBarAction? action, bool long = false}) {
    final m = messengerKey.currentState;
    if (m == null) return;
    m
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(
        content: Text(text, style: const TextStyle(color: C.text)),
        action: action,
        backgroundColor: const Color(0xFF1C1C1C),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: const BorderSide(color: C.border2)),
        duration: Duration(milliseconds: long ? 12000 : 3000),
      ));
  }
}
