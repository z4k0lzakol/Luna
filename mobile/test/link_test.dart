// Testy Luna Link na telefonie: dwa telefony w jednym procesie oraz zgodność z Luną na komputerze (luna_link.py).
//   flutter test test/link_test.dart          (zgodność z komputerem – gdy jest python3 z pakietem cryptography)
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:luna/link/link.dart';

class H extends LinkHandler {
  final String dir;
  final log = <List<Object?>>[];
  bool acceptFiles = true;
  H(this.dir);

  @override
  List<String> features() => ['open', 'tabs', 'clip', 'sync', 'files', 'remote', 'notify'];
  @override
  bool allowed(String feature, Device? peer) => feature != 'files_unpaired' || acceptFiles;
  @override
  void onOpen(Device d, String url, String title) => log.add(['open', url, title]);
  @override
  List<Map<String, String>> tabs(Device d) => [
        {'url': 'https://tel.example.org/', 'title': 'Z telefonu'}
      ];
  @override
  void onClip(Device d, String text) => log.add(['clip', text]);
  @override
  Future<Map<String, dynamic>> onSync(Device d, Map<String, dynamic> payload) async {
    log.add(['sync', (payload['cols'] as Map?)?.keys.toList()]);
    return {'v': 1, 'cols': {'bookmarks': []}};
  }

  @override
  Future<List<int>> offerFiles(Device sender, List<FileOffer> files) async =>
      acceptFiles ? List.generate(files.length, (i) => i) : const [];
  @override
  Future<String> filesDir() async => dir;
  @override
  void onFilesDone(Device sender, List<File> files) => log.add(['files', files.map((f) => f.uri.pathSegments.last).toList()]);
  @override
  void onRemote(Device d, String cmd, Object? value) => log.add(['remote', cmd, value]);
  @override
  void onNotify(Device d, String title, String body, String kind) => log.add(['notify', title, body]);
}

void main() {
  late Directory tmp;
  setUpAll(() => tmp = Directory.systemTemp.createTempSync('luna_link_'));

  test('two phones: pair, open, tabs, clipboard, files byte-for-byte, unpair', () async {
    final ha = H('${tmp.path}/a_in'), hb = H('${tmp.path}/b_in');
    final a = Link(File('${tmp.path}/a.json'), ha, name: 'Telefon A', discovery: false, portWanted: 0);
    final b = Link(File('${tmp.path}/b.json'), hb, name: 'Telefon B', discovery: false, portWanted: 0);
    await a.start();
    await b.start();
    expect(a.fp, hasLength(64));
    expect(a.fp, isNot(b.fp));
    final uri = await a.pairUri();
    final d = Link.parsePairUri(uri);
    expect(d['code'], a.code);
    await expectLater(b.pairWith('127.0.0.1', a.port!, '0' * 64, d['code'] as String), throwsA(isA<LinkError>()));
    await expectLater(b.pairWith('127.0.0.1', a.port!, a.fp, '999999' == d['code'] ? '111111' : '999999'), throwsA(isA<LinkError>()));
    final p = await b.pairWith('127.0.0.1', a.port!, a.fp, d['code'] as String);
    expect(p.id, a.id);
    expect(a.peers.containsKey(b.id), isTrue);
    a.peers[b.id]!
      ..addr = '127.0.0.1'
      ..port = b.port!;

    await b.openOn(a.id, 'https://example.com/x', 'X');
    expect(ha.log, contains(['open', 'https://example.com/x', 'X']));
    await expectLater(b.openOn(a.id, 'file:///etc/passwd'), throwsA(isA<LinkError>()));
    expect(await b.tabsOf(a.id), [
      {'url': 'https://tel.example.org/', 'title': 'Z telefonu'}
    ]);
    await a.clipTo(b.id, 'zażółć');
    expect(hb.log, contains(['clip', 'zażółć']));

    final src = File('${tmp.path}/zdjęcie.jpg')..writeAsBytesSync(List.generate(3 * 1024 * 1024 + 7, (i) => (i * 31) % 256));
    var last = 0;
    final n = await b.sendFiles(a.id, [src], progress: (d, t, _) => last = d);
    expect(n, 1);
    expect(last, src.lengthSync());
    expect(File('${ha.dir}/zdjęcie.jpg').readAsBytesSync(), src.readAsBytesSync());
    await b.sendFiles(a.id, [src]);
    expect(File('${ha.dir}/zdjęcie (2).jpg').existsSync(), isTrue);
    ha.acceptFiles = false;
    await expectLater(b.sendFiles(a.id, [src]), throwsA(isA<LinkError>()));

    await b.forget(a.id);
    expect(a.peers.containsKey(b.id), isFalse);
    expect(b.peers.containsKey(a.id), isFalse);
    await a.stop();
    await b.stop();
  });

  test('pairing code stops working after 5 wrong guesses', () async {
    final a = Link(File('${tmp.path}/g.json'), H('${tmp.path}/g'), discovery: false, portWanted: 0);
    final b = Link(File('${tmp.path}/h.json'), H('${tmp.path}/h'), discovery: false, portWanted: 0);
    await a.start();
    await b.start();
    a.newCode();
    for (var i = 0; i < 5; i++) {
      await expectLater(b.pairWith('127.0.0.1', a.port!, a.fp, 'x'), throwsA(isA<LinkError>()));
    }
    expect(a.code, isNull);
    await a.stop();
    await b.stop();
  });

  test('works with Luna on the computer (luna_link.py)', () async {
    final py = Platform.environment['LUNA_PYTHON'] ?? 'python3';
    final script = File('../tests/link_peer.py');
    if (!script.existsSync()) {
      markTestSkipped('brak tests/link_peer.py');
      return;
    }
    Process pc;
    try {
      pc = await Process.start(py, [script.path, '${tmp.path}/pc']);
    } catch (e) {
      markTestSkipped('brak pythona: $e');
      return;
    }
    final events = StreamController<Map<String, dynamic>>.broadcast();
    final seen = <Map<String, dynamic>>[];
    pc.stdout.transform(utf8.decoder).transform(const LineSplitter()).listen((l) {
      final m = Map<String, dynamic>.from(jsonDecode(l) as Map);
      seen.add(m);
      events.add(m);
    });
    final err = StringBuffer();
    pc.stderr.transform(utf8.decoder).listen(err.write);
    Future<Map<String, dynamic>> wait(String ev) async {
      final had = seen.where((m) => m['ev'] == ev || m['ev'] == 'error');
      if (had.isNotEmpty) return had.first;
      return events.stream.firstWhere((m) => m['ev'] == ev || m['ev'] == 'error').timeout(const Duration(seconds: 30),
          onTimeout: () => throw StateError('czekam na $ev; stderr: $err'));
    }

    final ready = await wait('ready');
    if (ready['ev'] == 'error' || (err.toString().contains('ModuleNotFoundError'))) {
      markTestSkipped('komputer nie wystartował: ${ready['error']} $err');
      pc.kill();
      return;
    }
    final ht = H('${tmp.path}/tel_in');
    final tel = Link(File('${tmp.path}/tel.json'), ht, name: 'Telefon', discovery: false, portWanted: 0);
    await tel.start();

    final p = await tel.pairWith('127.0.0.1', ready['port'] as int, ready['fp'] as String, ready['code'] as String);
    expect(p.name, 'Komputer testowy');
    expect((await wait('paired'))['type'], 'phone');

    await tel.openOn(p.id, 'https://z-telefonu.example.org/', 'Z telefonu');
    expect((await wait('open'))['url'], 'https://z-telefonu.example.org/');
    expect((await tel.tabsOf(p.id)).first['title'], 'Z komputera');
    await tel.clipTo(p.id, 'schowek ąę');
    expect((await wait('clip'))['text'], 'schowek ąę');
    await tel.remote(p.id, 'seek', 10);
    expect((await wait('remote'))['value'], 10);
    final r = await tel.syncWith(p.id, {'v': 1, 'cols': {'bookmarks': [], 'tiles': []}, 'mtime': {}, 'tabs': []});
    expect((await wait('sync'))['cols'], ['bookmarks', 'tiles']);
    expect(((r['cols'] as Map)['bookmarks'] as List).first['url'], 'https://bm.example.org');

    final photo = File('${tmp.path}/film.mp4')..writeAsBytesSync(List.generate(2 * 1024 * 1024 + 3, (i) => (i * 7) % 251));
    expect(await tel.sendFiles(p.id, [photo]), 1);
    final f = await wait('files');
    expect(f['sizes'], [photo.lengthSync()]);
    expect(File('${tmp.path}/pc/odebrane/film.mp4').readAsBytesSync(), photo.readAsBytesSync());

    // komputer → telefon
    void cmd(Map<String, dynamic> c) => pc.stdin.writeln(jsonEncode({...c, 'addr': '127.0.0.1', 'port': tel.port}));
    cmd({'cmd': 'open', 'url': 'https://z-komputera.example.org/'});
    await wait('done');
    expect(ht.log.any((e) => e[0] == 'open' && e[1] == 'https://z-komputera.example.org/'), isTrue);
    seen.removeWhere((m) => m['ev'] == 'done');
    cmd({'cmd': 'clip', 'text': 'z komputera'});
    await wait('done');
    expect(ht.log, contains(['clip', 'z komputera']));
    seen.removeWhere((m) => m['ev'] == 'done');
    cmd({'cmd': 'notify', 'title': 'Pobieranie skończone', 'body': 'a.zip'});
    await wait('done');
    expect(ht.log, contains(['notify', 'Pobieranie skończone', 'a.zip']));
    seen.removeWhere((m) => m['ev'] == 'done');
    cmd({'cmd': 'files', 'name': 'dokument.pdf', 'kb': 600});
    final sent = await wait('sent');
    expect(sent['n'], 1, reason: '$sent $err');
    expect(File('${ht.dir}/dokument.pdf').lengthSync(), sent['size']);
    expect(seen.where((m) => m['ev'] == 'error'), isEmpty, reason: '$seen');

    await pc.stdin.close();
    await pc.exitCode.timeout(const Duration(seconds: 10), onTimeout: () {
      pc.kill();
      return -1;
    });
    await tel.stop();
  });
}
