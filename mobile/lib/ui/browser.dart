// Przeglądarka: strony w zaokrąglonych ramkach, pasek na dole (tarcza, adres, karty, menu), gesty,
// dwie strony jedna pod drugą, arkusze menu i asystenta, blokada reklam.
import 'dart:async';
import 'dart:collection';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:url_launcher/url_launcher.dart';

import '../adblock.dart';
import '../link/manager.dart';
import '../scripts.dart';
import '../state.dart';
import '../suggest.dart';
import '../thumbs.dart';
import 'common.dart';
import 'devices.dart';
import 'home.dart';
import 'lists.dart';
import 'menu.dart';
import 'panel.dart';
import 'tabs.dart';
import 'updates.dart';
import 'widgets.dart';

/// Zmienia się po pobraniu / aktualizacji list – strony na iOS dostają wtedy nowe reguły.
final blockerVersion = ValueNotifier<int>(0);

class BrowserScreen extends StatefulWidget {
  final LunaState s;
  final String userAgent;
  final VoidCallback onGuide;
  const BrowserScreen({super.key, required this.s, required this.userAgent, required this.onGuide});

  @override
  State<BrowserScreen> createState() => _BrowserScreenState();
}

class _BrowserScreenState extends State<BrowserScreen> with WidgetsBindingObserver {
  static const _maxAlive = 4;
  final _used = <String, DateTime>{};   // ostatnie użycie karty – usypianie nieużywanych
  Timer? _sleepT;
  String? _lastCur;

  LunaState get s => widget.s;
  final _ctls = <String, InAppWebViewController>{};
  final _ptr = <String, PullToRefreshController>{};
  final _keys = <String, GlobalKey>{};
  final _alive = <String>[];
  Map<String, Uint8List> get _thumbs => ThumbStore.instance.map;
  final _zoom = <String, int>{};
  final _progress = <String, ValueNotifier<double>>{}; // pasek postępu odświeża tylko siebie, nie cały ekran
  final _lastY = <String, int>{};

  bool _barVisible = true;
  bool _editing = false;
  final _addr = TextEditingController();
  final _addrFocus = FocusNode();
  List<Entry> _sugg = [];
  List<String> _net = [];
  Timer? _netT;

  String? _sTop, _sBot; // dwie strony: górna i dolna
  double _ratio = 0.5;
  double _dir = 0; // kierunek wjazdu strony po przełączeniu karty (-1 / 0 / 1)

  late final UnmodifiableListView<UserScript> _scripts = UnmodifiableListView([
    UserScript(source: youtubeScript, injectionTime: UserScriptInjectionTime.AT_DOCUMENT_START, forMainFrameOnly: true),
    UserScript(source: consentScript, injectionTime: UserScriptInjectionTime.AT_DOCUMENT_END, forMainFrameOnly: true),
  ]);

  @override
  void initState() {
    super.initState();
    blockerVersion.addListener(_applyBlocker);
    WidgetsBinding.instance.addObserver(this);
    ThumbStore.instance.load({for (final t in s.tabs) t.id});
    _sleepT = Timer.periodic(const Duration(minutes: 1), (_) => _sleepIdle());
    LinkManager.instance?.onSharedFiles = (paths) async {   // „Udostępnij → Luna”: wybór urządzenia
      final m = LinkManager.instance!;
      if (!mounted) return;
      final t = await pickDevice(context, m, 'Wyślij ${paths.length == 1 ? 'plik' : '${paths.length} pliki'} do', nearby: true);
      if (t != null && mounted) await pickAndSend(context, m, t, paths);
    };
  }

  @override
  void dispose() {
    blockerVersion.removeListener(_applyBlocker);
    WidgetsBinding.instance.removeObserver(this);
    _sleepT?.cancel();
    _netT?.cancel();
    _addr.dispose();
    _addrFocus.dispose();
    super.dispose();
  }

  // ------------------------------------------------------------------ strony
  bool get _split => _sTop != null && _sBot != null && s.byId(_sTop) != null && s.byId(_sBot) != null;

  void _touch(String id) {
    _alive.removeWhere((x) => s.byId(x) == null);
    _used[id] = DateTime.now();
    if (_alive.isNotEmpty && _alive.last == id) return;
    _alive.remove(id);
    _alive.add(id);
    while (_alive.length > _maxAlive) {
      // usypia najdawniej używaną kartę: przy powrocie strona wczyta się od nowa
      final old = _alive.firstWhere((x) => x != _sTop && x != _sBot && x != s.currentId, orElse: () => '');
      if (old.isEmpty) break;
      _sleep(old);
    }
  }

  bool _keepAwake(String id) => id == s.currentId || id == _sTop || id == _sBot;

  /// Usypia kartę: strona znika z pamięci (podgląd zostaje), przy powrocie wczyta się od nowa.
  void _sleep(String id) {
    _alive.remove(id);
    _ctls.remove(id);
    _ptr.remove(id);
    _progress.remove(id);
  }

  /// Karty nieużywane dłużej niż ustawienie (Ustawienia → Usypiaj nieużywane karty).
  void _sleepIdle() {
    final min = s.sleepMinutes;
    if (min <= 0 || !mounted) return;
    final now = DateTime.now();
    final idle = [for (final id in _alive) if (!_keepAwake(id) && now.difference(_used[id] ?? now).inMinutes >= min) id];
    if (idle.isEmpty) return;
    setState(() => idle.forEach(_sleep));
  }

  /// Mało pamięci (Android): usypia wszystkie karty w tle.
  @override
  void didHaveMemoryPressure() {
    final bg = [for (final id in _alive) if (!_keepAwake(id)) id];
    if (bg.isNotEmpty && mounted) setState(() => bg.forEach(_sleep));
  }

  bool asleep(String id) => !_alive.contains(id);

  final Map<String, (DateTime, int, int)> _perfLoad = {};   // pomiar (LUNA_PERF): początek, żądania, zablokowane

  InAppWebViewSettings _settings(TabData t) => InAppWebViewSettings(
        userAgent: Platform.isAndroid && widget.userAgent.isNotEmpty ? widget.userAgent : null,
        applicationNameForUserAgent: Platform.isIOS ? 'Version/18.0 Safari/604.1' : null,
        incognito: t.private,
        useShouldOverrideUrlLoading: true,
        useShouldInterceptRequest: Platform.isAndroid && !const bool.fromEnvironment('LUNA_NOINTERCEPT'),
        contentBlockers: Platform.isIOS && s.adblock && !s.allowedHere(t.host) ? AdBlock.instance.iosRules() : [],
        supportMultipleWindows: true,
        javaScriptCanOpenWindowsAutomatically: false,
        safeBrowsingEnabled: false,
        isFraudulentWebsiteWarningEnabled: false,
        allowsBackForwardNavigationGestures: true,
        allowsInlineMediaPlayback: true,
        mediaPlaybackRequiresUserGesture: true,
        textZoom: _zoom[t.id] ?? 100,
        // tryb tekstury: animacje Luny nad stroną są kilka razy płynniejsze niż w trybie hybrydowym (pomiar w emulatorze)
        useHybridComposition: const String.fromEnvironment('LUNA_HC', defaultValue: '0') == '1',
        transparentBackground: false,
      );

  PullToRefreshController? _refresher(TabData t) {
    if (_ptr.containsKey(t.id)) return _ptr[t.id];
    final p = PullToRefreshController(
      settings: PullToRefreshSettings(color: C.text, backgroundColor: const Color(0xFF1C1C1C)),
      onRefresh: () async => _ctls[t.id]?.reload(),
    );
    _ptr[t.id] = p;
    return p;
  }

  Widget _webview(TabData t) => InAppWebView(
        initialUrlRequest: URLRequest(url: WebUri(t.url)),
        initialSettings: _settings(t),
        initialUserScripts: _scripts,
        pullToRefreshController: _refresher(t),
        onWebViewCreated: (c) => _ctls[t.id] = c,
        onLoadStart: (c, u) {
          s.blockedByTab[t.id] = 0;
          if (kPerf) _perfLoad[t.id] = (DateTime.now(), 0, 0);
          if (t.id == s.currentId && !_barVisible) setState(() => _barVisible = true);
        },
        onProgressChanged: (c, p) => _progress.putIfAbsent(t.id, () => ValueNotifier(1)).value = p / 100,
        onPageCommitVisible: kPerf
            ? (c, u) {
                final p = _perfLoad[t.id];
                if (p != null) debugPrint('LUNAPERF widoczna ${u?.host} ${DateTime.now().difference(p.$1).inMilliseconds} ms');
              }
            : null,
        onLoadStop: (c, u) async {
          _ptr[t.id]?.endRefreshing();
          final pl = _perfLoad.remove(t.id);
          if (pl != null) {
            debugPrint('LUNAPERF zaladowana ${u?.host} ${DateTime.now().difference(pl.$1).inMilliseconds} ms, zadan ${pl.$2}, zablokowanych ${pl.$3}');
          }
          if (u == null) return;
          final title = await c.getTitle() ?? '';
          s.pageLoaded(t, u.toString(), title);
          if (t.dark) await c.evaluateJavascript(source: darkScript(true));
          Future.delayed(const Duration(milliseconds: 900), () => _thumb(t.id));
        },
        onReceivedError: (c, req, err) => _ptr[t.id]?.endRefreshing(),
        onTitleChanged: (c, title) {
          if (title != null && title.isNotEmpty && title != t.title) {
            t.title = title;
            s.changed();
          }
        },
        onUpdateVisitedHistory: (c, u, reload) {
          final v = u?.toString() ?? '';
          if (v.startsWith('http') && v != t.url) {
            t.url = v;
            s.changed();
          }
        },
        onScrollChanged: (c, x, y) {
          if (t.id != s.currentId) return;
          final last = _lastY[t.id] ?? 0;
          _lastY[t.id] = y;
          if (y - last > 14 && _barVisible && y > 80) {
            setState(() => _barVisible = false);
          } else if (last - y > 14 && !_barVisible) {
            setState(() => _barVisible = true);
          }
        },
        shouldOverrideUrlLoading: (c, a) async {
          final u = a.request.url;
          if (u == null) return NavigationActionPolicy.ALLOW;
          const web = {'http', 'https', 'about', 'data', 'blob', 'javascript', 'file'};
          if (!web.contains(u.scheme)) {
            try {
              await launchUrl(u, mode: LaunchMode.externalApplication);
            } catch (_) {}
            return NavigationActionPolicy.CANCEL;
          }
          return NavigationActionPolicy.ALLOW;
        },
        shouldInterceptRequest: Platform.isAndroid
            ? (c, req) async {
                if (kPerf) {
                  final p = _perfLoad[t.id];
                  if (p != null) _perfLoad[t.id] = (p.$1, p.$2 + 1, p.$3);
                }
                if (!s.adblock || req.isForMainFrame == true) return null;
                final page = t.host;
                if (page.isNotEmpty && s.allowedHere(page)) return null;
                if (!AdBlock.instance.blocks(req.url.host, page)) return null;
                s.countBlocked(t.id);
                if (kPerf) {
                  final p = _perfLoad[t.id];
                  if (p != null) _perfLoad[t.id] = (p.$1, p.$2, p.$3 + 1);
                }
                return WebResourceResponse(contentType: 'text/plain', data: Uint8List(0), statusCode: 200, reasonPhrase: 'OK');
              }
            : null,
        onCreateWindow: (c, a) async {
          final u = a.request.url?.toString() ?? '';
          if (u.startsWith('http')) {
            s.newTab(url: u, private: t.private);
          }
          return false;
        },
        onDownloadStartRequest: (c, r) async {
          try {
            await launchUrl(r.url, mode: LaunchMode.externalApplication);
          } catch (_) {}
        },
        onPermissionRequest: (c, r) async => PermissionResponse(resources: r.resources, action: PermissionResponseAction.DENY),
      );

  Future<void> _thumb(String id) async {
    final c = _ctls[id];
    final t = s.byId(id);
    if (c == null || t == null || t.isHome) return;
    try {
      final b = await c.takeScreenshot(
          screenshotConfiguration: ScreenshotConfiguration(compressFormat: CompressFormat.JPEG, quality: 45, snapshotWidth: 360));
      if (b != null && b.isNotEmpty) await ThumbStore.instance.put(id, b, private: t.private);
    } catch (_) {}
  }

  /// Ramka strony: cienki nagłówek (litera strony, tytuł) i zaokrąglona strona.
  Widget _frame(TabData t, {bool bottomPane = false}) {
    if (t.isHome) {
      return HomeView(s: s, onOpen: (u) => _openIn(t, u), onSpaces: _spaces, onLater: () => _openTabs(segment: 1), onSearch: _startEditing);
    }
    final active = t.id == s.currentId;
    final progress = _progress.putIfAbsent(t.id, () => ValueNotifier(1));
    final landscape = MediaQuery.of(context).orientation == Orientation.landscape;
    Widget nav(IconData i, String tip, VoidCallback f) => IconButton(
        tooltip: tip, onPressed: f, visualDensity: VisualDensity.compact, icon: Icon(i, size: 18, color: active ? const Color(0xFFBDBDBD) : C.muted));
    final header = (s.focus || landscape) && !_split
        ? const SizedBox(height: 4)
        : SizedBox(
            height: 38,
            child: Row(children: [
              const SizedBox(width: 6),
              nav(Icons.arrow_back, 'Wstecz', () => _ctls[t.id]?.goBack()),
              nav(Icons.arrow_forward, 'Dalej', () => _ctls[t.id]?.goForward()),
              const SizedBox(width: 4),
              SiteLetter(t.host),
              const SizedBox(width: 8),
              Expanded(
                  child: Text(t.private ? 'Prywatna · ${t.title}' : t.title,
                      maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 12.5, color: active ? const Color(0xFFBDBDBD) : const Color(0xFF7A7A7A)))),
              if (_split && bottomPane)
                IconButton(tooltip: 'Zamknij dolną stronę', onPressed: _closeSplit, icon: const Icon(Icons.close, size: 16, color: C.muted))
              else if (!_split)
                IconButton(
                    tooltip: 'Druga strona obok', onPressed: _chooseSplit, icon: const Icon(Icons.view_agenda_outlined, size: 17, color: C.muted)),
              const SizedBox(width: 6),
            ]),
          );
    return Listener(
      onPointerDown: (_) {
        if (_split && !active) s.activate(t.id);
      },
      child: Column(children: [
        header,
        Expanded(
          child: Padding(
            padding: EdgeInsets.fromLTRB(s.focus && !_split ? 0 : 8, landscape && !_split ? 4 : 0, s.focus && !_split ? 0 : 8, landscape ? 8 : 0),
            child: DecoratedBox(
              position: DecorationPosition.foreground,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(s.focus && !_split ? 0 : 20),
                border: Border.all(color: _split && active ? const Color(0xFF8A8A8A) : Colors.transparent),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(s.focus && !_split ? 0 : 20),
                child: Stack(children: [
                  Positioned.fill(child: _webview(t)),
                  Positioned(
                    left: 0,
                    right: 0,
                    top: 0,
                    child: ValueListenableBuilder<double>(
                      valueListenable: progress,
                      builder: (_, v, __) => AnimatedOpacity(
                        opacity: v < 1 ? 1 : 0,
                        duration: const Duration(milliseconds: 250),
                        child: TweenAnimationBuilder<double>(
                          tween: Tween(end: v),
                          duration: const Duration(milliseconds: 200),
                          curve: Curves.easeOutCubic,
                          builder: (_, x, __) => LinearProgressIndicator(value: x, minHeight: 2, backgroundColor: Colors.transparent, color: C.cream),
                        ),
                      ),
                    ),
                  ),
                ]),
              ),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _page(TabData t, {bool bottomPane = false}) =>
      // osobny klucz dla każdej orientacji: po obrocie telefonu strona dostaje nowy widok (Android nie przenosi widoku
      // strony w trybie tekstury do zupełnie innego układu – zostawał czarny ekran); strona wczytuje się wtedy od nowa
      KeyedSubtree(
          key: _keys.putIfAbsent('${t.id}-${MediaQuery.of(context).orientation.name}', () => GlobalKey()),
          child: _frame(t, bottomPane: bottomPane));

  Widget _content(TabData cur) {
    final shown = <String>{};
    Widget main;
    if (_split) {
      final top = s.byId(_sTop)!, bot = s.byId(_sBot)!;
      shown.addAll([top.id, bot.id]);
      final wide = MediaQuery.of(context).orientation == Orientation.landscape;
      main = LayoutBuilder(builder: (ctx, box) {
        if (wide) {
          return Row(children: [
            SizedBox(width: (box.maxWidth - 22) * _ratio, child: _page(top)),
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onHorizontalDragUpdate: (d) => setState(() => _ratio = (_ratio + d.delta.dx / (box.maxWidth - 22)).clamp(0.25, 0.75)),
              onDoubleTap: () => setState(() {
                final x = _sTop;
                _sTop = _sBot;
                _sBot = x;
              }),
              child: SizedBox(
                  width: 22,
                  child: Center(child: Container(width: 5, height: 44, decoration: BoxDecoration(color: const Color(0xFF6A6A6A), borderRadius: BorderRadius.circular(3))))),
            ),
            Expanded(child: EnterAnim(key: ValueKey('split-${bot.id}'), from: const Offset(0.25, 0), ms: 340, child: _page(bot, bottomPane: true))),
          ]);
        }
        return Column(children: [
          SizedBox(height: (box.maxHeight - 22) * _ratio, child: _page(top)),
          GestureDetector(
            behavior: HitTestBehavior.opaque,
            onVerticalDragUpdate: (d) => setState(() => _ratio = (_ratio + d.delta.dy / (box.maxHeight - 22)).clamp(0.25, 0.75)),
            onDoubleTap: () => setState(() {
              final x = _sTop;
              _sTop = _sBot;
              _sBot = x;
            }),
            child: Semantics(
              label: 'Uchwyt podziału: przeciągnij, by zmienić proporcje; dotknij dwa razy, by zamienić strony',
              child: SizedBox(
                  height: 22,
                  child: Center(child: Container(width: 44, height: 5, decoration: BoxDecoration(color: const Color(0xFF6A6A6A), borderRadius: BorderRadius.circular(3))))),
            ),
          ),
          Expanded(child: EnterAnim(key: ValueKey('split-${bot.id}'), from: const Offset(0, 0.25), ms: 340, child: _page(bot, bottomPane: true))),
        ]);
      });
    } else {
      shown.add(cur.id);
      main = EnterAnim(key: ValueKey('main-${cur.id}'), from: Offset(_dir * 0.06, 0), child: _page(cur));
    }
    final hidden = [for (final id in _alive) if (!shown.contains(id)) s.byId(id)].whereType<TabData>().where((t) => !t.isHome).toList();
    return Stack(children: [
      Positioned.fill(child: main),
      for (final t in hidden) Offstage(child: _page(t)),
    ]);
  }

  // ------------------------------------------------------------------ nawigacja
  void _openIn(TabData t, String url) {
    if (url.isEmpty) return;
    if (t.isHome || _ctls[t.id] == null) {
      t.url = url;
      t.title = hostOf(url);
      s.activate(t.id);
    } else {
      _ctls[t.id]!.loadUrl(urlRequest: URLRequest(url: WebUri(url)));
      s.activate(t.id);
    }
  }

  void _open(String url) => _openIn(s.current, url);

  Future<void> _back() async {
    if (_editing) {
      _stopEditing();
      return;
    }
    final cur = s.current;
    final c = _ctls[cur.id];
    if (!cur.isHome && c != null && await c.canGoBack()) {
      await c.goBack();
      return;
    }
    if (_split) {
      _closeSplit();
      return;
    }
    if (!cur.isHome) {
      cur.url = '';
      cur.title = 'Nowa karta';
      _ctls.remove(cur.id);
      s.changed();
      return;
    }
    await SystemNavigator.pop();
  }

  void _typed(String v) {
    setState(() => _sugg = s.suggest(v).take(3).toList());
    _netT?.cancel();
    if (!s.suggestNet || v.trim().length < 2 || v.contains('://')) {
      if (_net.isNotEmpty) setState(() => _net = []);
      return;
    }
    _netT = Timer(const Duration(milliseconds: 180), () async {
      final sw = Stopwatch()..start();
      final r = await netSuggestions(s.engine, v);
      if (kPerf) debugPrint('LUNAPERF podpowiedzi ${sw.elapsedMilliseconds} ms (${r.length})');
      if (mounted && _editing && _addr.text == v) setState(() => _net = r);
    });
  }

  void _go(String text) {
    _stopEditing();
    _open(s.resolve(text));
  }

  void _startEditing() {
    final cur = s.current;
    _addr.text = cur.isHome ? '' : cur.url;
    _addr.selection = TextSelection(baseOffset: 0, extentOffset: _addr.text.length);
    setState(() {
      _editing = true;
      _sugg = [];
      _net = [];
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => _addrFocus.requestFocus());
  }

  void _stopEditing() {
    _addrFocus.unfocus();
    setState(() => _editing = false);
  }

  void _closeSplit() => setState(() {
        if (s.currentId == _sBot && _sTop != null) s.activate(_sTop!);
        _sTop = _sBot = null;
      });

  Future<void> _chooseSplit() async {
    final others = s.openTabs.where((t) => t.id != s.currentId).toList();
    final id = await showLunaSheet<String>(context, heightFactor: 0.6, (ctx) => ListView(padding: const EdgeInsets.symmetric(horizontal: 8), children: [
          Padding(padding: const EdgeInsets.fromLTRB(12, 0, 12, 8), child: Text(MediaQuery.of(context).orientation == Orientation.landscape ? 'Druga strona obok' : 'Druga strona pod spodem', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w500))),
          ListTile(leading: const Icon(Icons.add), title: const Text('Nowa karta'), onTap: () => Navigator.pop(ctx, '+')),
          for (final t in others)
            ListTile(
                leading: t.isHome ? const Icon(Icons.nightlight_round, color: C.cream) : SiteLetter(t.host, size: 24),
                title: Text(t.isHome ? 'Nowa karta' : t.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                onTap: () => Navigator.pop(ctx, t.id)),
        ]));
    if (id == null) return;
    final top = s.currentId;
    final bot = id == '+' ? s.newTab(activate: false).id : id;
    _splitWith(top, bot);
  }

  void _splitWith(String top, String bot) {
    if (top == bot) return;
    setState(() {
      _sTop = top;
      _sBot = bot;
      _ratio = 0.5;
    });
    s.activate(top);
  }

  Future<void> _openTabs({int segment = 0}) async {
    // miniatura bieżącej karty – najwyżej 150 ms, żeby siatka kart otwierała się bez czekania
    await _thumb(s.currentId).timeout(const Duration(milliseconds: 150), onTimeout: () {});
    if (!mounted) return;
    await Navigator.push(
        context,
        PageRouteBuilder(
          transitionDuration: const Duration(milliseconds: 240),
          reverseTransitionDuration: const Duration(milliseconds: 200),
          pageBuilder: (_, __, ___) => TabsScreen(
            s: s,
            thumbs: _thumbs,
            asleep: asleep,
            initialSegment: segment,
            onSplit: (id) {
              final cur = s.currentId;
              _splitWith(cur, id);
            },
          ),
          transitionsBuilder: (_, a, __, child) => FadeTransition(
              opacity: CurvedAnimation(parent: a, curve: Curves.easeOutCubic),
              child: SlideTransition(position: Tween(begin: const Offset(0, 0.04), end: Offset.zero).animate(CurvedAnimation(parent: a, curve: Curves.easeOutCubic)), child: child)),
        ));
    setState(() {});
  }

  Future<void> _spaces() async {
    await showLunaSheet<void>(context, heightFactor: 0.5, (ctx) => ListView(children: [
          for (final sp in s.spaces)
            ListTile(
              leading: Icon(sp == s.space ? Icons.radio_button_checked : Icons.radio_button_unchecked, color: C.text2),
              title: Text(sp),
              onTap: () {
                Navigator.pop(ctx);
                setState(() => _sTop = _sBot = null);
                s.switchSpace(sp);
              },
            ),
          ListTile(
              leading: const Icon(Icons.add),
              title: const Text('Nowa przestrzeń'),
              onTap: () async {
                Navigator.pop(ctx);
                final n = await askText(context, 'Nazwa przestrzeni', 'np. Szkoła, Praca');
                if (n != null) s.addSpace(n);
              }),
        ]));
  }

  void _applyBlocker() async {
    if (!Platform.isIOS) return;
    for (final e in _ctls.entries) {
      final t = s.byId(e.key);
      if (t == null) continue;
      try {
        final st = await e.value.getSettings();
        if (st == null) continue;
        st.contentBlockers = s.adblock && !s.allowedHere(t.host) ? AdBlock.instance.iosRules() : [];
        await e.value.setSettings(settings: st);
      } catch (_) {}
    }
  }

  // ------------------------------------------------------------------ arkusze
  Future<void> _shield() async {
    final cur = s.current;
    await showLunaSheet(
        context,
        heightFactor: 0.82,
        (ctx) => ShieldSheet(
            s: s,
            host: cur.isHome ? '' : cur.host,
            blockedHere: s.blockedByTab[cur.id] ?? 0,
            onChanged: () {
              blockerVersion.value++;
              _ctls[cur.id]?.reload();
            }));
  }

  Future<void> _panel() async {
    final cur = s.current;
    var sel = '';
    try {
      sel = (await _ctls[cur.id]?.evaluateJavascript(source: selectionScript))?.toString() ?? '';
    } catch (_) {}
    if (!mounted) return;
    await showLunaSheet(
        context,
        heightFactor: 0.8,
        (ctx) => PanelSheet(
              s: s,
              pageTitle: cur.isHome ? '' : cur.title,
              pageUrl: cur.isHome ? '' : cur.url,
              selection: sel.length > 600 ? sel.substring(0, 600) : sel,
              userAgent: widget.userAgent,
              onOpenTab: (u) => s.newTab(url: u),
            ));
  }

  Future<void> _menu() async {
    final cur = s.current;
    final c = _ctls[cur.id];
    final id = await showLunaSheet<String>(
        context,
        heightFactor: 0.88,
        (ctx) => MenuSheet(
              onPage: !cur.isHome,
              dark: cur.dark,
              focus: s.focus,
              zoom: _zoom[cur.id] ?? 100,
              onZoom: (z) async {
                _zoom[cur.id] = z;
                final st = await c?.getSettings();
                if (st == null) return;
                if (Platform.isIOS) {
                  st.pageZoom = z / 100;
                } else {
                  st.textZoom = z;
                }
                await c?.setSettings(settings: st);
              },
            ));
    if (id == null || !mounted) return;
    final needsPage = {'later', 'addBookmark', 'reader', 'translate', 'dark', 'copy', 'sendTab'};
    if (needsPage.contains(id) && cur.isHome) {
      toast(context, 'Najpierw otwórz stronę');
      return;
    }
    switch (id) {
      case 'new':
        s.newTab();
      case 'private':
        s.newTab(private: true);
      case 'history':
        _push(EntryList(
            s: s,
            title: 'Historia',
            items: () => s.history,
            onOpen: _open,
            empty: 'Historia jest pusta.',
            onClear: () {
              s.history.clear();
              s.changed();
            }));
      case 'settings':
        _push(SettingsScreen(s: s, onOpen: (u) => s.newTab(url: u), onGuide: widget.onGuide, onBlockerChanged: () => blockerVersion.value++));
      case 'tabs':
        _openTabs();
      case 'split':
        _split ? _closeSplit() : _chooseSplit();
      case 'space':
        _spaces();
      case 'later':
        s.saveForLater(cur);
        toast(context, 'Odłożono na później');
      case 'bookmarks':
        _push(EntryList(s: s, title: 'Zakładki', items: () => s.bookmarks, onOpen: _open, empty: 'Brak zakładek. Dodasz je w menu → Dodaj zakładkę.'));
      case 'addBookmark':
        s.bookmarks.removeWhere((e) => e.url == cur.url);
        s.bookmarks.insert(0, Entry(cur.url, cur.title));
        s.changed();
        toast(context, 'Dodano do zakładek');
      case 'notes':
        _push(NotesScreen(s));
      case 'widgets':
        _push(WidgetsScreen(s));
      case 'reader':
        _reader();
      case 'translate':
        s.newTab(url: 'https://translate.google.com/translate?sl=auto&tl=pl&u=${Uri.encodeComponent(cur.url)}');
      case 'dark':
        cur.dark = !cur.dark;
        await c?.evaluateJavascript(source: darkScript(cur.dark));
        setState(() {});
      case 'copy':
        await Clipboard.setData(ClipboardData(text: cur.url));
        if (mounted) toast(context, 'Skopiowano adres');
      case 'focus':
        s.focus = !s.focus;
        s.changed();
        if (mounted) toast(context, s.focus ? 'Tryb skupienia: strona na cały ekran, pasek chowa się przy przewijaniu' : 'Tryb skupienia wyłączony');
      case 'shield':
        _shield();
      case 'updates':
        _push(const UpdatesScreen());
      case 'guide':
        widget.onGuide();
      case 'panel':
        _panel();
      case 'devices':
        final lmDevices = LinkManager.instance;
        if (lmDevices != null) _push(DevicesScreen(m: lmDevices, onOpen: _open));
      case 'sendTab':
        final lmSendTab = LinkManager.instance;
        if (lmSendTab == null) return;
        final toTab = await pickDevice(context, lmSendTab, 'Wyślij stronę na');
        if (toTab is String) await lmSendTab.sendUrl(toTab, cur.url, cur.title);
      case 'sendFiles':
        final lmSendFiles = LinkManager.instance;
        if (lmSendFiles == null) return;
        final toFiles = await pickDevice(context, lmSendFiles, 'Wyślij pliki do', nearby: true);
        if (toFiles != null && mounted) await pickAndSend(context, lmSendFiles, toFiles);
      case 'remote':
        final lmRemote = LinkManager.instance;
        if (lmRemote == null) return;
        final pc = await pickDevice(context, lmRemote, 'Pilot – komputer', desktopsOnly: true);
        if (pc is String && mounted) _push(RemoteScreen(m: lmRemote, d: lmRemote.peers[pc]!));
    }
  }

  void _push(Widget w) => Navigator.push(context, MaterialPageRoute(builder: (_) => w));

  Future<void> _reader() async {
    final c = _ctls[s.currentId];
    if (c == null) return;
    try {
      final r = await c.evaluateJavascript(source: readerScript);
      final m = jsonDecode(r.toString()) as Map;
      final items = [for (final it in m['items'] as List) ReaderItem(it['h'] == true, it['t'] as String)];
      if (items.isEmpty) {
        if (mounted) toast(context, 'Na tej stronie nie ma tekstu do czytania');
        return;
      }
      _push(ReaderScreen(title: m['title'] as String, site: m['site'] as String, items: items));
    } catch (_) {
      if (mounted) toast(context, 'Nie udało się przygotować trybu czytania');
    }
  }

  // ------------------------------------------------------------------ pasek
  Widget _shieldButton(TabData cur) {
    final blocked = s.blockedByTab[cur.id] ?? 0;
    final allowed = !cur.isHome && s.allowedHere(cur.host);
    return Stack(clipBehavior: Clip.none, children: [
      SquareButton(
        label: 'Tarcza: zablokowano $blocked',
        onTap: _shield,
        child: Icon(s.adblock && !allowed ? Icons.shield_outlined : Icons.remove_moderator_outlined, size: 20, color: C.text2),
      ),
      if (blocked > 0 && s.adblock && !allowed)
        Positioned(
          top: -5,
          right: -5,
          child: Container(
            constraints: const BoxConstraints(minWidth: 18),
            height: 18,
            padding: const EdgeInsets.symmetric(horizontal: 4),
            alignment: Alignment.center,
            decoration: BoxDecoration(color: C.text, borderRadius: BorderRadius.circular(9)),
            child: Text(blocked > 99 ? '99+' : '$blocked', style: const TextStyle(color: Color(0xFF111111), fontSize: 10, fontWeight: FontWeight.w600)),
          ),
        ),
    ]);
  }

  Widget _bar(TabData cur, {bool top = false}) {
    final count = cur.private ? s.privateTabs.length : s.openTabs.length;
    if (_editing) {
      final list = (_sugg.isNotEmpty || _net.isNotEmpty)
          ? Container(
              margin: const EdgeInsets.fromLTRB(12, 0, 12, 8),
              constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * (top ? 0.6 : 0.45)),
              decoration: BoxDecoration(color: C.card, borderRadius: BorderRadius.circular(16), border: Border.all(color: C.border)),
              child: ListView(shrinkWrap: true, padding: const EdgeInsets.symmetric(vertical: 4), reverse: !top, children: [
                for (final q in _net)
                  ListTile(
                    dense: true,
                    leading: const Icon(Icons.search, size: 18, color: C.muted),
                    title: Text(q, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 14.5)),
                    trailing: IconButton(
                      tooltip: 'Wstaw do pola',
                      icon: Icon(top ? Icons.south_west : Icons.north_west, size: 16, color: C.muted),
                      onPressed: () {
                        _addr.text = '$q ';
                        _addr.selection = TextSelection.collapsed(offset: _addr.text.length);
                        _typed(_addr.text);
                      },
                    ),
                    onTap: () => _go(q),
                  ),
                for (final e in _sugg)
                  ListTile(
                    dense: true,
                    leading: SiteLetter(hostOf(e.url), size: 22),
                    title: Text(e.title.isEmpty ? e.url : e.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                    subtitle: Text(hostOf(e.url), style: const TextStyle(color: C.muted)),
                    onTap: () {
                      _stopEditing();
                      _open(e.url);
                    },
                  ),
              ]),
            )
          : const SizedBox.shrink();
      final field = Padding(
        padding: EdgeInsets.fromLTRB(12, 8, 12, top ? 8 : 10),
        child: Row(children: [
          Expanded(
            child: TextField(
              controller: _addr,
              focusNode: _addrFocus,
              keyboardType: TextInputType.url,
              textInputAction: TextInputAction.go,
              autocorrect: false,
              onChanged: _typed,
              onSubmitted: _go,
              style: const TextStyle(fontSize: 15),
              decoration: InputDecoration(
                hintText: 'Szukaj lub wpisz adres',
                isDense: true,
                filled: true,
                fillColor: C.field,
                prefixIcon: const Icon(Icons.search, size: 18, color: Color(0xFF8F8F8F)),
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(15), borderSide: const BorderSide(color: C.border2)),
                enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(15), borderSide: const BorderSide(color: C.border2)),
                focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(15), borderSide: const BorderSide(color: Color(0xFF555555))),
              ),
            ),
          ),
          TextButton(onPressed: _stopEditing, child: const Text('Anuluj', style: TextStyle(color: C.text2))),
        ]),
      );
      return Column(mainAxisSize: MainAxisSize.min, children: top ? [field, list] : [list, field]);
    }

    final shield = ValueListenableBuilder<int>(valueListenable: s.blocks, builder: (_, __, ___) => _shieldButton(cur));
    final address = Expanded(
      child: Material(
        color: C.field,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15), side: const BorderSide(color: C.border2)),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: _startEditing,
          child: SizedBox(
            height: 46,
            child: Row(children: [
              const SizedBox(width: 14),
              if (!cur.isHome) ...[
                Icon(cur.url.startsWith('https') ? Icons.lock_outline : Icons.info_outline, size: 14, color: const Color(0xFF8F8F8F)),
                const SizedBox(width: 8),
              ],
              Expanded(
                child: Text(cur.isHome ? 'Szukaj lub wpisz adres' : (top ? cur.url : hostOf(cur.url)),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 14, color: cur.isHome ? const Color(0xFF8F8F8F) : const Color(0xFFDCDCDC))),
              ),
              if (!cur.isHome)
                IconButton(
                  tooltip: 'Odśwież',
                  onPressed: () => _ctls[cur.id]?.reload(),
                  icon: const Icon(Icons.refresh, size: 18, color: Color(0xFF8F8F8F)),
                ),
            ]),
          ),
        ),
      ),
    );
    final tabs = SquareButton(
      label: 'Karty: $count otwarte',
      onTap: _openTabs,
      onLongPress: () => s.newTab(private: cur.private),
      child: Container(
        width: 22,
        height: 22,
        alignment: Alignment.center,
        decoration: BoxDecoration(border: Border.all(color: C.text2, width: 1.7), borderRadius: BorderRadius.circular(6)),
        child: Text(count > 99 ? ':)' : '$count', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
      ),
    );
    final menu = SquareButton(label: 'Menu Luny', onTap: _menu, child: const Icon(Icons.menu, size: 20, color: C.text2));
    const gap = SizedBox(width: 8);

    if (top) {
      Widget icon(IconData i, String tip, VoidCallback? f) =>
          IconButton(tooltip: tip, onPressed: f, icon: Icon(i, size: 20, color: f == null ? const Color(0xFF555555) : C.text2));
      final c = _ctls[cur.id];
      return Padding(
        padding: const EdgeInsets.fromLTRB(8, 6, 12, 2),
        child: Row(children: [
          icon(Icons.arrow_back, 'Wstecz', cur.isHome ? null : () => c?.goBack()),
          icon(Icons.arrow_forward, 'Dalej', cur.isHome ? null : () => c?.goForward()),
          gap,
          shield,
          gap,
          address,
          gap,
          SquareButton(
              label: _split ? 'Jedna strona' : 'Druga strona obok',
              onTap: _split ? _closeSplit : _chooseSplit,
              child: Icon(_split ? Icons.crop_square : Icons.vertical_split_outlined, size: 20, color: C.text2)),
          gap,
          SquareButton(label: 'Asystent AI i komunikatory', onTap: _panel, child: const Icon(Icons.auto_awesome_outlined, size: 20, color: C.text2)),
          gap,
          tabs,
          gap,
          menu,
        ]),
      );
    }
    return GestureDetector(
      onHorizontalDragEnd: (d) {
        final v = d.primaryVelocity ?? 0;
        if (v.abs() > 350) {
          _dir = v < 0 ? 1 : -1;
          s.step(v < 0 ? 1 : -1);
          Future.delayed(const Duration(milliseconds: 400), () => _dir = 0);
        }
      },
      onVerticalDragEnd: (d) {
        if ((d.primaryVelocity ?? 0) < -350) _openTabs();
      },
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
        child: Row(children: [shield, gap, address, gap, tabs, gap, menu]),
      ),
    );
  }

  Orientation? _orient;

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: s,
        builder: (ctx, _) {
          final cur = s.current;
          final o = MediaQuery.of(context).orientation;
          if (_orient != null && _orient != o) {
            _ctls.clear();
            _ptr.clear();
            _keys.removeWhere((k, _) => !k.endsWith('-${o.name}'));
          }
          _orient = o;
          if (_lastCur != null && _lastCur != cur.id) {
            final prev = _lastCur!;   // podgląd karty, z której odchodzisz (jeszcze żywa w tle)
            Future.microtask(() => _thumb(prev));
          }
          _lastCur = cur.id;
          if (!cur.isHome) _touch(cur.id);
          if (_split) {
            _touch(_sTop!);
            _touch(_sBot!);
          }
          final showBar = _editing || _barVisible || cur.isHome;
          final landscape = MediaQuery.of(context).orientation == Orientation.landscape;
          if (landscape) {
            // poziomo: jeden pasek u góry (jak na komputerze), strony pod nim
            return PopScope(
              canPop: false,
              onPopInvokedWithResult: (did, _) {
                if (!did) _back();
              },
              child: Scaffold(
                backgroundColor: C.bg,
                resizeToAvoidBottomInset: true,
                body: SafeArea(
                  bottom: false,
                  child: Column(children: [
                    BarSlot(
                      visible: showBar,
                      top: true,
                      child: _bar(cur, top: true),
                      hidden: GestureDetector(
                              onTap: () => setState(() => _barVisible = true),
                              child: Container(
                                height: 12,
                                alignment: Alignment.center,
                                child: Container(
                                    width: 36, height: 4, decoration: BoxDecoration(color: const Color(0xFF3A3A3A), borderRadius: BorderRadius.circular(2))),
                              ),
                            ),
                    ),
                    Expanded(child: _content(cur)),
                  ]),
                ),
              ),
            );
          }
          return PopScope(
            canPop: false,
            onPopInvokedWithResult: (did, _) {
              if (!did) _back();
            },
            child: Scaffold(
              backgroundColor: C.bg,
              resizeToAvoidBottomInset: true,
              body: SafeArea(
                bottom: false,
                top: !(cur.isHome && !_split),
                child: Column(children: [
                  Expanded(
                    child: Stack(children: [
                      Positioned.fill(child: _content(cur)),
                      if (!cur.isHome && !_editing && showBar)
                        Positioned(
                          right: 18,
                          bottom: 14,
                          child: Semantics(
                            button: true,
                            label: 'Asystent AI i komunikatory',
                            child: Material(
                              color: C.field,
                              shape: const CircleBorder(side: BorderSide(color: Color(0xFF2E2E2E))),
                              elevation: 6,
                              child: InkWell(
                                customBorder: const CircleBorder(),
                                onTap: _panel,
                                child: const SizedBox(width: 46, height: 46, child: Icon(Icons.auto_awesome_outlined, size: 20, color: C.text)),
                              ),
                            ),
                          ),
                        ),
                    ]),
                  ),
                  BarSlot(
                    visible: showBar,
                    child: SafeArea(top: false, child: _bar(cur)),
                    hidden: GestureDetector(
                            onTap: () => setState(() => _barVisible = true),
                            child: Container(
                              height: MediaQuery.of(context).padding.bottom + 10,
                              alignment: Alignment.topCenter,
                              child: Container(margin: const EdgeInsets.only(top: 3), width: 36, height: 4, decoration: BoxDecoration(color: const Color(0xFF3A3A3A), borderRadius: BorderRadius.circular(2))),
                            ),
                          ),
                  ),
                ]),
              ),
            ),
          );
        },
      );
}

/// Pasek, który chowa się przesunięciem (bez zmiany rozmiaru strony w każdej klatce): przy chowaniu najpierw
/// zjeżdża, a dopiero potem zwalnia miejsce; przy pokazaniu najpierw zajmuje miejsce, potem wjeżdża.
class BarSlot extends StatefulWidget {
  final bool visible;
  final bool top;
  final Widget child;
  final Widget hidden;
  const BarSlot({super.key, required this.visible, required this.child, required this.hidden, this.top = false});

  @override
  State<BarSlot> createState() => _BarSlotState();
}

class _BarSlotState extends State<BarSlot> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 220), reverseDuration: const Duration(milliseconds: 180), value: widget.visible ? 1 : 0);
  late bool _laid = widget.visible;

  @override
  void didUpdateWidget(BarSlot old) {
    super.didUpdateWidget(old);
    if (widget.visible == old.visible) return;
    if (widget.visible) {
      setState(() => _laid = true);
      _c.forward();
    } else {
      _c.reverse().then((_) {
        if (mounted && !widget.visible) setState(() => _laid = false);
      });
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_laid) return widget.hidden;
    return ClipRect(
      child: AnimatedBuilder(
        animation: _c,
        builder: (_, child) {
          final v = Curves.easeOutCubic.transform(_c.value);
          return FractionalTranslation(translation: Offset(0, (widget.top ? -1 : 1) * (1 - v)), child: Opacity(opacity: 0.4 + 0.6 * v, child: child));
        },
        child: widget.child,
      ),
    );
  }
}
