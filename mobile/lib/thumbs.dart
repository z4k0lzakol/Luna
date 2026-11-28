// Podglądy kart (zrzut strony, JPEG ~360 px): w pamięci i na dysku, więc lista kart pokazuje je także po ponownym
// otwarciu Luny i dla kart uśpionych. Prywatne karty nie trafiają na dysk.
import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

class ThumbStore {
  ThumbStore._();
  static final instance = ThumbStore._();

  final Map<String, Uint8List> map = {};
  Directory? _dir;

  Future<Directory> _d() async {
    if (_dir != null) return _dir!;
    _dir = Directory('${(await getApplicationSupportDirectory()).path}/miniatury');
    await _dir!.create(recursive: true);
    return _dir!;
  }

  /// Wczytuje zapisane podglądy otwartych kart; pozostałe (zamknięte karty) usuwa.
  Future<void> load(Set<String> openIds) async {
    try {
      await for (final f in (await _d()).list()) {
        if (f is! File || !f.path.endsWith('.jpg')) continue;
        final id = f.uri.pathSegments.last.replaceAll('.jpg', '');
        if (openIds.contains(id)) {
          map.putIfAbsent(id, () => f.readAsBytesSync());
        } else {
          await f.delete();
        }
      }
    } catch (_) {}
  }

  Future<void> put(String id, Uint8List bytes, {bool private = false}) async {
    map[id] = bytes;
    if (private) return;
    try {
      await File('${(await _d()).path}/$id.jpg').writeAsBytes(bytes, flush: false);
    } catch (_) {}
  }

  Future<void> remove(String id) async {
    map.remove(id);
    try {
      final f = File('${(await _d()).path}/$id.jpg');
      if (await f.exists()) await f.delete();
    } catch (_) {}
  }
}
