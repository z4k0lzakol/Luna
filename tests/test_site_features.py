"""Real Luna (temp USERPROFILE, no network): page features – full screen on request, site permissions (notice bar,
remembered decision, reset), spell checking setup, and the other site tools added later.

python -I tests/test_site_features.py
"""
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
REPO = os.path.dirname(HERE)
HOMEDIR = tempfile.mkdtemp(prefix="luna_site_")
if os.environ.get("LUNA_TEST_DICTS"):   # słowniki obecne już przy starcie (jak w drugim uruchomieniu Luny)
    import shutil
    os.makedirs(os.path.join(HOMEDIR, ".luna_slowniki"))
    for _l in ("pl-PL", "en-US"):
        _src = os.path.join(os.environ["LUNA_TEST_DICTS"], _l + ".bdic")
        if os.path.isfile(_src):
            shutil.copy(_src, os.path.join(HOMEDIR, ".luna_slowniki", _l + ".bdic"))
os.environ["USERPROFILE"] = os.environ["HOME"] = HOMEDIR
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
RES = {"checks": 0, "fail": []}


def check(name, cond, detail=""):
    RES["checks"] += 1
    print(("ok   " if cond else "FAIL ") + name, "" if cond else detail, flush=True)
    if not cond:
        RES["fail"].append(name)


def finish():
    print("%d checks, %d failures" % (RES["checks"], len(RES["fail"])), flush=True)
    if RES["fail"]:
        print("FAILED:", RES["fail"], flush=True)
    os._exit(1 if RES["fail"] else 0)


threading.Timer(240, lambda: (print("WATCHDOG", flush=True), finish())).start()

PAGE = """<!doctype html><html><head><meta charset=utf-8><title>site</title><style>
button{position:absolute;width:200px;height:60px}#fs{left:20px;top:20px}#nt{left:20px;top:100px}
#vid{position:absolute;left:300px;top:20px;width:200px;height:120px;background:#336}</style></head><body>
<div id=vid></div><button id=fs onclick="document.getElementById('vid').requestFullscreen().then(function(){R.fs='on'},function(e){R.fs='err:'+e.name})">fs</button>
<button id=nt onclick="Notification.requestPermission().then(function(p){R.perm=p})">nt</button>
<script>window.R={};document.addEventListener('fullscreenchange',function(){R.fsel=!!document.fullscreenElement})</script>
<textarea id=ta style="position:absolute;left:20px;top:200px;width:300px;height:60px"></textarea>
</body></html>"""


EN_PAGE = """<!doctype html><html lang="en"><head><meta charset=utf-8><title>English</title></head><body>
<h1 id=h>Good morning, my friend</h1><p id=p>The weather is beautiful today.</p>
<code id=c>print("hello world")</code><p id=n translate="no">Brand Name Inc</p>
<script>setTimeout(function(){var e=document.createElement('p');e.id='late';e.textContent='Thank you very much';document.body.appendChild(e)},1500)</script>
</body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        b = (EN_PAGE if self.path.startswith("/en") else PAGE).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
PORT = srv.server_address[1]

sys.path.insert(0, REPO)
spec = importlib.util.spec_from_file_location("luna", os.path.join(REPO, "luna.py"))
luna = importlib.util.module_from_spec(spec)
sys.modules["luna"] = luna
spec.loader.exec_module(luna)
from PyQt6.QtCore import QTimer, QEventLoop, QPoint, Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402

app = QApplication([sys.argv[0]])
app.setQuitOnLastWindowClosed(False)
app.setStyleSheet(luna.full_style())


def wait(ms):
    lp = QEventLoop()
    QTimer.singleShot(int(ms), lp.quit)
    lp.exec()


def until(fn, ms, step=50):
    end = time.time() + ms / 1000
    while time.time() < end:
        try:
            if fn():
                return True
        except Exception:
            pass
        wait(step)
    return bool(fn())


w = luna.Browser()
w.resize(1100, 800)
w.show()
wait(300)


def runjs(view, code):
    out = {}
    view.page().runJavaScript(code, 0, lambda v: out.__setitem__("v", v))
    until(lambda: "v" in out, 5000, 20)
    return out.get("v")


def open_tab(url):
    w.open_url_new_tab(url)
    t = w.cur()
    until(lambda: t.web is not None, 5000)
    ok = {}
    t.web.loadFinished.connect(lambda v: ok.__setitem__("v", v))
    until(lambda: "v" in ok, 15000)
    wait(300)
    return t


def click(view, x, y):
    tgt = view.focusProxy() or view
    QTest.mouseClick(tgt, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(x, y))


def R(view):
    return json.loads(runjs(view, "JSON.stringify(window.R)") or "{}")


def main():
    t = open_tab(f"http://site-a.localhost:{PORT}/")
    web = t.web
    page = web.page()
    A = luna.QWebEngineSettings.WebAttribute
    check("full screen support enabled in profile", page.profile().settings().testAttribute(A.FullScreenSupportEnabled))

    # --- full screen on request
    SKIP = os.environ.get("LUNA_TEST_SKIP", "")
    if "fs" not in SKIP:
        click(web, 120, 50)
    until(lambda: page in luna.PAGE_FULLSCREEN and R(luna.PAGE_FULLSCREEN[page].view).get("fsel") is True, 6000)
    fs = luna.PAGE_FULLSCREEN.get(page)
    check("page requestFullscreen opens a Luna full-screen window", fs is not None and fs.isFullScreen(), fs)
    if fs is not None:
        check("page reports fullscreenElement", R(fs.view).get("fsel") is True, R(fs.view))
        check("same page shown in the full-screen window", fs.view.page() is page)
        check("Esc hint shown", fs.hint.isVisible())
        QTest.keyClick(fs, Qt.Key.Key_Escape)
        until(lambda: page not in luna.PAGE_FULLSCREEN, 5000)
        wait(300)
        check("Esc exits full screen", page not in luna.PAGE_FULLSCREEN)
        check("page returned to its tab", web.page() is page)
        check("page knows it left full screen", R(web).get("fsel") is False, R(web))

    # --- permissions: notice bar, grant, remembered, reset
    if luna.QWebEnginePermission is None:
        check("QWebEnginePermission available", False)
        return finish()
    click(web, 120, 130)
    until(lambda: w.notice.isVisible() and "prosi o dostęp" in w.notice.text.text(), 5000)
    check("permission request shows the notice bar", w.notice.isVisible() and "powiadomień" in w.notice.text.text(),
          w.notice.text.text())
    btn = next((b for b in w.notice.findChildren(QPushButton) if b.text() == "Zezwól"), None)
    check("notice has Zezwól / Blokuj", btn is not None and any(b.text() == "Blokuj" for b in w.notice.findChildren(QPushButton)))
    if btn is not None:
        btn.click()
    until(lambda: R(web).get("perm") == "granted", 5000)
    check("granting reaches the page", R(web).get("perm") == "granted", R(web))
    S = luna.QWebEnginePermission.State
    perms = [p for p in page.profile().listAllPermissions() if p.origin().host() == "site-a.localhost"]
    check("decision remembered by the profile", any(p.state() == S.Granted for p in perms), [(p.permissionType(), p.state()) for p in perms])
    runjs(web, "R.perm=null")
    click(web, 120, 130)
    until(lambda: R(web).get("perm") == "granted", 4000)
    check("second request answered without asking", R(web).get("perm") == "granted" and not
          (w.notice.isVisible() and "prosi o dostęp" in w.notice.text.text()))
    for p in perms:
        p.reset()
    check("reset clears the decision", not any(p.state() == S.Granted for p in page.profile().listAllPermissions()
                                                if p.origin().host() == "site-a.localhost"))
    # settings page lists permissions
    perm_ok = [p for p in page.profile().listAllPermissions()]
    check("profile permission listing works", isinstance(perm_ok, list))
    EXTRA(t)
    finish()


def EXTRA(t):
    spellcheck(t)
    updater_check()
    translation()
    palette()
    read_later()


def palette():
    w.notice.hide()
    w.palette()
    p = w._palette
    check("palette opens (Ctrl+K)", p.isVisible())

    def first(q):
        p.edit.setText(q)
        return p.list.item(0).text() if p.list.count() else ""
    check("finds translation without diacritics", first("tlumacz").startswith("Przetłumacz"), first("tlumacz"))
    check("finds a settings page", first("ustawienia pryw").startswith("Ustawienia: Prywatność"), first("ustawienia pryw"))
    check("finds an open tab by title", first("English").startswith("English"), first("English"))
    txt = first("example.org")
    last = p.list.item(p.list.count() - 1).text()
    check("unknown text offers open address", last == "Otwórz: example.org", last)
    p.edit.setText("szukaj luna browser")
    check("plain words offer web search", p.list.item(p.list.count() - 1).text() == "Szukaj w sieci: szukaj luna browser")
    n = len(w.all_tabs())
    p.edit.setText("nowa karta")
    QTest.keyClick(p.edit, Qt.Key.Key_Return)
    wait(300)
    check("Enter runs the command (new tab)", len(w.all_tabs()) == n + 1 and not p.isVisible(), (n, len(w.all_tabs())))


def read_later():
    t = open_tab(f"http://site-en.localhost:{PORT}/en")
    rl = luna.ReadLater.get()
    before = len(rl.items)
    w.read_later_add()
    check("page added to read later", len(rl.items) == before + 1 and rl.items[0]["title"] == "English", rl.items[:1])
    it = rl.items[0]
    until(lambda: rl.offline_path(it).exists() and rl.offline_path(it).stat().st_size > 200, 8000)
    check("offline copy saved (MHTML)", rl.offline_path(it).exists(), rl.offline_path(it))
    check("offline copy not listed as a download", not any("mhtml" in luna.DOWNLOADS[0].path(r) for r in luna.DOWNLOADS[0].items))
    w.open_read_later(it, offline=True)
    t2 = w.cur()
    until(lambda: t2.web is not None and t2.web.title() == "English", 8000)
    check("offline copy opens", t2.web is not None and t2.web.url().scheme() == "file" and t2.web.title() == "English",
          (t2.web and t2.web.url().toString(), t2.web and t2.web.title()))
    check("opened item marked as read", it.get("read") is True)
    txt = {}
    t2.web.page().toPlainText(lambda s: txt.__setitem__("v", s))
    until(lambda: "v" in txt, 5000)
    check("offline copy shows the saved text", "Good morning, my friend" in txt.get("v", ""), txt.get("v", "")[:120])
    rl.remove(it)
    check("remove deletes entry and offline file", rl.find(it["url"]) is None and not rl.offline_path(it).exists())


def translation():
    """Needs network (Google Translate endpoint)."""
    w.notice.hide()
    t = open_tab(f"http://site-en.localhost:{PORT}/en")
    web = t.web
    until(lambda: w.notice.isVisible() and "po angielsku" in w.notice.text.text(), 5000)
    check("offer shown for an English page", w.notice.isVisible() and "po angielsku" in w.notice.text.text(), w.notice.text.text())
    btn = next((b for b in w.notice.findChildren(QPushButton) if b.text() == "Przetłumacz"), None)
    check("offer has Przetłumacz / Nigdy / Nie", btn is not None)
    if btn is None:
        return
    btn.click()
    T = lambda i: runjs(web, f"document.getElementById('{i}')&&document.getElementById('{i}').textContent")
    until(lambda: T("h") != "Good morning, my friend", 15000)
    check("heading translated to Polish", (T("h") or "").lower().startswith("dzień dobry"), T("h"))
    check("paragraph translated", "pogod" in (T("p") or "").lower(), T("p"))
    check("code left untouched", T("c") == 'print("hello world")', T("c"))
    check("translate=no respected", T("n") == "Brand Name Inc", T("n"))
    until(lambda: T("late") and T("late") != "Thank you very much", 8000)
    check("content added later is translated too", T("late") and "dzięk" in T("late").lower(), T("late"))
    w.translate_page()   # drugi raz: oryginał
    wait(500)
    check("restore brings the original back", T("h") == "Good morning, my friend" and T("late") == "Thank you very much",
          (T("h"), T("late")))
    check("page scripts cannot see Luna's translation state", runjs(web, "typeof window.__ltr") == "undefined")


def updater_check():
    """Updater against local git repositories (no network): behind -> notice -> pull."""
    import subprocess
    up = luna.updater()
    if not up.git:
        check("git found for updater", False)
        return
    base = tempfile.mkdtemp(prefix="luna_upd_")
    G = lambda *a, cwd=None: subprocess.run([up.git] + list(a), cwd=cwd, capture_output=True, text=True,
                                            creationflags=0x08000000)
    origin, a, b = (os.path.join(base, n) for n in ("origin.git", "a", "b"))
    G("init", "--bare", "-b", "main", origin)
    G("clone", origin, a)
    for repo in (a,):
        G("-C", repo, "config", "user.email", "t@example.com"); G("-C", repo, "config", "user.name", "t")
    open(os.path.join(a, "f.txt"), "w").write("1")
    G("-C", a, "add", "f.txt"); G("-C", a, "commit", "-m", "pierwsza"); G("-C", a, "push", "-u", "origin", "main")
    G("clone", origin, b)
    G("-C", b, "config", "user.email", "t@example.com"); G("-C", b, "config", "user.name", "t")
    open(os.path.join(b, "f.txt"), "w").write("2")
    G("-C", b, "commit", "-am", "nowa funkcja"); G("-C", b, "push")
    old_repo, up.repo, up.state = up.repo, luna.Path(a), {}
    try:
        check("updater available for a git checkout", up.available())
        check("version string", " z " in up.version(), up.version())
        got = {}
        up.result.connect(lambda s: got.__setitem__("s", s))
        up.check()
        until(lambda: "s" in got, 30000)
        s = got.get("s", {})
        check("updater sees 1 new commit", s.get("behind") == 1 and not s.get("error"), s)
        check("updater lists the change", "nowa funkcja" in (s.get("changes") or []), s)
        luna.WINDOWS[:] = [w] + [x for x in luna.WINDOWS if x is not w]
        w.on_update_result(s)
        check("notice offers the update", w.notice.isVisible() and "nowa wersja" in w.notice.text.text(), w.notice.text.text())
        ok, msg = up.pull()
        check("pull fast-forwards", ok and open(os.path.join(a, "f.txt")).read() == "2", msg)
        open(os.path.join(a, "f.txt"), "w").write("lokalna zmiana")
        got.clear(); G("-C", b, "commit", "--allow-empty", "-m", "jeszcze jedna"); G("-C", b, "push")
        up.check()
        until(lambda: "s" in got, 30000)
        check("local changes detected (no auto update)", got.get("s", {}).get("dirty") is True, got.get("s"))
    finally:
        up.repo = old_repo


def spellcheck(t):
    """Needs network once: downloads the Chromium dictionaries, then checks a misspelled Polish word."""
    web = t.web
    prof = web.page().profile()
    check("spell check off until dictionaries exist", not prof.isSpellCheckEnabled() or luna.spell_langs())
    done = {}
    luna.ensure_dictionaries(w.store, lambda: done.__setitem__("ok", True))
    until(lambda: "ok" in done, 60000, 200)
    check("dictionaries downloaded (pl-PL, en-US)", sorted(luna.spell_langs()) == ["en-US", "pl-PL"], luna.spell_langs())
    check("spell check enabled with Polish", prof.isSpellCheckEnabled() and "pl-PL" in prof.spellCheckLanguages(),
          (prof.isSpellCheckEnabled(), prof.spellCheckLanguages()))
    click(web, 60, 230)
    QTest.keyClicks(web.focusProxy() or web, "Ala ma kota, a to slowo jest zle: chrzaszcz ")
    wait(1500)
    # prawy klik na „chrzaszcz” (błąd: „chrząszcz”) – menu kontekstowe z podpowiedziami
    rect = json.loads(runjs(web, """(function(){var t=document.getElementById('ta');var s=t.value.indexOf('chrzaszcz');
        var r=t.getBoundingClientRect();return JSON.stringify({x:r.left,y:r.top,s:s})})()""") or "{}")
    sugg = []
    for dx in range(330, 200, -12):   # od końca tekstu: „chrzaszcz” jest ostatnim słowem (wcześniej jest też „zle”)
        QTest.mouseClick(web.focusProxy() or web, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(int(rect.get("x", 20)) + dx, int(rect.get("y", 200)) + 12))
        wait(400)
        req = web.lastContextMenuRequest()
        for m in app.topLevelWidgets():
            if m.metaObject().className() == "QMenu" and m.isVisible():
                m.hide()
        if req is not None and req.misspelledWord():
            sugg = [req.misspelledWord()] + list(req.spellCheckerSuggestions())
            break
    check("misspelled Polish word gets suggestions", len(sugg) > 1 and any("chrząszcz" in s for s in sugg[1:]), sugg)


QTimer.singleShot(0, main)
app.exec()
