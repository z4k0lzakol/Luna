// Panel aplikacji: asystent AI i komunikatory. Czaty i komunikatory działają na swoich stronach,
// na koncie użytkownika – Luna przekazuje im tylko to, o co poprosisz.
import 'dart:collection';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';

import '../state.dart';
import 'common.dart';

class AiProvider {
  final String name, url;
  final String? askUrl; // adres z gotowym pytaniem (gdy czat to obsługuje)
  const AiProvider(this.name, this.url, [this.askUrl]);
}

const aiProviders = [
  AiProvider('ChatGPT', 'https://chatgpt.com/', 'https://chatgpt.com/?q='),
  AiProvider('Claude', 'https://claude.ai/new', 'https://claude.ai/new?q='),
  AiProvider('Gemini', 'https://gemini.google.com/app'),
  AiProvider('DeepSeek', 'https://chat.deepseek.com/'),
];

const messengers = [
  ('WhatsApp', 'https://web.whatsapp.com/', Color(0xFF25B862)),
  ('Messenger', 'https://www.messenger.com/', Color(0xFF2F6FED)),
  ('Telegram', 'https://web.telegram.org/k/', Color(0xFF2AA3D8)),
  ('Instagram', 'https://www.instagram.com/direct/inbox/', Color(0xFFD6336C)),
  ('Discord', 'https://discord.com/app', Color(0xFF5865F2)),
];

class PanelSheet extends StatefulWidget {
  final LunaState s;
  final String pageTitle, pageUrl, selection;
  final String userAgent;
  final ValueChanged<String> onOpenTab;
  const PanelSheet(
      {super.key, required this.s, required this.pageTitle, required this.pageUrl, required this.selection, required this.userAgent, required this.onOpenTab});

  @override
  State<PanelSheet> createState() => _PanelSheetState();
}

class _PanelSheetState extends State<PanelSheet> {
  int _tab = 0;
  int _prov = 1;
  final _q = TextEditingController();

  @override
  void dispose() {
    _q.dispose();
    super.dispose();
  }

  void _ask(String prompt) {
    final p = aiProviders[_prov];
    String url;
    if (p.askUrl != null && prompt.isNotEmpty) {
      url = p.askUrl! + Uri.encodeQueryComponent(prompt);
    } else {
      if (prompt.isNotEmpty) {
        Clipboard.setData(ClipboardData(text: prompt));
        toast(context, 'Pytanie skopiowane – wklej je w czacie.');
      }
      url = p.url;
    }
    _openApp(p.name, url);
  }

  void _openApp(String name, String url) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => AppPage(name: name, url: url, userAgent: widget.userAgent, onOpenTab: widget.onOpenTab)));
  }

  @override
  Widget build(BuildContext context) {
    final hasPage = widget.pageUrl.isNotEmpty;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Segmented(labels: const ['Asystent AI', 'Komunikatory'], index: _tab, light: true, onChanged: (i) => setState(() => _tab = i)),
        const SizedBox(height: 14),
        if (_tab == 0)
          Expanded(
            child: ListView(children: [
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (var i = 0; i < aiProviders.length; i++)
                  ChoiceChip(
                    label: Text(aiProviders[i].name),
                    selected: i == _prov,
                    showCheckmark: false,
                    onSelected: (_) => setState(() => _prov = i),
                    selectedColor: C.text,
                    backgroundColor: C.card,
                    labelStyle: TextStyle(color: i == _prov ? const Color(0xFF111111) : C.text2, fontWeight: FontWeight.w500),
                    shape: StadiumBorder(side: BorderSide(color: i == _prov ? C.text : C.border2)),
                  ),
              ]),
              const SizedBox(height: 14),
              if (hasPage)
                LunaCard(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Text('TA STRONA', style: TextStyle(fontSize: 10.5, letterSpacing: 1.3, color: C.label, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 6),
                    Text(widget.pageTitle, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 14)),
                    const SizedBox(height: 10),
                    Wrap(spacing: 8, runSpacing: 8, children: [
                      _action('Streść stronę', () => _ask('Streść po polsku tę stronę: ${widget.pageUrl}')),
                      if (widget.selection.isNotEmpty)
                        _action('Wyjaśnij zaznaczenie', () => _ask('Wyjaśnij po polsku: "${widget.selection}" (ze strony ${widget.pageUrl})')),
                      _action('Przetłumacz', () => _ask('Przetłumacz na polski najważniejsze treści tej strony: ${widget.pageUrl}')),
                    ]),
                  ]),
                ),
              const SizedBox(height: 12),
              const Text('Rozmowa toczy się na stronie wybranego czatu, na Twoim koncie. Luna przekazuje mu tylko to, o co poprosisz.',
                  style: TextStyle(fontSize: 12.5, color: Color(0xFF8F8F8F), height: 1.5)),
              const SizedBox(height: 14),
              TextField(
                controller: _q,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: (v) => _ask(v.trim()),
                decoration: InputDecoration(
                  hintText: hasPage ? 'Zapytaj o tę stronę' : 'Zapytaj asystenta',
                  filled: true,
                  fillColor: C.card,
                  suffixIcon: IconButton(
                    tooltip: 'Wyślij',
                    onPressed: () => _ask(_q.text.trim()),
                    icon: Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(color: C.cream, borderRadius: BorderRadius.circular(12)),
                        child: const Icon(Icons.arrow_upward, size: 16, color: Color(0xFF111111))),
                  ),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: const BorderSide(color: C.border2)),
                  enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: const BorderSide(color: C.border2)),
                ),
              ),
            ]),
          )
        else
          Expanded(
            child: ListView(children: [
              for (final m in messengers)
                ListTile(
                  contentPadding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                  leading: CircleAvatar(
                      radius: 21,
                      backgroundColor: m.$3,
                      child: Text(m.$1[0], style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600))),
                  title: Text(m.$1, style: const TextStyle(fontWeight: FontWeight.w500)),
                  subtitle: const Text('Dotknij, aby otworzyć', style: TextStyle(color: Color(0xFF8F8F8F), fontSize: 12.5)),
                  onTap: () => _openApp(m.$1, m.$2),
                ),
              ListTile(
                contentPadding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                leading: Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: const Color(0xFF3A3A3A))),
                    child: const Icon(Icons.add, size: 18, color: C.text2)),
                title: const Text('Otwórz inną stronę w panelu', style: TextStyle(fontWeight: FontWeight.w500)),
                subtitle: const Text('Wpisz adres komunikatora lub strony', style: TextStyle(color: Color(0xFF8F8F8F), fontSize: 12.5)),
                onTap: () async {
                  final c = TextEditingController();
                  final u = await showDialog<String>(
                    context: context,
                    builder: (ctx) => AlertDialog(
                      backgroundColor: C.sheet,
                      title: const Text('Adres strony'),
                      content: TextField(controller: c, autofocus: true, keyboardType: TextInputType.url),
                      actions: [
                        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Anuluj')),
                        TextButton(onPressed: () => Navigator.pop(ctx, c.text), child: const Text('Otwórz')),
                      ],
                    ),
                  );
                  if (u != null && u.trim().isNotEmpty) _openApp(hostOf(widget.s.resolve(u)), widget.s.resolve(u));
                },
              ),
              const Padding(
                padding: EdgeInsets.fromLTRB(4, 12, 4, 0),
                child: Text('WhatsApp i część komunikatorów działa w przeglądarce tylko na komputerze – na telefonie użyj ich aplikacji.',
                    style: TextStyle(fontSize: 12, color: Color(0xFF8F8F8F), height: 1.5)),
              ),
            ]),
          ),
      ]),
    );
  }

  Widget _action(String t, VoidCallback onTap) => OutlinedButton(
        onPressed: onTap,
        style: OutlinedButton.styleFrom(
          foregroundColor: C.text,
          backgroundColor: const Color(0xFF1B1B1B),
          side: const BorderSide(color: C.border2),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
        child: Text(t),
      );
}

/// Strona aplikacji (czat, komunikator) na pełnym ekranie, z przyciskiem „otwórz jako kartę”.
class AppPage extends StatelessWidget {
  final String name, url, userAgent;
  final ValueChanged<String> onOpenTab;
  const AppPage({super.key, required this.name, required this.url, required this.userAgent, required this.onOpenTab});

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: C.bg,
        body: SafeArea(
          child: Column(children: [
            Row(children: [
              IconButton(tooltip: 'Zamknij', onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close, color: C.text2)),
              Expanded(child: Text(name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500))),
              IconButton(
                tooltip: 'Otwórz jako kartę',
                onPressed: () {
                  Navigator.popUntil(context, (r) => r.isFirst);
                  onOpenTab(url);
                },
                icon: const Icon(Icons.open_in_new, size: 20, color: C.text2),
              ),
            ]),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(20),
                  child: InAppWebView(
                    initialUrlRequest: URLRequest(url: WebUri(url)),
                    initialSettings: InAppWebViewSettings(
                      userAgent: userAgent,
                      safeBrowsingEnabled: false,
                      isFraudulentWebsiteWarningEnabled: false,
                      allowsBackForwardNavigationGestures: true,
                    ),
                    initialUserScripts: UnmodifiableListView<UserScript>([]),
                  ),
                ),
              ),
            ),
          ]),
        ),
      );
}
