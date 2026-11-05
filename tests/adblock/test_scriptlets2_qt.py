"""SCRIPTLETS-2 (DOM / cookies / storage / trusted method scriptlets) in a real QtWebEngine.
Run: python -I tests/adblock/test_scriptlets2_qt.py        (needs PyQt6-WebEngine; ~25 s)

Every scriptlet goes through scriptlets.build() and is injected like the glue does it (MainWorld,
DocumentCreation, runsOnSubFrames, host guard, empty name, sourceURL=<anonymous>).
Hosts (local HTTP server, *.localhost = secure context):
  s2-a  plain page
  s2-b  CSP require-trusted-types-for 'script' (YouTube-like; any policy name allowed) + report-uri
  s2-c  CSP require-trusted-types-for + trusted-types pp (name allowlist) + report-uri; script-text rewrites
        and inline-handler creation are left out there (known residual, see report)
  s2-z  same page, no scriptlets (baseline for toString / names / globals)
  s2-r  set-cookie-reload; s2-w close-window; s2-f prevent-refresh (s2-z = baseline for the meta refresh)
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
_TMP = tempfile.mkdtemp(prefix="luna-s2-test-")
os.environ["USERPROFILE"] = _TMP
os.environ["HOME"] = _TMP

from adblock import scriptlet_names as names  # noqa: E402
from adblock import scriptlets  # noqa: E402


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
        print("FAIL:", label, "" if extra is None else repr(extra)[:500], flush=True)


MINE = {
    "remove-attr", "remove-class", "set-attr", "trusted-set-attr", "trusted-replace-node-text",
    "set-cookie", "set-cookie-reload", "trusted-set-cookie", "trusted-set-cookie-reload", "remove-cookie",
    "set-local-storage-item", "set-session-storage-item", "trusted-set-local-storage-item",
    "trusted-set-session-storage-item", "href-sanitizer", "trusted-click-element", "prevent-innerHTML",
    "spoof-css", "close-window", "disable-newtab-links", "prevent-refresh", "prevent-requestAnimationFrame",
    "prevent-canvas", "call-nothrow", "trusted-replace-argument", "trusted-prevent-dom-bypass",
    "trusted-create-html",
}

# ------------------------------------------------------------------ page
PAGE = r"""<!doctype html><html><head><meta charset=utf-8><title>t</title>
<script>
var TT = %(TT)s;
var T = {errs: 0, viol: 0, vlog: []};
window.onerror = function (m) { T.errs++; T.lastErr = String(m); };
document.addEventListener('securitypolicyviolation', function (e) { T.viol++; T.vlog.push(e.violatedDirective + '|' + e.sample); });
var pol = TT ? trustedTypes.createPolicy('pp', {createScript: function (s) { return s; }, createHTML: function (s) { return s; }}) : null;
function HT(s) { return pol ? pol.createHTML(s) : s; }
function SC(s) { return pol ? pol.createScript(s) : s; }
</script>
<script>var cfg2 = {"adBlockWallEnabled":true}; T.rpnt1 = cfg2.adBlockWallEnabled;</script>
<script>T.sed1 = 'COUNTME';</script>
<script>T.sed2 = 'COUNTME';</script>
<script>T.rpnt_untrusted = 'UNTRUSTED_MARK';</script>
<script>
var s = document.createElement('script'); s.text = SC('T.rpnt_dyn = "DYNMARK";'); document.head.appendChild(s);
T.rpnt_dyn_type = s.getAttribute('type');
if (!TT) document.write('<script>T.rpnt_dw = "DWMARK";<\/script>');
</script>
<script>
T.cookie0 = document.cookie;
T.ls = [localStorage.getItem('lsk'), localStorage.getItem('lsq'), localStorage.getItem('lsbad'),
        localStorage.getItem('ls_rm1'), localStorage.getItem('ls_rm_x2'), localStorage.getItem('ls_keep'),
        localStorage.getItem('tls'), sessionStorage.getItem('ssk'), localStorage.getItem('tls_untrusted')];
var cv = document.createElement('canvas');
T.canvas = [cv.getContext('bitmaprenderer') === null, document.createElement('canvas').getContext('2d') !== null];
try { T.cnt = String(JSON.parse('{bad')); } catch (e) { T.cnt = 'threw'; }
T.cnt_ok = JSON.parse('{"k":2}').k;
T.ra_json = JSON.parse('{"ads":true}').ads;
T.ra_this = 'magicword'.toUpperCase() + '|' + 'other'.toUpperCase();
function adRaf() {}
T.raf_id = requestAnimationFrame(function () { adRaf(); T.raf_bad = 1; });
requestAnimationFrame(function () { T.raf_good = 1; });
</script>
</head><body>
<div id=ra1 oncontextmenu="return false" data-x="1"></div>
<div id=ra2 data-x="1"></div>
<div id=rac data-c="1"></div>
<div id=rc1 class="ad-banner blur keep"></div>
<div id=sa1></div>
<img class=lazy data-src="/img.png" alt="">
<p id=txt1>Werbung 42</p>
<h2 id=h21>foo title</h2>
<a id=hs1 href="https://out.example/?url=https%%3A%%2F%%2Ftarget.example%%2Fp">x</a>
<a id=hs2 href="/redir?x">https://text.example/</a>
<a id=hs3 href="https://out.example/?u=aHR0cHM6Ly9iNjQuZXhhbXBsZS9x">x</a>
<a id=hs4 href="/r" title="https://title.example/">x</a>
<a id=hs5 href="https://out.example/?url=javascript%%3Aalert(1)">x</a>
<a id=hs7 href="https://out.example/?url=https%%3A%%2F%%2Fnot-selected.example%%2F">x</a>
<div id=pi1 class=pi></div><div id=pi2 class=pi></div><div id=pi3></div>
<div id=bait class=adsbox style="display:none;width:1px;height:1px"></div>
<div id=nobait style="display:none"></div>
<a id=nt target=_blank href="#nt-hash">nt</a><a id=nn href="#nn-hash">nn</a>
<div id=tch-parent></div>
<div id=shhost></div>
<button id=neg-btn></button><button id=neg-btn2></button>
<script>
T.tch_temp0 = !!document.getElementById('tch-temp');
T.dcl = {};
document.addEventListener('DOMContentLoaded', function () {
  var ra1 = document.getElementById('ra1'), ra2 = document.getElementById('ra2');
  T.dcl.ra = [ra1.hasAttribute('oncontextmenu'), ra1.hasAttribute('data-x'), ra2.hasAttribute('data-x')];
  T.dcl.rac = document.getElementById('rac').hasAttribute('data-c');
});
document.getElementById('neg-btn').addEventListener('click', function () { T.tce_neg = 1; });
document.getElementById('neg-btn2').addEventListener('click', function () { T.tce_neg2 = 1; });
document.getElementById('nt').addEventListener('click', function () { T.nt_listener = 1; });
addEventListener('load', function () { setTimeout(step1, 30); });
function q(id) { return document.getElementById(id); }
function step1() {
  var F = Function.prototype.toString;
  T.rac = q('rac').hasAttribute('data-c');
  T.rc1 = q('rc1').className;
  var sa = q('sa1');
  T.sa = [sa.getAttribute('data-status'), sa.getAttribute('data-bad'), sa.getAttribute('onclick'),
          sa.getAttribute('data-ad-status'), sa.getAttribute('data-untrusted')];
  T.lazy = document.querySelector('img.lazy').getAttribute('src');
  sa.setAttribute('data-status', 'false');
  T.txt1 = q('txt1').textContent;
  T.h21 = q('h21').textContent;
  T.hs = [q('hs1').getAttribute('href'), q('hs2').getAttribute('href'), q('hs3').getAttribute('href'),
          q('hs4').getAttribute('href'), q('hs5').getAttribute('href'), q('hs7').getAttribute('href')];
  var a6 = document.createElement('a'); a6.id = 'hs6';
  a6.setAttribute('href', 'https://o.example/?url=https%%3A%%2F%%2Fdyn.example%%2F'); document.body.appendChild(a6);
  var late = document.createElement('div'); late.className = 'late'; late.setAttribute('data-late', '1');
  document.body.appendChild(late);
  document.body.classList.add('modal-open');
  document.cookie = 'rmlate1=1; path=/';
  T.rmlate0 = document.cookie.indexOf('rmlate1=') !== -1;
  dispatchEvent(new Event('scroll'));
  T.cookie1 = document.cookie;
  // prevent-innerHTML
  q('pi1').innerHTML = HT('<b>html-load.com</b>');
  q('pi2').innerHTML = HT('<b>ok</b>');
  q('pi3').innerHTML = HT('<i>html-load.com</i>');
  T.pi = [q('pi1').innerHTML, q('pi2').innerHTML, q('pi3').innerHTML];
  // spoof-css
  var cs = getComputedStyle(q('bait')), cs2 = getComputedStyle(q('nobait'));
  var r = q('bait').getBoundingClientRect();
  T.spoof = [cs.display, cs.getPropertyValue('display'), cs['visibility'], cs.getPropertyValue('visibility'),
             cs.position, r.width, r.height, cs2.display, cs instanceof CSSStyleDeclaration,
             Object.prototype.toString.call(cs), cs.getPropertyValue === CSSStyleDeclaration.prototype.getPropertyValue,
             typeof cs.length, Object.prototype.toString.call(r)];
  // disable-newtab-links
  var h0 = location.hash;
  q('nt').click(); T.hash1 = location.hash === h0;
  q('nn').click(); T.hash2 = location.hash;
  // replace-argument
  T.qs = [document.querySelector('.ad-zone') === document.body, document.querySelector('#pi2') === q('pi2')];
  var el = q('pi2'); el.setAttribute('data-r', 'error-report-1'); el.setAttribute('data-r2', 'fine');
  T.setattr = [el.getAttribute('data-r'), el.getAttribute('data-r2')];
  new MutationObserver(function () { T.mo_bad = 1; }).observe(document.body, {childList: true});
  document.body.appendChild(document.createElement('span'));
  // dom bypass
  var f = document.createElement('iframe'); document.body.appendChild(f);
  T.db1 = [f.contentWindow.JSON.parse === JSON.parse, f.contentWindow.JSON.parse('{"a":1}').a];
  var f2 = document.createElement('iframe'); document.body.append(f2);
  T.db2 = [f2.contentWindow === window, f2.contentDocument === document];
  // click targets
  setTimeout(function () {
    var b = document.createElement('button'); b.id = 'consent-accept';
    b.addEventListener('click', function () { T.tce = (T.tce || 0) + 1; });
    document.body.appendChild(b);
    var sr = q('shhost').attachShadow({mode: 'open'});
    sr.innerHTML = HT('<button class=sh>s</button>');
    sr.querySelector('button.sh').addEventListener('click', function () { T.tce_sh = 1; });
  }, 100);
  // create-html
  var ins = document.querySelector('#tch-parent ins.adsbygoogle');
  T.tch = [!!q('aswift_2_host'), !!q('aswift_2'), ins ? ins.getAttribute('data-x') : null,
           q('aswift_2_host') ? q('aswift_2_host').parentNode.id : null];
  T.tch_temp1 = !!q('tch-temp');
  setTimeout(step2, 350);
}
function step2() {
  var F = Function.prototype.toString;
  T.late = document.querySelector('.late').hasAttribute('data-late');
  T.body_cls = document.body.classList.contains('modal-open');
  T.sa_back = q('sa1').getAttribute('data-status');
  T.hs6 = q('hs6').getAttribute('href');
  T.mo_ran = T.mo_bad === 1;
  T.ts = [F.call(requestAnimationFrame), F.call(HTMLCanvasElement.prototype.getContext), F.call(JSON.parse),
          F.call(String.prototype.toUpperCase), F.call(MutationObserver), F.call(Element.prototype.setAttribute),
          F.call(document.querySelector), F.call(getComputedStyle), F.call(Element.prototype.getBoundingClientRect),
          F.call(CSSStyleDeclaration.prototype.getPropertyValue),
          F.call(Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML').set),
          F.call(Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML').get),
          F.call(Node.prototype.appendChild), F.call(Element.prototype.append), F.call(F)];
  T.names = [getComputedStyle.name, getComputedStyle.length, MutationObserver.name, MutationObserver.length,
             JSON.parse.name, JSON.parse.length, requestAnimationFrame.length,
             Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML').set.name,
             JSON.stringify(Reflect.ownKeys(Element.prototype.setAttribute)),
             typeof MutationObserver.prototype.observe, 'prototype' in String.prototype.toUpperCase];
  T.globals = Object.getOwnPropertyNames(window);
  setTimeout(function () {
    T.cookie2 = document.cookie;
    T.tch_temp2 = !!q('tch-temp');
    T.done = true;
  }, 1300);
}
</script>
</body></html>
"""

WARM = r"""<!doctype html><script>localStorage.setItem('ls_rm1', '1'); localStorage.setItem('ls_rm_x2', '1');
localStorage.setItem('ls_keep', '1'); document.title = 'warm';</script>"""

RELOAD = r"""<!doctype html><script>sessionStorage.setItem('n', String((+sessionStorage.getItem('n') || 0) + 1));
document.title = 'n' + sessionStorage.getItem('n') + '|' + document.cookie;</script>"""

REFRESH = r"""<!doctype html><html><head><meta http-equiv="refresh" content="1;url=/refreshed.html"></head><body>r</body></html>"""

CSP_B = "require-trusted-types-for 'script'; script-src 'self' 'unsafe-inline'; report-uri /csp-report"
CSP_C = "require-trusted-types-for 'script'; trusted-types pp; script-src 'self' 'unsafe-inline'; report-uri /csp-report"

REPORTS = []


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
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        if self.path.startswith("/csp-report"):
            REPORTS.append((self.headers.get("Host"), body.decode("utf-8", "replace")[:400]))
        self._send(204, "")

    def do_GET(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        p = self.path
        if p.startswith("/t.html"):
            extra = [("Set-Cookie", "rmme=1; path=/"), ("Set-Cookie", "rmkeep=1; path=/"),
                     ("Set-Cookie", "pre=keep; path=/")]
            tt = "0"
            if host.startswith("s2-b"):
                extra.append(("Content-Security-Policy", CSP_B))
                tt = "1"
            elif host.startswith("s2-c") or host.startswith("s2-d"):
                extra.append(("Content-Security-Policy", CSP_C))
                tt = "1"
            return self._send(200, PAGE % {"TT": tt}, extra=extra)
        if p.startswith("/warm.html"):
            return self._send(200, WARM)
        if p.startswith("/reload.html"):
            return self._send(200, RELOAD)
        if p.startswith("/refresh.html"):
            return self._send(200, REFRESH)
        if p.startswith("/refresh2.html"):
            return self._send(200, '<!doctype html><meta http-equiv="Refresh" content="1"><script>'
                              "sessionStorage.setItem('k', String((+sessionStorage.getItem('k') || 0) + 1));"
                              "document.title = 'n' + sessionStorage.getItem('k');</script>")
        if p.startswith("/nav.html"):
            return self._send(200, "<!doctype html><script>setTimeout(function () { location.href = "
                              "'/refreshed.html'; }, 300);</script>")
        if p.startswith("/refreshed.html"):
            return self._send(200, "<!doctype html><title>refreshed</title>")
        if p.startswith("/w.html") or p.startswith("/x.html"):
            return self._send(200, "<!doctype html><title>w</title>")
        if p.startswith("/img.png"):
            png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                                "1f15c4890000000d4944415478da63f8ffff3f0005fe02fea7d6a4580000000049454e44ae426082")
            return self._send(200, png, ctype="image/png")
        self._send(404, "nf")


F_, T_ = False, True
COMMON = [
    ("ra", ["oncontextmenu|data-x", "#ra1"], F_),
    ("ra", ["data-late", ".late", "stay"], F_),
    ("ra", ["data-c", "#rac", "complete"], F_),
    ("rc", ["ad-banner|blur", "#rc1"], F_),
    ("rc", ["modal-open", "body", "stay"], F_),
    ("set-attr", ["#sa1", "data-status", "true"], F_),
    ("set-attr", ["img.lazy", "src", "[data-src]"], F_),
    ("set-attr", ["#sa1", "data-bad", "hello"], F_),
    ("set-attr", ["#sa1", "onclick", "1"], F_),
    ("trusted-set-attr", ["#sa1", "data-ad-status", "unfill-optimize"], T_),
    ("trusted-set-attr", ["#sa1", "data-untrusted", "x"], F_),
    ("rpnt", ["#text", r"/Werbung (\d+)/", "Anzeige $1"], T_),
    ("replace-node-text", ["h2", "foo", "bar"], T_),
    ("set-cookie", ["consent", "accept"], F_),
    ("set-cookie", ["cq", '"ok"'], F_),
    ("set-cookie", ["bad1", "hello"], F_),
    ("set-cookie", ["pre", "yes", "dontOverwrite", "1"], F_),
    ("trusted-set-cookie", ["tsc", '{"a":1}|$now$', "1year", "", "domain", r"/s2-[a-z]\.localhost/"], T_),
    ("trusted-set-cookie", ["tsc_u", "x"], F_),
    ("remove-cookie", ["rmme"], F_),
    ("cookie-remover", ["/^rmlate/", "when", "scroll"], F_),
    ("set-local-storage-item", ["lsk", "true"], F_),
    ("set-local-storage-item", ["lsq", '"dismissed"'], F_),
    ("set-local-storage-item", ["lsbad", "hello"], F_),
    ("set-local-storage-item", ["ls_rm1", "$remove$"], F_),
    ("set-local-storage-item", ["/^ls_rm_x/", "$remove$"], F_),
    ("trusted-set-local-storage-item", ["tls", '{"preferences":3,"t":"$now$"}'], T_),
    ("trusted-set-local-storage-item", ["tls_untrusted", "x"], F_),
    ("set-session-storage-item", ["ssk", "accept"], F_),
    ("href-sanitizer", ["a#hs1, a#hs6", "?url"], F_),
    ("href-sanitizer", ["a#hs2"], F_),
    ("href-sanitizer", ["a#hs3", "?u -base64"], F_),
    ("href-sanitizer", ["a#hs4", "[title]"], F_),
    ("href-sanitizer", ["a#hs5", "?url"], F_),
    ("trusted-click-element", ["#consent-accept"], T_),
    ("trusted-click-element", ["#shhost >>> button.sh", "", "200"], T_),
    ("trusted-click-element", ["#neg-btn", "cookie:nonexistent_zz"], T_),
    ("trusted-click-element", ["#neg-btn2"], F_),
    ("prevent-innerHTML", ["div.pi", "html-load.com"], F_),
    ("spoof-css", ["#bait", "display", "block", "visibility", "visible", "_rectw", "300", "_recth", "250"], F_),
    ("disable-newtab-links", [], F_),
    ("no-requestAnimationFrame-if", ["adRaf"], F_),
    ("prevent-canvas", ["/bitmap/"], F_),
    ("call-nothrow", ["JSON.parse"], F_),
    ("trusted-replace-argument", ["JSON.parse", "0", 'repl:/"ads":true/"ads":false/'], T_),
    ("trusted-replace-argument", ["String.prototype.toUpperCase", "this", 'json:"replaced"', "condition", "magicword"], T_),
    ("trusted-replace-argument", ["MutationObserver", "0", "noopFunc"], T_),
    ("trusted-replace-argument", ["Element.prototype.setAttribute", "1", "", "condition", "/error-report/"], T_),
    ("trusted-replace-argument", ["document.querySelector", "0", 'json:"body"', "condition", ".ad-zone"], T_),
    ("trusted-prevent-dom-bypass", ["Node.prototype.appendChild", "JSON.parse"], T_),
    ("trusted-prevent-dom-bypass", ["Element.prototype.append"], T_),
    ("trusted-create-html", ["#tch-parent", '<div id="aswift_2_host"><iframe id="aswift_2"></iframe></div>'
                             '<ins class="adsbygoogle" data-x="a&amp;b"></ins>'], T_),
    ("trusted-create-html", ["body", '<div id="tch-temp"></div>', "800"], T_),
]
SCRIPT_EDITS = [   # need a Trusted Types policy on TT pages: not on s2-c (name allowlist)
    ("rpnt", ["script", '"adBlockWallEnabled":true', '"adBlockWallEnabled":false'], T_),
    ("trusted-rpnt", ["script", "COUNTME", "COUNTED", "sedCount", "1"], T_),
    ("rpnt", ["script", "UNTRUSTED_MARK", "X"], F_),
    ("rpnt", ["script", "DYNMARK", "DYNDONE"], T_),
    ("rpnt", ["script", "DWMARK", "DWDONE"], T_),
    ("trusted-create-html", ["#tch-parent", '<img id="tchimg" src="/nonexist.png" onerror="T.tch_onerror=1">'], T_),
]


def t_python():
    b = scriptlets.build
    # trusted-only names never built from untrusted lists
    for nm in ("trusted-set-attr", "rpnt", "replace-node-text", "trusted-set-cookie", "trusted-set-cookie-reload",
               "trusted-set-local-storage-item", "trusted-set-session-storage-item", "trusted-click-element",
               "trusted-replace-argument", "trusted-prevent-dom-bypass", "trusted-create-html", "trusted-create-HTML"):
        check(b([(nm, ["a", "b", "c"], False)], "x.com") is None, "untrusted dropped: " + nm)
        check(b([(nm, ["a", "b", "c"], True)], "x.com") is not None, "trusted built: " + nm)
    for nm in ("ra", "rc", "cookie-remover", "norafif", "no-requestAnimationFrame-if", "window-close-if",
               "refresh-defuser"):
        check(b([(nm, ["x"], False)], "x.com") is not None, "alias builds: " + nm)
    avail = scriptlets.available()
    check(MINE <= avail, "all files present", sorted(MINE - avail))
    check(MINE <= names.SUPPORTED, "registered in SUPPORTED", sorted(MINE - names.SUPPORTED))
    js = b([(n, ["x", "y", "z"], True) for n in sorted(MINE)], "x.com")
    for bad in ("eval(", "new Function", "Function(", "debugger", "console.", "innerHTML =", ".outerHTML",
                "srcdoc =", "new n.DOMParser", "parseFromString"):
        check(bad not in js, "bundle free of " + bad)
    # deps bundled once
    js2 = b([("set-cookie-reload", ["a", "ok"], False), ("trusted-set-cookie", ["b", "c"], True),
             ("set-cookie", ["d", "ok"], False)], "x.com")
    check(len(re.findall(r"(?m)^var a\d+=", js2)) == 3 and js2.count('"set-cookie":') == 1, "deps once")
    import shutil
    import subprocess
    node = shutil.which("node")
    if node:
        p = os.path.join(_TMP, "b.js")
        with open(p, "w", encoding="utf-8") as f:
            f.write(js)
        r = subprocess.run([node, "--check", p], capture_output=True, text=True)
        check(r.returncode == 0, "node --check", r.stderr[:300])


def main():
    t_python()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    from PyQt6.QtCore import QEventLoop, QTimer, QUrl
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript
    from PyQt6.QtWidgets import QApplication

    app = QApplication([sys.argv[0], "--webEngineArgs", "--disable-gpu"])  # noqa: F841

    class Page(QWebEnginePage):
        def __init__(self, prof):
            super().__init__(prof)
            self.console = []
            self.closed = 0
            self.windowCloseRequested.connect(self._closed)

        def _closed(self):
            self.closed += 1

        def javaScriptConsoleMessage(self, level, msg, line, src):
            self.console.append((msg[:300], src[-60:] if src else "", line))

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

    def load(page, url, wait=15000):
        loop = QEventLoop()
        page.loadFinished.connect(lambda ok: loop.quit())
        page.load(QUrl(url))
        QTimer.singleShot(wait, loop.quit)
        loop.exec()

    prof = QWebEngineProfile()   # off-the-record
    bundles = {
        "s2-a.localhost": COMMON + SCRIPT_EDITS,
        "s2-b.localhost": COMMON + SCRIPT_EDITS,
        "s2-c.localhost": COMMON,
        "s2-d.localhost": COMMON + SCRIPT_EDITS,   # residual: allowlisted TT + script edits
        "s2-r.localhost": [("set-cookie-reload", ["rl", "accept"], F_)],
        "s2-w.localhost": [("window-close-if", [r"/w\.html/"], F_)],
        "s2-f.localhost": [("refresh-defuser", [], F_)],
    }
    t0 = time.perf_counter()
    for host, rules in bundles.items():
        b = scriptlets.build(rules, host, sr="xtest://l/t/")
        check(b is not None, "bundle built " + host)
        s = QWebEngineScript()
        s.setName("")
        s.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        s.setRunsOnSubFrames(True)
        s.setSourceCode('if(location.hostname==="%s"){%s}\n//# sourceURL=<anonymous>' % (host, b))
        prof.scripts().insert(s)
    print("build: %.1f ms for %d bundles" % ((time.perf_counter() - t0) * 1000, len(bundles)), flush=True)

    results = {}
    for host in ("s2-z.localhost", "s2-a.localhost", "s2-b.localhost", "s2-c.localhost", "s2-d.localhost"):
        page = Page(prof)
        page.setVisible(True)
        load(page, "http://%s:%d/warm.html" % (host, port))
        load(page, "http://%s:%d/t.html" % (host, port))
        end = time.time() + 15
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
        results[host] = (val or {}, list(page.console))
        page.deleteLater()
        pump(50)

    base, _ = results["s2-z.localhost"]
    for host in ("s2-a.localhost", "s2-b.localhost", "s2-c.localhost", "s2-d.localhost"):
        T, console = results[host]
        tag = host + ": "
        edits = host.startswith("s2-a") or host.startswith("s2-b")
        resid = host.startswith("s2-d")
        # remove-attr / remove-class
        check(T.get("dcl", {}).get("ra") == [False, False, True], tag + "ra at DOMContentLoaded", T.get("dcl"))
        check(T.get("dcl", {}).get("rac") is True and T.get("rac") is False, tag + "ra complete (at load)",
              (T.get("dcl"), T.get("rac")))
        check(T.get("late") is False, tag + "ra stay (later element)")
        check(T.get("rc1") == "keep", tag + "rc", T.get("rc1"))
        check(T.get("body_cls") is False, tag + "rc stay on body")
        # set-attr
        check(T.get("sa") == ["true", None, None, "unfill-optimize", None], tag + "set-attr values", T.get("sa"))
        check(T.get("lazy") == "/img.png", tag + "set-attr [data-src] copy", T.get("lazy"))
        check(T.get("sa_back") == "true", tag + "set-attr re-applied after page change", T.get("sa_back"))
        # node text
        check(T.get("txt1") == "Anzeige 42", tag + "rpnt #text regex $1", T.get("txt1"))
        check(T.get("h21") == "bar title", tag + "replace-node-text h2", T.get("h21"))
        if edits:
            check(T.get("rpnt1") is False, tag + "rpnt parser script edited", T.get("rpnt1"))
            check(T.get("sed1") == "COUNTED" and T.get("sed2") == "COUNTME", tag + "rpnt sedCount 1",
                  (T.get("sed1"), T.get("sed2")))
            check(T.get("rpnt_dyn") == "DYNDONE" and T.get("rpnt_dyn_type") is None, tag + "rpnt dynamic script",
                  (T.get("rpnt_dyn"), T.get("rpnt_dyn_type")))
            if host.startswith("s2-a"):
                check(T.get("rpnt_dw") == "DWDONE", tag + "rpnt document.write", T.get("rpnt_dw"))
        else:
            check(T.get("rpnt1") is True, tag + "no script edits on allowlisted-TT page")
        check(T.get("rpnt_untrusted") == "UNTRUSTED_MARK", tag + "untrusted rpnt dropped")
        # cookies
        c0 = T.get("cookie0", "")
        ck = dict(x.strip().split("=", 1) for x in c0.split(";") if "=" in x)
        check(ck.get("consent") == "accept", tag + "set-cookie token", c0)
        check(ck.get("cq") == '"ok"', tag + "set-cookie quoted value kept", c0)
        check("bad1" not in ck, tag + "set-cookie invalid value inert", c0)
        check(ck.get("pre") == "keep", tag + "set-cookie dontOverwrite", c0)
        check(re.match(r'^\{"a":1\}\|\d{13}$', ck.get("tsc", "")) is not None, tag + "trusted-set-cookie $now$ + domain regex", c0)
        check("tsc_u" not in ck, tag + "untrusted trusted-set-cookie dropped")
        check("rmme" not in ck and ck.get("rmkeep") == "1", tag + "remove-cookie at start", c0)
        check(T.get("rmlate0") is True and "rmlate1" in T.get("cookie1", "") and "rmlate1" not in T.get("cookie2", ""),
              tag + "remove-cookie when scroll (debounced)", (T.get("cookie1"), T.get("cookie2")))
        # storage
        ls = T.get("ls") or [None] * 9
        check(ls[0] == "true" and ls[1] == '"dismissed"' and ls[2] is None, tag + "set-local-storage-item", ls)
        check(ls[3] is None and ls[4] is None and ls[5] == "1", tag + "$remove$ plain + /regex/ key", ls)
        check(isinstance(ls[6], str) and re.match(r'^\{"preferences":3,"t":"\d{13}"\}$', ls[6]) is not None,
              tag + "trusted-set-local-storage-item $now$", ls[6])
        check(ls[7] == "accept" and ls[8] is None, tag + "session item / untrusted trusted dropped", ls)
        # href-sanitizer
        check(T.get("hs") == ["https://target.example/p", "https://text.example/", "https://b64.example/q",
                              "https://title.example/", "https://out.example/?url=javascript%3Aalert(1)",
                              "https://out.example/?url=https%3A%2F%2Fnot-selected.example%2F"],
              tag + "href-sanitizer", T.get("hs"))
        check(T.get("hs6") == "https://dyn.example/", tag + "href-sanitizer on mutation", T.get("hs6"))
        # clicks
        check(T.get("tce") == 1, tag + "trusted-click-element waits for element", T.get("tce"))
        check(T.get("tce_sh") == 1, tag + "trusted-click-element >>> shadow + delay")
        check("tce_neg" not in T and "tce_neg2" not in T, tag + "click: failed condition / untrusted dropped")
        # innerHTML, spoof-css
        check(T.get("pi") == ["", "<b>ok</b>", "<i>html-load.com</i>"], tag + "prevent-innerHTML", T.get("pi"))
        sp = T.get("spoof") or []
        check(sp[:8] == ["block", "block", "visible", "visible", "static", 300, 250, "none"],
              tag + "spoof-css values", sp)
        check(sp[8:] == [True, "[object CSSStyleDeclaration]", True, "number", "[object DOMRect]"],
              tag + "spoof-css proxy identity", sp)
        # newtab, rAF, canvas, call-nothrow, replace-argument, dom bypass
        check(T.get("hash1") is True and "nt_listener" not in T and T.get("hash2") == "#nn-hash",
              tag + "disable-newtab-links", (T.get("hash1"), T.get("hash2")))
        check("raf_bad" not in T and isinstance(T.get("raf_id"), int) and T["raf_id"] > 0, tag + "norafif")
        check(T.get("raf_good") == base.get("raf_good"), tag + "rAF others behave as baseline", (T.get("raf_good"), base.get("raf_good")))
        check(T.get("canvas") == [True, True] and base.get("canvas") == [False, True], tag + "prevent-canvas /bitmap/", (T.get("canvas"), base.get("canvas")))
        check(T.get("cnt") == "undefined" and T.get("cnt_ok") == 2, tag + "call-nothrow", (T.get("cnt"), T.get("cnt_ok")))
        check(T.get("ra_json") is False, tag + "replace-argument repl:", T.get("ra_json"))
        check(T.get("ra_this") == "REPLACED|OTHER", tag + "replace-argument this + condition", T.get("ra_this"))
        check(T.get("mo_ran") is False, tag + "replace-argument constructor arg (MutationObserver noopFunc)")
        check(T.get("setattr") == ["", "fine"], tag + "replace-argument empty value + condition", T.get("setattr"))
        check(T.get("qs") == [True, True], tag + "replace-argument json: on document method", T.get("qs"))
        check(T.get("db1") == [True, 1], tag + "prevent-dom-bypass JSON.parse (+ adopted realm)", T.get("db1"))
        check(T.get("db2") == [True, True], tag + "prevent-dom-bypass without targetProp", T.get("db2"))
        # create-html
        check(T.get("tch") == [True, True, "a&b", "tch-parent"], tag + "trusted-create-html", T.get("tch"))
        check(T.get("tch_temp0") is True and T.get("tch_temp1") is True and T.get("tch_temp2") is False,
              tag + "trusted-create-html into late body + duration",
              (T.get("tch_temp0"), T.get("tch_temp1"), T.get("tch_temp2")))
        if edits:
            check(T.get("tch_onerror") == 1, tag + "create-html inline handler runs (TT policy)", T.get("tch_onerror"))
        # stealth
        check(T.get("ts") == base.get("ts"), tag + "toString native", [x for x, y in zip(T.get("ts") or [], base.get("ts") or []) if x != y])
        check(T.get("names") == base.get("names"), tag + "names/lengths/ownKeys", (T.get("names"), base.get("names")))
        g = {x for x in set(T.get("globals") or []) - set(base.get("globals") or []) if not x.isdigit()}
        check(not g, tag + "no leaked globals", sorted(g))
        check(T.get("errs") == 0, tag + "no page errors", T.get("lastErr"))
        if resid:   # one failed createPolicy per document, then script edits are skipped
            check(len(T.get("vlog") or []) == 1 and "trusted-types" in T["vlog"][0], tag + "residual: exactly one TT violation", T.get("vlog"))
            check(len(console) == 1 and "TrustedTypePolicy" in console[0][0], tag + "residual: one console error", console)
        else:
            check(T.get("viol") == 0, tag + "no securitypolicyviolation events", T.get("vlog"))
            check(not console, tag + "no console messages", console)
    check(base.get("rpnt1") is True and base.get("txt1") == "Werbung 42" and "consent=accept" not in base.get("cookie0", ""),
          "baseline: no scriptlets on s2-z")
    check(base.get("spoof", [None])[0] == "none" and base.get("pi", [None])[0] == "<b>html-load.com</b>",
          "baseline: natives unchanged")

    # ---- set-cookie-reload: one reload, then stable
    page = Page(prof)
    load(page, "http://s2-r.localhost:%d/reload.html" % port)
    pump(1500)
    title = run_js(page, "document.title")
    check(title == "n2|rl=accept", "set-cookie-reload reloads once", title)
    check(not page.console, "reload: no console", page.console)
    page.deleteLater()

    # ---- close-window (fresh pages: history length 1)
    page = Page(prof)
    load(page, "http://s2-w.localhost:%d/w.html" % port)
    pump(200)
    check(page.closed == 1, "close-window matching -> windowCloseRequested", page.closed)
    page.deleteLater()
    page = Page(prof)
    load(page, "http://s2-w.localhost:%d/x.html" % port)
    pump(200)
    check(page.closed == 0, "close-window not matching", page.closed)
    page.deleteLater()

    # ---- prevent-refresh vs baseline
    pf, pz = Page(prof), Page(prof)
    load(pf, "http://s2-f.localhost:%d/refresh.html" % port)
    load(pz, "http://s2-z.localhost:%d/refresh.html" % port)
    pump(2500)
    uf, uz = pf.url().path(), pz.url().path()
    check(uf == "/refresh.html", "prevent-refresh stops meta refresh", uf)
    check(uz == "/refreshed.html", "baseline meta refresh navigates", uz)
    check(not pf.console, "prevent-refresh: no console", pf.console)
    p2, p3 = Page(prof), Page(prof)
    load(p2, "http://s2-f.localhost:%d/refresh2.html" % port)
    load(p3, "http://s2-f.localhost:%d/nav.html" % port)
    pump(2500)
    check(p2.title() == "n1", "prevent-refresh stops self-refresh (reload)", p2.title())
    check(p3.url().path() == "/refreshed.html", "prevent-refresh leaves script navigation alone", p3.url().path())

    pump(300)
    rep = [r for r in REPORTS if not (r[0] or "").startswith("s2-d")]
    check(not rep, "no CSP reports sent to server", rep)
    check(len(REPORTS) - len(rep) <= 1, "residual host: at most one report", REPORTS)
    print("%d checks, %d failures" % (COUNT[0], len(FAILS)), flush=True)
    srv.shutdown()
    os._exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
