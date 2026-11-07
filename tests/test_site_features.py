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


PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
       b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
       b"4 0 obj<</Length 44>>stream\nBT /F1 18 Tf 20 100 Td (Luna PDF test) Tj ET\nendstream endobj\n"
       b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
YT_PAGE = """<!doctype html><html><head><meta charset=utf-8><title>yt</title></head><body>
<video id=v muted loop src="/v.mp4" style="width:320px;height:180px"></video></body></html>"""
ADDR_PAGE = """<!doctype html><html lang=pl><head><meta charset=utf-8><title>Dostawa</title></head><body><form id=f>
<label for=a1>Imię</label><input id=a1 name="firstName">
<label for=a2>Nazwisko</label><input id=a2 name="lastName">
<input id=a3 autocomplete="street-address" placeholder="Ulica">
<input id=a4 name="zip" placeholder="Kod pocztowy">
<input id=a5 name="miasto" placeholder="Miejscowość">
<input id=a6 type=email name="email">
<input id=a7 type=tel name="telefon">
<input id=pw type=password name="pass"></form>
<script>window.EV=0;document.querySelectorAll('input').forEach(function(i){i.addEventListener('input',function(){window.EV++})})</script>
</body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        ctype = "text/html; charset=utf-8"
        if self.path.startswith("/doc.pdf"):
            b, ctype = PDF, "application/pdf"
        elif self.path.startswith("/v.mp4"):
            b, ctype = open(os.path.join(REPO, "adblock", "res", "noop-1s.mp4"), "rb").read(), "video/mp4"
        elif self.path.startswith("/watch"):
            b = YT_PAGE.encode()
        elif self.path.startswith("/addr"):
            b = ADDR_PAGE.encode()
        else:
            b = (EN_PAGE if self.path.startswith("/en") else PAGE).encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
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
    error_guard()
    pdf_viewer()
    context_menu()
    site_zoom()
    browser_import()
    sponsorblock()
    highlights()
    leak_check()
    address_fill()
    memory_and_animations()


def memory_and_animations():
    A = luna.QWebEngineSettings.WebAttribute
    prof = luna.get_profile("")
    check("instant back off by default (saves RAM)", w.store.feature("instant_back") is False
          and not prof.settings().testAttribute(A.BackForwardCacheEnabled))
    w.store.set_feature("instant_back", True); wait(200)
    check("instant back switch turns the cache on", prof.settings().testAttribute(A.BackForwardCacheEnabled))
    w.store.set_feature("instant_back", False); wait(200)
    # niski poziom wolnej pamięci: usypianie kart nieużywanych od 2 minut (zamiast 15)
    tabs = [t for t in w.all_tabs() if t is not w.cur() and t.main is not None and not t.asleep]
    check("have background tabs to test", len(tabs) >= 2, len(tabs))
    if len(tabs) >= 2:
        old, recent = tabs[0], tabs[1]
        old.last_active = time.time() - 3 * 60; recent.last_active = time.time() - 30
        for t in tabs[2:]:
            t.last_active = time.time()
        w.store.settings.setdefault("features", {})["sleep_tabs"] = True
        real = luna.low_memory
        luna.low_memory = lambda: False
        w._sleep_tick()
        check("normal memory: 3-minute-old tab stays awake (limit 15 min)", not old.asleep)
        luna.low_memory = lambda: True
        w._sleep_tick()
        luna.low_memory = real
        check("low memory: tab unused for 3 min goes to sleep", old.asleep)
        check("low memory: tab used 30 s ago stays awake", not recent.asleep)
    check("low_memory() returns a bool on this system", isinstance(luna.low_memory(), bool))
    E = luna.QEasingCurve.Type
    sb = w.findChildren(luna.Sidebar)
    check("panel slide uses easing", sb and sb[0].anim.easingCurve().type() == E.OutCubic)
    wf = w.findChildren(luna.WidgetFrame)
    check("widget collapse uses easing", wf and wf[0].anim.easingCurve().type() == E.InOutCubic)
    page = luna.scroll_page(luna.QWidget())
    check("settings pages scroll smoothly", isinstance(page, luna.SmoothScroll))


def menu_texts(fn):
    """Uruchamia fn (która otwiera QMenu.popup) i zwraca teksty akcji widocznego menu."""
    from PyQt6.QtWidgets import QMenu
    fn()
    wait(500)
    for m in app.topLevelWidgets():
        if isinstance(m, QMenu) and m.isVisible():
            t = [a.text() for a in m.actions() if a.text()]
            subs = {a.text(): [x.text() for x in a.menu().actions()] for a in m.actions() if a.menu()}
            m.hide()
            return t, subs
    return [], {}


def error_guard():
    luna.install_error_guard()
    QTimer.singleShot(0, lambda: 1 / 0)   # nieobsłużony wyjątek w slocie Qt
    wait(400)
    log = luna.ERROR_LOG.read_text(encoding="utf-8") if luna.ERROR_LOG.exists() else ""
    check("unhandled error in a Qt slot is logged, Luna keeps running", "ZeroDivisionError" in log and w.isVisible())
    check("running marker set (crash detection)", w.store.settings.get("running") is True)


def pdf_viewer():
    n0 = len(luna.DOWNLOADS[0].items)
    t = open_tab(f"http://site-a.localhost:{PORT}/doc.pdf")
    wait(1500)
    check("PDF opens in the tab (not downloaded)", len(luna.DOWNLOADS[0].items) == n0 and t.web is not None
          and t.web.url().toString().endswith("doc.pdf"), (len(luna.DOWNLOADS[0].items), t.web and t.web.url().toString()))


def context_menu():
    t = open_tab(f"http://site-a.localhost:{PORT}/")
    v = t.web
    base = {"link": "", "link_text": "", "media": None, "media_url": "", "sel": "", "edit": False, "miss": "",
            "sugg": [], "image": False, "video": False}
    pos = w.mapToGlobal(QPoint(200, 200))
    txt, _ = menu_texts(lambda: QTest.mouseClick(v.focusProxy() or v, Qt.MouseButton.RightButton,
                                                 Qt.KeyboardModifier.NoModifier, QPoint(700, 400)))
    check("real right-click shows Luna's Polish menu", "Odśwież" in txt and "Zbadaj element" in txt, txt)
    txt, _ = menu_texts(lambda: w.page_context_menu(v, dict(base), "", pos))
    check("page menu is Polish with Luna actions", "Wstecz" in txt and "Odśwież" in txt and any(x.startswith("Przetłumacz stronę na") for x in txt)
          and "Zbadaj element" in txt, txt)
    link = "https://example.com/a?utm_source=x&id=7&fbclid=abc"
    txt, subs = menu_texts(lambda: w.page_context_menu(v, dict(base, link=link), "", pos))
    check("link menu: new tab, split, container, clean link, QR", all(x in txt for x in (
        "Otwórz link w nowej karcie", "Otwórz link w podziale ekranu", "Otwórz link w kontenerze",
        "Kopiuj czysty link (bez śledzenia)", "Kod QR linku")), txt)
    check("clean_url strips trackers, keeps real params", luna.clean_url(link) == "https://example.com/a?id=7", luna.clean_url(link))
    txt, subs = menu_texts(lambda: w.page_context_menu(v, dict(base, sel="Bonjour tout le monde"), "", pos))
    check("selection menu: search, translate, highlight", any(x.startswith("Szukaj „Bonjour") for x in txt)
          and any(x.startswith("Przetłumacz „Bonjour") for x in txt) and "Zakreśl" in subs, (txt, list(subs)))
    txt, _ = menu_texts(lambda: w.page_context_menu(v, dict(base, edit=True, miss="chrzaszcz", sugg=["chrząszcz"]), "", pos))
    check("editable field menu: spelling first, edit actions", txt[:1] == ["chrząszcz"] and "Wklej jako zwykły tekst" in txt, txt)
    # tłumaczenie zaznaczenia z dowolnego języka, wybór języka docelowego
    p = luna.TranslatePopup(w, "日本語のテキストを翻訳します", pos)
    until(lambda: p.out.toPlainText() not in ("Tłumaczę…", ""), 10000)
    check("selection translation: Japanese -> Polish, source detected", "japoński" in p.src.text()
          and p.out.toPlainText() and p.out.toPlainText() != "Tłumaczę…", (p.src.text(), p.out.toPlainText()))
    p.combo.setCurrentIndex(p.combo.findData("de"))
    until(lambda: p.out.toPlainText() not in ("Tłumaczę…", "") and p.combo.currentData() == "de", 10000)
    wait(1500)
    check("target language selectable (all languages)", p.combo.count() >= 100 and luna.translate_target(w.store) == "de",
          (p.combo.count(), luna.translate_target(w.store)))
    w.store.settings["translate_target"] = "pl"
    p.hide()
    check("lang_code maps page tags", luna.lang_code("en-GB") == "en" and luna.lang_code("he") == "iw" and luna.lang_code("zh-Hant") == "zh-TW"
          and luna.lang_code("xx") == "", [luna.lang_code(x) for x in ("en-GB", "he", "zh-Hant", "xx")])


def site_zoom():
    t = open_tab(f"http://zoom-site.localhost:{PORT}/")
    w.zoom(1); w.zoom(1)
    z = t.web.zoomFactor()
    check("zoom remembered for the site", abs(w.store.settings.get("zoom_sites", {}).get("zoom-site.localhost", 0) - z) < 0.01 and z > 1, z)
    t2 = open_tab(f"http://zoom-site.localhost:{PORT}/en")
    check("same site opens with remembered zoom", abs(t2.web.zoomFactor() - z) < 0.01, t2.web.zoomFactor())
    t3 = open_tab(f"http://site-a.localhost:{PORT}/")
    check("other sites stay at 100%", abs(t3.web.zoomFactor() - 1.0) < 0.01, t3.web.zoomFactor())
    w.zoom(0)


def browser_import():
    import sqlite3, base64 as b64
    # wektor testowy NIST (AES-256-GCM, klucz/IV zerowe, 16 B zer)
    ct = luna.aes_gcm(bytes(32), bytes(12), bytes(16), decrypt=False)
    check("AES-GCM (Windows CNG) matches NIST vector", ct[0].hex() == "cea7403d4d606b6e074ec5d3baf39d18"
          and ct[1].hex() == "d0d1c8a799996bf0265b98b5d48ab919", (ct[0].hex(), ct[1].hex()))
    # syntetyczny profil Brave
    local = tempfile.mkdtemp(prefix="luna_fakeapp_")
    os.environ["LOCALAPPDATA"] = local
    root = os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data"); prof = os.path.join(root, "Default")
    os.makedirs(prof)
    key = os.urandom(32)
    json.dump({"os_crypt": {"encrypted_key": b64.b64encode(b"DPAPI" + luna._dpapi(key, True)).decode()},
               "profile": {"info_cache": {"Default": {"name": "Kasper"}}}}, open(os.path.join(root, "Local State"), "w"))
    json.dump({"roots": {"bookmark_bar": {"type": "folder", "name": "Pasek", "children": [
        {"type": "url", "name": "Wikipedia", "url": "https://pl.wikipedia.org/"},
        {"type": "folder", "name": "Praca", "children": [{"type": "url", "name": "GitHub", "url": "https://github.com/"}]}]}}},
              open(os.path.join(prof, "Bookmarks"), "w"))
    db = sqlite3.connect(os.path.join(prof, "History"))
    db.execute("CREATE TABLE urls(id INTEGER PRIMARY KEY, url TEXT, title TEXT, visit_count INT, typed_count INT, last_visit_time INT, hidden INT)")
    db.execute("INSERT INTO urls(url,title,visit_count,typed_count,last_visit_time,hidden) VALUES(?,?,?,?,?,0)",
               ("https://imported.example.org/page", "Zaimportowana strona", 3, 0, (int(time.time()) + 11644473600) * 1000000))
    db.commit(); db.close()
    nonce = os.urandom(12); enc, tag = luna.aes_gcm(key, nonce, "Tajne-Haslo-123".encode(), decrypt=False)
    db = sqlite3.connect(os.path.join(prof, "Login Data"))
    db.execute("CREATE TABLE logins(origin_url TEXT, username_value TEXT, password_value BLOB, blacklisted_by_user INT)")
    db.execute("INSERT INTO logins VALUES(?,?,?,0)", ("https://login.example.org/signin", "kasper", b"v10" + nonce + enc + tag))
    db.execute("INSERT INTO logins VALUES(?,?,?,0)", ("https://new.example.org/", "x", b"v20" + os.urandom(40)))
    db.commit(); db.close()
    profs = luna.chromium_profiles()
    check("Brave profile found by name", any(p[0] == "Brave – Kasper" for p in profs), [p[0] for p in profs])
    d = luna.ImportDialog(w)
    d.combo.setCurrentIndex([p[0] for p in d.profiles].index("Brave – Kasper"))
    d.run()
    check("bookmarks imported with folders", any(b["url"] == "https://github.com/" and b["folder"] == "Pasek zakładek / Praca"
                                                 for b in luna.Bookmarks.items()), luna.Bookmarks.items())
    check("history imported", any(h["url"] == "https://imported.example.org/page" for h in w.store.history))
    got = luna.VAULT[0].find("https://login.example.org", "kasper")
    check("v10 password decrypted into Luna's vault", got is not None and got["pw"] == "Tajne-Haslo-123", got)
    check("v20 (app-bound) password reported, CSV hint shown", "CSV" in d.out.text() and "1 haseł" in d.out.text(), d.out.text())
    csvp = os.path.join(local, "p.csv")
    open(csvp, "w", encoding="utf-8").write("name,url,username,password\nnew,https://new.example.org/,x,Z-csv-pass\n")
    check("CSV password import", luna.import_passwords_csv(csvp) == [{"origin": "https://new.example.org", "user": "x", "pw": "Z-csv-pass"}])
    d.close()


def sponsorblock():
    check("youtube_id parses watch/shorts/youtu.be", luna.youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=3") == "dQw4w9WgXcQ"
          and luna.youtube_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
          and luna.youtube_id("https://www.youtube.com/shorts/abcdefghijk") == "abcdefghijk"
          and luna.youtube_id("https://example.com/watch?v=dQw4w9WgXcQ") == "")
    got = {}
    luna.SponsorBlock.segments(w.store, "dQw4w9WgXcQ", lambda s: got.__setitem__("s", s))
    until(lambda: "s" in got, 15000)
    check("SponsorBlock API answers (hash-prefix query)", isinstance(got.get("s"), list), got)
    # pomijanie: lokalny film 1 s, segment 0,1–0,8 s
    t = open_tab(f"http://site-a.localhost:{PORT}/watch?v=abcdefghijk")
    w.notice.hide()
    luna._safe_js(t.web, luna.SB_JS % (json.dumps([[0.1, 0.8, "sponsor"]]), json.dumps("abcdefghijk"), json.dumps(luna.PW_KEY)))
    wait(300)
    runjs(t.web, "var v=document.getElementById('v');v.currentTime=0;v.play();1")
    until(lambda: w.notice.isVisible() and "Pominięto" in w.notice.text.text(), 6000)
    check("sponsored segment skipped + notice", w.notice.isVisible() and "Pominięto fragment sponsorowany" in w.notice.text.text(),
          w.notice.text.text())


def highlights():
    t = open_tab(f"http://site-hl.localhost:{PORT}/en")
    v = t.web
    runjs(v, "var r=document.createRange();var p=document.getElementById('p').firstChild;r.setStart(p,4);r.setEnd(p,11);"
             "getSelection().removeAllRanges();getSelection().addRange(r);1")
    w.highlight_selection(v, "#fff176")
    until(lambda: luna.Highlights.for_url(v.url().toString()), 4000)
    items = luna.Highlights.for_url(v.url().toString())
    check("highlight saved with text and context", items and items[0]["text"] == "weather" and items[0]["prefix"].endswith("The "), items)
    check("highlight drawn on page", runjs(v, "document.querySelectorAll('mark[data-lhl]').length") == 1)
    t2 = open_tab(f"http://site-hl.localhost:{PORT}/en")
    until(lambda: runjs(t2.web, "document.querySelectorAll('mark[data-lhl]').length") == 1, 5000)
    check("highlight restored on next visit", runjs(t2.web, "document.querySelector('mark[data-lhl]')&&document.querySelector('mark[data-lhl]').textContent") == "weather")
    w.highlight_remove(t2.web, items[0]["id"])
    wait(200)
    check("highlight removed (page and storage)", runjs(t2.web, "document.querySelectorAll('mark[data-lhl]').length") == 0
          and not luna.Highlights.for_url(t2.web.url().toString()))


def leak_check():
    from PyQt6.QtWidgets import QPushButton as B, QLabel as L, QListWidget as LW
    v = luna.VAULT[0]
    v.put("https://weak.example.org", "a", "password")
    v.put("https://strong.example.org", "b", "Xq7#" + os.urandom(12).hex())
    dlg = luna.SettingsDialog(w.store, w.host, w)
    dlg.show_page("passwords"); dlg.show(); wait(500)
    bt = next((b for b in dlg.findChildren(B) if b.text() == "Sprawdź wycieki haseł"), None)
    check("leak check button present", bt is not None)
    if bt is None:
        return
    bt.click()
    lab = lambda: next((x.text() for x in dlg.findChildren(L) if x.text().startswith(("Hasła z wycieków", "Żadne", "Nie udało"))), "")
    until(lambda: lab(), 20000)
    lists = [x for x in dlg.findChildren(LW) if x.isVisible() and x.count() and "w wyciekach" in x.item(0).text()]
    check("breached password found, strong one not", lab().startswith("Hasła z wycieków") and lists
          and any("weak.example.org" in lists[0].item(i).text() for i in range(lists[0].count()))
          and not any("strong.example.org" in lists[0].item(i).text() for i in range(lists[0].count())), (lab(), lists and lists[0].item(0).text()))
    dlg.close()


def address_fill():
    luna.addresses().append({"label": "Dom", "first": "Jan", "last": "Kowalski", "street": "Polna 1", "postal": "00-001",
                             "city": "Warszawa", "country": "Polska", "tel": "500600700", "email": "jan@example.org"})
    luna.VAULT[0].save()
    w.notice.hide()
    t = open_tab(f"http://site-addr.localhost:{PORT}/addr")
    until(lambda: w.notice.isVisible() and "formularz adresu" in w.notice.text.text(), 6000)
    check("address form detected, fill offered", w.notice.isVisible() and "formularz adresu" in w.notice.text.text(), w.notice.text.text())
    btn = next((b for b in w.notice.findChildren(QPushButton) if b.text().startswith("Wypełnij")), None)
    if btn is not None:
        btn.click()
    wait(500)
    vals = json.loads(runjs(t.web, "JSON.stringify(Array.prototype.map.call(document.querySelectorAll('input'),function(i){return i.value}))") or "[]")
    check("fields filled from saved address", vals[:7] == ["Jan", "Kowalski", "Polna 1", "00-001", "Warszawa", "jan@example.org", "500600700"], vals)
    check("password field untouched", vals[7:] == [""], vals)
    check("page sees input events (works with React/Vue forms)", (runjs(t.web, "window.EV") or 0) >= 7, runjs(t.web, "window.EV"))


def palette():
    w.notice.hide()
    w.palette()
    p = w._palette
    check("palette opens (Ctrl+K)", p.isVisible())

    def first(q):
        p.edit.setText(q)
        return p.list.item(0).text() if p.list.count() else ""
    check("finds translation without diacritics", first("przetlumacz").startswith("Przetłumacz"), first("przetlumacz"))
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
    until(lambda: w.notice.isVisible() and "angielski" in w.notice.text.text(), 5000)
    check("offer shown for an English page", w.notice.isVisible() and "Język strony: angielski" in w.notice.text.text(), w.notice.text.text())
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
