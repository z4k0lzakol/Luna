// Aktualizacje Luny na Androida: zaraz po otwarciu sprawdza najnowsze wydanie na GitHubie, pobiera Luna-Android.apk
// w tle (domyślnie tylko przez Wi-Fi) i gdy plik jest gotowy – proponuje instalację. Android zawsze pyta o zgodę
// (aplikacja spoza Sklepu Play nie może aktualizować się po cichu) i przyjmie tylko plik z tym samym podpisem co Luna.
// Ekran „Aktualizacje” (ui/updates.dart) pokazuje stan, opis zmian i postęp.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart' as crypto;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'ui/common.dart';

/// Wersja tej Luny – nadawana przy budowaniu (--dart-define=LUNA_VERSION=1.0.12); pusta przy budowaniu u siebie.
const kVersion = String.fromEnvironment('LUNA_VERSION');

/// Do komunikatów o aktualizacji spoza konkretnego ekranu (MaterialApp.scaffoldMessengerKey).
final messengerKey = GlobalKey<ScaffoldMessengerState>();

const _api = 'https://api.github.com/repos/z4k0lzakol/Luna/releases/latest';
const _apk = 'Luna-Android.apk';
const _channel = MethodChannel('luna/update');
const _recheck = Duration(hours: 6);   // ponowne sprawdzenie przy powrocie do Luny

List<int> _parts(String v) => RegExp(r'\d+').allMatches(v).take(3).map((m) => int.parse(m[0]!)).toList();

bool newer(String a, String b) {
  final x = _parts(a), y = _parts(b);
  for (var i = 0; i < 3; i++) {
    final p = i < x.length ? x[i] : 0, q = i < y.length ? y[i] : 0;
    if (p != q) return p > q;
  }
  return false;
}

enum UpdState { idle, checking, upToDate, available, downloading, ready, error }

class Release {
  final String version, url, notes, sha256;
  final int size;
  const Release(this.version, this.url, this.size, this.sha256, this.notes);
}

class Updater extends ChangeNotifier {
  Updater._();
  static final instance = Updater._();

  bool get supported => Platform.isAndroid && kVersion.isNotEmpty;
  UpdState state = UpdState.idle;
  Release? latest;
  double progress = 0;          // 0–1 podczas pobierania
  String error = '';
  DateTime? lastCheck;
  File? _file;
  bool auto = true;             // pobieraj nowe wersje samodzielnie
  bool wifiOnly = true;         // …tylko przez Wi-Fi
  SharedPreferences? _p;
  bool _offered = false;        // komunikat „gotowa do instalacji” w tej sesji

  Future<void> _load() async {
    if (_p != null) return;
    _p = await SharedPreferences.getInstance();
    auto = _p!.getBool('upd_auto') ?? true;
    wifiOnly = _p!.getBool('upd_wifi') ?? true;
    final t = _p!.getInt('upd_last');
    if (t != null) lastCheck = DateTime.fromMillisecondsSinceEpoch(t);
  }

  void setAuto(bool v) {
    auto = v;
    _p?.setBool('upd_auto', v);
    notifyListeners();
    if (v && state == UpdState.available) _maybeDownload();
  }

  void setWifiOnly(bool v) {
    wifiOnly = v;
    _p?.setBool('upd_wifi', v);
    notifyListeners();
    if (!v && state == UpdState.available) _maybeDownload();
  }

  /// Zaraz po otwarciu Luny (pierwsze uruchomienie po nowym wydaniu pobiera je od razu) i po powrocie do niej.
  void checkLater() {
    if (!supported) return;
    Future.delayed(const Duration(seconds: 2), () async {
      await _load();
      await _cleanup();
      await check();
    });
  }

  void resumed() {
    if (!supported || state == UpdState.checking || state == UpdState.downloading) return;
    if (state == UpdState.ready) {
      _offerInstall();
      return;
    }
    if (lastCheck == null || DateTime.now().difference(lastCheck!) > _recheck) check();
  }

  /// [interactive] – z ekranu Aktualizacje albo Ustawień: mówi też „Masz najnowszą wersję” i o błędach.
  Future<void> check({bool interactive = false}) async {
    if (!supported || state == UpdState.checking || state == UpdState.downloading) return;
    await _load();
    state = UpdState.checking;
    error = '';
    notifyListeners();
    try {
      latest = await _fetchLatest();
      lastCheck = DateTime.now();
      _p?.setInt('upd_last', lastCheck!.millisecondsSinceEpoch);
      if (latest == null) {
        state = UpdState.upToDate;
        notifyListeners();
        if (interactive) _say('Masz najnowszą wersję Luny ($kVersion)');
        return;
      }
      final have = await _downloaded(latest!);
      if (have != null) {
        _file = have;
        state = UpdState.ready;
        notifyListeners();
        _offerInstall();
        return;
      }
      state = UpdState.available;
      notifyListeners();
      if (interactive) {
        await download();
      } else {
        await _maybeDownload();
      }
    } catch (e) {
      state = UpdState.error;
      error = 'Nie udało się sprawdzić aktualizacji – sprawdź połączenie z internetem.';
      notifyListeners();
      if (interactive) _say(error);
    }
  }

  Future<void> _maybeDownload() async {
    if (!auto || latest == null || state != UpdState.available) return;
    if (wifiOnly && !await _onWifi()) {
      _say('Dostępna nowa wersja Luny – ${latest!.version}', action: SnackBarAction(label: 'Pobierz', onPressed: download), long: true);
      return;
    }
    await download(quiet: true);
  }

  Future<bool> _onWifi() async {
    try {
      return await _channel.invokeMethod<bool>('isWifi') ?? true;
    } catch (_) {
      return true;
    }
  }

  /// Najnowsze wydanie, jeśli jest nowsze od tej Luny i ma plik APK.
  Future<Release?> _fetchLatest() async {
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
        if (a is Map && a['name'] == _apk) {
          final dg = '${a['digest'] ?? ''}';   // GitHub podaje „sha256:…” dla każdego pliku wydania
          return Release(tag, a['browser_download_url'] as String, (a['size'] ?? 0) as int,
              dg.startsWith('sha256:') ? dg.substring(7).toLowerCase() : '', _notes('${d['body'] ?? ''}'));
        }
      }
      return null;   // wydanie bez APK (np. jeszcze się buduje) – spróbujemy następnym razem
    } finally {
      c.close();
    }
  }

  /// Pierwsza sekcja opisu wydania („Co nowego w …”) jako zwykły tekst.
  static String _notes(String md) {
    final lines = md.split('\n');
    final out = <String>[];
    var started = false;
    for (final l in lines) {
      if (l.startsWith('## ')) {
        if (started) break;
        started = true;
        continue;
      }
      if (started) out.add(l.replaceAll('**', '').replaceAll('`', '').replaceAll(RegExp(r'\[([^\]]+)\]\([^)]+\)'), r'$1'));
    }
    return out.join('\n').trim();
  }

  Future<Directory> _dir() async {
    final d = Directory('${(await getTemporaryDirectory()).path}/aktualizacje');
    await d.create(recursive: true);
    return d;
  }

  /// Plik pobrany wcześniej (np. przed zamknięciem Luny) – bez ponownego pobierania.
  Future<File?> _downloaded(Release r) async {
    final f = File('${(await _dir()).path}/Luna-${r.version}.apk');
    if (!await f.exists() || (r.size > 0 && await f.length() != r.size)) return null;
    if (r.sha256.isNotEmpty && (await crypto.sha256.bind(f.openRead()).first).toString() != r.sha256) return null;
    return f;
  }

  /// Usuwa pliki starszych wersji (np. tej, która jest już zainstalowana).
  Future<void> _cleanup() async {
    try {
      await for (final e in (await _dir()).list()) {
        final m = RegExp(r'Luna-([\d.]+)\.apk').firstMatch(e.path.split('/').last);
        if (m == null || !newer(m.group(1)!, kVersion)) await e.delete();
      }
    } catch (_) {}
  }

  Future<void> download({bool quiet = false}) async {
    final r = latest;
    if (r == null || state == UpdState.downloading) return;
    state = UpdState.downloading;
    progress = 0;
    error = '';
    notifyListeners();
    if (!quiet) _say('Pobieranie Luny ${r.version}…');
    final dir = await _dir();
    final part = File('${dir.path}/Luna-${r.version}.apk.czesc');
    final c = HttpClient()..connectionTimeout = const Duration(seconds: 20);
    try {
      final req = await c.getUrl(Uri.parse(r.url));
      req.headers.set('User-Agent', 'Luna-browser');
      final res = await req.close();
      if (res.statusCode != 200) throw HttpException('HTTP ${res.statusCode}');
      final total = res.contentLength > 0 ? res.contentLength : r.size;
      var got = 0;
      final sink = part.openWrite();
      final hs = _Hash();
      final hasher = crypto.sha256.startChunkedConversion(hs);
      var lastNote = DateTime.now();
      await for (final chunk in res) {
        sink.add(chunk);
        hasher.add(chunk);
        got += chunk.length;
        if (total > 0 && DateTime.now().difference(lastNote).inMilliseconds > 150) {
          lastNote = DateTime.now();
          progress = got / total;
          notifyListeners();
        }
      }
      await sink.close();
      hasher.close();
      if (total > 0 && got != total) throw const HttpException('plik pobrany tylko częściowo');
      if (r.sha256.isNotEmpty && hs.value.toString() != r.sha256) throw const HttpException('suma kontrolna się nie zgadza');
      final f = await part.rename('${dir.path}/Luna-${r.version}.apk');
      _file = f;
      progress = 1;
      state = UpdState.ready;
      notifyListeners();
      _offerInstall(force: !quiet);
    } catch (e) {
      try {
        if (await part.exists()) await part.delete();
      } catch (_) {}
      state = UpdState.error;
      error = 'Nie udało się pobrać nowej wersji${e is HttpException ? ' (${e.message})' : ''}. Spróbuj ponownie.';
      notifyListeners();
      if (!quiet) _say(error);
    } finally {
      c.close();
    }
  }

  void _offerInstall({bool force = false}) {
    if (_offered && !force) return;
    _offered = true;
    _say('Luna ${latest?.version ?? ''} jest gotowa do instalacji', action: SnackBarAction(label: 'Zainstaluj', onPressed: install), long: true);
  }

  /// Otwiera systemowe okno instalacji (po pobraniu – od razu; inaczej najpierw pobiera).
  Future<void> install() async {
    if (state != UpdState.ready || _file == null) {
      await download();
      if (state != UpdState.ready) return;
    }
    try {
      final r = await _channel.invokeMethod<String>('install', {'path': _file!.path});
      if (r == 'settings') {
        _say('Zezwól Lunie na instalowanie aplikacji, wróć i kliknij „Zainstaluj” jeszcze raz',
            action: SnackBarAction(label: 'Zainstaluj', onPressed: install), long: true);
      }
    } catch (e) {
      _say('Nie udało się otworzyć instalacji: $e');
    }
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
        duration: Duration(milliseconds: long ? 15000 : 3000),
      ));
  }
}

class _Hash implements Sink<crypto.Digest> {
  late crypto.Digest value;
  @override
  void add(crypto.Digest data) => value = data;
  @override
  void close() {}
}
