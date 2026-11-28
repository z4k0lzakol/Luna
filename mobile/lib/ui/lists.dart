// Historia, zakładki, notatki, tarcza, ustawienia i tryb czytania.
import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';

import '../adblock.dart';
import '../state.dart';
import '../update.dart';
import 'common.dart';
import 'tabs.dart';
import 'updates.dart';
import 'widgets.dart';

class _Page extends StatelessWidget {
  final String title;
  final List<Widget> actions;
  final Widget child;
  const _Page({required this.title, required this.child, this.actions = const []});

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: C.bg,
        body: SafeArea(
          child: Column(children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(4, 6, 8, 0),
              child: Row(children: [
                IconButton(tooltip: 'Wróć', onPressed: () => Navigator.pop(context), icon: const Icon(Icons.chevron_left, color: C.text2)),
                Expanded(child: Text(title, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w500))),
                ...actions,
              ]),
            ),
            Expanded(child: child),
          ]),
        ),
      );
}

class EntryList extends StatefulWidget {
  final LunaState s;
  final String title;
  final List<Entry> Function() items;
  final ValueChanged<String> onOpen;
  final String empty;
  final VoidCallback? onClear;
  const EntryList({super.key, required this.s, required this.title, required this.items, required this.onOpen, required this.empty, this.onClear});

  @override
  State<EntryList> createState() => _EntryListState();
}

class _EntryListState extends State<EntryList> {
  String _q = '';

  @override
  Widget build(BuildContext context) => _Page(
        title: widget.title,
        actions: [
          if (widget.onClear != null)
            TextButton(
                onPressed: () {
                  widget.onClear!();
                  setState(() {});
                },
                child: const Text('Wyczyść', style: TextStyle(color: C.muted))),
        ],
        child: AnimatedBuilder(
          animation: widget.s,
          builder: (ctx, _) {
            final q = _q.toLowerCase();
            final list = widget.items().where((e) => q.isEmpty || e.title.toLowerCase().contains(q) || e.url.toLowerCase().contains(q)).toList();
            return ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 24), children: [
              TextField(
                onChanged: (v) => setState(() => _q = v),
                decoration: InputDecoration(
                  isDense: true,
                  hintText: 'Szukaj',
                  prefixIcon: const Icon(Icons.search, size: 18),
                  filled: true,
                  fillColor: C.field,
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: C.border2)),
                ),
              ),
              const SizedBox(height: 10),
              if (list.isEmpty) Padding(padding: const EdgeInsets.all(24), child: Text(widget.empty, textAlign: TextAlign.center, style: const TextStyle(color: C.muted))),
              for (final e in list.take(300))
                Dismissible(
                  key: ObjectKey(e),
                  onDismissed: (_) {
                    widget.items().remove(e);
                    widget.s.changed();
                  },
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(horizontal: 4),
                    leading: SiteLetter(hostOf(e.url), size: 28),
                    title: Text(e.title.isEmpty ? e.url : e.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                    subtitle: Text(hostOf(e.url), style: const TextStyle(color: C.muted, fontSize: 12)),
                    onTap: () {
                      Navigator.pop(context);
                      widget.onOpen(e.url);
                    },
                  ),
                ),
            ]);
          },
        ),
      );
}

class NotesScreen extends StatelessWidget {
  final LunaState s;
  const NotesScreen(this.s, {super.key});

  Future<void> _edit(BuildContext context, [int? i]) async {
    final c = TextEditingController(text: i == null ? '' : s.notes[i]);
    final v = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: C.sheet,
        title: Text(i == null ? 'Nowa notatka' : 'Notatka'),
        content: TextField(controller: c, autofocus: true, minLines: 4, maxLines: 10),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Anuluj')),
          TextButton(onPressed: () => Navigator.pop(ctx, c.text), child: const Text('Zapisz')),
        ],
      ),
    );
    if (v == null) return;
    if (i == null) {
      if (v.trim().isNotEmpty) s.notes.insert(0, v.trim());
    } else if (v.trim().isEmpty) {
      s.notes.removeAt(i);
    } else {
      s.notes[i] = v.trim();
    }
    s.changed();
  }

  @override
  Widget build(BuildContext context) => _Page(
        title: 'Notatki',
        actions: [IconButton(tooltip: 'Nowa notatka', onPressed: () => _edit(context), icon: const Icon(Icons.add, color: C.text2))],
        child: AnimatedBuilder(
          animation: s,
          builder: (ctx, _) => ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 24), children: [
            if (s.notes.isEmpty) const Padding(padding: EdgeInsets.all(24), child: Text('Brak notatek. Dodaj pierwszą przyciskiem +.', textAlign: TextAlign.center, style: TextStyle(color: C.muted))),
            for (var i = 0; i < s.notes.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: LunaCard(onTap: () => _edit(context, i), child: Text(s.notes[i], maxLines: 6, overflow: TextOverflow.ellipsis, style: const TextStyle(height: 1.45))),
              ),
          ]),
        ),
      );
}

/// Tarcza: blokada reklam i śledzenia, wyjątek dla strony, listy filtrów.
class ShieldSheet extends StatefulWidget {
  final LunaState s;
  final String host;
  final int blockedHere;
  final VoidCallback onChanged;
  const ShieldSheet({super.key, required this.s, required this.host, required this.blockedHere, required this.onChanged});

  @override
  State<ShieldSheet> createState() => _ShieldSheetState();
}

class _ShieldSheetState extends State<ShieldSheet> {
  @override
  Widget build(BuildContext context) {
    final s = widget.s, ab = AdBlock.instance;
    final base = hostOf('https://${widget.host}');
    final allowed = widget.host.isNotEmpty && s.allowedHere(widget.host);
    return ListView(padding: const EdgeInsets.fromLTRB(16, 0, 16, 24), children: [
      Row(children: [
        Icon(s.adblock && !allowed ? Icons.shield : Icons.shield_outlined, size: 30, color: C.text),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(s.adblock ? (allowed ? 'Blokada wyłączona na tej stronie' : 'Blokada reklam i śledzenia działa') : 'Blokada wyłączona',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
            if (widget.host.isNotEmpty) Text(widget.host, style: const TextStyle(color: C.muted, fontSize: 12.5)),
          ]),
        ),
      ]),
      const SizedBox(height: 14),
      if (widget.blockedHere > 0 || s.blockedTotal > 0)
        LunaCard(
          child: Row(children: [
            Expanded(child: _stat('${widget.blockedHere}', 'na tej stronie')),
            Expanded(child: _stat('${s.blockedTotal}', 'łącznie')),
          ]),
        ),
      const SizedBox(height: 10),
      SwitchListTile(
        contentPadding: EdgeInsets.zero,
        title: const Text('Blokuj reklamy i śledzenie'),
        value: s.adblock,
        onChanged: (v) {
          s.adblock = v;
          s.changed();
          widget.onChanged();
          setState(() {});
        },
      ),
      if (widget.host.isNotEmpty)
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: Text('Blokuj na $base'),
          subtitle: const Text('Wyłącz, jeśli strona przez blokadę nie działa', style: TextStyle(color: C.muted, fontSize: 12.5)),
          value: !allowed,
          onChanged: s.adblock
              ? (v) {
                  if (v) {
                    s.allow.removeWhere((d) => widget.host == d || widget.host.endsWith('.$d'));
                  } else {
                    s.allow.add(base);
                  }
                  s.changed();
                  widget.onChanged();
                  setState(() {});
                }
              : null,
        ),
      const SizedBox(height: 8),
      const SectionLabel('Listy filtrów'),
      for (final l in filterLists) ListTile(contentPadding: EdgeInsets.zero, dense: true, title: Text(l.name), subtitle: Text(Uri.parse(l.url).host, style: const TextStyle(color: C.muted))),
      Text(
        ab.ready
            ? '${ab.domains} zablokowanych domen · aktualizacja ${ab.updated!.day}.${two(ab.updated!.month)}.${ab.updated!.year}'
            : (ab.busy ? 'Pobieranie list…' : (ab.error ?? 'Listy nie zostały jeszcze pobrane.')),
        style: const TextStyle(color: C.muted, fontSize: 12.5),
      ),
      const SizedBox(height: 10),
      Align(
        alignment: Alignment.centerLeft,
        child: OutlinedButton.icon(
          onPressed: ab.busy
              ? null
              : () async {
                  setState(() {});
                  final ok = await ab.update();
                  widget.onChanged();
                  if (mounted) {
                    setState(() {});
                    toast(context, ok ? 'Listy zaktualizowane' : (ab.error ?? 'Nie udało się'));
                  }
                },
          icon: const Icon(Icons.refresh, size: 18),
          label: const Text('Aktualizuj listy'),
          style: OutlinedButton.styleFrom(foregroundColor: C.text, side: const BorderSide(color: C.border2)),
        ),
      ),
      const SizedBox(height: 14),
      const Text('Reklamy na YouTube usuwa osobny skrypt Luny. Na iPhonie blokadą zarządza system (reguły WebKit), więc licznik pokazuje tylko Android.',
          style: TextStyle(color: Color(0xFF7A7A7A), fontSize: 12, height: 1.5)),
    ]);
  }

  Widget _stat(String n, String l) => Column(children: [
        Text(n, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w300)),
        Text(l, style: const TextStyle(color: C.muted, fontSize: 12)),
      ]);
}

class SettingsScreen extends StatelessWidget {
  final LunaState s;
  final ValueChanged<String> onOpen;
  final VoidCallback onGuide;
  final VoidCallback onBlockerChanged;
  const SettingsScreen({super.key, required this.s, required this.onOpen, required this.onGuide, required this.onBlockerChanged});

  @override
  Widget build(BuildContext context) => _Page(
        title: 'Ustawienia',
        child: AnimatedBuilder(
          animation: s,
          builder: (ctx, _) => ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 32), children: [
            const SectionLabel('Wyszukiwarka'),
            RadioGroup<String>(
              groupValue: s.engine,
              onChanged: (v) {
                s.engine = v!;
                s.changed();
              },
              child: Column(children: [
                for (final e in engines.keys) RadioListTile<String>(contentPadding: EdgeInsets.zero, dense: true, value: e, title: Text(e)),
              ]),
            ),
            const SizedBox(height: 8),
            const SectionLabel('Funkcje'),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Podpowiedzi z sieci'),
              subtitle: const Text('Wpisywany tekst trafia do wyszukiwarki po propozycje. Wyłącz dla pełnej prywatności.',
                  style: TextStyle(color: C.muted, fontSize: 12.5)),
              value: s.suggestNet,
              onChanged: (v) {
                s.suggestNet = v;
                s.changed();
              },
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Pogoda na ekranie głównym'),
              subtitle: Text('Open-Meteo · ${s.city['name']}', style: const TextStyle(color: C.muted, fontSize: 12.5)),
              value: s.weatherOn,
              onChanged: (v) {
                s.weatherOn = v;
                s.changed();
                if (v) Weather.instance.refresh(s, force: true);
              },
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Tarcza – blokada reklam'),
              subtitle: Text(s.adblock ? 'Włączona' : 'Wyłączona', style: const TextStyle(color: C.muted, fontSize: 12.5)),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => showLunaSheet(context, (c) => ShieldSheet(s: s, host: '', blockedHere: 0, onChanged: onBlockerChanged)),
            ),
            ListTile(contentPadding: EdgeInsets.zero, title: const Text('Przewodnik po Lunie'), trailing: const Icon(Icons.chevron_right), onTap: () {
              Navigator.pop(context);
              onGuide();
            }),
            const SizedBox(height: 8),
            const SectionLabel('Przestrzenie'),
            for (final sp in s.spaces)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(sp),
                trailing: sp == 'Główna'
                    ? null
                    : IconButton(
                        tooltip: 'Usuń przestrzeń',
                        icon: const Icon(Icons.delete_outline, size: 20),
                        onPressed: () {
                          for (final t in s.tabs.where((t) => t.space == sp)) {
                            t.space = 'Główna';
                          }
                          s.spaces.remove(sp);
                          if (s.space == sp) s.switchSpace('Główna');
                          s.changed();
                        }),
              ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.add),
              title: const Text('Nowa przestrzeń'),
              onTap: () async {
                final n = await askText(context, 'Nazwa przestrzeni', 'np. Szkoła, Praca');
                if (n != null) s.addSpace(n);
              },
            ),
            const SizedBox(height: 8),
            const SectionLabel('Dane na tym telefonie'),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Wyczyść historię'),
              onTap: () {
                s.history.clear();
                s.changed();
                toast(context, 'Historia wyczyszczona');
              },
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Usuń ciasteczka i dane stron'),
              subtitle: const Text('Wylogujesz się ze stron', style: TextStyle(color: C.muted, fontSize: 12.5)),
              onTap: () async {
                await CookieManager.instance().deleteAllCookies();
                try {
                  await WebStorageManager.instance().deleteAllData();
                } catch (_) {
                  try {
                    await WebStorageManager.instance().removeDataModifiedSince(
                        dataTypes: WebsiteDataType.ALL, date: DateTime.fromMillisecondsSinceEpoch(0));
                  } catch (_) {}
                }
                if (context.mounted) toast(context, 'Usunięto ciasteczka i dane stron');
              },
            ),
            const SizedBox(height: 8),
            const SectionLabel('O Lunie'),
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 6),
              child: Text(
                  'Luna – prywatna przeglądarka. Bez kont, bez telemetrii i bez serwerów Luny: zakładki, historia i ustawienia zostają na tym telefonie. '
                  'Wolne oprogramowanie na licencji GNU GPL v3, bez gwarancji. Projekt jednoosobowy.',
                  style: TextStyle(color: C.muted, height: 1.5, fontSize: 13)),
            ),
            if (Updater.instance.supported)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Aktualizacje'),
                subtitle: const Text('Wersja $kVersion – sprawdzanie, pobieranie i instalacja nowej wersji',
                    style: TextStyle(color: C.muted, fontSize: 12.5)),
                trailing: const Icon(Icons.system_update_outlined, size: 20),
                onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const UpdatesScreen())),
              ),
            for (final l in [
              ('Strona Luny', 'https://z4k0lzakol.github.io/Luna/'),
              ('Prywatność', 'https://z4k0lzakol.github.io/Luna/privacy.html'),
              ('Kod źródłowy', 'https://github.com/z4k0lzakol/Luna'),
            ])
              ListTile(contentPadding: EdgeInsets.zero, title: Text(l.$1), trailing: const Icon(Icons.open_in_new, size: 18), onTap: () {
                Navigator.pop(context);
                onOpen(l.$2);
              }),
          ]),
        ),
      );
}

class ReaderItem {
  final bool heading;
  final String text;
  ReaderItem(this.heading, this.text);
}

class ReaderScreen extends StatefulWidget {
  final String title, site;
  final List<ReaderItem> items;
  const ReaderScreen({super.key, required this.title, required this.site, required this.items});

  @override
  State<ReaderScreen> createState() => _ReaderScreenState();
}

class _ReaderScreenState extends State<ReaderScreen> {
  double _size = 18;

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: const Color(0xFF101010),
        body: SafeArea(
          child: Column(children: [
            Row(children: [
              IconButton(tooltip: 'Zamknij', onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close, color: C.text2)),
              Expanded(child: Text(widget.site, style: const TextStyle(color: C.muted, fontSize: 13))),
              IconButton(tooltip: 'Mniejsza czcionka', onPressed: () => setState(() => _size = (_size - 1).clamp(14, 28)), icon: const Icon(Icons.text_decrease, color: C.text2)),
              IconButton(tooltip: 'Większa czcionka', onPressed: () => setState(() => _size = (_size + 1).clamp(14, 28)), icon: const Icon(Icons.text_increase, color: C.text2)),
            ]),
            Expanded(
              child: ListView(padding: const EdgeInsets.fromLTRB(24, 12, 24, 48), children: [
                Text(widget.title, style: TextStyle(fontSize: _size + 10, fontWeight: FontWeight.w600, height: 1.25)),
                const SizedBox(height: 20),
                for (final it in widget.items)
                  Padding(
                    padding: EdgeInsets.only(bottom: it.heading ? 8 : 16, top: it.heading ? 12 : 0),
                    child: Text(it.text,
                        style: TextStyle(
                            fontSize: it.heading ? _size + 3 : _size,
                            fontWeight: it.heading ? FontWeight.w600 : FontWeight.w400,
                            height: 1.6,
                            color: const Color(0xFFDDDDDD))),
                  ),
              ]),
            ),
          ]),
        ),
      );
}
