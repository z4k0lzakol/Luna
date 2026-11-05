"""Test of adblock/__init__.py (Qt glue) in real QtWebEngine.

python -I tests/adblock/test_glue.py

- temp USERPROFILE, off-the-record profile, local HTTP server on *.localhost (no network)
- builds the filter set through the real path: AdBlock.reconfigure() -> compiler subprocess (pythonw) -> swap
- checks: network block + stealth surrogates (script/img/iframe/xhr), explicit $redirect, generic+specific
  cosmetics, scriptlets (main world, guarded), $document block page + "Przejdź mimo to", $removeparam,
  $popup, allowlist, scheme token protection, fail-open, LRU eviction, fallback mode without a build.
"""
import http.server
import json
import os
import socketserver
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="luna_glue_")
os.environ["USERPROFILE"] = TMP
os.environ["HOME"] = TMP
sys.path.insert(0, REPO)

FAIL = []
N = [0]


def check(name, cond, detail=""):
    N[0] += 1
    if cond:
        print("ok  ", name)
    else:
        print("FAIL", name, detail)
        FAIL.append(name)


def watchdog(sec):
    def boom():
        print(f"WATCHDOG {sec}s exceeded", flush=True)
        os._exit(3)
    t = threading.Timer(sec, boom)
    t.daemon = True
    t.start()


SEEN = []   # (host, path) seen by the server


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head=False):
        host = (self.headers.get("Host") or "").split(":")[0]
        SEEN.append((host, self.path))
        p = self.path.split("?")[0]
        if host.startswith("ads.") or host.startswith("pop."):
            body, ct = b"window.__realAd = 1;", "application/javascript"
            if p.endswith(".png"):
                body, ct = PNG1, "image/png"
        elif p == "/" or p.endswith(".html"):
            body, ct = PAGE.replace("%P%", str(PORT)).encode(), "text/html; charset=utf-8"
        else:
            body, ct = b"ok", "text/plain"
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if not head:
            self.wfile.write(body)


PNG1 = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                     "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")

PAGE = """<!doctype html><html><head><meta charset=utf-8><title>site</title></head><body>
<div class="ad-x" id="spec">spec</div>
<div class="glue-generic-bait" id="gen">gen</div>
<script>
window.R = {};
function ld(id, url){ var s=document.createElement('script'); s.onload=function(){R[id]='load'}; s.onerror=function(){R[id]='error'};
  s.src=url; document.head.appendChild(s); }
ld('surr', 'http://ads.localhost:%P%/tag/surrogate.js');
ld('plain', 'http://ads.localhost:%P%/x/other.js');
var i=new Image(); i.onload=function(){R.img='load:'+i.naturalWidth}; i.onerror=function(){R.img='error'};
i.src='http://ads.localhost:%P%/pix.png';
var f=document.createElement('iframe'); f.onload=function(){R.frame='load'}; f.src='http://ads.localhost:%P%/frame.html';
document.body.appendChild(f);
fetch('http://ads.localhost:%P%/probe.txt',{mode:'no-cors'}).then(function(r){R.fetch='ok:'+r.type},function(e){R.fetch='err'});
</script></body></html>"""


def serve():
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


USER = """! test filters (user list)
||ads.localhost^
||ads.localhost^*/tag/surrogate.js$script,redirect=googletagservices_gpt.js
site-a.localhost##.ad-x
##.glue-generic-bait
##a[href^="http://blocked.localhost"]
site-a.localhost##+js(set-constant, lunaGlueConst, true)
||blocked.localhost^$document
||pop.localhost^$popup
$removeparam=utm_source
"""


class Store:
    def __init__(self):
        self.settings = {"adblock_lists": {l: False for l in
                                           ["ubo-filters", "ubo-badware", "ubo-privacy", "ubo-quick-fixes",
                                            "ubo-unbreak", "easylist", "easyprivacy", "pgl", "pol0"]},
                         "adblock_user": USER}

    def feature(self, n):
        return self.settings.get("features", {}).get(n, True)

    def save_soon(self):
        pass


def main():
    global PORT
    watchdog(180)
    srv, PORT = serve()
    import adblock
    check("scheme registered before QApplication", adblock.SCHEME_OK)
    from PyQt6.QtCore import QUrl, QTimer, QEventLoop
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineScript
    app = QApplication([sys.argv[0], "--webEngineArgs", "--disable-gpu", "--no-proxy-server"])

    def wait(ms):
        lp = QEventLoop()
        QTimer.singleShot(ms, lp.quit)
        lp.exec()

    def until(fn, ms=10000, step=50):
        end = time.time() + ms / 1000
        while time.time() < end:
            if fn():
                return True
            wait(step)
        return fn()

    store = Store()
    t0 = time.perf_counter()
    ab = adblock.AdBlock(store, home=TMP, legacy_domains={"legacy-tracker.localhost"})
    check("constructor without build is cheap", (time.perf_counter() - t0) < 0.2, time.perf_counter() - t0)
    check("no build -> fallback mode", ab.net is None)

    prof = QWebEngineProfile(app)
    ab.install(prof)

    class Page(QWebEnginePage):
        popups = []

        def acceptNavigationRequest(self, url, t, main):
            ab.prepare(self, url, main)
            return super().acceptNavigationRequest(url, t, main)

    page = Page(prof, app)

    def load(url, ms=15000):
        done = {"ok": None}
        c = page.loadFinished.connect(lambda ok: done.__setitem__("ok", ok))
        page.load(QUrl(url))
        until(lambda: done["ok"] is not None, ms)
        page.loadFinished.disconnect(c)
        return done["ok"]

    def js(code, world=QWebEngineScript.ScriptWorldId.MainWorld.value):
        out = {}
        page.runJavaScript(code, world, lambda v: out.__setitem__("v", v))
        until(lambda: "v" in out, 5000, 20)
        return out.get("v")

    # --- fallback mode: legacy third-party host list
    SEEN.clear()
    load(f"http://site-a.localhost:{PORT}/")
    check("fallback mode lets non-listed 3p through", any(h == "ads.localhost" for h, _ in SEEN))

    # --- build through the real subprocess path
    ab.meta["psl"] = {"ok": False, "tried": time.time()}   # no network in this test
    done = {}
    ab._dl_done.append(lambda ok: done.__setitem__("ok", ok))
    t0 = time.time()
    ab.reconfigure()
    until(lambda: "ok" in done, 60000, 100)
    check("compile via subprocess succeeded", done.get("ok") is True and ab.net is not None,
          (done, ab.error, getattr(ab, "compile_log", "")))
    if ab.net is None:
        return finish()
    print("     compile wall %.1fs (subprocess %d ms), info total=%s" % (time.time() - t0, ab.compile_ms, ab.rules_total()))
    check("rules counted", ab.rules_total() >= 7, ab.info.get("counts"))
    check("build dir created", ab.build_dir and os.path.isdir(ab.build_dir))
    check("meta records build signature", (ab.meta.get("_build") or {}).get("sig") == ab._sig())
    check("static cosmetic script inserted", sum(1 for s in prof.scripts().toList() if s.worldId() == 7) == 1)

    # --- main page with ads
    SEEN.clear()
    ok = load(f"http://site-a.localhost:{PORT}/")
    check("page loads", ok)
    until(lambda: (js("JSON.stringify(window.R)") or "").count(":") >= 5, 6000)
    R = json.loads(js("JSON.stringify(window.R)") or "{}")
    ads_seen = [p for h, p in SEEN if h == "ads.localhost"]
    check("no request reached the ad host", not ads_seen, ads_seen)
    check("explicit $redirect -> gpt surrogate executed", R.get("surr") == "load" and
          js("typeof googletag==='object'&&!!googletag.cmd") is True, R)
    check("blocked script -> noop.js (onload, no error)", R.get("plain") == "load", R)
    check("blocked image -> 2x2 surrogate", R.get("img") == "load:2", R)
    check("blocked iframe -> loads (noop.html)", R.get("frame") == "load", R)
    check("blocked no-cors fetch resolves", str(R.get("fetch", "")).startswith("ok"), R)
    check("real ad script never ran", js("window.__realAd===undefined") is True)
    check("scriptlet set-constant applied", js("window.lunaGlueConst") is True)
    check("scriptlet leaves no userscript: in stack", "userscript" not in (js("new Error().stack") or ""))
    until(lambda: js("getComputedStyle(document.getElementById('spec')).display") == "none", 3000)
    check("specific ## hides (display:none)", js("getComputedStyle(document.getElementById('spec')).display") == "none")
    until(lambda: js("getComputedStyle(document.getElementById('gen')).position") == "absolute", 4000)
    check("generic ## hides off-screen (bait-safe)",
          js("(function(e){var c=getComputedStyle(e);return c.position==='absolute'&&c.display!=='none'&&e.offsetHeight>0})(document.getElementById('gen'))") is True)
    check("counter per first-party host", ab.count(f"http://site-a.localhost:{PORT}/") >= 4, ab.blocked)
    check("no DOM traces (no style elements, no attrs)",
          js("document.querySelectorAll('style').length===0&&!document.documentElement.attributes.length") is True)
    lru = ab._profiles[prof].lru
    check("per-host scripts in profile LRU", "site-a.localhost" in lru and len(lru["site-a.localhost"]) >= 2,
          {k: len(v) for k, v in lru.items()})
    tl = js("(function(){return location.hostname})()")
    check("main world sane", tl == "site-a.localhost")

    # --- scheme protection: wrong token / unknown path fail, page cannot read with bad token
    js("""(function(){var o={};window.__o=o;fetch('%s://l/wrongtoken/r/noop.js').then(function(r){o.v=r.status+':';
          return r.text().then(function(t){o.v=r.status+':'+t.length})},function(e){o.v='fail'});return 1})()""" % adblock.SCHEME)
    until(lambda: js("window.__o&&window.__o.v") is not None, 3000)
    # job.fail() -> status 404 without a body (Qt never ends the body stream; only reachable knowing the scheme)
    check("scheme with wrong token serves nothing", js("window.__o.v") in ("fail", "404:", "404:0"), js("window.__o.v"))

    # --- $removeparam on navigation
    load(f"http://site-a.localhost:{PORT}/page.html?utm_source=x&keep=1")
    check("$removeparam strips utm_source on navigation", page.url().toString().endswith("/page.html?keep=1"),
          page.url().toString())

    # --- $document block page + proceed
    SEEN.clear()
    load(f"http://blocked.localhost:{PORT}/")
    check("$document -> block page on our scheme", page.url().scheme() == adblock.SCHEME and
          page.title() == "Strona zablokowana", (page.url().toString(), page.title()))
    check("$document: server never contacted", not any(h == "blocked.localhost" for h, _ in SEEN))
    href = js("document.querySelector('a.b.p').getAttribute('href')")
    check("block page offers 'Przejdź mimo to' to the original URL", href == f"http://blocked.localhost:{PORT}/", href)
    wait(400)
    pos = js("(function(){var a=document.querySelector('a.b.p'),c=getComputedStyle(a),r=a.getBoundingClientRect();"
             "return [c.display,c.position,Math.round(r.left)].join(',')})()")
    check("no cosmetics on our own pages (generic a[href^=...] rule keeps the proceed link visible)",
          pos and pos.split(",")[0] != "none" and pos.split(",")[1] != "absolute", pos)
    done2 = {"ok": None}
    c = page.loadFinished.connect(lambda ok: done2.__setitem__("ok", ok))
    js("document.querySelector('a.b.p').click()")
    until(lambda: page.url().host() == "blocked.localhost", 8000)
    page.loadFinished.disconnect(c)
    check("proceed anyway reaches the site", page.url().host() == "blocked.localhost" and
          any(h == "blocked.localhost" for h, _ in SEEN), page.url().toString())
    load(f"http://blocked.localhost:{PORT}/again.html")
    check("proceeded host stays allowed for the session", page.url().host() == "blocked.localhost")

    # --- popups
    check("$popup blocked", ab.popup_blocked(f"http://pop.localhost:{PORT}/x", f"http://site-a.localhost:{PORT}/"))
    check("other popup allowed", not ab.popup_blocked(f"http://site-b.localhost:{PORT}/", f"http://site-a.localhost:{PORT}/"))

    # --- allowlist
    store.settings["shield_allow"] = ["site-a.localhost"]
    ab.reload()
    check("allowlist change clears host scripts", not ab._profiles[prof].lru)
    SEEN.clear()
    load(f"http://site-a.localhost:{PORT}/")
    until(lambda: (js("JSON.stringify(window.R)") or "").count(":") >= 5, 6000)
    check("allowlisted site: requests not blocked", any(h == "ads.localhost" for h, _ in SEEN))
    check("allowlisted site: no scriptlets", js("window.lunaGlueConst") is None)
    wait(300)
    check("allowlisted site: no cosmetics",
          js("getComputedStyle(document.getElementById('spec')).display") == "block" and
          js("document.adoptedStyleSheets.length") == 0)
    check("allowlisted site: popup not blocked", not ab.popup_blocked(f"http://pop.localhost:{PORT}/x", f"http://site-a.localhost:{PORT}/"))
    store.settings["shield_allow"] = []
    ab.reload()

    # --- feature off
    store.settings["features"] = {"adblock": False}
    ab.reload()
    check("off: static script removed", not any(s.worldId() == 7 for s in prof.scripts().toList()))
    SEEN.clear()
    load(f"http://site-a.localhost:{PORT}/")
    wait(500)
    check("off: nothing blocked", any(h == "ads.localhost" for h, _ in SEEN))
    store.settings["features"] = {}
    ab.reload()
    check("on again: static script back", sum(1 for s in prof.scripts().toList() if s.worldId() == 7) == 1)

    # --- fail open: broken engine must not break loading
    real = ab.net

    class Boom:
        def match(self, *a, **k):
            raise RuntimeError("boom")

        def page_flags(self, *a):
            raise RuntimeError("boom")
    ab.net = Boom()
    ab._hcache.clear()
    for st in ab._profiles.values():
        ab._clear_host_scripts(st)
    SEEN.clear()
    ok = load(f"http://site-c.localhost:{PORT}/")
    check("fail open on engine exception", ok and any(h == "ads.localhost" for h, _ in SEEN))
    ab.net = real

    # --- LRU eviction bound + prepare cost
    st = ab._profiles[prof]
    t0 = time.perf_counter()
    for i in range(adblock.LRU_HOSTS + 40):
        ab.prepare(prof, QUrl(f"https://h{i}.example{i % 7}.com/"), True)
    dt = (time.perf_counter() - t0) / (adblock.LRU_HOSTS + 40)
    check("LRU bounded", len(st.lru) <= adblock.LRU_HOSTS, len(st.lru))
    check("prepare <= 1 ms per new host", dt < 0.001, "%.3f ms" % (dt * 1000))
    n_scripts = len(prof.scripts().toList())
    check("profile script count bounded", n_scripts <= 1 + 3 * adblock.LRU_HOSTS, n_scripts)

    # --- interceptor cost (Python side, real filter set is tiny here; see e2e for full lists)
    # --- second profile gets its own interceptor
    prof2 = QWebEngineProfile(app)
    ab.install(prof2)
    check("per-profile interceptor objects", ab._profiles[prof2].icpt is not ab._profiles[prof].icpt)

    # --- rebuild on user filter change swaps data and clears LRUs
    done3 = {}
    ab._dl_done.append(lambda ok: done3.__setitem__("ok", ok))
    old_dir = ab.build_dir
    ab.set_user_filters(USER + "site-a.localhost##+js(set-constant, lunaGlueConst2, true)\n")
    until(lambda: "ok" in done3, 60000, 100)
    check("rebuild after user filter change", done3.get("ok") and ab.build_dir != old_dir, (done3, ab.error))
    print("     second compile: subprocess %d ms" % ab.compile_ms)
    check("old build directory removed", not os.path.isdir(old_dir))
    load(f"http://site-a.localhost:{PORT}/")
    check("new data applies after swap", js("window.lunaGlueConst2") is True)
    finish()


def finish():
    print(f"\n{N[0]} checks, {len(FAIL)} failures")
    if FAIL:
        print("FAILED:", FAIL)
    sys.stdout.flush()
    os._exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
