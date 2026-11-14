"""Wbudowana, trudna do wykrycia blokada reklam Luny – klej Qt (DESIGN §8).

Moduły bez Qt (używane też przez kompilator w podprocesie):
  catalog (listy), compiler (listy -> build), netfilter (silnik sieciowy), cosmetic (kosmetyka, świat 7),
  scriptlets (świat strony), resources (zasoby zastępcze), psl (Public Suffix List).

Tutaj (Qt, wątek GUI):
  register_scheme()  – losowy schemat na sesję (przed QApplication!), SR = "<schemat>://l/<token>/"
  AdBlock            – następca Shield z luna.py: przechwytywanie zapytań, skrypty per host (LRU),
                       wyskakujące okna, pobieranie list (zapytania warunkowe) i kompilacja w podprocesie.
Każde nasze wywołanie zwrotne z Qt jest w try/except – błąd przepuszcza zapytanie (fail open).
"""
import gc
import hashlib
import json
import marshal
import os
import re
import secrets
import shutil
import sqlite3
import sys
import time
from collections import OrderedDict
from urllib.parse import quote, unquote
from urllib.request import pathname2url

from PyQt6.QtCore import QObject, QTimer, QUrl, QByteArray, QBuffer, QIODevice, QProcess, QProcessEnvironment, pyqtSignal
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtWebEngineCore import (QWebEngineUrlScheme, QWebEngineUrlSchemeHandler, QWebEngineUrlRequestJob,
                                   QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestInfo, QWebEngineScript,
                                   QWebEnginePage, QWebEngineProfile)

from . import catalog, cosmetic, resources, scriptlets
from . import netfilter
from .psl import PSL

# ------------------------------------------------------------------------------------------ schemat
SCHEME = "x" + secrets.token_hex(5)
TOKEN = secrets.token_urlsafe(12)
SR = f"{SCHEME}://l/{TOKEN}/"
SCHEME_OK = False
_ENC = QUrl.ComponentFormattingOption.EncodeUnicode
_FULL = QUrl.ComponentFormattingOption.FullyEncoded
_DENY = QWebEngineUrlRequestJob.Error.UrlNotFound


def register_scheme():
    """Rejestruje schemat zasobów zastępczych. Działa tylko przed utworzeniem QCoreApplication."""
    global SCHEME_OK
    if SCHEME_OK:
        return True
    if QCoreApplication.instance() is not None:
        return False
    try:
        s = QWebEngineUrlScheme(SCHEME.encode())
        s.setSyntax(QWebEngineUrlScheme.Syntax.Host)
        F = QWebEngineUrlScheme.Flag
        s.setFlags(F.SecureScheme | F.ContentSecurityPolicyIgnored | F.CorsEnabled | F.FetchApiAllowed)
        QWebEngineUrlScheme.registerScheme(s)
        SCHEME_OK = True
        scriptlets.configure(sr=SR)
    except Exception:
        SCHEME_OK = False
    return SCHEME_OK


register_scheme()

# ------------------------------------------------------------------------------------------ stałe
RT = netfilter.RT
WORLD = cosmetic.WORLD_ID
LRU_HOSTS = 256
DL_CAP = 25 * 1024 * 1024
COMPILE_TIMEOUT_MS = 180000
_SLD = {"co", "com", "org", "net", "gov", "edu", "ac", "gob"}
_FLAG_JS_OFF = netfilter.JS_OFF | netfilter.DOC | netfilter.EHIDE


def base_domain(host):
    """Jak base_domain() w luna.py (klucze listy wyjątków „shield_allow”)."""
    p = (host or "").lower().strip(".").split(".")
    return ".".join(p[-3:] if len(p) >= 3 and p[-2] in _SLD else p[-2:])


def _rt_map():
    T = QWebEngineUrlRequestInfo.ResourceType
    pairs = {"ResourceTypeMainFrame": RT.DOCUMENT, "ResourceTypeSubFrame": RT.SUBDOCUMENT,
             "ResourceTypeStylesheet": RT.STYLESHEET, "ResourceTypeScript": RT.SCRIPT,
             "ResourceTypeImage": RT.IMAGE, "ResourceTypeFontResource": RT.FONT,
             "ResourceTypeSubResource": RT.OTHER, "ResourceTypeObject": RT.OBJECT, "ResourceTypeMedia": RT.MEDIA,
             "ResourceTypeWorker": RT.SCRIPT, "ResourceTypeSharedWorker": RT.SCRIPT,
             "ResourceTypeServiceWorker": RT.SCRIPT, "ResourceTypePrefetch": RT.OTHER,
             "ResourceTypeFavicon": RT.IMAGE, "ResourceTypeXhr": RT.XHR, "ResourceTypePing": RT.PING,
             "ResourceTypeCspReport": RT.OTHER, "ResourceTypePluginResource": RT.OBJECT,
             "ResourceTypeNavigationPreloadMainFrame": RT.OTHER, "ResourceTypeNavigationPreloadSubFrame": RT.OTHER,
             "ResourceTypeWebSocket": RT.WEBSOCKET, "ResourceTypeJson": RT.XHR, "ResourceTypeUnknown": RT.OTHER}
    out = {}
    for name, v in pairs.items():
        e = getattr(T, name, None)
        if e is not None:
            out[int(e.value)] = v
    workers = set()
    for name in ("ResourceTypeWorker", "ResourceTypeSharedWorker", "ResourceTypeServiceWorker"):
        e = getattr(T, name, None)
        if e is not None:
            workers.add(int(e.value))
    return out, workers


_RT, _WORKERS = _rt_map()
_REDIRECTABLE = {RT.SCRIPT, RT.SUBDOCUMENT, RT.IMAGE, RT.STYLESHEET, RT.MEDIA, RT.XHR}


def _probe_like(url):
    """Czy zapytanie fetch/XHR wygląda na sondę wykrywającą bloker: pobranie skryptu (…/adsbygoogle.js,
    show_ads.js, ad_status.js) albo znanej biblioteki reklamowej. Takim udajemy sukces; resztę blokujemy."""
    if resources.known_library(url):
        return True
    p = url.split("#", 1)[0].split("?", 1)[0].lower()
    return p.endswith(".js")


def _js(v):
    return json.dumps(v, ensure_ascii=True, separators=(",", ":"))


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def _host_keys(host):
    """www.a.example.co.uk -> [www.a.example.co.uk, a.example.co.uk, example.co.uk, co.uk] (bez samego TLD)."""
    p = host.split(".")
    return [".".join(p[i:]) for i in range(len(p) - 1)] or [host]


def _block_page(url, flt):
    u = _esc(url)
    f = _esc(flt or "")
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>Strona zablokowana</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
html,body{{height:100%;margin:0}}body{{display:flex;align-items:center;justify-content:center;background:#111;color:#ececec;
font:15px/1.5 system-ui,'Segoe UI',sans-serif}}main{{max-width:620px;padding:32px}}h1{{font-size:22px;margin:0 0 8px}}
p{{color:#bdbdbd}}code{{display:block;background:#1d1d1d;border-radius:8px;padding:10px 12px;word-break:break-all;
color:#9a9a9a;font-size:12px}}a.b{{display:inline-block;margin:18px 10px 0 0;padding:9px 16px;border-radius:9px;
background:#2a2a2a;color:#ececec;text-decoration:none}}a.b.p{{background:#ececec;color:#111}}</style></head><body><main>
<h1>Luna zablokowała tę stronę</h1>
<p>Adres pasuje do filtra blokującego reklamy, śledzenie albo złośliwe strony. Jeśli ufasz tej stronie, możesz
przejść mimo to – do końca tej sesji Luna nie będzie już jej blokować.</p>
<code>{u}</code>{"<p>Filtr:</p><code>" + f + "</code>" if f else ""}
<a class="b" href="javascript:history.back()">Wróć</a><a class="b p" href="{u}">Przejdź mimo to</a>
</main></body></html>""".encode("utf-8")


# ------------------------------------------------------------------------------------------ Qt: schemat
class _SchemeHandler(QWebEngineUrlSchemeHandler):
    def __init__(self, ab):
        super().__init__(ab)
        self.ab = ab

    def requestStarted(self, job):
        try:
            self._serve(job)
        except Exception:
            try:
                job.fail(QWebEngineUrlRequestJob.Error.RequestFailed)
            except Exception:
                pass

    def _reply(self, job, mime, body):
        try:
            if hasattr(job, "setAdditionalResponseHeaders"):
                job.setAdditionalResponseHeaders({QByteArray(b"Access-Control-Allow-Origin"): QByteArray(b"*")})
        except Exception:
            pass
        buf = QBuffer(job)
        buf.setData(QByteArray(body))
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(mime.encode("ascii", "replace"), buf)

    def _serve(self, job):
        u = job.requestUrl()
        path = u.path(_FULL)
        pre = "/" + TOKEN + "/"
        if u.host() != "l" or not path.startswith(pre):
            job.fail(_DENY)
            return
        rest = path[len(pre):]
        method = bytes(job.requestMethod()).decode("latin-1").upper() or "GET"
        if rest.startswith("r/"):
            r = resources.get(unquote(rest[2:]))
            if r is None:
                job.fail(_DENY)
                return
            self._reply(job, r[0], b"" if method == "HEAD" else r[1])
        elif rest == "c":
            self._reply(job, "application/json", cosmetic.lookup_json(u.query(_FULL)))
        elif rest.startswith("x/"):
            r = scriptlets.fake_body(rest[2:], method)
            if r is None:
                job.fail(_DENY)
                return
            self._reply(job, r[0], r[1])
        elif rest == "blocked":
            q = {}
            for part in u.query(_FULL).split("&"):
                k, _, v = part.partition("=")
                q[k] = unquote(v)
            target = q.get("u", "")
            if not re.match(r"^https?://", target, re.I):
                target = ""
            self._reply(job, "text/html; charset=utf-8", _block_page(target, q.get("f", "")))
        else:
            job.fail(_DENY)


class _Interceptor(QWebEngineUrlRequestInterceptor):
    """Osobny dla każdego profilu (wie, do którego profilu należy zapytanie)."""

    def __init__(self, ab, profile):
        super().__init__(profile)
        self.ab, self.profile = ab, profile

    def interceptRequest(self, info):
        for hook in REQUEST_HOOKS:   # dodatkowe reguły programu (np. nagłówki dla logowania Google)
            try:
                hook(info)
            except Exception:
                pass
        try:
            self.ab._intercept(info, self.profile)
        except Exception:
            pass   # fail open


REQUEST_HOOKS = []   # funkcje(info) wywoływane dla każdego zapytania, przed blokadą


class _PState:
    __slots__ = ("profile", "icpt", "static", "lru")

    def __init__(self, profile, icpt):
        self.profile, self.icpt = profile, icpt
        self.static = None
        self.lru = OrderedDict()   # host -> [QWebEngineScript, ...]


YT_START_HOSTS = {"www.youtube.com", "m.youtube.com"}
_YT_START = []


def _yt_start_src():
    """Treść js/youtube_start.js (wczytywana raz) albo ""."""
    if not _YT_START:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "js", "youtube_start.js"), encoding="utf-8") as f:
                _YT_START.append(f.read())
        except OSError:
            _YT_START.append("")
    return _YT_START[0]


def _mk_script(src, world):
    s = QWebEngineScript()
    s.setName("")
    s.setSourceCode(src)
    s.setWorldId(world)
    s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    s.setRunsOnSubFrames(True)
    return s


# ------------------------------------------------------------------------------------------ AdBlock
class AdBlock(QObject):
    """Blokada reklam i śledzenia. Publiczne API zgodne z dawnym Shield: on, allow, total, blocked, domains,
    count(url), reset(url), reload(), update_list(done), maybe_update(); nowe: install(profile),
    prepare(page|profile, url, is_main), popup_blocked(url, opener_url), set_list_enabled, set_user_filters."""
    status_changed = pyqtSignal()

    def __init__(self, store, home=None, legacy_domains=(), legacy_file=None, parent=None):
        super().__init__(parent or QCoreApplication.instance())
        self.store = store
        self.home = str(home) if home else os.path.expanduser("~")
        self.root = catalog.root(self.home)
        self.legacy = set(legacy_domains or ())
        self.legacy_file = legacy_file
        self.domains = set(self.legacy)
        self.blocked = {}
        self.by_domain = {}          # host strony -> {domena zapytania: liczba} (panel „co zablokowano”)
        self.exc = {}                # wyjątki per strona: domena strony -> {domeny przepuszczane}
        self.total = int(store.settings.get("shield_total", 0) or 0)
        self.on, self.allow = True, set()
        self.net = None              # NetEngine z bieżącego buildu (None = tryb awaryjny: TRACKERS + lista PGL)
        self.db = None
        self.psl = PSL(None)
        self.info = {}
        self.build_dir = None
        self._re_hosts = []          # [(re, key)] dla kluczy /regex/ w site.db
        self._profiles = {}
        self._hcache = OrderedDict()  # host -> [(world, source)] wspólne dla profili
        self._static_src = None
        self._doc_ok = set()         # hosty $document dopuszczone przyciskiem „Przejdź mimo to” (sesja)
        self.handler = _SchemeHandler(self) if SCHEME_OK else None
        self.meta = catalog.load_meta(self.home)
        self.state = ""              # "" | "pobieranie" | "kompilacja"
        self.error = ""
        self._dl_pending = 0
        self._dl_changed = False
        self._dl_failed = []
        self._dl_running = False
        self._dl_done = []
        self._proc = None
        self._compile_again = False
        self._nam = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.maybe_update)
        self._recfg = QTimer(self)
        self._recfg.setSingleShot(True)
        self._recfg.timeout.connect(self._reconfigure_now)
        self._load_legacy()
        self.reload(initial=True)
        self._loaded = False
        if self.on:   # wyłączona blokada: nie wczytujemy filtrów (zrobi to reload() po włączeniu)
            self._ensure_loaded()

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True
        try:
            self._load_latest()
        except Exception:
            self.net = None

    # ---------------------------------------------------------------- stan / ustawienia
    def _load_legacy(self):
        d = set(self.legacy)
        if self.legacy_file:
            try:
                with open(self.legacy_file, encoding="utf-8") as f:
                    d |= {x.strip().lower() for x in f.read().split() if "." in x and not x.startswith("#")}
            except OSError:
                pass
        self.domains = d

    def reload(self, initial=False):
        """Ponownie czyta ustawienia (włączenie funkcji, wyjątki). Skrypty odświeżane tylko przy zmianie."""
        try:
            on = bool(self.store.feature("adblock"))
        except Exception:
            on = True
        allow = set(self.store.settings.get("shield_allow", []) or [])
        changed = (on != self.on) or (allow != self.allow)
        self.on, self.allow = on, allow
        self._load_exc()
        if not initial:
            self._load_legacy()
            if on and not getattr(self, "_loaded", True):
                self._ensure_loaded()   # włączono po starcie z wyłączoną blokadą
            if on and changed and self.net is None and not self._dl_running:
                QTimer.singleShot(2000, self.maybe_update)   # brak list: pobierz po włączeniu
            if changed:
                self._refresh_scripts()
                self.status_changed.emit()

    # ---------------------------------------------------------------- wyjątki per strona (panel tarczy)
    def _load_exc(self):
        raw = self.store.settings.get("shield_exc") or {}
        out = {}
        if isinstance(raw, dict):
            for site, doms in raw.items():
                if isinstance(site, str) and isinstance(doms, list):
                    s = {d for d in doms if isinstance(d, str) and d}
                    if s:
                        out[site] = s
        self.exc = out

    def site_exceptions(self, url):
        """Domeny odblokowane na stronie url (posortowane)."""
        return sorted(self.exc.get(base_domain(QUrl(str(url)).host(_ENC)), ()))

    def set_site_exception(self, url, domain, allowed):
        """Przepuszcza (allowed=True) albo znów blokuje zapytania do domain na stronie url. Działa od razu,
        bez przebudowy filtrów; zapisywane w ustawieniach („shield_exc”)."""
        site = base_domain(QUrl(str(url)).host(_ENC))
        domain = base_domain(domain)
        if not site or not domain:
            return
        raw = {k: list(v) for k, v in self.exc.items()}
        cur = set(raw.get(site, []))
        cur = (cur | {domain}) if allowed else (cur - {domain})
        if cur:
            raw[site] = sorted(cur)
        else:
            raw.pop(site, None)
        self.store.settings["shield_exc"] = raw
        try:
            self.store.save_soon()
        except Exception:
            pass
        self._load_exc()
        if allowed:
            d = self.by_domain.get(QUrl(str(url)).host(_ENC).lower().rstrip("."), {})
            d.pop(domain, None)
        self.status_changed.emit()

    def breakdown(self, url):
        """[(domena, liczba)] zablokowane na stronie url od ostatniego wczytania, najczęstsze najpierw."""
        d = self.by_domain.get(QUrl(str(url)).host(_ENC).lower().rstrip("."), {})
        return sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))

    def enabled_ids(self):
        return catalog.enabled_ids(self.store.settings.get("adblock_lists") or {})

    def user_filters(self):
        v = self.store.settings.get("adblock_user") or ""
        return v if isinstance(v, str) else ""

    def set_list_enabled(self, list_id, enabled):
        m = dict(self.store.settings.get("adblock_lists") or {})
        m[list_id] = bool(enabled)
        self.store.settings["adblock_lists"] = m
        self.store.save_soon()
        self.reconfigure()

    def set_user_filters(self, text):
        self.store.settings["adblock_user"] = text or ""
        self.store.save_soon()
        self.reconfigure()

    def reconfigure(self):
        """Zmiana list / własnych filtrów: dociągnij brakujące listy i przebuduj (z opóźnieniem 1,5 s)."""
        self._recfg.start(1500)

    def _reconfigure_now(self):
        self._start_updates(force=False, need_build=True)

    def rules_total(self):
        try:
            return int(self.info.get("total") or 0)
        except Exception:
            return 0

    def list_count(self, list_id):
        return int((self.info.get("counts") or {}).get(list_id, 0) or 0)

    def last_update(self):
        ts = [float((self.meta.get(i) or {}).get("fetched") or 0) for i in self.enabled_ids()]
        ts = [t for t in ts if t]
        return max(ts) if ts else 0.0

    def status_text(self):
        if self.state == "pobieranie":
            return "Pobieranie list filtrów…"
        if self.state == "kompilacja":
            return "Przygotowywanie filtrów…"
        if self.error:
            return self.error
        return ""

    # ---------------------------------------------------------------- profile i skrypty
    def install(self, profile):
        if profile in self._profiles:
            return
        icpt = _Interceptor(self, profile)
        profile.setUrlRequestInterceptor(icpt)
        if self.handler is not None:
            try:
                profile.installUrlSchemeHandler(SCHEME.encode(), self.handler)
            except Exception:
                pass
        st = _PState(profile, icpt)
        self._profiles[profile] = st
        try:
            profile.destroyed.connect(lambda _=None, p=profile: self._profiles.pop(p, None))
        except Exception:
            pass
        self._install_static(st)

    def _active(self):
        return self.on and self.net is not None

    def _install_static(self, st):
        if st.static is not None:
            try:
                st.profile.scripts().remove(st.static)
            except Exception:
                pass
            st.static = None
        if not self._active():
            return
        if self._static_src is None:
            self._static_src = cosmetic.static_script({"sr": SR if SCHEME_OK else "", "allow": sorted(self.allow)})
        st.static = _mk_script(self._static_src, WORLD)
        st.profile.scripts().insert(st.static)

    def _clear_host_scripts(self, st):
        sc = st.profile.scripts()
        for lst in st.lru.values():
            for s in lst:
                try:
                    sc.remove(s)
                except Exception:
                    pass
        st.lru.clear()

    def _refresh_scripts(self):
        """Dane/wyjątki/włączenie zmienione: usuń skrypty hostów, wstaw nowy skrypt statyczny."""
        self._hcache.clear()
        self._static_src = None
        for st in list(self._profiles.values()):
            try:
                self._clear_host_scripts(st)
                self._install_static(st)
            except Exception:
                pass

    def prepare(self, target, url, is_main=True):
        """Z LunaPage.acceptNavigationRequest (główne źródło – widzi też nawigacje z service workera) i jako
        zapas z interceptora (MainFrame/SubFrame). Wstawia małe skrypty dla hosta do profilu (LRU)."""
        try:
            if not self._active():
                return
            prof = target.profile() if isinstance(target, QWebEnginePage) else target
            st = self._profiles.get(prof)
            if st is None:
                return
            q = url if isinstance(url, QUrl) else QUrl(str(url))
            if q.scheme() not in ("http", "https"):
                return
            host = q.host(_ENC).lower().rstrip(".")
            if not host:
                return
            lru = st.lru
            if host in lru:
                lru.move_to_end(host)
                return
            srcs = self._hcache.get(host)
            if srcs is None:
                srcs = self._host_sources(host, bytes(q.toEncoded()).decode("ascii", "replace"))
                self._hcache[host] = srcs
                while len(self._hcache) > 2 * LRU_HOSTS:
                    self._hcache.popitem(last=False)
            else:
                self._hcache.move_to_end(host)
            scripts = []
            sc = prof.scripts()
            for world, src in srcs:
                s = _mk_script(src, world)
                sc.insert(s)
                scripts.append(s)
            lru[host] = scripts
            while len(lru) > LRU_HOSTS:
                _, old = lru.popitem(last=False)
                for s in old:
                    try:
                        sc.remove(s)
                    except Exception:
                        pass
        except Exception:
            pass

    def _rows(self, keys):
        if self.db is None or not keys:
            return {}
        try:
            cur = self.db.execute("SELECT key, data FROM site WHERE key IN (%s)" % ",".join("?" * len(keys)), keys)
            out = {}
            for k, d in cur:
                try:
                    out[k] = json.loads(d)
                except ValueError:
                    pass
            return out
        except Exception:
            return {}

    def _host_sources(self, host, url):
        """-> [(world, source)] dla hosta: scriptlety (świat strony), kosmetyka (świat 7), scriptlety ramek
        osadzonych w tym hoście (>>host)."""
        out = []
        flags = 0
        try:
            flags = self.net.page_flags(url, host)
        except Exception:
            pass
        hk = _host_keys(host)
        ek = self.psl.entity_keys(host)
        keys = hk + ek
        rx = [k for r, k in self._re_hosts if r.search(host)]
        anc = [">>" + k for k in hk + ek]
        rows = self._rows(keys + rx + anc)
        own = [rows[k] for k in keys + rx if k in rows]
        anc_rows = [rows[k] for k in anc if k in rows]
        allow = sorted(self.allow)
        # --- scriptlety (MAIN world), z gardą hosta i wyjątków
        if not flags & _FLAG_JS_OFF:
            src = self._scriptlet_bundle(own, host)
            if src:
                out.append((QWebEngineScript.ScriptWorldId.MainWorld.value,
                            "(function(){if(location.hostname!==" + _js(host) + ")return;" + self._allow_guard(allow)
                            + src + "})();\n//# sourceURL=<anonymous>"))
            if anc_rows:
                src = self._scriptlet_bundle(anc_rows, host)
                if src:
                    out.append((QWebEngineScript.ScriptWorldId.MainWorld.value,
                                "(function(){var a=location.ancestorOrigins,H=" + _js(host) + ",k=false;"
                                "if(!a||!a.length)return;for(var i=0;i<a.length;i++){var h;try{h=new URL(a[i]).hostname;}"
                                "catch(e){continue;}if(h===H||(h.length>H.length&&h.slice(-H.length-1)===\".\"+H)){k=true;break;}}"
                                "if(!k)return;" + self._allow_guard(allow) + src + "})();\n//# sourceURL=<anonymous>"))
            if host in YT_START_HOSTS:   # YouTube: przeładowanie filmu wstrzymanego po usunięciu reklamy (js/youtube_start.js)
                yt = _yt_start_src()
                if yt:
                    out.append((QWebEngineScript.ScriptWorldId.MainWorld.value,
                                "(function(){if(location.hostname!==" + _js(host) + ")return;" + self._allow_guard(allow)
                                + yt + "})();\n//# sourceURL=<anonymous>"))
        # --- kosmetyka (świat 7)
        if own or flags:
            try:
                data = cosmetic.host_data(own, flags)
                if len(data) > 1 or data.get("flags"):
                    out.append((WORLD, cosmetic.host_script(host, data)))
            except Exception:
                pass
        return out

    @staticmethod
    def _allow_guard(allow):
        if not allow:
            return ""
        return ("var t=location.hostname;try{if(window.top!==window){var o=location.ancestorOrigins;"
                "if(o&&o.length)t=new URL(o[o.length-1]).hostname;}}catch(e){}var A=" + _js(allow) + ";"
                "for(var j=0;j<A.length;j++){var d=A[j];if(t===d||(t.length>d.length&&t.slice(-d.length-1)===\".\"+d))return;}")

    @staticmethod
    def _scriptlet_bundle(rows, host):
        rules, un, unall = [], set(), False
        for r in rows:
            for e in r.get("unjs") or ():
                if isinstance(e, list) and e:
                    if e[0] == "*":
                        unall = True
                    elif len(e) >= 2 and isinstance(e[1], list):
                        un.add((e[0], tuple(str(a) for a in e[1])))
        if unall:
            return None
        for r in rows:
            for e in r.get("js") or ():
                if not isinstance(e, list) or len(e) < 2 or not isinstance(e[1], list):
                    continue
                if (e[0], tuple(str(a) for a in e[1])) in un:
                    continue
                rules.append((e[0], e[1], bool(e[2]) if len(e) > 2 else False))
        if not rules:
            return None
        try:
            return scriptlets.build(rules, host)
        except Exception:
            return None

    # ---------------------------------------------------------------- przechwytywanie zapytań
    def _count(self, fp_host, host=""):
        self.blocked[fp_host] = self.blocked.get(fp_host, 0) + 1
        if host:
            d = self.by_domain.setdefault(fp_host, {})
            b = base_domain(host)
            if b in d or len(d) < 500:
                d[b] = d.get(b, 0) + 1
        self.total += 1
        try:
            self.store.settings["shield_total"] = self.total
        except Exception:
            pass

    def _intercept(self, info, profile):
        if not self.on:
            return
        u = info.requestUrl()
        sch = u.scheme()
        if sch not in ("http", "https", "ws", "wss"):
            return
        rti = int(info.resourceType().value)
        rt = _RT.get(rti, RT.OTHER)
        host = u.host(_ENC).lower().rstrip(".")
        if rt == RT.DOCUMENT:
            fp_host = host
        else:
            fp_host = info.firstPartyUrl().host(_ENC).lower().rstrip(".") or host
        fp_base = base_domain(fp_host)
        if fp_base in self.allow:
            return
        if self.exc:
            ex = self.exc.get(fp_base)
            if ex and base_domain(host) in ex:   # domena odblokowana na tej stronie (panel tarczy)
                return
        net = self.net
        if net is None:   # tryb awaryjny (brak skompilowanych list): stara blokada domen z cudzych stron
            if host and fp_host and base_domain(host) != fp_base:
                parts = host.split(".")
                for i in range(len(parts) - 1):
                    if ".".join(parts[i:]) in self.domains:
                        info.block(True)
                        self._count(fp_host, host)
                        return
            return
        if rt == RT.DOCUMENT or rt == RT.SUBDOCUMENT:
            self.prepare(profile, u, rt == RT.DOCUMENT)
            ini = info.initiator()
            if ini.scheme() == SCHEME:   # „Przejdź mimo to” / click2load z naszych stron
                if rt == RT.DOCUMENT:
                    self._doc_ok.add(host)
                return
        url = bytes(u.toEncoded()).decode("ascii", "replace")
        method = bytes(info.requestMethod()).decode("latin-1") or "GET"
        res = net.match(url, host, fp_host, rt, method)
        if res is None:
            return
        kind = res[0]
        if kind == "removeparam":
            info.redirect(QUrl.fromEncoded(res[1].encode("ascii", "replace")))
            return
        if rt == RT.DOCUMENT:
            if host in self._doc_ok or info.isDownload():
                return
            self._count(fp_host, host)
            if SCHEME_OK:
                info.redirect(QUrl.fromEncoded((SR + "blocked?u=" + quote(url, safe="") + "&f=" +
                                                quote(res[-1][:500], safe="")).encode("ascii")))
            else:
                info.block(True)
            return
        if (rt == RT.XHR and kind != "removeparam" and method.upper() == "HEAD" and SCHEME_OK
                and resources.known_library(url)):
            # sonda HEAD do znanej biblioteki (np. adsbygoogle.js): XHR w trybie CORS nie da się w Qt podmienić,
            # a błąd zdradza bloker – przepuszczamy (HEAD nie zwraca treści, nic nie jest wykonywane)
            return
        self._count(fp_host, host)
        if SCHEME_OK and rt in _REDIRECTABLE and rti not in _WORKERS:
            name = None
            if kind == "redirect":
                name = resources.canonical(res[1])
                if rt == RT.XHR and str(res[-1]).startswith("*") and not _probe_like(url):
                    # ogólna reguła uBO „*$xhr,3p,method=head,redirect-rule=nooptext” udaje sukces KAŻDEGO
                    # zablokowanego HEAD – także do trackerów i telemetrii, których nikt nie używa jako sondy.
                    # Zostawiamy ją tylko dla sond (skrypty reklamowe); resztę naprawdę blokujemy
                    name = resources.NONE
            if name is None or name == resources.NONE:
                if rt == RT.XHR and not _probe_like(url):
                    # fetch/XHR do trackerów, telemetrii, API reklam: zwykły błąd sieci jak w uBO/Brave.
                    # Udawana odpowiedź zostaje tylko dla sond anty-adblock (pobranie skryptu reklamowego)
                    info.block(True)
                    return
                name = resources.known_library(url, rt) or resources.default_for(rt, url)
            if name and resources.get(name) is not None:
                tgt = SR + "r/" + quote(name, safe="")
                if name == "click2load.html":
                    tgt += "?url=" + quote(url, safe="")
                info.redirect(QUrl.fromEncoded(tgt.encode("ascii")))
                return
        info.block(True)

    def popup_blocked(self, url, opener_url=""):
        """True, gdy filtr $popup blokuje otwarcie url ze strony opener_url (WebView.createWindow/_grab)."""
        try:
            if not self._active():
                return False
            q = url if isinstance(url, QUrl) else QUrl(str(url))
            if q.scheme() not in ("http", "https"):
                return False
            o = opener_url if isinstance(opener_url, QUrl) else QUrl(str(opener_url or ""))
            oh = o.host(_ENC).lower()
            if oh and base_domain(oh) in self.allow:
                return False
            host = q.host(_ENC).lower()
            if self.net.popup(bytes(q.toEncoded()).decode("ascii", "replace"), host, oh or host):
                self._count(oh or host, host)
                return True
        except Exception:
            pass
        return False

    def count(self, url):
        return self.blocked.get(QUrl(url).host(_ENC).lower(), 0)

    def reset(self, url):
        h = QUrl(url).host(_ENC).lower()
        self.blocked.pop(h, None)
        self.by_domain.pop(h, None)

    # ---------------------------------------------------------------- buildy
    def _builds(self):
        out = []
        try:
            for n in os.listdir(self.root):
                m = re.fullmatch(r"build-(\d+)", n)
                if m and os.path.isdir(os.path.join(self.root, n)):
                    out.append((int(m.group(1)), os.path.join(self.root, n)))
        except OSError:
            pass
        return sorted(out)

    def _load_latest(self):
        for _, d in reversed(self._builds()):
            if os.path.isfile(os.path.join(d, "info.json")) and os.path.isfile(os.path.join(d, "net.bin")):
                try:
                    self._swap(self._read_build(d))
                    return True
                except Exception:
                    continue
        return False

    @staticmethod
    def _read_build(d):
        # marshal.loads(całość) jest ok. 10x szybsze niż marshal.load(plik); GC wyłączony na czas tworzenia
        # ~100k kontenerów (inaczej kilka pełnych przebiegów GC na wątku GUI)
        was = gc.isenabled()
        gc.disable()
        try:
            with open(os.path.join(d, "net.bin"), "rb") as f:
                net = netfilter.NetEngine.from_dict(marshal.loads(f.read()))
            try:
                with open(os.path.join(d, "cos.bin"), "rb") as f:
                    cos = marshal.loads(f.read())
            except OSError:
                cos = {}
        finally:
            if was:
                gc.enable()
        with open(os.path.join(d, "info.json"), encoding="utf-8") as f:
            info = json.load(f)
        db = None
        p = os.path.join(d, "site.db")
        if os.path.isfile(p):
            db = sqlite3.connect("file:" + pathname2url(os.path.abspath(p)) + "?mode=ro&immutable=1", uri=True)
        pp = os.path.join(d, "psl.bin")
        ps = PSL.load(pp) if os.path.isfile(pp) else PSL(None)
        rxs = []
        if db is not None:
            try:
                row = db.execute("SELECT data FROM site WHERE key='/'").fetchone()
                for k in (json.loads(row[0]).get("re") or []) if row else []:
                    try:
                        rxs.append((re.compile(k[1:-1]), k))
                    except re.error:
                        pass
            except Exception:
                pass
        return {"dir": d, "net": net, "cos": cos, "info": info, "db": db, "psl": ps, "re": rxs}

    def _swap(self, b):
        old_db = self.db
        b["net"].set_registrable(b["psl"].registrable if b["psl"].data else None)
        was = gc.isenabled()
        gc.disable()
        try:
            cosmetic.load(b["cos"])
        finally:
            if was:
                gc.enable()
        self.net, self.db, self.psl, self.info = b["net"], b["db"], b["psl"], b["info"]
        self._re_hosts, self.build_dir = b["re"], b["dir"]
        if old_db is not None:
            try:
                old_db.close()
            except Exception:
                pass
        self._refresh_scripts()
        gc.freeze()   # ~100k obiektów silnika poza pełnym GC (inaczej ok. 30 ms pauzy)
        QTimer.singleShot(1500, self._warm)
        self._cleanup_builds()
        self.status_changed.emit()

    @staticmethod
    def _warm():
        """Po starcie, w wolnej chwili: wczytaj pliki scriptletów do pamięci (pierwszy host nie czeka na dysk)."""
        try:
            scriptlets.runtime_source()
            scriptlets.available()
        except Exception:
            pass

    def _cleanup_builds(self):
        """Usuwa stare buildy (i resztki .tmp/.err/.json) poza bieżącym i właśnie kompilowanym."""
        keep = {os.path.basename(self.build_dir or "")}
        if self._proc is not None:
            keep.add(getattr(self, "_out_name", ""))
        try:
            for n in os.listdir(self.root):
                p = os.path.join(self.root, n)
                if n.split(".")[0] in keep:
                    continue
                if re.fullmatch(r"build-\d+(\.tmp|\.err|\.json)?", n):
                    if os.path.isdir(p):
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        try:
                            os.remove(p)
                        except OSError:
                            pass
        except OSError:
            pass

    # ---------------------------------------------------------------- aktualizacje list
    def maybe_update(self):
        """Odroczone sprawdzenie po starcie, potem pojedynczy timer do najbliższego wygaśnięcia (bez odpytywania)."""
        try:
            if not self.on:
                return
            self._start_updates(force=False)
        except Exception:
            pass

    def update_list(self, done=None):
        """„Zaktualizuj teraz”: pobierz wszystkie włączone listy (zapytania warunkowe) i przebuduj przy zmianach.
        done(ok) po zakończeniu."""
        if done:
            self._dl_done.append(done)
        self._start_updates(force=True)

    def _ids_with_psl(self):
        return self.enabled_ids() + ["psl"]

    def _due(self, list_id, now):
        lst = catalog.get(list_id)
        m = self.meta.get(list_id) or {}
        if not os.path.isfile(catalog.list_path(list_id, self.home)):
            return now >= float(m.get("tried") or 0) + 600 or not m.get("tried")
        if m.get("ok") is False and float(m.get("tried") or 0) + 3600 > now:
            return False
        return now >= float(m.get("fetched") or 0) + lst["expires_h"] * 3600

    def _sig(self):
        parts = {"ids": self.enabled_ids(), "user": hashlib.sha1(self.user_filters().encode("utf-8")).hexdigest(),
                 "files": {}}
        lp = catalog.luna_list_path()   # zmiana wbudowanych poprawek (aktualizacja Luny) → przebudowa
        if lp:
            try:
                parts["luna"] = hashlib.sha1(open(lp, "rb").read()).hexdigest()
            except OSError:
                pass
        for i in self._ids_with_psl():
            lst = catalog.get(i)
            paths = [catalog.list_path(i, self.home)] + [catalog.include_path(i, n, self.home) for n in lst["includes"]]
            for p in paths:
                try:
                    s = os.stat(p)
                    parts["files"][os.path.basename(p)] = [s.st_size, s.st_mtime_ns]
                except OSError:
                    pass
        return hashlib.sha1(json.dumps(parts, sort_keys=True).encode()).hexdigest()

    def _start_updates(self, force=False, need_build=False):
        self._need_build = getattr(self, "_need_build", False) or need_build
        if self._dl_running:
            self._dl_force_again = getattr(self, "_dl_force_again", False) or force
            return
        now = time.time()
        ids = [i for i in self._ids_with_psl() if force or self._due(i, now)]
        self._dl_running = True
        self._dl_changed = False
        self._dl_failed = []
        self._dl_pending = 0
        if ids:
            self.state = "pobieranie"
            self.error = ""
            self.status_changed.emit()
        for i in ids:
            lst = catalog.get(i)
            self._dl_pending += 1
            self._fetch(i, lst["url"], lst.get("fallback"), catalog.list_path(i, self.home), lst)
        if self._dl_pending == 0:
            QTimer.singleShot(0, self._downloads_finished)

    def _fetch(self, key, url, fallback, dest, lst, parent=None):
        if self._nam is None:
            self._nam = QNetworkAccessManager(self)
        req = QNetworkRequest(QUrl(url))
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "Mozilla/5.0")
        req.setTransferTimeout(60000)
        m = self.meta.get(key) or {}
        if os.path.isfile(dest):
            if m.get("etag"):
                req.setRawHeader(b"If-None-Match", m["etag"].encode("latin-1", "replace"))
            if m.get("last_modified"):
                req.setRawHeader(b"If-Modified-Since", m["last_modified"].encode("latin-1", "replace"))
        if not url.lower().startswith("https://"):
            self._fetch_done(key, None, None, fallback, dest, lst, parent)
            return
        r = self._nam.get(req)

        def prog(rec, tot, r=r):
            if rec > DL_CAP or tot > DL_CAP:
                r.abort()
        r.downloadProgress.connect(prog)
        r.finished.connect(lambda r=r: self._fetch_done(key, r, url, fallback, dest, lst, parent))

    def _fetch_done(self, key, r, url, fallback, dest, lst, parent):
        ok, changed = False, False
        try:
            m = dict(self.meta.get(key) or {})
            if r is not None:
                status = r.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                final = r.url().scheme().lower()
                err = r.error()
                if final == "https" and status == 304 and os.path.isfile(dest):
                    ok = True
                elif final == "https" and err == QNetworkReply.NetworkError.NoError and status == 200:
                    data = bytes(r.readAll())
                    if self._valid_list(data, lst):
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        old = None
                        try:
                            with open(dest, "rb") as f:
                                old = hashlib.sha1(f.read()).digest()
                        except OSError:
                            pass
                        if old != hashlib.sha1(data).digest():
                            tmp = dest + ".tmp"
                            with open(tmp, "wb") as f:
                                f.write(data)
                            os.replace(tmp, dest)
                            changed = True
                        ok = True
                        et = bytes(r.rawHeader(b"ETag")).decode("latin-1")
                        lm = bytes(r.rawHeader(b"Last-Modified")).decode("latin-1")
                        m["etag"], m["last_modified"] = et or None, lm or None
                r.deleteLater()
            now = time.time()
            if ok:
                m.update(fetched=now, ok=True, tried=now)
                self.meta[key] = m
            elif fallback:
                self._fetch(key, fallback, None, dest, lst, parent)
                return
            else:
                m.update(ok=False, tried=now)
                self.meta[key] = m
                self._dl_failed.append(key)
            if changed:
                self._dl_changed = True
            # pliki !#include (tylko z tego samego katalogu, z katalogu listy)
            if ok and parent is None and lst.get("includes"):
                for name in lst["includes"]:
                    iu = catalog.include_url(lst, name)
                    if iu:
                        self._dl_pending += 1
                        self._fetch("%s__%s" % (lst["id"], name), iu, None,
                                    catalog.include_path(lst["id"], name, self.home), lst, parent=lst["id"])
        except Exception:
            self._dl_failed.append(key)
        self._dl_pending -= 1
        if self._dl_pending <= 0:
            QTimer.singleShot(0, self._downloads_finished)

    @staticmethod
    def _valid_list(data, lst):
        if not data or len(data) > DL_CAP:
            return False
        head = data[:512].lstrip().lower()
        if head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"\x00" in data[:4096]:
            return False   # portal logowania Wi-Fi, strona błędu, plik binarny
        return b"." in data

    def _downloads_finished(self):
        if not self._dl_running:
            return
        self._dl_running = False
        try:
            catalog.save_meta(self.meta, self.home)
        except Exception:
            pass
        if getattr(self, "_dl_force_again", False):
            self._dl_force_again = False
            self._start_updates(force=True)
            return
        have = (any(os.path.isfile(catalog.list_path(i, self.home)) for i in self.enabled_ids())
                or bool(self.user_filters().strip()))
        built = (self.meta.get("_build") or {}).get("sig")
        need = ((have and (self._dl_changed or self.net is None or built != self._sig()))
                or (self.net is not None and built != self._sig()))
        self._need_build = False
        if self._dl_failed and not need:
            self.error = "Nie udało się pobrać: " + ", ".join(sorted(set(self._dl_failed)))
        if need:
            self._compile()
        else:
            self.state = ""
            self._finish(not self._dl_failed or self.net is not None)
        self._schedule()

    def _finish(self, ok):
        cbs, self._dl_done = self._dl_done, []
        self.status_changed.emit()
        for cb in cbs:
            try:
                cb(ok)
            except Exception:
                pass

    def _schedule(self):
        now = time.time()
        best = None
        for i in self._ids_with_psl():
            lst = catalog.get(i)
            m = self.meta.get(i) or {}
            if m.get("ok") is False or not m.get("fetched"):
                t = float(m.get("tried") or now) + 3600
            else:
                t = float(m["fetched"]) + lst["expires_h"] * 3600
            best = t if best is None else min(best, t)
        if best is None:
            return
        delay = max(60.0, best - now)
        self._timer.start(int(min(delay, 20 * 86400) * 1000))

    # ---------------------------------------------------------------- kompilacja (podproces)
    def _compile(self):
        if self._proc is not None:
            self._compile_again = True
            return
        n = (self._builds()[-1][0] + 1) if self._builds() else 1
        while os.path.exists(os.path.join(self.root, "build-%d" % n)):
            n += 1
        out = os.path.join(self.root, "build-%d" % n)
        self._out_name = "build-%d" % n
        cfgp = out + ".json"
        sig = self._sig()
        cfg = catalog.build_config(self.enabled_ids(), self.user_filters(), self.home)
        try:
            os.makedirs(self.root, exist_ok=True)
            with open(cfgp, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False)
        except OSError as e:
            self.state, self.error = "", "Błąd zapisu konfiguracji filtrów: %s" % e
            self._finish(False)
            return
        prog, args = compiler_command(cfg["lists_dir"], out, cfgp)
        p = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.remove("PYTHONPATH")
        p.setProcessEnvironment(env)
        p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        try:   # bez okna konsoli nawet przy python.exe (CREATE_NO_WINDOW)
            def _mod(a):
                a.flags |= 0x08000000
            p.setCreateProcessArgumentsModifier(_mod)
            self._mod = _mod
        except Exception:
            pass
        self._proc = p
        self.state = "kompilacja"
        self.status_changed.emit()
        t0 = time.time()
        kill = QTimer(p)
        kill.setSingleShot(True)
        kill.timeout.connect(p.kill)
        kill.start(COMPILE_TIMEOUT_MS)
        p.finished.connect(lambda code, st, p=p, out=out, cfgp=cfgp, sig=sig, t0=t0:
                           self._compiled(p, code, st, out, cfgp, sig, t0))
        p.errorOccurred.connect(lambda e, p=p, out=out, cfgp=cfgp, sig=sig, t0=t0:
                                e == QProcess.ProcessError.FailedToStart and self._compiled(p, -1, None, out, cfgp, sig, t0))
        p.start(prog, args)

    def _compiled(self, *args):
        try:
            self._compiled_impl(*args)
        except RuntimeError:   # Luna zamknięta w trakcie kompilacji list – obiekty Qt już usunięte, nic do zrobienia
            pass

    def _compiled_impl(self, p, code, status, out, cfgp, sig, t0):
        if self._proc is not p:
            return
        self._proc = None
        try:
            self.compile_log = bytes(p.readAll()).decode("utf-8", "replace")[-4000:]
        except Exception:
            self.compile_log = ""
        try:
            p.deleteLater()
        except RuntimeError:   # Luna zamykana w trakcie kompilacji – proces został już usunięty
            pass
        self.compile_ms = int((time.time() - t0) * 1000)
        try:
            os.remove(cfgp)
        except OSError:
            pass
        ok = code == 0 and os.path.isfile(os.path.join(out, "info.json"))
        if ok:
            try:
                b = self._read_build(out)
                self._swap(b)
                self.meta["_build"] = {"dir": os.path.basename(out), "sig": sig, "at": time.time()}
                catalog.save_meta(self.meta, self.home)
                self.state, self.error = "", ""
            except Exception as e:
                ok = False
                self.state, self.error = "", "Nie udało się wczytać filtrów: %s" % e
        else:
            err = ""
            try:
                with open(out + ".err", encoding="utf-8") as f:
                    err = f.read().strip().splitlines()[-1]
            except Exception:
                pass
            self.state, self.error = "", "Kompilacja filtrów nie powiodła się" + (": " + err[:200] if err else "")
            shutil.rmtree(out, ignore_errors=True)
        if self._compile_again:
            self._compile_again = False
            QTimer.singleShot(0, self._compile)
            return
        self._finish(ok)


def compiler_command(lists_dir, out_dir, cfg_path):
    """(program, argumenty) podprocesu kompilatora. Bez okna konsoli: pythonw.exe; w .exe (PyInstaller):
    Luna.exe --luna-adblock-compile (obsługiwane na początku luna.py)."""
    if getattr(sys, "frozen", False):
        return sys.executable, ["--luna-adblock-compile", lists_dir, out_dir, cfg_path]
    exe = sys.executable
    d = os.path.dirname(exe)
    if sys.platform == "win32":
        for n in ("pythonw.exe",):
            c = os.path.join(d, n)
            if os.path.isfile(c):
                exe = c
                break
    pkg = os.path.dirname(os.path.abspath(__file__))
    # pakiet „adblock” bez __init__ (bez Qt): tylko moduły kompilatora
    code = ("import sys,types;m=types.ModuleType('adblock');m.__path__=[%r];sys.modules['adblock']=m;"
            "from adblock import compiler;compiler.main()" % pkg)
    return exe, ["-I", "-c", code, lists_dir, out_dir, cfg_path]


__all__ = ["SCHEME", "TOKEN", "SR", "SCHEME_OK", "register_scheme", "AdBlock", "base_domain", "compiler_command"]
