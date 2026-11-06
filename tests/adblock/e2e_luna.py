"""End-to-end: real Luna (luna.py) with a temp USERPROFILE, REAL NETWORK (downloads the filter lists).

python -I tests/adblock/e2e_luna.py [--home DIR] [--phase 1|2] [--doh-proxy] [--shots DIR] [--real URL ...]

phase 1 (default): fresh profile -> Browser starts in fallback mode -> deferred update (8 s) downloads all lists,
         compiler subprocess (pythonw, watched for console windows) -> new build swapped in -> local test page with
         real ad URLs (blocked/redirected, surrogates run, cosmetics) -> optional real sites -> settings page.
phase 2: same --home, build present -> measures startup (AdBlock load) vs. a run with the feature off.
Never touches the real profile; exits by itself (watchdog). Prints a JSON summary on the last line.
"""
import argparse
import ctypes
import http.server
import importlib.util
import json
import os
import socketserver
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)
ap = argparse.ArgumentParser()
ap.add_argument("--home")
ap.add_argument("--phase", default="1")
ap.add_argument("--off", action="store_true", help="phase 2: adblock feature disabled (baseline)")
ap.add_argument("--doh-proxy", default="", help="path to dohproxy.py dir (bypass LAN DNS sinkhole)")
ap.add_argument("--shots", default="")
ap.add_argument("--real", action="append", default=[])
ap.add_argument("--timeout", type=float, default=420)
ap.add_argument("--probe", default="", help="phase 2: JS expression evaluated on each --real page (result printed)")
ap.add_argument("--settle", type=int, default=8000, help="phase 2: ms to wait on each --real page before measuring")
ap.add_argument("--pre", default="", help="phase 2: JS run on each --real page right after load (e.g. start a video)")
ap.add_argument("--menu", action="store_true", help="phase 2: record (and screenshot with --shots) the shield menu per page")
args = ap.parse_args()
HOMEDIR = args.home or tempfile.mkdtemp(prefix="luna_e2e_")
os.makedirs(HOMEDIR, exist_ok=True)
os.environ["USERPROFILE"] = HOMEDIR
os.environ["HOME"] = HOMEDIR
flags = ["--disable-gpu"]
if args.doh_proxy:
    sys.path.insert(0, args.doh_proxy)
    import dohproxy
    _ps, pport = dohproxy.start()
    flags.append(f"--proxy-server=http://127.0.0.1:{pport}")
    os.environ["http_proxy"] = os.environ["https_proxy"] = f"http://127.0.0.1:{pport}"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags)
OUT = {"home": HOMEDIR, "phase": args.phase, "checks": {}, "fail": []}


def check(name, cond, detail=""):
    OUT["checks"][name] = bool(cond)
    print(("ok   " if cond else "FAIL ") + name, ("" if cond else detail), flush=True)
    if not cond:
        OUT["fail"].append(name)


def finish(code=None):
    print("SUMMARY " + json.dumps(OUT, ensure_ascii=False, default=str), flush=True)
    os._exit(code if code is not None else (1 if OUT["fail"] else 0))


_wd = threading.Timer(args.timeout, lambda: (OUT.__setitem__("watchdog", True), finish(3)))
_wd.daemon = True
_wd.start()

# ---------------------------------------------------------------- console-window detector (Win32)
user32 = ctypes.windll.user32
EnumWindows = user32.EnumWindows
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
CONSOLE_CLASSES = {"ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS", "PseudoConsoleWindow"}


def console_windows():
    found = []

    def cb(h, _):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(h), buf, 256)
        if buf.value in CONSOLE_CLASSES and user32.IsWindowVisible(ctypes.c_void_p(h)):
            found.append(int(h or 0))
        return True
    EnumWindows(WNDENUMPROC(cb), 0)
    return set(found)


# ---------------------------------------------------------------- local test page with REAL ad URLs
PAGE = """<!doctype html><html><head><meta charset=utf-8><title>e2e</title></head><body>
<div class="adsbygoogle" id="gen1" style="height:50px">a</div>
<div id="div-gpt-ad-123" class="ad-slot">b</div>
<p id="txt">Treść strony</p>
<script>
window.R = {};
function ld(id, url){ var s=document.createElement('script'); s.onload=function(){R[id]='load'}; s.onerror=function(){R[id]='error'};
  s.src=url; document.head.appendChild(s); }
ld('gpt', 'https://securepubads.g.doubleclick.net/tag/js/gpt.js');
ld('abg', 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1');
ld('ga', 'https://www.google-analytics.com/analytics.js');
var i=new Image(); i.onload=function(){R.img='load:'+i.naturalWidth}; i.onerror=function(){R.img='error'};
i.src='https://googleads.g.doubleclick.net/pagead/viewthroughconversion/1/?x=1';
</script></body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        b = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
PORT = srv.server_address[1]

# ---------------------------------------------------------------- import Luna (like `python luna.py`, but driven)
t_imp = time.perf_counter()
spec = importlib.util.spec_from_file_location("luna", os.path.join(REPO, "luna.py"))
luna = importlib.util.module_from_spec(spec)
sys.modules["luna"] = luna
spec.loader.exec_module(luna)
OUT["import_ms"] = round((time.perf_counter() - t_imp) * 1000)
import adblock  # same module object luna imported
check("scheme registered before QApplication", adblock.SCHEME_OK)

from PyQt6.QtCore import QTimer, QUrl, QEventLoop, Qt
from PyQt6.QtWidgets import QApplication, QCheckBox, QLabel

app = QApplication([sys.argv[0]])
app.setQuitOnLastWindowClosed(False)
app.setApplicationName("Luna")
app.setStyleSheet(luna.full_style())

if args.phase == "2":
    s = json.loads(open(luna.SETTINGS, encoding="utf-8").read()) if luna.SETTINGS.exists() else {}
    s.setdefault("features", {})["adblock"] = not args.off
    luna.SETTINGS.write_text(json.dumps(s), encoding="utf-8")

# time AdBlock construction inside Browser()
_orig_init = adblock.AdBlock.__init__
T = {}


def timed_init(self, *a, **k):
    t = time.perf_counter()
    _orig_init(self, *a, **k)
    T["adblock_init_ms"] = round((time.perf_counter() - t) * 1000, 1)


adblock.AdBlock.__init__ = timed_init
_orig_install = adblock.AdBlock.install


def timed_install(self, p):
    t = time.perf_counter()
    _orig_install(self, p)
    T["install_ms"] = T.get("install_ms", 0) + round((time.perf_counter() - t) * 1000, 2)


adblock.AdBlock.install = timed_install
_orig_icpt = adblock.AdBlock._intercept
ICPT = []


def timed_icpt(self, info, prof):
    t = time.perf_counter()
    try:
        return _orig_icpt(self, info, prof)
    finally:
        ICPT.append(time.perf_counter() - t)


adblock.AdBlock._intercept = timed_icpt


def icpt_stats():
    if not ICPT:
        return {}
    s = sorted(ICPT)
    q = lambda p: round(s[min(len(s) - 1, int(p * len(s)))] * 1e6)
    return {"calls": len(s), "median_us": q(0.5), "p90_us": q(0.9), "p99_us": q(0.99), "max_us": round(s[-1] * 1e6),
            "total_ms": round(sum(s) * 1000, 1)}


def wait(ms):
    lp = QEventLoop()
    QTimer.singleShot(int(ms), lp.quit)
    lp.exec()


def until(fn, ms, step=100):
    end = time.time() + ms / 1000
    while time.time() < end:
        try:
            if fn():
                return True
        except Exception:
            pass
        wait(step)
    return fn()


t0 = time.perf_counter()
w = luna.Browser()
w.show()
OUT["browser_ms"] = round((time.perf_counter() - t0) * 1000)
OUT.update(T)
ab = luna.SHIELD[0]
check("SHIELD[0] is adblock.AdBlock", isinstance(ab, adblock.AdBlock))
print("browser up in %d ms; AdBlock init %s ms; install %s ms" % (OUT["browser_ms"], T.get("adblock_init_ms"),
                                                                  T.get("install_ms")), flush=True)
wait(300)


def runjs(view, code, world=0):
    out = {}
    view.page().runJavaScript(code, world, lambda v: out.__setitem__("v", v))
    until(lambda: "v" in out, 5000, 20)
    return out.get("v")


def open_tab(url, ms=30000):
    w.open_url_new_tab(url)
    t = w.cur()
    until(lambda: t.web is not None, 5000, 50)
    ok = {"v": None}
    t.web.loadFinished.connect(lambda v: ok.__setitem__("v", v))
    until(lambda: ok["v"] is not None, ms, 100)
    return t, ok["v"]


if args.phase == "2":
    OUT["net_loaded"] = ab.net is not None
    OUT["rules"] = ab.rules_total()
    t, ok = open_tab(f"http://e2e-site.localhost:{PORT}/")
    wait(2500)
    R = runjs(t.web, "JSON.stringify(window.R)")
    OUT["page_R"] = R
    if not args.off:
        check("phase2: build loaded at startup", ab.net is not None)
        check("phase2: blocking active immediately (no 8 s wait)", ab.count(f"http://e2e-site.localhost:{PORT}/") >= 3,
              ab.blocked)
    OUT["real"] = {}
    for url in args.real:
        ICPT.clear()
        t0 = time.time()
        t, ok = open_tab(url, 45000)
        if args.pre and t.web:
            wait(3000)
            runjs(t.web, args.pre)
        wait(args.settle)
        OUT["real"][url] = {"loaded": ok, "blocked": ab.count(url), "s": round(time.time() - t0, 1),
                            "title": t.web.title()[:60] if t.web else "", "interceptor": icpt_stats()}
        if args.probe and t.web:
            OUT["real"][url]["probe"] = runjs(t.web, args.probe)
        if args.menu:
            w.shield_menu()
            mm = w.shield_btn.menu()
            OUT["real"][url]["menu"] = [a.text() for a in mm.actions() if a.text()]
            if args.shots:
                mm.popup(w.shield_btn.mapToGlobal(w.shield_btn.rect().bottomLeft()))
                wait(400)
                os.makedirs(args.shots, exist_ok=True)
                mm.grab().save(os.path.join(args.shots, "menu_%d.png" % len(OUT["real"])))
                mm.hide()
        print("real", url, OUT["real"][url], flush=True)
        if args.shots:
            os.makedirs(args.shots, exist_ok=True)
            t.web.grab().save(os.path.join(args.shots, "p2_%s_%d.png" % ("off" if args.off else "on", len(OUT["real"]))))
    finish()

# ---------------------------------------------------------------- phase 1: first run
check("first run starts in fallback mode", ab.net is None)
consoles0 = console_windows()
seen_consoles = set()
seen_prog = {}
_orig_cc = adblock.compiler_command


def cc(*a):
    r = _orig_cc(*a)
    seen_prog["program"] = r[0]
    return r


adblock.compiler_command = cc
states = []
ab.status_changed.connect(lambda: states.append((round(time.time() - T0, 2), ab.state, ab.error)))
T0 = time.time()


def poll_console():
    seen_consoles.update(console_windows() - consoles0)


ct = QTimer()
ct.timeout.connect(poll_console)
ct.start(25)
ok = until(lambda: ab.net is not None and ab.state == "" and ab._proc is None, 300000, 200)
ct.stop()
OUT["update_s"] = round(time.time() - T0, 1)
OUT["states"] = states
check("lists downloaded + compiled + swapped in (deferred start at 8 s)", ok, (ab.state, ab.error, states))
if not ok:
    finish()
OUT["compile_ms"] = ab.compile_ms
OUT["compiler_program"] = seen_prog.get("program")
OUT["rules"] = ab.rules_total()
OUT["counts"] = ab.info.get("counts")
OUT["meta"] = {k: {kk: v.get(kk) for kk in ("ok", "etag", "last_modified")} for k, v in ab.meta.items() if isinstance(v, dict) and k != "_build"}
check("compiler runs under pythonw.exe", (seen_prog.get("program") or "").lower().endswith("pythonw.exe"), seen_prog)
check("no console window appeared during compile", not seen_consoles, seen_consoles)
check("all enabled lists fetched ok", all((ab.meta.get(i) or {}).get("ok") for i in ab.enabled_ids()),
      {i: (ab.meta.get(i) or {}).get("ok") for i in ab.enabled_ids()})
check("pol0 includes fetched", all(os.path.isfile(adblock.catalog.include_path("pol0", n, HOMEDIR))
                                   for n in adblock.catalog.get("pol0")["includes"]))
check("PSL fetched and used", (ab.meta.get("psl") or {}).get("ok") and ab.psl.data is not None)
check("full rule set (>100k rules)", ab.rules_total() > 100000, ab.rules_total())
check("next update scheduled (single-shot timer)", ab._timer.isActive() and ab._timer.isSingleShot(),
      ab._timer.remainingTime())
OUT["next_update_h"] = round(ab._timer.remainingTime() / 3600000, 1)
print("rules=%d compile=%d ms update=%ss" % (ab.rules_total(), ab.compile_ms, OUT["update_s"]), flush=True)

# --- local page with real ad URLs
t, ok = open_tab(f"http://e2e-site.localhost:{PORT}/")
check("test page loads in a Luna tab", ok)
until(lambda: (runjs(t.web, "JSON.stringify(window.R)") or "").count(":") >= 4, 8000)
R = json.loads(runjs(t.web, "JSON.stringify(window.R)") or "{}")
OUT["page_R"] = R
check("gpt.js redirected to surrogate (googletag works)", R.get("gpt") == "load" and
      runjs(t.web, "!!(window.googletag&&googletag.cmd&&googletag.apiReady!==undefined)") is True, R)
check("adsbygoogle.js surrogate (loaded===true)", R.get("abg") == "load" and
      runjs(t.web, "!!(window.adsbygoogle&&adsbygoogle.loaded===true)") is True, R)
check("analytics.js surrogate (ga function)", R.get("ga") == "load" and runjs(t.web, "typeof ga==='function'") is True, R)
check("tracking pixel -> image surrogate", str(R.get("img", "")).startswith("load"), R)
n_blk = ab.count(f"http://e2e-site.localhost:{PORT}/")
check("requests counted as blocked", n_blk >= 4, n_blk)
wait(1500)
gen = runjs(t.web, "(function(e){var c=getComputedStyle(e);return c.position+'/'+c.left+'/'+e.offsetHeight})(document.getElementById('div-gpt-ad-123'))")
OUT["generic_ins"] = gen
check("generic cosmetic (div-gpt-ad / .ad-slot) off-screen but measurable", str(gen).startswith("absolute/-10000px") and
      not str(gen).endswith("/0"), gen)
check("content untouched", runjs(t.web, "getComputedStyle(document.getElementById('txt')).display") == "block")
luna_menu = w.shield_btn.menu() if w.shield_btn.menu() else None
if args.shots:
    os.makedirs(args.shots, exist_ok=True)

# --- real sites (network)
OUT["real"] = {}
for url in args.real:
    t0 = time.time()
    t, ok = open_tab(url, 45000)
    wait(6000)
    n = ab.count(url)
    OUT["real"][url] = {"loaded": ok, "blocked": n, "s": round(time.time() - t0, 1),
                        "title": t.web.title()[:60] if t.web else ""}
    print("real", url, OUT["real"][url], flush=True)
    if args.shots:
        t.web.grab().save(os.path.join(args.shots, "real_%d.png" % len(OUT["real"])))

# --- shield menu
w.shield_menu()
texts = [a.text() for a in w.shield_btn.menu().actions()]
OUT["shield_menu"] = texts
check("shield menu shows counts + rules", any("Aktywnych reguł" in x for x in texts), texts)

# --- settings page (non-modal so the test can inspect it)
dlg = luna.SettingsDialog(w.store, w.host, w)
dlg.show_page("privacy")
dlg.show()
wait(500)
page = dlg.built.get("privacy")
labels = [x.text() for x in page.findChildren(QLabel)]
switches = [c for c in page.findChildren(QCheckBox) if c.objectName() == "switch"]
OUT["settings_switches"] = len(switches)
check("settings: 9 list switches + feature switch", len(switches) == 1 + len(adblock.catalog.filter_lists()), len(switches))
check("settings: licences/attribution shown", any("GPL-3.0" in x for x in labels) and any("CC BY-NC-SA 4.0" in x for x in labels)
      and any("MPL-2.0" in x for x in labels))
check("settings: rule counts and last update shown", any("Aktywnych reguł" in x for x in labels), [x for x in labels if "reguł" in x][:2])
check("settings: 'Moje filtry' editor", any(x == "Moje filtry" for x in labels))
if args.shots:
    dlg.grab().save(os.path.join(args.shots, "settings_privacy.png"))
dlg.close()

# --- toggling a list rebuilds (EasyPrivacy off) and settings switch drives it
before = ab.rules_total()
done = {}
ab._dl_done.append(lambda ok: done.__setitem__("ok", ok))
ab.set_list_enabled("easyprivacy", False)
until(lambda: "ok" in done, 120000, 200)
check("disabling a list recompiles with fewer rules", done.get("ok") and ab.rules_total() < before,
      (before, ab.rules_total(), ab.error))
ab.set_list_enabled("easyprivacy", True)
done.clear()
ab._dl_done.append(lambda ok: done.__setitem__("ok", ok))
until(lambda: "ok" in done, 120000, 200)
check("re-enabling restores the rule count", ab.rules_total() == before, (before, ab.rules_total()))
w.store.save_settings()
finish()
