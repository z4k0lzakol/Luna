// Blokada reklam i śledzenia na telefonie.
//
// Listy (EasyList, EasyPrivacy, Peter Lowe, Oficjalne Polskie Filtry) pobieramy przy pierwszym uruchomieniu
// i co kilka dni – jak w Lunie na komputerze; nie są częścią aplikacji (licencje list).
// Z list bierzemy reguły blokujące całe domeny (||domena^ i wpisy w formacie hosts) oraz wyjątki @@||domena^.
//
// Android: każde zapytanie strony sprawdzamy w Dart (zbiór domen, sprawdzenie końcówek nazwy hosta).
//   Wbudowany bloker wtyczki wysyła przed każdym zapytaniem dodatkowe zapytanie HEAD, także do serwerów reklam.
// iOS: reguły WebKit (WKContentRuleList) – sprawdzane natywnie przez system.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:path_provider/path_provider.dart';

class FilterList {
  final String id, name, url;
  const FilterList(this.id, this.name, this.url);
}

const filterLists = [
  FilterList('easylist', 'EasyList', 'https://ublockorigin.github.io/uAssetsCDN/thirdparties/easylist.txt'),
  FilterList('easyprivacy', 'EasyPrivacy', 'https://ublockorigin.github.io/uAssetsCDN/thirdparties/easyprivacy.txt'),
  FilterList('pgl', 'Peter Lowe – serwery reklam',
      'https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=0&mimetype=plaintext'),
  FilterList('pol0', 'Oficjalne Polskie Filtry',
      'https://raw.githubusercontent.com/MajkiIT/polish-ads-filter/master/polish-adblock-filters/adblock.txt'),
];

class AdBlock {
  AdBlock._();
  static final instance = AdBlock._();

  Set<String> any = {};
  Set<String> third = {};
  DateTime? updated;
  bool busy = false;
  String? error;
  List<ContentBlocker>? _iosRules;

  int get domains => any.length + third.length;
  bool get ready => any.isNotEmpty;

  Future<File> _file() async => File('${(await getApplicationSupportDirectory()).path}/adblock_domains.json');

  Future<void> init() async {
    try {
      final f = await _file();
      if (await f.exists()) {
        final m = jsonDecode(await f.readAsString()) as Map;
        any = {for (final d in m['any'] as List) d as String};
        third = {for (final d in m['third'] as List) d as String};
        updated = DateTime.fromMillisecondsSinceEpoch(m['updated'] as int);
      }
    } catch (_) {}
    if (updated == null || DateTime.now().difference(updated!) > const Duration(days: 5)) {
      await update();
    }
  }

  Future<bool> update() async {
    if (busy) return false;
    busy = true;
    error = null;
    final a = <String>{}, t = <String>{}, ok = <String>{};
    var got = 0;
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 20);
    try {
      for (final l in filterLists) {
        try {
          final req = await client.getUrl(Uri.parse(l.url));
          final res = await req.close().timeout(const Duration(seconds: 60));
          if (res.statusCode != 200) continue;
          final text = await res.transform(utf8.decoder).join();
          parse(text, a, t, ok);
          got++;
        } catch (_) {}
      }
    } finally {
      client.close(force: true);
    }
    busy = false;
    if (got == 0) {
      error = 'Nie udało się pobrać list – sprawdź połączenie.';
      return false;
    }
    a.removeAll(ok);
    t.removeAll(ok);
    t.removeAll(a);
    any = a;
    third = t;
    updated = DateTime.now();
    _iosRules = null;
    try {
      await (await _file()).writeAsString(jsonEncode({'any': any.toList(), 'third': third.toList(), 'updated': updated!.millisecondsSinceEpoch}));
    } catch (_) {}
    return true;
  }

  static final _host = RegExp(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$');
  static const _thirdOpts = {'third-party', '3p'};

  /// Reguły domenowe z listy w formacie Adblock/uBlock albo hosts.
  static void parse(String text, Set<String> any, Set<String> third, Set<String> allow) {
    for (var line in const LineSplitter().convert(text)) {
      line = line.trim();
      if (line.isEmpty || line.startsWith('!') || line.startsWith('[') || line.startsWith('#')) continue;
      if (line.startsWith('0.0.0.0 ') || line.startsWith('127.0.0.1 ')) {
        final d = line.split(RegExp(r'\s+'))[1].toLowerCase();
        if (d != 'localhost' && _host.hasMatch(d)) any.add(d);
        continue;
      }
      final exc = line.startsWith('@@||');
      if (!exc && !line.startsWith('||')) continue;
      final body = line.substring(exc ? 4 : 2);
      final caret = body.indexOf('^');
      if (caret <= 0) continue;
      final d = body.substring(0, caret).toLowerCase();
      if (!_host.hasMatch(d)) continue;
      final rest = body.substring(caret + 1);
      if (exc) {
        if (rest.isEmpty || rest.startsWith(r'$') && !rest.contains('domain=')) allow.add(d);
        continue;
      }
      if (rest.isEmpty || rest == r'$important') {
        any.add(d);
      } else if (rest.startsWith(r'$')) {
        final opts = rest.substring(1).split(',').map((o) => o.trim()).toSet()..remove('important');
        if (opts.isNotEmpty && opts.every(_thirdOpts.contains)) third.add(d);
      }
    }
  }

  /// Czy zapytanie z danej strony powinno zostać zablokowane (Android).
  bool blocks(String host, String pageHost) {
    if (host.isEmpty) return false;
    var h = host.toLowerCase();
    final thirdParty = pageHost.isNotEmpty && _base(h) != _base(pageHost);
    while (true) {
      if (any.contains(h)) return true;
      if (thirdParty && third.contains(h)) return true;
      final i = h.indexOf('.');
      if (i < 0) return false;
      h = h.substring(i + 1);
      if (!h.contains('.')) return false;
    }
  }

  static String _base(String h) {
    final p = h.split('.');
    if (p.length <= 2) return h;
    final two = '${p[p.length - 2]}.${p.last}';
    // przybliżenie bez listy sufiksów: co.uk, com.pl, org.pl… → trzy człony
    if (p[p.length - 2].length <= 3 && p.last.length == 2) return '${p[p.length - 3]}.$two';
    return two;
  }

  /// Reguły dla WebKit (iOS); bez dokumentów głównych, żeby nie zablokować strony otwartej przez użytkownika.
  List<ContentBlocker> iosRules() {
    if (_iosRules != null) return _iosRules!;
    final types = [
      ContentBlockerTriggerResourceType.IMAGE,
      ContentBlockerTriggerResourceType.STYLE_SHEET,
      ContentBlockerTriggerResourceType.SCRIPT,
      ContentBlockerTriggerResourceType.FONT,
      ContentBlockerTriggerResourceType.MEDIA,
      ContentBlockerTriggerResourceType.SVG_DOCUMENT,
      ContentBlockerTriggerResourceType.RAW,
    ];
    String rx(String d) => '^https?://([^/]*\\.)?${d.replaceAll('.', '\\.')}[:/]';
    final out = <ContentBlocker>[
      for (final d in any)
        ContentBlocker(
            trigger: ContentBlockerTrigger(urlFilter: rx(d), resourceType: types),
            action: ContentBlockerAction(type: ContentBlockerActionType.BLOCK)),
      for (final d in third)
        ContentBlocker(
            trigger: ContentBlockerTrigger(urlFilter: rx(d), resourceType: types, loadType: [ContentBlockerTriggerLoadType.THIRD_PARTY]),
            action: ContentBlockerAction(type: ContentBlockerActionType.BLOCK)),
    ];
    // WebKit przyjmuje do 150 tys. reguł
    _iosRules = out.length > 140000 ? out.sublist(0, 140000) : out;
    return _iosRules!;
  }
}
