"""Zasoby zastępcze (surrogates) dla przekierowań $redirect / $redirect-rule.

API (kontrakt DESIGN §7):
    get(name) -> (mime, bytes) | None     # nazwy kanoniczne, aliasy uBO/AdGuard/ABP i stare nazwy-ścieżki
    NAMES                                  # wszystkie akceptowane nazwy (do walidacji filtrów), łącznie z "none"
    canonical(name) -> str | None          # alias -> nazwa kanoniczna
    default_for(rtype, url="") -> name | None
    known_library(url, rtype=None) -> name | None
    script_body(name) -> str | None        # treść JS (np. do wstrzyknięcia jako scriptlet: nobab, nofab, google-ima…)

Pliki leżą w adblock/res/ (obrazy i MP3 generuje res/_gen.py; MP4/WebM nagrane przez QtWebEngine).
Wszystko jest serwowane wyłącznie z tej listy (allowlista w pamięci) – nigdy po nazwie pliku z URL.
"""
import os
import sys

# typy żądań – te same liczby co netfilter.RT (kontrakt §3); nie importujemy netfilter, żeby nie wiązać modułów
_DOCUMENT, _SUBDOCUMENT, _STYLESHEET, _SCRIPT, _IMAGE, _FONT, _OBJECT, _MEDIA, _XHR = 1, 2, 3, 4, 5, 6, 7, 8, 9

_JS = "application/javascript"
_XML_HEAD = '<?xml version="1.0" encoding="UTF-8"?>'

# kanoniczna nazwa -> (mime, plik w res/ | bytes)
_TABLE = {
    # puste
    "noop.js": (_JS, b"(function(){})();\n"),
    "noop.txt": ("text/plain", b""),
    "empty": ("text/plain", b""),
    "noop.css": ("text/css", b""),
    "noop.json": ("application/json", b"{}"),
    "noop.html": ("text/html", b"<!DOCTYPE html><html><head></head><body></body></html>"),
    "noop-vast2.xml": ("application/xml", (_XML_HEAD + '<VAST version="2.0"></VAST>').encode()),
    "noop-vast3.xml": ("application/xml", (_XML_HEAD + '<VAST version="3.0"></VAST>').encode()),
    "noop-vast4.xml": ("application/xml", (_XML_HEAD + '<VAST version="4.0"></VAST>').encode()),
    "noop-vmap1.xml": ("application/xml", (_XML_HEAD + '<vmap:VMAP xmlns:vmap="http://www.iab.net/videosuite/vmap"'
                                           ' version="1.0"></vmap:VMAP>').encode()),
    "click2load.html": ("text/html", "click2load.html"),
    # binarne
    "1x1.gif": ("image/gif", "1x1.gif"),
    "2x2.png": ("image/png", "2x2.png"),
    "3x2.png": ("image/png", "3x2.png"),
    "32x32.png": ("image/png", "32x32.png"),
    "noop-0.1s.mp3": ("audio/mpeg", "noop-0.1s.mp3"),
    "noop-0.5s.mp3": ("audio/mpeg", "noop-0.5s.mp3"),
    # brak H.264 w tym Qt: VP9 we fragmentowanym MP4 (element <video> rozpoznaje kontener po zawartości)
    "noop-1s.mp4": ("video/mp4", "noop-1s.mp4"),
    "noop-1s.webm": ("video/webm", "noop-1s.webm"),
    # skrypty zastępcze
    "googletagservices_gpt.js": (_JS, "googletagservices_gpt.js"),
    "googlesyndication_adsbygoogle.js": (_JS, "googlesyndication_adsbygoogle.js"),
    "google-ima.js": (_JS, "google-ima.js"),
    "google-analytics_analytics.js": (_JS, "google-analytics_analytics.js"),
    "google-analytics_ga.js": (_JS, "google-analytics_ga.js"),
    "google-analytics_cx_api.js": (_JS, "google-analytics_cx_api.js"),
    "google-analytics_inpage_linkid.js": (_JS, "google-analytics_inpage_linkid.js"),
    "googletagmanager_gtm.js": (_JS, "googletagmanager_gtm.js"),
    "amazon_apstag.js": (_JS, "amazon_apstag.js"),
    "amazon_ads.js": (_JS, "amazon_ads.js"),
    "ampproject_v0.js": (_JS, "ampproject_v0.js"),
    "doubleclick_instream_ad_status.js": (_JS, "doubleclick_instream_ad_status.js"),
    "scorecardresearch_beacon.js": (_JS, "scorecardresearch_beacon.js"),
    "outbrain-widget.js": (_JS, "outbrain-widget.js"),
    "fingerprint2.js": (_JS, "fingerprint2.js"),
    "fingerprint3.js": (_JS, "fingerprint3.js"),
    "nobab.js": (_JS, "nobab.js"),
    "nobab2.js": (_JS, "nofab.js"),          # BAB 4.2b: globalne BlockAdBlock w stanie "nie wykryto" (spec 04 §5.19)
    "nofab.js": (_JS, "nofab.js"),
    "popads.js": (_JS, "popads.js"),
    "popads-dummy.js": (_JS, "popads-dummy.js"),
    "prebid-ads.js": (_JS, "prebid-ads.js"),
    "sensors-analytics.js": (_JS, "sensors-analytics.js"),
    "nitropay_ads.js": (_JS, "nitropay_ads.js"),
    "chartbeat.js": (_JS, "chartbeat.js"),
    "noeval-silent.js": (_JS, "noeval-silent.js"),
    "noeval.js": (_JS, "noeval-silent.js"),
    # API nieudokumentowane / przestarzałe -> zachowanie jak noop.js (spec 04 §5.24)
    "adthrive_abd.js": (_JS, b"(function(){})();\n"),
    "hd-main.js": (_JS, b"(function(){})();\n"),
    "addthis_widget.js": (_JS, b"(function(){})();\n"),
    "monkeybroker.js": (_JS, b"(function(){})();\n"),
    "ligatus_angular-tag.js": (_JS, b"(function(){})();\n"),
    "piano-analytics.js": (_JS, b"(function(){})();\n"),
    # przynęta Adblock Analytics (detectadblock.com i klienci): oryginał dopisuje ukryty pusty <div> o stałym id,
    # strona sprawdza tylko jego obecność – odtwarzamy dokładnie to, bez wysyłania danych do dostawcy
    "adblockanalytics_bait.js": (_JS, b"(function(){var d=document,e=d.createElement('div');e.id='nqoybpxnanylgvpfpbz';"
                                      b"e.style.display='none';(d.body||d.documentElement).appendChild(e);})();\n"),
}

# alias -> kanoniczna (uBO legacy path names, AdGuard, ABP)
ALIASES = {
    "1x1-transparent.gif": "1x1.gif", "1x1-transparent-gif": "1x1.gif",
    "2x2-transparent.png": "2x2.png", "2x2-transparent-png": "2x2.png",
    "3x2-transparent.png": "3x2.png", "3x2-transparent-png": "3x2.png",
    "32x32-transparent.png": "32x32.png", "32x32-transparent-png": "32x32.png",
    "noopcss": "noop.css", "blank-css": "noop.css",
    "noopframe": "noop.html", "blank-html": "noop.html", "noop-frame": "noop.html",
    "noopjs": "noop.js", "blank-js": "noop.js",
    "noopjson": "noop.json",
    "nooptext": "noop.txt", "blank-text": "noop.txt",
    "noopmp3-0.1s": "noop-0.1s.mp3", "blank-mp3": "noop-0.1s.mp3",
    "noopmp4-1s": "noop-1s.mp4", "blank-mp4": "noop-1s.mp4", "mp4": "noop-1s.mp4",
    "noopvast-2.0": "noop-vast2.xml", "noopvast-3.0": "noop-vast3.xml", "noopvast-4.0": "noop-vast4.xml",
    "noop-vmap1.0.xml": "noop-vmap1.xml", "noopvmap-1.0": "noop-vmap1.xml",
    "googletagservices.com/gpt.js": "googletagservices_gpt.js", "googletagservices-gpt": "googletagservices_gpt.js",
    "googlesyndication.com/adsbygoogle.js": "googlesyndication_adsbygoogle.js",
    "googlesyndication-adsbygoogle": "googlesyndication_adsbygoogle.js",
    "google-ima3": "google-ima.js",
    "google-analytics.com/analytics.js": "google-analytics_analytics.js",
    "google-analytics": "google-analytics_analytics.js",
    "googletagmanager-gtm": "googletagmanager_gtm.js",
    "google-analytics.com/ga.js": "google-analytics_ga.js", "google-analytics-ga": "google-analytics_ga.js",
    "google-analytics.com/cx/api.js": "google-analytics_cx_api.js",
    "google-analytics.com/inpage_linkid.js": "google-analytics_inpage_linkid.js",
    "googletagmanager.com/gtm.js": "googletagmanager_gtm.js",
    "amazon-apstag": "amazon_apstag.js",
    "amazon-adsystem.com/aax2/amzn_ads.js": "amazon_ads.js",
    "ampproject.org/v0.js": "ampproject_v0.js",
    "doubleclick.net/instream/ad_status.js": "doubleclick_instream_ad_status.js",
    "scorecardresearch.com/beacon.js": "scorecardresearch_beacon.js",
    "scorecardresearch-beacon": "scorecardresearch_beacon.js",
    "widgets.outbrain.com/outbrain.js": "outbrain-widget.js",
    "fingerprintjs2": "fingerprint2.js", "fingerprintjs3": "fingerprint3.js",
    "bab-defuser.js": "nobab.js", "prevent-bab": "nobab.js",
    "prevent-bab2": "nobab2.js",
    "fuckadblock.js-3.2.0": "nofab.js", "prevent-fab-3.2.0": "nofab.js",
    "popads.net.js": "popads.js", "prevent-popads-net": "popads.js",
    "set-popads-dummy": "popads-dummy.js",
    "prebid-ads": "prebid-ads.js",
    "silent-noeval.js": "noeval-silent.js", "noeval": "noeval-silent.js",
    "static.chartbeat.com/chartbeat.js": "chartbeat.js",
    "addthis.com/addthis_widget.js": "addthis_widget.js",
    "d3pkae9owd2lcf.cloudfront.net/mb105.js": "monkeybroker.js",
    "ligatus.com/*/angular-tag.js": "ligatus_angular-tag.js",
}

# "none" – zarezerwowana dyrektywa bez przekierowania (neutralizuje inne redirect-rule); get("none") -> None
NONE = "none"
NAMES = frozenset(_TABLE) | frozenset(ALIASES) | {NONE}

_HERE = os.path.dirname(os.path.abspath(__file__))
_cache = {}


def _res_dir():
    d = os.path.join(_HERE, "res")
    if os.path.isdir(d):
        return d
    base = getattr(sys, "_MEIPASS", None)  # PyInstaller --onefile
    if base:
        alt = os.path.join(base, "adblock", "res")
        if os.path.isdir(alt):
            return alt
    return d


def canonical(name):
    """Nazwa kanoniczna albo None (nieznana). Akceptuje prefiks 'abp-resource:' i sufiks priorytetu ':N'."""
    if not name:
        return None
    n = str(name).strip()
    if n.startswith("abp-resource:"):
        n = n[13:]
    if n in _TABLE:
        return n
    if n in ALIASES:
        return ALIASES[n]
    i = n.rfind(":")
    if i > 0 and n[i + 1:].lstrip("-").isdigit():
        return canonical(n[:i])
    if n == NONE:
        return NONE
    return None


def get(name):
    """(mime, bytes) albo None (nieznana nazwa / 'none' / brak pliku)."""
    c = canonical(name)
    if c is None or c == NONE:
        return None
    hit = _cache.get(c)
    if hit is not None:
        return hit
    mime, src = _TABLE[c]
    if isinstance(src, bytes):
        data = src
    else:
        try:
            with open(os.path.join(_res_dir(), src), "rb") as f:
                data = f.read()
        except OSError:
            return None
    hit = (mime, data)
    _cache[c] = hit
    return hit


def script_body(name):
    """Treść JS zasobu (str) – np. do wstrzyknięcia zasobu jako scriptletu; None gdy to nie skrypt."""
    r = get(name)
    if r is None or r[0] != _JS:
        return None
    return r[1].decode("utf-8")


_AUDIO_EXT = (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac", ".weba")


def _path_of(url):
    i = url.find("://")
    rest = url[i + 3:] if i >= 0 else url
    j = len(rest)
    for ch in "/?#":
        k = rest.find(ch)
        if 0 <= k < j:
            j = k
    host = rest[:j]
    at = host.rfind("@")
    if at >= 0:
        host = host[at + 1:]
    if host.startswith("["):
        host = host[:host.find("]") + 1]
    else:
        c = host.find(":")
        if c >= 0:
            host = host[:c]
    path = rest[j:]
    for ch in "?#":
        k = path.find(ch)
        if k >= 0:
            path = path[:k]
    return host.lower().rstrip("."), path.lower() or "/"


def default_for(rtype, url=""):
    """Domyślny zasób dla zablokowanego żądania danego typu (None = zwykła blokada)."""
    if rtype == _SCRIPT:
        return "noop.js"
    if rtype == _SUBDOCUMENT:
        return "noop.html"
    if rtype == _IMAGE:
        # naturalWidth >= 2 (sondy obrazkowe); ikony -> 32x32
        if url:
            p = _path_of(url)[1]
            if p.endswith(".ico") or "favicon" in p:
                return "32x32.png"
        return "2x2.png"
    if rtype == _STYLESHEET:
        return "noop.css"
    if rtype == _MEDIA:
        if url and _path_of(url)[1].endswith(_AUDIO_EXT):
            return "noop-0.1s.mp3"
        return "noop-1s.mp4"
    if rtype == _XHR:
        return "noop.txt"
    return None


# znane biblioteki reklamowe/analityczne: nazwa pliku -> [(sufiks hosta | None, fragment ścieżki | None, zasób)]
_LIBS = {}


def _lib(fname, host, part, name):
    _LIBS.setdefault(fname, []).append((host, part, name))


for _h in ("doubleclick.net", "googletagservices.com", "googlesyndication.com"):
    _lib("gpt.js", _h, None, "googletagservices_gpt.js")
_lib("adsbygoogle.js", "googlesyndication.com", None, "googlesyndication_adsbygoogle.js")
_lib("adsbygoogle.js", "googleadservices.com", None, "googlesyndication_adsbygoogle.js")
for _f in ("ima3.js", "ima3_debug.js"):
    _lib(_f, "imasdk.googleapis.com", None, "google-ima.js")
for _f in ("analytics.js", "analytics_debug.js"):
    _lib(_f, "google-analytics.com", None, "google-analytics_analytics.js")
for _f in ("ga.js", "ga_debug.js"):
    _lib(_f, "google-analytics.com", None, "google-analytics_ga.js")
_lib("dc.js", "doubleclick.net", None, "google-analytics_ga.js")
_lib("api.js", "google-analytics.com", "/cx/", "google-analytics_cx_api.js")
_lib("inpage_linkid.js", "google-analytics.com", None, "google-analytics_inpage_linkid.js")
_lib("gtm.js", "googletagmanager.com", None, "googletagmanager_gtm.js")
_lib("js", "googletagmanager.com", "/gtag/js", "googletagmanager_gtm.js")
_lib("apstag.js", "amazon-adsystem.com", None, "amazon_apstag.js")
_lib("amzn_ads.js", "amazon-adsystem.com", None, "amazon_ads.js")
_lib("ad_status.js", "doubleclick.net", "/instream/", "doubleclick_instream_ad_status.js")
_lib("beacon.js", "scorecardresearch.com", None, "scorecardresearch_beacon.js")
_lib("outbrain.js", "outbrain.com", None, "outbrain-widget.js")
_lib("v0.js", "ampproject.org", None, "ampproject_v0.js")
for _f in ("chartbeat.js", "chartbeat_mab.js"):
    _lib(_f, "chartbeat.com", None, "chartbeat.js")
for _f in ("fuckadblock.js", "fuckadblock.min.js", "blockadblock.js", "blockadblock.min.js",
           "sniffadblock.js", "sniffadblock.min.js"):
    _lib(_f, None, None, "nofab.js")
for _f in ("fingerprint2.js", "fingerprint2.min.js", "fingerprintjs2.js", "fingerprintjs2.min.js"):
    _lib(_f, None, None, "fingerprint2.js")
_lib("v3", "openfpcdn.io", "/fingerprintjs/", "fingerprint3.js")
for _f in ("sensorsdata.full.min.js", "sensorsdata.min.js", "sensorsdata.full.js"):
    _lib(_f, None, None, "sensors-analytics.js")
_lib("google-adsense.js", "adblockanalytics.com", None, "adblockanalytics_bait.js")
# pliki-przynęty typu „ads.js” (ustawiają canRunAds / isAdBlockActive)
for _f in ("prebid-ads.js", "ads-prebid.js", "ads.js", "advert.js", "adframe.js", "advertisement.js"):
    _lib(_f, None, None, "prebid-ads.js")


def _host_match(host, suffix):
    return host == suffix or host.endswith("." + suffix)


def known_library(url, rtype=None):
    """Zasób zastępczy dla znanej biblioteki (gpt.js, adsbygoogle.js, analytics.js, gtm.js, ima3.js…).

    rtype: gdy podany i różny od SCRIPT -> None (zastępcze JS mają sens tylko dla <script>)."""
    if rtype is not None and rtype != _SCRIPT:
        return None
    try:
        host, path = _path_of(url)
    except Exception:
        return None
    fname = path[path.rfind("/") + 1:]
    cand = _LIBS.get(fname)
    if not cand:
        return None
    for suffix, part, name in cand:
        if suffix is not None and not _host_match(host, suffix):
            continue
        if part is not None and part not in path:
            continue
        return name
    return None
