// Ekran „Aktualizacje”: wersja Luny, stan sprawdzania i pobierania, opis zmian, instalacja i ustawienia.
import 'package:flutter/material.dart';

import '../update.dart';
import 'common.dart';

class UpdatesScreen extends StatelessWidget {
  const UpdatesScreen({super.key});

  static const _muted = TextStyle(color: C.muted, fontSize: 12.5, height: 1.45);

  String _when(DateTime? t) {
    if (t == null) return 'jeszcze nie';
    final d = DateTime.now().difference(t);
    if (d.inMinutes < 1) return 'przed chwilą';
    if (d.inHours < 1) return '${d.inMinutes} min temu';
    if (d.inDays < 1) return 'dziś o ${two(t.hour)}:${two(t.minute)}';
    return '${t.day}.${two(t.month)} o ${two(t.hour)}:${two(t.minute)}';
  }

  @override
  Widget build(BuildContext context) {
    final u = Updater.instance;
    return Scaffold(
      backgroundColor: C.bg,
      body: SafeArea(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 6, 8, 0),
            child: Row(children: [
              IconButton(tooltip: 'Wróć', onPressed: () => Navigator.pop(context), icon: const Icon(Icons.chevron_left, color: C.text2)),
              const Expanded(child: Text('Aktualizacje', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w500))),
            ]),
          ),
          Expanded(
            child: AnimatedBuilder(
              animation: u,
              builder: (ctx, _) {
                final r = u.latest;
                final (IconData icon, String title, String sub) = switch (u.state) {
                  UpdState.checking => (Icons.sync, 'Sprawdzanie…', 'Łączę się z wydaniami Luny na GitHubie.'),
                  UpdState.available => (Icons.new_releases_outlined, 'Dostępna Luna ${r?.version}', r != null && r.size > 0 ? 'Plik: ${(r.size / 1048576).toStringAsFixed(0)} MB' : ''),
                  UpdState.downloading => (Icons.downloading, 'Pobieranie Luny ${r?.version}', '${(u.progress * 100).round()}%'),
                  UpdState.ready => (Icons.check_circle_outline, 'Luna ${r?.version} jest gotowa', 'Kliknij „Zainstaluj” – Android poprosi o potwierdzenie. Karty i dane zostają.'),
                  UpdState.error => (Icons.error_outline, 'Coś poszło nie tak', u.error),
                  UpdState.upToDate => (Icons.verified_outlined, 'Masz najnowszą wersję', 'Luna $kVersion'),
                  UpdState.idle => (Icons.system_update_outlined, 'Luna $kVersion', 'Sprawdź, czy jest nowsza wersja.'),
                };
                return ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 32), children: [
                  LunaCard(
                    padding: const EdgeInsets.all(18),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [
                        Icon(icon, color: C.cream, size: 28),
                        const SizedBox(width: 12),
                        Expanded(child: Text(title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w500))),
                      ]),
                      if (sub.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Text(sub, style: _muted)),
                      if (u.state == UpdState.downloading)
                        Padding(
                          padding: const EdgeInsets.only(top: 12),
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(3),
                            child: LinearProgressIndicator(value: u.progress > 0 ? u.progress : null, minHeight: 6,
                                backgroundColor: C.border2, color: C.cream),
                          ),
                        ),
                      const SizedBox(height: 14),
                      Row(children: [
                        if (u.state == UpdState.ready || u.state == UpdState.available)
                          FilledButton.icon(
                            style: FilledButton.styleFrom(backgroundColor: C.cream, foregroundColor: Colors.black),
                            onPressed: u.state == UpdState.ready ? u.install : () => u.download(),
                            icon: Icon(u.state == UpdState.ready ? Icons.install_mobile : Icons.download),
                            label: Text(u.state == UpdState.ready ? 'Zainstaluj' : 'Pobierz'),
                          ),
                        if (u.state != UpdState.ready && u.state != UpdState.available) ...[
                          OutlinedButton.icon(
                            onPressed: u.state == UpdState.checking || u.state == UpdState.downloading ? null : () => u.check(interactive: true),
                            icon: const Icon(Icons.refresh),
                            label: const Text('Sprawdź teraz'),
                          ),
                        ],
                      ]),
                    ]),
                  ),
                  if (r != null && r.notes.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    SectionLabel('Co nowego w ${r.version}'),
                    Padding(padding: const EdgeInsets.fromLTRB(4, 6, 4, 0), child: Text(r.notes, style: const TextStyle(color: C.text2, height: 1.5, fontSize: 13.5))),
                  ],
                  const SizedBox(height: 16),
                  const SectionLabel('Ustawienia'),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Pobieraj nowe wersje samodzielnie'),
                    subtitle: const Text('Zaraz po otwarciu Luna sprawdza wydania i pobiera nową wersję w tle – instalację zawsze potwierdzasz ty.',
                        style: _muted),
                    value: u.auto,
                    onChanged: u.setAuto,
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Tylko przez Wi-Fi'),
                    subtitle: const Text('Przez sieć komórkową Luna tylko poinformuje o nowej wersji (plik ma ok. 75 MB).', style: _muted),
                    value: u.wifiOnly,
                    onChanged: u.auto ? u.setWifiOnly : null,
                  ),
                  const SizedBox(height: 8),
                  Text('Zainstalowana wersja: $kVersion · ostatnie sprawdzenie: ${_when(u.lastCheck)}', style: _muted),
                  const SizedBox(height: 4),
                  const Text('Aktualizacje pochodzą z oficjalnych wydań Luny na GitHubie. Android instaluje tylko plik podpisany tym samym '
                      'kluczem co zainstalowana Luna.', style: _muted),
                ]);
              },
            ),
          ),
        ]),
      ),
    );
  }
}
