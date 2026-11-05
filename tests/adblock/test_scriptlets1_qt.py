"""SCRIPTLETS-1 (network / data scriptlets) in a real QtWebEngine: MainWorld, DocumentCreation, built by
scriptlets.build(). Run: python -I tests/adblock/test_scriptlets1_qt.py      (needs PyQt6-WebEngine; ~20 s)

Hosts (local HTTP server, *.localhost):
  site-a.localhost  all scriptlets, no CSP
  site-b.localhost  same scriptlets, strict CSP (connect-src 'self', no unsafe-eval) + enforced Trusted Types
  site-d.localhost  noeval-silent only
  site-z.localhost  same page, no scriptlets (baseline for toString / names / globals)
  ads.localhost     "ad server": every request it receives is recorded (faked requests must never arrive)
A test scheme (like the glue's) serves R.SR + "r/<resource>" (resources.get) and "x/<spec>" (scriptlets.fake_body).
"""
import json
import os
import re
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
_TMP = tempfile.mkdtemp(prefix="luna-s1-test-")
os.environ["USERPROFILE"] = _TMP
os.environ["HOME"] = _TMP

from adblock import resources, scriptlets  # noqa: E402


def _watchdog(sec):
    def boom():
        print("WATCHDOG: %ss exceeded" % sec, flush=True)
        os._exit(3)
    t = threading.Timer(sec, boom)
    t.daemon = True
    t.start()


_watchdog(150)
FAILS, COUNT = [], [0]


def check(cond, label, extra=None):
    COUNT[0] += 1
    if not cond:
        FAILS.append(label)
        print("FAIL:", label, "" if extra is None else repr(extra)[:600], flush=True)


SCHEME = b"xs1test"
TOKEN = "tok123"
SR = "xs1test://l/%s/" % TOKEN

# ------------------------------------------------------------------ page
PAGE = r"""<!doctype html><html><head><meta charset=utf-8><title>t</title>
<script>
var T = {errs: 0, viol: 0, vlog: []};
window.onerror = function (m) { T.errs++; T.lastErr = String(m); };
document.addEventListener('securitypolicyviolation', function (e) { T.viol++; T.vlog.push(e.violatedDirective + '|' + e.blockedURI + '|' + e.sample); });
var TT = location.hostname.indexOf('site-b') === 0, EVAL = !TT;
var ADS = 'http://ads.localhost:' + location.port;
var JOBS = [];
function tst(name, f) {
  var p;
  try { p = Promise.resolve(f()); } catch (e) { p = Promise.reject(e); }
  JOBS.push(p.then(function (v) { T[name] = v; }, function (e) { T[name] = 'ERR ' + (e && e.name) + ': ' + (e && e.message); }));
}
function xhr(m, u, o) {
  o = o || {};
  return new Promise(function (res) {
    var r = new XMLHttpRequest(), ev = [];
    r.open(m, u, !o.sync);
    if (o.rt) r.responseType = o.rt;
    ['loadstart', 'progress', 'load', 'loadend', 'error'].forEach(function (k) { r.addEventListener(k, function (e) { ev.push(k + (e.isTrusted ? '' : '!')); }); });
    r.onreadystatechange = function () { ev.push('rs' + r.readyState); };
    r.send(o.body === undefined ? null : o.body);
    function fin() {
      res({st: r.status, stt: r.statusText, rt: r.responseType,
           text: (r.responseType === '' || r.responseType === 'text') ? r.responseText : null,
           resp: r.response, url: r.responseURL, ev: ev.join(','), hdr: r.getAllResponseHeaders(),
           acao: r.getResponseHeader('access-control-allow-origin'), ct: r.getResponseHeader('content-type'),
           xml: r.responseType === '' || r.responseType === 'document' ? r.responseXML : null});
    }
    if (o.sync) fin(); else r.addEventListener('loadend', fin);
  });
}
function resp(r) {
  return r.text().then(function (t) {
    return {st: r.status, stt: r.statusText, ok: r.ok, type: r.type, url: r.url, red: r.redirected,
            ct: r.headers.get('content-type'), cl: r.headers.get('content-length'), text: t,
            own: Reflect.ownKeys(r).length};
  });
}
</script>
<div class=edx id=edx1 data-ad=1 data-ok=1></div>
<script>
// ---------------- prevent-fetch
tst('pf_empty', function () { var u = ADS + '/pagead/js/adsbygoogle.js'; return fetch(u).then(function (r) { var c = r.clone(); return resp(r).then(function (o) { o.cloneUrl = c.url; o.cloneType = c.type; o.expUrl = u; return o; }); }); });
tst('pf_war', function () { return fetch(ADS + '/warprobe/x.js').then(resp); });
tst('pf_opaque', function () { return fetch(ADS + '/adsbygoogle-op', {mode: 'no-cors'}).then(resp); });
tst('pf_head', function () { return fetch(ADS + '/adsbygoogle.js', {method: 'HEAD'}).then(resp); });
tst('pf_same', function () { return fetch('/sameorigin-adsbygoogle').then(resp); });
tst('pf_req', function () { return fetch(new Request(ADS + '/x/adsbygoogle')).then(resp); });
tst('pf_abort', function () { return fetch(ADS + '/adsbygoogle', {signal: AbortSignal.abort()}).then(resp); });
tst('pf_json', function () { return fetch(ADS + '/emptyprobe').then(function (r) { return r.json().then(function (j) { return [JSON.stringify(j), r.headers.get('content-type')]; }); }); });
tst('pf_len', function () { return fetch(ADS + '/lenprobe').then(function (r) { return r.text(); }).then(function (t) { return [t.length, /^[A-Za-z0-9]*$/.test(t)]; }); });
tst('pf_trusted', function () { return fetch(ADS + '/literalprobe').then(function (r) { return r.text().then(function (t) { return [r.status, t, r.headers.get('x-a')]; }); }); });
tst('pf_untlit', function () { return fetch(ADS + '/untlit').then(function (r) { return r.text(); }); });
tst('pf_throttle', function () { var t0 = performance.now(); return fetch(ADS + '/throttleprobe').then(function () { return performance.now() - t0; }); });
tst('pf_pass', function () { return fetch('/plain').then(function (r) { return r.text().then(function (t) { return [t, r.type, r.url.slice(-6)]; }); }); });
tst('pf_opq2', function () { return fetch('/opq2').then(function (r) { return [r.type, r.status, r.ok]; }); });
tst('pf_untrusted_trusted', function () { return fetch('/plain?tru').then(function (r) { return r.text(); }); });
// ---------------- prevent-xhr
function xs(o) { return {st: o.st, stt: o.stt, text: o.text, url: o.url, ev: o.ev, hdr: o.hdr, acao: o.acao, ct: o.ct}; }
tst('px_empty', function () { return xhr('GET', ADS + '/adsbygoogle.js').then(xs); });
tst('px_war', function () { return xhr('GET', ADS + '/vastprobe').then(function (o) { return [o.st, o.text.indexOf('<VAST version="3.0">') !== -1, o.xml && o.xml.documentElement.nodeName, o.ct, o.url]; }); });
tst('px_doc', function () { return xhr('GET', ADS + '/vastprobe2', {rt: 'document'}).then(function (o) { return [o.st, o.resp && o.resp.documentElement.nodeName]; }); });
tst('px_post', function () { return xhr('POST', ADS + '/xhrpost', {body: 'a=1'}).then(xs); });
tst('px_post_get', function () { return xhr('GET', '/plain?xhrpost').then(function (o) { return o.text; }); });
tst('px_sync', function () { return xhr('GET', ADS + '/adsbygoogle-sync', {sync: 1}).then(xs); });
tst('px_json', function () { return xhr('GET', ADS + '/jsonprobe', {rt: 'json'}).then(function (o) { return [o.st, JSON.stringify(o.resp)]; }); });
tst('px_trusted', function () { return xhr('GET', ADS + '/literalx').then(function (o) { return o.text; }); });
tst('px_len', function () { return xhr('GET', ADS + '/lenx').then(function (o) { return o.text; }); });
tst('px_real_empty', function () { return xhr('GET', '/emptybody').then(function (o) { return o.ev; }); });
tst('px_pass', function () { return xhr('GET', '/plain').then(function (o) { return [o.text, o.url.slice(-6)]; }); });
// ---------------- json-prune
tst('jp1', function () { return JSON.stringify(JSON.parse('{"ads":1,"k":2}')); });
tst('jp_needle', function () { return [JSON.stringify(JSON.parse('{"a":{"b":1}}')), JSON.stringify(JSON.parse('{"a":{"b":1},"needle":0}'))]; });
tst('jp_arr', function () { return JSON.stringify(JSON.parse('{"entries":[{"isAd":0},{"x":1}]}')); });
tst('jp_star', function () { return [JSON.stringify(JSON.parse('{"showTrkURL":1,"z":2}')), JSON.stringify(JSON.parse('{"z":2}'))]; });
function stackFn() { return JSON.parse('{"stkprop":1,"o":1}'); }
tst('jp_stack', function () { return [JSON.stringify(stackFn()), JSON.stringify(JSON.parse('{"stkprop":1}'))]; });
tst('jp_rjson', function () { return fetch('/data.json').then(function (r) { return r.json(); }).then(function (j) { return JSON.stringify(j); }); });
// ---------------- *-response
tst('jpf', function () { return fetch('/api/feed').then(resp); });
tst('jpf_other', function () { return fetch('/api/other').then(function (r) { return r.text(); }); });
tst('jpx', function () { return xhr('GET', '/api/xfeed').then(function (o) { return [o.text, o.resp, o.url.slice(-10)]; }); });
tst('jpx_json', function () { return xhr('GET', '/api/xfeed', {rt: 'json'}).then(function (o) { return JSON.stringify(o.resp); }); });
tst('jsonl_f', function () { return fetch('/api/lines').then(function (r) { return r.text(); }); });
tst('jsonl_x', function () { return xhr('GET', '/xlines').then(function (o) { return o.text; }); });
tst('rpfr', function () { return fetch('/player').then(function (r) { return r.text(); }); });
tst('rpxr', function () { return xhr('GET', '/vastx').then(function (o) { return o.text; }); });
tst('xml_f', function () { return fetch('/vast.xml').then(function (r) { return r.text(); }); });
tst('xml_x', function () { return xhr('GET', '/vast2.xml', {rt: 'document'}).then(function (o) { return [o.resp.querySelectorAll('Ad').length, o.resp.querySelectorAll('Creative').length]; }); });
tst('xml_xt', function () { return xhr('GET', '/vast2.xml').then(function (o) { return [o.text.indexOf('<Ad') === -1, o.xml ? o.xml.querySelectorAll('Ad').length : -1]; }); });
tst('xml_attr', function () { return fetch('/a.mpd').then(function (r) { return r.text(); }); });
tst('xml_check', function () { return fetch('/vast3.xml').then(function (r) { return r.text(); }); });
tst('m3u_line', function () { return fetch('/list.m3u8').then(function (r) { return r.text(); }); });
tst('m3u_whole', function () { return xhr('GET', '/whole.m3u8').then(function (o) { return o.text; }); });
// ---------------- edits
tst('jefr', function () { return fetch('/echo', {method: 'POST', body: '{"tracking":1,"q":2}'}).then(function (r) { return r.text(); }); });
tst('jefr_req', function () { return fetch(new Request('/echo2', {method: 'POST', body: '{"tracking":1,"q":3}'})).then(function (r) { return r.text(); }); });
tst('jexr', function () { return xhr('POST', '/xecho', {body: '{"tracking":1,"q":4}'}).then(function (o) { return o.text; }); });
tst('tjef', function () { return fetch('/play').then(function (r) { return r.json(); }).then(function (j) { return JSON.stringify(j); }); });
tst('ti', function () { return JSON.stringify({drop: 1, keep: 2, secret: 3}); });
tst('to', function () { return Object.keys(Object.getOwnPropertyDescriptors({zzprobe: 1, b: 2})).join(); });
tst('je', function () { return JSON.stringify(JSON.parse('{"a":{"isAd":true,"x":1},"b":[{"isAd":1}]}')); });
tst('je_f', function () { return JSON.stringify(JSON.parse('{"items":[{"sponsored":true},{"sponsored":false}]}')); });
tst('tje', function () { return JSON.stringify(JSON.parse('{"cfg":{"allowAdblock":false}}')); });
tst('je_ua', function () { return JSON.stringify(JSON.parse('{"allowX":false}')); });
tst('je_m', function () { return [JSON.stringify(JSON.parse('{"mx":1}')), JSON.stringify(JSON.parse('{"mx":1,"pad":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'))]; });
tst('eo', function () { return JSON.stringify(Object.fromEntries([['bad', 1], ['ok', 2]])); });
tst('et', function () { return JSON.stringify([{ad: 1}, {b: 2}].reverse()); });
window.initials = [{advertiser: 1}, {b: 1}];
tst('eos', function () { return JSON.stringify(initials); });
window.gcfg = {ads: 1, k: 1};
tst('eog', function () { return JSON.stringify(gcfg); });
var dyn = document.createElement('div'); dyn.className = 'edx'; dyn.setAttribute('data-ad', '2'); document.head.appendChild(dyn);
tst('ee', function () { return new Promise(function (res) { setTimeout(function () { res([document.getElementById('edx1').hasAttribute('data-ad'), document.getElementById('edx1').hasAttribute('data-ok'), dyn.hasAttribute('data-ad')]); }, 50); }); });
// ---------------- eval family
if (EVAL) {
  tst('nei', function () { return [eval('1+1'), String(eval('var adblockcheck=1; 5'))]; });
  tst('edp', function () { return JSON.stringify(eval('({"adx":1,"k":2})')); });
}
// ---------------- nowebrtc
tst('rtc', function () {
  var pc = new RTCPeerConnection({iceServers: [{urls: 'stun:stun.example.org'}]});
  var st = 'pending'; pc.createOffer().then(function () { st = 'resolved'; }, function () { st = 'rejected'; });
  var dc = pc.createDataChannel('chan');
  var f = function () {}; pc.onicecandidate = f;
  var plain; try { RTCPeerConnection(); plain = 'no throw'; } catch (e) { plain = e.name; }
  var out = [pc instanceof RTCPeerConnection, pc.constructor === RTCPeerConnection, Object.prototype.toString.call(pc),
             pc.signalingState, pc.localDescription, pc.iceConnectionState, dc instanceof RTCDataChannel, dc.readyState, dc.label,
             pc.onicecandidate === f, plain, pc instanceof EventTarget, typeof pc.addEventListener, pc.getSenders().length,
             Reflect.ownKeys(pc).length];
  pc.close(); dc.close(); out.push(dc.readyState);
  return new Promise(function (res) { setTimeout(function () { out.push(st); res(out); }, 300); });
});
</script>
<script>
addEventListener('load', function () { setTimeout(function () {
  var F = Function.prototype.toString, D = function (o, p) { return Object.getOwnPropertyDescriptor(o, p); };
  T.ts = [F.call(fetch), F.call(XMLHttpRequest.prototype.open), F.call(XMLHttpRequest.prototype.send), F.call(JSON.parse),
          F.call(JSON.stringify), F.call(Response.prototype.json), F.call(Response.prototype.clone), F.call(D(Response.prototype, 'url').get),
          F.call(D(Response.prototype, 'type').get), F.call(D(XMLHttpRequest.prototype, 'responseURL').get),
          F.call(D(XMLHttpRequest.prototype, 'response').get), F.call(XMLHttpRequest.prototype.getAllResponseHeaders),
          F.call(eval), F.call(RTCPeerConnection), F.call(RTCPeerConnection.prototype.createOffer),
          F.call(D(RTCPeerConnection.prototype, 'signalingState').get), F.call(Object.fromEntries), F.call(Array.prototype.reverse),
          F.call(D(window, 'initials').get || function initials() {})];
  T.names = [fetch.name, fetch.length, XMLHttpRequest.prototype.open.name, XMLHttpRequest.prototype.open.length,
             JSON.parse.name, JSON.parse.length, D(Response.prototype, 'url').get.name, eval.name, eval.length,
             RTCPeerConnection.name, RTCPeerConnection.length, JSON.stringify(Reflect.ownKeys(fetch)),
             JSON.stringify(D(window, 'fetch'), function (k, v) { return typeof v === 'function' ? 'fn' : v; }),
             JSON.stringify(Object.keys(D(Response.prototype, 'url'))), RTCPeerConnection.prototype === Object.getPrototypeOf(new RTCPeerConnection()),
             new Response('x').type, new Response('x').url, new Response('x').statusText, Reflect.ownKeys(new Response('x')).length];
  try { fetch.call({}, ADS + '/adsbygoogle').catch(function (e) { T.fetchIllegal = e.message; }); T.names.push('no throw'); } catch (e) { T.names.push(e.name + ': ' + e.message); }
  try { XMLHttpRequest.prototype.open.call({}, 'GET', '/x'); T.names.push('no throw'); } catch (e) { T.names.push(e.name + ': ' + e.message); }
  try { D(Response.prototype, 'url').get.call({}); T.names.push('no throw'); } catch (e) { T.names.push(e.name + ': ' + e.message); }
  try { JSON.parse('{bad'); } catch (e) { T.names.push(e.name + ': ' + e.message); }
  T.globals = Object.getOwnPropertyNames(window);
  var fr = document.createElement('iframe'); document.body.appendChild(fr);
  tst('child_realm', function () { var cw = fr.contentWindow; return cw.fetch(ADS + '/adsbygoogle-child').then(function (r) { return [r.status, r.type, F.call(cw.fetch), cw.JSON.stringify(cw.JSON.parse('{"ads":1,"k":2}'))]; }); });
  Promise.all(JOBS).then(function () { setTimeout(function () { T.done = true; }, 400); });
}, 0); });
</script>
</head><body></body></html>
"""

CSP = ("require-trusted-types-for 'script'; trusted-types pp; script-src 'self' 'unsafe-inline'; "
       "connect-src 'self'; object-src 'self'; report-uri /csp-report")

VAST = '<?xml version="1.0" encoding="UTF-8"?>\n<VAST version="3.0"><Ad id="1"><InLine><Creative/></InLine></Ad><Ad id="2"/></VAST>'
ROUTES = {
    "/plain": ("text/plain", "real-body"),
    "/emptybody": ("text/plain", ""),
    "/api/feed": ("application/json", '{"adverts":[1,2],"items":[1],"banner":"x"}'),
    "/api/other": ("application/json", '{"adverts":[1]}'),
    "/api/xfeed": ("application/json", '{"adverts":[1,2],"items":[1],"banner":"x"}'),
    "/api/lines": ("application/x-ndjson", '{"ad":1,"k":1}\n{"k":2}\n'),
    "/xlines": ("application/x-ndjson", '{"ad":1,"k":1}\n{"k":2}\n'),
    "/player": ("text/plain", 'A "adPlacements" B "adPlacements" C'),
    "/vastx": ("text/xml", '<VAST version="3.0"><Ad id="1"></Ad></VAST>'),
    "/vast.xml": ("application/xml", VAST),
    "/vast2.xml": ("application/xml", VAST),
    "/vast3.xml": ("application/xml", VAST),
    "/a.mpd": ("application/dash+xml", '<MPD mediaPresentationDuration="PT1M" x="1"><Period id="p"/></MPD>'),
    "/list.m3u8": ("application/vnd.apple.mpegurl",
                   "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:6\n#EXTINF:6,\nseg1.ts\n"
                   "#EXT-X-DISCONTINUITY\n#EXTINF:6,\nhttps://x.test/adsegment1.ts\n#EXTINF:6,\nseg2.ts\n#EXT-X-ENDLIST\n"),
    "/whole.m3u8": ("application/vnd.apple.mpegurl",
                    "#EXTM3U\n#EXTINF:6,\nseg1.ts\n#EXT-X-CUE-OUT:30\n#EXTINF:6,\nad1.ts\n#EXT-X-CUE-IN\n#EXTINF:6,\nseg2.ts\n"),
    "/data.json": ("application/json", '{"ads":[1],"keep":1}'),
    "/play": ("application/json", '{"result":{"PlayAds":true,"k":1}}'),
}
REPORTS, HITS = [], []


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=()):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(b)

    def _host(self):
        return (self.headers.get("Host") or "").split(":")[0]

    def _route(self, body=b""):
        host, path = self._host(), self.path
        if host.startswith("ads.") or "adsbygoogle" in path or "opq2" in path:
            HITS.append((self._host_page(), self.command, host + path))
            return self._send(200, "REAL", "text/plain", [("Access-Control-Allow-Origin", "*")])
        if path.startswith("/csp-report"):
            REPORTS.append(body.decode("utf-8", "replace")[:500])
            return self._send(204, "")
        if path in ("/echo", "/echo2", "/xecho"):
            return self._send(200, body, "application/json")
        if path.startswith("/t.html"):
            extra = [("Content-Security-Policy", CSP)] if host.startswith("site-b") else []
            return self._send(200, PAGE, extra=extra)
        r = ROUTES.get(path.split("?")[0])
        if r:
            return self._send(200, r[1], r[0])
        self._send(404, "nf", "text/plain")

    def _host_page(self):
        ref = self.headers.get("Referer") or self.headers.get("Origin") or ""
        m = re.match(r"https?://([^/:]+)", ref)
        return m.group(1) if m else "?"

    def do_GET(self):
        self._route()

    def do_HEAD(self):
        self._route()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self._route(self.rfile.read(n) if n else b"")


R_ALL = [
    # prevent-fetch / trusted
    ("no-fetch-if", ["adsbygoogle"], False),
    ("no-fetch-if", ["warprobe", "war:googlesyndication_adsbygoogle.js"], False),
    ("prevent-fetch", ["emptyprobe", "emptyObj"], False),
    ("no-fetch-if", ["lenprobe", "length:100-200"], False),
    ("trusted-prevent-fetch", ["literalprobe", "hello world", '{"headers":{"x-a":"1"},"status":201}'], True),
    ("no-fetch-if", ["untlit", "hello"], False),
    ("no-fetch-if", ["throttleprobe", "", "", "throttle", "300"], False),
    ("no-fetch-if", ["opq2", "", "opaque"], False),
    ("trusted-prevent-fetch", ["plain?tru", "zzz"], False),          # trusted-only from untrusted list: dropped
    ("no-fetch-if", [""], False),                                     # log-only form: inert
    # prevent-xhr / trusted
    ("no-xhr-if", ["adsbygoogle"], False),
    ("no-xhr-if", ["vastprobe", "war:noop-vast3.xml"], False),
    ("no-xhr-if", ["method:POST xhrpost"], False),
    ("no-xhr-if", ["jsonprobe", "emptyObj"], False),
    ("trusted-prevent-xhr", ["literalx", 'a.getAttribute("data-ad-client")||""'], True),
    ("no-xhr-if", ["lenx", "length:10"], False),
    # json-prune
    ("json-prune", ["ads"], False),
    ("json-prune", ["a.b", "needle"], False),
    ("json-prune", ["entries.[-].isAd"], False),
    ("json-prune", ["*", "showTrkURL"], False),
    ("json-prune", ["stkprop", "", "stackFn"], False),
    # response editors
    ("json-prune-fetch-response", ["adverts", "", "propsToMatch", "/api/feed"], False),
    ("json-edit-fetch-response", [".banner", "propsToMatch", "/api/feed"], False),
    ("json-prune-xhr-response", ["adverts", "", "propsToMatch", "/api/xfeed"], False),
    ("json-edit-xhr-response", [".banner", "propsToMatch", "/api/xfeed"], False),
    ("jsonl-prune-fetch-response", ["ad", "", "propsToMatch", "/api/lines"], False),
    ("jsonl-edit-xhr-response", [".ad", "propsToMatch", "/xlines"], False),
    ("trusted-rpfr", ['"adPlacements"', '"no_ads"', "/player"], True),
    ("trusted-replace-xhr-response", ["/<VAST version.+VAST>/", '<VAST version="4.0"></VAST>', "/vastx"], True),
    ("xml-prune", ["VAST > Ad", "", "/vast"], False),
    ("xml-prune", ['xpath(//*[name()="MPD"]/@mediaPresentationDuration)', "", ".mpd"], False),
    ("xml-prune", ["Period", "Nope", ".mpd"], False),                 # checkSelector absent -> untouched
    ("m3u-prune", ["adsegment", "list.m3u8"], False),
    ("m3u-prune", [r"/^#EXT-X-CUE-OUT[\s\S]*?#EXT-X-CUE-IN\n/m", "whole.m3u8"], False),
    # request editors
    ("json-edit-fetch-request", [".tracking", "propsToMatch", "/echo"], False),
    ("json-edit-xhr-request", [".tracking", "propsToMatch", "/xecho"], False),
    ("trusted-json-edit-fetch-response", [".result.PlayAds=false", "propsToMatch", "/play"], True),
    # object editors
    ("trusted-prune-inbound-object", ["JSON.stringify", "1", "secret"], True),
    ("edit-inbound-object", ["JSON.stringify", "0", ".drop"], False),
    ("trusted-prune-outbound-object", ["Object.getOwnPropertyDescriptors", "zzprobe"], True),
    ("json-edit", ["..isAd"], False),
    ("json-edit", [".items.*[?.sponsored==true]"], False),
    ("trusted-json-edit", ["..allowAdblock=true"], True),
    ("json-edit", ["..allowX=true"], False),                          # assignment from untrusted list: inert
    ("json-edit", [".mx", "matches", "/^.{30,}/"], False),
    ("edit-outbound-object", ["Object.fromEntries", ".bad"], False),
    ("edit-this-object", ["Array.prototype.reverse", ".*[?.ad]"], False),
    ("edit-element-object", ["div.edx", ".dataset.ad"], False),
    ("edit-object-on-setter", ["initials", ".*[?.advertiser]"], False),
    ("edit-object-on-getter", ["gcfg", ".ads"], False),
    # eval family / webrtc
    ("noeval-if", ["adblockcheck"], False),
    ("evaldata-prune", ["adx"], False),
    ("nowebrtc", [], False),
]
R_D = [("noeval-silent", [], False)]
# no scheme (R.SR == ""): XHR fakes fall back to data: URLs, xml-prune to DOMParser
R_E = [("no-xhr-if", ["adsbygoogle", "emptyObj"], False), ("no-fetch-if", ["warprobe", "war:noop.json"], False),
       ("xml-prune", ["Ad", "", "/vast"], False)]
E_PAGE = r"""<!doctype html><script>
var E = {};
var r = new XMLHttpRequest(); r.open('GET', 'http://ads.localhost:' + location.port + '/adsbygoogle.js');
r.onload = function () { E.x = [r.status, r.responseText, r.responseURL.slice(0, 20)]; };
r.send();
fetch('http://ads.localhost:' + location.port + '/warprobe').then(function (x) { return x.text(); }).then(function (t) { E.f = t; });
fetch('/vast.xml').then(function (x) { return x.text(); }).then(function (t) { E.v = t.indexOf('<Ad') === -1; });
</script>"""


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    from PyQt6.QtCore import QBuffer, QByteArray, QEventLoop, QTimer, QUrl
    from PyQt6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile, QWebEngineScript, QWebEngineUrlRequestJob,
                                       QWebEngineUrlScheme, QWebEngineUrlSchemeHandler)
    sc = QWebEngineUrlScheme(SCHEME)
    sc.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    F = QWebEngineUrlScheme.Flag
    sc.setFlags(F.SecureScheme | F.ContentSecurityPolicyIgnored | F.CorsEnabled | F.FetchApiAllowed)
    QWebEngineUrlScheme.registerScheme(sc)
    from PyQt6.QtWidgets import QApplication
    app = QApplication([sys.argv[0], "--webEngineArgs", "--disable-gpu"])
    SCHEME_HITS = []

    class SH(QWebEngineUrlSchemeHandler):   # the glue's handler, reduced to r/ and x/
        def requestStarted(self, job):
            try:
                path = job.requestUrl().path()
                method = bytes(job.requestMethod()).decode()
                SCHEME_HITS.append((method, path[:60]))
                pre = "/%s/" % TOKEN
                res = None
                if path.startswith(pre + "r/"):
                    res = resources.get(QUrl.fromPercentEncoding(path[len(pre) + 2:].encode()))
                    if res and method == "HEAD":
                        res = (res[0], b"")
                elif path.startswith(pre + "x/"):
                    res = scriptlets.fake_body(path[len(pre) + 2:], method)
                if res is None:
                    job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                    return
                buf = QBuffer(parent=job)
                buf.setData(QByteArray(res[1]))
                buf.open(QBuffer.OpenModeFlag.ReadOnly)
                job.setAdditionalResponseHeaders({QByteArray(b"Access-Control-Allow-Origin"): QByteArray(b"*")})
                job.reply(res[0].encode(), buf)
            except Exception as e:  # noqa: BLE001
                print("HANDLER ERROR", e, flush=True)
                job.fail(QWebEngineUrlRequestJob.Error.RequestFailed)

    class Page(QWebEnginePage):
        def __init__(self, prof):
            super().__init__(prof)
            self.console = []

        def javaScriptConsoleMessage(self, level, msg, line, src):
            self.console.append((msg[:300], src[-60:] if src else "", line))

    def pump(ms):
        loop = QEventLoop()
        QTimer.singleShot(int(ms), loop.quit)
        loop.exec()

    def run_js(page, code, timeout=10.0):
        loop = QEventLoop()
        box = {}

        def cb(v):
            box["v"] = v
            loop.quit()
        page.runJavaScript(code, 0, cb)
        QTimer.singleShot(int(timeout * 1000), loop.quit)
        if "v" not in box:
            loop.exec()
        return box.get("v")

    scriptlets.configure(sr=SR)
    bundle = scriptlets.build(R_ALL, "site-a.localhost")
    check(bundle is not None, "bundle built")
    for nm in ("lib-net", "lib-json"):
        check(bundle.count('"%s":' % nm) <= 1, "dep %s mapped once" % nm)
    check("console" not in bundle and "debugger" not in bundle, "no console/debugger in bundle")
    check("trusted-prevent-fetch" not in bundle or bundle.count('"plain?tru"') == 0, "trusted-only rule dropped")
    print("bundle: %d bytes, %d invocations" % (len(bundle), bundle.count("try{a")), flush=True)
    prof = QWebEngineProfile()   # off-the-record
    sh = SH(prof)
    prof.installUrlSchemeHandler(SCHEME, sh)
    for host, b in (("site-a.localhost", bundle), ("site-b.localhost", bundle),
                    ("site-d.localhost", scriptlets.build(R_D, "site-d.localhost")),
                    ("site-e.localhost", scriptlets.build(R_E, "site-e.localhost", sr=""))):
        s = QWebEngineScript()
        s.setName("")
        s.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        s.setRunsOnSubFrames(True)
        s.setSourceCode('if(location.hostname==="%s"){%s}\n//# sourceURL=<anonymous>' % (host, b))
        prof.scripts().insert(s)

    results = {}
    for host in ("site-z.localhost", "site-a.localhost", "site-b.localhost"):
        del HITS[:]
        page = Page(prof)
        loop = QEventLoop()
        page.loadFinished.connect(lambda ok: loop.quit())
        page.load(QUrl("http://%s:%d/t.html" % (host, port)))
        QTimer.singleShot(15000, loop.quit)
        loop.exec()
        end = time.time() + 20
        val = None
        while time.time() < end:
            v = run_js(page, "window.T && T.done ? JSON.stringify(T) : ''")
            if v:
                val = json.loads(v)
                break
            pump(100)
        if val is None:
            print("PARTIAL", host, run_js(page, "JSON.stringify([document.readyState, window.T || null])"),
                  page.console[:10], flush=True)
        check(val is not None, host + ": page finished")
        results[host] = (val or {}, list(page.console), list(HITS))
        page.deleteLater()
        pump(50)

    base = results["site-z.localhost"][0]
    for host in ("site-a.localhost", "site-b.localhost"):
        T, console, hits = results[host]
        tt = host.startswith("site-b")
        tag = host + ": "

        def eq(key, exp):
            check(T.get(key) == exp, tag + key, T.get(key))
        # ---- prevent-fetch
        o = T.get("pf_empty") or {}
        check(isinstance(o, dict) and [o.get(k) for k in ("st", "stt", "ok", "type", "red", "ct", "cl", "text", "own")] ==
              [200, "OK", True, "cors", False, "text/plain", "0", "", 0], tag + "no-fetch-if response shape", o)
        check(isinstance(o, dict) and o.get("url") == o.get("expUrl") and o.get("cloneUrl") == o.get("expUrl") and
              o.get("cloneType") == "cors", tag + "masked url/type (and on clone)", o)
        o = T.get("pf_war") or {}
        check(isinstance(o, dict) and o.get("st") == 200 and "adsbygoogle" in (o.get("text") or "") and
              o.get("ct") == "application/javascript" and o.get("cl") == str(len((o.get("text") or "").encode())),
              tag + "war: body", {k: (v if k != "text" else (v or "")[:80]) for k, v in (o.items() if isinstance(o, dict) else [])})
        o = T.get("pf_opaque") or {}
        check(isinstance(o, dict) and [o.get(k) for k in ("type", "st", "ok", "stt", "url", "text", "ct")] ==
              ["opaque", 0, False, "", "", "", None], tag + "no-cors cross-origin -> opaque", o)
        o = T.get("pf_head") or {}
        check(isinstance(o, dict) and o.get("st") == 200 and o.get("text") == "", tag + "HEAD", o)
        o = T.get("pf_same") or {}
        check(isinstance(o, dict) and o.get("type") == "basic" and (o.get("url") or "").endswith("/sameorigin-adsbygoogle"),
              tag + "same-origin -> basic", o)
        check((T.get("pf_req") or {}).get("st") == 200, tag + "Request object", T.get("pf_req"))
        eq("pf_abort", "ERR AbortError: signal is aborted without reason")
        eq("pf_json", ["{}", "application/json"])
        v = T.get("pf_len") or [0, False]
        check(100 <= v[0] <= 200 and v[1] is True, tag + "length:100-200", v)
        eq("pf_trusted", [201, "hello world", "1"])
        eq("pf_untlit", "")
        check(isinstance(T.get("pf_throttle"), (int, float)) and T["pf_throttle"] >= 280, tag + "throttle", T.get("pf_throttle"))
        eq("pf_pass", ["real-body", "basic", "/plain"])
        eq("pf_opq2", ["opaque", 0, False])
        eq("pf_untrusted_trusted", "real-body")
        # ---- prevent-xhr
        o = T.get("px_empty") or {}
        check(isinstance(o, dict) and o.get("st") == 200 and o.get("stt") == "OK" and o.get("text") == "" and
              o.get("url") == "http://ads.localhost:%d/adsbygoogle.js" % port and
              o.get("ev") == T.get("px_real_empty") == "loadstart,rs2,rs4,load,loadend" and "access-control" not in (o.get("hdr") or "") and
              o.get("acao") is None and o.get("ct") == "text/plain", tag + "no-xhr-if genuine load, masked", o)
        v = T.get("px_war") or []
        check(v[:4] == [200, True, "VAST", "application/xml"] and v[4] == "http://ads.localhost:%d/vastprobe" % port,
              tag + "xhr war:noop-vast3.xml", v)
        eq("px_doc", [200, "VAST"])
        o = T.get("px_post") or {}
        check(isinstance(o, dict) and o.get("st") == 200 and o.get("text") == "", tag + "xhr POST faked", o)
        eq("px_post_get", "real-body")
        o = T.get("px_sync") or {}
        check(isinstance(o, dict) and o.get("st") == 200 and o.get("ev") == "rs4,load,loadend", tag + "sync xhr", o)
        eq("px_json", [200, "{}"])
        eq("px_trusted", 'a.getAttribute("data-ad-client")||""')
        v = T.get("px_len")
        check(isinstance(v, str) and len(v) == 10 and v.isalnum(), tag + "xhr length:10", v)
        eq("px_pass", ["real-body", "/plain"])
        # ---- json-prune
        eq("jp1", '{"k":2}')
        eq("jp_needle", ['{"a":{"b":1}}', '{"a":{},"needle":0}'])
        eq("jp_arr", '{"entries":[{"x":1}]}')
        eq("jp_star", ['{}', '{"z":2}'])
        eq("jp_stack", ['{"o":1}', '{"stkprop":1}'])
        eq("jp_rjson", '{"keep":1}')
        o = T.get("jpf") or {}
        check(isinstance(o, dict) and [o.get(k) for k in ("st", "stt", "ok", "type", "red", "ct", "text", "own")] ==
              [200, "OK", True, "basic", False, "application/json", '{"items":[1]}', 0] and
              (o.get("url") or "").endswith("/api/feed"), tag + "json-prune-fetch-response + json-edit-fetch-response", o)
        eq("jpf_other", '{"adverts":[1]}')
        v = T.get("jpx") or []
        check(v[:2] == ['{"items":[1]}', '{"items":[1]}'] and v[2:] == ["/api/xfeed"], tag + "json-prune-xhr-response text", v)
        eq("jpx_json", '{"items":[1]}')
        eq("jsonl_f", '{"k":1}\n{"k":2}\n')
        eq("jsonl_x", '{"k":1}\n{"k":2}\n')
        eq("rpfr", 'A "no_ads" B "no_ads" C')
        eq("rpxr", '<VAST version="4.0"></VAST>')
        v = T.get("xml_f") or ""
        check(isinstance(v, str) and v.startswith('<?xml version="1.0" encoding="UTF-8"?>') and "<Ad" not in v and
              '<VAST version="3.0"' in v, tag + "xml-prune fetch", v)
        eq("xml_x", [0, 0])
        eq("xml_xt", [True, 0])
        v = T.get("xml_attr") or ""
        check(isinstance(v, str) and "mediaPresentationDuration" not in v and 'x="1"' in v and "<Period" in v,
              tag + "xml-prune xpath attribute", v)
        v = T.get("xml_check")
        check(isinstance(v, str) and "<Ad" not in v, tag + "xml-prune /vast matches vast3 too", v)
        eq("m3u_line", "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:6\n#EXTINF:6,\nseg1.ts\n#EXTINF:6,\nseg2.ts\n#EXT-X-ENDLIST\n")
        eq("m3u_whole", "#EXTM3U\n#EXTINF:6,\nseg1.ts\n#EXTINF:6,\nseg2.ts\n")
        # ---- edits
        eq("jefr", '{"q":2}')
        eq("jefr_req", '{"q":3}')
        eq("jexr", '{"q":4}')
        eq("tjef", '{"result":{"PlayAds":false,"k":1}}')
        eq("ti", '{"keep":2}')
        eq("to", "b")
        eq("je", '{"a":{"x":1},"b":[{}]}')
        eq("je_f", '{"items":[{"sponsored":false}]}')
        eq("tje", '{"cfg":{"allowAdblock":true}}')
        eq("je_ua", '{"allowX":false}')
        eq("je_m", ['{"mx":1}', '{"pad":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'])
        eq("eo", '{"ok":2}')
        eq("et", '[{"b":2}]')
        eq("eos", '[{"b":1}]')
        eq("eog", '{"k":1}')
        eq("ee", [False, True, False])
        if not tt:
            eq("nei", [2, "undefined"])
            eq("edp", '{"k":2}')
        v = T.get("rtc") or []
        check(v == [True, True, "[object RTCPeerConnection]", "stable", None, "new", True, "connecting", "chan", True,
                    "TypeError", True, "function", 0, 0, "closed", "pending"], tag + "nowebrtc inert peer connection", v)
        eq("child_realm", [200, "cors", "function fetch() { [native code] }", '{"k":2}'])
        # ---- network: nothing faked reached the server
        check(not hits, tag + "faked requests never reached the network", hits)
        # ---- stealth
        nat = lambda nm: "function %s() { [native code] }" % nm
        exp_ts = [nat("fetch"), nat("open"), nat("send"), nat("parse"), nat("stringify"), nat("json"), nat("clone"),
                  nat("get url"), nat("get type"), nat("get responseURL"), nat("get response"),
                  nat("getAllResponseHeaders"), nat("eval"), nat("RTCPeerConnection"), nat("createOffer"),
                  nat("get signalingState"), nat("fromEntries"), nat("reverse")]
        check((T.get("ts") or [])[:-1] == exp_ts and (T.get("ts") or [])[:-1] == (base.get("ts") or [])[:-1],
              tag + "toString native", T.get("ts"))
        check((T.get("ts") or [""])[-1] == "function get initials() { [native code] }", tag + "trap getter native",
              (T.get("ts") or [""])[-1])
        check(T.get("names") == base.get("names"), tag + "name/length/ownKeys/descriptors", (T.get("names"), base.get("names")))
        g = set(T.get("globals") or []) - set(base.get("globals") or [])
        check(not g, tag + "no leaked globals", sorted(g))
        check(T.get("errs") == 0, tag + "no page errors", T.get("lastErr"))
        check(T.get("viol") == 0, tag + "no securitypolicyviolation events", T.get("vlog"))
        check(not console, tag + "no console messages", console)
    # baseline sanity: without scriptlets the same page really talks to the network
    zT, _, zhits = results["site-z.localhost"]
    check(zT.get("jp1") == '{"ads":1,"k":2}' and zT.get("pf_pass") == ["real-body", "basic", "/plain"],
          "baseline: no scriptlets on site-z", (zT.get("jp1"), zT.get("pf_pass")))
    check(any("adsbygoogle" in h[2] for h in zhits), "baseline: ad requests reach the server", zhits[:3])
    check(any(p.startswith("/%s/x/" % TOKEN) for _, p in SCHEME_HITS) and
          any(p.startswith("/%s/r/" % TOKEN) for _, p in SCHEME_HITS), "XHR fakes served by the scheme",
          SCHEME_HITS[:5])

    # ---- site-d: noeval-silent
    page = Page(prof)
    loop = QEventLoop()
    page.loadFinished.connect(lambda ok: loop.quit())
    page.setHtml("<!doctype html><script>var r=eval('1+1');var t=Function.prototype.toString.call(eval);</script>",
                 QUrl("http://site-d.localhost:%d/d.html" % port))
    QTimer.singleShot(10000, loop.quit)
    loop.exec()
    v = run_js(page, "JSON.stringify([String(r), t, eval.name])")
    check(v == json.dumps(["undefined", "function eval() { [native code] }", "eval"], separators=(",", ":")),
          "noeval-silent", v)
    check(not page.console, "site-d: no console", page.console)
    page.deleteLater()
    # ---- site-e: no scheme
    del HITS[:]
    page = Page(prof)
    loop = QEventLoop()
    page.loadFinished.connect(lambda ok: loop.quit())
    page.setHtml(E_PAGE, QUrl("http://site-e.localhost:%d/e.html" % port))
    QTimer.singleShot(10000, loop.quit)
    loop.exec()
    v = None
    for _ in range(50):
        v = run_js(page, "E.x && E.f !== undefined && E.v !== undefined ? JSON.stringify(E) : ''")
        if v:
            break
        pump(100)
    check(v and json.loads(v) == {"x": [200, "{}", "http://ads.localhost"], "f": "", "v": True},
          "no-scheme fallback (data: XHR, empty war body, DOMParser xml-prune)", v)
    check(not HITS, "site-e: nothing reached the ad server", HITS)
    page.deleteLater()
    pump(300)
    check(not REPORTS, "no CSP reports sent to server", REPORTS)
    print("%d checks, %d failures" % (COUNT[0], len(FAILS)), flush=True)
    srv.shutdown()
    os._exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
