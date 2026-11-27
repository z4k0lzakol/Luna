// Menu Luny w arkuszu od dołu – te same kafelki i działy co na komputerze.
import 'package:flutter/material.dart';

import 'common.dart';

class MenuItemDef {
  final String id;
  final IconData icon;
  final String label;
  final List<String> keywords;
  const MenuItemDef(this.id, this.icon, this.label, [this.keywords = const []]);
}

const _top = [
  MenuItemDef('new', Icons.add, 'Nowa karta'),
  MenuItemDef('private', Icons.visibility_off_outlined, 'Prywatna', ['incognito']),
  MenuItemDef('history', Icons.history, 'Historia'),
  MenuItemDef('settings', Icons.settings_outlined, 'Ustawienia', ['wyszukiwarka', 'dane']),
];

const _sections = <(String, List<MenuItemDef>)>[
  ('Karty i przestrzenie', [
    MenuItemDef('tabs', Icons.search, 'Szukaj kart', ['karty']),
    MenuItemDef('split', Icons.horizontal_split_outlined, 'Dwie strony', ['podział', 'ekran']),
    MenuItemDef('space', Icons.layers_outlined, 'Przestrzeń'),
    MenuItemDef('later', Icons.schedule, 'Na później', ['odłóż']),
  ]),
  ('Twoje rzeczy', [
    MenuItemDef('bookmarks', Icons.bookmark_border, 'Zakładki'),
    MenuItemDef('addBookmark', Icons.bookmark_add_outlined, 'Dodaj zakładkę'),
    MenuItemDef('notes', Icons.sticky_note_2_outlined, 'Notatki'),
    MenuItemDef('widgets', Icons.grid_view_outlined, 'Widgety', ['pogoda', 'zadania']),
    MenuItemDef('devices', Icons.devices_outlined, 'Urządzenia', ['połączone', 'komputer', 'telefon', 'synchronizacja', 'parowanie']),
    MenuItemDef('sendFiles', Icons.upload_file, 'Wyślij pliki', ['localsend', 'zdjęcia', 'komputer']),
    MenuItemDef('remote', Icons.settings_remote_outlined, 'Pilot', ['komputer', 'film', 'sterowanie']),
  ]),
  ('Ta strona', [
    MenuItemDef('reader', Icons.chrome_reader_mode_outlined, 'Czytanie'),
    MenuItemDef('translate', Icons.translate, 'Tłumacz'),
    MenuItemDef('dark', Icons.dark_mode_outlined, 'Ciemny tryb'),
    MenuItemDef('copy', Icons.link, 'Kopiuj adres', ['udostępnij']),
    MenuItemDef('sendTab', Icons.send_to_mobile_outlined, 'Na urządzenie', ['wyślij', 'komputer', 'udostępnij']),
  ]),
  ('Dostosuj Lunę', [
    MenuItemDef('focus', Icons.center_focus_strong_outlined, 'Skupienie', ['tryb skupienia']),
    MenuItemDef('shield', Icons.shield_outlined, 'Tarcza', ['reklamy', 'blokada']),
    MenuItemDef('guide', Icons.help_outline, 'Przewodnik', ['pomoc']),
    MenuItemDef('panel', Icons.auto_awesome_outlined, 'Asystent AI', ['komunikatory', 'czat']),
  ]),
];

class MenuSheet extends StatefulWidget {
  final bool onPage;
  final bool dark;
  final bool focus;
  final int zoom;
  final ValueChanged<int> onZoom;
  const MenuSheet({super.key, required this.onPage, required this.dark, required this.focus, required this.zoom, required this.onZoom});

  @override
  State<MenuSheet> createState() => _MenuSheetState();
}

class _MenuSheetState extends State<MenuSheet> {
  String _q = '';
  late int _zoom = widget.zoom;

  bool _active(String id) => (id == 'dark' && widget.dark) || (id == 'focus' && widget.focus);

  Widget _grid(List<MenuItemDef> items) => GridView.count(
        crossAxisCount: 4,
        mainAxisSpacing: 8,
        crossAxisSpacing: 8,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        childAspectRatio: 1.08,
        children: [for (final m in items) MenuTile(m.icon, m.label, () => Navigator.pop(context, m.id), active: _active(m.id))],
      );

  @override
  Widget build(BuildContext context) {
    final all = [..._top, for (final s in _sections) ...s.$2];
    final q = _q.trim().toLowerCase();
    final found = q.isEmpty
        ? <MenuItemDef>[]
        : all.where((m) => m.label.toLowerCase().contains(q) || m.keywords.any((k) => k.contains(q))).toList();
    return ListView(padding: const EdgeInsets.fromLTRB(14, 0, 14, 24), children: [
      TextField(
        onChanged: (v) => setState(() => _q = v),
        decoration: InputDecoration(
          isDense: true,
          hintText: 'Szukaj poleceń i ustawień',
          hintStyle: const TextStyle(color: Color(0xFF8F8F8F)),
          prefixIcon: const Icon(Icons.search, size: 18, color: Color(0xFF8F8F8F)),
          filled: true,
          fillColor: const Color(0xFF0C0C0C),
          contentPadding: const EdgeInsets.symmetric(vertical: 13),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: C.border2)),
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: C.border2)),
        ),
      ),
      const SizedBox(height: 12),
      if (q.isNotEmpty) ...[
        if (found.isEmpty) const Padding(padding: EdgeInsets.all(16), child: Text('Nic nie znaleziono', style: TextStyle(color: C.muted))),
        _grid(found),
      ] else ...[
        Reveal(0, stepMs: 35, child: _grid(_top)),
        for (final (i, s) in _sections.indexed)
          Reveal(i + 1,
              stepMs: 35,
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const SizedBox(height: 10),
                SectionLabel(s.$1),
                const SizedBox(height: 6),
                _grid(s.$2),
              ])),
        if (widget.onPage) ...[
          const SizedBox(height: 10),
          Container(
            height: 48,
            padding: const EdgeInsets.only(left: 14, right: 4),
            decoration: BoxDecoration(color: C.card2, borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0xFF262626))),
            child: Row(children: [
              const Icon(Icons.zoom_in, size: 19, color: Color(0xFFE6E6E6)),
              const SizedBox(width: 10),
              const Text('Powiększ', style: TextStyle(fontSize: 14)),
              const Spacer(),
              IconButton(
                  tooltip: 'Pomniejsz',
                  onPressed: () => setState(() {
                        _zoom = (_zoom - 10).clamp(50, 250);
                        widget.onZoom(_zoom);
                      }),
                  icon: const Icon(Icons.remove, size: 20)),
              SizedBox(width: 48, child: Text('$_zoom%', textAlign: TextAlign.center, style: const TextStyle(fontSize: 13, color: C.text2))),
              IconButton(
                  tooltip: 'Powiększ',
                  onPressed: () => setState(() {
                        _zoom = (_zoom + 10).clamp(50, 250);
                        widget.onZoom(_zoom);
                      }),
                  icon: const Icon(Icons.add, size: 20)),
            ]),
          ),
        ],
      ],
    ]);
  }
}
