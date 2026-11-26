// Przewodnik przy pierwszym uruchomieniu – w stylu przewodnika z komputera.
import 'package:flutter/material.dart';

import 'common.dart';

class GuideScreen extends StatefulWidget {
  final VoidCallback onDone;
  const GuideScreen({super.key, required this.onDone});

  @override
  State<GuideScreen> createState() => _GuideScreenState();
}

class _GuideScreenState extends State<GuideScreen> {
  int _i = 0;

  static const _slides = [
    ('WITAJ W LUNIE', 'Prywatna przeglądarka w kieszeni',
        'Bez kont, bez telemetrii i bez serwerów Luny. Zakładki, historia i notatki zostają na tym telefonie.'),
    ('PASEK', 'Wszystko pod kciukiem',
        'Przesuń pasek w bok, by przejść do sąsiedniej karty, albo w górę, by zobaczyć wszystkie. Menu, asystent AI i komunikatory wysuwają się od dołu.'),
    ('DWIE STRONY', 'Dwie strony jedna pod drugą',
        'Przytrzymaj kartę i wybierz „Otwórz pod spodem”. Uchwyt pośrodku zmienia proporcje, a dwa dotknięcia zamieniają strony miejscami.'),
    ('PRYWATNOŚĆ', 'Bez reklam i śledzenia',
        'Tarcza blokuje reklamy i skrypty śledzące, także na YouTube. Jeśli strona nie działa, wyłącz blokadę tylko dla niej.'),
  ];

  Widget _art() {
    Widget phone(List<Widget> c) => Container(
          width: 150,
          height: 270,
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(26), border: Border.all(color: const Color(0xFF3A3A3A), width: 1.5), color: const Color(0xFF101010)),
          child: Column(children: c),
        );
    Widget block({double? h, bool dashed = false}) => Container(
          height: h,
          decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              color: dashed ? const Color(0xFF1A1A1A) : const Color(0xFF2A2A2A),
              border: dashed ? Border.all(color: const Color(0xFF6A6A6A), width: 1.5) : null),
        );
    final bar = Container(height: 22, margin: const EdgeInsets.only(top: 6), decoration: BoxDecoration(color: const Color(0xFF1F1F1F), borderRadius: BorderRadius.circular(8)));
    switch (_i) {
      case 0:
        return const Icon(Icons.nightlight_round, size: 110, color: C.cream);
      case 1:
        return phone([
          Expanded(child: block()),
          Container(
            height: 120,
            margin: const EdgeInsets.only(top: 6),
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(color: const Color(0xFF1C1C1C), borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0xFF3A3A3A))),
            child: GridView.count(
                crossAxisCount: 3,
                mainAxisSpacing: 5,
                crossAxisSpacing: 5,
                physics: const NeverScrollableScrollPhysics(),
                children: List.generate(9, (_) => Container(decoration: BoxDecoration(color: const Color(0xFF2E2E2E), borderRadius: BorderRadius.circular(6))))),
          ),
          bar,
        ]);
      case 2:
        return phone([
          Expanded(child: block()),
          Container(width: 26, height: 3, margin: const EdgeInsets.symmetric(vertical: 6), color: const Color(0xFF6A6A6A)),
          Expanded(child: block(dashed: true)),
          bar,
        ]);
      default:
        return phone([
          Expanded(child: Container(alignment: Alignment.center, decoration: BoxDecoration(color: const Color(0xFF2A2A2A), borderRadius: BorderRadius.circular(12)), child: const Icon(Icons.verified_user_outlined, size: 54, color: C.text))),
          bar,
        ]);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = _slides[_i];
    final last = _i == _slides.length - 1;
    return Scaffold(
      body: StarField(
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(28, 32, 28, 20),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SizedBox(
                height: 300,
                width: double.infinity,
                child: Center(child: AnimatedSwitcher(duration: const Duration(milliseconds: 220), child: KeyedSubtree(key: ValueKey(_i), child: _art()))),
              ),
              const SizedBox(height: 24),
              Text('${s.$1} · ${_i + 1} / ${_slides.length}', style: const TextStyle(fontSize: 11, letterSpacing: 1.5, color: C.label, fontWeight: FontWeight.w600)),
              const SizedBox(height: 12),
              Text(s.$2, style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w700, height: 1.18)),
              const SizedBox(height: 14),
              Text(s.$3, style: const TextStyle(fontSize: 15, height: 1.55, color: Color(0xFFB5B5B5))),
              const Spacer(),
              Row(children: [
                TextButton(onPressed: widget.onDone, child: const Text('Pomiń', style: TextStyle(color: Color(0xFFBDBDBD)))),
                Expanded(
                  child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    for (var k = 0; k < _slides.length; k++)
                      Container(
                          margin: const EdgeInsets.symmetric(horizontal: 3.5),
                          width: 8,
                          height: 8,
                          decoration: BoxDecoration(shape: BoxShape.circle, color: k == _i ? C.text : const Color(0xFF3A3A3A))),
                  ]),
                ),
                CreamButton(last ? 'Zaczynamy' : 'Dalej', onTap: () => last ? widget.onDone() : setState(() => _i++)),
              ]),
            ]),
          ),
        ),
      ),
    );
  }
}
