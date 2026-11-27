// Synchronizacja telefonu z Luną na komputerze w sieci domowej – ten sam ładunek co plik .lunasync na komputerze.
// Kolekcja w całości: nowsza (czas zmiany) wygrywa. Pola, których telefon nie zna (np. ikona kafelka, folder zakładki),
// zostają zachowane z wersji komputera.
import 'dart:convert';

import 'package:crypto/crypto.dart' as crypto;

import '../state.dart';

/// Kolekcje telefonu ↔ nazwy z komputera: kafelki, zakładki, „Na później” ↔ „Do przeczytania”.
const syncCols = {'tiles': 'name', 'bookmarks': 'title', 'readlater': 'title'};

List<Entry> _listOf(LunaState s, String col) => switch (col) {
      'tiles' => s.tiles,
      'bookmarks' => s.bookmarks,
      _ => s.later,
    };

void _setList(LunaState s, String col, List<Entry> v) {
  switch (col) {
    case 'tiles':
      s.tiles = v;
    case 'bookmarks':
      s.bookmarks = v;
    default:
      s.later = v;
  }
}

String _hash(Object v) => crypto.sha1.convert(utf8.encode(jsonEncode(v))).toString();

class PhoneSync {
  /// Stan synchronizacji (zapisywany przez menedżera): {"state": {kol: {hash, mtime}}, "raw": {kol: [...]}}
  final Map<String, dynamic> st;
  PhoneSync(this.st);

  Map<String, dynamic> get _state => (st['state'] ??= <String, dynamic>{}) as Map<String, dynamic>;
  Map<String, dynamic> get _raw => (st['raw'] ??= <String, dynamic>{}) as Map<String, dynamic>;

  /// Lista w formacie komputera – z zachowaniem pól, których telefon nie ma.
  List<Map<String, dynamic>> _export(LunaState s, String col) {
    final key = syncCols[col]!;
    final old = {for (final m in (_raw[col] as List? ?? const [])) '${(m as Map)['url']}': Map<String, dynamic>.from(m)};
    return [
      for (final e in _listOf(s, col)) {...(old[e.url] ?? {}), 'url': e.url, key: e.title}
    ];
  }

  int _stamp(String col, List v) {
    final h = _hash(v);
    final cur = (_state[col] as Map?) ?? {};
    if (cur['hash'] != h) {
      _state[col] = {'hash': h, 'mtime': DateTime.now().millisecondsSinceEpoch ~/ 1000};
    }
    return (_state[col] as Map)['mtime'] as int;
  }

  Map<String, dynamic> payload(LunaState s, String device, String name, {bool tabs = true}) {
    final cols = <String, dynamic>{}, mtime = <String, int>{};
    for (final col in syncCols.keys) {
      final v = _export(s, col);
      cols[col] = v;
      mtime[col] = _stamp(col, v);
    }
    return {
      'v': 1,
      'device': device,
      'name': name,
      't': DateTime.now().millisecondsSinceEpoch ~/ 1000,
      'cols': cols,
      'mtime': mtime,
      'logins': const [],
      'deleted': const {},
      'tabs': tabs
          ? [
              for (final t in s.openTabs)
                if (!t.isHome) {'url': t.url, 'title': t.title}
            ]
          : const [],
    };
  }

  /// Scala ładunek z komputera. Zwraca true, gdy coś się zmieniło na telefonie.
  bool merge(LunaState s, Map<String, dynamic> r) {
    final cols = (r['cols'] as Map?) ?? {}, mts = (r['mtime'] as Map?) ?? {};
    var changed = false;
    for (final col in syncCols.keys) {
      final v = cols[col];
      if (v is! List) continue;
      _stamp(col, _export(s, col));   // najpierw zarejestruj lokalne zmiany
      final remoteT = (mts[col] ?? 0) as int, localT = ((_state[col] as Map?)?['mtime'] ?? 0) as int;
      if (remoteT <= localT) continue;
      final key = syncCols[col]!;
      final list = [
        for (final m in v)
          if (m is Map && m['url'] is String) Map<String, dynamic>.from(m)
      ];
      _setList(s, col, [for (final m in list) Entry(m['url'] as String, '${m[key] ?? m['title'] ?? m['name'] ?? ''}')]);
      _raw[col] = list;
      _state[col] = {'hash': _hash(_export(s, col)), 'mtime': remoteT};
      changed = true;
    }
    return changed;
  }
}
