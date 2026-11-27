// Ekrany połączonych urządzeń: ustawienia i lista, skanowanie kodu QR z komputera, pilot, karty z innych urządzeń.
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../link/link.dart';
import '../link/manager.dart';
import 'common.dart';

String deviceLabel(String type) => switch (type) { 'desktop' => 'komputer', 'tablet' => 'tablet', _ => 'telefon' };
IconData deviceIcon(String type) => type == 'desktop' ? Icons.computer : Icons.smartphone;

class _Page extends StatelessWidget {
  final String title;
  final Widget child;
  const _Page({required this.title, required this.child});

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
              ]),
            ),
            Expanded(child: child),
          ]),
        ),
      );
}

const _muted = TextStyle(color: C.muted, fontSize: 12.5, height: 1.4);

class DevicesScreen extends StatelessWidget {
  final LinkManager m;
  final ValueChanged<String> onOpen;
  const DevicesScreen({super.key, required this.m, required this.onOpen});

  @override
  Widget build(BuildContext context) => _Page(
        title: 'Połączone urządzenia',
        child: AnimatedBuilder(
          animation: m,
          builder: (ctx, _) => ListView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 32), children: [
            const Padding(
              padding: EdgeInsets.only(bottom: 8),
              child: Text(
                  'Luna na komputerze i innych telefonach w tej samej sieci Wi-Fi: wysyłanie stron i plików, wspólne zakładki, '
                  'karty, schowek i pilot. Połączenie jest bezpośrednie i szyfrowane – bez serwerów Luny.',
                  style: _muted),
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Połączenie urządzeń'),
              subtitle: const Text('Wyłączone: Luna nie ogłasza się w sieci i nie przyjmuje połączeń.', style: _muted),
              value: m.on,
              onChanged: (v) => m.setOn(v),
            ),
            if (m.error != null) Text(m.error!, style: const TextStyle(color: Colors.redAccent)),
            if (m.on) ...[
              const SizedBox(height: 6),
              Row(children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: () => scanAndPair(context, m),
                    icon: const Icon(Icons.qr_code_scanner),
                    label: const Text('Skanuj kod z komputera'),
                  ),
                ),
              ]),
              const SizedBox(height: 4),
              Row(children: [
                TextButton(onPressed: () => _showCode(context, m), child: const Text('Pokaż kod parowania')),
                const Spacer(),
                TextButton(onPressed: () => _rename(context, m), child: Text('Nazwa: ${m.link?.name ?? ''}', overflow: TextOverflow.ellipsis)),
              ]),
              if (m.progress != null) ...[
                LinearProgressIndicator(value: m.progress!.$2 > 0 ? m.progress!.$1 / m.progress!.$2 : null),
                Text('Wysyłanie: ${m.progress!.$3}', style: _muted),
              ],
              const SizedBox(height: 10),
              const SectionLabel('Sparowane'),
              if (m.peers.isEmpty)
                const Padding(
                    padding: EdgeInsets.symmetric(vertical: 8),
                    child: Text('Brak. Na komputerze otwórz Ustawienia → Połączone urządzenia → Sparuj urządzenie i zeskanuj kod.',
                        style: _muted)),
              for (final d in m.peers.values) _PeerCard(m: m, d: d, onOpen: onOpen),
              const SizedBox(height: 10),
              const SectionLabel('W tej sieci'),
              if (m.nearbyUnpaired.isEmpty)
                const Padding(
                    padding: EdgeInsets.symmetric(vertical: 8),
                    child: Text('Nie widać innych urządzeń z Luną (na nich też musi być włączone połączenie).', style: _muted)),
              for (final d in m.nearbyUnpaired)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(deviceIcon(d.type), color: C.text2),
                  title: Text(d.name),
                  subtitle: Text('${deviceLabel(d.type)} z Luną · niesparowane', style: _muted),
                  trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                    IconButton(tooltip: 'Wyślij pliki', icon: const Icon(Icons.upload_file), onPressed: () => pickAndSend(context, m, d)),
                    TextButton(onPressed: () => _pairByCode(context, m, d), child: const Text('Połącz')),
                  ]),
                ),
              const SizedBox(height: 10),
              const SectionLabel('Co mogą połączone urządzenia'),
              for (final f in phoneFeats)
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(f.$2),
                  subtitle: Text(f.$3, style: _muted),
                  value: m.feat(f.$1),
                  onChanged: (v) => m.setFeat(f.$1, v),
                ),
            ],
          ]),
        ),
      );
}

class _PeerCard extends StatelessWidget {
  final LinkManager m;
  final Device d;
  final ValueChanged<String> onOpen;
  const _PeerCard({required this.m, required this.d, required this.onOpen});

  @override
  Widget build(BuildContext context) {
    final near = m.reachable(d.id);
    final last = m.lastSync(d.id);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: LunaCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(deviceIcon(d.type), color: near ? C.cream : C.muted),
            const SizedBox(width: 10),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(d.name, style: const TextStyle(fontSize: 15.5)),
                Text(
                    '${deviceLabel(d.type)} · ${near ? 'w tej sieci' : 'poza siecią'}'
                    '${last != null ? ' · synchronizacja ${two(last.hour)}:${two(last.minute)}' : ''}',
                    style: _muted),
              ]),
            ),
            PopupMenuButton<String>(
              color: C.sheet,
              onSelected: (v) async {
                if (v == 'forget' &&
                    await _confirm(context, 'Usunąć „${d.name}”?', 'Ponowne połączenie wymaga parowania.') == true) {
                  await m.link?.forget(d.id);
                }
              },
              itemBuilder: (_) => [const PopupMenuItem(value: 'forget', child: Text('Usuń urządzenie'))],
            ),
          ]),
          const SizedBox(height: 8),
          Wrap(spacing: 6, runSpacing: 6, children: [
            _Chip(Icons.upload_file, 'Wyślij pliki', () => pickAndSend(context, m, d.id)),
            _Chip(Icons.tab, 'Karty', () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => RemoteTabsScreen(m: m, d: d, onOpen: onOpen)))),
            if (d.type == 'desktop')
              _Chip(Icons.settings_remote_outlined, 'Pilot',
                  () => Navigator.push(context, MaterialPageRoute(builder: (_) => RemoteScreen(m: m, d: d)))),
            if (m.feat('clip')) _Chip(Icons.content_paste_go, 'Wyślij schowek', () => m.sendClipboard(d.id)),
          ]),
        ]),
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _Chip(this.icon, this.label, this.onTap);

  @override
  Widget build(BuildContext context) => ActionChip(
        avatar: Icon(icon, size: 18, color: C.text2),
        label: Text(label),
        backgroundColor: C.card2,
        side: const BorderSide(color: C.border2),
        onPressed: onTap,
      );
}

Future<bool?> _confirm(BuildContext context, String title, String text) => showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        backgroundColor: C.sheet,
        title: Text(title),
        content: Text(text),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Anuluj')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Tak')),
        ],
      ),
    );

Future<void> _rename(BuildContext context, LinkManager m) async {
  final ctl = TextEditingController(text: m.link?.name ?? '');
  final v = await showDialog<String>(
    context: context,
    builder: (c) => AlertDialog(
      backgroundColor: C.sheet,
      title: const Text('Nazwa tego telefonu'),
      content: TextField(controller: ctl, autofocus: true, maxLength: 40),
      actions: [
        TextButton(onPressed: () => Navigator.pop(c), child: const Text('Anuluj')),
        FilledButton(onPressed: () => Navigator.pop(c, ctl.text), child: const Text('Zapisz')),
      ],
    ),
  );
  if (v != null) {
    m.link?.setName(v);
    m.refresh();
  }
}

/// Kod do sparowania z innym telefonem albo komputerem (wpisywany po wybraniu tego telefonu z listy „W tej sieci”).
Future<void> _showCode(BuildContext context, LinkManager m) async {
  final code = m.link!.newCode();
  await showDialog<void>(
    context: context,
    builder: (c) => AlertDialog(
      backgroundColor: C.sheet,
      title: const Text('Kod parowania'),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        Text('${code.substring(0, 3)} ${code.substring(3)}', style: const TextStyle(fontSize: 38, letterSpacing: 6, color: C.cream)),
        const SizedBox(height: 8),
        Text('Na drugim urządzeniu wybierz „${m.link!.name}” z listy „W tej sieci” i wpisz ten kod. Ważny 5 minut.',
            style: _muted, textAlign: TextAlign.center),
      ]),
      actions: [TextButton(onPressed: () => Navigator.pop(c), child: const Text('Gotowe'))],
    ),
  );
}

Future<void> _pairByCode(BuildContext context, LinkManager m, Device d) async {
  final ctl = TextEditingController();
  final code = await showDialog<String>(
    context: context,
    builder: (c) => AlertDialog(
      backgroundColor: C.sheet,
      title: Text('Połącz z „${d.name}”'),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        Text(d.type == 'desktop'
            ? 'Na komputerze otwórz Ustawienia → Połączone urządzenia → Sparuj urządzenie i wpisz pokazany kod (albo zeskanuj kod QR).'
            : 'Na tamtym telefonie otwórz Połączone urządzenia → Pokaż kod parowania i wpisz go tutaj.', style: _muted),
        TextField(controller: ctl, autofocus: true, keyboardType: TextInputType.number, maxLength: 6),
      ]),
      actions: [
        TextButton(onPressed: () => Navigator.pop(c), child: const Text('Anuluj')),
        FilledButton(onPressed: () => Navigator.pop(c, ctl.text.replaceAll(RegExp(r'\D'), '')), child: const Text('Połącz')),
      ],
    ),
  );
  if (code == null || code.length != 6 || d.addr == null) return;
  try {
    await m.link!.pairWith(d.addr!, d.port, d.fp, code);
  } catch (e) {
    if (context.mounted) toast(context, 'Nie udało się: $e');
  }
}

Future<void> scanAndPair(BuildContext context, LinkManager m) async {
  if (!m.on) await m.setOn(true);
  if (!context.mounted) return;
  final uri = await Navigator.push<String>(context, MaterialPageRoute(builder: (_) => const ScanScreen()));
  if (uri == null || !context.mounted) return;
  toast(context, 'Łączenie…');
  try {
    final p = await m.link!.pairFromUri(uri);
    if (context.mounted) toast(context, 'Sparowano: ${p.name}');
  } catch (e) {
    if (context.mounted) toast(context, '$e');
  }
}

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  bool _done = false;

  @override
  Widget build(BuildContext context) => _Page(
        title: 'Skanuj kod z komputera',
        child: Column(children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: Text('Na komputerze: Ustawienia → Połączone urządzenia → Sparuj urządzenie. Telefon i komputer muszą być w tej samej sieci Wi-Fi.',
                style: _muted),
          ),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: MobileScanner(
                onDetect: (cap) {
                  if (_done) return;
                  for (final b in cap.barcodes) {
                    final v = b.rawValue ?? '';
                    if (v.startsWith('luna://pair')) {
                      _done = true;
                      Navigator.pop(context, v);
                      return;
                    }
                  }
                },
              ),
            ),
          ),
          const SizedBox(height: 16),
        ]),
      );
}

/// Wybór urządzenia: sparowane (i opcjonalnie widoczne w sieci). Zwraca id sparowanego albo Device niesparowanego.
Future<Object?> pickDevice(BuildContext context, LinkManager m, String title, {bool nearby = false, bool desktopsOnly = false}) {
  final list = <(String, String, Object, bool)>[
    for (final d in m.peers.values)
      if (!desktopsOnly || d.type == 'desktop') (d.name, '${deviceLabel(d.type)}${m.reachable(d.id) ? '' : ' · poza siecią'}', d.id, m.reachable(d.id)),
    if (nearby)
      for (final d in m.nearbyUnpaired) (d.name, '${deviceLabel(d.type)} · niesparowane', d, true),
  ];
  if (list.isEmpty) {
    toast(context, m.on ? 'Brak urządzeń – sparuj komputer w Połączonych urządzeniach' : 'Włącz Połączone urządzenia w menu');
    return Future.value(null);
  }
  return showLunaSheet<Object>(
    context,
    heightFactor: 0.5,
    (c) => ListView(padding: const EdgeInsets.all(16), children: [
      SectionLabel(title),
      for (final e in list)
        ListTile(
          leading: Icon(Icons.devices, color: e.$4 ? C.cream : C.muted),
          title: Text(e.$1),
          subtitle: Text(e.$2, style: _muted),
          onTap: () => Navigator.pop(c, e.$3),
        ),
    ]),
  );
}

Future<void> pickAndSend(BuildContext context, LinkManager m, Object target, [List<String>? paths]) async {
  final files = paths ?? await m.pickFiles();
  if (files.isEmpty) return;
  await m.sendFiles(target, files);
}

class RemoteTabsScreen extends StatefulWidget {
  final LinkManager m;
  final Device d;
  final ValueChanged<String> onOpen;
  const RemoteTabsScreen({super.key, required this.m, required this.d, required this.onOpen});

  @override
  State<RemoteTabsScreen> createState() => _RemoteTabsScreenState();
}

class _RemoteTabsScreenState extends State<RemoteTabsScreen> {
  List<Map<String, String>>? _tabs;

  @override
  void initState() {
    super.initState();
    widget.m.tabsOf(widget.d.id).then((t) {
      if (mounted) setState(() => _tabs = t);
    });
  }

  @override
  Widget build(BuildContext context) => _Page(
        title: 'Karty: ${widget.d.name}',
        child: _tabs == null
            ? const Center(child: CircularProgressIndicator())
            : _tabs!.isEmpty
                ? const Center(child: Text('Brak otwartych kart (albo urządzenie jest poza siecią).', style: _muted))
                : ListView(padding: const EdgeInsets.all(12), children: [
                    for (final t in _tabs!)
                      ListTile(
                        leading: SiteLetter(Uri.tryParse(t['url']!)?.host ?? ''),
                        title: Text(t['title']!.isEmpty ? t['url']! : t['title']!, maxLines: 1, overflow: TextOverflow.ellipsis),
                        subtitle: Text(Uri.tryParse(t['url']!)?.host ?? '', style: _muted),
                        onTap: () {
                          Navigator.pop(context);
                          widget.onOpen(t['url']!);
                        },
                      ),
                  ]),
      );
}

/// Pilot: filmy i muzyka w aktywnej karcie Luny na komputerze.
class RemoteScreen extends StatefulWidget {
  final LinkManager m;
  final Device d;
  const RemoteScreen({super.key, required this.m, required this.d});

  @override
  State<RemoteScreen> createState() => _RemoteScreenState();
}

class _RemoteScreenState extends State<RemoteScreen> {
  double _vol = 0.8;

  void _cmd(String c, [Object? v]) => widget.m.remote(widget.d.id, c, v);

  Widget _btn(IconData i, String label, VoidCallback f, {double size = 34}) => Column(mainAxisSize: MainAxisSize.min, children: [
        IconButton.filledTonal(iconSize: size, padding: const EdgeInsets.all(18), onPressed: f, icon: Icon(i)),
        const SizedBox(height: 4),
        Text(label, style: _muted),
      ]);

  @override
  Widget build(BuildContext context) => _Page(
        title: 'Pilot: ${widget.d.name}',
        child: ListView(padding: const EdgeInsets.all(24), children: [
          const Text('Steruje filmem albo muzyką w aktywnej karcie Luny na komputerze.', style: _muted, textAlign: TextAlign.center),
          const SizedBox(height: 28),
          Center(child: _btn(Icons.play_arrow_rounded, 'Odtwórz / pauza', () => _cmd('playpause'), size: 56)),
          const SizedBox(height: 24),
          Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
            _btn(Icons.replay_30, '−30 s', () => _cmd('seek', -30)),
            _btn(Icons.replay_10, '−10 s', () => _cmd('seek', -10)),
            _btn(Icons.forward_10, '+10 s', () => _cmd('seek', 10)),
            _btn(Icons.forward_30, '+30 s', () => _cmd('seek', 30)),
          ]),
          const SizedBox(height: 28),
          Row(children: [
            IconButton(onPressed: () => _cmd('mute'), icon: const Icon(Icons.volume_off_outlined)),
            Expanded(
              child: Slider(
                value: _vol,
                onChanged: (v) => setState(() => _vol = v),
                onChangeEnd: (v) => _cmd('volume', double.parse(v.toStringAsFixed(2))),
              ),
            ),
            const Icon(Icons.volume_up_outlined),
          ]),
          const SizedBox(height: 24),
          Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
            _btn(Icons.chevron_left, 'Poprzednia karta', () => _cmd('prev_tab')),
            _btn(Icons.fullscreen, 'Pełny ekran', () => _cmd('fullscreen')),
            _btn(Icons.chevron_right, 'Następna karta', () => _cmd('next_tab')),
          ]),
        ]),
      );
}
