"""Scriptlet runtime + first 12 scriptlets in a real QtWebEngine (MainWorld, DocumentCreation, subframes).
Run: python -I tests/adblock/test_runtime_qt.py        (needs PyQt6-WebEngine; ~15 s)

Pages are served by a local HTTP server on *.localhost (secure context, no certificates needed):
  site-a.localhost  scriptlets, plain page + same-origin child frame
  site-b.localhost  same scriptlets, strict CSP + enforced Trusted Types + report-uri
  site-z.localhost  same HTML, no scriptlets (baseline for globals / toString / stack shape)
Stealth checks: native-looking toString (same realm, fresh iframe, child frame), no userscript: frames,
no globals leaked, no console output, no CSP/TT violations (events and server reports).
"""
import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
_TMP = tempfile.mkdtemp(prefix="luna-rt-test-")
os.environ["USERPROFILE"] = _TMP
os.environ["HOME"] = _TMP

from adblock import scriptlets  # noqa: E402


def _watchdog(sec):
    def boom():
        print("WATCHDOG: %ss exceeded" % sec, flush=True)
        os._exit(3)
    t = threading.Timer(sec, boom)
    t.daemon = True
    t.start()


_watchdog(120)

FAILS, COUNT = [], [0]


def check(cond, label, extra=None):
    COUNT[0] += 1
    if not cond:
        FAILS.append(label)
        print("FAIL:", label, "" if extra is None else repr(extra)[:400], flush=True)


# ------------------------------------------------------------------ pages
HEAD = r"""<!doctype html><html><head><meta charset=utf-8><title>t</title>
<script>
var T = {errs: 0, viol: 0, vlog: []};
window.onerror = function () { T.errs++; };
addEventListener('error', function () { T.errs++; });
document.addEventListener('securitypolicyviolation', function (e) { T.viol++; T.vlog.push(e.violatedDirective + '|' + e.sample); });
var BAD = 'BAD_' + 'INLINE';
</script>
"""

COMMON = r"""
<script>
var adblock = true; T.sc_var = adblock;
var cfg = {ads: {enabled: true}}; T.sc_chain = cfg.ads.enabled;
T.sc_noop = typeof blurred === 'function' ? Function.prototype.toString.call(blurred) + '|' + String(blurred()) : typeof blurred;
window.flag2 = 'page-string'; T.sc_retype = flag2;
T.sc_as = typeof asFn === 'function' ? asFn() : 'no';
var d = Object.getOwnPropertyDescriptor(window, 'adblock');
T.sc_getter = d && d.get ? [d.get.name, Function.prototype.toString.call(d.get), d.get.length, d.configurable] : 'no-getter';
</script>
<script>
try { adsBlockedDetector.check(); T.aopr = 'not aborted'; } catch (e) { T.aopr = e.name + ': ' + e.message; T.abortStack = String(e.stack); }
</script>
<script>uncaughtProbe.go(); T.afterUncaught1 = 'should not run';</script>
<script>T.afterUncaught2 = 'ran'; function bypassFn() { adTimer(); T.bypass_bad = 1; }</script>
<script>try { window.atOptions = {k: 1}; T.aopw = 'not aborted'; } catch (e) { T.aopw = e.message; } T.aopw_read = typeof atOptions;</script>
<script>/* BAD_MARKER */ try { document.createElement('div'); T.acs = 'not aborted'; } catch (e) { T.acs = e.message; }</script>
<script>T.acs_clean = typeof document.createElement('div'); T.acs_identity = document.createElement === Document.prototype.createElement;</script>
<script>window.probeObj = {val: 1, val2: 2};
try { T.aost = probeObj.val; } catch (e) { T.aost = 'aborted'; }
try { T.aost2 = probeObj.val2; } catch (e) { T.aost2 = 'aborted'; }
function probeFn() { return probeObj.val3; }
probeObj.val3 = 3; try { T.aost3 = probeFn(); } catch (e) { T.aost3 = 'aborted'; }</script>
<script>
T.nostif_id = setTimeout(function () { adTimer(); T.nostif_bad = 1; }, 5);
setTimeout(function () { T.nostif_good = 1; }, 5);
var iv = setInterval(function () { intervalAd(); T.nosiif_bad = 1; }, 5);
setTimeout(function () { clearInterval(iv); }, 200);
var t0 = performance.now();
setTimeout(function boostMe() { T.boost_ms = performance.now() - t0; }, 5000);
addEventListener('adblockCheckEvt', function () { T.aeld_bad = 1; });
addEventListener('adblockCheckEvt2', function () { T.aeld_good = 1; });
dispatchEvent(new Event('adblockCheckEvt')); dispatchEvent(new Event('adblockCheckEvt2'));
document.addEventListener('click', function () { popMagic(); T.aeld_h_bad = 1; });
document.addEventListener('click', function () { T.aeld_h_good = 1; });
document.dispatchEvent(new Event('click'));
T.nowoif = String(window.open('https://ads.example/popunder'));
var dw = window.open('https://ads.example/decoyme', '_blank');
T.decoy0 = dw === null ? 'null' : typeof dw.closed + ':' + dw.closed;
setTimeout(function () { T.decoy1 = dw ? dw.closed : 'null'; }, 1300);
var ow = window.open('https://ads.example/objdecoy');
T.objdecoy = ow === null ? 'null' : typeof ow;
</script>
<script>window.lateFlag = false; T.late0 = lateFlag;
setTimeout(function () { rangeCb(); T.range50 = 1; }, 50);
setTimeout(function () { rangeCb(); T.range150 = 1; }, 150);
function rangeCb() {}
</script>
<button id=btn1></button><button id=btn2></button>
<script>
document.getElementById('btn1').addEventListener('click', function () { T.btn1 = 1; });
document.getElementById('btn2').addEventListener('click', function () { T.btn2 = 1; });
document.getElementById('btn1').click(); document.getElementById('btn2').click();
</script>
<script id=s1>T.rmnt1 = 'executed'; // BAD_INLINE</script>
<script>var s1 = document.getElementById('s1'); T.rmnt1_el = [s1 !== null, s1 && s1.textContent];</script>
"""

TAIL = r"""
<p id=p1>SponsoredLink here</p>
<iframe id=child src="/child.html"></iframe>
<script>addEventListener("message", function (e) { if (typeof e.data === "string" && e.data.slice(0, 2) === "c:") T.cross = e.data; });
var xf = document.createElement("iframe"); xf.src = "http://site-c.localhost:" + location.port + "/c.html"; document.head.appendChild(xf);</script>
<script>
addEventListener('load', function () { T.loaded = 1; setTimeout(function () { T.step = 1;
  var F = Function.prototype.toString;
  T.ts = [F.call(setTimeout), F.call(setInterval), F.call(window.open), F.call(EventTarget.prototype.addEventListener),
          F.call(F), String(setTimeout), setTimeout.toString(), F.call(Node.prototype.appendChild),
          F.call(Document.prototype.write), F.call(Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow').get)];
  T.names = [setTimeout.name, setTimeout.length, JSON.stringify(Reflect.ownKeys(setTimeout)), 'prototype' in setTimeout,
             F.name, F.length, JSON.stringify(Object.getOwnPropertyDescriptor(window, 'setTimeout')),
             JSON.stringify(Object.getOwnPropertyDescriptor(Function.prototype, 'toString'), function (k, v) { return typeof v === 'function' ? 'fn' : v; })];
  try { F.call({}); } catch (e) { T.ts_err = [e.name, e.message, String(e.stack).split('\n').slice(0, 3).join(' || '), JSON.stringify(Object.getOwnPropertyDescriptor(e, 'stack'), function (k, v) { return k === 'value' ? typeof v : typeof v === 'function' ? 'fn' : v; }), Object.keys(e).length]; }
  try { F.call(5); } catch (e) { T.ts_err2 = String(e.stack).split('\n').slice(0, 3).join(' || '); }
  try { new setTimeout(); } catch (e) { T.ctor_err = e.message; }
  var f = document.createElement('iframe'); document.body.appendChild(f);
  var cw = f.contentWindow;
  var g = Object.getOwnPropertyDescriptor(window, 'adblock');
  T.frame_ts = [cw.Function.prototype.toString.call(setTimeout), cw.Function.prototype.toString.call(cw.setTimeout),
                g && g.get ? cw.Function.prototype.toString.call(g.get) : 'no-getter',
                cw.Function.prototype.toString.call(cw.Function.prototype.toString)];
  cw.setTimeout(bypassFn, 5);
  var c = document.getElementById('child').contentWindow;
  T.child = [c.T2 ? c.T2.adblock : 'no-T2', F.call(c.setTimeout), c.Function.prototype.toString.call(setTimeout)];
  T.globals = Object.getOwnPropertyNames(window);
  T.p1 = document.getElementById('p1').textContent;
  T.late1 = lateFlag;
  setTimeout(function () { T.done = true; }, 1500);
}, 0); });
</script>
</head><body></body></html>
"""

DYN_PLAIN = r"""
<script src="data:text/javascript,try{dataProbe.x;T.acs_data='no'}catch(e){T.acs_data=e.message}"></script>
<script>try { dataProbe2 = 1; T.acs_inline = 'ok'; } catch (e) { T.acs_inline = 'aborted'; }</script>
<script>
var s2 = document.createElement('script'); s2.textContent = 'T.rmnt2 = "executed"; // ' + BAD;
document.head.appendChild(s2); T.rmnt2_type = s2.getAttribute('type'); T.rmnt2_conn = s2.isConnected;
var s3 = document.createElement('script'); s3.textContent = 'T.rmnt_ok = "executed";'; document.head.appendChild(s3);
var fr = document.createDocumentFragment(); var s4 = document.createElement('script');
s4.textContent = 'T.rmnt4 = "executed"; // ' + BAD; fr.appendChild(s4); document.head.append(fr);
document.write('<script>T.rmnt3 = "executed"; // ' + BAD + '<\/script>');
</script>
"""

DYN_TT = r"""
<script>
var pol = trustedTypes.createPolicy('pp', {createScript: function (s) { return s; }, createHTML: function (s) { return s; }});
var s2 = document.createElement('script'); s2.text = pol.createScript('T.rmnt2 = "executed"; // ' + BAD);
document.head.appendChild(s2); T.rmnt2_type = s2.getAttribute('type'); T.rmnt2_conn = s2.isConnected;
var s3 = document.createElement('script'); s3.text = pol.createScript('T.rmnt_ok = "executed";'); document.head.appendChild(s3);
var fr = document.createDocumentFragment(); var s4 = document.createElement('script');
s4.text = pol.createScript('T.rmnt4 = "executed"; // ' + BAD); fr.appendChild(s4); document.head.append(fr);
</script>
"""

CHILD = r"""<!doctype html><html><head><script>var T2 = {}; var adblock = true; T2.adblock = adblock;</script></head><body>c</body></html>"""

CROSS = r"""<!doctype html><script>var adblock = true; setTimeout(function () { adTimer(); }, 1);
parent.postMessage("c:" + adblock + ":" + Function.prototype.toString.call(setTimeout) + ":" + (window.top !== window), "*");</script>"""

CSP = ("require-trusted-types-for 'script'; trusted-types pp; script-src 'self' 'unsafe-inline'; "
       "connect-src 'self'; object-src 'self'; report-uri /csp-report")

REPORTS = []


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=()):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        if self.path.startswith("/csp-report"):
            REPORTS.append(body.decode("utf-8", "replace")[:500])
        self._send(204, "")

    def do_GET(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        if self.path.startswith("/c.html"):
            return self._send(200, CROSS)
        if self.path.startswith("/child.html"):
            extra = [("Content-Security-Policy", CSP)] if host.startswith("site-b") else []
            return self._send(200, CHILD, extra=extra)
        if self.path.startswith("/t.html"):
            if host.startswith("site-b"):
                return self._send(200, HEAD + COMMON + DYN_TT + TAIL, extra=[("Content-Security-Policy", CSP)])
            return self._send(200, HEAD + COMMON + DYN_PLAIN + TAIL)
        self._send(404, "nf")


RULES = [
    ("set", ["adblock", "false"], False),
    ("set-constant", ["cfg.ads.enabled", "false"], False),
    ("set", ["blurred", "noopFunc"], False),
    ("set", ["flag2", "true"], False),
    ("set", ["asFn", "true", "as", "function"], False),
    ("aopr", ["adsBlockedDetector"], False),
    ("abort-on-property-read", ["uncaughtProbe"], False),
    ("aopw", ["atOptions"], False),
    ("acs", ["document.createElement", "BAD_MARKER"], False),
    ("aost", ["probeObj.val", "inlineScript"], False),
    ("aost", ["probeObj.val2", "nomatch_xyz"], False),
    ("aost", ["probeObj.val3", r"/^stackDepth:2\tprobeFn@inlineScript:\d+:1\t@inlineScript:\d+:1$/"], False),
    ("acs", ["dataProbe", "", "/^data:/"], False),
    ("acs", ["dataProbe2", "", "/^data:/"], False),
    ("set", ["lateFlag", "true", "runAt", "interactive"], False),
    ("nostif", ["rangeCb", "!100-200"], False),
    ("aeld", ["click", "", "elements", "#btn1"], False),
    ("nostif", ["adTimer"], False),
    ("nosiif", ["intervalAd"], False),
    ("nano-stb", ["boostMe", "5000", "0.001"], False),
    ("aeld", ["adblockCheckEvt"], False),
    ("aeld", ["click", "popMagic"], False),
    ("nowoif", ["popunder"], False),
    ("nowoif", ["decoyme", "1"], False),
    ("nowoif", ["objdecoy", "1", "obj"], False),
    ("rmnt", ["script", "BAD_INLINE"], False),
    ("rmnt", ["#text", "SponsoredLink"], False),
]


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    from PyQt6.QtCore import QEventLoop, QTimer, QUrl
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript
    from PyQt6.QtWidgets import QApplication

    app = QApplication([sys.argv[0], "--webEngineArgs", "--disable-gpu"])

    class Page(QWebEnginePage):
        def __init__(self, prof):
            super().__init__(prof)
            self.console = []

        def javaScriptConsoleMessage(self, level, msg, line, src):
            self.console.append((msg[:200], src[-60:] if src else "", line))

        def createWindow(self, t):
            return None

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

    bundle = scriptlets.build(RULES, "site-a.localhost", sr="xtest://l/t/")
    check(bundle is not None, "bundle built")
    prof = QWebEngineProfile()   # off-the-record
    for host in ("site-a.localhost", "site-b.localhost", "site-c.localhost"):
        s = QWebEngineScript()
        s.setName("")
        s.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        s.setRunsOnSubFrames(True)
        b = bundle if host != "site-c.localhost" else scriptlets.build(
            [("set", ["adblock", "false"], False), ("nostif", ["adTimer"], False)], host)
        s.setSourceCode('if(location.hostname==="%s"){%s}\n//# sourceURL=<anonymous>' % (host, b))
        prof.scripts().insert(s)

    results = {}
    for host in ("site-z.localhost", "site-a.localhost", "site-b.localhost"):
        page = Page(prof)
        page.setVisible(True)
        loop = QEventLoop()
        page.loadFinished.connect(lambda ok: loop.quit())
        page.load(QUrl("http://%s:%d/t.html" % (host, port)))
        QTimer.singleShot(15000, loop.quit)
        loop.exec()
        end = time.time() + 15
        val = None
        while time.time() < end:
            v = run_js(page, "window.T && T.done ? JSON.stringify(T) : ''")
            if v:
                val = json.loads(v)
                break
            pump(100)
        if val is None:
            v = run_js(page, "JSON.stringify([document.readyState, window.T || null])")
            print("PARTIAL", host, v, page.console[:10], flush=True)
        check(val is not None, host + ": page finished")
        results[host] = (val or {}, list(page.console))
        page.deleteLater()
        pump(50)

    base, _ = results["site-z.localhost"]

    def same(x, y, host):   # compare ignoring the host name embedded in stack frames
        import re
        f = lambda s: re.sub(r":\d+:\d+", ":L:C", s)
        return f(json.dumps(x).replace(host, "H")) == f(json.dumps(y).replace("site-z.localhost", "H"))
    for host in ("site-a.localhost", "site-b.localhost"):
        T, console = results[host]
        tt = host.startswith("site-b")
        tag = host + ": "
        # set-constant
        check(T.get("sc_var") is False, tag + "set var adblock=false", T.get("sc_var"))
        check(T.get("sc_chain") is False, tag + "set deferred chain", T.get("sc_chain"))
        check(T.get("sc_noop") == "function () {}|undefined", tag + "set noopFunc + toString", T.get("sc_noop"))
        check(T.get("sc_retype") == "page-string", tag + "set different-type write wins", T.get("sc_retype"))
        check(T.get("sc_as") is True, tag + "set as function", T.get("sc_as"))
        check(T.get("sc_getter") == ["get adblock", "function get adblock() { [native code] }", 0, True],
              tag + "trap getter looks native", T.get("sc_getter"))
        # abort family
        check(T.get("aopr") == "ReferenceError: adsBlockedDetector is not defined", tag + "aopr", T.get("aopr"))
        check("userscript:" not in T.get("abortStack", "") and "<anonymous>" not in T.get("abortStack", "") and T.get("abortStack", "").count("\n") == 1, tag + "abort stack has only the page frame", T.get("abortStack"))
        check("afterUncaught1" not in T and T.get("afterUncaught2") == "ran", tag + "uncaught abort stops script only")
        check(T.get("errs") == 0, tag + "silent abort: page error handlers not called", T.get("errs"))
        check(T.get("aopw") == "atOptions is not defined" and T.get("aopw_read") == "undefined", tag + "aopw",
              (T.get("aopw"), T.get("aopw_read")))
        check(T.get("acs") == "createElement is not defined", tag + "acs aborts matching script", T.get("acs"))
        check(T.get("acs_clean") == "object" and T.get("acs_identity") is True, tag + "acs passes through others")
        check(T.get("aost") == "aborted" and T.get("aost2") == 2, tag + "aost", (T.get("aost"), T.get("aost2")))
        check(T.get("aost3") == "aborted", tag + "aost normalised stack format", T.get("aost3"))
        if not tt:
            check(T.get("acs_data") == "dataProbe is not defined", tag + "acs data: src needle", T.get("acs_data"))
            check(T.get("acs_inline") == "ok", tag + "acs src needle spares inline", T.get("acs_inline"))
        check(T.get("late0") is False and T.get("late1") is True, tag + "set runAt interactive", (T.get("late0"), T.get("late1")))
        check("range50" not in T and T.get("range150") == 1, tag + "nostif negated delay range")
        check("btn1" not in T and T.get("btn2") == 1, tag + "aeld elements selector")
        # timers
        check("nostif_bad" not in T and T.get("nostif_good") == 1, tag + "nostif defuses matching only")
        check(isinstance(T.get("nostif_id"), int) and T["nostif_id"] > 0, tag + "nostif returns real id")
        check("nosiif_bad" not in T, tag + "nosiif")
        check(isinstance(T.get("boost_ms"), (int, float)) and T["boost_ms"] < 2000, tag + "nano-stb boost",
              T.get("boost_ms"))
        # events / windows
        check("aeld_bad" not in T and T.get("aeld_good") == 1, tag + "aeld by type")
        check("aeld_h_bad" not in T and T.get("aeld_h_good") == 1, tag + "aeld by handler")
        check(T.get("nowoif") == "null", tag + "nowoif -> null", T.get("nowoif"))
        check(T.get("decoy0") == "boolean:false" and T.get("decoy1") is True, tag + "nowoif decoy",
              (T.get("decoy0"), T.get("decoy1")))
        check(T.get("objdecoy") == "object", tag + "nowoif obj decoy", T.get("objdecoy"))
        # rmnt
        check("rmnt1" not in T and T.get("rmnt1_el") == [True, ""], tag + "rmnt parser script emptied",
              (T.get("rmnt1"), T.get("rmnt1_el")))
        check("rmnt2" not in T and T.get("rmnt2_type") is None and T.get("rmnt2_conn") is True,
              tag + "rmnt dynamic script neutered, type restored", (T.get("rmnt2"), T.get("rmnt2_type")))
        check("rmnt4" not in T, tag + "rmnt script in fragment")
        check(T.get("rmnt_ok") == "executed", tag + "rmnt leaves other scripts")
        if not tt:
            check("rmnt3" not in T, tag + "rmnt document.write")
        check(T.get("p1") == "", tag + "rmnt #text", T.get("p1"))
        # stealth
        exp_ts = ["function setTimeout() { [native code] }", "function setInterval() { [native code] }",
                  "function open() { [native code] }", "function addEventListener() { [native code] }",
                  "function toString() { [native code] }", "function setTimeout() { [native code] }",
                  "function setTimeout() { [native code] }", "function appendChild() { [native code] }",
                  "function write() { [native code] }", "function get contentWindow() { [native code] }"]
        check(T.get("ts") == exp_ts and T.get("ts") == base.get("ts"), tag + "toString native", T.get("ts"))
        check(T.get("names") == base.get("names"), tag + "name/length/ownKeys/descriptors", (T.get("names"), base.get("names")))
        check(same(T.get("ts_err"), base.get("ts_err"), host), tag + "toString invalid receiver error identical",
              (T.get("ts_err"), base.get("ts_err")))
        check(same(T.get("ts_err2"), base.get("ts_err2"), host), tag + "toString(5) error identical", (T.get("ts_err2"), base.get("ts_err2")))
        check(T.get("ctor_err") == base.get("ctor_err"), tag + "new setTimeout error", T.get("ctor_err"))
        fts = T.get("frame_ts") or []
        check(fts[:2] == ["function setTimeout() { [native code] }"] * 2 and
              fts[2] == "function get adblock() { [native code] }" and
              fts[3] == "function toString() { [native code] }", tag + "fresh iframe toString", fts)
        check("bypass_bad" not in T, tag + "fresh iframe setTimeout also defused (DOM bypass)")
        check(T.get("child") == [False, "function setTimeout() { [native code] }",
                                 "function setTimeout() { [native code] }"], tag + "same-origin child frame",
              T.get("child"))
        g = {x for x in set(T.get("globals") or []) - set(base.get("globals") or []) if not x.isdigit() and x != "pol"}
        allowed = {"adsBlockedDetector", "uncaughtProbe", "blurred", "asFn", "dataProbe"}
        check(g <= allowed, tag + "no leaked globals", sorted(g - allowed))
        check(T.get("cross") == "c:false:function setTimeout() { [native code] }:true", tag + "cross-origin frame runtime",
              T.get("cross"))
        check(T.get("viol") == 0, tag + "no securitypolicyviolation events", T.get("vlog"))
        check(not console, tag + "no console messages", console)
        if tt:
            check(T.get("rmnt_ok") == "executed", tag + "TT policy page works")
    check(base.get("acs") == "not aborted" and base.get("rmnt1") == "executed", "baseline: no scriptlets on site-z")
    pump(300)
    check(not REPORTS, "no CSP reports sent to server", REPORTS)
    print("%d checks, %d failures" % (COUNT[0], len(FAILS)), flush=True)
    srv.shutdown()
    os._exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
