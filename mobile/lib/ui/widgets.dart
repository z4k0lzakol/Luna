// Widgety: zegar, pogoda (Open-Meteo, jak na komputerze), seria dni i zadania.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

import '../state.dart';
import 'common.dart';

class WeatherData {
  final double temp, feels, wind;
  final int code, humidity;
  final List<(DateTime, int, double, double)> days;
  WeatherData(this.temp, this.feels, this.wind, this.code, this.humidity, this.days);
}

class Weather {
  Weather._();
  static final instance = Weather._();
  final data = ValueNotifier<WeatherData?>(null);
  DateTime? _at;
  String _key = '';

  Future<void> refresh(LunaState s, {bool force = false}) async {
    if (!s.weatherOn) return;
    final key = '${s.city['lat']},${s.city['lon']}';
    if (!force && key == _key && _at != null && DateTime.now().difference(_at!) < const Duration(minutes: 30)) return;
    final u = Uri.parse('https://api.open-meteo.com/v1/forecast?latitude=${s.city['lat']}&longitude=${s.city['lon']}'
        '&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code'
        '&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=6');
    try {
      final m = await _getJson(u);
      final c = m['current'] as Map;
      final d = m['daily'] as Map;
      final days = <(DateTime, int, double, double)>[];
      for (var i = 1; i < (d['time'] as List).length; i++) {
        days.add((
          DateTime.parse(d['time'][i] as String),
          (d['weather_code'][i] as num).toInt(),
          (d['temperature_2m_min'][i] as num).toDouble(),
          (d['temperature_2m_max'][i] as num).toDouble()
        ));
      }
      data.value = WeatherData((c['temperature_2m'] as num).toDouble(), (c['apparent_temperature'] as num).toDouble(),
          (c['wind_speed_10m'] as num).toDouble(), (c['weather_code'] as num).toInt(), (c['relative_humidity_2m'] as num).toInt(), days);
      _at = DateTime.now();
      _key = key;
    } catch (_) {}
  }

  static Future<List<Map<String, dynamic>>> searchCity(String q) async {
    final u = Uri.parse('https://geocoding-api.open-meteo.com/v1/search?count=8&language=pl&format=json&name=${Uri.encodeQueryComponent(q)}');
    final m = await _getJson(u);
    return [
      for (final r in (m['results'] ?? []) as List)
        {'name': r['name'], 'admin': r['admin1'] ?? r['country'] ?? '', 'lat': r['latitude'], 'lon': r['longitude']}
    ];
  }

  static Future<Map<String, dynamic>> _getJson(Uri u) async {
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 12);
    try {
      final res = await (await client.getUrl(u)).close().timeout(const Duration(seconds: 20));
      return jsonDecode(await res.transform(utf8.decoder).join()) as Map<String, dynamic>;
    } finally {
      client.close();
    }
  }
}

String weatherText(int c) {
  if (c == 0) return 'Bezchmurnie';
  if (c <= 2) return 'Częściowe zachmurzenie';
  if (c == 3) return 'Pochmurno';
  if (c == 45 || c == 48) return 'Mgła';
  if (c >= 51 && c <= 57) return 'Mżawka';
  if (c >= 61 && c <= 67) return 'Deszcz';
  if (c >= 71 && c <= 77) return 'Śnieg';
  if (c >= 80 && c <= 82) return 'Przelotny deszcz';
  if (c == 85 || c == 86) return 'Przelotny śnieg';
  if (c >= 95) return 'Burza';
  return '';
}

IconData weatherIcon(int c) {
  if (c == 0) return Icons.wb_sunny_outlined;
  if (c <= 2) return Icons.wb_cloudy_outlined;
  if (c == 3) return Icons.cloud_outlined;
  if (c == 45 || c == 48) return Icons.foggy;
  if (c >= 71 && c <= 77 || c == 85 || c == 86) return Icons.ac_unit;
  if (c >= 95) return Icons.thunderstorm_outlined;
  if (c >= 51) return Icons.grain;
  return Icons.cloud_outlined;
}

String deg(double v) => '${v.round()}°';

class _CardHead extends StatelessWidget {
  final String title;
  final VoidCallback? onMore;
  const _CardHead(this.title, {this.onMore});

  @override
  Widget build(BuildContext context) => Row(children: [
        Text(title, style: const TextStyle(fontSize: 10.5, letterSpacing: 1.3, color: C.label, fontWeight: FontWeight.w600)),
        const Spacer(),
        if (onMore != null)
          InkResponse(
              onTap: onMore,
              radius: 18,
              child: const Padding(padding: EdgeInsets.all(2), child: Icon(Icons.more_horiz, size: 18, color: Color(0xFF6F6F6F)))),
      ]);
}

/// Mała karta pogody (ekran główny).
class WeatherSmall extends StatelessWidget {
  final LunaState s;
  const WeatherSmall(this.s, {super.key});

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<WeatherData?>(
        valueListenable: Weather.instance.data,
        builder: (ctx, w, _) => LunaCard(
          onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => WidgetsScreen(s))),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const _CardHead('POGODA'),
            const SizedBox(height: 6),
            Row(children: [
              Icon(w == null ? Icons.cloud_outlined : weatherIcon(w.code), size: 24, color: const Color(0xFFD8D8D8)),
              const SizedBox(width: 8),
              Text(w == null ? '–' : '${w.temp.round()}°C', style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w300)),
            ]),
            const SizedBox(height: 4),
            Text('${s.city['name']}${w == null ? '' : ' · ${weatherText(w.code).toLowerCase()}'}',
                maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: C.muted)),
          ]),
        ),
      );
}

class StreakSmall extends StatelessWidget {
  final LunaState s;
  const StreakSmall(this.s, {super.key});

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final monday = now.subtract(Duration(days: now.weekday - 1));
    return LunaCard(
      onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => WidgetsScreen(s))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const _CardHead('SERIA'),
        const SizedBox(height: 6),
        Row(crossAxisAlignment: CrossAxisAlignment.baseline, textBaseline: TextBaseline.alphabetic, children: [
          Text('${s.streak}', style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w300)),
          const SizedBox(width: 6),
          Text(s.streak == 1 ? 'dzień z rzędu' : 'dni z rzędu', style: const TextStyle(fontSize: 12, color: C.muted)),
        ]),
        const SizedBox(height: 6),
        Row(children: [
          for (var i = 0; i < 7; i++)
            Container(
              margin: const EdgeInsets.only(right: 4),
              width: 14,
              height: 14,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: s.dayActive(monday.add(Duration(days: i))) ? C.text : Colors.transparent,
                border: Border.all(color: const Color(0xFF3A3A3A)),
              ),
            ),
        ]),
      ]),
    );
  }
}

class TasksCard extends StatefulWidget {
  final LunaState s;
  final bool compact;
  const TasksCard(this.s, {super.key, this.compact = false});

  @override
  State<TasksCard> createState() => _TasksCardState();
}

class _TasksCardState extends State<TasksCard> {
  final _c = TextEditingController();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  void _add(String t) {
    t = t.trim();
    if (t.isEmpty) return;
    widget.s.tasks.add(Task(t));
    widget.s.changed();
    _c.clear();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.s;
    final open = s.tasks.where((t) => !t.done).toList();
    if (widget.compact) {
      return LunaCard(
        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => WidgetsScreen(s))),
        child: Row(children: [
          const Text('ZADANIA', style: TextStyle(fontSize: 10.5, letterSpacing: 1.3, color: C.label, fontWeight: FontWeight.w600)),
          const SizedBox(width: 12),
          Expanded(
              child: Text(open.isEmpty ? 'Brak zadań. Świetnie!' : open.first.text,
                  maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13, color: C.text2))),
          if (open.length > 1) Text('+${open.length - 1}', style: const TextStyle(fontSize: 12, color: C.label)),
        ]),
      );
    }
    return LunaCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const _CardHead('ZADANIA'),
        const SizedBox(height: 10),
        TextField(
          controller: _c,
          onSubmitted: _add,
          style: const TextStyle(fontSize: 14),
          decoration: InputDecoration(
            isDense: true,
            hintText: 'Dodaj zadanie i naciśnij Enter',
            hintStyle: const TextStyle(color: Color(0xFF6F6F6F)),
            filled: true,
            fillColor: const Color(0xFF0E0E0E),
            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: C.border2)),
            enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: C.border2)),
          ),
        ),
        const SizedBox(height: 6),
        if (s.tasks.isEmpty) const Padding(padding: EdgeInsets.only(top: 4), child: Text('Brak zadań. Świetnie!', style: TextStyle(color: C.muted, fontSize: 13))),
        for (final t in List.of(s.tasks))
          Dismissible(
            key: ObjectKey(t),
            onDismissed: (_) {
              s.tasks.remove(t);
              s.changed();
            },
            child: InkWell(
              onTap: () {
                t.done = !t.done;
                s.changed();
                setState(() {});
              },
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(children: [
                  Icon(t.done ? Icons.check_circle : Icons.radio_button_unchecked, size: 20, color: t.done ? C.muted : C.text2),
                  const SizedBox(width: 10),
                  Expanded(
                      child: Text(t.text,
                          style: TextStyle(
                              fontSize: 14, color: t.done ? C.muted : C.text, decoration: t.done ? TextDecoration.lineThrough : null))),
                ]),
              ),
            ),
          ),
      ]),
    );
  }
}

/// Pełna lista widgetów.
class WidgetsScreen extends StatefulWidget {
  final LunaState s;
  const WidgetsScreen(this.s, {super.key});

  @override
  State<WidgetsScreen> createState() => _WidgetsScreenState();
}

class _WidgetsScreenState extends State<WidgetsScreen> {
  late Timer _t;
  DateTime _now = DateTime.now();

  @override
  void initState() {
    super.initState();
    _t = Timer.periodic(const Duration(seconds: 1), (_) => setState(() => _now = DateTime.now()));
    Weather.instance.refresh(widget.s);
  }

  @override
  void dispose() {
    _t.cancel();
    super.dispose();
  }

  Future<void> _pickCity() async {
    final s = widget.s;
    final picked = await showLunaSheet<Map<String, dynamic>>(context, (ctx) => const _CityPicker(), heightFactor: 0.8);
    if (picked != null) {
      s.city = picked;
      s.changed();
      await Weather.instance.refresh(s, force: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.s;
    return Scaffold(
      backgroundColor: C.bg,
      body: SafeArea(
        child: AnimatedBuilder(
          animation: s,
          builder: (ctx, _) => ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 24), children: [
            Row(children: [
              IconButton(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.chevron_left, color: C.text2), tooltip: 'Wróć'),
              const Text('Widgety', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w500)),
            ]),
            const SizedBox(height: 8),
            Reveal(0, child: LunaCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const _CardHead('ZEGAR'),
                const SizedBox(height: 6),
                Text.rich(TextSpan(children: [
                  TextSpan(text: '${two(_now.hour)}:${two(_now.minute)}'),
                  TextSpan(text: ':${two(_now.second)}', style: const TextStyle(color: Color(0xFF6F6F6F))),
                ]), style: const TextStyle(fontSize: 44, fontWeight: FontWeight.w300, height: 1.05)),
                const SizedBox(height: 4),
                Text('${weekdaysPl[_now.weekday - 1]}, ${_now.day} ${monthsPl[_now.month - 1]} ${_now.year}',
                    style: const TextStyle(fontSize: 13, color: C.muted)),
              ]),
            )),
            const SizedBox(height: 12),
            if (s.weatherOn)
              Reveal(1, child: ValueListenableBuilder<WeatherData?>(
                valueListenable: Weather.instance.data,
                builder: (ctx, w, _) => LunaCard(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    _CardHead('POGODA', onMore: _pickCity),
                    const SizedBox(height: 8),
                    Row(children: [
                      Icon(w == null ? Icons.cloud_outlined : weatherIcon(w.code), size: 44, color: const Color(0xFFE0E0E0)),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(w == null ? '–' : '${w.temp.round()}°C', style: const TextStyle(fontSize: 36, fontWeight: FontWeight.w300, height: 1)),
                          const SizedBox(height: 4),
                          Text('${s.city['name']}, ${s.city['admin']}${w == null ? '' : ' · ${weatherText(w.code).toLowerCase()}'}',
                              style: const TextStyle(fontSize: 13, color: C.muted)),
                        ]),
                      ),
                    ]),
                    if (w != null) ...[
                      const SizedBox(height: 12),
                      _row('Odczuwalna', deg(w.feels)),
                      _row('Wiatr', '${w.wind.round()} km/h'),
                      _row('Wilgotność', '${w.humidity}%'),
                      const Divider(height: 20),
                      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                        for (final d in w.days.take(5))
                          Column(children: [
                            Text(['pon.', 'wt.', 'śr.', 'czw.', 'pt.', 'sob.', 'niedz.'][d.$1.weekday - 1],
                                style: const TextStyle(fontSize: 12, color: C.muted)),
                            const SizedBox(height: 4),
                            Icon(weatherIcon(d.$2), size: 18, color: C.text2),
                            const SizedBox(height: 4),
                            Text('${deg(d.$3)}/${deg(d.$4)}', style: const TextStyle(fontSize: 12, color: C.text2)),
                          ]),
                      ]),
                    ],
                    const SizedBox(height: 10),
                    const Text('Dane pogodowe: Open-Meteo.com (CC BY 4.0)', style: TextStyle(fontSize: 11, color: Color(0xFF6F6F6F))),
                  ]),
                ),
              )),
            if (s.weatherOn) const SizedBox(height: 12),
            Reveal(2, child: StreakSmall(s)),
            const SizedBox(height: 12),
            Reveal(3, child: TasksCard(s)),
          ]),
        ),
      ),
    );
  }

  Widget _row(String k, String v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(children: [Text(k, style: const TextStyle(color: C.muted, fontSize: 13.5)), const Spacer(), Text(v, style: const TextStyle(fontSize: 13.5))]),
      );
}

class _CityPicker extends StatefulWidget {
  const _CityPicker();

  @override
  State<_CityPicker> createState() => _CityPickerState();
}

class _CityPickerState extends State<_CityPicker> {
  List<Map<String, dynamic>> _res = [];
  bool _busy = false;
  Timer? _deb;

  void _search(String q) {
    _deb?.cancel();
    _deb = Timer(const Duration(milliseconds: 350), () async {
      if (q.trim().length < 2) return;
      setState(() => _busy = true);
      try {
        final r = await Weather.searchCity(q.trim());
        if (mounted) setState(() => _res = r);
      } catch (_) {}
      if (mounted) setState(() => _busy = false);
    });
  }

  @override
  void dispose() {
    _deb?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(children: [
          TextField(
            autofocus: true,
            onChanged: _search,
            decoration: InputDecoration(
              hintText: 'Wpisz miejscowość',
              prefixIcon: const Icon(Icons.search, color: C.muted),
              filled: true,
              fillColor: C.field,
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: C.border2)),
            ),
          ),
          if (_busy) const LinearProgressIndicator(minHeight: 2),
          Expanded(
            child: ListView(children: [
              for (final r in _res)
                ListTile(
                  title: Text(r['name'] as String),
                  subtitle: Text(r['admin'] as String, style: const TextStyle(color: C.muted)),
                  onTap: () => Navigator.pop(context, r),
                ),
            ]),
          ),
        ]),
      );
}
