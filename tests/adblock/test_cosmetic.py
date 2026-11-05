"""Tests for adblock/cosmetic.py + adblock/js/cosmetic.js.

Run:  python -I tests/adblock/test_cosmetic.py   [--no-qt]
Part 1: pure-Python unit tests. Part 2: real QtWebEngine (offscreen view, temp HOME, local HTTP server with *.test
mapped to 127.0.0.1, stub scheme handler answering `c?t=` lookups via cosmetic.lookup_json).
"""
import os
import sys
import json
import time
import tempfile
import threading
import importlib.util
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="luna_cos_")
os.environ["USERPROFILE"] = TMP
os.environ["HOME"] = TMP
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_spec = importlib.util.spec_from_file_location("luna_cosmetic", os.path.join(REPO, "adblock", "cosmetic.py"))
cos = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cos)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else f"   -> {detail}"), flush=True)


def watchdog(sec):
    def boom():
        print(f"WATCHDOG {sec}s exceeded", flush=True)
        os._exit(3)
    t = threading.Timer(sec, boom)
    t.daemon = True
    t.start()


# ====================================================================== part 1: unit tests
COS_BIN = {
    "lowly": {".adsbox": [".adsbox"], ".gen-ad": [".gen-ad", "div.gen-ad > .inner"], "#gen-id": ["#gen-id"],
              ".late-ad": [".late-ad"], ".unh": [".unh"], ".gunh": [".gunh"], ".bad": [".bad:::nope("],
              ".item7": [".item7"]},
    "high": ["[data-gen-high]", ".gunh-high", "a{x}"],
    "unhide": [".gunh", ".gunh-high"],
}


def unit():
    print("== unit")
    st = cos.load(COS_BIN)
    check("load stats", st["high"] == 2 and st["unhide"] == 2 and st["lowly_keys"] == 7, st)
    check("lookup basic", cos.generic_lookup([".gen-ad", "#gen-id", ".nothing"]) == [".gen-ad", "div.gen-ad > .inner", "#gen-id"])
    check("lookup generic unhide", cos.generic_lookup([".gunh"]) == [])
    check("lookup host unhide", cos.generic_lookup([".unh", ".adsbox"], {".unh"}) == [".adsbox"])
    check("lookup dedupe", cos.generic_lookup([".adsbox", ".adsbox"]) == [".adsbox"])
    check("parse_tokens", cos.parse_tokens(".a #b  x .c" + " .z" * 5000)[:3] == [".a", "#b", ".c"]
          and len(cos.parse_tokens(" .z" * 5000)) == cos.MAX_TOKENS)
    q = "t=" + "%2Egen-ad%20%23gen-id%20.a%2Bb"
    check("lookup_json", json.loads(cos.lookup_json(q)) == [".gen-ad", "div.gen-ad > .inner", "#gen-id"])
    check("lookup_json garbage", json.loads(cos.lookup_json("x=%%%")) == [])

    rows = [
        {"hide": ["#a", ".b", ".u1"], "style": [[".s", "color:red"], [".s2", "color:blue"]], "remove": [".r", ".r2"],
         "proc": [{"s": "div:has-text(x)", "t": [["css", "div"], ["has-text", {"t": "x"}]]},
                  {"s": "p:upward(1)", "t": [["css", "p"], ["upward", 1]]}], "js": [["set-constant", ["a", "1"], True]]},
        json.dumps({"hide": ["#a", ".c"], "unhide": [".u1", ".s2:style(color:blue)", ".r2:remove()", "p:upward(1)", ".gen"]}),
        "not json", 5,
    ]
    d = cos.host_data(rows, 0)
    check("host_data merge+unhide", d["hide"] == ["#a", ".b", ".c"] and d["style"] == [[".s", "color:red"]]
          and d["remove"] == [".r"] and [p["s"] for p in d["proc"]] == ["div:has-text(x)"] and ".gen" in d["unhide"]
          and "js" not in d, d)
    check("host_data json-safe", json.loads(json.dumps(d)) == d)
    d2 = cos.host_data(rows, cos.SHIDE)
    check("host_data SHIDE", "hide" not in d2 and "proc" not in d2 and d2["flags"] == 2 and "unhide" in d2, d2)
    d3 = cos.host_data(rows, cos.GHIDE)
    check("host_data GHIDE", d3["hide"] and "unhide" not in d3, d3)
    check("host_data EHIDE/DOC", cos.host_data(rows, cos.EHIDE) == {"flags": 4} and cos.host_data(rows, cos.DOC) == {"flags": 8})
    check("host_data empty", cos.host_data([], 0) == {"flags": 0})

    s = cos.static_script({"sr": "xq://l/t/", "allow": ["Example.COM"]})
    check("static_script shape", s.startswith("(function(){try{(") and s.endswith(");}catch(e){}})();")
          and '"high":["[data-gen-high]"]' in s and '"allow":["example.com"]' in s and "a{x}" not in s)
    hs = cos.host_script("WWW.Example.com", {"flags": 1, "hide": ["</script> "]})
    check("host_script shape", 'location.hostname!=="www.example.com"' in hs and "\\u2028" in hs and "__lcq" in hs)


# ====================================================================== part 2: QtWebEngine
SCHEME = b"xlctest"
TOKEN = "tk123"
SR = f"{SCHEME.decode()}://l/{TOKEN}/"
LOOKUPS = []          # token lists received by the stub scheme handler

PAGES = {}


def page(path, html, csp=None):
    PAGES[path] = (html, csp)


page("/main.html", r"""<!doctype html><html><head><meta charset="utf-8"><script>
window.__g0 = Object.getOwnPropertyNames(window); window.__viol = 0;
document.addEventListener('securitypolicyviolation', function(){ __viol++; });
</script></head><body>
<div id="sp-hide">specific</div>
<div class="unhidden-spec">unhidden specific</div>
<div class="styled">styled</div>
<div class="rm-me">remove me (plain)</div>
<div class="adsbox" style="height:10px">bait</div>
<div class="gen-ad"><span class="inner">gen</span></div>
<div id="gen-id">gen id</div>
<div class="unh">host-unhidden generic</div>
<div class="gunh">generic-unhidden</div>
<div data-gen-high="1">high generic</div>
<div class="card">Hello <b>SPONSORED</b> post</div>
<div class="card">normal post</div>
<div id="up-gp"><div><span id="up-src">x</span></div></div>
<div class="up2-box"><div><div><i id="up2-src">y</i></div></div></div>
<section class="feed"><article id="art1"><span>Ad</span></article><article id="art2"><div><span>Ad</span></div></article></section>
<ul id="nl"><li id="li-keep">keep this</li><li id="li-drop">drop this</li></ul>
<style>.mcss::before{content:"AD"}</style>
<div class="mcss" id="mcss1">a</div><div class="mcss" id="mcss2" style="--x:1">b</div>
<button id="btn-x" data-x12="1">x</button><button id="btn-y" data-y="1">y</button>
<div><div id="xp-target">xp</div></div>
<div id="mp-target">mp no</div><div id="mp-yes">mp yes</div>
<p class="mtl" id="mtl-long">this paragraph is quite long indeed</p><p class="mtl" id="mtl-short">short</p>
<div class="prm" id="prm1">please remove me now</div>
<div class="pst" id="pst1">style me please</div>
<a class="ra" id="ra1" onclick="return 1" href="#">ra</a>
<div class="rc rc-bad keep" id="rc1">rc</div>
<div id="sib-anchor">anchor</div><div id="sib-next">next</div><div id="sib-third">third</div>
<div id="mm">media</div>
<div class="wa" id="wa1" data-state="ok">watch</div>
<div class="never" id="never1">never</div>
<script>window.__ready = 1;</script>
</body></html>""")
# NOTE: <style> in the page above is page-owned; the trace test counts style elements == 1.

page("/ghide.html", r"""<!doctype html><html><head></head><body>
<div class="adsbox" style="height:10px">bait</div><div data-gen-high="1">high</div><div id="sp-hide">s</div>
</body></html>""")

page("/allow.html", r"""<!doctype html><html><head></head><body>
<div class="adsbox" style="height:10px">bait</div><div id="sp-hide">s</div></body></html>""")

page("/csp.css", ".adsbox{height:10px}")
page("/csp.html", r"""<!doctype html><html><head><script nonce="n1">
window.__viol = []; document.addEventListener('securitypolicyviolation', function(e){ __viol.push(e.violatedDirective + ' ' + e.blockedURI); });
</script><link rel="stylesheet" href="/csp.css"></head><body>
<div id="sp-hide">s</div><div class="adsbox">bait</div>
<div class="card">SPONSORED</div><div class="rm-me">rm</div>
<script nonce="n1">setTimeout(function(){ var d=document.createElement('div'); d.className='late-ad'; d.id='late1'; document.body.appendChild(d); }, 200);</script>
</body></html>""", csp="default-src 'self'; script-src 'nonce-n1'; style-src 'self'; connect-src 'self'; "
                      "require-trusted-types-for 'script'; trusted-types 'none'")

page("/frame-host.html", "<!doctype html><html><body><div id='sp-hide'>top</div>"
     "<iframe id='f' src='http://site-d.test:%PORT%/frame.html' width=400 height=300></iframe>"
     "<script>window.__fr=null; addEventListener('message', function(e){ window.__fr = e.data; });</script></body></html>")

page("/frame.html", r"""<!doctype html><html><body>
<div id="f-spec">frame specific</div><div class="adsbox" style="height:10px">bait</div><div class="card">SPONSORED</div>
<script>
setTimeout(function(){
  var b = document.querySelector('.adsbox'), r = b.getBoundingClientRect();
  parent.postMessage(JSON.stringify({spec: getComputedStyle(document.getElementById('f-spec')).display,
    baitLeft: r.left, baitH: b.offsetHeight, baitDisp: getComputedStyle(b).display,
    card: getComputedStyle(document.querySelector('.card')).display,
    adopted: document.adoptedStyleSheets.length, host: location.hostname}), '*');
}, 900);
</script></body></html>""")

page("/replace.html", r"""<!doctype html><html><body><div id="sp-hide">s</div><div class="adsbox" style="height:10px">b</div>
<div class="card">SPONSORED</div></body></html>""")

page("/others.html", r"""<!doctype html><html><head></head><body>
<div id="o-top">top</div><div id="o-wrap"><div id="o-sib">sib</div><div id="o-keep"><p id="o-inner">keep</p></div></div>
<div id="o-bottom">bottom</div></body></html>""")


def big_html():
    rows = []
    for i in range(5000):
        txt = "Sponsored" if i % 997 == 0 else f"item {i}"
        rows.append(f'<div class="item item{i % 1000} c{i % 37}" id="it{i}"><span>{txt}</span></div>')
    return ("<!doctype html><html><head></head><body><div id='root'>" + "".join(rows) + "</div>"
            "<script>window.__t=performance.now();</script></body></html>")


page("/big.html", big_html())

# per-host data (as site.db rows -> host_data)
P = lambda s, t, a=None: dict(s=s, t=t, **({"a": a} if a else {}))
HOSTDATA = {
    "site-a.test": cos.host_data([{
        "hide": ["#sp-hide", ".unhidden-spec"],
        "unhide": [".unhidden-spec", ".unh", "div.never"],
        "style": [[".styled", "color: rgb(255, 0, 0) !important"], [".styled", "background: url(x)"]],
        "remove": [".rm-me"],
        "proc": [
            P("div.card:has-text(/Sponsored/i)", [["css", "div.card"], ["has-text", {"r": "Sponsored", "f": "i"}]]),
            P("#up-src:upward(2)", [["css", "#up-src"], ["upward", 2]]),
            P("#up2-src:upward(.up2-box)", [["css", "#up2-src"], ["upward", ".up2-box"]]),
            P("section.feed > article:has(> span:has-text(Ad))",
              [["css", "section.feed > article"], ["has", [["css", "> span"], ["has-text", {"t": "Ad"}]]]]),
            P("ul#nl > li:not(:has-text(keep))", [["css", "ul#nl > li"], ["not", [["has-text", {"t": "keep"}]]]]),
            P(".mcss:matches-css-before(content: \"AD\")",
              [["css", ".mcss"], ["matches-css", "before", "content", {"r": "^\"AD\"$", "f": ""}]]),
            P("button:matches-attr(/^data-x[0-9]+$/)", [["css", "button"], ["matches-attr", {"r": "^data-x[0-9]+$", "f": ""}, None]]),
            P(":xpath(//div[@id='xp-target'])", [["xpath", "//div[@id='xp-target']"]]),
            P(":matches-path(/nope) #mp-target", [["matches-path", {"t": "/nope"}], ["css", "#mp-target"]]),
            P(":matches-path(/^\\/main/) #mp-yes", [["matches-path", {"r": "^/main", "f": ""}], ["css", "#mp-yes"]]),
            P("p.mtl:min-text-length(20)", [["css", "p.mtl"], ["min-text-length", 20]]),
            P("div.prm:has-text(remove me):remove()", [["css", "div.prm"], ["has-text", {"t": "remove me"}]], ["remove"]),
            P("div.pst:has-text(style me):style(opacity: 0.5 !important)", [["css", "div.pst"], ["has-text", {"t": "style me"}]],
              ["style", "opacity: 0.5 !important"]),
            P("a.ra[onclick]:remove-attr(onclick)", [["css", "a.ra[onclick]"]], ["remove-attr", {"r": "^onclick$", "f": ""}]),
            P("div.rc:remove-class(rc-bad)", [["css", "div.rc"]], ["remove-class", {"r": "^rc-bad$", "f": ""}]),
            P("#sib-anchor:has-text(anchor) + div", [["css", "#sib-anchor"], ["has-text", {"t": "anchor"}], ["spath", " + div"]]),
            P("#mm:matches-media((min-width: 1px))", [["css", "#mm"], ["matches-media", "(min-width: 1px)"]]),
            P("div.wa[data-state=\"ad\"]:watch-attr(data-state)", [["css", "div.wa[data-state=\"ad\"]"], ["watch-attr", ["data-state"]]]),
            P("div.never", [["css", "div.never"], ["has-text", {"t": "never"}]]),
            P("bogus", [["no-such-op", 1]]),
            P(":others()", [["css", "#o-keep"], ["others"]]),
        ]}], 0),
    "site-b.test": cos.host_data([{"hide": ["#sp-hide"]}], cos.GHIDE),
    "site-c.test": cos.host_data([{"hide": ["#sp-hide"]}], 0),
    "site-d.test": cos.host_data([{"hide": ["#f-spec"], "proc": [
        P("div.card:has-text(SPONSORED)", [["css", "div.card"], ["has-text", {"t": "SPONSORED"}]])]}], 0),
    "big.test": cos.host_data([{"hide": ["#it5"], "proc": [
        P("div.item:has-text(Sponsored)", [["css", "div.item"], ["has-text", {"t": "Sponsored"}]]),
        P("span:has-text(item 42):upward(1)", [["css", "#root > div > span"], ["has-text", {"r": "^item 42$", "f": ""}], ["upward", 1]]),
    ]}], 0),
}
# /others.html is on site-a.test; the :others() filter targets #o-keep which only exists there.


class AttrNames(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names = set()

    def handle_starttag(self, tag, attrs):
        self.names.update(a for a, _ in attrs)


def start_server():
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            item = PAGES.get(path)
            if not item:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            html, csp = item
            body = html.replace("%PORT%", str(PORT)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/css" if path.endswith(".css") else "text/html; charset=utf-8")
            if csp:
                self.send_header("Content-Security-Policy", csp)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1]


PORT = 0


def qt_tests():
    global PORT
    PORT = start_server()
    from PyQt6.QtCore import QTimer, QEventLoop, QUrl, QBuffer, QIODevice, QByteArray
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtWebEngineCore import (QWebEngineUrlScheme, QWebEngineUrlSchemeHandler, QWebEngineProfile,
                                       QWebEnginePage, QWebEngineScript)
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    sch = QWebEngineUrlScheme(SCHEME)
    sch.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    F = QWebEngineUrlScheme.Flag
    sch.setFlags(F.SecureScheme | F.ContentSecurityPolicyIgnored | F.CorsEnabled | F.FetchApiAllowed)
    QWebEngineUrlScheme.registerScheme(sch)

    app = QApplication([sys.argv[0], "--webEngineArgs", "--host-resolver-rules=MAP *.test 127.0.0.1",
                        "--disable-gpu", "--no-proxy-server"])

    class Handler(QWebEngineUrlSchemeHandler):
        def requestStarted(self, job):
            try:
                u = job.requestUrl()
                if u.path() != f"/{TOKEN}/c":
                    job.fail(job.Error.UrlNotFound)
                    return
                q = u.query(QUrl.ComponentFormattingOption.FullyEncoded)
                body = cos.lookup_json(q)
                from urllib.parse import parse_qs
                LOOKUPS.append(cos.parse_tokens(parse_qs(q).get("t", [""])[0]))
                buf = QBuffer(job)
                buf.setData(body)
                buf.open(QIODevice.OpenModeFlag.ReadOnly)
                job.setAdditionalResponseHeaders({QByteArray(b"Access-Control-Allow-Origin"): QByteArray(b"*")})
                job.reply(b"application/json", buf)
            except Exception as e:
                print("handler error", e, flush=True)
                job.fail(job.Error.RequestFailed)

    def mkscript(name, src, world=cos.WORLD_ID):
        s = QWebEngineScript()
        s.setName(name)
        s.setSourceCode(src)
        s.setWorldId(world)
        s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        s.setRunsOnSubFrames(True)
        return s

    console = []

    class TPage(QWebEnginePage):
        def javaScriptConsoleMessage(self, level, msg, line, src):
            console.append((msg[:200], src, line))

    def make_profile(with_cos=True, allow=()):
        prof = QWebEngineProfile(app)       # off-the-record
        h = Handler(prof)
        prof.installUrlSchemeHandler(SCHEME, h)
        prof._h = h
        if with_cos:
            t0 = time.perf_counter()
            src = cos.static_script({"sr": SR, "allow": list(allow)})
            prof.scripts().insert(mkscript("cos-static", src))
            for host, data in HOSTDATA.items():
                prof.scripts().insert(mkscript("cos-" + host, cos.host_script(host, data)))
            prof._ins_ms = (time.perf_counter() - t0) * 1000
        return prof

    def pump(ms):
        loop = QEventLoop()
        QTimer.singleShot(int(ms), loop.quit)
        loop.exec()

    def js(pg, code, world=0, timeout=10):
        loop = QEventLoop()
        box = {}

        def cb(v):
            box["v"] = v
            loop.quit()
        pg.runJavaScript(code, world, cb)
        QTimer.singleShot(int(timeout * 1000), loop.quit)
        if "v" not in box:
            loop.exec()
        return box.get("v", "<<timeout>>")

    def jj(pg, code, world=0):
        v = js(pg, "JSON.stringify(" + code + ")", world)
        try:
            return json.loads(v)
        except Exception:
            return v

    def load(pg, url, timeout=20):
        loop = QEventLoop()
        box = {}

        def done(ok):
            box["ok"] = ok
            loop.quit()
        pg.loadFinished.connect(done)
        t = time.perf_counter()
        pg.load(QUrl(url))
        QTimer.singleShot(int(timeout * 1000), loop.quit)
        loop.exec()
        pg.loadFinished.disconnect(done)
        return box.get("ok"), (time.perf_counter() - t) * 1000

    def wait(pg, expr, timeout=5.0, world=0):
        end = time.perf_counter() + timeout
        while time.perf_counter() < end:
            if js(pg, "!!(" + expr + ")", world) is True:
                return True
            pump(40)
        return False

    def url(host, path):
        return f"http://{host}:{PORT}{path}"

    prof = make_profile(allow=["site-c.test"])
    print(f"== qt  (static script {len(cos.static_script({'sr': SR})) / 1024:.1f} KB, insert {prof._ins_ms:.2f} ms)")
    view = QWebEngineView()
    pg = TPage(prof, view)
    view.setPage(pg)
    view.resize(1200, 900)
    view.show()

    # ------------------------------------------------------------ main page
    ok, ms = load(pg, url("site-a.test", "/main.html"))
    check("main loads", ok is True, ok)
    disp = lambda sel: f"(document.querySelector({json.dumps(sel)})?getComputedStyle(document.querySelector({json.dumps(sel)})).display:'GONE')"
    wait(pg, "getComputedStyle(document.querySelector('.gen-ad')).position==='absolute'", 3)
    wait(pg, "!document.querySelector('a.ra').hasAttribute('onclick')", 2)
    check("specific hide", js(pg, disp("#sp-hide")) == "none")
    check("specific unhide (#@#)", js(pg, disp(".unhidden-spec")) == "block")
    check(":style specific", js(pg, "getComputedStyle(document.querySelector('.styled')).color") == "rgb(255, 0, 0)")
    check(":style unsafe decl dropped", "url(x)" not in json.dumps(js(pg, "document.adoptedStyleSheets[0] && [...document.adoptedStyleSheets[0].cssRules].map(r=>r.cssText).join()")))
    check(":remove plain", js(pg, "document.querySelectorAll('.rm-me').length") == 0)
    bait = jj(pg, "(function(){var b=document.querySelector('.adsbox'),r=b.getBoundingClientRect(),cs=getComputedStyle(b);"
                  "return {h:b.offsetHeight,p:!!b.offsetParent,d:cs.display,v:cs.visibility,l:r.left,t:r.top}})()")
    check("generic lowly off-screen", isinstance(bait, dict) and bait["l"] <= -9000 and bait["t"] <= -9000, bait)
    check("bait checks pass (offsetHeight>0, offsetParent, display/visibility)",
          isinstance(bait, dict) and bait["h"] > 0 and bait["p"] and bait["d"] != "none" and bait["v"] == "visible", bait)
    left = lambda sel: js(pg, f"document.querySelector({json.dumps(sel)}).getBoundingClientRect().left")
    check("generic lowly #id + compound selector", left("#gen-id") <= -9000 and left(".gen-ad") <= -9000)
    check("generic high", left("[data-gen-high]") <= -9000)
    check("host #@# removes generic", left(".unh") >= 0)
    check("generic #@# removes generic", left(".gunh") >= 0)
    check("lookup requests sent", len(LOOKUPS) >= 1 and any(".adsbox" in l for l in LOOKUPS), LOOKUPS[:2])
    # procedural
    P_EXPECT = {"div.card:nth-of-type(1)": None}
    cards = jj(pg, "[...document.querySelectorAll('.card')].map(e=>getComputedStyle(e).display)")
    check("proc has-text regex", cards == ["none", "block"], cards)
    for sel, want, name in [("#up-gp", "none", "upward(n)"), (".up2-box", "none", "upward(css)"),
                            ("#art1", "none", "has(> procedural)"), ("#art2", "block", "has(> ...) child-only"),
                            ("#li-drop", "none", "not(procedural)"), ("#li-keep", "list-item", "not keeps"),
                            ("#mcss1", "none", "matches-css-before"), ("#btn-x", "none", "matches-attr"),
                            ("#btn-y", "inline-block", "matches-attr negative"), ("#xp-target", "none", "xpath"),
                            ("#mp-target", "block", "matches-path negative"), ("#mp-yes", "none", "matches-path positive"),
                            ("#mtl-long", "none", "min-text-length"), ("#mtl-short", "block", "min-text-length negative"),
                            ("#prm1", "GONE", ":remove() procedural"), ("#sib-next", "none", "spath + sibling"),
                            ("#sib-third", "block", "spath + only adjacent"), ("#mm", "none", "matches-media"),
                            ("#never1", "block", "proc #@# exception"), ("#wa1", "block", "watch-attr before change")]:
        got = js(pg, disp(sel))
        check("proc " + name, got == want, f"{sel}: {got}")
    check("proc :style()", js(pg, "getComputedStyle(document.getElementById('pst1')).opacity") == "0.5")
    check("proc :remove-attr()", js(pg, "document.getElementById('ra1').hasAttribute('onclick')") is False)
    check("proc :remove-class()", js(pg, "document.getElementById('rc1').className") == "rc keep")

    # dynamic content
    js(pg, """(function(){
      var c=document.createElement('div'); c.className='card'; c.id='late-card'; c.textContent='late sponsored'; document.body.appendChild(c);
      var g=document.createElement('div'); g.className='late-ad'; g.id='late-ad1'; g.textContent='late'; document.body.appendChild(g);
      var r=document.createElement('div'); r.className='rm-me'; r.id='late-rm'; document.body.appendChild(r);
      document.getElementById('wa1').setAttribute('data-state','ad');
      var x=document.createElement('section'); x.innerHTML='<div class=\"prm\" id=\"prm2\">remove me too</div>'; document.body.appendChild(x);
      return 1})()""")
    ok1 = wait(pg, "getComputedStyle(document.getElementById('late-card')).display==='none'", 2)
    check("late procedural match", ok1)
    ok2 = wait(pg, "document.getElementById('late-ad1').getBoundingClientRect().left<-9000", 2)
    check("late generic lookup", ok2)
    check("late plain :remove", js(pg, "!document.getElementById('late-rm')") is True)
    check("late :remove() procedural (innerHTML subtree)", wait(pg, "!document.getElementById('prm2')", 2))
    check("watch-attr reacts to attribute change", wait(pg, "getComputedStyle(document.getElementById('wa1')).display==='none'", 2))
    # path-selector re-verification: insert siblings before a hidden element -> still the right element hidden
    js(pg, "(function(){var a=document.getElementById('nl'); for(var i=0;i<3;i++){var d=document.createElement('div');"
           "d.textContent='spacer'+i; d.className='spacer'; document.body.insertBefore(d, document.body.firstChild);} return 1})()")
    pump(30)
    sp = jj(pg, "[...document.querySelectorAll('.spacer')].map(e=>getComputedStyle(e).display)")
    check("no wrong element hidden after DOM shift", sp == ["block"] * 3, sp)
    check("hidden element stays hidden after DOM shift",
          js(pg, disp("#li-drop")) == "none" and js(pg, disp("#xp-target")) == "none")
    # SPA navigation -> matches-path re-evaluation
    js(pg, "history.pushState({}, '', '/nope/x'); 1")
    check("matches-path re-evaluated after pushState",
          wait(pg, "getComputedStyle(document.getElementById('mp-target')).display==='none'", 2))
    js(pg, "history.pushState({}, '', '/main.html'); 1")

    # ------------------------------------------------------------ DOM traces / stealth
    names = AttrNames()
    names.feed(PAGES["/main.html"][0])
    allowed = names.names | {"class", "id"}
    found = set(jj(pg, "(function(){var s=new Set();document.querySelectorAll('*').forEach(function(e){for(var a of e.attributes)s.add(a.name)});return [...s]})()"))
    check("no foreign DOM attributes", found <= allowed, found - allowed)
    check("no <style> elements added", js(pg, "document.querySelectorAll('style').length") == 1)
    check("document.styleSheets untouched", js(pg, "document.styleSheets.length") == 1)
    newg = set(jj(pg, "Object.getOwnPropertyNames(window).filter(function(n){return __g0.indexOf(n)<0})"))
    check("no main-world globals", newg <= {"__g0", "__viol", "__ready"}, newg)
    check("no engine globals in main world", js(pg, "typeof __lc + typeof __lcq + typeof __lce + typeof __lcstat") == "undefined" * 4)
    check("exactly one adopted sheet", js(pg, "document.adoptedStyleSheets.length") == 1)
    check("no resource timing entry for lookups",
          js(pg, "performance.getEntriesByType('resource').filter(function(e){return e.name.indexOf('xlctest')===0}).length") == 0)
    check("no CSP violations", js(pg, "__viol") == 0)
    stat = jj(pg, "__lcstat", cos.WORLD_ID)
    print("     engine stats main.html:", stat)

    # ------------------------------------------------------------ page replaces / empties adoptedStyleSheets
    ok, _ = load(pg, url("site-a.test", "/replace.html"))
    wait(pg, "document.querySelector('.adsbox').getBoundingClientRect().left<-9000", 3)
    js(pg, "document.adoptedStyleSheets = []; 1")
    check("page can drop sheet (precondition)", js(pg, disp("#sp-hide")) == "block")
    js(pg, "document.body.appendChild(document.createElement('div')); 1")
    pump(20)
    check("sheet re-added after page replaced adoptedStyleSheets",
          js(pg, disp("#sp-hide")) == "none" and js(pg, "document.adoptedStyleSheets.length") == 1)
    js(pg, "var s2=new CSSStyleSheet(); document.adoptedStyleSheets=[s2]; document.body.appendChild(document.createElement('p')); 1")
    pump(20)
    check("re-added alongside page's own sheet", js(pg, "document.adoptedStyleSheets.length") == 2 and js(pg, disp("#sp-hide")) == "none")
    js(pg, "document.adoptedStyleSheets[1].replaceSync(''); document.body.appendChild(document.createElement('p')); 1")
    pump(20)
    check("sheet rebuilt after page emptied it", js(pg, disp("#sp-hide")) == "none"
          and js(pg, "document.querySelector('.adsbox').getBoundingClientRect().left") <= -9000
          and js(pg, disp(".card")) == "none")

    # ------------------------------------------------------------ $ghide host
    n0 = len(LOOKUPS)
    ok, _ = load(pg, url("site-b.test", "/ghide.html"))
    pump(300)
    check("ghide: specific still applied", js(pg, disp("#sp-hide")) == "none")
    check("ghide: generic not applied", left(".adsbox") >= 0 and left("[data-gen-high]") >= 0)
    check("ghide: no lookups", len(LOOKUPS) == n0)

    # ------------------------------------------------------------ host without per-host script -> defaults
    ok, _ = load(pg, url("nodata.test", "/ghide.html"))
    wait(pg, "document.querySelector('.adsbox').getBoundingClientRect().left<-9000", 3)
    check("no host data: generic high + lowly via defaults", left(".adsbox") <= -9000 and left("[data-gen-high]") <= -9000
          and js(pg, disp("#sp-hide")) == "block")
    st = jj(pg, "__lcstat", cos.WORLD_ID)
    # dynamically created about:blank iframe (engine injected late, existing DOM)
    js(pg, "(function(){var f=document.createElement('iframe');document.body.appendChild(f);var d=f.contentDocument;"
           "var b=d.createElement('div');b.className='adsbox';b.textContent='x';d.body.appendChild(b);window.__ifr=f;return 1})()")
    check("about:blank iframe: generic applied after late injection",
          wait(pg, "__ifr.contentDocument.querySelector('.adsbox').getBoundingClientRect().left<-9000", 3))
    ok, _ = load(pg, url("site-a.test", "/replace.html"))
    pump(100)
    st = jj(pg, "__lcstat", cos.WORLD_ID)
    check("single sheet build when host data present", isinstance(st, dict) and st["rebuilds"] == 1, st)

    # ------------------------------------------------------------ allowlisted top host
    ok, _ = load(pg, url("site-c.test", "/allow.html"))
    pump(300)
    check("allowlist: nothing applied", js(pg, disp("#sp-hide")) == "block" and left(".adsbox") >= 0
          and js(pg, "document.adoptedStyleSheets.length") == 0)

    # ------------------------------------------------------------ CSP + Trusted Types page
    ok, _ = load(pg, url("site-a.test", "/csp.html"))
    wait(pg, "document.getElementById('late1') && document.getElementById('late1').getBoundingClientRect().left<-9000", 3)
    check("csp: specific", js(pg, disp("#sp-hide")) == "none")
    check("csp: generic lookup via scheme", left(".adsbox") <= -9000 and js(pg, "document.querySelector('.adsbox').offsetHeight") == 10)
    check("csp: late generic", js(pg, "document.getElementById('late1').getBoundingClientRect().left") <= -9000)
    check("csp: procedural", js(pg, disp(".card")) == "none")
    check("csp: plain remove", js(pg, "document.querySelectorAll('.rm-me').length") == 0)
    viol = jj(pg, "__viol")
    check("csp: zero securitypolicyviolation events", viol == [], viol)

    # ------------------------------------------------------------ cross-origin iframe
    ok, _ = load(pg, url("site-a.test", "/frame-host.html"))
    wait(pg, "window.__fr", 5)
    fr = jj(pg, "JSON.parse(window.__fr||'null')")
    check("iframe: top specific", js(pg, disp("#sp-hide")) == "none")
    check("iframe: own host specific", isinstance(fr, dict) and fr["spec"] == "none" and fr["host"] == "site-d.test", fr)
    check("iframe: generic off-screen + bait ok", isinstance(fr, dict) and fr["baitLeft"] <= -9000 and fr["baitH"] > 0
          and fr["baitDisp"] != "none", fr)
    check("iframe: procedural", isinstance(fr, dict) and fr["card"] == "none", fr)

    # ------------------------------------------------------------ :others()
    ok, _ = load(pg, url("site-a.test", "/others.html"))
    pump(150)
    od = {k: js(pg, disp("#" + k)) for k in ("o-top", "o-wrap", "o-sib", "o-keep", "o-inner", "o-bottom")}
    check(":others()", od == {"o-top": "none", "o-wrap": "block", "o-sib": "none", "o-keep": "block",
                              "o-inner": "block", "o-bottom": "none"}, od)

    # ------------------------------------------------------------ cost on a 5k-element page
    def measure(p):
        view.setPage(p)
        ok, ms = load(p, url("big.test", "/big.html"))
        pump(250)
        return ms, js(p, "performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd")
    prof0 = make_profile(with_cos=False)
    pg0 = TPage(prof0, view)
    base, withc, stats = [], [], []
    for _ in range(5):
        base.append(measure(pg0))
        withc.append(measure(pg))
        stats.append(jj(pg, "__lcstat", cos.WORLD_ID))
    stats.sort(key=lambda s: s["ms"] + s["passMs"])
    stat = stats[len(stats) // 2]
    hid = jj(pg, "[...document.querySelectorAll('div.item')].filter(e=>getComputedStyle(e).display==='none').map(e=>e.id)")
    check("big: procedural hides 6 sponsored + upward + specific",
          sorted(hid) == sorted(["it0", "it997", "it1994", "it2991", "it3988", "it4985", "it42", "it5"]), hid)
    check("big: lowly generic .item7 applied", left("#it7") <= -9000 and left("#it8") >= 0)
    med = lambda xs: sorted(xs)[len(xs) // 2]
    print(f"     5k page: load base {med([m for m, _ in base]):.0f} ms / with cosmetics {med([m for m, _ in withc]):.0f} ms; "
          f"DCL base {med([d for _, d in base]):.1f} ms / with {med([d for _, d in withc]):.1f} ms")
    print("     engine stats (median of 5 loads of the 5k page):", stat)
    check("big: engine main-thread time < 60 ms (callbacks + passes, upper bound)",
          isinstance(stat, dict) and stat["ms"] + stat["passMs"] < 60, stat)
    # mutation storm: 2000 elements in 100 batches
    js(pg, "__lcstat.ms=0;__lcstat.passes=0;__lcstat.passMs=0;__lcstat.cb=0;1", cos.WORLD_ID)
    t0 = time.perf_counter()
    js(pg, """(function(){var i=0;function b(){for(var k=0;k<20;k++){var d=document.createElement('div');d.className='item c'+(i%50)+' n'+i;
      d.innerHTML='<span>'+(i%400===0?'Sponsored':'x'+i)+'</span>';document.getElementById('root').appendChild(d);i++;}
      if(i<2000)setTimeout(b,5);else window.__done=1;}b();return 1})()""")
    wait(pg, "window.__done", 10)
    pump(300)
    st2 = jj(pg, "__lcstat", cos.WORLD_ID)
    wall = (time.perf_counter() - t0) * 1000
    print(f"     storm (2000 nodes/100 batches, {wall:.0f} ms wall):", st2)
    check("storm: engine share of wall time < 20%", isinstance(st2, dict) and (st2["ms"] + st2["passMs"]) / wall < 0.2, st2)
    check("storm: late sponsored hidden",
          wait(pg, "[...document.querySelectorAll('div.n0,div.n400,div.n1600')].every(e=>getComputedStyle(e).display==='none')", 2))

    check("no console output from engine", not [c for c in console if "xlctest" in c[0] or "userscript" in str(c[1])], console[:5])
    print("     console:", console[:5])
    return app


def main():
    watchdog(240)
    unit()
    if "--no-qt" not in sys.argv:
        qt_tests()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", FAIL)
    sys.stdout.flush()
    os._exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
