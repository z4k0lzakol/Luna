// Podpowiedzi wyszukiwania z sieci – jak w Lunie na komputerze: wpisywany tekst trafia do wybranej wyszukiwarki
// (Brave, Google), dla pozostałych do DuckDuckGo. Wyłączysz to w Ustawieniach → „Podpowiedzi z sieci”.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

const _endpoints = {
  'Brave': 'https://search.brave.com/api/suggest?q=',
  'Google': 'https://suggestqueries.google.com/complete/search?client=chrome&q=',
};
const _ddg = 'https://duckduckgo.com/ac/?type=list&q=';

final _client = HttpClient()..connectionTimeout = const Duration(seconds: 4);

Future<List<String>> netSuggestions(String engine, String q) async {
  q = q.trim();
  if (q.length < 2) return [];
  final base = _endpoints[engine] ?? _ddg;
  try {
    final req = await _client.getUrl(Uri.parse(base + Uri.encodeQueryComponent(q)));
    final res = await req.close().timeout(const Duration(seconds: 4));
    if (res.statusCode != 200) return [];
    final body = jsonDecode(await res.transform(utf8.decoder).join());
    // format OpenSearch: ["zapytanie", ["podpowiedź", …]]
    if (body is List && body.length > 1 && body[1] is List) {
      return [for (final s in body[1] as List) if (s is String && s.trim().isNotEmpty) s].take(6).toList();
    }
  } catch (_) {}
  return [];
}
