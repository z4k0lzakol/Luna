// Wspólny wygląd Luny na telefonie – te same barwy i formy co w wersji na komputer:
// czarne tło z gwiazdami, płaskie ciemne karty, małe etykiety wersalikami, kremowy przycisk główny.
import 'dart:math';

import 'package:flutter/cupertino.dart' show CupertinoPageTransitionsBuilder;
import 'package:flutter/material.dart';

class C {
  static const bg = Color(0xFF0B0B0B);
  static const sheet = Color(0xFF111111);
  static const card = Color(0xFF141414);
  static const card2 = Color(0xFF171717);
  static const field = Color(0xFF151515);
  static const border = Color(0xFF232323);
  static const border2 = Color(0xFF2A2A2A);
  static const text = Color(0xFFECECEC);
  static const text2 = Color(0xFFCFCFCF);
  static const muted = Color(0xFF9A9A9A);
  static const label = Color(0xFF8A8A8A);
  static const cream = Color(0xFFF3EFE6);
}

ThemeData lunaTheme() {
  final base = ThemeData(brightness: Brightness.dark, useMaterial3: true);
  return base.copyWith(
    scaffoldBackgroundColor: C.bg,
    colorScheme: const ColorScheme.dark(primary: C.cream, onPrimary: Color(0xFF111111), surface: C.sheet, onSurface: C.text),
    textTheme: base.textTheme.apply(bodyColor: C.text, displayColor: C.text),
    dividerColor: C.border,
    splashFactory: InkRipple.splashFactory,
    // przejścia między ekranami: krótkie przenikanie z lekkim przesunięciem (jak w Lunie na komputerze);
    // na iPhonie zostaje systemowe przesuwanie z gestem „wstecz” od krawędzi
    pageTransitionsTheme: const PageTransitionsTheme(builders: {
      TargetPlatform.android: _LunaTransitions(),
      TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
    }),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? const Color(0xFF111111) : C.muted),
      trackColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? C.cream : C.card2),
    ),
  );
}

/// Tło z gwiazdami (ekran główny, przewodnik) – stały układ, bez animacji.
class StarField extends StatelessWidget {
  final Widget child;
  const StarField({super.key, required this.child});

  @override
  Widget build(BuildContext context) => Stack(fit: StackFit.expand, children: [
        // gwiazdy na osobnej warstwie – nie są przemalowywane, gdy zmienia się zegar czy widgety
        RepaintBoundary(child: CustomPaint(painter: _Stars())),
        child,
      ]);
}

class _Stars extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = C.bg);
    final r = Random(7);
    final p = Paint();
    final n = (size.width * size.height / 5200).clamp(40, 260).toInt();
    for (var i = 0; i < n; i++) {
      p.color = Colors.white.withValues(alpha: 0.12 + r.nextDouble() * 0.45);
      canvas.drawCircle(Offset(r.nextDouble() * size.width, r.nextDouble() * size.height), 0.4 + r.nextDouble() * 0.8, p);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class SectionLabel extends StatelessWidget {
  final String text;
  final Widget? trailing;
  const SectionLabel(this.text, {super.key, this.trailing});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 4, 4, 2),
        child: Row(children: [
          Text(text.toUpperCase(),
              style: const TextStyle(fontSize: 11, letterSpacing: 1.4, color: C.label, fontWeight: FontWeight.w600)),
          const Spacer(),
          if (trailing != null) trailing!,
        ]),
      );
}

class LunaCard extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;
  final double radius;
  const LunaCard({super.key, required this.child, this.padding = const EdgeInsets.all(14), this.onTap, this.onLongPress, this.radius = 16});

  @override
  Widget build(BuildContext context) => Material(
        color: C.card,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(radius), side: const BorderSide(color: C.border)),
        clipBehavior: Clip.antiAlias,
        child: InkWell(onTap: onTap, onLongPress: onLongPress, child: Padding(padding: padding, child: child)),
      );
}

class SquareButton extends StatelessWidget {
  final Widget child;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;
  final String label;
  final double size;
  const SquareButton({super.key, required this.child, required this.label, this.onTap, this.onLongPress, this.size = 46});

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: label,
        child: Material(
          color: C.field,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15), side: const BorderSide(color: C.border2)),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: onTap,
            onLongPress: onLongPress,
            child: SizedBox(width: size, height: size, child: Center(child: child)),
          ),
        ),
      );
}

class CreamButton extends StatelessWidget {
  final String text;
  final IconData? icon;
  final VoidCallback onTap;
  const CreamButton(this.text, {super.key, this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) => Material(
        color: C.cream,
        shape: const StadiumBorder(),
        child: InkWell(
          customBorder: const StadiumBorder(),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 13),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              if (icon != null) ...[Icon(icon, size: 18, color: const Color(0xFF111111)), const SizedBox(width: 8)],
              Text(text, style: const TextStyle(color: Color(0xFF111111), fontWeight: FontWeight.w600, fontSize: 15)),
            ]),
          ),
        ),
      );
}

/// Kafelek menu: ikona nad podpisem.
class MenuTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final bool active;
  const MenuTile(this.icon, this.label, this.onTap, {super.key, this.active = false});

  @override
  Widget build(BuildContext context) => Material(
        color: active ? const Color(0xFF242424) : C.card2,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14), side: BorderSide(color: active ? const Color(0xFF555555) : const Color(0xFF262626))),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: SizedBox(
            height: 72,
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Icon(icon, size: 21, color: const Color(0xFFE6E6E6)),
              const SizedBox(height: 7),
              Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11.5, color: Color(0xFFDCDCDC))),
            ]),
          ),
        ),
      );
}

/// Segmentowy przełącznik (np. Otwarte / Na później / Prywatne).
class Segmented extends StatelessWidget {
  final List<String> labels;
  final int index;
  final ValueChanged<int> onChanged;
  final bool light;
  const Segmented({super.key, required this.labels, required this.index, required this.onChanged, this.light = false});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(color: const Color(0xFF121212), borderRadius: BorderRadius.circular(14), border: Border.all(color: C.border)),
        child: Row(children: [
          for (var i = 0; i < labels.length; i++)
            Expanded(
              child: GestureDetector(
                onTap: () => onChanged(i),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 180),
                  curve: Curves.easeOutCubic,
                  height: 36,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: i == index ? (light ? C.text : const Color(0xFF2A2A2A)) : Colors.transparent,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(labels[i],
                      style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w500,
                          color: i == index ? (light ? const Color(0xFF111111) : Colors.white) : C.muted)),
                ),
              ),
            ),
        ]),
      );
}

/// Arkusz od dołu w stylu Luny (zaokrąglony, z uchwytem).
Future<T?> showLunaSheet<T>(BuildContext context, WidgetBuilder builder, {double heightFactor = 0.86}) {
  return showModalBottomSheet<T>(
    context: context,
    sheetAnimationStyle: AnimationStyle(
      duration: const Duration(milliseconds: 280),
      reverseDuration: const Duration(milliseconds: 200),
      curve: Curves.easeOutCubic,
      reverseCurve: Curves.easeInCubic,
    ),
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: C.sheet,
    barrierColor: Colors.black54,
    shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(26)), side: BorderSide(color: Color(0xFF262626))),
    builder: (ctx) => FractionallySizedBox(
      heightFactor: heightFactor,
      child: Column(children: [
        const SizedBox(height: 8),
        Container(width: 38, height: 4, decoration: BoxDecoration(color: const Color(0xFF3A3A3A), borderRadius: BorderRadius.circular(2))),
        const SizedBox(height: 10),
        Expanded(child: builder(ctx)),
      ]),
    ),
  );
}

/// Litera zamiast ikony strony (bez pobierania ikon z zewnętrznych usług).
class SiteLetter extends StatelessWidget {
  final String host;
  final double size;
  const SiteLetter(this.host, {super.key, this.size = 16});

  @override
  Widget build(BuildContext context) {
    final p = host.split('.').where((x) => x.isNotEmpty).toList();
    var name = p.length >= 2 ? p[p.length - 2] : (p.isEmpty ? '' : p.first);
    if (p.length >= 3 && name.length <= 3 && p.last.length == 2) name = p[p.length - 3]; // np. onet.com.pl
    final letter = name.isEmpty ? '·' : name[0].toUpperCase();
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(color: const Color(0xFFF2F2F2), borderRadius: BorderRadius.circular(size / 4)),
      child: Text(letter, style: TextStyle(color: const Color(0xFF111111), fontWeight: FontWeight.w700, fontSize: size * 0.6)),
    );
  }
}

const weekdaysPl = ['poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota', 'niedziela'];
const monthsPl = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'];

String two(int n) => n.toString().padLeft(2, '0');

void toast(BuildContext context, String text) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      content: Text(text, style: const TextStyle(color: C.text)),
      backgroundColor: const Color(0xFF1C1C1C),
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: const BorderSide(color: C.border2)),
      duration: const Duration(milliseconds: 2200),
    ));
}

class _LunaTransitions extends PageTransitionsBuilder {
  const _LunaTransitions();

  @override
  Duration get transitionDuration => const Duration(milliseconds: 260);

  @override
  Duration get reverseTransitionDuration => const Duration(milliseconds: 200);

  @override
  Widget buildTransitions<T>(PageRoute<T> route, BuildContext context, Animation<double> animation, Animation<double> secondaryAnimation, Widget child) {
    final a = CurvedAnimation(parent: animation, curve: Curves.easeOutCubic, reverseCurve: Curves.easeInCubic);
    return FadeTransition(
      opacity: a,
      child: SlideTransition(position: Tween(begin: const Offset(0.06, 0), end: Offset.zero).animate(a), child: child),
    );
  }
}
