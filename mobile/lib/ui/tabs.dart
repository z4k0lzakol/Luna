// Karty i przestrzenie: Otwarte · Na później · Prywatne, wyszukiwanie, menu karty po przytrzymaniu.
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../state.dart';
import 'common.dart';

class TabsScreen extends StatefulWidget {
  final LunaState s;
  final Map<String, Uint8List> thumbs;
  final bool Function(String id)? asleep;   // karta uśpiona (strona nie zajmuje pamięci)
  final int initialSegment;
  final void Function(String id) onSplit;
  const TabsScreen({super.key, required this.s, required this.thumbs, required this.onSplit, this.asleep, this.initialSegment = 0});

  @override
  State<TabsScreen> createState() => _TabsScreenState();
}

class _TabsScreenState extends State<TabsScreen> {
  late int _seg = widget.initialSegment;
  String _q = '';
  bool _search = false;

  LunaState get s => widget.s;

  bool _match(String title, String url) {
    final q = _q.trim().toLowerCase();
    return q.isEmpty || title.toLowerCase().contains(q) || url.toLowerCase().contains(q);
  }

  Future<void> pickSpace() async {
    final name = await showLunaSheet<String>(context, heightFactor: 0.5, (ctx) => ListView(children: [
          for (final sp in s.spaces)
            ListTile(
              leading: Icon(sp == s.space ? Icons.radio_button_checked : Icons.radio_button_unchecked, color: C.text2),
              title: Text(sp),
              trailing: Text('${s.tabs.where((t) => t.space == sp && !t.private).length}', style: const TextStyle(color: C.muted)),
              onTap: () => Navigator.pop(ctx, sp),
            ),
          ListTile(leading: const Icon(Icons.add), title: const Text('Nowa przestrzeń'), onTap: () => Navigator.pop(ctx, '+')),
        ]));
    if (name == null || !mounted) return;
    if (name == '+') {
      final n = await askText(context, 'Nazwa przestrzeni', 'np. Szkoła, Praca');
      if (n != null) s.addSpace(n);
    } else {
      s.switchSpace(name);
    }
    setState(() {});
  }

  void _tabMenu(TabData t) {
    showLunaSheet(context, heightFactor: 0.45, (ctx) => ListView(children: [
          ListTile(title: Text(t.title, maxLines: 1, overflow: TextOverflow.ellipsis), subtitle: Text(hostOf(t.url))),
          if (!t.isHome && !t.private)
            ListTile(leading: const Icon(Icons.schedule), title: const Text('Na później'), onTap: () {
              s.saveForLater(t);
              Navigator.pop(ctx);
            }),
          if (!t.private)
            ListTile(leading: const Icon(Icons.layers_outlined), title: const Text('Przenieś do przestrzeni'), onTap: () async {
              Navigator.pop(ctx);
              final sp = await showLunaSheet<String>(context, heightFactor: 0.45, (c2) => ListView(children: [
                    for (final x in s.spaces) ListTile(title: Text(x), onTap: () => Navigator.pop(c2, x)),
                  ]));
              if (sp != null) s.moveToSpace(t, sp);
            }),
          if (t.id != s.currentId)
            ListTile(leading: const Icon(Icons.horizontal_split_outlined), title: const Text('Otwórz pod spodem'), onTap: () {
              Navigator.pop(ctx);
              Navigator.pop(context);
              widget.onSplit(t.id);
            }),
          ListTile(leading: const Icon(Icons.close), title: const Text('Zamknij'), onTap: () {
            s.close(t.id);
            Navigator.pop(ctx);
          }),
        ]));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: C.bg,
      body: SafeArea(
        child: AnimatedBuilder(
          animation: s,
          builder: (ctx, _) {
            final open = s.openTabs.where((t) => _match(t.title, t.url)).toList();
            final priv = s.privateTabs.where((t) => _match(t.title, t.url)).toList();
            final later = s.later.where((e) => _match(e.title, e.url)).toList();
            return Column(children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 12, 12, 0),
                child: Row(children: [
                  const Text('Karty', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w500)),
                  const Spacer(),
                  IconButton(tooltip: 'Szukaj kart', onPressed: () => setState(() => _search = !_search), icon: const Icon(Icons.search, color: C.text2)),
                  OutlinedButton.icon(
                    onPressed: pickSpace,
                    icon: const Icon(Icons.layers_outlined, size: 16),
                    label: Text('Przestrzeń: ${s.space}'),
                    style: OutlinedButton.styleFrom(
                        foregroundColor: C.text2, side: const BorderSide(color: C.border2), backgroundColor: C.field, shape: const StadiumBorder()),
                  ),
                ]),
              ),
              if (_search)
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
                  child: TextField(
                    autofocus: true,
                    onChanged: (v) => setState(() => _q = v),
                    decoration: InputDecoration(
                      isDense: true,
                      hintText: 'Szukaj w kartach',
                      prefixIcon: const Icon(Icons.search, size: 18),
                      filled: true,
                      fillColor: C.field,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: C.border2)),
                    ),
                  ),
                ),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 14, 20, 0),
                child: Segmented(
                  labels: ['Otwarte · ${s.openTabs.length}', 'Na później · ${s.later.length}', 'Prywatne · ${s.privateTabs.length}'],
                  index: _seg,
                  onChanged: (i) => setState(() => _seg = i),
                ),
              ),
              Expanded(
                child: _seg == 1
                    ? _laterList(later)
                    : GridView.count(
                        padding: const EdgeInsets.fromLTRB(16, 16, 16, 100),
                        // telefon: 2 kolumny; tablet i poziomo: tyle, ile się zmieści (karta ok. 220 px)
                        crossAxisCount: (MediaQuery.of(context).size.width / 220).floor().clamp(2, 6),
                        mainAxisSpacing: 12,
                        crossAxisSpacing: 12,
                        childAspectRatio: 0.78,
                        children: [
                          for (final (i, t) in (_seg == 0 ? open : priv).indexed)
                            Reveal(i, key: ValueKey('$_seg-${t.id}'), stepMs: 40, child: _card(t)),
                        ],
                      ),
              ),
            ]);
          },
        ),
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 10),
          child: Row(children: [
            if (_seg != 1)
              OutlinedButton(
                onPressed: () {
                  s.closeAll(private: _seg == 2);
                  if (_seg == 0) Navigator.pop(context);
                },
                style: OutlinedButton.styleFrom(
                    foregroundColor: C.text2,
                    backgroundColor: C.field,
                    side: const BorderSide(color: C.border2),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15))),
                child: const Text('Zamknij wszystkie'),
              ),
            const Spacer(),
            CreamButton(_seg == 2 ? 'Nowa prywatna' : 'Nowa karta', icon: Icons.add, onTap: () {
              s.newTab(private: _seg == 2);
              Navigator.pop(context);
            }),
          ]),
        ),
      ),
    );
  }

  Widget _card(TabData t) {
    final active = t.id == s.currentId;
    final thumb = widget.thumbs[t.id];
    return Material(
      color: C.card,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18), side: BorderSide(color: active ? const Color(0xFF8A8A8A) : C.border)),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () {
          s.activate(t.id);
          Navigator.pop(context);
        },
        onLongPress: () => _tabMenu(t),
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 6, 2, 4),
            child: Row(children: [
              t.isHome ? const Icon(Icons.nightlight_round, size: 15, color: C.cream) : SiteLetter(t.host),
              const SizedBox(width: 6),
              Expanded(child: Text(t.isHome ? 'Nowa karta' : t.title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: Color(0xFFDCDCDC)))),
              if (!t.isHome && (widget.asleep?.call(t.id) ?? false))
                const Tooltip(message: 'Uśpiona – wczyta się po otwarciu', child: Icon(Icons.bedtime_outlined, size: 14, color: C.muted)),
              IconButton(
                tooltip: 'Zamknij kartę',
                visualDensity: VisualDensity.compact,
                onPressed: () => s.close(t.id),
                icon: const Icon(Icons.close, size: 15, color: C.muted),
              ),
            ]),
          ),
          Expanded(
            child: Container(
              margin: const EdgeInsets.fromLTRB(6, 0, 6, 6),
              decoration: BoxDecoration(borderRadius: BorderRadius.circular(13), color: t.isHome ? C.bg : const Color(0xFF1B1B1B)),
              clipBehavior: Clip.antiAlias,
              width: double.infinity,
              child: thumb != null
                  ? Image.memory(thumb, fit: BoxFit.cover, alignment: Alignment.topCenter, gaplessPlayback: true)
                  : t.isHome
                      ? const StarField(child: Center(child: Icon(Icons.nightlight_round, color: C.cream, size: 28)))
                      : Center(child: SiteLetter(t.host, size: 36)),
            ),
          ),
        ]),
      ),
    );
  }

  Widget _laterList(List<Entry> later) {
    if (later.isEmpty) {
      return const Center(
          child: Padding(
        padding: EdgeInsets.all(32),
        child: Text('Przytrzymaj kartę i wybierz „Na później”. Odłożone karty nie zajmują pamięci.',
            textAlign: TextAlign.center, style: TextStyle(color: C.muted, height: 1.5)),
      ));
    }
    return ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 100), children: [
      for (final e in later)
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Dismissible(
            key: ObjectKey(e),
            onDismissed: (_) {
              s.later.remove(e);
              s.changed();
            },
            child: LunaCard(
              onTap: () {
                s.later.remove(e);
                s.newTab(url: e.url);
                Navigator.pop(context);
              },
              child: Row(children: [
                SiteLetter(hostOf(e.url), size: 30),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(e.title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 14)),
                    Text(hostOf(e.url), style: const TextStyle(fontSize: 12, color: C.muted)),
                  ]),
                ),
              ]),
            ),
          ),
        ),
    ]);
  }
}

Future<String?> askText(BuildContext context, String title, String hint, {String initial = ''}) {
  final c = TextEditingController(text: initial);
  return showDialog<String>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: C.sheet,
      title: Text(title),
      content: TextField(controller: c, autofocus: true, decoration: InputDecoration(hintText: hint), onSubmitted: (v) => Navigator.pop(ctx, v)),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Anuluj')),
        TextButton(onPressed: () => Navigator.pop(ctx, c.text), child: const Text('OK')),
      ],
    ),
  ).then((v) => (v == null || v.trim().isEmpty) ? null : v.trim());
}
