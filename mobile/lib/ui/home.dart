// Ekran główny: gwiazdy, cienki zegar, wyszukiwarka, kafelki i widgety.
import 'dart:async';

import 'package:flutter/material.dart';

import '../state.dart';
import 'common.dart';
import 'widgets.dart';

class HomeView extends StatefulWidget {
  final LunaState s;
  final ValueChanged<String> onOpen;
  final VoidCallback onSpaces;
  final VoidCallback onLater;
  final VoidCallback onSearch;
  const HomeView({super.key, required this.s, required this.onOpen, required this.onSpaces, required this.onLater, required this.onSearch});

  @override
  State<HomeView> createState() => _HomeViewState();
}

class _HomeViewState extends State<HomeView> {
  late Timer _t;
  DateTime _now = DateTime.now();

  @override
  void initState() {
    super.initState();
    _t = Timer.periodic(const Duration(seconds: 5), (_) {
      final n = DateTime.now();
      if (n.minute != _now.minute) setState(() => _now = n);
    });
    Weather.instance.refresh(widget.s);
  }

  @override
  void dispose() {
    _t.cancel();
    super.dispose();
  }

  Future<void> _addTile() async {
    final name = TextEditingController(), url = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: C.sheet,
        title: const Text('Dodaj kafelek'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: name, decoration: const InputDecoration(labelText: 'Nazwa')),
          TextField(controller: url, decoration: const InputDecoration(labelText: 'Adres strony'), keyboardType: TextInputType.url),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Anuluj')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Dodaj')),
        ],
      ),
    );
    if (ok == true && url.text.trim().isNotEmpty) {
      final u = widget.s.resolve(url.text);
      widget.s.tiles.add(Entry(u, name.text.trim().isEmpty ? hostOf(u) : name.text.trim()));
      widget.s.changed();
    }
  }

  void _tileMenu(Entry e) {
    showLunaSheet(context, heightFactor: 0.3, (ctx) => Column(children: [
          ListTile(title: Text(e.title), subtitle: Text(e.url, maxLines: 1, overflow: TextOverflow.ellipsis)),
          ListTile(
            leading: const Icon(Icons.delete_outline),
            title: const Text('Usuń kafelek'),
            onTap: () {
              widget.s.tiles.remove(e);
              widget.s.changed();
              Navigator.pop(ctx);
            },
          ),
        ]));
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (ctx, box) => _layout(box));
  }

  Widget _layout(BoxConstraints box) {
    final s = widget.s;
    // dwie kolumny tylko, gdy jest na nie miejsce (poziomo, cały ekran) – nie w połowie podzielonego ekranu
    final landscape = box.maxWidth > 720 && box.maxWidth > box.maxHeight;
    final clockSize = (box.maxWidth / 4.6).clamp(48.0, 84.0);
    final top = Padding(

            padding: const EdgeInsets.fromLTRB(20, 14, 12, 0),
            child: Row(children: [
              const Icon(Icons.nightlight_round, size: 20, color: C.cream),
              const SizedBox(width: 10),
              InkWell(
                onTap: widget.onSpaces,
                borderRadius: BorderRadius.circular(8),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
                  child: Text('Przestrzeń: ${s.space}', style: const TextStyle(fontSize: 13, color: Color(0xFF8F8F8F))),
                ),
              ),
              const Spacer(),
              IconButton(
                tooltip: 'Widgety',
                onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => WidgetsScreen(s))),
                icon: const Icon(Icons.grid_view_outlined, size: 20, color: Color(0xFFBDBDBD)),
              ),
            ]),
          );
    final clock = <Widget>[
          SizedBox(height: landscape ? 8 : 48),
          Center(
              child: Text('${two(_now.hour)}:${two(_now.minute)}',
                  style: TextStyle(fontSize: clockSize, fontWeight: FontWeight.w200, letterSpacing: -1.5, height: 1))),
          const SizedBox(height: 6),
          Center(
              child: Text('${weekdaysPl[_now.weekday - 1]}, ${_now.day} ${monthsPl[_now.month - 1]}',
                  style: const TextStyle(fontSize: 15, color: C.muted))),
          const SizedBox(height: 30),
          Padding(padding: const EdgeInsets.symmetric(horizontal: 20), child: _searchBox()),
          const SizedBox(height: 26),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Wrap(alignment: WrapAlignment.center, spacing: 10, runSpacing: 14, children: [
              for (final e in s.tiles) _tile(e.title.isEmpty ? '?' : e.title[0].toUpperCase(), e.title, () => widget.onOpen(e.url), () => _tileMenu(e)),
              _tile('+', 'Dodaj', _addTile, null),
            ]),
          ),
    ];
    final widgets = <Widget>[
          if (s.later.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 26, 16, 0),
              child: LunaCard(
                onTap: widget.onLater,
                child: Row(children: [
                  const Icon(Icons.schedule, size: 18, color: C.text2),
                  const SizedBox(width: 10),
                  Expanded(
                      child: Text('Na później: ${s.later.first.title}',
                          maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13.5, color: C.text2))),
                  if (s.later.length > 1) Text('+${s.later.length - 1}', style: const TextStyle(fontSize: 12, color: C.label)),
                ]),
              ),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 28, 16, 0),
            child: Column(children: [
              SectionLabel('Widgety',
                  trailing: GestureDetector(
                      onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => WidgetsScreen(s))),
                      child: const Text('Wszystkie', style: TextStyle(fontSize: 12, color: C.muted)))),
              const SizedBox(height: 8),
              IntrinsicHeight(
                child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  if (s.weatherOn) Expanded(child: WeatherSmall(s)),
                  if (s.weatherOn) const SizedBox(width: 10),
                  Expanded(child: StreakSmall(s)),
                ]),
              ),
              const SizedBox(height: 10),
              TasksCard(s, compact: true),
            ]),
          ),
    ];
    return StarField(
      child: SafeArea(
        bottom: false,
        child: landscape
            ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(child: ListView(padding: const EdgeInsets.only(bottom: 16), children: [top, ...clock])),
                SizedBox(width: 380, child: ListView(padding: const EdgeInsets.only(bottom: 16, right: 8), children: widgets)),
              ])
            : ListView(padding: const EdgeInsets.fromLTRB(0, 0, 0, 24), children: [top, ...clock, ...widgets]),
      ),
    );
  }

  Widget _searchBox() => Semantics(
        button: true,
        label: 'Szukaj lub wpisz adres',
        child: Material(
          color: C.card,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(26), side: const BorderSide(color: C.border2)),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: widget.onSearch,
            child: const SizedBox(
              height: 52,
              child: Row(children: [
                SizedBox(width: 16),
                Icon(Icons.search, size: 20, color: Color(0xFF8F8F8F)),
                SizedBox(width: 12),
                Text('Szukaj lub wpisz adres', style: TextStyle(fontSize: 16, color: Color(0xFF8F8F8F))),
              ]),
            ),
          ),
        ),
      );

  Widget _tile(String letter, String name, VoidCallback onTap, VoidCallback? onLong) => SizedBox(
        width: 66,
        child: InkWell(
          onTap: onTap,
          onLongPress: onLong,
          borderRadius: BorderRadius.circular(16),
          child: Column(children: [
            Container(
              width: 56,
              height: 56,
              alignment: Alignment.center,
              decoration: BoxDecoration(color: C.card2, borderRadius: BorderRadius.circular(16), border: Border.all(color: C.border2)),
              child: Text(letter, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
            ),
            const SizedBox(height: 7),
            Text(name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: C.text2)),
          ]),
        ),
      );
}
