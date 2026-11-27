// Luna Link na telefonie – połączenie z Luną na komputerze (i innymi telefonami) w sieci lokalnej, bez serwerów Luny.
// Ten sam protokół co luna_link.py na komputerze: POLACZENIE_URZADZEN.md. Tylko dart:io – testowane bez interfejsu.
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:basic_utils/basic_utils.dart';
import 'package:crypto/crypto.dart' as crypto;

const linkGroup = '224.0.0.167';
const discoveryPort = 53318;
const httpPort = 53317;
const codeTtl = Duration(minutes: 5);
const nearbyTtl = Duration(seconds: 90);

final _rnd = Random.secure();

String _hex(List<int> b) => b.map((x) => x.toRadixString(16).padLeft(2, '0')).join();
String randomHex(int bytes) => _hex(List.generate(bytes, (_) => _rnd.nextInt(256)));
String b64u(List<int> b) => base64Url.encode(b).replaceAll('=', '');
List<int> unb64u(String s) => base64Url.decode(s + '=' * ((4 - s.length % 4) % 4));
String fingerprintDer(List<int> der) => crypto.sha256.convert(der).toString();

List<int> pemToDer(String pem) =>
    base64.decode(pem.split('\n').where((l) => l.isNotEmpty && !l.startsWith('-----')).join());

class LinkError implements Exception {
  final String message;
  LinkError(this.message);
  @override
  String toString() => message;
}

/// Urządzenie: sparowane (z tokenem) albo tylko widoczne w sieci.
class Device {
  final String id;
  String name, type, fp;
  String? token, addr;
  int port;
  DateTime seen;
  Device({required this.id, required this.name, required this.type, required this.fp, this.token, this.addr, this.port = httpPort})
      : seen = DateTime.now();

  bool get paired => token != null;

  Map<String, dynamic> toJson() => {'name': name, 'type': type, 'fp': fp, 'token': token, 'addr': addr, 'port': port};
  factory Device.fromJson(String id, Map m) => Device(
      id: id, name: '${m['name'] ?? '?'}', type: '${m['type'] ?? 'desktop'}', fp: '${m['fp'] ?? ''}',
      token: m['token'] as String?, addr: m['addr'] as String?, port: (m['port'] ?? httpPort) as int);
}

class FileOffer {
  final String name, sha256, type;
  final int size;
  FileOffer(this.name, this.size, this.sha256, this.type);
  Map<String, dynamic> toJson() => {'name': name, 'size': size, 'sha256': sha256, 'type': type};
}

/// To, co Luna obsługuje po stronie interfejsu. Domyślnie wszystko odmawia.
abstract class LinkHandler {
  List<String> features() => const [];
  bool allowed(String feature, Device? peer) => false;
  void onPaired(Device d) {}
  void onUnpaired(Device d) {}
  void onOpen(Device d, String url, String title) {}
  List<Map<String, String>> tabs(Device d) => const [];
  void onClip(Device d, String text) {}
  Future<Map<String, dynamic>> onSync(Device d, Map<String, dynamic> payload) async => {};
  Future<List<int>> offerFiles(Device sender, List<FileOffer> files) async => const [];
  Future<String> filesDir();
  void onFile(Device sender, File f, FileOffer meta) {}
  void onFilesDone(Device sender, List<File> files) {}
  void onRemote(Device d, String cmd, Object? value) {}
  void onNotify(Device d, String title, String body, String kind) {}
  Future<bool> onApprove(Device d, String what, String detail) async => false;
  void nearbyChanged() {}
}

class Link {
  final File stateFile;
  final LinkHandler h;
  final bool discovery;
  final int portWanted, discoveryPortWanted;
  Map<String, dynamic> st = {};
  final Map<String, Device> peers = {};
  final Map<String, Device> nearby = {};
  HttpServer? _server;
  RawDatagramSocket? _udp;
  Timer? _announceTimer;
  (String, DateTime)? _code;
  int _codeFails = 0;
  final Map<String, _Session> _sessions = {};

  Link(this.stateFile, this.h,
      {String name = 'Telefon', String type = 'phone', this.discovery = true, this.portWanted = httpPort,
      this.discoveryPortWanted = discoveryPort}) {
    _load();
    st.putIfAbsent('id', () => randomHex(8));
    st.putIfAbsent('name', () => name);
    st.putIfAbsent('type', () => type);
  }

  String get id => st['id'] as String;
  String get name => st['name'] as String;
  String get type => st['type'] as String;
  String get fp => (st['fp'] ?? '') as String;
  int? get port => _server?.port;
  bool get running => _server != null;
  String? get code => _code != null && _code!.$2.isAfter(DateTime.now()) ? _code!.$1 : null;

  void _load() {
    try {
      final m = jsonDecode(stateFile.readAsStringSync()) as Map;
      st = Map<String, dynamic>.from(m);
      for (final e in ((st['peers'] ?? {}) as Map).entries) {
        peers[e.key as String] = Device.fromJson(e.key as String, e.value as Map);
      }
    } catch (_) {}
  }

  void save() {
    st['peers'] = {for (final p in peers.values) p.id: p.toJson()};
    final tmp = File('${stateFile.path}.tmp');
    tmp.writeAsStringSync(jsonEncode(st));
    tmp.renameSync(stateFile.path);
  }

  void setName(String n) {
    n = n.trim();
    if (n.isEmpty) return;
    st['name'] = n.length > 60 ? n.substring(0, 60) : n;
    save();
    announce();
  }

  Map<String, dynamic> info() =>
      {'luna': 1, 'id': id, 'name': name, 'type': type, 'fp': fp, 'port': port ?? portWanted, 'features': h.features()};

  // --- certyfikat ---
  void ensureCert() {
    if (st['cert'] == null || st['key'] == null) {
      final pair = CryptoUtils.generateEcKeyPair();
      final priv = pair.privateKey as ECPrivateKey, pub = pair.publicKey as ECPublicKey;
      final csr = X509Utils.generateEccCsrPem({'CN': 'Luna $id'}, priv, pub);
      st['cert'] = X509Utils.generateSelfSignedCertificate(priv, csr, 365 * 20,
          serialNumber: BigInt.parse(randomHex(8), radix: 16).toString(), notBefore: DateTime.now().subtract(const Duration(days: 1)));
      st['key'] = CryptoUtils.encodeEcPrivateKeyToPem(priv);
    }
    final f = fingerprintDer(pemToDer(st['cert'] as String));
    if (st['fp'] != f) st['fp'] = f;
    save();
  }

  // --- start / stop ---
  Future<void> start() async {
    if (_server != null) return;
    ensureCert();
    final ctx = SecurityContext()
      ..useCertificateChainBytes(utf8.encode(st['cert'] as String))
      ..usePrivateKeyBytes(utf8.encode(st['key'] as String));
    final ports = portWanted == 0 ? [0] : [for (var i = 0; i < 20; i++) portWanted + i, 0];
    for (final p in ports) {
      try {
        _server = await HttpServer.bindSecure(InternetAddress.anyIPv4, p, ctx);
        break;
      } on SocketException {
        continue;
      }
    }
    if (_server == null) throw LinkError('nie udało się otworzyć portu');
    _server!.listen(_handle, onError: (_) {});
    if (discovery) {
      try {
        await _startDiscovery();
      } catch (_) {
        _udp = null;
      }
    }
  }

  Future<void> stop() async {
    _announceTimer?.cancel();
    _udp?.close();
    _udp = null;
    await _server?.close(force: true);
    _server = null;
    nearby.clear();
  }

  // --- wykrywanie ---
  Future<void> _startDiscovery() async {
    final s = await RawDatagramSocket.bind(InternetAddress.anyIPv4, discoveryPortWanted, reuseAddress: true);
    s.joinMulticast(InternetAddress(linkGroup));
    s.multicastHops = 1;
    s.broadcastEnabled = true;
    _udp = s;
    s.listen((ev) {
      if (ev != RawSocketEvent.read) return;
      final dg = s.receive();
      if (dg == null) return;
      try {
        final d = jsonDecode(utf8.decode(dg.data)) as Map;
        if (d['luna'] != 1 || d['id'] == null || d['id'] == id) return;
        saw('${d['id']}', '${d['name'] ?? '?'}', '${d['type'] ?? 'desktop'}', '${d['fp'] ?? ''}', dg.address.address,
            (d['port'] ?? httpPort) as int);
        if (d['reply'] != true) announce(reply: true);
      } catch (_) {}
    });
    announce();
    _announceTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      announce();
      final old = nearby.values.where((n) => DateTime.now().difference(n.seen) > nearbyTtl).map((n) => n.id).toList();
      for (final k in old) {
        nearby.remove(k);
      }
      if (old.isNotEmpty) h.nearbyChanged();
    });
  }

  void announce({bool reply = false}) {
    final s = _udp;
    if (s == null) return;
    try {
      s.send(utf8.encode(jsonEncode({'luna': 1, 'id': id, 'name': name, 'type': type, 'port': port, 'fp': fp, 'reply': reply})),
          InternetAddress(linkGroup), discoveryPortWanted);
    } catch (_) {}
  }

  void saw(String pid, String n, String t, String f, String addr, int p) {
    final isNew = !nearby.containsKey(pid);
    nearby[pid] = Device(id: pid, name: n, type: t, fp: f, addr: addr, port: p, token: peers[pid]?.token);
    final known = peers[pid];
    if (known != null && known.fp == f && (known.addr != addr || known.port != p)) {
      known.addr = addr;
      known.port = p;
      save();
    }
    if (isNew) h.nearbyChanged();
  }

  bool reachable(String pid) => nearby.containsKey(pid);

  // --- parowanie ---
  String newCode() {
    _code = ('${_rnd.nextInt(1000000)}'.padLeft(6, '0'), DateTime.now().add(codeTtl));
    _codeFails = 0;
    return _code!.$1;
  }

  Future<String> pairUri() async {
    final c = code ?? newCode();
    final ips = <String>[];
    try {
      for (final i in await NetworkInterface.list(type: InternetAddressType.IPv4)) {
        for (final a in i.addresses) {
          if (!a.isLoopback) ips.add(a.address);
        }
      }
    } catch (_) {}
    final d = {'v': 1, 'id': id, 'name': name, 'type': type, 'ips': ips, 'port': port, 'fp': fp, 'code': c};
    return 'luna://pair?d=${b64u(utf8.encode(jsonEncode(d)))}';
  }

  static Map<String, dynamic> parsePairUri(String uri) {
    final m = RegExp(r'^luna://pair\?d=([A-Za-z0-9_-]+)$').firstMatch(uri.trim());
    if (m == null) throw LinkError('to nie jest kod parowania Luny');
    return Map<String, dynamic>.from(jsonDecode(utf8.decode(unb64u(m.group(1)!))) as Map);
  }

  Map<String, dynamic> _acceptPair(Map d, String addr) {
    final c = code;
    if (c == null || '${d['code']}' != c) {
      if (++_codeFails >= 5) _code = null;
      throw LinkError('zły albo nieważny kod parowania');
    }
    if (!RegExp(r'^[0-9a-f]{16}$').hasMatch('${d['id']}') || !RegExp(r'^[0-9a-f]{64}$').hasMatch('${d['fp']}')) {
      throw LinkError('niepoprawne dane urządzenia');
    }
    _code = null;
    final token = b64u(List.generate(32, (_) => _rnd.nextInt(256)));
    final p = Device(id: '${d['id']}', name: _short('${d['name'] ?? '?'}'), type: '${d['type'] ?? 'desktop'}', fp: '${d['fp']}',
        token: token, addr: addr, port: (d['port'] ?? httpPort) as int);
    peers[p.id] = p;
    save();
    h.onPaired(p);
    return {'token': token, 'id': id, 'name': name, 'type': type, 'fp': fp};
  }

  Future<Device> pairWith(String addr, int port, String fp, String code) async {
    final r = await _call(addr, port, fp, 'POST', '/v1/pair',
        body: {'id': id, 'name': name, 'type': type, 'fp': this.fp, 'port': this.port, 'code': code});
    if (r['fp'] != fp || r['token'] == null) throw LinkError('urządzenie odpowiedziało niepoprawnie');
    final p = Device(id: '${r['id']}', name: _short('${r['name'] ?? '?'}'), type: '${r['type'] ?? 'desktop'}', fp: fp,
        token: '${r['token']}', addr: addr, port: port);
    peers[p.id] = p;
    nearby[p.id]?.token = p.token;
    save();
    h.onPaired(p);
    return p;
  }

  Future<Device> pairFromUri(String uri) async {
    final d = parsePairUri(uri);
    Object? last;
    for (final ip in (d['ips'] as List? ?? const [])) {
      try {
        return await pairWith('$ip', d['port'] as int, '${d['fp']}', '${d['code']}');
      } on LinkError catch (e) {
        if (e.message.contains('kod')) rethrow;
        last = e;
      } catch (e) {
        last = e;
      }
    }
    throw LinkError('nie udało się połączyć z „${d['name']}” – czy telefon i komputer są w tej samej sieci Wi-Fi? ($last)');
  }

  Future<void> forget(String pid, {bool tell = true}) async {
    final p = peers[pid];
    if (p == null) return;
    if (tell) {
      try {
        await request(pid, 'POST', '/v1/unpair', body: {}, timeout: const Duration(seconds: 4));
      } catch (_) {}
    }
    peers.remove(pid);
    nearby[pid]?.token = null;
    save();
    h.onUnpaired(p);
  }

  // --- klient ---
  HttpClient _client(String fp, Duration timeout) {
    final c = HttpClient(context: SecurityContext(withTrustedRoots: false))
      ..connectionTimeout = timeout
      ..idleTimeout = const Duration(seconds: 5);
    // samopodpisany certyfikat: przyjmowany tylko gdy odcisk zgadza się z zapisanym / ogłoszonym
    c.badCertificateCallback = (cert, host, port) => fp.isNotEmpty && fingerprintDer(cert.der) == fp;
    return c;
  }

  Map<String, String> _headers(String? token) => {'X-Luna-Id': id, if (token != null) 'X-Luna-Token': token, 'User-Agent': 'Luna-Link/1'};

  Future<Map<String, dynamic>> _call(String addr, int port, String fp, String method, String path,
      {Map<String, dynamic>? body, String? token, Duration timeout = const Duration(seconds: 10)}) async {
    final c = _client(fp, timeout);
    try {
      final req = await c.openUrl(method, Uri(scheme: 'https', host: addr, port: port, path: path)).timeout(timeout);
      _headers(token).forEach(req.headers.set);
      if (body != null) {
        final data = utf8.encode(jsonEncode(body));
        req.headers.contentType = ContentType.json;
        req.contentLength = data.length;
        req.add(data);
      }
      final res = await req.close().timeout(timeout * 6);
      final text = await res.transform(utf8.decoder).join();
      Map<String, dynamic> d;
      try {
        d = text.isEmpty ? {} : Map<String, dynamic>.from(jsonDecode(text) as Map);
      } catch (_) {
        d = {};
      }
      if (res.statusCode >= 400) throw LinkError('${d['error'] ?? 'błąd ${res.statusCode}'}');
      return d;
    } on HandshakeException {
      throw LinkError('certyfikat urządzenia się nie zgadza – połączenie przerwane');
    } finally {
      c.close(force: true);
    }
  }

  List<(String, int)> addresses(String pid) {
    final p = peers[pid];
    final out = <(String, int)>[];
    final n = nearby[pid];
    if (n != null && n.addr != null && n.fp == p?.fp) out.add((n.addr!, n.port));
    if (p?.addr != null && !out.contains((p!.addr!, p.port))) out.add((p.addr!, p.port));
    return out;
  }

  Future<Map<String, dynamic>> request(String pid, String method, String path,
      {Map<String, dynamic>? body, Duration timeout = const Duration(seconds: 10)}) async {
    final p = peers[pid];
    if (p == null) throw LinkError('urządzenie nie jest sparowane');
    Object last = LinkError('urządzenie nie jest w tej sieci');
    for (final (addr, port) in addresses(pid)) {
      try {
        final r = await _call(addr, port, p.fp, method, path, body: body, token: p.token, timeout: timeout);
        if (p.addr != addr || p.port != port) {
          p.addr = addr;
          p.port = port;
          save();
        }
        return r;
      } on LinkError catch (e) {
        if (!e.message.startsWith('certyfikat')) rethrow;
        last = e;
      } catch (e) {
        last = e;
      }
    }
    throw last is LinkError ? last : LinkError('brak połączenia ($last)');
  }

  Future<void> openOn(String pid, String url, [String title = '']) => request(pid, 'POST', '/v1/open', body: {'url': url, 'title': title});
  Future<List<Map<String, String>>> tabsOf(String pid) async {
    final r = await request(pid, 'GET', '/v1/tabs', timeout: const Duration(seconds: 6));
    return [for (final t in (r['tabs'] as List? ?? const [])) {'url': '${(t as Map)['url']}', 'title': '${t['title'] ?? ''}'}];
  }

  Future<void> clipTo(String pid, String text) => request(pid, 'POST', '/v1/clip', body: {'text': text});
  Future<Map<String, dynamic>> syncWith(String pid, Map<String, dynamic> payload) =>
      request(pid, 'POST', '/v1/sync', body: payload, timeout: const Duration(seconds: 30));
  Future<void> remote(String pid, String cmd, [Object? value]) =>
      request(pid, 'POST', '/v1/remote', body: {'cmd': cmd, 'value': value}, timeout: const Duration(seconds: 5));
  Future<void> notify(String pid, String title, [String body = '', String kind = '']) =>
      request(pid, 'POST', '/v1/notify', body: {'title': title, 'body': body, 'kind': kind}, timeout: const Duration(seconds: 5));

  /// Pliki bajt w bajt. target: sparowane urządzenie (id) albo widoczne w sieci (Device bez tokenu).
  Future<int> sendFiles(Object target, List<File> files,
      {void Function(int done, int total, String name)? progress, bool Function()? cancelled}) async {
    late List<(String, int)> addrs;
    late String tfp;
    String? token;
    if (target is String) {
      final p = peers[target];
      if (p == null) throw LinkError('urządzenie nie jest sparowane');
      addrs = addresses(target);
      tfp = p.fp;
      token = p.token;
    } else {
      final d = target as Device;
      addrs = [(d.addr!, d.port)];
      tfp = d.fp;
      token = peers[d.id]?.token;
    }
    final offers = <FileOffer>[];
    for (final f in files) {
      final digest = await crypto.sha256.bind(f.openRead()).first;
      final n = f.path.split(RegExp(r'[/\\]')).last;
      offers.add(FileOffer(n.isEmpty ? 'plik' : n, await f.length(), digest.toString(), ''));
    }
    final total = offers.fold<int>(0, (a, o) => a + o.size);
    Map<String, dynamic>? offer;
    String? addr;
    int? port;
    Object? last;
    for (final (a, p) in addrs) {
      try {
        offer = await _call(a, p, tfp, 'POST', '/v1/files',
            body: {'files': [for (final o in offers) o.toJson()]}, token: token, timeout: const Duration(seconds: 75));
        addr = a;
        port = p;
        break;
      } on LinkError {
        rethrow;
      } catch (e) {
        last = e;
      }
    }
    if (offer == null) throw LinkError('brak połączenia ($last)');
    final sess = '${offer['session']}';
    var done = 0, sent = 0;
    for (final i in (offer['accept'] as List? ?? const [])) {
      final idx = i as int;
      if (cancelled?.call() ?? false) throw LinkError('przerwano');
      final c = _client(tfp, const Duration(seconds: 30));
      try {
        final req = await c.openUrl('PUT', Uri(scheme: 'https', host: addr, port: port, path: '/v1/files/$sess/$idx'));
        _headers(token).forEach(req.headers.set);
        req.contentLength = offers[idx].size;
        req.headers.contentType = ContentType.binary;
        await for (final chunk in files[idx].openRead()) {
          if (cancelled?.call() ?? false) throw LinkError('przerwano');
          req.add(chunk);
          done += chunk.length;
          progress?.call(done, total, offers[idx].name);
        }
        final res = await req.close();
        final text = await res.transform(utf8.decoder).join();
        if (res.statusCode >= 400) {
          String? msg;
          try {
            msg = (jsonDecode(text) as Map)['error'] as String?;
          } catch (_) {}
          throw LinkError(msg ?? 'błąd ${res.statusCode}');
        }
        sent++;
      } finally {
        c.close(force: true);
      }
    }
    return sent;
  }

  // --- serwer ---
  Device? _auth(HttpRequest r) {
    final pid = r.headers.value('x-luna-id') ?? '';
    final tok = r.headers.value('x-luna-token');
    final p = peers[pid];
    if (p != null && tok != null && tok == p.token) return p;
    return null;
  }

  Future<void> _handle(HttpRequest r) async {
    int code;
    Map<String, dynamic> out;
    try {
      (code, out) = await _route(r);
    } on LinkError catch (e) {
      (code, out) = (403, {'error': e.message});
    } on FormatException {
      (code, out) = (400, {'error': 'niepoprawne żądanie'});
    } catch (e) {
      (code, out) = (500, {'error': 'błąd urządzenia'});
    }
    try {
      final data = utf8.encode(jsonEncode(out));
      r.response
        ..statusCode = code
        ..headers.contentType = ContentType.json
        ..headers.set('Connection', 'close')
        ..contentLength = data.length
        ..add(data);
      await r.response.close();
    } catch (_) {}
  }

  Future<Map<String, dynamic>> _json(HttpRequest r, [int max = 64 * 1024 * 1024]) async {
    final b = BytesBuilder(copy: false);
    await for (final c in r) {
      b.add(c);
      if (b.length > max) throw const FormatException('za duże');
    }
    if (b.isEmpty) return {};
    final d = jsonDecode(utf8.decode(b.takeBytes()));
    return d is Map ? Map<String, dynamic>.from(d) : {};
  }

  Future<(int, Map<String, dynamic>)> _route(HttpRequest r) async {
    final peer = _auth(r);
    final path = r.uri.path, m = r.method;
    final addr = r.connectionInfo?.remoteAddress.address ?? '';
    if (m == 'GET' && path == '/v1/info') return (200, info());
    if (m == 'POST' && path == '/v1/pair') return (200, _acceptPair(await _json(r, 65536), addr));
    if (m == 'PUT' && path.startsWith('/v1/files/')) return _receiveFile(r, path, peer, addr);
    if (m == 'POST' && path == '/v1/files') return _offer(r, peer, addr);
    if (peer == null) return (401, {'error': 'urządzenie nie jest sparowane'});
    if (peer.addr != addr) {
      peer.addr = addr;
      save();
    }
    if (m == 'POST' && path == '/v1/unpair') {
      peers.remove(peer.id);
      nearby[peer.id]?.token = null;
      save();
      h.onUnpaired(peer);
      return (200, <String, dynamic>{});
    }
    const feats = {
      'POST /v1/open': 'open', 'GET /v1/tabs': 'tabs', 'POST /v1/clip': 'clip', 'POST /v1/sync': 'sync',
      'POST /v1/remote': 'remote', 'POST /v1/notify': 'notify', 'POST /v1/approve': 'approve',
    };
    final feat = feats['$m $path'];
    if (feat == null) return (404, {'error': 'nieznane żądanie'});
    if (!h.allowed(feat, peer)) return (403, {'error': 'ta funkcja jest wyłączona na tym urządzeniu'});
    final d = m == 'POST' ? await _json(r) : <String, dynamic>{};
    switch (feat) {
      case 'open':
        final url = '${d['url'] ?? ''}';
        if (!RegExp(r'^https?://', caseSensitive: false).hasMatch(url)) return (400, {'error': 'można otwierać tylko adresy http(s)'});
        h.onOpen(peer, url, '${d['title'] ?? ''}');
      case 'tabs':
        return (200, {'tabs': h.tabs(peer)});
      case 'clip':
        h.onClip(peer, '${d['text'] ?? ''}');
      case 'sync':
        return (200, await h.onSync(peer, d));
      case 'remote':
        h.onRemote(peer, '${d['cmd'] ?? ''}', d['value']);
      case 'notify':
        h.onNotify(peer, _short('${d['title'] ?? ''}', 200), _short('${d['body'] ?? ''}', 1000), '${d['kind'] ?? ''}');
      case 'approve':
        return (200, {'ok': await h.onApprove(peer, '${d['what'] ?? ''}', '${d['detail'] ?? ''}')});
    }
    return (200, <String, dynamic>{});
  }

  Future<(int, Map<String, dynamic>)> _offer(HttpRequest r, Device? peer, String addr) async {
    if (!h.allowed(peer == null ? 'files_unpaired' : 'files', peer)) return (403, {'error': 'to urządzenie nie przyjmuje plików'});
    final d = await _json(r);
    final list = d['files'];
    if (list is! List || list.isEmpty || list.length > 1000) return (400, {'error': 'brak plików'});
    final files = [
      for (final f in list)
        FileOffer(safeName('${(f as Map)['name']}'), (f['size'] ?? 0) as int, '${f['sha256'] ?? ''}'.toLowerCase(), '${f['type'] ?? ''}')
    ];
    final sid = r.headers.value('x-luna-id') ?? '';
    final sender = peer ??
        Device(id: sid, name: nearby[sid]?.name ?? addr, type: nearby[sid]?.type ?? 'desktop', fp: nearby[sid]?.fp ?? '', addr: addr);
    final acc = (await h.offerFiles(sender, files)).where((i) => i >= 0 && i < files.length).toSet();
    if (acc.isEmpty) return (403, {'error': 'odbiorca odrzucił pliki'});
    final s = randomHex(12);
    _sessions[s] = _Session(files, acc, sender, peer?.id, addr);
    return (200, {'session': s, 'accept': acc.toList()..sort()});
  }

  Future<(int, Map<String, dynamic>)> _receiveFile(HttpRequest r, String path, Device? peer, String addr) async {
    final m = RegExp(r'^/v1/files/([0-9a-f]{24})/(\d+)$').firstMatch(path);
    final s = m == null ? null : _sessions[m.group(1)];
    if (s == null || s.until.isBefore(DateTime.now()) || s.addr != addr || (s.peer != null && peer?.id != s.peer)) {
      return (403, {'error': 'nieznana albo wygasła sesja'});
    }
    final i = int.parse(m!.group(2)!);
    if (!s.accept.remove(i)) return (403, {'error': 'ten plik nie został przyjęty'});
    final f = s.files[i];
    if (r.contentLength != f.size) return (400, {'error': 'zły rozmiar pliku'});
    final dir = Directory(await h.filesDir());
    await dir.create(recursive: true);
    final part = File('${dir.path}/.${randomHex(6)}.czesc');
    final sink = part.openWrite();
    final hs = _DigestSink();
    final hasher = crypto.sha256.startChunkedConversion(hs);
    var got = 0;
    try {
      await for (final c in r) {
        sink.add(c);
        hasher.add(c);
        got += c.length;
      }
      await sink.close();
      hasher.close();
      if (got != f.size) throw const FileSystemException('połączenie przerwane');
      if (f.sha256.isNotEmpty && hs.value.toString() != f.sha256) throw const FileSystemException('suma kontrolna się nie zgadza');
      final dest = uniqueFile(dir, f.name);
      await part.rename(dest.path);
      s.saved.add(dest);
      h.onFile(s.sender, dest, f);
      if (s.accept.isEmpty) {
        _sessions.remove(m.group(1));
        h.onFilesDone(s.sender, s.saved);
      }
      return (200, {'saved': dest.uri.pathSegments.last});
    } catch (e) {
      try {
        await sink.close();
      } catch (_) {}
      if (await part.exists()) await part.delete();
      return (400, {'error': 'plik odrzucony: ${e is FileSystemException ? e.message : e}'});
    }
  }
}

class _Session {
  final List<FileOffer> files;
  final Set<int> accept;
  final Device sender;
  final String? peer;
  final String addr;
  final DateTime until = DateTime.now().add(const Duration(hours: 1));
  final List<File> saved = [];
  _Session(this.files, this.accept, this.sender, this.peer, this.addr);
}

class _DigestSink implements Sink<crypto.Digest> {
  late crypto.Digest value;
  @override
  void add(crypto.Digest data) => value = data;
  @override
  void close() {}
}

String _short(String s, [int n = 60]) => s.length > n ? s.substring(0, n) : s;

String safeName(String name) {
  var n = name.split(RegExp(r'[/\\]')).last.replaceAll(RegExp(r'[\x00-\x1f<>:"|?*]'), '_').trim();
  while (n.startsWith('.')) {
    n = n.substring(1);
  }
  if (n.isEmpty) n = 'plik';
  return n.length > 180 ? n.substring(0, 180) : n;
}

File uniqueFile(Directory dir, String name) {
  var f = File('${dir.path}/$name');
  if (!f.existsSync()) return f;
  final dot = name.lastIndexOf('.');
  final stem = dot > 0 ? name.substring(0, dot) : name, ext = dot > 0 ? name.substring(dot) : '';
  for (var i = 2; i < 10000; i++) {
    f = File('${dir.path}/$stem ($i)$ext');
    if (!f.existsSync()) return f;
  }
  return File('${dir.path}/$stem (${randomHex(3)})$ext');
}
