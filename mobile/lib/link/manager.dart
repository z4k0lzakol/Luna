// Połączone urządzenia na telefonie: łączy Luna Link (link.dart) ze stanem Luny i interfejsem.
// Wszystko da się wyłączyć – główny przełącznik (domyślnie wyłączony) i osobno każda funkcja.
import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';

import '../state.dart';
import '../ui/common.dart';
import '../update.dart' show messengerKey;
import 'link.dart';
import 'sync.dart';

/// Do okien (np. „Przyjąć pliki?”) z wątków sieci.
final navigatorKey = GlobalKey<NavigatorState>();

const _native = MethodChannel('luna/link');

/// (id, nazwa, opis, domyślnie)
const phoneFeats = [
  ('open', 'Strony z innych urządzeń', '„Wyślij na urządzenie” na komputerze otwiera stronę w nowej karcie tutaj.', true),
  ('tabs', 'Moje karty widoczne na komputerze', 'Sparowane urządzenia widzą listę kart otwartych na telefonie.', true),
  ('sync', 'Synchronizacja w sieci domowej', 'Kafelki, zakładki i „Na później” wspólne z komputerem, gdy jesteście w tej samej Wi-Fi.', true),
  ('clip', 'Wspólny schowek', 'Tekst skopiowany na komputerze trafia do schowka telefonu; z telefonu wyślesz go przyciskiem „Wyślij schowek”.', false),
  ('files', 'Pliki od sparowanych urządzeń', 'Zdjęcia, filmy i dokumenty bez utraty jakości – trafiają do Pobrane/Luna.', true),
  ('files_auto', 'Przyjmuj pliki od sparowanych bez pytania', 'Bez tego Luna za każdym razem pyta „Przyjmij / Odrzuć”.', false),
  ('files_unpaired', 'Pliki od innych urządzeń w tej sieci', 'Jak LocalSend: każda Luna w Twojej sieci może zaproponować pliki – zawsze z pytaniem.', false),
  ('notify', 'Powiadomienia z komputera', 'Np. „Pobieranie skończone” albo koniec Pomodoro na komputerze.', true),
];

class LinkManager extends LinkHandler with ChangeNotifier {
  static LinkManager? instance;
  final LunaState s;
  Link? link;
  Map<String, dynamic> cfg = {};
  late PhoneSync _sync;
  final Map<String, (String, DateTime, List<Map<String, String>>)> remoteTabs = {};
  final Set<String> _syncing = {};
  Timer? _syncTimer, _debounce;
  String? error;
  (int, int, String)? progress;   // wysyłanie plików: (wysłane, wszystkie, nazwa)

  LinkManager(this.s) {
    instance = this;
  }

  bool get on => cfg['on'] == true;
  void refresh() => notifyListeners();
  bool feat(String k) => ((cfg['feat'] as Map?)?[k] as bool?) ?? phoneFeats.firstWhere((f) => f.$1 == k, orElse: () => (k, '', '', false)).$4;
  void setFeat(String k, bool v) {
    (cfg['feat'] ??= <String, dynamic>{})[k] = v;
    _saveCfg();
    notifyListeners();
  }

  Future<void> init() async {
    final dir = await getApplicationSupportDirectory();
    link = Link(File('${dir.path}/polaczenie.json'), this, name: _defaultName(), type: 'phone');
    cfg = Map<String, dynamic>.from((link!.st['cfg'] ?? {}) as Map);
    _sync = PhoneSync((cfg['sync'] ??= <String, dynamic>{}) as Map<String, dynamic>);
    s.addListener(_stateChanged);
    _native.setMethodCallHandler((call) async {
      if (call.method == 'sharedFiles' && call.arguments is List) _shared([for (final p in call.arguments as List) '$p']);
    });
    if (on) await start();
    try {
      final first = await _native.invokeMethod<List<dynamic>>('initialShared');
      if (first != null && first.isNotEmpty) Future.delayed(const Duration(seconds: 2), () => _shared([for (final p in first) '$p']));
    } catch (_) {}
  }

  String _defaultName() => Platform.isAndroid ? 'Telefon z Androidem' : 'iPhone';

  void _saveCfg() {
    link?.st['cfg'] = cfg;
    link?.save();
  }

  Future<bool> start() async {
    final l = link;
    if (l == null) return false;
    try {
      if (Platform.isAndroid) await _native.invokeMethod('multicast', {'on': true});
    } catch (_) {}
    try {
      await l.start();
      error = null;
    } catch (e) {
      error = 'Nie udało się włączyć połączenia: $e';
      notifyListeners();
      return false;
    }
    _syncTimer?.cancel();
    _syncTimer = Timer.periodic(const Duration(minutes: 3), (_) => syncAll());
    Future.delayed(const Duration(seconds: 4), syncAll);
    notifyListeners();
    return true;
  }

  Future<void> stop() async {
    _syncTimer?.cancel();
    await link?.stop();
    try {
      if (Platform.isAndroid) await _native.invokeMethod('multicast', {'on': false});
    } catch (_) {}
    notifyListeners();
  }

  Future<void> setOn(bool v) async {
    cfg['on'] = v;
    _saveCfg();
    v ? await start() : await stop();
    notifyListeners();
  }

  Map<String, Device> get peers => link?.peers ?? const {};
  List<Device> get nearbyUnpaired => [for (final d in link?.nearby.values ?? const <Device>[]) if (!peers.containsKey(d.id)) d];
  bool reachable(String id) => link?.reachable(id) ?? false;

  // --- LinkHandler (wywołania z sieci) ---
  @override
  List<String> features() => [for (final f in phoneFeats) if (feat(f.$1)) f.$1];

  @override
  bool allowed(String feature, Device? peer) => on && feature != 'approve' && feature != 'remote' && feat(feature);

  @override
  void nearbyChanged() {
    notifyListeners();
    _debounce?.cancel();
    _debounce = Timer(const Duration(seconds: 3), syncAll);
  }

  @override
  void onPaired(Device d) {
    _say('Sparowano: ${d.name}');
    notifyListeners();
    Future.delayed(const Duration(seconds: 1), () => _syncOne(d.id));
  }

  @override
  void onUnpaired(Device d) {
    remoteTabs.remove(d.id);
    notifyListeners();
  }

  @override
  void onOpen(Device d, String url, String title) {
    s.newTab(url: url);
    _say('Strona z urządzenia ${d.name}');
  }

  @override
  List<Map<String, String>> tabs(Device d) => feat('tabs')
      ? [
          for (final t in s.openTabs)
            if (!t.isHome) {'url': t.url, 'title': t.title}
        ]
      : const [];

  @override
  void onClip(Device d, String text) {
    Clipboard.setData(ClipboardData(text: text));
    _say('Schowek z urządzenia ${d.name} – możesz wkleić');
  }

  @override
  Future<Map<String, dynamic>> onSync(Device d, Map<String, dynamic> payload) async {
    if (_sync.merge(s, payload)) s.changed();
    remoteTabs[d.id] = (d.name, DateTime.now(), _tabsOf(payload));
    _markSynced(d.id);
    return _payload();
  }

  @override
  Future<List<int>> offerFiles(Device sender, List<FileOffer> files) async {
    if (sender.paired && feat('files_auto')) return List.generate(files.length, (i) => i);
    final ctx = navigatorKey.currentContext;
    if (ctx == null) return const [];
    final size = files.fold<int>(0, (a, f) => a + f.size);
    final names = files.take(3).map((f) => f.name).join(', ') + (files.length > 3 ? ' i ${files.length - 3} innych' : '');
    final ok = await showDialog<bool>(
      context: ctx,
      builder: (c) => AlertDialog(
        backgroundColor: C.sheet,
        title: Text('${sender.name}${sender.paired ? '' : ' (niesparowane)'} wysyła pliki'),
        content: Text('${files.length} ${files.length == 1 ? 'plik' : 'pliki'} (${humanSize(size)}): $names'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Odrzuć')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Przyjmij')),
        ],
      ),
    ).timeout(const Duration(seconds: 55), onTimeout: () {
      final n = navigatorKey.currentState;
      if (n != null && n.canPop()) n.pop(false);
      return false;
    });
    return ok == true ? List.generate(files.length, (i) => i) : const [];
  }

  @override
  Future<String> filesDir() async => '${(await getTemporaryDirectory()).path}/odebrane';

  @override
  void onFilesDone(Device sender, List<File> files) async {
    final saved = <String>[];
    for (final f in files) {
      saved.add(await _toDownloads(f));
    }
    final one = files.length == 1;
    _say('Odebrano ${one ? 'plik' : '${files.length} pliki'} od ${sender.name} – Pobrane/Luna',
        action: one && saved.first.isNotEmpty ? SnackBarAction(label: 'Otwórz', onPressed: () => _openSaved(saved.first)) : null);
  }

  Future<String> _toDownloads(File f) async {
    final name = f.uri.pathSegments.last;
    if (Platform.isAndroid) {
      try {
        return await _native.invokeMethod<String>('saveToDownloads', {'path': f.path, 'name': name}) ?? '';
      } catch (_) {}
    }
    final docs = Directory('${(await getApplicationDocumentsDirectory()).path}/Luna');
    await docs.create(recursive: true);
    final dest = uniqueFile(docs, name);
    await f.rename(dest.path);
    return dest.uri.toString();
  }

  void _openSaved(String uri) {
    try {
      _native.invokeMethod('openSaved', {'uri': uri});
    } catch (_) {}
  }

  @override
  void onNotify(Device d, String title, String body, String kind) => _say('${d.name}: $title${body.isEmpty ? '' : ' – $body'}', long: true);

  // --- wysyłanie ---
  Future<void> sendUrl(String id, String url, String title) async {
    final name = peers[id]?.name ?? 'urządzenie';
    try {
      await link!.openOn(id, url, title);
      _say('Wysłano na: $name');
    } catch (e) {
      _say('Nie udało się wysłać na $name: $e');
    }
  }

  Future<void> sendClipboard(String id) async {
    final t = (await Clipboard.getData(Clipboard.kTextPlain))?.text ?? '';
    if (t.isEmpty) return _say('Schowek jest pusty');
    try {
      await link!.clipTo(id, t);
      _say('Wysłano schowek na: ${peers[id]?.name}');
    } catch (e) {
      _say('Nie udało się: $e');
    }
  }

  Future<List<String>> pickFiles() async {
    if (!Platform.isAndroid) return const [];
    try {
      return [for (final p in await _native.invokeMethod<List<dynamic>>('pickFiles') ?? const []) '$p'];
    } catch (_) {
      return const [];
    }
  }

  Future<void> sendFiles(Object target, List<String> paths) async {
    final name = target is String ? (peers[target]?.name ?? 'urządzenie') : (target as Device).name;
    _say('Wysyłanie do: $name… czekam, aż odbiorca przyjmie pliki', long: true);
    try {
      final n = await link!.sendFiles(target, [for (final p in paths) File(p)], progress: (d, t, f) {
        progress = (d, t, f);
        notifyListeners();
      });
      _say('Wysłano $n z ${paths.length} do: $name');
    } catch (e) {
      _say('Nie udało się wysłać do $name: $e', long: true);
    } finally {
      progress = null;
      notifyListeners();
      for (final p in paths) {
        try {
          if (p.contains('/wyslij/')) File(p).deleteSync();
        } catch (_) {}
      }
    }
  }

  void Function(List<String> paths)? onSharedFiles;   // ustawia przeglądarka: wybór urządzenia
  void _shared(List<String> paths) {
    if (paths.isEmpty) return;
    if (onSharedFiles != null) {
      onSharedFiles!(paths);
    } else {
      _say('Włącz połączone urządzenia, aby wysłać pliki');
    }
  }

  Future<void> remote(String id, String cmd, [Object? value]) async {
    try {
      await link!.remote(id, cmd, value);
    } catch (e) {
      _say('Pilot: $e');
    }
  }

  Future<List<Map<String, String>>> tabsOf(String id) async {
    try {
      final t = await link!.tabsOf(id);
      remoteTabs[id] = (peers[id]?.name ?? '?', DateTime.now(), t);
      return t;
    } catch (_) {
      return remoteTabs[id]?.$3 ?? const [];
    }
  }

  // --- synchronizacja ---
  Map<String, dynamic> _payload() => _sync.payload(s, link!.id, link!.name, tabs: feat('tabs'));

  List<Map<String, String>> _tabsOf(Map payload) => [
        for (final t in (payload['tabs'] as List? ?? const []))
          if (t is Map && t['url'] is String) {'url': t['url'] as String, 'title': '${t['title'] ?? ''}'}
      ];

  void _stateChanged() {
    if (!on || !feat('sync')) return;
    _debounce?.cancel();
    _debounce = Timer(const Duration(seconds: 20), syncAll);
  }

  void syncAll() {
    if (!on || !feat('sync') || link?.running != true) return;
    for (final id in peers.keys) {
      if (reachable(id)) _syncOne(id);
    }
  }

  Future<void> _syncOne(String id) async {
    if (!on || !feat('sync') || _syncing.contains(id)) return;
    _syncing.add(id);
    try {
      final r = await link!.syncWith(id, _payload());
      if (_sync.merge(s, r)) s.changed();
      remoteTabs[id] = (peers[id]?.name ?? '?', DateTime.now(), _tabsOf(r));
      _markSynced(id);
    } catch (_) {
    } finally {
      _syncing.remove(id);
    }
  }

  void _markSynced(String id) {
    (cfg['last_sync'] ??= <String, dynamic>{})[id] = DateTime.now().millisecondsSinceEpoch;
    _saveCfg();
    notifyListeners();
  }

  DateTime? lastSync(String id) {
    final v = (cfg['last_sync'] as Map?)?[id];
    return v is int ? DateTime.fromMillisecondsSinceEpoch(v) : null;
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
        duration: Duration(milliseconds: long ? 8000 : 3000),
      ));
  }
}

String humanSize(int n) {
  if (n < 1024) return '$n B';
  if (n < 1024 * 1024) return '${(n / 1024).toStringAsFixed(0)} KB';
  if (n < 1024 * 1024 * 1024) return '${(n / 1024 / 1024).toStringAsFixed(1).replaceAll('.', ',')} MB';
  return '${(n / 1024 / 1024 / 1024).toStringAsFixed(1).replaceAll('.', ',')} GB';
}
