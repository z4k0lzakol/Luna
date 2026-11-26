// Stan Luny na telefonie: karty, przestrzenie, historia, zakładki, notatki, zadania i ustawienia.
// Wszystko zostaje na telefonie (SharedPreferences) – bez kont i serwerów Luny.
import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class TabData {
  final String id;
  String url;
  String title;
  final bool private;
  String space;
  bool dark = false;
  TabData({required this.id, this.url = '', this.title = 'Nowa karta', this.private = false, this.space = 'Główna'});

  bool get isHome => url.isEmpty;
  String get host => Uri.tryParse(url)?.host ?? '';

  Map<String, dynamic> toJson() => {'id': id, 'url': url, 'title': title, 'space': space};
  factory TabData.fromJson(Map m) =>
      TabData(id: m['id'] as String, url: (m['url'] ?? '') as String, title: (m['title'] ?? '') as String, space: (m['space'] ?? 'Główna') as String);
}

class Entry {
  final String url;
  final String title;
  final int time;
  Entry(this.url, this.title, [int? time]) : time = time ?? DateTime.now().millisecondsSinceEpoch;
  Map<String, dynamic> toJson() => {'u': url, 't': title, 'd': time};
  factory Entry.fromJson(Map m) => Entry(m['u'] as String, (m['t'] ?? '') as String, (m['d'] ?? 0) as int);
  String get host => Uri.tryParse(url)?.host ?? url;
}

class Task {
  String text;
  bool done;
  Task(this.text, [this.done = false]);
  Map<String, dynamic> toJson() => {'x': text, 'd': done};
  factory Task.fromJson(Map m) => Task(m['x'] as String, (m['d'] ?? false) as bool);
}

const engines = {
  'Brave': 'https://search.brave.com/search?q=',
  'DuckDuckGo': 'https://duckduckgo.com/?q=',
  'Google': 'https://www.google.com/search?q=',
  'Startpage': 'https://www.startpage.com/do/search?query=',
  'Ecosia': 'https://www.ecosia.org/search?q=',
  'Bing': 'https://www.bing.com/search?q=',
};

/// Słowa kluczowe aplikacji w pasku adresu, jak na komputerze: „yt kot” → wyszukiwanie w YouTube, samo „yt” → YouTube.
const appKeywords = {
  'yt': ['https://m.youtube.com/', 'https://m.youtube.com/results?search_query='],
  'youtube': ['https://m.youtube.com/', 'https://m.youtube.com/results?search_query='],
  'sp': ['https://open.spotify.com/', 'https://open.spotify.com/search/'],
  'tt': ['https://www.tiktok.com/', 'https://www.tiktok.com/search?q='],
  'ig': ['https://www.instagram.com/', 'https://www.instagram.com/explore/search/keyword/?q='],
  'fb': ['https://www.facebook.com/', 'https://www.facebook.com/search/top?q='],
  'wiki': ['https://pl.wikipedia.org/', 'https://pl.wikipedia.org/w/index.php?search='],
  'allegro': ['https://allegro.pl/', 'https://allegro.pl/listing?string='],
};

class LunaState extends ChangeNotifier {
  late SharedPreferences _p;
  final _rnd = Random();

  List<TabData> tabs = [];
  String currentId = '';
  String space = 'Główna';
  List<String> spaces = ['Główna'];
  String? splitId;
  double splitRatio = 0.5;

  List<Entry> history = [];
  List<Entry> bookmarks = [];
  List<Entry> later = [];
  List<String> notes = [];
  List<Task> tasks = [];
  Set<String> activeDays = {};
  List<Entry> tiles = [
    Entry('https://www.google.com/', 'Google'),
    Entry('https://m.youtube.com/', 'YouTube'),
    Entry('https://pl.wikipedia.org/', 'Wikipedia'),
  ];

  String engine = 'Brave';
  bool adblock = true;
  bool suggestNet = true;
  Set<String> allow = {};
  bool weatherOn = true;
  Map<String, dynamic> city = {'name': 'Warszawa', 'admin': 'mazowieckie', 'lat': 52.2298, 'lon': 21.0118};
  bool guideDone = false;
  bool focus = false;
  int blockedTotal = 0;
  final Map<String, int> blockedByTab = {};

  Timer? _saveTimer;

  Future<void> load() async {
    _p = await SharedPreferences.getInstance();
    final raw = _p.getString('luna');
    if (raw != null) {
      try {
        final m = jsonDecode(raw) as Map;
        tabs = [for (final t in (m['tabs'] ?? []) as List) TabData.fromJson(t as Map)];
        currentId = (m['current'] ?? '') as String;
        space = (m['space'] ?? 'Główna') as String;
        spaces = [for (final s in (m['spaces'] ?? ['Główna']) as List) s as String];
        history = [for (final e in (m['history'] ?? []) as List) Entry.fromJson(e as Map)];
        bookmarks = [for (final e in (m['bookmarks'] ?? []) as List) Entry.fromJson(e as Map)];
        later = [for (final e in (m['later'] ?? []) as List) Entry.fromJson(e as Map)];
        tiles = [for (final e in (m['tiles'] ?? []) as List) Entry.fromJson(e as Map)];
        notes = [for (final n in (m['notes'] ?? []) as List) n as String];
        tasks = [for (final t in (m['tasks'] ?? []) as List) Task.fromJson(t as Map)];
        activeDays = {for (final d in (m['days'] ?? []) as List) d as String};
        engine = (m['engine'] ?? 'Brave') as String;
        if (!engines.containsKey(engine)) engine = 'Brave';
        adblock = (m['adblock'] ?? true) as bool;
        suggestNet = (m['suggestNet'] ?? true) as bool;
        allow = {for (final d in (m['allow'] ?? []) as List) d as String};
        weatherOn = (m['weather'] ?? true) as bool;
        if (m['city'] is Map) city = Map<String, dynamic>.from(m['city'] as Map);
        guideDone = (m['guide'] ?? false) as bool;
        blockedTotal = (m['blocked'] ?? 0) as int;
      } catch (_) {}
    }
    if (!spaces.contains(space)) spaces.add(space);
    if (tabs.where((t) => t.space == space).isEmpty) newTab(notify: false);
    if (tabs.every((t) => t.id != currentId)) currentId = tabs.firstWhere((t) => t.space == space).id;
    markActive();
  }

  void _save() {
    _saveTimer?.cancel();
    _saveTimer = Timer(const Duration(milliseconds: 400), () {
      _p.setString(
          'luna',
          jsonEncode({
            'tabs': [for (final t in tabs.where((t) => !t.private)) t.toJson()],
            'current': currentId,
            'space': space,
            'spaces': spaces,
            'history': [for (final e in history.take(800)) e.toJson()],
            'bookmarks': [for (final e in bookmarks) e.toJson()],
            'later': [for (final e in later) e.toJson()],
            'tiles': [for (final e in tiles) e.toJson()],
            'notes': notes,
            'tasks': [for (final t in tasks) t.toJson()],
            'days': activeDays.toList(),
            'engine': engine,
            'adblock': adblock,
            'suggestNet': suggestNet,
            'allow': allow.toList(),
            'weather': weatherOn,
            'city': city,
            'guide': guideDone,
            'blocked': blockedTotal,
          }));
    });
  }

  void changed() {
    _save();
    notifyListeners();
  }

  // ---------------------------------------------------------------- karty
  TabData get current => tabs.firstWhere((t) => t.id == currentId, orElse: () => tabs.first);
  TabData? byId(String? id) {
    for (final t in tabs) {
      if (t.id == id) return t;
    }
    return null;
  }

  List<TabData> get openTabs => tabs.where((t) => t.space == space && !t.private).toList();
  List<TabData> get privateTabs => tabs.where((t) => t.private).toList();

  String _id() => '${DateTime.now().microsecondsSinceEpoch}${_rnd.nextInt(999)}';

  TabData newTab({String url = '', bool private = false, bool notify = true, bool activate = true}) {
    final t = TabData(id: _id(), url: url, title: url.isEmpty ? 'Nowa karta' : url, private: private, space: space);
    tabs.add(t);
    if (activate) currentId = t.id;
    if (notify) changed();
    return t;
  }

  void activate(String id) {
    currentId = id;
    final t = byId(id);
    if (t != null && !t.private && t.space != space) space = t.space;
    changed();
  }

  void close(String id) {
    final idx = tabs.indexWhere((t) => t.id == id);
    if (idx < 0) return;
    final wasCurrent = id == currentId;
    final t = tabs.removeAt(idx);
    blockedByTab.remove(id);
    if (splitId == id) splitId = null;
    if (wasCurrent) {
      final same = tabs.where((x) => x.private == t.private && (t.private || x.space == space)).toList();
      if (same.isNotEmpty) {
        currentId = same.last.id;
      } else if (openTabs.isNotEmpty) {
        currentId = openTabs.last.id;
      } else {
        newTab(notify: false);
      }
    }
    if (openTabs.isEmpty && privateTabs.isEmpty) newTab(notify: false);
    changed();
  }

  void closeAll({bool private = false}) {
    for (final t in (private ? privateTabs : openTabs)) {
      tabs.remove(t);
      if (splitId == t.id) splitId = null;
    }
    if (tabs.every((t) => t.id != currentId)) {
      if (openTabs.isNotEmpty) {
        currentId = openTabs.last.id;
      } else {
        newTab(notify: false);
      }
    }
    changed();
  }

  /// Kolejna / poprzednia karta (przesunięcie paska w bok).
  void step(int d) {
    final list = current.private ? privateTabs : openTabs;
    final i = list.indexWhere((t) => t.id == currentId);
    if (i < 0 || list.length < 2) return;
    currentId = list[(i + d) % list.length].id;
    changed();
  }

  void pageLoaded(TabData t, String url, String title) {
    t.url = url;
    if (title.isNotEmpty) t.title = title;
    if (!t.private && url.startsWith('http')) {
      history.removeWhere((e) => e.url == url);
      history.insert(0, Entry(url, t.title));
      if (history.length > 1000) history.removeRange(1000, history.length);
    }
    changed();
  }

  void saveForLater(TabData t) {
    if (t.isHome) return;
    later.removeWhere((e) => e.url == t.url);
    later.insert(0, Entry(t.url, t.title));
    close(t.id);
  }

  void moveToSpace(TabData t, String s) {
    t.space = s;
    if (t.id == currentId) space = s;
    changed();
  }

  void addSpace(String name) {
    name = name.trim();
    if (name.isEmpty || spaces.contains(name)) return;
    spaces.add(name);
    switchSpace(name);
  }

  void switchSpace(String s) {
    space = s;
    final list = openTabs;
    if (list.isEmpty) {
      newTab(notify: false);
    } else {
      currentId = list.last.id;
    }
    splitId = null;
    changed();
  }

  // ---------------------------------------------------------------- reszta
  void markActive() {
    final n = DateTime.now();
    activeDays.add('${n.year}-${n.month}-${n.day}');
    _save();
  }

  bool dayActive(DateTime d) => activeDays.contains('${d.year}-${d.month}-${d.day}');

  int get streak {
    var d = DateTime.now();
    var n = 0;
    while (dayActive(d)) {
      n++;
      d = d.subtract(const Duration(days: 1));
    }
    return n;
  }

  Timer? _blockTimer;
  /// Zmienia się, gdy rośnie licznik tarczy – odświeża tylko plakietkę, nie cały ekran.
  final blocks = ValueNotifier<int>(0);

  /// Licznik tarczy – odświeżenie paska najwyżej co pół sekundy (strona potrafi mieć dziesiątki blokad naraz).
  void countBlocked(String tabId) {
    blockedTotal++;
    blockedByTab[tabId] = (blockedByTab[tabId] ?? 0) + 1;
    _blockTimer ??= Timer(const Duration(milliseconds: 500), () {
      _blockTimer = null;
      _save();
      blocks.value++;
    });
  }

  bool allowedHere(String host) {
    for (final d in allow) {
      if (host == d || host.endsWith('.$d')) return true;
    }
    return false;
  }

  /// Tekst z paska adresu → adres strony.
  String resolve(String input) {
    final s = input.trim();
    if (s.isEmpty) return '';
    final low = s.toLowerCase();
    final parts = low.split(RegExp(r'\s+'));
    final kw = appKeywords[parts.first];
    if (kw != null) {
      if (parts.length == 1) return kw[0];
      return kw[1] + Uri.encodeComponent(s.substring(s.indexOf(' ') + 1).trim());
    }
    if (RegExp(r'^(https?|about|data|file):', caseSensitive: false).hasMatch(s)) return s;
    if (!s.contains(' ') && RegExp(r'^(localhost|[\w-]+(\.[\w-]+)+)(:\d+)?(/.*)?$').hasMatch(s)) return 'https://$s';
    return engines[engine]! + Uri.encodeQueryComponent(s);
  }

  List<Entry> suggest(String q) {
    q = q.trim().toLowerCase();
    if (q.isEmpty) return [];
    final out = <Entry>[];
    final seen = <String>{};
    for (final e in [...bookmarks, ...history]) {
      if ((e.url.toLowerCase().contains(q) || e.title.toLowerCase().contains(q)) && seen.add(e.url)) out.add(e);
      if (out.length >= 5) break;
    }
    return out;
  }

  @override
  void dispose() {
    _saveTimer?.cancel();
    super.dispose();
  }
}

String hostOf(String url) {
  final h = Uri.tryParse(url)?.host ?? '';
  return h.startsWith('www.') ? h.substring(4) : h;
}

void debugLog(String s) {
  if (kDebugMode) debugPrint('[luna] $s');
}
