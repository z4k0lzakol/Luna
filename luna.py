#!/usr/bin/env python3
"""Luna z kafelkami-aplikacjami na ekranie głównym.
Ikona kafelka = favicon zapisanej strony. Styl: głęboka czerń, fonty Inter + Playfair Display.

Instalacja:   pip install PyQt6 PyQt6-WebEngine
Uruchomienie: python luna.py

Dane w katalogu domowym:
  .luna.json          kafelki
  .luna_ostatnie.json ostatnio odwiedzone
  .luna_ustawienia.json  wybrana wyszukiwarka
  .luna_ikony/        favicony
  .luna_fonty/        fonty (pobierane automatycznie przy 1. uruchomieniu;
                                    możesz tu wrzucić własne pliki .ttf/.otf)
"""
import sys, json, math, re, html, os, random, base64
from datetime import date, timedelta
from pathlib import Path
from PyQt6.QtCore import Qt, QUrl, QSize, QObject, QPointF, QRectF, QEvent, QTimer, QLocale, QDateTime, QPropertyAnimation, pyqtSignal
from PyQt6.QtGui import (QCursor, QBrush, QRadialGradient, QIcon, QPixmap, QPainter, QColor, QFont, QFontDatabase, QPen,
                         QPolygonF, QKeySequence, QShortcut, QActionGroup, QTextDocument, QPalette, QPainterPath)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QStackedWidget, QTabBar,
                             QToolButton, QLineEdit, QListWidget, QListWidgetItem, QListView,
                             QAbstractItemView, QMenu, QInputDialog, QVBoxLayout, QLabel,
                             QPushButton, QHBoxLayout, QDialog, QDialogButtonBox,
                             QFrame, QScrollArea, QPlainTextEdit, QGraphicsOpacityEffect, QButtonGroup, QToolTip)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

HOME = Path.home()
DATA = HOME / ".luna.json"
RECENT = HOME / ".luna_ostatnie.json"
SETTINGS = HOME / ".luna_ustawienia.json"
ICONS = HOME / ".luna_ikony"
FONT_DIR = HOME / ".luna_fonty"
FONT_URLS = {
    "Inter.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
    "PlayfairDisplay.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
}

def migrate_old_data():
    """Przenosi dane z poprzednich nazw programu (Lekka przeglądarka, Lumen) do Luna."""
    for prefix in (".lumen", ".lekka_przegladarka"):  # nowsza nazwa ma pierwszeństwo
        for old, new in ((prefix + ".json", DATA), (prefix + "_ostatnie.json", RECENT),
                         (prefix + "_ustawienia.json", SETTINGS), (prefix + "_ikony", ICONS),
                         (prefix + "_fonty", FONT_DIR)):
            o = HOME / old
            try:
                if o.exists() and not new.exists():
                    o.rename(new)
            except OSError:
                pass


# Logo Luna (PNG 256×256, przezroczyste narożniki), osadzone w pliku
LOGO_B64 = (
    "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"
)
_LOGO_SRC = []


def _logo_src() -> QPixmap:
    if not _LOGO_SRC:
        pm = QPixmap(); pm.loadFromData(base64.b64decode(LOGO_B64)); _LOGO_SRC.append(pm)
    return _LOGO_SRC[0]


def logo_pixmap(size: int) -> QPixmap:
    """Logo w podanym rozmiarze logicznym (ostre na ekranach HiDPI)."""
    pm = _logo_src().scaled(size * 2, size * 2, Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
    pm.setDevicePixelRatio(2.0)
    return pm


def app_icon() -> QIcon:
    ic = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(_logo_src().scaled(sz, sz, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation))
    return ic


ENGINES = {"Brave": "https://search.brave.com/search?q=",
           "Google": "https://www.google.com/search?q=",
           "DuckDuckGo": "https://duckduckgo.com/?q=",
           "Bing": "https://www.bing.com/search?q=",
           "Startpage": "https://www.startpage.com/sp/search?query=",
           "Ecosia": "https://www.ecosia.org/search?q=",
           "Qwant": "https://www.qwant.com/?q=",
           "Yahoo": "https://search.yahoo.com/search?p=",
           "Yandex": "https://yandex.com/search/?text=",
           "Perplexity": "https://www.perplexity.ai/search?q="}
CURRENT = ["Brave"]  # aktywna wyszukiwarka (domyślnie Brave)
# Asystent AI = strony tych serwisów w panelu bocznym (logujesz się normalnie – bez kluczy API)
PROVIDERS = {"ChatGPT": "https://chatgpt.com", "Claude": "https://claude.ai/new",
             "Gemini": "https://gemini.google.com/app", "DeepSeek": "https://chat.deepseek.com"}

# Zmieniające się podpisy na ekranie głównym (<u>…</u> = podkreślone słowo)
CAPTIONS = [
    "Twoje ulubione strony – jak <u>aplikacje</u> na telefonie.",
    "Wszystko, czego potrzebujesz, w <u>jednym</u> miejscu.",
    "Mniej kart, więcej <u>spokoju</u>.",
    "Szybko, lekko i <u>po Twojemu</u>.",
    "Cisza w sieci. Tylko to, co <u>ważne</u>.",
    "Jedno kliknięcie dzieli Cię od <u>celu</u>.",
    "Niech seria <u>trwa</u>. Jeszcze jeden dzień.",
    "ChatGPT, Claude, Gemini i DeepSeek – <u>pod ręką</u>.",
]

DEFAULTS = [
    {"name": "Google", "url": "https://www.google.com"},
    {"name": "YouTube", "url": "https://www.youtube.com"},
    {"name": "Wikipedia", "url": "https://pl.wikipedia.org"},
]
CATALOG = [
    ("Google", "https://www.google.com"), ("YouTube", "https://www.youtube.com"),
    ("Gmail", "https://mail.google.com"), ("Mapy Google", "https://maps.google.com"),
    ("Wikipedia", "https://pl.wikipedia.org"), ("GitHub", "https://github.com"),
    ("Facebook", "https://www.facebook.com"), ("Instagram", "https://www.instagram.com"),
    ("X", "https://x.com"), ("Reddit", "https://www.reddit.com"),
    ("Netflix", "https://www.netflix.com"), ("Spotify", "https://open.spotify.com"),
    ("Allegro", "https://allegro.pl"), ("OLX", "https://www.olx.pl"),
    ("Onet", "https://www.onet.pl"), ("WP", "https://www.wp.pl"),
    ("ChatGPT", "https://chatgpt.com"), ("Claude", "https://claude.ai"),
]

SERIF = '"Playfair Display","Playfair","Georgia","Times New Roman",serif'
STYLE = """
* { font-family: "Inter","Segoe UI","Roboto","Noto Sans",sans-serif; }
QMainWindow, QWidget, QDialog { background:#111111; color:#ececec; }
QLabel { background:transparent; }
QWidget#assistant { background:#111111; border-left:1px solid #1e1e1e; }
QScrollArea#chat { border:0; background:transparent; }
QFrame#bub_user { background:#ececec; border-radius:16px; }
QFrame#bub_user QLabel { color:#111111; }
QFrame#bub_ai { background:#1a1a1a; border:1px solid #262626; border-radius:16px; }
QPlainTextEdit#ai_input { background:#171717; border:1px solid #2a2a2a; border-radius:16px;
                          padding:8px 10px; color:#ececec; }
QPlainTextEdit#ai_input:focus { border:1px solid #666; }
QToolButton#send { background:#ececec; border-radius:20px; }
QToolButton#send:hover { background:#ffffff; }
QToolButton#more { font-size:20px; color:#bbbbbb; border-radius:15px; }
QToolButton#more::menu-indicator { image:none; width:0; }
QToolButton#chip:checked { background:#ececec; color:#111111; }
QPushButton#sugg { background:#1a1a1a; border:1px solid #2a2a2a; border-radius:14px;
                   padding:10px 14px; text-align:left; color:#cfcfcf; }
QPushButton#sugg:hover { background:#232323; color:#fff; }
QWidget#aihead { background:#0d0d0d; border-bottom:1px solid #1e1e1e; border-left:1px solid #1e1e1e; }
QToolButton#aipick { background:transparent; color:#9a9a9a; border-radius:16px; padding:5px 11px 5px 6px;
                     font-size:12px; font-weight:600; }
QToolButton#aipick:hover { background:#1f1f1f; color:#ffffff; }
QToolButton#aipick:checked { background:#ececec; color:#111111; }
QWidget#frame { background:#0a0a0a; border:1px solid #242424; }
QWidget#strip { background:#0a0a0a; }
QToolButton#winclose:hover { background:#b3352c; }
QWidget#tool { background:#111111; border-bottom:1px solid #1e1e1e; }
QTabBar { background:transparent; }
QTabBar::tab { background:transparent; color:#8c8c8c; padding:7px 8px 7px 14px; margin:0 2px;
               border-radius:15px; max-width:190px; font-size:13px; }
QTabBar::tab:hover { background:#1a1a1a; color:#cfcfcf; }
QTabBar::tab:selected { background:#ececec; color:#111111; font-weight:600; }
QToolButton { background:transparent; border:0; border-radius:18px; padding:0; }
QToolButton:hover { background:#1f1f1f; }
QToolButton#tabclose { color:#808080; font-size:10px; border-radius:9px; }
QToolButton#tabclose:hover { background:rgba(128,128,128,70); }
QToolButton#chip { background:#232323; color:#bdbdbd; border-radius:14px; padding:4px 12px;
                   font-size:12px; font-weight:600; }
QToolButton#chip:hover { background:#2e2e2e; color:#fff; }
QToolButton#chip::menu-indicator { image:none; width:0; }
QToolButton#engine { background:#1d1d1d; color:#dcdcdc; border:1px solid #2d2d2d; border-radius:15px;
                     padding:4px 24px 4px 5px; font-size:12px; font-weight:600; }
QToolButton#engine:hover { background:#272727; color:#ffffff; border-color:#3c3c3c; }
QToolButton#engine:open { background:#2e2e2e; border-color:#4a4a4a; }
QToolButton#engine::menu-indicator { image:url("%CHEV%"); width:10px; height:10px;
                                     subcontrol-origin:padding; subcontrol-position:center right; right:9px; }
QPushButton { background:#232323; color:#ececec; border:0; border-radius:10px; padding:8px 16px; }
QPushButton:hover { background:#2f2f2f; }
QPushButton#round { border-radius:17px; padding:0; font-size:17px; }
QLineEdit { background:#191919; border:1px solid #2a2a2a; border-radius:12px;
            padding:9px 12px; color:#ececec; selection-background-color:#555; }
QLineEdit:focus { border:1px solid #666; }
QLineEdit#addr { border-radius:20px; padding:0 14px; min-height:40px; font-size:13px; }
QLineEdit#search { border-radius:14px; padding:14px 12px; font-size:14px; background:#171717; }
QLabel#brand { font-family:""" + SERIF + """; font-size:26px; font-weight:600; color:#f4f4f4; }
QLabel#headline { font-family:""" + SERIF + """; font-size:30px; color:#d6d6d6; }
QLabel#ai_empty { font-family:""" + SERIF + """; font-size:26px; color:#d6d6d6; }
QLabel#bignum { font-family:""" + SERIF + """; font-size:46px; color:#f2f2f2; }
QFrame#card { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1a1a1a,stop:1 #131313);
              border:1px solid #262626; border-radius:20px; }
QLabel#cap { color:#6b6b6b; font-size:10px; font-weight:700; }
QFrame#sep { background:#252525; border:0; min-height:1px; max-height:1px; }
QLabel#clock { font-size:40px; font-weight:600; color:#f2f2f2; }
QLabel#temp { font-size:30px; font-weight:600; color:#f2f2f2; }
QLabel#muted2 { color:#9a9a9a; font-size:13px; }
QLabel#h3 { font-size:14px; font-weight:600; }
QLabel#h1 { font-size:17px; font-weight:600; }
QLabel#h2 { font-size:17px; font-weight:600; margin-top:6px; }
QLabel#muted { color:#7f7f7f; font-size:12px; }
QListWidget { border:0; background:transparent; outline:0; }
QListWidget::item { padding:6px; border-radius:10px; }
QListWidget::item:hover { background:#1a1a1a; }
QListWidget#grid { color:#e6e6e6; font-size:12px; font-weight:600; }
QListWidget#grid::item { padding:2px; border-radius:18px; }
QListWidget#grid::item:selected { background:#1a1a1a; color:#fff; }
QListWidget#recent::item { background:#181818; padding:8px; border-radius:12px; }
QListWidget#recent::item:hover { background:#222222; }
QMenu { background:#191919; border:1px solid #2a2a2a; border-radius:8px; padding:4px; }
QMenu::item { padding:7px 20px 7px 8px; border-radius:6px; } QMenu::item:selected { background:#2a2a2a; }
QMenu::icon { padding-left:8px; }
QScrollBar:vertical { background:transparent; width:8px; }
QScrollBar::handle:vertical { background:#2e2e2e; border-radius:4px; min-height:30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
"""


def normalize(text: str) -> str:
    text = text.strip()
    if "://" in text:
        return text
    if " " in text or "." not in text:
        return ENGINES[CURRENT[0]] + QUrl.toPercentEncoding(text).data().decode()
    return "https://" + text


def host_of(url: str) -> str:
    h = QUrl(url).host()
    return h[4:] if h.startswith("www.") else h


def icon_path(url: str) -> Path:
    return ICONS / (host_of(url) + ".png")


def plural(n: int) -> str:
    if n == 1:
        return "aplikacja"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "aplikacje"
    return "aplikacji"


def glyph(kind: str, color: str = "#c9c9c9") -> QIcon:
    """Ikony paska rysowane liniowo (spójna, cienka kreska)."""
    S = 44
    pm = QPixmap(S, S); pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    P = lambda *pts: QPolygonF([QPointF(x, y) for x, y in pts])
    if kind == "back":
        p.drawPolyline(P((26, 11), (15, 22), (26, 33)))
    elif kind == "forward":
        p.drawPolyline(P((18, 11), (29, 22), (18, 33)))
    elif kind == "reload":
        p.drawArc(QRectF(11, 11, 22, 22), 40 * 16, 280 * 16)
        p.drawPolyline(P((31, 7), (31, 16), (22, 16)))
    elif kind == "home":
        p.drawPolyline(P((10, 22), (22, 11), (34, 22)))
        p.drawPolyline(P((15, 20), (15, 33), (29, 33), (29, 20)))
    elif kind in ("star", "starfill"):
        if kind == "starfill":
            p.setBrush(QColor(color))
        pts = []
        for i in range(10):
            r = 13 if i % 2 == 0 else 5.5
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((22 + r * math.cos(a), 23 + r * math.sin(a)))
        p.drawPolygon(P(*pts))
    elif kind == "plus":
        p.drawLine(22, 12, 22, 32); p.drawLine(12, 22, 32, 22)
    elif kind == "min":
        p.drawLine(13, 24, 31, 24)
    elif kind == "max":
        p.drawRoundedRect(QRectF(13, 13, 18, 18), 3, 3)
    elif kind == "restore":
        p.drawRoundedRect(QRectF(11, 17, 16, 16), 3, 3)
        p.drawPolyline(P((17, 17), (17, 11), (33, 11), (33, 27), (27, 27)))
    elif kind == "external":
        p.drawPolyline(P((19, 13), (12, 13), (12, 32), (31, 32), (31, 25)))
        p.drawPolyline(P((24, 10), (34, 10), (34, 20))); p.drawLine(34, 10, 22, 22)
    elif kind == "copy":
        p.drawRoundedRect(QRectF(17, 17, 16, 16), 3, 3)
        p.drawPolyline(P((13, 27), (13, 13), (27, 13)))
    elif kind == "close":
        p.drawLine(14, 14, 30, 30); p.drawLine(30, 14, 14, 30)
    elif kind in ("assistant", "assistantfill"):
        if kind == "assistantfill":
            p.setBrush(QColor(color))
        p.drawPolygon(P((22, 8), (26, 18), (36, 22), (26, 26), (22, 36), (18, 26), (8, 22), (18, 18)))
    elif kind == "send":
        p.drawLine(22, 33, 22, 13); p.drawPolyline(P((13, 22), (22, 13), (31, 22)))
    elif kind == "search":
        p.setPen(QPen(QColor("#9a9a9a"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawEllipse(9, 9, 18, 18); p.drawLine(24, 24, 34, 34)
    p.end()
    return QIcon(pm)


def make_icon(name: str, url: str = "") -> QIcon:
    """Ciemna karta; w środku favicon strony na jasnej płytce albo – gdy brak – serifowa litera."""
    S = 128
    pm = QPixmap(S, S); pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setPen(QPen(QColor("#2a2a2a"), 3)); p.setBrush(QColor("#1b1b1b"))
    p.drawRoundedRect(2, 2, S - 4, S - 4, 26, 26)
    path = icon_path(url) if url else None
    fav = QPixmap(str(path)) if path and path.exists() else QPixmap()
    if not fav.isNull():
        plate = 80; o = (S - plate) // 2
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#ececea"))
        p.drawRoundedRect(o, o, plate, plate, 20, 20)
        side = max(36, min(56, fav.width() * 2))
        s = fav.scaled(side, side, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((S - s.width()) // 2, (S - s.height()) // 2, s)
    else:
        f = QFont("Playfair Display"); f.setStyleHint(QFont.StyleHint.Serif); f.setPixelSize(64)
        p.setFont(f); p.setPen(QColor("#ececea"))
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, (name.strip() or "?")[0].upper())
    p.end()
    return QIcon(pm)


def mini_icon(name: str, url: str = "") -> QIcon:
    """Okrągła ikonka wyszukiwarki / AI: favicon na jasnym kółku albo monogram."""
    S = 64
    pm = QPixmap(S, S); pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setPen(Qt.PenStyle.NoPen)
    path = icon_path(url) if url else None
    fav = QPixmap(str(path)) if path and path.exists() else QPixmap()
    if not fav.isNull():
        p.setBrush(QColor("#ececea")); p.drawEllipse(0, 0, S, S)
        sc = fav.scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((S - sc.width()) // 2, (S - sc.height()) // 2, sc)
    else:
        p.setBrush(QColor("#303030")); p.drawEllipse(0, 0, S, S)
        f = QFont(); f.setPixelSize(34); f.setBold(True); p.setFont(f); p.setPen(QColor("#ececec"))
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, name[:1].upper())
    p.end()
    return QIcon(pm)


def chevron_path() -> str:
    """Mała strzałka ▾ dla przycisków z menu (zapisywana raz jako PNG, bo QSS wymaga pliku)."""
    f = ICONS / "_chevron.png"
    try:
        if not f.exists():
            ICONS.mkdir(exist_ok=True)
            pm = QPixmap(20, 20); pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(QColor("#9a9a9a"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPolyline(QPolygonF([QPointF(5, 8), QPointF(10, 13), QPointF(15, 8)])); p.end()
            pm.save(str(f), "PNG")
    except OSError:
        pass
    return f.as_posix()


def full_style() -> str:
    return STYLE.replace("%CHEV%", chevron_path())


POPUPS, _PROFILE = [], []


def get_profile() -> QWebEngineProfile:
    """Jeden trwały profil dla całej Luny: logowania na stronach (też w panelu AI) zostają po restarcie."""
    if not _PROFILE:
        prof = QWebEngineProfile("Luna", QApplication.instance())
        base = HOME / ".luna_profile"
        try:
            base.mkdir(exist_ok=True)
        except OSError:
            pass
        prof.setPersistentStoragePath(str(base / "data")); prof.setCachePath(str(base / "cache"))
        prof.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        # zwykły Chromium zamiast „QtWebEngine” w User-Agent – logowanie (np. Google) rzadziej jest blokowane
        prof.setHttpUserAgent(re.sub(r"\s*QtWebEngine/\S+", "", prof.httpUserAgent()))
        _PROFILE.append(prof)
    return _PROFILE[0]


class WebView(QWebEngineView):
    """Widok strony: linki „w nowej karcie” otwierają kartę Luny, okna logowania – osobne okienko."""
    link_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPage(QWebEnginePage(get_profile(), self))
        self.page().setBackgroundColor(QColor("#111111"))

    def createWindow(self, wtype):
        W = QWebEnginePage.WebWindowType
        if wtype in (W.WebDialog, W.WebBrowserWindow):  # np. okno logowania Google/OAuth
            pop = WebView(); pop.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            pop.resize(520, 720); pop.setWindowTitle("Luna – logowanie"); pop.setWindowIcon(app_icon())
            pop.page().windowCloseRequested.connect(pop.close)
            POPUPS.append(pop)
            pop.destroyed.connect(lambda _=None, p=pop: POPUPS.remove(p) if p in POPUPS else None)
            pop.show()
            return pop
        tmp = WebView(self)  # zwykły link: łapiemy docelowy adres i otwieramy go w nowej karcie
        tmp.page().urlChanged.connect(lambda u, t=tmp: self._grab(u, t))
        return tmp

    def _grab(self, url, tmp):
        u = url.toString()
        if u and u != "about:blank":
            tmp.stop(); tmp.deleteLater(); self.link_requested.emit(u)


class Store(QObject):
    changed = pyqtSignal()
    weather_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.nam = QNetworkAccessManager(self)
        self.items = self._load(DATA, list(DEFAULTS))
        self.recent = self._load(RECENT, [])
        self.settings = self._load(SETTINGS, {})
        old_keys = [k for k in ("gemini_key", "gemini_model", "ai_keys", "ai_models") if k in self.settings]
        for k in old_keys:
            self.settings.pop(k)
        if old_keys:
            self.save_settings()
        eng = self.settings.get("engine", "Brave")
        CURRENT[0] = eng if eng in ENGINES else "Brave"
        for b in self.items + self.recent:
            self.fetch_icon(b["url"])
        for u in list(ENGINES.values()) + list(PROVIDERS.values()):
            self.fetch_icon(u)
        self.weather = {}
        self.bump_day(emit=False)  # samo uruchomienie przeglądarki liczy się do serii
        QTimer.singleShot(800, self.fetch_weather)
        self.wtimer = QTimer(self); self.wtimer.timeout.connect(self.fetch_weather)
        self.wtimer.start(15 * 60 * 1000)

    @staticmethod
    def _load(path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    @staticmethod
    def _write(path, data):
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def set_engine(self, name):
        CURRENT[0] = name
        self.settings["engine"] = name
        self.save_settings()
        self.changed.emit()

    def save_settings(self):
        self._write(SETTINGS, self.settings)
        try:
            os.chmod(SETTINGS, 0o600)  # klucz API tylko dla Ciebie (Linux/macOS)
        except OSError:
            pass

    def save(self, notify=True):
        self._write(DATA, self.items)
        if notify:
            self.changed.emit()

    def add(self, name, url, save=True):
        url = normalize(url)
        self.items.append({"name": name, "url": url})
        self.fetch_icon(url)
        if save:
            self.save()

    # --- seria dni (kalendarz aktywności) ---
    def bump_day(self, n=1, emit=True):
        days = self.settings.setdefault("days", {})
        k = date.today().isoformat()
        days[k] = days.get(k, 0) + n
        if len(days) > 500:
            for old in sorted(days)[:-400]:
                del days[old]
        self.save_settings()
        if emit:
            self.changed.emit()

    def streak(self):
        days = {k for k, v in self.settings.get("days", {}).items() if v > 0}
        d, cur = date.today(), 0
        while d.isoformat() in days:
            cur += 1; d -= timedelta(days=1)
        best = run = 0; prev = None
        for x in sorted(date.fromisoformat(k) for k in days):
            run = run + 1 if prev and (x - prev).days == 1 else 1
            best = max(best, run); prev = x
        return cur, best

    def stats(self):
        days = {k: v for k, v in self.settings.get("days", {}).items() if v > 0}
        today = date.today(); mon = today - timedelta(days=today.weekday())
        return {"week": sum(1 for k in days if mon <= date.fromisoformat(k) <= today),
                "month": sum(1 for k in days if k.startswith(today.strftime("%Y-%m"))),
                "total": len(days), "acts": sum(days.values())}

    # --- pogoda (Open-Meteo; lokalizacja z IP albo wybrane miasto) ---
    def _json(self, reply):
        try:
            j = json.loads(bytes(reply.readAll()).decode("utf-8"))
        except Exception:
            j = None
        reply.deleteLater()
        return j

    def fetch_weather(self):
        c = self.settings.get("weather_city")
        if c:
            self._forecast(c["lat"], c["lon"], c["name"]); return
        r = self._request("https://ipwho.is/")
        r.finished.connect(lambda r=r: self._geo_done(r))

    def _geo_done(self, r):
        j = self._json(r)
        if isinstance(j, dict) and j.get("latitude") is not None:
            self._forecast(j["latitude"], j["longitude"], j.get("city") or j.get("region") or "Twoja lokalizacja")
        else:
            self.weather = {"error": "Nie udało się ustalić lokalizacji"}; self.weather_changed.emit()

    def _forecast(self, lat, lon, name):
        r = self._request(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,is_day"
            "&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&wind_speed_unit=kmh")
        r.finished.connect(lambda r=r: self._forecast_done(r, name))

    def _forecast_done(self, r, name):
        j = self._json(r)
        try:
            c, d = j["current"], j["daily"]
            self.weather = {"city": name, "temp": c["temperature_2m"], "feels": c["apparent_temperature"],
                            "hum": c["relative_humidity_2m"], "code": c["weather_code"],
                            "wind": c["wind_speed_10m"], "day": c.get("is_day", 1),
                            "max": d["temperature_2m_max"][0], "min": d["temperature_2m_min"][0],
                            "daily": [(d["time"][i], d["weather_code"][i], d["temperature_2m_min"][i],
                                       d["temperature_2m_max"][i]) for i in range(1, min(6, len(d["time"])))]}
        except Exception:
            self.weather = {"error": "Brak danych pogodowych"}
        self.weather_changed.emit()

    def set_city(self, query):
        q = QUrl.toPercentEncoding(query).data().decode()
        r = self._request(f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1&language=pl&format=json")
        r.finished.connect(lambda r=r: self._city_done(r))

    def _city_done(self, r):
        j = self._json(r)
        res = j.get("results") if isinstance(j, dict) else None
        if res:
            c = res[0]
            self.settings["weather_city"] = {"name": c.get("name", "?"), "lat": c["latitude"], "lon": c["longitude"]}
            self.save_settings(); self.fetch_weather()
        else:
            self.weather = {"error": "Nie znaleziono takiego miasta"}; self.weather_changed.emit()

    def add_recent(self, name, url):
        self.bump_day(emit=False)
        self.recent = [r for r in self.recent if r["url"] != url]
        self.recent.insert(0, {"name": name, "url": url})
        self.recent = self.recent[:8]
        self._write(RECENT, self.recent)
        self.fetch_icon(url)
        self.changed.emit()

    # --- favicony ---
    def _request(self, url, timeout=8000):
        req = QNetworkRequest(QUrl(url))
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "Mozilla/5.0 Luna")
        req.setTransferTimeout(timeout)
        return self.nam.get(req)

    def fetch_icon(self, url, force=False):
        host = QUrl(url).host()
        if not host or (icon_path(url).exists() and not force):
            return
        self._try([f"https://{host}/favicon.ico",
                   f"https://icons.duckduckgo.com/ip3/{host}.ico"], url)

    def _try(self, urls, page_url):
        if not urls:
            return
        reply = self._request(urls[0])
        reply.finished.connect(lambda r=reply: self._done(r, urls[1:], page_url))

    def _done(self, reply, rest, page_url):
        pm = QPixmap()
        ok = (reply.error() == QNetworkReply.NetworkError.NoError
              and pm.loadFromData(reply.readAll()) and pm.width() >= 16)
        reply.deleteLater()
        if ok:
            ICONS.mkdir(exist_ok=True)
            pm.save(str(icon_path(page_url)), "PNG")
            self.changed.emit()
        else:
            self._try(rest, page_url)

    # --- fonty (Inter + Playfair Display) ---
    def ensure_fonts(self):
        try:
            FONT_DIR.mkdir(exist_ok=True)
        except OSError:
            return
        for fn, url in FONT_URLS.items():
            path = FONT_DIR / fn
            if not path.exists():
                r = self._request(url, 40000)
                r.finished.connect(lambda r=r, path=path: self._font_done(r, path))

    def _font_done(self, reply, path):
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = bytes(reply.readAll())
                if len(data) > 50000:
                    path.write_bytes(data)
                    if QFontDatabase.addApplicationFont(str(path)) >= 0:
                        QApplication.instance().setStyleSheet(full_style())
                        self.changed.emit()
                    else:
                        path.unlink(missing_ok=True)
        except OSError:
            pass
        reply.deleteLater()


class AddDialog(QDialog):
    """Własna strona + wybór z listy popularnych aplikacji."""

    def __init__(self, parent, existing):
        super().__init__(parent)
        self.setWindowTitle("Dodaj aplikacje"); self.resize(420, 540)
        lay = QVBoxLayout(self); lay.setSpacing(8)
        h = QLabel("Własna strona"); h.setObjectName("h2"); lay.addWidget(h)
        self.name = QLineEdit(placeholderText="Nazwa (opcjonalnie)")
        self.url = QLineEdit(placeholderText="Adres, np. wp.pl")
        lay.addWidget(self.name); lay.addWidget(self.url)
        h2 = QLabel("Popularne – zaznacz, które dodać"); h2.setObjectName("h2"); lay.addWidget(h2)
        self.list = QListWidget()
        for n, u in CATALOG:
            it = QListWidgetItem(n + ("  (już dodano)" if u in existing else ""))
            it.setData(Qt.ItemDataRole.UserRole, (n, u))
            if u in existing:
                it.setFlags(Qt.ItemFlag.NoItemFlags)
            else:
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(Qt.CheckState.Unchecked)
            self.list.addItem(it)
        lay.addWidget(self.list)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def chosen(self):
        out = []
        if self.url.text().strip():
            u = normalize(self.url.text())
            out.append((self.name.text().strip() or host_of(u).split(".")[0].capitalize(), u))
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(it.data(Qt.ItemDataRole.UserRole))
        return out


WMO = {0: ("Bezchmurnie", "sun"), 1: ("Głównie słonecznie", "sun"), 2: ("Częściowe zachmurzenie", "partly"),
       3: ("Pochmurno", "cloud"), 45: ("Mgła", "fog"), 48: ("Mgła szronowa", "fog"),
       51: ("Lekka mżawka", "rain"), 53: ("Mżawka", "rain"), 55: ("Gęsta mżawka", "rain"),
       56: ("Marznąca mżawka", "rain"), 57: ("Marznąca mżawka", "rain"),
       61: ("Lekki deszcz", "rain"), 63: ("Deszcz", "rain"), 65: ("Silny deszcz", "rain"),
       66: ("Marznący deszcz", "rain"), 67: ("Marznący deszcz", "rain"),
       71: ("Lekki śnieg", "snow"), 73: ("Śnieg", "snow"), 75: ("Silny śnieg", "snow"), 77: ("Ziarna śniegu", "snow"),
       80: ("Przelotny deszcz", "rain"), 81: ("Przelotny deszcz", "rain"), 82: ("Ulewa", "rain"),
       85: ("Przelotny śnieg", "snow"), 86: ("Przelotny śnieg", "snow"),
       95: ("Burza", "storm"), 96: ("Burza z gradem", "storm"), 99: ("Burza z gradem", "storm")}
LEVELS = ["#242424", "#444444", "#737373", "#aeaeae", "#ececec"]


def weather_pixmap(kind: str) -> QPixmap:
    S = 64
    pm = QPixmap(S, S); pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#ececec"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    nob = Qt.BrushStyle.NoBrush

    def sun(cx, cy, r, ray=6):
        p.drawEllipse(QPointF(cx, cy), r, r)
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(QPointF(cx + (r + 4) * math.cos(a), cy + (r + 4) * math.sin(a)),
                       QPointF(cx + (r + 4 + ray) * math.cos(a), cy + (r + 4 + ray) * math.sin(a)))

    def cloud(ox=0, oy=0):
        path = QPainterPath()
        path.addEllipse(QRectF(10 + ox, 30 + oy, 20, 20)); path.addEllipse(QRectF(22 + ox, 20 + oy, 26, 26))
        path.addEllipse(QRectF(40 + ox, 30 + oy, 18, 18)); path.addRect(QRectF(20 + ox, 36 + oy, 30, 14))
        p.setBrush(QColor("#161616")); p.drawPath(path.simplified()); p.setBrush(nob)

    if kind == "sun":
        sun(32, 32, 9)
    elif kind == "moon":
        path = QPainterPath(); path.addEllipse(QRectF(16, 12, 32, 32))
        cut = QPainterPath(); cut.addEllipse(QRectF(26, 6, 32, 32))
        p.drawPath(path.subtracted(cut))
    elif kind == "partly":
        sun(24, 24, 7, 5); cloud(4, 8)
    elif kind == "cloud":
        cloud(0, 0)
    elif kind == "rain":
        cloud(0, -8)
        for x in (22, 32, 42):
            p.drawLine(x, 46, x - 3, 55)
    elif kind == "snow":
        cloud(0, -8); p.setBrush(QColor("#ececec"))
        for x, y in ((22, 48), (32, 54), (42, 48)):
            p.drawEllipse(QPointF(x, y), 1.8, 1.8)
    elif kind == "storm":
        cloud(0, -8)
        p.drawPolyline(QPolygonF([QPointF(35, 40), QPointF(28, 50), QPointF(35, 50), QPointF(30, 60)]))
    elif kind == "fog":
        for (x1, x2, y) in ((14, 50, 24), (20, 54, 34), (14, 46, 44)):
            p.drawLine(x1, y, x2, y)
    p.end()
    return pm


class Heatmap(QWidget):
    """Kalendarz aktywności jak na GitHubie: kolumny = tygodnie (pn–nd), jasność = liczba aktywności."""
    W, C, G = 15, 12, 3
    LX, TY = 18, 16  # miejsce na podpisy dni tygodnia (lewo) i miesięcy (góra)
    MONTHS = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]

    def __init__(self, store):
        super().__init__()
        self.store = store; self.setMouseTracking(True)
        self.setFixedSize(self.LX + self.W * (self.C + self.G) - self.G,
                          self.TY + 7 * (self.C + self.G) - self.G + 26)

    @staticmethod
    def level(n):
        return 0 if n <= 0 else 1 if n <= 2 else 2 if n <= 6 else 3 if n <= 14 else 4

    def start(self, today):
        return today - timedelta(days=today.weekday()) - timedelta(weeks=self.W - 1)

    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        days = self.store.settings.get("days", {})
        today = date.today(); start = self.start(today); C, G, LX, TY = self.C, self.G, self.LX, self.TY
        small = p.font(); small.setPixelSize(9); p.setFont(small); p.setPen(QColor("#6b6b6b"))
        step = C + G
        for row, name in ((0, "Pn"), (2, "Śr"), (4, "Pt")):
            p.drawText(QRectF(0, TY + row * step - 1, LX - 2, C + 2),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
        last = -9
        for col in range(self.W):
            m = (start + timedelta(weeks=col)).month
            prev = (start + timedelta(weeks=col - 1)).month if col else None
            nxt = (start + timedelta(weeks=1)).month
            if (col == 0 and nxt == m) or (col > 0 and m != prev):
                if col - last >= 3:
                    p.drawText(QRectF(LX + col * step, 0, 30, TY - 3),
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.MONTHS[m - 1])
                    last = col
        for col in range(self.W):
            for row in range(7):
                d = start + timedelta(days=col * 7 + row)
                if d > today:
                    continue
                r = QRectF(LX + col * step, TY + row * step, C, C)
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(LEVELS[self.level(days.get(d.isoformat(), 0))]))
                p.drawRoundedRect(r, 3, 3)
                if d == today:
                    p.setPen(QPen(QColor("#ffffff"), 1)); p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), 3, 3)
        y = TY + 7 * step - G + 10
        p.setPen(QColor("#6b6b6b"))
        p.drawText(QRectF(LX, y, 40, C), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Mniej")
        x = LX + 36
        for lv in LEVELS:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(lv)); p.drawRoundedRect(QRectF(x, y, C, C), 3, 3); x += C + 2
        p.setPen(QColor("#6b6b6b"))
        p.drawText(QRectF(x + 4, y, 50, C), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Więcej")

    def mouseMoveEvent(self, ev):
        pt = ev.position(); step = self.C + self.G
        col, row = int((pt.x() - self.LX) // step), int((pt.y() - self.TY) // step)
        tip = ""
        if 0 <= col < self.W and 0 <= row < 7 and pt.x() >= self.LX and pt.y() >= self.TY:
            d = self.start(date.today()) + timedelta(days=col * 7 + row)
            if d <= date.today():
                tip = f"{d.strftime('%d.%m.%Y')} — aktywność: {self.store.settings.get('days', {}).get(d.isoformat(), 0)}"
        self.setToolTip(tip)


class WeekStrip(QWidget):
    """Siedem kółek: które dni bieżącego tygodnia były aktywne."""

    def __init__(self, store):
        super().__init__()
        self.store = store; self.setFixedHeight(48)

    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        days = self.store.settings.get("days", {}); today = date.today()
        mon = today - timedelta(days=today.weekday()); step = self.width() / 7
        f = p.font(); f.setPixelSize(10); p.setFont(f)
        for i in range(7):
            d = mon + timedelta(days=i); cx = step * (i + 0.5); cy = 15
            active = days.get(d.isoformat(), 0) > 0 and d <= today
            if active:
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#ececec")); p.drawEllipse(QPointF(cx, cy), 11, 11)
                p.setPen(QPen(QColor("#111111"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.drawPolyline(QPolygonF([QPointF(cx - 4, cy), QPointF(cx - 1, cy + 3.5), QPointF(cx + 4.5, cy - 3)]))
            else:
                p.setPen(QPen(QColor("#2f2f2f"), 1.6)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), 10.5, 10.5)
            if d == today:
                p.setPen(QPen(QColor("#6f6f6f"), 1)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), 14, 14)
            p.setPen(QColor("#ffffff") if d == today else QColor("#7a7a7a"))
            p.drawText(QRectF(cx - 12, 33, 24, 13), Qt.AlignmentFlag.AlignCenter, "PWŚCPSN"[i])


def dni(n):
    return "dzień" if n == 1 else "dni"


def stat_row(layout, label):
    h = QHBoxLayout(); a = QLabel(label); a.setObjectName("muted2")
    v = QLabel("–"); v.setObjectName("h3")
    h.addWidget(a); h.addStretch(); h.addWidget(v); layout.addLayout(h)
    return v


def section(text):
    c = QLabel(text.upper()); c.setObjectName("cap")
    return c


class StreakCard(QFrame):
    """Lewy panel na całą wysokość: seria, tydzień, kalendarz aktywności i statystyki."""

    def __init__(self, store):
        super().__init__()
        self.store = store; self.setObjectName("card"); self.setFixedWidth(280)
        l = QVBoxLayout(self); l.setContentsMargins(20, 18, 20, 18); l.setSpacing(4)
        l.addWidget(section("Seria"))
        row = QHBoxLayout(); row.setSpacing(8)
        self.num = QLabel("0"); self.num.setObjectName("bignum")
        self.unit = QLabel("dni z rzędu"); self.unit.setObjectName("muted2")
        row.addWidget(self.num); row.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignBottom); row.addStretch()
        l.addLayout(row)
        self.best = QLabel(); self.best.setObjectName("muted"); l.addWidget(self.best)
        l.addSpacing(10)
        self.strip = WeekStrip(store); l.addWidget(self.strip)
        l.addSpacing(10)
        l.addWidget(section("Aktywność"))
        self.map = Heatmap(store); l.addWidget(self.map, 0, Qt.AlignmentFlag.AlignHCenter)
        l.addStretch(1)
        sep = QFrame(); sep.setObjectName("sep"); l.addWidget(sep); l.addSpacing(6)
        self.vals = {key: stat_row(l, label) for key, label in
                     (("week", "Ten tydzień"), ("month", "Ten miesiąc"),
                      ("total", "Dni aktywne łącznie"), ("acts", "Wszystkie aktywności"))}
        store.changed.connect(self.refresh); self.refresh()

    def refresh(self):
        cur, best = self.store.streak(); st = self.store.stats()
        self.num.setText(str(cur)); self.unit.setText(f"{dni(cur)} z rzędu")
        self.best.setText(f"Najdłuższa seria: {best} {dni(best)}")
        self.vals["week"].setText(f"{st['week']} z 7 dni")
        self.vals["month"].setText(f"{st['month']} {dni(st['month'])}")
        self.vals["total"].setText(str(st["total"])); self.vals["acts"].setText(str(st["acts"]))
        self.strip.update(); self.map.update()


class ClockCard(QFrame):
    """Prawy panel na całą wysokość: data, godzina z sekundami, pogoda i prognoza."""
    DAYS = ["pon.", "wt.", "śr.", "czw.", "pt.", "sob.", "niedz."]

    def __init__(self, store):
        super().__init__()
        self.store = store; self.setObjectName("card"); self.setFixedWidth(280)
        self.loc = QLocale(QLocale.Language.Polish)
        l = QVBoxLayout(self); l.setContentsMargins(20, 18, 20, 18); l.setSpacing(4)
        l.addWidget(section("Teraz"))
        self.time = QLabel(); self.time.setObjectName("clock"); self.time.setTextFormat(Qt.TextFormat.RichText)
        self.date = QLabel(); self.date.setObjectName("muted2"); self.date.setWordWrap(True)
        l.addWidget(self.time); l.addWidget(self.date); l.addSpacing(10)
        sep = QFrame(); sep.setObjectName("sep"); l.addWidget(sep); l.addSpacing(8)

        head = QHBoxLayout()
        self.city = QLabel("Pogoda"); self.city.setObjectName("h3")
        more = QToolButton(); more.setObjectName("more"); more.setText("⋯"); more.setFixedSize(28, 28)
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        m = QMenu(more)
        m.addAction("Zmień miasto…", self.change_city)
        m.addAction("Wykryj lokalizację automatycznie", self.auto_city)
        m.addAction("Odśwież pogodę", store.fetch_weather)
        more.setMenu(m)
        head.addWidget(self.city); head.addStretch(); head.addWidget(more)
        l.addLayout(head)

        row = QHBoxLayout(); row.setSpacing(10)
        self.icon = QLabel(); self.icon.setFixedSize(64, 64)
        col = QVBoxLayout(); col.setSpacing(0)
        self.temp = QLabel("…"); self.temp.setObjectName("temp")
        self.desc = QLabel(); self.desc.setObjectName("muted2"); self.desc.setWordWrap(True)
        col.addWidget(self.temp); col.addWidget(self.desc)
        row.addWidget(self.icon); row.addLayout(col, 1)
        l.addLayout(row); l.addSpacing(6)
        self.det = {k: stat_row(l, t) for k, t in (("feels", "Odczuwalna"), ("wind", "Wiatr"),
                                                    ("hum", "Wilgotność"), ("mm", "Min / max"))}

        l.addStretch(1)
        sep2 = QFrame(); sep2.setObjectName("sep"); l.addWidget(sep2); l.addSpacing(6)
        l.addWidget(section("Kolejne dni"))
        self.fc = []
        for _ in range(5):
            h = QHBoxLayout(); h.setSpacing(8)
            d = QLabel(); d.setObjectName("muted2"); d.setFixedWidth(48)
            ic = QLabel(); ic.setFixedSize(24, 24)
            r = QLabel(); r.setObjectName("h3")
            h.addWidget(d); h.addWidget(ic); h.addStretch(); h.addWidget(r)
            l.addLayout(h); self.fc.append((d, ic, r))

        self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(1000)
        store.weather_changed.connect(self.render)
        self.tick(); self.render()

    def tick(self):
        now = QDateTime.currentDateTime()
        self.time.setText(f"{now.toString('HH:mm')}<span style='color:#6b6b6b'>:{now.toString('ss')}</span>")
        txt = self.loc.toString(now.date(), "dddd, d MMMM yyyy")
        self.date.setText(txt[:1].upper() + txt[1:])

    def change_city(self):
        name, ok = QInputDialog.getText(self, "Pogoda", "Miasto:")
        if ok and name.strip():
            self.desc.setText("Szukam…"); self.store.set_city(name.strip())

    def auto_city(self):
        self.store.settings.pop("weather_city", None); self.store.save_settings()
        self.store.fetch_weather()

    def render(self):
        w = self.store.weather
        for d, ic, r in self.fc:
            d.clear(); ic.clear(); r.clear()
        for v in self.det.values():
            v.setText("–")
        if not w:
            self.temp.setText("…"); self.desc.setText("Ładowanie pogody…"); return
        if "error" in w:
            self.temp.setText("–"); self.desc.setText(w["error"]); self.icon.clear(); return
        text, kind = WMO.get(w["code"], ("Pogoda", "cloud"))
        if kind == "sun" and not w.get("day", 1):
            kind = "moon"
        self.icon.setPixmap(weather_pixmap(kind).scaled(
            64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.city.setText(w["city"]); self.temp.setText(f"{round(w['temp'])}°C"); self.desc.setText(text)
        self.det["feels"].setText(f"{round(w['feels'])}°C"); self.det["wind"].setText(f"{round(w['wind'])} km/h")
        self.det["hum"].setText(f"{round(w['hum'])}%"); self.det["mm"].setText(f"{round(w['min'])}° / {round(w['max'])}°")
        for (d, ic, r), (day, code, lo, hi) in zip(self.fc, w.get("daily", [])):
            d.setText(self.DAYS[date.fromisoformat(day).weekday()])
            k = WMO.get(code, ("", "cloud"))[1]
            ic.setPixmap(weather_pixmap(k).scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation))
            r.setText(f"{round(lo)}° / {round(hi)}°")


class Caption(QLabel):
    """Podpis nad wyszukiwarką – zmienia się co kilka sekund (płynne przejście); klik = następny."""

    def __init__(self):
        super().__init__()
        self.setObjectName("headline"); self.setWordWrap(True); self.setMinimumHeight(46)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter); self.setTextFormat(Qt.TextFormat.RichText)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pool = [self.greeting()] + random.sample(CAPTIONS, len(CAPTIONS))
        self.i = 0; self.phase = "idle"
        self.setText(self.pool[0])
        self.eff = QGraphicsOpacityEffect(self); self.setGraphicsEffect(self.eff)
        self.anim = QPropertyAnimation(self.eff, b"opacity", self); self.anim.setDuration(380)
        self.anim.finished.connect(self._step)
        self.timer = QTimer(self); self.timer.timeout.connect(self.next); self.timer.start(9000)

    @staticmethod
    def greeting():
        h = QDateTime.currentDateTime().time().hour()
        if 5 <= h < 12:
            return "Dzień dobry. Od czego <u>zaczniemy</u>?"
        if 12 <= h < 18:
            return "Miłego dnia. Dokąd <u>dziś</u>?"
        if 18 <= h < 23:
            return "Dobry wieczór. Co dziś <u>odkryjesz</u>?"
        return "Jeszcze nie śpisz? Zostań w <u>spokoju</u>."

    def mousePressEvent(self, ev):
        self.next()

    def next(self):
        if self.phase != "idle" or not self.isVisible():
            return
        self.phase = "out"
        self.anim.setStartValue(1.0); self.anim.setEndValue(0.0); self.anim.start()

    def _step(self):
        if self.phase == "out":
            self.i = (self.i + 1) % len(self.pool); self.setText(self.pool[self.i])
            self.phase = "in"
            self.anim.setStartValue(0.0); self.anim.setEndValue(1.0); self.anim.start()
        else:
            self.phase = "idle"


class HomePage(QWidget):
    opened = pyqtSignal(str)

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        outer = QHBoxLayout(self); outer.setContentsMargins(24, 0, 24, 0)
        content = QWidget(); content.setMaximumWidth(1300)
        outer.addStretch(1); outer.addWidget(content, 100); outer.addStretch(1)
        # układ: [karta serii] [środek: logo, podpis, wyszukiwarka, kafelki] [karta zegara] – karty na pełną wysokość
        mid = QHBoxLayout(content); mid.setContentsMargins(0, 14, 0, 14); mid.setSpacing(18)
        lay = QVBoxLayout(); lay.setContentsMargins(0, 12, 0, 0); lay.setSpacing(10)

        logo = QLabel(); logo.setPixmap(logo_pixmap(46)); logo.setFixedSize(46, 46)
        brand = QLabel("Luna"); brand.setObjectName("brand")
        brow = QHBoxLayout(); brow.setSpacing(12)
        brow.addStretch(); brow.addWidget(logo); brow.addWidget(brand); brow.addStretch()
        head = Caption()
        lay.addLayout(brow); lay.addWidget(head); lay.addSpacing(8)

        self.search = QLineEdit(); self.search.setObjectName("search")
        self.search.addAction(glyph("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.returnPressed.connect(self.do_search)
        self.search.setMaximumWidth(680)
        lay.addWidget(self.search, 0, Qt.AlignmentFlag.AlignHCenter)

        center = lay
        top = QHBoxLayout()
        title = QLabel("Aplikacje"); title.setObjectName("h1")
        self.count = QLabel(); self.count.setObjectName("muted")
        add = QPushButton("＋"); add.setObjectName("round"); add.setFixedSize(34, 34)
        add.clicked.connect(self.add_dialog)
        top.addWidget(title); top.addStretch(); top.addWidget(self.count); top.addSpacing(8); top.addWidget(add)
        center.addLayout(top)

        self.grid = QListWidget(); self.grid.setObjectName("grid")
        self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setIconSize(QSize(88, 88)); self.grid.setGridSize(QSize(116, 130))
        self.grid.setMovement(QListView.Movement.Snap)
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.setWordWrap(True); self.grid.setSpacing(6)
        self.grid.itemClicked.connect(lambda it: self.opened.emit(it.data(Qt.ItemDataRole.UserRole)))
        self.grid.customContextMenuRequested.connect(self.menu)
        self.grid.model().rowsMoved.connect(self.reordered)
        center.addWidget(self.grid, 3)

        h2 = QLabel("Ostatnie"); h2.setObjectName("h1"); center.addWidget(h2)
        self.recent = QListWidget(); self.recent.setObjectName("recent")
        self.recent.setIconSize(QSize(38, 38)); self.recent.setSpacing(6)
        self.recent.itemClicked.connect(lambda it: self.opened.emit(it.data(Qt.ItemDataRole.UserRole)))
        center.addWidget(self.recent, 2)

        self.left_card, self.right_card = StreakCard(store), ClockCard(store)
        mid.addWidget(self.left_card)
        mid.addLayout(lay, 1)
        mid.addWidget(self.right_card)

        self.store.changed.connect(self.refresh)
        self.refresh()

    def resizeEvent(self, ev):
        show = self.width() >= 940  # w wąskim oknie (np. z otwartym asystentem) chowamy boczne karty
        self.left_card.setVisible(show); self.right_card.setVisible(show)
        super().resizeEvent(ev)

    def refresh(self):
        self.search.setPlaceholderText(f"Szukaj w {CURRENT[0]} lub wpisz adres…")
        n = len(self.store.items)
        self.count.setText(f"{n} {plural(n)}")
        self.grid.blockSignals(True); self.grid.clear()
        for b in self.store.items:
            it = QListWidgetItem(make_icon(b["name"], b["url"]), b["name"])
            it.setData(Qt.ItemDataRole.UserRole, b["url"])
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            it.setToolTip(b["url"])
            self.grid.addItem(it)
        self.grid.blockSignals(False)
        self.recent.clear()
        for r in self.store.recent:
            it = QListWidgetItem(make_icon(r["name"], r["url"]), f'{r["name"]}\n{host_of(r["url"])}')
            it.setData(Qt.ItemDataRole.UserRole, r["url"])
            it.setSizeHint(QSize(0, 60)); it.setToolTip(r["url"])
            self.recent.addItem(it)

    def do_search(self):
        text = self.search.text().strip()
        if text:
            self.opened.emit(text); self.search.clear()

    def reordered(self, *_):
        self.store.items = [{"name": self.grid.item(i).text(),
                             "url": self.grid.item(i).data(Qt.ItemDataRole.UserRole)}
                            for i in range(self.grid.count())]
        self.store.save(notify=False)

    def add_dialog(self):
        dlg = AddDialog(self, {b["url"] for b in self.store.items})
        if dlg.exec():
            for n, u in dlg.chosen():
                self.store.add(n, u, save=False)
            self.store.save()

    def menu(self, pos):
        it = self.grid.itemAt(pos)
        if not it:
            return
        m = QMenu(self)
        a_edit, a_icon, a_del = m.addAction("Edytuj"), m.addAction("Odśwież ikonę"), m.addAction("Usuń")
        act = m.exec(self.grid.mapToGlobal(pos))
        row = self.grid.row(it)
        b = self.store.items[row]
        if act == a_del:
            del self.store.items[row]; self.store.save()
        elif act == a_icon:
            self.store.fetch_icon(b["url"], force=True)
        elif act == a_edit:
            name, ok = QInputDialog.getText(self, "Edytuj", "Nazwa:", text=b["name"])
            if not ok or not name.strip():
                return
            url, ok = QInputDialog.getText(self, "Edytuj", "Adres:", text=b["url"])
            if ok and url.strip():
                url = normalize(url)
                self.store.items[row] = {"name": name.strip(), "url": url}
                self.store.fetch_icon(url); self.store.save()


class Tab(QStackedWidget):
    """Karta: ekran główny, a po wejściu na stronę – widok WWW (tworzony leniwie)."""

    def __init__(self, store, browser):
        super().__init__()
        self.browser, self.web = browser, None
        self.home = HomePage(store)
        self.addWidget(self.home)
        self.home.opened.connect(self.go)

    def go(self, url):
        if self.web is None:
            self.web = WebView()
            self.web.link_requested.connect(self.browser.open_url_new_tab)
            self.addWidget(self.web)
            self.web.titleChanged.connect(lambda t: self.browser.on_title(self, t))
            self.web.urlChanged.connect(lambda u: self.browser.on_url(self, u))
            self.web.iconChanged.connect(lambda i: self.browser.on_icon(self, i))
            self.web.loadFinished.connect(lambda ok: self.browser.on_loaded(self, ok))
        self.web.setUrl(QUrl(normalize(url)))
        self.setCurrentWidget(self.web)

    def show_home(self):
        self.setCurrentWidget(self.home)

    def on_home(self):
        return self.currentWidget() is self.home


class Assistant(QWidget):
    """Panel boczny z ChatGPT, Claude, Gemini i DeepSeek jako zwykłymi stronami (własne logowanie)."""

    def __init__(self, store, browser):
        super().__init__()
        self.store, self.browser = store, browser
        self.views, self.picks = {}, {}
        self.setObjectName("assistant"); self.setFixedWidth(440)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        head = QWidget(); head.setObjectName("aihead")
        h = QVBoxLayout(head); h.setContentsMargins(12, 10, 12, 8); h.setSpacing(6)
        row = QHBoxLayout(); row.setSpacing(4)
        group = QButtonGroup(self); group.setExclusive(True)
        for name, url in PROVIDERS.items():
            b = QToolButton(); b.setObjectName("aipick"); b.setCheckable(True); b.setText(name)
            b.setIcon(mini_icon(name, url)); b.setIconSize(QSize(16, 16))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=name: self.select(n))
            group.addButton(b); row.addWidget(b); self.picks[name] = b
        row.addStretch()
        h.addLayout(row)

        tools = QHBoxLayout(); tools.setSpacing(2)
        self.hint = QLabel("Zaloguj się raz – Luna zapamięta sesję."); self.hint.setObjectName("muted")
        tools.addWidget(self.hint); tools.addStretch()
        for kind, tip, fn in (("reload", "Odśwież", self.reload),
                              ("external", "Otwórz w zwykłej karcie", self.open_tab),
                              ("copy", "Skopiuj treść otwartej strony (do wklejenia w czacie)", self.copy_page)):
            tb = QToolButton(); tb.setIcon(glyph(kind)); tb.setIconSize(QSize(22, 22)); tb.setFixedSize(30, 30)
            tb.setToolTip(tip); tb.setCursor(Qt.CursorShape.PointingHandCursor)
            tb.clicked.connect(lambda _=False, f=fn: f()); tools.addWidget(tb)
        h.addLayout(tools)
        lay.addWidget(head)

        self.stack = QStackedWidget(); lay.addWidget(self.stack, 1)
        store.changed.connect(self.refresh_icons)

    def provider(self):
        p = self.store.settings.get("ai_provider", "ChatGPT")
        return p if p in PROVIDERS else "ChatGPT"

    def refresh_icons(self):
        for name, b in self.picks.items():
            b.setIcon(mini_icon(name, PROVIDERS[name]))

    def ensure(self):
        """Wywoływane przy otwarciu panelu: ładuje aktualnie wybraną stronę AI."""
        self.select(self.provider())

    def select(self, name):
        self.store.settings["ai_provider"] = name; self.store.save_settings()
        v = self.views.get(name)
        if v is None:
            v = WebView()
            v.link_requested.connect(self.browser.open_url_new_tab)
            v.setUrl(QUrl(PROVIDERS[name]))
            self.views[name] = v; self.stack.addWidget(v)
        self.stack.setCurrentWidget(v); self.picks[name].setChecked(True)

    def current(self):
        return self.stack.currentWidget()

    def reload(self):
        v = self.current()
        if v:
            v.reload()

    def open_tab(self):
        v = self.current()
        if v:
            self.browser.open_url_new_tab(v.url().toString())

    def copy_page(self):
        t = self.browser.cur()
        if not (t and t.web and not t.on_home()):
            QToolTip.showText(QCursor.pos(), "Najpierw otwórz jakąś stronę w karcie.", self)
            return
        title, url = t.web.title(), t.web.url().toString()

        def done(text):
            QApplication.clipboard().setText(f"Strona: {title}\n{url}\n\n{text[:20000]}")
            QToolTip.showText(QCursor.pos(), "Skopiowano treść strony – wklej ją w czacie (Ctrl+V).", self)
        t.web.page().toPlainText(done)


class Frame(QWidget):
    """Tło okna bez ramki systemowej; wąski margines służy do zmiany rozmiaru okna."""
    M = 6

    def __init__(self):
        super().__init__()
        self.setObjectName("frame"); self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def edges(self, pos):
        e = Qt.Edge(0)
        w = self.window()
        if w.isMaximized() or w.isFullScreen():
            return e
        if pos.x() <= self.M: e |= Qt.Edge.LeftEdge
        if pos.x() >= self.width() - self.M: e |= Qt.Edge.RightEdge
        if pos.y() <= self.M: e |= Qt.Edge.TopEdge
        if pos.y() >= self.height() - self.M: e |= Qt.Edge.BottomEdge
        return e

    def mouseMoveEvent(self, ev):
        e = self.edges(ev.position().toPoint())
        L, R, T, B = Qt.Edge.LeftEdge, Qt.Edge.RightEdge, Qt.Edge.TopEdge, Qt.Edge.BottomEdge
        horiz, vert = bool(e & (L | R)), bool(e & (T | B))
        if horiz and vert:
            cur = (Qt.CursorShape.SizeFDiagCursor if bool(e & L) == bool(e & T)
                   else Qt.CursorShape.SizeBDiagCursor)
        elif horiz:
            cur = Qt.CursorShape.SizeHorCursor
        elif vert:
            cur = Qt.CursorShape.SizeVerCursor
        else:
            cur = None
        self.setCursor(cur) if cur else self.unsetCursor()

    def mousePressEvent(self, ev):
        e = self.edges(ev.position().toPoint())
        h = self.window().windowHandle()
        if ev.button() == Qt.MouseButton.LeftButton and e and h:
            h.startSystemResize(e)


class TitleStrip(QWidget):
    """Pasek kart pełni też rolę paska tytułu: przeciąganie okna, dwuklik = maksymalizacja."""

    def __init__(self):
        super().__init__()
        self.setObjectName("strip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def mousePressEvent(self, ev):
        h = self.window().windowHandle()
        if ev.button() == Qt.MouseButton.LeftButton and h:
            h.startSystemMove()

    def mouseDoubleClickEvent(self, ev):
        w = self.window()
        w.showNormal() if w.isMaximized() else w.showMaximized()


class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Luna"); self.setWindowIcon(app_icon()); self.resize(1300, 860)
        self.setMinimumSize(640, 480)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)  # bez ramki systemowej
        self.store = Store()

        central = Frame(); v = QVBoxLayout(central); self.frame_layout = v
        v.setContentsMargins(5, 5, 5, 5); v.setSpacing(0)

        # --- pasek kart (jednocześnie pasek tytułu) ---
        strip = TitleStrip()
        sl = QHBoxLayout(strip); sl.setContentsMargins(10, 5, 6, 4); sl.setSpacing(6)
        self.bar = QTabBar(); self.bar.setExpanding(False); self.bar.setMovable(True)
        self.bar.setDrawBase(False); self.bar.setElideMode(Qt.TextElideMode.ElideRight)
        self.bar.currentChanged.connect(self.on_tab_changed)
        self.bar.tabMoved.connect(self.on_tab_moved)
        lg = QLabel(); lg.setPixmap(logo_pixmap(22)); lg.setFixedSize(22, 22); lg.setToolTip("Luna")
        sl.addWidget(lg); sl.addSpacing(4)
        sl.addWidget(self.bar); sl.addWidget(self.btn("plus", "Nowa karta (Ctrl+T)", self.new_tab, 30))
        sl.addStretch()
        self.max_btn = self.btn("max", "Maksymalizuj", self.toggle_max, 30)
        close_btn = self.btn("close", "Zamknij", self.close, 30); close_btn.setObjectName("winclose")
        for b in (self.btn("min", "Minimalizuj", self.showMinimized, 30), self.max_btn, close_btn):
            sl.addWidget(b)
        v.addWidget(strip)

        # --- pasek narzędzi ---
        tool = QWidget(); tool.setObjectName("tool")
        tl = QHBoxLayout(tool); tl.setContentsMargins(12, 8, 12, 8); tl.setSpacing(4)
        tl.addWidget(self.btn("back", "Wstecz", lambda: self.nav("back")))
        tl.addWidget(self.btn("forward", "Dalej", lambda: self.nav("forward")))
        tl.addWidget(self.btn("reload", "Odśwież", lambda: self.nav("reload")))
        tl.addWidget(self.btn("home", "Ekran główny", self.go_home))
        tl.addSpacing(6)

        self.address = QLineEdit(); self.address.setObjectName("addr")
        self.address.addAction(glyph("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.address.returnPressed.connect(self.submit)
        self.chip = QToolButton(self.address); self.chip.setObjectName("engine")
        self.chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chip.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.chip.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.chip.setIconSize(QSize(18, 18)); self.chip.setToolTip("Wybierz wyszukiwarkę")
        self.chip.setMenu(QMenu(self.chip))
        inner = QHBoxLayout(self.address); inner.setContentsMargins(0, 0, 6, 0)
        inner.addStretch(); inner.addWidget(self.chip)
        tl.addWidget(self.address, 1)
        tl.addSpacing(6)
        self.star_btn = self.btn("star", "Dodaj stronę do ekranu głównego", self.pin_current)
        tl.addWidget(self.star_btn)
        self.ai_btn = self.btn("assistant", "Asystent AI (Ctrl+J)", self.toggle_assistant)
        tl.addWidget(self.ai_btn)
        v.addWidget(tool)

        self.stack = QStackedWidget()
        body = QHBoxLayout(); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(0)
        body.addWidget(self.stack, 1)
        self.assistant = Assistant(self.store, self); self.assistant.hide()
        body.addWidget(self.assistant)
        v.addLayout(body, 1)
        self.setCentralWidget(central)
        self.store.changed.connect(self.update_engine_ui)
        self.store.changed.connect(self.update_star)
        self.update_engine_ui()

        QShortcut(QKeySequence("Ctrl+T"), self, self.new_tab)
        QShortcut(QKeySequence("Ctrl+J"), self, self.toggle_assistant)
        QShortcut(QKeySequence("Ctrl+W"), self, lambda: self.close_tab(self.cur()))
        QShortcut(QKeySequence("Ctrl+L"), self, lambda: (self.address.setFocus(), self.address.selectAll()))
        self.new_tab()
        self.store.ensure_fonts()

    # --- pomocnicze ---
    def btn(self, kind, tip, fn, size=38):
        b = QToolButton(); b.setIcon(glyph(kind)); b.setIconSize(QSize(size - 8, size - 8))
        b.setFixedSize(size, size); b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda: fn())
        return b

    def update_engine_ui(self):
        cur = CURRENT[0]
        self.chip.setText(cur); self.chip.setIcon(mini_icon(cur, ENGINES[cur]))
        self.address.setPlaceholderText(f"Szukaj w {cur} lub wpisz adres…")
        menu = self.chip.menu(); menu.clear()
        for name in ENGINES:
            a = menu.addAction(mini_icon(name, ENGINES[name]), name + ("\t✓" if name == cur else ""))
            a.triggered.connect(lambda _=False, n=name: QTimer.singleShot(0, lambda: self.store.set_engine(n)))
        self.chip.adjustSize()
        self.address.setTextMargins(0, 0, self.chip.sizeHint().width() + 12, 0)

    def update_star(self):
        t = self.cur()
        pinned = False
        if t and t.web and not t.on_home():
            h = host_of(t.web.url().toString())
            pinned = bool(h) and any(host_of(b["url"]) == h for b in self.store.items)
        self.star_btn.setIcon(glyph("starfill" if pinned else "star"))

    def toggle_assistant(self):
        show = not self.assistant.isVisible()
        self.assistant.setVisible(show)
        self.ai_btn.setIcon(glyph("assistantfill" if show else "assistant"))
        if show:
            self.assistant.ensure()

    def open_url_new_tab(self, url):
        self.new_tab(); self.cur().go(url)

    def toggle_max(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def changeEvent(self, e):
        if e.type() == QEvent.Type.WindowStateChange and hasattr(self, "frame_layout"):
            m = 0 if self.isMaximized() else 5
            self.frame_layout.setContentsMargins(m, m, m, m)
            self.max_btn.setIcon(glyph("restore" if self.isMaximized() else "max"))
        super().changeEvent(e)

    def cur(self):
        return self.stack.currentWidget()

    # --- karty ---
    def new_tab(self):
        t = Tab(self.store, self)
        self.stack.addWidget(t)
        i = self.bar.addTab("Ekran główny")
        cb = QToolButton(); cb.setObjectName("tabclose"); cb.setText("✕"); cb.setFixedSize(18, 18)
        cb.clicked.connect(lambda: self.close_tab(t))
        self.bar.setTabButton(i, QTabBar.ButtonPosition.RightSide, cb)
        self.bar.setCurrentIndex(i)

    def close_tab(self, tab):
        if tab is None:
            return
        if self.bar.count() <= 1:
            self.close(); return
        i = self.stack.indexOf(tab)
        self.bar.removeTab(i); self.stack.removeWidget(tab); tab.deleteLater()
        self.stack.setCurrentIndex(self.bar.currentIndex())
        self.sync_address()

    def on_tab_changed(self, i):
        if 0 <= i < self.stack.count():
            self.stack.setCurrentIndex(i)
        self.sync_address()

    def on_tab_moved(self, frm, to):
        w = self.stack.widget(frm)
        self.stack.removeWidget(w); self.stack.insertWidget(to, w)
        self.stack.setCurrentIndex(self.bar.currentIndex())

    # --- nawigacja ---
    def nav(self, what):
        t = self.cur()
        if t and t.web and not t.on_home():
            getattr(t.web, what)()
        elif what == "forward" and t and t.web is not None:
            t.setCurrentWidget(t.web)

    def go_home(self):
        self.cur().show_home()
        i = self.stack.indexOf(self.cur())
        self.bar.setTabText(i, "Ekran główny"); self.bar.setTabIcon(i, QIcon())
        self.address.clear()

    def submit(self):
        text = self.address.text().strip()
        if text:
            self.cur().go(text)

    def pin_current(self):
        t = self.cur()
        if not (t.web and not t.on_home()):
            return
        name = (t.web.title() or host_of(t.web.url().toString()))[:24]
        name, ok = QInputDialog.getText(self, "Dodaj do ekranu głównego", "Nazwa:", text=name)
        if not (ok and name.strip()):
            return
        url = t.web.url().toString()
        pm = t.web.icon().pixmap(128, 128) if not t.web.icon().isNull() else QPixmap()
        if not pm.isNull():  # favicon już załadowany przez stronę – użyj go
            ICONS.mkdir(exist_ok=True)
            pm.save(str(icon_path(url)), "PNG")
        self.store.add(name.strip(), url)

    # --- zdarzenia strony ---
    def on_title(self, tab, title):
        i = self.stack.indexOf(tab)
        if i >= 0:
            self.bar.setTabText(i, title[:26] or "…")

    def on_icon(self, tab, icon):
        i = self.stack.indexOf(tab)
        if i >= 0:
            self.bar.setTabIcon(i, icon)

    def on_loaded(self, tab, ok):
        if ok and tab.web:
            url = tab.web.url().toString()
            if url.startswith("http"):
                self.store.add_recent((tab.web.title() or host_of(url))[:40], url)

    def on_url(self, tab, url):
        if tab is self.cur() and not tab.on_home():
            self.address.setText(url.toString())
            self.update_star()

    def sync_address(self):
        t = self.cur()
        self.address.setText("" if not t or t.on_home() or not t.web else t.web.url().toString())
        self.update_star()


def load_local_fonts():
    if FONT_DIR.exists():
        for f in FONT_DIR.glob("*.[to]tf"):
            QFontDatabase.addApplicationFont(str(f))


if __name__ == "__main__":
    if sys.platform == "win32":  # własna ikona na pasku zadań (a nie ikona Pythona)
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pl.luna.browser")
        except Exception:
            pass
    app = QApplication(sys.argv)
    migrate_old_data()
    load_local_fonts()
    app.setApplicationName("Luna"); app.setWindowIcon(app_icon())
    app.setStyleSheet(full_style())
    w = Browser(); w.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True); w.show()
    sys.exit(app.exec())
