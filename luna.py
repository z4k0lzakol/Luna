#!/usr/bin/env python3
"""Luna – lekka przeglądarka z kafelkami-aplikacjami, panelami bocznymi (widgety) i asystentem AI.

Instalacja:   pip install PyQt6 PyQt6-WebEngine   (opcjonalnie: psutil – monitor zasobów)
              Windows, sterowanie Spotify/odtwarzaczami bez logowania: pip install winrt-Windows.Media.Control winrt-Windows.Storage.Streams
Uruchomienie: python luna.py

Dane w katalogu domowym (odpowiednik localStorage):
  .luna_ustawienia.json   ustawienia: funkcje, widgety, sesje (tokeny, gdy brak pęku kluczy), notatki, zadania…
  .luna.json (kafelki)    .luna_ostatnie.json (ostatnie)    .luna_historia.json (historia do podpowiedzi)
  .luna_ikony/ favicony   .luna_fonty/ fonty                .luna_profile/ profil przeglądarki (zapamiętane logowania)

Luna nie łączy się z kontami przez zewnętrzne aplikacje (OAuth): liczniki nieprzeczytanych na kafelkach korzystają
z logowania z kart Luny (wspólny profil, SessionBridge), a komunikatory działają w panelu aplikacji.
"""
import sys, json, math, re, html, os, random, base64, time, ast, operator, secrets, hashlib, weakref
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, quote_plus, urlencode
from PyQt6.QtCore import (Qt, QUrl, QSize, QObject, QPoint, QPointF, QRect, QRectF, QEvent, QTimer, QLocale, QDateTime,
                          QFileInfo,
                          QEasingCurve, QElapsedTimer,
                          QPropertyAnimation, pyqtSignal)
from PyQt6.QtGui import (QGuiApplication, QImage, QCursor, QBrush, QRadialGradient, QLinearGradient, QIcon, QPixmap, QPainter, QColor, QFont,
                         QFontDatabase, QFontMetrics, QPen, QPolygonF, QKeySequence, QShortcut, QActionGroup, QTextDocument,
                         QPalette, QPainterPath, QDesktopServices)
from PyQt6.QtNetwork import (QNetworkAccessManager, QNetworkRequest, QNetworkReply, QTcpServer, QHostAddress,
                             QNetworkCookieJar)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QStackedWidget, QTabBar, QToolButton, QLineEdit,
                             QListWidget, QListWidgetItem, QListView, QAbstractItemView, QMenu, QInputDialog,
                             QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QDialog, QDialogButtonBox, QFrame,
                             QScrollArea, QPlainTextEdit, QGraphicsOpacityEffect, QButtonGroup, QToolTip, QComboBox,
                             QCheckBox, QSlider, QProgressBar, QFileDialog, QSizePolicy, QMessageBox, QStyledItemDelegate, QStyle,
                             QGraphicsDropShadowEffect, QSplitter, QSplitterHandle, QTreeWidget, QTreeWidgetItem, QWidgetAction,
                             QSizeGrip, QFileIconProvider)
from PyQt6.QtWebEngineWidgets import QWebEngineView
try:
    from PyQt6.QtSvg import QSvgRenderer   # tło wektorowe (SVG)
except ImportError:
    QSvgRenderer = None
from PyQt6.QtWebEngineCore import (QWebEngineProfile, QWebEnginePage, QWebEngineUrlRequestInterceptor, QWebEngineScript,
                                   QWebEngineDownloadRequest, QWebEngineSettings)
try:   # Qt 6.8+: uprawnienia stron (kamera, mikrofon, powiadomienia…) i wybór ekranu do udostępnienia
    from PyQt6.QtWebEngineCore import QWebEnginePermission
except ImportError:
    QWebEnginePermission = None
try:   # systemowe sterowanie multimediami Windows (SMTC): pip install winrt-Windows.Media.Control winrt-Windows.Storage.Streams
    import asyncio, threading
    from winrt.windows.media.control import (GlobalSystemMediaTransportControlsSessionManager as _SMTC,
                                             GlobalSystemMediaTransportControlsSessionPlaybackStatus as _SMTC_STATUS)
    from winrt.windows.storage.streams import DataReader as _DataReader
except Exception:
    _SMTC = _SMTC_STATUS = _DataReader = None
import adblock   # wbudowana blokada reklam (adblock/); rejestruje własny schemat – musi być przed QApplication

HOME = Path.home()
DATA = HOME / ".luna.json"
# słowniki sprawdzania pisowni (format Chromium .bdic, pobierane przy pierwszym uruchomieniu – nie w repozytorium);
# ścieżka musi być ustawiona przed utworzeniem QApplication
DICT_DIR = HOME / ".luna_slowniki"
try:   # katalog musi istnieć przy starcie silnika, inaczej Qt nie użyje słowników w tej sesji
    DICT_DIR.mkdir(exist_ok=True)
except OSError:
    pass
os.environ.setdefault("QTWEBENGINE_DICTIONARIES_PATH", str(DICT_DIR))
RECENT = HOME / ".luna_ostatnie.json"
HIST = HOME / ".luna_historia.json"
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
QStackedWidget { background:transparent; }
QWidget#clear, QWidget#bgframe, QWidget#qt_scrollarea_viewport { background:transparent; }
QFrame#wf { background:transparent; border:0; }
QCheckBox, QSlider, QProgressBar { background:transparent; }
QScrollArea#sb { background:transparent; border:0; }
QToolTip { background:#1c1c1c; color:#ececec; border:1px solid #333333; padding:5px 8px; }
QPushButton#gbtn { background:#ffffff; color:#1f1f1f; border-radius:18px; padding:8px 18px 8px 12px; font-weight:600; }
QPushButton#gbtn:hover { background:#e9e9e9; }
QToolButton#acct { border-radius:17px; }
QToolButton#acct::menu-indicator { image:none; width:0; }
QFrame#sugg_popup { background:transparent; border:0; }
QFrame#sugg_card { background:#18181b; border:1px solid #2e2e33; border-radius:14px; }
QListWidget#sugg_list { background:transparent; border:0; }
QFrame#acc { background:#161618; border:1px solid #26262a; border-radius:16px; }
QPushButton#spotbtn { background:#1db954; color:#08140c; border-radius:18px; padding:8px 18px; font-weight:700; }
QPushButton#spotbtn:hover { background:#25d366; }
QPushButton#discbtn { background:#5865f2; color:#ffffff; border-radius:18px; padding:8px 18px; font-weight:700; }
QPushButton#discbtn:hover { background:#6b77f5; }
QToolButton#rail { background:rgba(255,255,255,0.06); border-radius:8px; }
QToolButton#rail:hover { background:rgba(255,255,255,0.15); }
QLabel#badge { background:#ececec; color:#111111; border-radius:8px; padding:0 6px; font-size:10px; font-weight:700; }
QLabel#cover { background:#1c1c1c; border-radius:12px; }
QLineEdit#glassin { background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.10); border-radius:10px; padding:7px 10px; }
QLineEdit#glassin:focus { border:1px solid #777777; }
QPlainTextEdit#note { background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.09); border-radius:12px;
                      padding:8px; color:#ececec; selection-background-color:#555555; }
QPlainTextEdit#note:focus { border:1px solid #777777; }
QPushButton#clipitem, QPushButton#newsitem, QPushButton#mailitem { background:rgba(255,255,255,0.05); border:0; border-radius:10px;
                      padding:7px 10px; text-align:left; color:#dedede; font-size:12px; }
QPushButton#clipitem:hover, QPushButton#newsitem:hover, QPushButton#mailitem:hover { background:rgba(255,255,255,0.12); color:#ffffff; }
QComboBox { background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.10); border-radius:10px;
            padding:5px 10px; color:#ececec; }
QComboBox::drop-down { border:0; width:22px; }
QComboBox::down-arrow { image:url("%CHEV%"); width:10px; height:10px; }
QComboBox QAbstractItemView { background:#191919; border:1px solid #2a2a2a; selection-background-color:#2a2a2a; outline:0; color:#ececec; }
QSlider::groove:horizontal { height:4px; background:#2a2a2a; border-radius:2px; }
QSlider::sub-page:horizontal { background:#ececec; border-radius:2px; }
QSlider::handle:horizontal { background:#ececec; width:12px; height:12px; margin:-4px 0; border-radius:6px; }
QProgressBar { background:#242424; border:0; border-radius:3px; }
QProgressBar::chunk { background:#ececec; border-radius:3px; }
QCheckBox#switch::indicator { width:36px; height:20px; }
QCheckBox#switch::indicator:unchecked { image:url("%SWOFF%"); }
QCheckBox#switch::indicator:checked { image:url("%SWON%"); }
QCheckBox#todo { spacing:8px; color:#e6e6e6; }
QCheckBox#todo::indicator { width:20px; height:20px; }
QCheckBox#todo::indicator:unchecked { image:url("%CKOFF%"); }
QCheckBox#todo::indicator:checked { image:url("%CKON%"); }
QDialog#settings { background:#111111; border:1px solid #2c2c2c; }
QWidget#setHead { background:#0d0d0d; border-bottom:1px solid #1e1e1e; }
QFrame#dlgpanel { background:#0c0c0c; border:1px solid #1f1f1f; border-radius:12px; }
QFrame#optcard { background:#161616; border:1px solid #242424; border-radius:12px; }
QFrame#optcard:hover { border:1px solid #333333; }
QLabel#tileicon { background:#1f1f1f; border-radius:10px; }
QLabel#emptyicon { background:#161616; border:1px solid #262626; border-radius:28px; }
QLabel#seclabel { color:#7d7d7d; font-size:11px; font-weight:600; letter-spacing:1px; }
QLabel#menusec { color:#6f6f6f; font-size:11px; font-weight:600; letter-spacing:1px; padding:8px 12px 3px 12px; }
QFrame#menusearchrow { background:#111111; border:1px solid #2a2a2a; border-radius:8px; margin:2px 2px 4px 2px; }
QFrame#menusearchrow:hover { border:1px solid #474747; background:#151515; }
QSizeGrip { background:transparent; width:16px; height:16px; }
QToolButton#splitbtn[on="true"] { background:#2e2e2e; border-radius:6px; }
QListWidget#nav { background:#0d0d0d; border-right:1px solid #1e1e1e; padding:10px 8px; }
QListWidget#nav::item { padding:10px 12px; border-radius:10px; color:#9a9a9a; margin:1px 0; }
QListWidget#nav::item:selected { background:#ececec; color:#111111; font-weight:600; }
QListWidget#nav::item:hover:!selected { background:#1a1a1a; color:#ffffff; }
QListWidget#wlist { background:rgba(255,255,255,0.03); border:1px solid #232323; border-radius:12px; padding:6px; }
QListWidget#wlist::item { padding:9px 8px; border-radius:8px; }
QListWidget#wlist::item:selected { background:#2a2a2a; color:#ffffff; }
QListWidget#wlist::indicator { width:20px; height:20px; }
QListWidget#wlist::indicator:unchecked { image:url("%CKOFF%"); }
QListWidget#wlist::indicator:checked { image:url("%CKON%"); }
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
QTabBar::tab { background:transparent; color:#8c8c8c; height:30px; padding:0 2px 0 14px; margin:1px 2px;
               border-radius:15px; max-width:190px; font-size:13px; }
QTabBar::tab:hover:!selected { background:#1a1a1a; color:#d4d4d4; }
QTabBar::tab:selected { background:#ececec; color:#111111; font-weight:600; }
QToolButton { background:transparent; border:0; border-radius:18px; padding:0; }
QToolButton:hover { background:#1f1f1f; }
QToolButton#tabclose { border-radius:9px; padding:0; margin:0; }
QToolButton#tabclose:hover { background:rgba(128,128,128,0.38); }
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


# Słowa kluczowe aplikacji w pasku adresu: „yt kot” → wyszukiwarka YouTube, samo „yt” → YouTube.
# (nazwa, strona główna, adres wyszukiwania z {q}; „@nazwa” – profil / kanał, „#tag” – tag, gdzie aplikacja to ma)
APPS = {
    "youtube": ("YouTube", "https://www.youtube.com/", "https://www.youtube.com/results?search_query={q}",
                "https://www.youtube.com/@{u}", "https://www.youtube.com/hashtag/{t}"),
    "ytmusic": ("YouTube Music", "https://music.youtube.com/", "https://music.youtube.com/search?q={q}", "", ""),
    "spotify": ("Spotify", "https://open.spotify.com/", "https://open.spotify.com/search/{p}", "", ""),
    "tiktok": ("TikTok", "https://www.tiktok.com/", "https://www.tiktok.com/search?q={q}",
               "https://www.tiktok.com/@{u}", "https://www.tiktok.com/tag/{t}"),
    "facebook": ("Facebook", "https://www.facebook.com/", "https://www.facebook.com/search/top?q={q}",
                 "https://www.facebook.com/{u}", "https://www.facebook.com/hashtag/{t}"),
    "instagram": ("Instagram", "https://www.instagram.com/", "https://www.instagram.com/explore/search/keyword/?q={q}",
                  "https://www.instagram.com/{u}/", "https://www.instagram.com/explore/tags/{t}/"),
    "x": ("X", "https://x.com/", "https://x.com/search?q={q}", "https://x.com/{u}", "https://x.com/hashtag/{t}"),
    "reddit": ("Reddit", "https://www.reddit.com/", "https://www.reddit.com/search/?q={q}", "https://www.reddit.com/user/{u}/", ""),
    "twitch": ("Twitch", "https://www.twitch.tv/", "https://www.twitch.tv/search?term={q}", "https://www.twitch.tv/{u}", ""),
    "soundcloud": ("SoundCloud", "https://soundcloud.com/", "https://soundcloud.com/search?q={q}", "https://soundcloud.com/{u}", ""),
    "pinterest": ("Pinterest", "https://www.pinterest.com/", "https://www.pinterest.com/search/pins/?q={q}", "", ""),
    "netflix": ("Netflix", "https://www.netflix.com/", "https://www.netflix.com/search?q={q}", "", ""),
    "linkedin": ("LinkedIn", "https://www.linkedin.com/", "https://www.linkedin.com/search/results/all/?keywords={q}", "", ""),
}
APP_KEYWORDS = {"yt": "youtube", "youtube": "youtube", "ytm": "ytmusic", "sp": "spotify", "spotify": "spotify",
                "tt": "tiktok", "tiktok": "tiktok", "fb": "facebook", "facebook": "facebook", "ig": "instagram",
                "insta": "instagram", "instagram": "instagram", "tw": "x", "twitter": "x", "rd": "reddit", "reddit": "reddit",
                "twitch": "twitch", "soundcloud": "soundcloud",
                "pinterest": "pinterest", "nf": "netflix", "netflix": "netflix", "linkedin": "linkedin"}


def app_match(text):
    """(nazwa aplikacji, adres, zapytanie) dla „yt kot” / „ig #morze” / „tt @ktoś” / samego „yt”; None – zwykły tekst."""
    w = (text or "").strip().split(None, 1)
    if not w or "://" in w[0]:
        return None
    key = APP_KEYWORDS.get(w[0].lower())
    if key is None:
        return None
    name, home, search, user, tag = APPS[key]
    if len(w) == 1:
        return name, home, ""
    q = w[1].strip()
    if q.startswith("@") and user and " " not in q and len(q) > 1:
        return name, user.format(u=quote(q[1:], safe="._-")), q
    if q.startswith("#") and tag and " " not in q and len(q) > 1:
        return name, tag.format(t=quote(q[1:], safe="._-")), q
    return name, search.format(q=quote_plus(q), p=quote(q, safe="")), q


def normalize(text: str) -> str:
    text = text.strip()
    app = app_match(text)
    if app is not None:
        return app[1]
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


def gicon(btn, kind, size=18):
    """Ikona wektorowa na przycisku zamiast znaku tekstowego (część symboli nie istnieje w czcionce Inter)."""
    btn.setText(""); btn.setIcon(glyph(kind)); btn.setIconSize(QSize(size, size))
    return btn


def _path(pts, close=False):
    path = QPainterPath(QPointF(*pts[0]))
    for x, y in pts[1:]:
        path.lineTo(x, y)
    if close:
        path.closeSubpath()
    return path


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
    elif kind == "gear":
        p.drawEllipse(QPointF(22, 22), 6, 6); p.drawEllipse(QPointF(22, 22), 11, 11)
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(QPointF(22 + 11 * math.cos(a), 22 + 11 * math.sin(a)),
                       QPointF(22 + 15.5 * math.cos(a), 22 + 15.5 * math.sin(a)))
    elif kind == "chev_down":
        p.drawPolyline(P((13, 17), (22, 26), (31, 17)))
    elif kind == "chev_right":
        p.drawPolyline(P((17, 13), (26, 22), (17, 31)))
    elif kind == "history":
        p.drawEllipse(QPointF(22, 22), 12, 12); p.drawPolyline(P((22, 14), (22, 22), (28, 26)))
    elif kind == "tabs":
        p.drawRoundedRect(QRectF(9, 17, 20, 17), 3, 3); p.drawPolyline(P((15, 12), (35, 12), (35, 28)))
    elif kind == "app":
        for gx in (11, 24):
            for gy in (11, 24):
                p.drawRoundedRect(QRectF(gx, gy, 9, 9), 2, 2)
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
    elif kind == "shield":
        p.drawPath(_path([(22, 8), (34, 13), (33, 24), (22, 36), (11, 24), (10, 13)], True))
    elif kind == "key":
        p.drawEllipse(9, 15, 13, 13); p.drawLine(21, 21, 35, 21); p.drawLine(30, 21, 30, 27); p.drawLine(35, 21, 35, 26)
    elif kind == "split":
        p.drawRoundedRect(QRectF(9, 11, 26, 22), 4, 4); p.drawLine(22, 11, 22, 33)
    elif kind == "book":
        p.drawPolyline(P((22, 14), (14, 11), (8, 12), (8, 31), (14, 30), (22, 33)))
        p.drawPolyline(P((22, 14), (30, 11), (36, 12), (36, 31), (30, 30), (22, 33))); p.drawLine(22, 14, 22, 33)
    elif kind == "splitv":
        p.drawRoundedRect(QRectF(11, 9, 22, 26), 4, 4); p.drawLine(11, 22, 33, 22)
    elif kind == "folder":
        p.drawPath(_path([(8, 14), (17, 14), (20, 17), (36, 17), (36, 32), (8, 32)], True))
    elif kind == "swap":
        p.drawPolyline(P((11, 16), (33, 16))); p.drawPolyline(P((28, 11), (33, 16), (28, 21)))
        p.drawPolyline(P((33, 28), (11, 28))); p.drawPolyline(P((16, 23), (11, 28), (16, 33)))
    elif kind == "scrollsync":   # dwie strzałki góra–dół obok siebie (przewijanie razem)
        for x in (15, 29):
            p.drawLine(x, 11, x, 33); p.drawPolyline(P((x - 5, 16), (x, 11), (x + 5, 16))); p.drawPolyline(P((x - 5, 28), (x, 33), (x + 5, 28)))
    elif kind == "layouts":   # trzy kolumny (zapisany układ podziału)
        p.drawRoundedRect(QRectF(8, 10, 28, 24), 4, 4); p.drawLine(17, 10, 17, 34); p.drawLine(27, 10, 27, 34)
    elif kind == "layers":
        p.drawPolygon(P((22, 9), (36, 16), (22, 23), (8, 16))); p.drawPolyline(P((8, 22), (22, 29), (36, 22)))
    elif kind == "moon":
        path = QPainterPath(); path.addEllipse(QRectF(9, 9, 26, 26))
        cut = QPainterPath(); cut.addEllipse(QRectF(17, 4, 26, 26)); p.drawPath(path.subtracted(cut))
    elif kind == "sun":
        p.drawEllipse(QPointF(22, 22), 6.5, 6.5)
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(QPointF(22 + 11 * math.cos(a), 22 + 11 * math.sin(a)), QPointF(22 + 15 * math.cos(a), 22 + 15 * math.sin(a)))
    elif kind == "dots":
        p.setBrush(QColor(color))
        for dx in (12, 22, 32):
            p.drawEllipse(QPointF(dx, 22), 1.6, 1.6)
    elif kind in ("volume", "mute"):
        p.drawPolygon(P((9, 18), (15, 18), (22, 12), (22, 32), (15, 26), (9, 26)))
        if kind == "volume":
            p.drawArc(QRectF(20, 15, 10, 14), -60 * 16, 120 * 16); p.drawArc(QRectF(20, 10, 16, 24), -60 * 16, 120 * 16)
        else:
            p.drawLine(27, 18, 35, 26); p.drawLine(35, 18, 27, 26)
    elif kind == "up":
        p.drawPolyline(P((13, 26), (22, 17), (31, 26)))
    elif kind == "grid":
        for gx, gy in ((9, 9), (24, 9), (9, 24), (24, 24)):
            p.drawRoundedRect(QRectF(gx, gy, 11, 11), 2.5, 2.5)
    elif kind == "timer":
        p.drawEllipse(10, 12, 24, 24); p.drawLine(22, 24, 22, 17); p.drawLine(22, 24, 27, 27); p.drawLine(18, 7, 26, 7)
    elif kind == "ruler":
        p.drawRoundedRect(QRectF(7, 15, 30, 14), 2, 2)
        for rx in (13, 19, 25, 31):
            p.drawLine(rx, 15, rx, 21 if rx % 2 else 23)
    elif kind == "text":
        p.drawLine(11, 11, 33, 11); p.drawLine(22, 11, 22, 34); p.drawLine(17, 34, 27, 34)
    elif kind == "qr":
        for qx, qy in ((8, 8), (24, 8), (8, 24)):
            p.drawRect(QRectF(qx, qy, 12, 12))
        p.drawRect(QRectF(26, 26, 3, 3)); p.drawRect(QRectF(32, 32, 3, 3)); p.drawRect(QRectF(32, 25, 3, 3))
    elif kind == "droplet":
        p.drawPath(_path([(22, 7), (32, 22), (32, 27), (28, 34), (22, 36), (16, 34), (12, 27), (12, 22)], True))
    elif kind == "package":
        p.drawPolygon(P((22, 7), (36, 14), (36, 30), (22, 37), (8, 30), (8, 14))); p.drawPolyline(P((8, 14), (22, 21), (36, 14)))
        p.drawLine(22, 21, 22, 37)
    elif kind == "signal":
        for i, sx in enumerate((10, 18, 26, 34)):
            p.drawLine(sx, 34, sx, 28 - i * 6)
    elif kind == "menu":
        p.drawLine(11, 14, 33, 14); p.drawLine(11, 22, 33, 22); p.drawLine(11, 30, 33, 30)
    elif kind == "window":
        p.drawRoundedRect(QRectF(8, 10, 28, 24), 4, 4); p.drawLine(8, 17, 36, 17)
    elif kind == "private":
        p.drawEllipse(9, 21, 10, 9); p.drawEllipse(25, 21, 10, 9); p.drawLine(19, 25, 25, 25)
        p.drawPolyline(P((7, 21), (12, 11), (32, 11), (37, 21)))
    elif kind == "sidebar":
        p.drawRoundedRect(QRectF(8, 10, 28, 24), 4, 4); p.drawLine(17, 10, 17, 34)
    elif kind == "bookmark":
        p.drawPath(_path([(13, 8), (31, 8), (31, 36), (22, 29), (13, 36)], True))
    elif kind == "download":
        p.drawLine(22, 8, 22, 28); p.drawPolyline(P((14, 21), (22, 29), (30, 21))); p.drawLine(10, 35, 34, 35)
    elif kind == "puzzle":
        p.drawPath(_path([(10, 14), (19, 14), (19, 10), (25, 10), (25, 14), (34, 14), (34, 34), (10, 34)], True))
    elif kind == "trash":
        p.drawLine(9, 13, 35, 13); p.drawPolyline(P((17, 13), (18, 8), (26, 8), (27, 13)))
        p.drawPath(_path([(12, 13), (14, 36), (30, 36), (32, 13)]))
    elif kind == "zoom":
        p.drawEllipse(9, 9, 20, 20); p.drawLine(26, 26, 35, 35); p.drawLine(14, 19, 24, 19); p.drawLine(19, 14, 19, 24)
    elif kind == "fullscreen":
        for a, b, c in (((9, 17), (9, 9), (17, 9)), ((27, 9), (35, 9), (35, 17)), ((35, 27), (35, 35), (27, 35)), ((17, 35), (9, 35), (9, 27))):
            p.drawPolyline(P(a, b, c))
    elif kind == "pin":
        p.drawPath(_path([(16, 8), (28, 8), (26, 20), (31, 26), (13, 26), (18, 20)], True)); p.drawLine(22, 26, 22, 37)
    elif kind == "print":
        p.drawRect(QRectF(14, 8, 16, 9)); p.drawRoundedRect(QRectF(8, 17, 28, 13), 3, 3); p.drawRect(QRectF(14, 25, 16, 11))
    elif kind == "cut":
        p.drawEllipse(9, 26, 9, 9); p.drawEllipse(26, 26, 9, 9); p.drawLine(16, 27, 30, 9); p.drawLine(28, 27, 14, 9)
    elif kind == "paste":
        p.drawRoundedRect(QRectF(10, 11, 24, 26), 3, 3); p.drawRoundedRect(QRectF(16, 7, 12, 7), 2, 2)
    elif kind == "select":
        p.setPen(QPen(QColor(color), 3, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)); p.drawRoundedRect(QRectF(9, 9, 26, 26), 3, 3)
    elif kind == "share":
        p.drawEllipse(9, 18, 8, 8); p.drawEllipse(27, 8, 8, 8); p.drawEllipse(27, 28, 8, 8)
        p.drawLine(16, 20, 28, 13); p.drawLine(16, 24, 28, 31)
    elif kind == "save":
        p.drawPath(_path([(9, 9), (30, 9), (35, 14), (35, 35), (9, 35)], True)); p.drawRect(QRectF(15, 9, 12, 8))
        p.drawRect(QRectF(14, 24, 16, 11))
    elif kind == "tools":
        p.drawLine(11, 33, 24, 20); p.drawEllipse(22, 9, 13, 13)
    elif kind == "help":
        p.drawEllipse(8, 8, 28, 28); p.drawArc(QRectF(17, 13, 10, 10), 160 * 16, -250 * 16); p.drawLine(22, 23, 22, 26)
        p.drawPoint(22, 31)
    elif kind == "exit":
        p.drawLine(13, 13, 31, 31); p.drawLine(31, 13, 13, 31)
    elif kind == "play":
        p.setBrush(QColor(color)); p.drawPolygon(P((15, 11), (33, 22), (15, 33)))
    elif kind == "pause":
        p.setBrush(QColor(color)); p.drawRoundedRect(QRectF(13, 11, 6, 22), 1.5, 1.5); p.drawRoundedRect(QRectF(25, 11, 6, 22), 1.5, 1.5)
    elif kind in ("prev", "next"):
        p.setBrush(QColor(color))
        if kind == "next":
            p.translate(S, 0); p.scale(-1, 1)
        p.drawLine(12, 12, 12, 32); p.drawPolygon(P((32, 12), (17, 22), (32, 32)))
    elif kind in ("chat", "chatfill"):   # dymek rozmowy – panel aplikacji (komunikatory)
        path = QPainterPath(); path.addRoundedRect(QRectF(9, 10, 26, 19), 7, 7)
        path.moveTo(15, 29); path.lineTo(13, 35); path.lineTo(21, 29)
        if kind == "chatfill":
            p.setBrush(QColor(color))
        p.drawPath(path)
        if kind == "chat":
            for x in (16, 22, 28):
                p.drawPoint(QPointF(x, 19.5))
    elif kind == "edit":   # ołówek – zakreślenia i notatki
        p.drawPolygon(P((13, 31), (14, 25), (28, 11), (33, 16), (19, 30)))
        p.drawLine(25, 14, 30, 19)
    elif kind == "eye":   # oko – tryb kompaktowy / pokaż ukryte
        path = QPainterPath(); path.moveTo(8, 22); path.quadTo(22, 8, 36, 22); path.quadTo(22, 36, 8, 22)
        p.drawPath(path); p.drawEllipse(QPointF(22, 22), 4.5, 4.5)
    elif kind == "target":   # celownik – „Ukryj ten element”
        p.drawEllipse(QPointF(22, 22), 9, 9)
        for a, b_, c, d in ((22, 7, 22, 13), (22, 31, 22, 37), (7, 22, 13, 22), (31, 22, 37, 22)):
            p.drawLine(a, b_, c, d)
    p.end()
    return QIcon(pm)


def make_icon(name: str, url: str = "", count: int = 0) -> QIcon:
    """Ciemna karta; w środku favicon strony na jasnej płytce albo – gdy brak – serifowa litera.
    count > 0 → plakietka z licznikiem (np. nieprzeczytane maile) w prawym górnym rogu."""
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
    if count > 0:
        txt = str(count) if count < 100 else "99+"
        f = QFont("Inter"); f.setPixelSize(22); f.setWeight(QFont.Weight.Bold); p.setFont(f)
        w = max(38, p.fontMetrics().horizontalAdvance(txt) + 20); r = QRectF(S - w - 2, 2, w, 38)
        p.setPen(QPen(QColor("#1b1b1b"), 4)); p.setBrush(QColor("#ececec"))
        p.drawRoundedRect(r, 19, 19)
        p.setPen(QColor("#111111")); p.drawText(r, Qt.AlignmentFlag.AlignCenter, txt)
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


STYLE += """
QWidget#tabpanel { background:rgba(10,10,10,0.92); border-right:1px solid #1d1d1d; }
QWidget#tabpanelpop { background:#121212; }
QFrame#tabpop { background:#121212; border:1px solid #2c2c2c; }
QToolButton#logo { background:transparent; border-radius:8px; padding:0; }
QToolButton#logo:hover { background:#1f1f1f; }
QLabel#privchip { background:#2b1f3d; color:#d9c7ff; border-radius:10px; font-size:11px; font-weight:600; }
QMenu#burger { padding:6px; min-width:330px; }
QMenu#burger::item { padding:8px 28px 8px 10px; }
QMenu::separator { height:1px; background:#2a2a2a; margin:6px 6px; }
QWidget#menurow { background:transparent; }
QWidget#menurow QLabel { color:#e6e6e6; }
QToolButton#menuchip { background:transparent; color:#cfcfcf; border-radius:6px; padding:4px 8px; }
QToolButton#menuchip:hover { background:#2a2a2a; color:#ffffff; }
QToolButton#menuchip:checked { background:#3a4a6b; color:#ffffff; }
QFrame#vsep { background:#2f2f2f; }
QFrame#mcard { background:#181818; border:1px solid #262626; border-radius:14px; }
QFrame#mcard:hover { border:1px solid #3a3a3a; }
QLabel#micon { background:#232323; border-radius:10px; }
QFrame#mrow { background:#1d1d1d; border-radius:10px; }
QListWidget#histlist { background:transparent; border:none; outline:0; }
QListWidget#histlist::item { border-radius:8px; padding:2px 6px; color:#dcdcdc; }
QListWidget#histlist::item:hover { background:#1f1f1f; }
QListWidget#histlist::item:selected { background:#2b2b2b; color:#ffffff; }
QTreeWidget#vtabs { background:transparent; border:none; color:#c9c9c9; outline:0; font-size:13px; show-decoration-selected:0; }
QTreeWidget#vtabs::item { height:30px; border-radius:8px; padding-left:2px; }
QTreeWidget#vtabs::item:hover { background:#1c1c1c; color:#ffffff; }
QTreeWidget#vtabs::item:selected { background:#ececec; color:#111111; }
QTreeWidget#vtabs::item:selected { border-top-left-radius:0; border-bottom-left-radius:0; }
QTreeWidget#vtabs::branch:selected { background:#ececec; border-top-left-radius:8px; border-bottom-left-radius:8px; }   /* zaznaczona jest zawsze karta (bez strzałki), więc pigułka obejmuje też margines */
QFrame#notice { background:#1b1b1b; border-bottom:1px solid #2a2a2a; }
QPushButton#primary { background:#ececec; color:#111111; font-weight:600; }
QPushButton#primary:hover { background:#ffffff; }
QPushButton:disabled { color:#5c5c5c; }
QPushButton#primary:disabled { background:#2a2a2a; color:#6a6a6a; }
QSplitter#split { background:#0a0a0a; }
QFrame#splitside { background:#0d0d0d; border:1px solid #1a1a1a; border-radius:9px; }
QFrame#splitside[active="true"] { border:1px solid #4a4a4a; }
QWidget#splithead { background:transparent; }
QLabel#splittitle { color:#6f6f6f; font-size:12px; }
QFrame#splitside[active="true"] QLabel#splittitle { color:#e6e6e6; }
QToolButton#splitbtn { background:transparent; border-radius:6px; padding:0; }
QToolButton#splitbtn:hover { background:#232323; }
QLineEdit#splitaddr { background:#1a1a1a; border:1px solid #2a2a2a; border-radius:16px; padding:6px 14px; color:#dcdcdc; }
QLineEdit#splitaddr:focus { border:1px solid #4a4a4a; }
QListWidget#splitlist { background:transparent; border:none; outline:0; color:#c9c9c9; }
QListWidget#splitlist::item { border-radius:8px; padding:6px 8px; }
QListWidget#splitlist::item:hover { background:#1c1c1c; color:#ffffff; }
"""


def full_style() -> str:
    s = STYLE.replace("%CHEV%", chevron_path())
    imgs = ui_images()
    for tok, key in (("%SWOFF%", "sw_off"), ("%SWON%", "sw_on"), ("%CKOFF%", "ck_off"), ("%CKON%", "ck_on")):
        s = s.replace(tok, imgs.get(key, ""))
    return s


def cur_screen():
    """Ekran, na którym jest kursor (przy kilku monitorach okno otwiera się tam, gdzie pracuje użytkownik)."""
    return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()


def fit_size(w, h, frac=0.92):
    """Rozmiar okna dialogowego przycięty do ekranu (małe laptopy, duże skalowanie Windows 125–200%)."""
    a = cur_screen().availableGeometry()
    return QSize(min(w, int(a.width() * frac)), min(h, int(a.height() * frac)))


POPUPS, _PROFILE = [], []


def get_profile(container: str = "") -> QWebEngineProfile:
    """Jeden trwały profil dla całej Luny: logowania na stronach (też w panelu AI) zostają po restarcie.
    container != "" → osobny profil kontenera (własne ciasteczka i logowania, np. drugie konto w tym samym serwisie)."""
    if container == PRIVATE:   # okno prywatne: profil bez zapisu na dysk (ciasteczka i historia znikają po zamknięciu)
        if PRIVATE not in _CONTAINER_PROFILES:
            prof = QWebEngineProfile(QApplication.instance()); _setup_profile(prof, None)
            _CONTAINER_PROFILES[PRIVATE] = prof
        return _CONTAINER_PROFILES[PRIVATE]
    if container:
        if container not in _CONTAINER_PROFILES:
            prof = QWebEngineProfile("Luna-" + container, QApplication.instance())
            _setup_profile(prof, HOME / ".luna_profile" / "kontenery" / container)
            _CONTAINER_PROFILES[container] = prof
        return _CONTAINER_PROFILES[container]
    if not _PROFILE:
        prof = QWebEngineProfile("Luna", QApplication.instance())
        _setup_profile(prof, HOME / ".luna_profile")
        _PROFILE.append(prof)
    return _PROFILE[0]


def _setup_profile(prof, base):
    if base is not None:
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        prof.setPersistentStoragePath(str(base / "data")); prof.setCachePath(str(base / "cache"))
        prof.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
    if DOWNLOADS:
        prof.downloadRequested.connect(DOWNLOADS[0].on_request)
    # płynność i szybkość: płynne przewijanie (jak w Chrome), wcześniejsze DNS, akcelerowany canvas,
    # natychmiastowe Wstecz / Dalej z pamięci (back-forward cache), większa pamięć podręczna stron
    A = QWebEngineSettings.WebAttribute
    # + pełny ekran na prośbę strony (przycisk w odtwarzaczach filmów) i przechwytywanie ekranu (udostępnianie w rozmowach)
    # + PluginsEnabled: wbudowana przeglądarka PDF silnika (bez tego pliki PDF tylko się pobierają)
    for name in ("ScrollAnimatorEnabled", "DnsPrefetchEnabled", "Accelerated2dCanvasEnabled",
                 "FullScreenSupportEnabled", "ScreenCaptureEnabled", "PluginsEnabled", "PdfViewerEnabled"):
        if hasattr(A, name):
            prof.settings().setAttribute(getattr(A, name), True)
    apply_bfcache(prof)   # błyskawiczne „Wstecz” – przełącznik w Funkcjach (pamięć vs. szybkość cofania)
    if base is not None:
        prof.setHttpCacheMaximumSize(300 * 1024 * 1024)
    apply_spellcheck(prof)
    try:   # decyzje o uprawnieniach zapamiętane na dysku (okno prywatne: tylko w pamięci); powiadomienia stron
        P = QWebEngineProfile.PersistentPermissionsPolicy
        prof.setPersistentPermissionsPolicy(P.StoreOnDisk if base is not None else P.StoreInMemory)
        prof.setNotificationPresenter(SiteNotifications.present)
    except Exception:
        pass
    # zwykły Chromium zamiast „QtWebEngine” w User-Agent – logowanie (np. Google) rzadziej jest blokowane
    prof.setHttpUserAgent(re.sub(r"\s*QtWebEngine/\S+", "", prof.httpUserAgent()))
    if SHIELD:
        SHIELD[0].install(prof)   # osobny interceptor profilu, schemat zasobów zastępczych, kosmetyka
    for name, src, world, point in ((("luna-hasla", PW_JS.replace("%K%", PW_KEY), QWebEngineScript.ScriptWorldId.ApplicationWorld,
                                       QWebEngineScript.InjectionPoint.DocumentReady)),
                                     ("luna-ddg", DDG_JS.replace("%K%", PW_KEY), QWebEngineScript.ScriptWorldId.MainWorld,
                                      QWebEngineScript.InjectionPoint.DocumentCreation),
                                     ("luna-peek", PEEK_JS.replace("%K%", PW_KEY), QWebEngineScript.ScriptWorldId.ApplicationWorld,
                                      QWebEngineScript.InjectionPoint.DocumentCreation)):
        s = QWebEngineScript(); s.setName(name); s.setSourceCode(src); s.setWorldId(world)
        s.setInjectionPoint(point); s.setRunsOnSubFrames(False); prof.scripts().insert(s)


_CONTAINER_PROFILES = {}

# --- pamięć: błyskawiczne „Wstecz” (back-forward cache) jako przełącznik; usypianie kart przy braku RAM ---
BFCACHE = {"on": False}


def apply_bfcache(prof):
    try:
        prof.settings().setAttribute(QWebEngineSettings.WebAttribute.BackForwardCacheEnabled, BFCACHE["on"])
    except (AttributeError, RuntimeError):
        pass


def low_memory():
    """True, gdy w systemie brakuje wolnej pamięci RAM (zajęte ≥ 85% albo wolne < 1,5 GB) – Windows."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS(); m.dwLength = ctypes.sizeof(MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return False
        return m.dwMemoryLoad >= 85 or m.ullAvailPhys < 1.5 * 2**30
    except Exception:
        return False


# --- sprawdzanie pisowni (polski + angielski): czerwone podkreślenia i podpowiedzi pod prawym przyciskiem myszy ---
DICTS = {"pl-PL": "pl-pl-3-0.bdic", "en-US": "en-us-10-1.bdic"}
DICT_URL = "https://redirector.gvt1.com/edgedl/chrome/dict/"
SPELL = {"on": True, "busy": False}


def spell_langs():
    return [lang for lang in DICTS if (DICT_DIR / f"{lang}.bdic").is_file()]


def all_profiles():
    return _PROFILE + list(_CONTAINER_PROFILES.values())


def apply_spellcheck(prof):
    langs = spell_langs() if SPELL["on"] else []
    try:
        prof.setSpellCheckLanguages(langs); prof.setSpellCheckEnabled(bool(langs))
    except Exception:
        pass


def ensure_dictionaries(store, done=None):
    """Pobiera brakujące słowniki (raz; ok. 3,7 MB) i włącza je we wszystkich profilach."""
    missing = [lang for lang in DICTS if not (DICT_DIR / f"{lang}.bdic").is_file()]
    if not missing or SPELL["busy"] or not SPELL["on"]:
        return
    SPELL["busy"] = True
    left = {"n": len(missing)}

    def got(lang, data, err, status):
        if status == 200 and data[:4] == b"BDic" and len(data) < 30 * 1024 * 1024:
            try:
                DICT_DIR.mkdir(parents=True, exist_ok=True)
                tmp = DICT_DIR / f"{lang}.tmp"; tmp.write_bytes(data); tmp.replace(DICT_DIR / f"{lang}.bdic")
            except OSError:
                pass
        left["n"] -= 1
        if left["n"] == 0:
            SPELL["busy"] = False
            for p in all_profiles():
                apply_spellcheck(p)
            if done:
                done()
    for lang in missing:
        store.http(DICT_URL + DICTS[lang], lambda d, e, s, l=lang: got(l, d, e, s), timeout=60000, raw=True)


CONTAINER_COLORS = ["#5b9bff", "#3ddc84", "#f0b232", "#ff5c5c", "#c77dff", "#2ec4b6"]

# --- blokada śledzenia i reklam (na poziomie sieci, bez wtyczek) ---
TRACKERS = set("""doubleclick.net googlesyndication.com googleadservices.com google-analytics.com googletagmanager.com
googletagservices.com adservice.google.com pagead2.googlesyndication.com connect.facebook.net scorecardresearch.com
quantserve.com adnxs.com criteo.com criteo.net taboola.com outbrain.com hotjar.com moatads.com amazon-adsystem.com
adsrvr.org rubiconproject.com pubmatic.com openx.net casalemedia.com 2mdn.net smartadserver.com bidswitch.net teads.tv
mgid.com zemanta.com clarity.ms bat.bing.com mouseflow.com fullstory.com mixpanel.com segment.io segment.com
gemius.pl hit.gemius.pl adocean.pl adform.net adform.com yandex.ru/metrika mc.yandex.ru ads.linkedin.com
analytics.tiktok.com ads-twitter.com static.ads-twitter.com ads.yahoo.com adroll.com doubleverify.com
adsafeprotected.com media.net yieldmo.com sharethrough.com indexww.com lijit.com sovrn.com""".split())
BLOCKLIST = HOME / ".luna_blokady.txt"
_SLD = {"co", "com", "org", "net", "gov", "edu", "ac", "gob"}


def base_domain(host):
    """Przybliżona domena główna: sklep.allegro.pl → allegro.pl, news.bbc.co.uk → bbc.co.uk."""
    p = (host or "").lower().strip(".").split(".")
    return ".".join(p[-3:] if len(p) >= 3 and p[-2] in _SLD else p[-2:])


# Shield (dawna blokada samych domen) zastąpiona przez adblock.AdBlock: listy uBlock Origin / EasyList / polskie filtry
# kompilowane w podprocesie, dopasowanie sieciowe z zasobami zastępczymi, kosmetyka i scriptlety. Bez skompilowanych
# list (pierwsze uruchomienie, brak sieci) działa jak dawniej: TRACKERS + .luna_blokady.txt, tylko cudze domeny.


SHIELD = []

# --- hasła: przechwytywanie formularzy logowania (świat izolowany – skrypty strony go nie widzą) ---
PW_KEY = "__luna_" + secrets.token_hex(8) + ":"
PW_JS = r"""(function(){
 if (window.__lunaPw) return; window.__lunaPw = 1; var K = "%K%", last = 0;
 function grab(root){
   var now = Date.now(); if (now - last < 800) return;
   root = root || document;
   var pws = [].slice.call(root.querySelectorAll('input[type=password]')).filter(function(p){return p.value;});
   var inputs = [].slice.call(root.querySelectorAll('input'));
   function isUser(x){var t=(x.type||'text').toLowerCase(); return (t=='text'||t=='email'||t=='tel') && x.value;}
   if (!pws.length) {   // logowanie dwuetapowe (np. Google): najpierw tylko login
     var u0 = inputs.filter(isUser)[0];
     if (u0 && /mail|user|login|identifier|konto/i.test((u0.name||'')+(u0.id||'')+(u0.autocomplete||'')+(u0.type||'')))
       console.log(K + JSON.stringify({u:u0.value, p:''}));
     return;
   }
   last = now; var pw = pws[0], idx = inputs.indexOf(pw), user = '';
   for (var i = idx - 1; i >= 0; i--) if (isUser(inputs[i])) { user = inputs[i].value; break; }
   if (!user) { var u = document.querySelector('input[autocomplete=username],input[type=email]'); if (u) user = u.value || ''; }
   console.log(K + JSON.stringify({u:user, p:pw.value, n:pws.length}));
 }
 document.addEventListener('submit', function(e){ grab(e.target); }, true);
 document.addEventListener('click', function(e){
   var b = e.target.closest && e.target.closest('button,input[type=submit],[role=button]');
   if (b) setTimeout(function(){ grab(b.form || null); }, 0); }, true);
 document.addEventListener('keydown', function(e){
   if (e.key === 'Enter' && e.target && e.target.tagName === 'INPUT') grab(e.target.form || null); }, true);
})();"""
# DuckDuckGo Email Protection: panel duckduckgo.com/email wysyła token w nagłówku Authorization przy tworzeniu adresu
DDG_JS = r"""(function(){
 if (!/(^|\.)duckduckgo\.com$/.test(location.hostname) || window.__lunaDdg) return; window.__lunaDdg = 1; var K = "%K%";
 function seen(url, auth){ if (auth && /quack\.duckduckgo\.com\/api\/email\/addresses/.test(String(url)) && /^Bearer /i.test(auth))
   console.log(K + "ddg:" + auth.slice(7)); }
 var f = window.fetch; if (f) window.fetch = function(input, init){
   try { var h = (init && init.headers) || (input && input.headers), a = '';
     if (h) a = h.get ? h.get('Authorization') : (h.Authorization || h.authorization || '');
     seen(input && input.url || input, a); } catch (e) {}
   return f.apply(this, arguments); };
 var o = XMLHttpRequest.prototype.open, s = XMLHttpRequest.prototype.setRequestHeader;
 XMLHttpRequest.prototype.open = function(m, u){ this.__lunaU = u; return o.apply(this, arguments); };
 XMLHttpRequest.prototype.setRequestHeader = function(k, v){
   if (/^authorization$/i.test(k)) seen(this.__lunaU, v); return s.apply(this, arguments); };
})();"""
FILL_JS = r"""(function(u, p){
 var pw = [].slice.call(document.querySelectorAll('input[type=password]')).filter(function(x){return x.offsetParent !== null;})[0];
 function set(el, v){ if (!el || v === null) return; el.focus(); el.value = v;
   el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); }
 var inputs = [].slice.call(document.querySelectorAll('input')), user = null;
 if (pw) { for (var i = inputs.indexOf(pw) - 1; i >= 0; i--) { var t = (inputs[i].type||'text').toLowerCase();
   if ((t=='text'||t=='email'||t=='tel') && inputs[i].offsetParent !== null) { user = inputs[i]; break; } } }
 if (!user) user = document.querySelector('input[autocomplete=username],input[type=email]');
 if (u !== null) set(user, u); if (p !== null && pw) set(pw, p);
 return !!pw || !!user;
})(%U%, %P%)"""
GEN_FILL_JS = r"""(function(p){
 var all = [].slice.call(document.querySelectorAll('input[type=password]')).filter(function(x){return x.offsetParent !== null;});
 all.forEach(function(el){ el.focus(); el.value = p;
   el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); });
 return all.length;
})(%P%)"""
EMAIL_FILL_JS = r"""(function(v){
 var a = document.activeElement, el = (a && a.tagName === 'INPUT' && /email|text/.test(a.type||'text')) ? a :
   document.querySelector('input[type=email],input[autocomplete=email],input[name*=mail i]');
 if (!el) return false; el.focus(); el.value = v;
 el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); return true;
})(%V%)"""


DARK = {"on": False, "except": set()}   # ciemny tryb stron (Funkcje / burger) i strony-wyjątki (domeny główne)
LUNA_PAGES = weakref.WeakSet()


def dark_for(url):
    return DARK["on"] and base_domain(QUrl(url).host()) not in DARK["except"]


class LunaPage(QWebEnginePage):
    """Strona z kanałem zwrotnym z naszych skryptów (hasła, token DuckDuckGo) przez komunikaty konsoli z kluczem sesji.
    Pilnuje też ciemnego trybu: włączony w silniku przed wczytaniem strony (wyjątki dla wybranych domen)."""
    pw_captured = pyqtSignal(dict)
    reader_state = pyqtSignal(dict)   # tryb czytania: {"state": "on"|"off"|"none", "prefs": {...}}
    sb_skipped = pyqtSignal(dict)     # YouTube: pominięty fragment sponsorowany {"c": kategoria, "d": sekundy}
    peek_requested = pyqtSignal(str)  # Shift+klik na linku → podgląd w okienku

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent); LUNA_PAGES.add(self)
        self.fullScreenRequested.connect(self._fullscreen)
        if QWebEnginePermission is not None:
            self.permissionRequested.connect(lambda p: ask_permission(self, p))
            self.desktopMediaRequested.connect(lambda r: choose_screen(self, r))

    def _fullscreen(self, req):
        """Pełny ekran na prośbę strony (np. przycisk w odtwarzaczu YouTube) – osobne okno na całym ekranie."""
        try:
            fs = PAGE_FULLSCREEN.get(self)
            if req.toggleOn():
                view = QWebEngineView.forPage(self)
                if fs is not None or view is None:
                    req.reject() if view is None else req.accept(); return
                req.accept(); PAGE_FULLSCREEN[self] = FullScreenWindow(self, view)
            else:
                req.accept()
                if fs is not None:
                    fs.restore()
        except Exception:
            try:
                req.reject()
            except Exception:
                pass

    def apply_dark(self, url=None):
        A = QWebEngineSettings.WebAttribute
        if hasattr(A, "ForceDarkMode"):   # działa od razu, bez przeładowania
            self.settings().setAttribute(A.ForceDarkMode, dark_for(url if url is not None else self.url().toString()))

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if is_main_frame:
            self.apply_dark(url.toString())
        if SHIELD:   # skrypty blokady dla hosta – przed załadowaniem dokumentu (też nawigacje z service workera)
            SHIELD[0].prepare(self, url, is_main_frame)
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    def javaScriptConsoleMessage(self, level, msg, line, src):
        if not msg.startswith(PW_KEY):
            return super().javaScriptConsoleMessage(level, msg, line, src)
        body = msg[len(PW_KEY):]
        if body.startswith("reader:"):
            try:
                d = json.loads(body[7:])
            except ValueError:
                return
            if isinstance(d, dict):
                self.reader_state.emit(d)
            return
        if body.startswith("peek:"):
            u = body[5:].strip()
            if u.startswith(("http://", "https://")):
                self.peek_requested.emit(u)
            return
        if body.startswith("sb:"):
            try:
                d = json.loads(body[3:])
            except ValueError:
                return
            if isinstance(d, dict):
                self.sb_skipped.emit(d)
            return
        if body.startswith("scroll:"):   # wspólne przewijanie stron podziału ekranu
            try:
                r = float(body[7:])
            except ValueError:
                return
            v = QWebEngineView.forPage(self); o = getattr(v, "owner", None)
            if v is not None and hasattr(o, "sync_scroll_from"):
                o.sync_scroll_from(v, r)
            return
        if body.startswith("ddg:"):
            if self.url().host().endswith("duckduckgo.com") and VAULT:
                VAULT[0].set_ddg_token(body[4:].strip())
            return
        try:
            d = json.loads(body)
        except ValueError:
            return
        if isinstance(d, dict):
            d["origin"] = origin_of(self.url().toString()); self.pw_captured.emit(d)


# Wspólne przewijanie w podziale ekranu: strona zgłasza położenie (0…1 wysokości), Luna ustawia je w pozostałych.
SCROLL_SYNC_JS = r"""(function(){
const K = %K%;
if (window.__lunaSS) { window.__lunaSS.on = true; return; }
const st = window.__lunaSS = {on: true, lock: 0, raf: 0};
const el = () => document.scrollingElement || document.documentElement;
addEventListener('scroll', () => {
  if (!st.on || Date.now() - st.lock < 150 || st.raf) return;
  st.raf = requestAnimationFrame(() => { st.raf = 0; const e = el(), m = e.scrollHeight - innerHeight;
    console.log(K + 'scroll:' + (m > 0 ? e.scrollTop / m : 0).toFixed(5)); });
}, {passive: true});
st.set = r => { st.lock = Date.now(); const e = el(); e.scrollTop = Math.round(r * (e.scrollHeight - innerHeight)); };
})();"""
SCROLL_SYNC_OFF_JS = "window.__lunaSS && (window.__lunaSS.on = false);"


PAGE_FULLSCREEN = {}   # strona -> FullScreenWindow


class FullScreenWindow(QWidget):
    """Strona (np. film) na całym ekranie: druga, pełnoekranowa kopia widoku przejmuje tę samą stronę, a po wyjściu
    strona wraca do karty (tak robi przykład Qt – bez przenoszenia widoku między układami okna)."""

    def __init__(self, page, old_view):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.page_, self.old = page, old_view
        self.setWindowTitle(page.title() or "Luna"); self.setWindowIcon(app_icon())
        self.setStyleSheet("background:#000000;")
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self); lay.addWidget(self.view)
        self.view.setPage(page)
        self.hint = QLabel("Naciśnij Esc, aby wyjść z pełnego ekranu", self)
        self.hint.setStyleSheet("background:rgba(20,20,20,220);color:#ececec;border-radius:10px;padding:10px 18px;"
                                "font-size:14px;")
        self.hint.adjustSize()
        for key in ("Esc", "F11"):
            QShortcut(QKeySequence(key), self, activated=lambda: self.page_.triggerAction(QWebEnginePage.WebAction.ExitFullScreen))
        page.destroyed.connect(self._gone)
        scr = (old_view.window().screen() if old_view.window() else None) or cur_screen()
        self.setGeometry(scr.geometry()); self.showFullScreen(); self.activateWindow(); self.view.setFocus()
        self._place_hint(); self.hint.show(); self.hint.raise_()
        self._ht = QTimer(self); self._ht.setSingleShot(True); self._ht.timeout.connect(self.hint.hide)
        self._ht.start(3000)   # timer należy do okna – znika razem z nim (szybkie Esc nie wywoła błędu)

    def _place_hint(self):
        self.hint.move((self.width() - self.hint.width()) // 2, 40)

    def resizeEvent(self, ev):
        super().resizeEvent(ev); self._place_hint()

    def restore(self):
        """Wraca stronę do karty i zamyka okno."""
        PAGE_FULLSCREEN.pop(self.page_, None)
        try:
            if self.old is not None and self.page_ is not None:
                self.old.setPage(self.page_)
                self.old.window().activateWindow(); self.old.setFocus()
        except RuntimeError:
            pass
        self.page_ = None; self.hide(); self.deleteLater()

    def _gone(self, *_):
        for k, v in list(PAGE_FULLSCREEN.items()):
            if v is self:
                PAGE_FULLSCREEN.pop(k, None)
        self.page_ = None; self.hide(); self.deleteLater()

    def closeEvent(self, ev):   # Alt+F4 w trybie pełnoekranowym: wyjście z pełnego ekranu zamiast zamknięcia strony
        if self.page_ is not None:
            ev.ignore(); self.page_.triggerAction(QWebEnginePage.WebAction.ExitFullScreen)
        else:
            super().closeEvent(ev)


PERM_TEXT = {   # „prosi o dostęp do …”
    "MediaAudioCapture": "mikrofonu", "MediaVideoCapture": "kamery", "MediaAudioVideoCapture": "kamery i mikrofonu",
    "DesktopVideoCapture": "udostępniania ekranu", "DesktopAudioVideoCapture": "udostępniania ekranu z dźwiękiem",
    "Notifications": "wysyłania powiadomień", "Geolocation": "Twojej lokalizacji", "ClipboardReadWrite": "schowka",
    "MouseLock": "przechwycenia kursora myszy", "LocalFontsAccess": "czcionek zainstalowanych w systemie"}


def perm_name(ptype):
    return PERM_TEXT.get(getattr(ptype, "name", str(ptype)), "dodatkowych uprawnień")


def ask_permission(page, perm):
    """Prośba strony o uprawnienie: pasek „Zezwolić?” w oknie Luny (albo okienko, gdy to wyskakujące okno).
    Decyzja zapamiętywana przez silnik dla tej witryny (profil na dysku); lista i cofanie w Ustawienia → Prywatność."""
    try:
        perm = QWebEnginePermission(perm)   # kopia: obiekt z sygnału żyje tylko do końca tego wywołania
        if perm.permissionType() == QWebEnginePermission.PermissionType.Unsupported:
            perm.deny(); return
        host = perm.origin().host() or perm.origin().toString()
        text = f"{host} prosi o dostęp do {perm_name(perm.permissionType())}."
        view = QWebEngineView.forPage(page)
        win = view.window() if view is not None else None
        notice = getattr(win, "notice", None)
        if notice is not None:
            win.raise_()
            notice.ask(text, [("Zezwól", perm.grant, True), ("Blokuj", perm.deny, False)], icon="shield")
            return
        mb = QMessageBox(win); mb.setWindowTitle("Luna – uprawnienia"); mb.setText(text)
        ok = mb.addButton("Zezwól", QMessageBox.ButtonRole.AcceptRole); mb.addButton("Blokuj", QMessageBox.ButtonRole.RejectRole)
        mb.exec()
        perm.grant() if mb.clickedButton() is ok else perm.deny()
    except Exception:
        try:
            perm.deny()
        except Exception:
            pass


def choose_screen(page, req):
    """Udostępnianie ekranu (np. w Google Meet): wybór całego ekranu albo jednego okna."""
    try:
        view = QWebEngineView.forPage(page)
        dlg = QDialog(view.window() if view is not None else None); dlg.setWindowTitle("Udostępnij ekran")
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        host = page.url().host()
        lay.addWidget(lbl(f"{host} chce zobaczyć Twój ekran. Wybierz, co udostępnić:", "h3", wrap=True))
        lst = QListWidget(); lst.setObjectName("wlist"); lay.addWidget(lst)
        for kind, model in (("screen", req.screensModel()), ("window", req.windowsModel())):
            if model is None:
                continue
            for r in range(model.rowCount()):
                idx = model.index(r, 0)
                name = model.data(idx, Qt.ItemDataRole.DisplayRole) or ""
                it = QListWidgetItem(("Cały ekran: " if kind == "screen" else "Okno: ") + str(name))
                it.setData(Qt.ItemDataRole.UserRole, (kind, r)); lst.addItem(it)
        if lst.count():
            lst.setCurrentRow(0)
        bb = QDialogButtonBox(); share = bb.addButton("Udostępnij", QDialogButtonBox.ButtonRole.AcceptRole)
        share.setObjectName("primary"); bb.addButton("Anuluj", QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); lay.addWidget(bb)
        lst.itemDoubleClicked.connect(lambda _: dlg.accept())
        if dlg.exec() == QDialog.DialogCode.Accepted and lst.currentItem() is not None:
            kind, r = lst.currentItem().data(Qt.ItemDataRole.UserRole)
            if kind == "screen":
                req.selectScreen(req.screensModel().index(r, 0))
            else:
                req.selectWindow(req.windowsModel().index(r, 0))
        else:
            req.cancel()
    except Exception:
        try:
            req.cancel()
        except Exception:
            pass


class SiteNotifications(QObject):
    """Powiadomienia stron (Notification API) jako dymki systemu Windows; kliknięcie pokazuje kartę strony."""
    _inst = None

    def __init__(self):
        super().__init__(QApplication.instance())
        from PyQt6.QtWidgets import QSystemTrayIcon
        self.tray = QSystemTrayIcon(app_icon(), self); self.tray.setToolTip("Luna")
        self.last = None
        self.tray.messageClicked.connect(self._clicked)

    @classmethod
    def present(cls, n):
        try:
            if cls._inst is None:
                cls._inst = SiteNotifications()
            s = cls._inst; s.last = n
            if not s.tray.isVisible():
                s.tray.show()
            host = n.origin().host()
            s.tray.showMessage(n.title() or host, (n.message() or "") + (f"\n{host}" if host else ""),
                               app_icon(), 8000)
            n.show()
        except Exception:
            pass

    def _clicked(self):
        try:
            if self.last is not None:
                self.last.click()
        except Exception:
            pass


def origin_of(url):
    u = QUrl(url)
    return f"{u.scheme()}://{u.host()}" + (f":{u.port()}" if u.port() > 0 else "")


def gen_password(n=20):
    """Silne hasło: litery, cyfry i znaki, bez mylących (l, I, 0, O)."""
    sets = ["abcdefghijkmnopqrstuvwxyz", "ABCDEFGHJKLMNPQRSTUVWXYZ", "23456789", "!#$%&*+-=?@_"]
    pw = [secrets.choice(s) for s in sets] + [secrets.choice("".join(sets)) for _ in range(max(4, n) - 4)]
    random.SystemRandom().shuffle(pw)
    return "".join(pw)


def _dpapi(data: bytes, protect: bool) -> bytes:
    """Szyfrowanie Windows DPAPI – klucz związany z kontem użytkownika Windows (jak w Chrome i Edge)."""
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data)); ent = ctypes.create_string_buffer(b"Luna-hasla", 10)
    inp = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    extra = BLOB(10, ctypes.cast(ent, ctypes.POINTER(ctypes.c_char))); out = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(inp), None, ctypes.byref(extra), None, None, 0x01, ctypes.byref(out)):
        raise OSError("DPAPI")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


# --- kopia zapasowa: jeden plik zaszyfrowany hasłem (scrypt → klucze; strumień HMAC-SHA256 w trybie licznika; HMAC jako
# znacznik integralności). Tylko biblioteka standardowa. Hasła z DPAPI są w kopii odszyfrowane i chronione hasłem kopii. ---
BACKUP_MAGIC = b"LUNABAK1"
FROZEN = [False]   # True po przywróceniu kopii, do ponownego uruchomienia


def _backup_keys(password, salt):
    k = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2 ** 15, r=8, p=1, maxmem=64 * 2 ** 20, dklen=64)
    return k[:32], k[32:]


def _keystream_xor(key, nonce, data):
    import hmac
    out = bytearray(len(data)); n = 0
    for i in range(0, len(data), 32):
        block = hmac.new(key, nonce + n.to_bytes(8, "big"), hashlib.sha256).digest(); n += 1
        chunk = data[i:i + 32]
        out[i:i + len(chunk)] = (int.from_bytes(chunk, "big") ^ int.from_bytes(block[:len(chunk)], "big")).to_bytes(len(chunk), "big")
    return bytes(out)


def backup_encrypt(payload: dict, password: str) -> bytes:
    import hmac, zlib
    raw = zlib.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"), 9)
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(16); ek, mk = _backup_keys(password, salt)
    body = BACKUP_MAGIC + salt + nonce + _keystream_xor(ek, nonce, raw)
    return body + hmac.new(mk, body, hashlib.sha256).digest()


def backup_decrypt(blob: bytes, password: str) -> dict:
    """ValueError z opisem po polsku: zły plik albo złe hasło."""
    import hmac, zlib
    if len(blob) < 8 + 32 + 32 or not blob.startswith(BACKUP_MAGIC):
        raise ValueError("To nie jest plik kopii zapasowej Luny.")
    body, tag = blob[:-32], blob[-32:]; salt, nonce = body[8:24], body[24:40]; ek, mk = _backup_keys(password, salt)
    if not hmac.compare_digest(hmac.new(mk, body, hashlib.sha256).digest(), tag):
        raise ValueError("Złe hasło albo uszkodzony plik kopii.")
    return json.loads(zlib.decompress(_keystream_xor(ek, nonce, body[40:])).decode("utf-8"))


class Vault(QObject):
    """Menedżer haseł: zaszyfrowany plik ~/.luna_hasla.bin (Windows DPAPI) albo pęk kluczy systemu (pakiet keyring).
    Odszyfrowany tylko w pamięci tego procesu. Zawiera też token DuckDuckGo do aliasów e-mail."""
    changed = pyqtSignal()
    PATH = HOME / ".luna_hasla.bin"

    def __init__(self):
        super().__init__()
        self.mode = "dpapi" if sys.platform == "win32" else ("keyring" if _keyring() else "")
        self.data = {"logins": [], "never": [], "ddg": ""}
        self.error = ""
        self._load()

    def available(self):
        return bool(self.mode)

    def _load(self):
        raw = None
        try:
            if self.mode == "dpapi" and self.PATH.exists():
                raw = _dpapi(self.PATH.read_bytes(), False)
            elif self.mode == "keyring":
                v = _keyring().get_password("Luna", "hasla"); raw = v.encode() if v else None
            if raw:
                self.data.update(json.loads(raw.decode("utf-8")))
        except Exception:
            self.error = "Nie udało się odczytać zapisanych haseł (inne konto Windows albo uszkodzony plik)."

    def save(self):
        raw = json.dumps(self.data, ensure_ascii=False).encode("utf-8")
        try:
            if self.mode == "dpapi":
                tmp = self.PATH.with_suffix(".tmp"); tmp.write_bytes(_dpapi(raw, True)); tmp.replace(self.PATH)
            elif self.mode == "keyring":
                _keyring().set_password("Luna", "hasla", raw.decode("utf-8"))
        except Exception:
            self.error = "Nie udało się zapisać haseł."
        self.changed.emit(); sync_touch()

    def logins(self, origin=None):
        return [x for x in self.data["logins"] if origin is None or x["origin"] == origin]

    def find(self, origin, user):
        return next((x for x in self.data["logins"] if x["origin"] == origin and x["user"] == user), None)

    def put(self, origin, user, pw):
        x = self.find(origin, user)
        if x:
            x.update(pw=pw, ts=int(time.time()))
        else:
            self.data["logins"].append({"origin": origin, "user": user, "pw": pw, "ts": int(time.time())})
        self.save()

    def remove(self, origin, user):
        self.data["logins"] = [x for x in self.data["logins"] if not (x["origin"] == origin and x["user"] == user)]
        self.data.setdefault("deleted", {})[origin + "\n" + user] = int(time.time())   # usunięcie trafi też na inne komputery
        self.save()

    def never(self, origin, add=None):
        if add is None:
            return origin in self.data["never"]
        lst = [o for o in self.data["never"] if o != origin] + ([origin] if add else [])
        self.data["never"] = lst; self.save()

    def set_ddg_token(self, tok):
        if tok and tok != self.data.get("ddg"):
            self.data["ddg"] = tok; self.save()


def _keyring():
    try:
        import keyring
        return keyring
    except Exception:
        return None


VAULT = []


class WebView(QWebEngineView):
    """Widok strony: linki „w nowej karcie” otwierają kartę Luny, okna logowania – osobne okienko."""
    link_requested = pyqtSignal(str)

    def __init__(self, parent=None, container=""):
        super().__init__(parent)
        self.container = container
        self.setPage(LunaPage(get_profile(container), self))
        self.page().setBackgroundColor(QColor("#111111"))

    # karta przeciągnięta z paska kart → podział ekranu (ta strona + przeciągnięta). Przeciąganie nad stroną trafia do
    # wewnętrznego widżetu silnika (focusProxy), więc tam podpinamy filtr; inne przeciągane dane idą do strony jak dotąd.
    def showEvent(self, ev):
        super().showEvent(ev)
        fp = self.focusProxy()
        if fp is not None and getattr(self, "_drop_fp", None) is not fp:
            self._drop_fp = fp; fp.installEventFilter(self)

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop) and ev.mimeData().hasFormat(TAB_MIME):
            if not getattr(self, "owner", None):
                return False
            ev.acceptProposedAction()
            if t == QEvent.Type.Drop:
                b = self.owner.browser; tab = b.tab_from_mime(ev.mimeData())
                QTimer.singleShot(0, lambda: b.drop_tab_on_view(self, tab))
            return True
        return super().eventFilter(obj, ev)

    def contextMenuEvent(self, ev):
        """Polskie menu prawego przycisku z akcjami Luny (karty widoku Luny); wyskakujące okna – menu silnika."""
        b = getattr(getattr(self, "owner", None), "browser", None)
        req = self.lastContextMenuRequest()
        if b is None or req is None:
            return super().contextMenuEvent(ev)
        M = req.mediaType().__class__
        d = {"link": req.linkUrl().toString() if req.linkUrl().isValid() else "", "link_text": req.linkText(),
             "media": req.mediaType(), "media_url": req.mediaUrl().toString() if req.mediaUrl().isValid() else "",
             "sel": req.selectedText(), "edit": req.isContentEditable(), "miss": req.misspelledWord(),
             "sugg": list(req.spellCheckerSuggestions()), "image": req.mediaType() == M.MediaTypeImage,
             "video": req.mediaType() in (M.MediaTypeVideo, M.MediaTypeAudio)}
        pos = ev.globalPos(); d["pt"] = (ev.pos().x(), ev.pos().y())
        _safe_js(self, HL_HOVER, lambda hid, d=d: b.page_context_menu(self, d, hid or "", pos))

    def createWindow(self, wtype):
        W = QWebEnginePage.WebWindowType
        if wtype in (W.WebDialog, W.WebBrowserWindow):  # np. okno logowania Google/OAuth
            pop = WebView(container=self.container); pop.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            pop.resize(520, 720); pop.setWindowTitle("Luna – logowanie"); pop.setWindowIcon(app_icon())
            pop.page().windowCloseRequested.connect(pop.close)
            opener = self.url()

            def first_url(u, p=pop):   # wyskakujące okno reklamowe ($popup) – zamykamy przy pierwszym adresie
                safe_disconnect(p.page().urlChanged, first_url)
                if SHIELD and SHIELD[0].popup_blocked(u, opener):
                    p.close()
            pop.page().urlChanged.connect(first_url)
            POPUPS.append(pop)
            pop.destroyed.connect(lambda _=None, p=pop: POPUPS.remove(p) if p in POPUPS else None)
            pop.show()
            return pop
        tmp = WebView(self, self.container)  # zwykły link: łapiemy docelowy adres i otwieramy go w nowej karcie
        tmp.page().urlChanged.connect(lambda u, t=tmp: self._grab(u, t))
        return tmp

    def _grab(self, url, tmp):
        u = url.toString()
        if u and u != "about:blank":
            tmp.stop(); tmp.deleteLater()
            if SHIELD and SHIELD[0].popup_blocked(url, self.url()):   # filtr $popup: nie otwieramy karty
                return
            self.link_requested.emit(u)


class Store(QObject):
    changed = pyqtSignal()
    weather_changed = pyqtSignal()
    layout_changed = pyqtSignal()
    features_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.nam = QNetworkAccessManager(self)
        self.weather_ts = 0.0
        self._hist_dirty = False
        self._save_timer = QTimer(self); self._save_timer.setSingleShot(True); self._save_timer.timeout.connect(self.save_settings)
        self.items = self._load(DATA, list(DEFAULTS))
        self.recent = self._load(RECENT, [])
        self.history = self._load(HIST, [])
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
        for u in list(ENGINES.values()) + list(PROVIDERS.values()) + ["https://open.spotify.com", "https://discord.com"]:
            self.fetch_icon(u)
        self.weather = {}
        GLASS_ALPHA[0] = int(self.settings.get("glass", 168)); BG.store = self
        self.bump_day(emit=False)  # samo uruchomienie przeglądarki liczy się do serii
        SHIELD.append(adblock.AdBlock(self, home=HOME, legacy_domains=TRACKERS, legacy_file=BLOCKLIST))
        VAULT.append(Vault()); DOWNLOADS.append(DownloadManager())   # przed pierwszym profilem
        self.session = SessionBridge(self)  # logowania z kart Luny dostępne dla widgetów i kafelków

    @staticmethod
    def _load(path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    @staticmethod
    def _write(path, data):
        if FROZEN[0]:   # po przywróceniu kopii – zamykające się okna nie nadpisują przywróconych plików
            return
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
        if FROZEN[0]:
            return
        if self._hist_dirty:
            self._write(HIST, self.history); self._hist_dirty = False
        self._write(SETTINGS, self.settings); sync_touch()
        try:
            os.chmod(SETTINGS, 0o600)  # klucz API tylko dla Ciebie (Linux/macOS)
        except OSError:
            pass

    # --- ustawienia (odpowiednik localStorage: plik JSON w katalogu domowym) ---
    def remove_history(self, pred):
        """Usuwa wpisy historii spełniające warunek (także z sekcji „Ostatnie”)."""
        self.history = [h for h in self.history if not pred(h)]; self.recent = [r for r in self.recent if not pred(r)]
        self._hist_dirty = True; self._write(RECENT, self.recent); self.save_soon(); self.changed.emit()

    def clear_history(self):
        self.history, self.recent = [], []; self._hist_dirty = True
        self._write(RECENT, []); self.save_settings(); self.changed.emit()

    def save_soon(self):
        self._save_timer.start(500)   # debounce zapisu

    def feature(self, name):
        return bool(self.settings.get("features", {}).get(name, FEATURES[name][2]))

    def set_feature(self, name, val):
        self.settings.setdefault("features", {})[name] = bool(val); self.save_settings()
        self.features_changed.emit(); self.layout_changed.emit()

    def wcfg(self, wid):
        d = WIDGETS[wid]; c = self.settings.get("widgets", {}).get(wid, {})
        return {"on": c.get("on", d[3]), "side": c.get("side", d[1]), "order": c.get("order", d[2]),
                "collapsed": c.get("collapsed", False)}

    def set_wcfg(self, wid, emit=True, **kw):
        self.settings.setdefault("widgets", {}).setdefault(wid, {}).update(kw); self.save_soon()
        if emit:
            self.layout_changed.emit()

    def side_order(self, side):
        ids = list(WIDGETS)
        return sorted((w for w in ids if self.wcfg(w)["side"] == side), key=lambda w: (self.wcfg(w)["order"], ids.index(w)))

    def apply_layout(self, left, right, ons=None):
        for side, ids in (("left", left), ("right", right)):
            for i, wid in enumerate(ids):
                c = self.settings.setdefault("widgets", {}).setdefault(wid, {}); c["side"], c["order"] = side, i
                if ons is not None and wid in ons:
                    c["on"] = bool(ons[wid])
        self.save_settings(); self.layout_changed.emit()

    def http(self, url, cb, headers=None, timeout=12000, raw=False):
        """GET z callbackiem cb(dane, błąd, status); dane = JSON albo bajty (raw=True)."""
        req = QNetworkRequest(QUrl(url))
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "Mozilla/5.0 Luna")
        for k, v in (headers or {}).items():
            req.setRawHeader(k.encode(), v.encode())
        req.setTransferTimeout(timeout)
        r = self.nam.get(req)

        def done():
            data = bytes(r.readAll())
            err = r.errorString() if r.error() != QNetworkReply.NetworkError.NoError else None
            status = r.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute); r.deleteLater()
            if raw:
                cb(data, err, status); return
            try:
                try:
                    txt = data.decode("utf-8")
                except UnicodeDecodeError:
                    txt = data.decode("latin-1")
                j = json.loads(txt)
            except Exception:
                j = None
            cb(j, err, status)
        r.finished.connect(done)
        return r

    def save(self, notify=True):
        self._write(DATA, self.items); sync_touch()
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
        self.save_soon()
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
        self.weather_ts = time.time()
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
        self.history = [h for h in self.history if h["url"] != url]    # pełna historia (podpowiedzi, Ctrl+H; max 1000)
        self.history.insert(0, {"name": name, "url": url, "t": int(time.time())}); del self.history[1000:]
        self._hist_dirty = True; self.save_soon()
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
        self.setWindowTitle("Dodaj aplikacje"); self.resize(fit_size(420, 540))
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
        path = QPainterPath(); path.setFillRule(Qt.FillRule.WindingFill)   # suma kształtów = jeden obrys chmury
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


# ======================================================================================
#  TŁO, SZKŁO, WIDGETY BOCZNE (infrastruktura)
# ======================================================================================
WIDGETS = {  # id: (tytuł, domyślna strona, kolejność, domyślnie włączony, funkcja wymagana)
    "streak": ("Seria", "left", 0, True, None),
    "todo": ("Zadania", "left", 1, True, None),
    "notes": ("Notatnik", "left", 2, False, None),
    "pomodoro": ("Pomodoro", "left", 3, False, None),
    "calc": ("Kalkulator", "left", 4, False, None),
    "translate": ("Tłumacz", "left", 5, False, None),
    "clipboard": ("Schowek", "left", 6, False, None),
    "clock": ("Zegar", "right", 0, True, None),
    "weather": ("Pogoda", "right", 1, True, None),
    "markets": ("Rynki", "right", 2, True, "markets"),
    "currency": ("Przelicznik walut", "right", 3, False, "markets"),
    "audio": ("Odtwarzacz audio", "right", 7, False, None),
    "system": ("Monitor zasobów", "right", 8, False, None),
    "rss": ("Wiadomości (RSS)", "right", 9, False, None),
    "parcels": ("Paczki", "right", 12, False, None),
    "countdown": ("Odliczanie", "left", 7, False, None),
    "ping": ("Ping", "right", 13, False, None),
    "pwqr": ("Hasła i kody QR", "left", 8, False, None),
    "picker": ("Próbnik kolorów", "left", 9, False, None),
    "convert": ("Konwerter jednostek i czasu", "left", 10, False, None),
    "textstat": ("Licznik znaków i słów", "left", 11, False, None),
}
FEATURES = {  # id: (nazwa, opis, domyślnie)
    "markets": ("Panele giełdowe i walutowe", "Rynki (akcje, krypto) i przelicznik walut. Wyłączone: brak zapytań o notowania.", True),
    "left": ("Lewy panel boczny", "Pokazuje widgety przypisane do lewej strony.", True),
    "right": ("Prawy panel boczny", "Pokazuje widgety przypisane do prawej strony.", True),
    "everywhere": ("Panele także na stronach WWW", "Domyślnie panele są widoczne tylko na ekranie głównym.", False),
    "suggest": ("Podpowiedzi wyszukiwania", "Lista pod paskiem adresu: historia, kafelki i otwarte karty (lokalnie, bez sieci).", True),
    "suggest_net": ("Podpowiedzi z sieci", "Wysyła wpisywany tekst do wybranej wyszukiwarki po propozycje. Wyłącz dla pełnej prywatności.", True),
    "dark_pages": ("Ciemny tryb stron", "Jasne strony wyświetlają się w ciemnych kolorach, jak reszta Luny (strony z własnym "
                   "ciemnym motywem zostają bez zmian). Wyjątki ustawisz dla pojedynczych stron w menu lub w Wyglądzie.", False),
    "panel_page_bg": ("Panele w kolorze strony", "Na stronach WWW tło pod panelami bocznymi przyjmuje kolor otwartej strony, "
                      "żeby panele nie odstawały. Wyłączone: zawsze tło Luny, jak wcześniej.", True),
    "vertical_tabs": ("Panel kart przypięty po lewej", "Lista kart z grupami na stałe po lewej stronie zamiast paska kart u góry. "
                      "Wyłączone: lista kart i grup otwiera się przyciskiem na pasku narzędzi.", False),
    "workspaces": ("Przestrzenie robocze", "Ikona przestrzeni na pasku kart (np. Praca, Zakupy, Hobby) – lista rozwija się po kliknięciu. "
                   "Wyłączone: ikona znika, a wszystkie karty są widoczne razem.", True),
    "restore_tabs": ("Przywracanie kart", "Po uruchomieniu wracają karty, grupy, przestrzenie i kontenery (strony wczytują się "
                     "dopiero po wejściu na kartę).", True),
    "sleep_tabs": ("Usypianie nieaktywnych kart", "Karty nieużywane przez dłuższy czas zwalniają pamięć RAM i nie zużywają baterii "
                   "(nie dotyczy kart odtwarzających dźwięk).", True),
    "battery_saver": ("Oszczędzanie baterii", "Gdy laptop działa na baterii: nieużywane karty usypiają się po 5 minutach, "
                      "a filmy w kartach w tle zatrzymują się. Na komputerze bez baterii opcja jest ukryta.", True),
    "adblock": ("Blokada reklam i śledzenia", "Wbudowany bloker (bez wtyczek): listy uBlock Origin, EasyList i polskie filtry – "
                "reklamy, śledzenie, wyskakujące okna i komunikaty „wyłącz AdBlocka”. Działa niewidocznie dla stron.", True),
    "passwords": ("Menedżer haseł", "Proponuje zapis haseł po zalogowaniu i sam wypełnia formularze. Hasła są szyfrowane "
                  "na tym komputerze.", True),
    "discord_watch": ("Licznik Discorda w tle", "Ukryty Discord Web (wyciszony) liczy wzmianki dla kafelka Discorda – ok. 200–300 MB RAM. "
                      "Wyłączony: licznik tylko z otwartych kart Discorda.", True),
    "shortcuts": ("Skróty klawiszowe i gesty myszy", "Ctrl+T/W/R/Tab, F5, środkowy przycisk myszy na kartach.", True),
    "assistant": ("Asystent AI", "Panel z ChatGPT, Claude, Gemini i DeepSeek (Ctrl+J).", True),
    "instant_back": ("Błyskawiczne „Wstecz”", "Strony, z których przechodzisz dalej, zostają w pamięci, więc powrót jest "
                     "natychmiastowy – kosztem ok. 50–100 MB RAM za każdą. Wyłączone: „Wstecz” wczytuje stronę ponownie "
                     "(szybko, z pamięci podręcznej na dysku), a Luna zużywa mniej pamięci.", False),
    "translate_offer": ("Propozycja tłumaczenia stron", "Gdy strona jest w innym języku (dowolnym), Luna proponuje "
                        "tłumaczenie na wybrany język – domyślnie polski (Ctrl+Shift+L). Tekst strony trafia do Tłumacza "
                        "Google dopiero po kliknięciu.", True),
    "sponsorblock": ("YouTube: pomijanie sponsorowanych wstawek", "Automatycznie przeskakuje fragmenty sponsorowane, "
                     "autopromocję i prośby o subskrypcję – według otwartej bazy SponsorBlock (sponsor.ajay.app, licencja "
                     "CC BY-NC-SA 4.0). Wysyłane są tylko 4 znaki skrótu identyfikatora filmu.", True),
    "updates": ("Sprawdzanie aktualizacji", "Po starcie i co 12 godzin Luna sprawdza w tle, czy na GitHubie jest nowa wersja, "
                "i proponuje aktualizację jednym kliknięciem.", True),
    "webapps": ("Panel aplikacji", "Komunikatory (WhatsApp, Messenger, Telegram…) i dowolne strony w panelu z boku – "
                "przycisk na górnym pasku (Ctrl+Shift+K). Wyłączony: żadna z tych stron nie działa w tle.", True),
    "spellcheck": ("Sprawdzanie pisowni", "Podkreśla błędy w polach tekstowych (polski i angielski); podpowiedzi pod prawym "
                   "przyciskiem myszy. Słowniki (ok. 4 MB) pobierają się raz przy pierwszym uruchomieniu.", True),
}
GLASS_ALPHA = [168]


def safe_disconnect(sig, slot):
    try:
        sig.disconnect(slot)
    except (TypeError, RuntimeError):
        pass


def luna_bg_svg() -> str:
    """Wektorowe tło (SVG 1920×1080): ciemne, ukośne arkusze z miękkimi cieniami + poświata „księżyca”.
    Wektor skaluje się bez utraty ostrości (Retina/HiDPI); losowość jest ustalona, więc wynik jest powtarzalny."""
    rnd = random.Random(11)
    parts, x = [], -900.0
    while x < 2900:
        w = rnd.choice((44, 66, 92, 128, 176, 236)) * rnd.uniform(0.8, 1.25)
        fill = "url(#sl)" if rnd.random() < 0.55 else "url(#sd)"
        parts.append(f'<rect x="{x:.1f}" y="-1300" width="{w:.1f}" height="3700" fill="{fill}" opacity="{rnd.uniform(0.55, 1.0):.2f}"/>')
        parts.append(f'<rect x="{x:.1f}" y="-1300" width="1.5" height="3700" fill="#ffffff" opacity="{rnd.uniform(0.05, 0.15):.2f}"/>')
        parts.append(f'<rect x="{x + w:.1f}" y="-1300" width="{rnd.uniform(16, 46):.1f}" height="3700" fill="url(#sh)"/>')
        x += w + rnd.uniform(0, 12)
    stripes = "".join(parts)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080">
<defs>
<linearGradient id="base" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1d1e23"/><stop offset="0.55" stop-color="#101114"/><stop offset="1" stop-color="#08080a"/></linearGradient>
<linearGradient id="sl" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#4a4c54" stop-opacity="0.55"/><stop offset="1" stop-color="#25262b" stop-opacity="0.30"/></linearGradient>
<linearGradient id="sd" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#202126" stop-opacity="0.85"/><stop offset="1" stop-color="#0c0c0e" stop-opacity="0.95"/></linearGradient>
<linearGradient id="sh" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000000" stop-opacity="0.5"/><stop offset="1" stop-color="#000000" stop-opacity="0"/></linearGradient>
<radialGradient id="g1" gradientUnits="userSpaceOnUse" cx="1560" cy="170" r="820"><stop offset="0" stop-color="#eceef6" stop-opacity="0.26"/><stop offset="0.4" stop-color="#a6adc2" stop-opacity="0.09"/><stop offset="1" stop-color="#a6adc2" stop-opacity="0"/></radialGradient>
<radialGradient id="g2" gradientUnits="userSpaceOnUse" cx="240" cy="1020" r="900"><stop offset="0" stop-color="#56627f" stop-opacity="0.20"/><stop offset="1" stop-color="#56627f" stop-opacity="0"/></radialGradient>
<radialGradient id="vig" gradientUnits="userSpaceOnUse" cx="960" cy="540" r="1180"><stop offset="0.45" stop-color="#000000" stop-opacity="0"/><stop offset="1" stop-color="#000000" stop-opacity="0.62"/></radialGradient>
</defs>
<rect width="1920" height="1080" fill="url(#base)"/>
<g transform="rotate(30 960 540)">{stripes}</g>
<rect width="1920" height="1080" fill="url(#g1)"/>
<rect width="1920" height="1080" fill="url(#g2)"/>
<rect width="1920" height="1080" fill="url(#vig)"/>
</svg>'''


class Background:
    """Tło okna: wektorowe SVG skalowane w trybie „cover” (wypełnia i centruje bez zniekształceń) w rozdzielczości
    fizycznej ekranu (ostre na Retina/HiDPI) + rozmyta kopia pod szklane panele.
    Cache zależy od rozmiaru, trybu i DPR; przeliczany dopiero po zakończeniu zmiany rozmiaru (debounce)."""
    MAX_PIXELS = 8_300_000   # limit pamięci (~4K): przy większych oknach obniżamy skalę HiDPI

    def __init__(self):
        self.store = self.frame = self.cover = self.blur = self.key = None
        self._svg = self._noise = None
        self.cache = {}   # klucz (rozmiar, tryb, DPR) → (tło, rozmyte tło); kilka okien = kilka rozmiarów

    def mode(self):
        return self.store.settings.get("bg", "image") if self.store else "image"

    def dpr(self, frame=None):
        try:
            f = frame or self.frame
            return f.devicePixelRatioF() if f is not None else 1.0
        except RuntimeError:   # okno już zamknięte
            return 1.0

    def wanted_key(self, size, frame=None):
        return (size.width(), size.height(), self.mode(), round(self.dpr(frame), 2))

    def renderer(self):
        if self._svg is None and QSvgRenderer is not None:
            self._svg = QSvgRenderer(luna_bg_svg().encode("utf-8"))
        return self._svg

    def noise(self):
        """Drobne ziarno nakładane na tło – likwiduje „schodki” (banding) w ciemnych gradientach."""
        if self._noise is None:
            rnd = random.Random(3); data = bytearray()
            for _ in range(128 * 128):
                v = rnd.randrange(256); data += bytes((v, v, v, 9))
            img = QImage(bytes(data), 128, 128, 128 * 4, QImage.Format.Format_RGBA8888).copy()
            self._noise = QPixmap.fromImage(img)
        return self._noise

    def prepare(self, size, frame=None):
        key = self.wanted_key(size, frame)
        if key in self.cache:
            self.cover, self.blur = self.cache[key]; self.key = key
            return key
        w, h = max(1, size.width()), max(1, size.height()); mode, dpr = key[2], key[3]
        if mode == "image" and self.renderer() is not None:
            scale = max(1.0, min(dpr, math.sqrt(self.MAX_PIXELS / (w * h))))
            pm = QPixmap(max(1, int(w * scale)), max(1, int(h * scale))); pm.setDevicePixelRatio(scale)
            p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            k = max(w / 1920.0, h / 1080.0)          # „cover”: bez zniekształceń, wyśrodkowane
            self.renderer().render(p, QRectF((w - 1920 * k) / 2, (h - 1080 * k) / 2, 1920 * k, 1080 * k))
            nz = self.noise(); nz.setDevicePixelRatio(scale); p.drawTiledPixmap(QRect(0, 0, w, h), nz); p.end()
        elif mode == "solid":
            pm = QPixmap(w, h); pm.fill(QColor("#111111"))
        else:  # gradient (a także awaryjnie, gdy brak QtSvg)
            pm = QPixmap(w, h); p = QPainter(pm)
            g = QLinearGradient(0, 0, w, h)
            g.setColorAt(0, QColor("#26282d")); g.setColorAt(0.55, QColor("#16171a")); g.setColorAt(1, QColor("#0b0b0d"))
            p.fillRect(pm.rect(), QBrush(g)); p.end()
        img = pm.toImage()
        small = img.scaled(max(1, w // 14), max(1, h // 14), Qt.AspectRatioMode.IgnoreAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        big = small.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        big.setDevicePixelRatio(1.0)
        self.blur = QPixmap.fromImage(big)
        self.cover, self.key = pm, key
        self.cache[key] = (pm, self.blur)
        while len(self.cache) > 3:   # najstarsze rozmiary wypadają (pamięć)
            self.cache.pop(next(iter(self.cache)))
        return key

    def draw_under(self, p, widget):
        """Rysuje rozmyty fragment tła znajdujący się pod widgetem (efekt matowego szkła)."""
        f = widget.parentWidget()
        while f is not None and not isinstance(f, BgFrame):   # tło okna, w którym jest widget
            f = f.parentWidget()
        if f is not None and f.page_color is not None:     # na stronie WWW: pod szkłem kolor strony
            p.fillRect(widget.rect(), f.color_for(widget)); return
        entry = self.cache.get(getattr(f, "key", None)) if f is not None else None
        if entry is None:
            return
        pos = widget.mapTo(f, QPoint(0, 0))
        p.drawPixmap(0, 0, entry[1], pos.x(), pos.y(), widget.width(), widget.height())


    @staticmethod
    def page_light(widget):
        """Czy widget leży na jasnej stronie WWW (wtedy szkło jest mniej przezroczyste, żeby tekst był czytelny)."""
        f = widget.parentWidget()
        while f is not None and not isinstance(f, BgFrame):
            f = f.parentWidget()
        c = f.color_for(widget) if isinstance(f, BgFrame) else None
        return c is not None and c.lightnessF() > 0.55


BG = Background()


class BgFrame(QWidget):
    """Kontener obszaru roboczego z tłem. Przeliczenie tła po zmianie rozmiaru jest opóźnione (debounce)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("bgframe"); self.key = None
        self.page_color = None   # kolor tła otwartej strony WWW (None = tło Luny, np. na ekranie głównym)
        self.page_color_r = None  # podział ekranu w poziomie: kolor strony po prawej (prawy panel); None = jak page_color
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self._recompute)

    def _recompute(self):
        self.key = BG.prepare(self.size(), self); self.update()
        for w in self.findChildren(WidgetFrame):
            w.update()

    def showEvent(self, ev):
        BG.frame = self
        if self.key is None:
            self.key = BG.prepare(self.size(), self)
        super().showEvent(ev)

    def set_page_color(self, color, right=None):
        if right is not None and color is not None and right == color:
            right = None
        if color != self.page_color or right != self.page_color_r:
            self.page_color, self.page_color_r = color, (right if color is not None else None); self.update()
            for w in self.findChildren(WidgetFrame):
                w.update()

    def color_for(self, widget):
        """Kolor tła pod widgetem: przy podziale ekranu lewa połowa okna – lewa strona, prawa – prawa."""
        if self.page_color_r is None or widget is None:
            return self.page_color
        x = widget.mapTo(self, QPoint(widget.width() // 2, 0)).x() if widget is not self else 0
        return self.page_color if x < self.width() / 2 else self.page_color_r

    def paintEvent(self, ev):
        p = QPainter(self)
        if self.page_color is not None:   # panele boczne na stronie: to samo tło co strona, nic nie odstaje
            if self.page_color_r is None:
                p.fillRect(self.rect(), self.page_color); return
            half = self.width() // 2
            p.fillRect(0, 0, half, self.height(), self.page_color)
            p.fillRect(half, 0, self.width() - half, self.height(), self.page_color_r); return
        p.fillRect(self.rect(), QColor("#111111"))
        if self.key != BG.wanted_key(self.size(), self):
            self._t.start(90)          # trwa zmiana rozmiaru – rysujemy stary cache, nowy po 90 ms ciszy
        entry = BG.cache.get(self.key)
        if entry is not None:
            p.drawPixmap(0, 0, entry[0])


def paint_glass(w, radius=18):
    p = QPainter(w); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath(); path.addRoundedRect(QRectF(w.rect()).adjusted(.5, .5, -.5, -.5), radius, radius)
    p.setClipPath(path)
    BG.draw_under(p, w)
    p.fillPath(path, QColor(14, 14, 16, max(GLASS_ALPHA[0], 228) if BG.page_light(w) else GLASS_ALPHA[0]))
    g = QLinearGradient(0, 0, 0, min(70, max(1, w.height())))
    g.setColorAt(0, QColor(255, 255, 255, 18)); g.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillPath(path, QBrush(g))
    p.setClipping(False); p.setPen(QPen(QColor(255, 255, 255, 30), 1)); p.drawPath(path)


class Sparkline(QWidget):
    """Miniaturowy wykres liniowy (zielony/czerwony zależnie od trendu)."""

    def __init__(self, w=64, h=26):
        super().__init__()
        self.vals, self.up = [], True
        self.setFixedSize(w, h)

    def set_data(self, vals, up):
        self.vals, self.up = [v for v in vals if v is not None], up; self.update()

    def paintEvent(self, ev):
        if len(self.vals) < 2:
            return
        lo, hi = min(self.vals), max(self.vals); span = (hi - lo) or 1.0
        w, h = self.width() - 2, self.height() - 4
        pts = [QPointF(1 + i * w / (len(self.vals) - 1), 2 + h - (v - lo) / span * h) for i, v in enumerate(self.vals)]
        col = QColor("#3ddc84" if self.up else "#ff5c5c")
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill = QPainterPath(); fill.moveTo(pts[0].x(), self.height()); [fill.lineTo(q) for q in pts]
        fill.lineTo(pts[-1].x(), self.height()); fill.closeSubpath()
        g = QLinearGradient(0, 0, 0, self.height()); c1 = QColor(col); c1.setAlpha(70); c2 = QColor(col); c2.setAlpha(0)
        g.setColorAt(0, c1); g.setColorAt(1, c2); p.fillPath(fill, QBrush(g))
        p.setPen(QPen(col, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPolyline(QPolygonF(pts))


class Skeleton(QWidget):
    """Szkielet ładowania (shimmer). Animacja działa tylko, gdy widget jest widoczny."""

    def __init__(self, rows=3):
        super().__init__()
        self.rows, self.phase = rows, 0.0
        self.setFixedHeight(rows * 30)
        self._t = QTimer(self); self._t.timeout.connect(self._tick)

    def _tick(self):
        self.phase = (self.phase + 0.045) % 1.0; self.update()

    def showEvent(self, e):
        self._t.start(50); super().showEvent(e)

    def hideEvent(self, e):
        self._t.stop(); super().hideEvent(e)

    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(Qt.PenStyle.NoPen)
        for i in range(self.rows):
            r = QRectF(0, i * 30 + 4, self.width() * (0.95 if i % 2 == 0 else 0.7), 20)
            g = QLinearGradient(r.left(), 0, r.right(), 0); x = (self.phase + i * 0.12) % 1.0
            g.setColorAt(0, QColor(255, 255, 255, 14)); g.setColorAt(max(0.0, x - 0.0001), QColor(255, 255, 255, 14))
            g.setColorAt(x, QColor(255, 255, 255, 40)); g.setColorAt(min(1.0, x + 0.0001), QColor(255, 255, 255, 14))
            g.setColorAt(1, QColor(255, 255, 255, 14))
            p.setBrush(QBrush(g)); p.drawRoundedRect(r, 7, 7)


WIDGET_MIME = "application/x-luna-widget"
TAB_MIME = "application/x-luna-tab"


class WidgetFrame(QFrame):
    """Szklana ramka widgetu: nagłówek (tytuł, zwijanie, menu) + treść. Timery i sieć działają tylko, gdy
    widget jest widoczny i rozwinięty (start/stop); po wyłączeniu widget jest usuwany z pamięci."""

    def __init__(self, wid, store, host):
        super().__init__()
        self.wid, self.store, self.host = wid, store, host
        self.setObjectName("wf"); self.running = False; self._alive = True
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)  # szerokość narzuca panel, nie zawartość
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        self.head = QWidget(); self.head.setObjectName("clear")
        h = QHBoxLayout(self.head); h.setContentsMargins(16, 9, 8, 4); h.setSpacing(2)
        self.title = QLabel(WIDGETS[wid][0].upper()); self.title.setObjectName("cap")
        self.badge = QLabel(); self.badge.setObjectName("badge"); self.badge.hide()
        h.addWidget(self.title); h.addSpacing(6); h.addWidget(self.badge); h.addStretch()
        self.menu = QMenu(self)
        self.menu_btn = gicon(QToolButton(), "dots", 18); self.menu_btn.setObjectName("more")
        self.menu_btn.setFixedSize(26, 26); self.menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_btn.setMenu(self.menu)
        self.fold_btn = QToolButton(); self.fold_btn.setFixedSize(26, 26); self.fold_btn.setIconSize(QSize(16, 16))
        self.fold_btn.setToolTip("Zwiń / rozwiń"); self.fold_btn.clicked.connect(lambda: self.toggle())
        h.addWidget(self.menu_btn); h.addWidget(self.fold_btn)
        v.addWidget(self.head)
        # nagłówek: kliknięcie zwija, przeciągnięcie przenosi widget (kolejność albo drugi panel)
        self._press = None
        self.head.mousePressEvent = self._head_press
        self.head.mouseMoveEvent = self._head_move
        self.head.mouseReleaseEvent = self._head_release
        self.body = QWidget(); self.body.setObjectName("clear")
        self.lay = QVBoxLayout(self.body); self.lay.setContentsMargins(16, 0, 16, 14); self.lay.setSpacing(6)
        v.addWidget(self.body)
        self.collapsed = bool(store.wcfg(wid)["collapsed"])
        # zwijanie widgetu: łagodny start i koniec (InOutCubic) zamiast stałej prędkości – płynniejsze dla oka
        self.anim = QPropertyAnimation(self.body, b"maximumHeight", self); self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.anim.finished.connect(self._anim_done)
        self.build()
        if self.menu.actions():
            self.menu.addSeparator()
        self.menu.addAction("Zwiń / rozwiń", self.toggle)
        self.menu.addAction("Przesuń w górę", lambda: host.move(wid, -1))
        self.menu.addAction("Przesuń w dół", lambda: host.move(wid, 1))
        self.menu.addAction("Przenieś na drugą stronę", lambda: host.flip(wid))
        self.menu.addAction("Odinstaluj widget", lambda: store.set_wcfg(wid, on=False))
        self.menu.addAction("Rynek Widgetów…", lambda: host.browser.open_market())
        self.body.setVisible(not self.collapsed); self._fold_icon()

    # --- do nadpisania ---
    def build(self): pass
    def start(self): pass
    def stop(self): pass
    def teardown(self): pass
    def refresh_now(self): pass

    def guard(self, fn):
        """Opakowuje callback tak, by nie wywołać go po usunięciu widgetu."""
        def inner(*a):
            if self._alive:
                fn(*a)
        return inner

    def set_badge(self, n):
        self.badge.setText(str(n)); self.badge.setVisible(bool(n))

    def _head_press(self, ev):
        self._press = ev.position().toPoint() if ev.button() == Qt.MouseButton.LeftButton else None

    def _head_move(self, ev):
        if self._press is None or not ev.buttons() & Qt.MouseButton.LeftButton:
            return
        if (ev.position().toPoint() - self._press).manhattanLength() < QApplication.startDragDistance():
            return
        self._press = None
        from PyQt6.QtGui import QDrag
        from PyQt6.QtCore import QMimeData
        md = QMimeData(); md.setData(WIDGET_MIME, self.wid.encode())
        d = QDrag(self.head); d.setMimeData(md)
        pm = self.grab(QRect(0, 0, self.width(), min(self.height(), 140)))
        d.setPixmap(pm.scaledToWidth(max(1, int(pm.width() / max(1.0, pm.devicePixelRatio()) * 0.8)),
                                     Qt.TransformationMode.SmoothTransformation))
        d.setHotSpot(QPoint(20, 12)); d.exec(Qt.DropAction.MoveAction)

    def _head_release(self, ev):
        if self._press is not None and ev.button() == Qt.MouseButton.LeftButton:
            self.toggle()
        self._press = None

    def _fold_icon(self):
        self.fold_btn.setIcon(glyph("chev_right" if self.collapsed else "chev_down", "#9a9a9a"))

    def toggle(self):
        self.collapsed = not self.collapsed
        self.store.set_wcfg(self.wid, collapsed=self.collapsed, emit=False)
        self.anim.stop()
        if self.collapsed:
            self.anim.setStartValue(self.body.height()); self.anim.setEndValue(0)
        else:
            self.body.setMaximumHeight(0); self.body.show()
            self.anim.setStartValue(0); self.anim.setEndValue(max(1, self.body.sizeHint().height()))
        self.anim.start(); self._fold_icon(); self._sync_active()

    def _anim_done(self):
        if self.collapsed:
            self.body.hide()
        self.body.setMaximumHeight(16777215)

    def _sync_active(self):
        want = self.isVisible() and not self.collapsed and getattr(self.host, "app_active", True)
        if want != self.running:
            self.running = want
            (self.start if want else self.stop)()

    def showEvent(self, e):
        super().showEvent(e); QTimer.singleShot(0, self._sync_active)

    def hideEvent(self, e):
        super().hideEvent(e); self._sync_active()

    def shutdown(self):
        self._alive = False
        if self.running:
            self.running = False; self.stop()
        self.teardown()

    def paintEvent(self, ev):
        paint_glass(self)


class SmoothScroll(QScrollArea):
    """Kółko myszy przewija płynnie (krótka animacja z wygaszeniem) zamiast skokami; gładzik zostaje bez zmian.
    Kolejne ruchy kółka w trakcie animacji sumują się do celu – przewijanie nie „szarpie” przy szybkim kręceniu."""

    def wheelEvent(self, ev):
        sb = self.verticalScrollBar(); d = ev.angleDelta().y()
        if not d or not ev.pixelDelta().isNull() or ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            return super().wheelEvent(ev)
        anim = getattr(self, "_anim", None)
        if anim is None:
            anim = self._anim = QPropertyAnimation(sb, b"value", self); anim.setDuration(220)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic); self._goal = sb.value()
        base = self._goal if anim.state() == QPropertyAnimation.State.Running else sb.value()
        self._goal = max(sb.minimum(), min(sb.maximum(), base - d))
        anim.stop(); anim.setStartValue(sb.value()); anim.setEndValue(self._goal); anim.start(); ev.accept()


class SidebarScroll(SmoothScroll):
    """Przewijany obszar panelu o stałej szerokości docelowej. Bez tego Qt przydzielał mu szerokość zawartości (bez
    pionowego paska); gdy pasek się pojawiał (wysoki panel), widok kurczył się o 8 px i obcinał prawą krawędź kart."""
    def sizeHint(self):
        return QSize(Sidebar.W, 400)

    def minimumSizeHint(self):
        return QSize(0, 0)


class Sidebar(QWidget):
    """Boczny panel: przewijana kolumna widgetów + wąska szyna (drawer). Panel sam zwija się do szyny, gdy w oknie
    brakuje miejsca; kliknięcie szyny wysuwa go z powrotem (przeglądarka zwija wtedy drugi, jeśli trzeba)."""
    W, RAIL = 300, 20
    rail_clicked = pyqtSignal(str)

    def __init__(self, side, store):
        super().__init__()
        self.side, self.store = side, store
        self.setObjectName("clear")
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        self.scroll = SidebarScroll(); self.scroll.setObjectName("sb"); self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        # szerokość zawartości < widok (300 − pasek 8 = 292), więc nic nie jest obcinane z pasekiem ani bez niego
        self.inner = QWidget(); self.inner.setObjectName("clear"); self.inner.setFixedWidth(self.W - 16)
        self.col = QVBoxLayout(self.inner)
        # marginesy lustrzane: większy po stronie krawędzi okna, mniejszy po stronie szyny
        self.col.setContentsMargins(*((8, 12, 0, 12) if side == "left" else (0, 12, 8, 12))); self.col.setSpacing(12)
        self.scroll.setWidget(self.inner)
        if side == "left":   # lewy panel: pasek przewijania przy krawędzi okna (po lewej), zawartość bez odwracania
            self.scroll.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.inner.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.scroll.setAlignment((Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute if side == "left"
                                  else Qt.AlignmentFlag.AlignRight) | Qt.AlignmentFlag.AlignTop)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Expanding)
        # półprzezroczyste tło: wymuś pełne odmalowanie przy przewijaniu (bez artefaktów po kopiowaniu pikseli)
        self.scroll.verticalScrollBar().valueChanged.connect(lambda _: self.scroll.viewport().update())
        self.scroll.setMinimumWidth(0); self.scroll.setMaximumWidth(self.W)
        self.rail = QToolButton(); self.rail.setObjectName("rail"); self.rail.setFixedSize(16, 54)
        self.rail.setCursor(Qt.CursorShape.PointingHandCursor); self.rail.setIconSize(QSize(14, 14))
        self.rail.clicked.connect(lambda: self.rail_clicked.emit(self.side))
        rb = QVBoxLayout(); rb.setContentsMargins(2, 18, 2, 0); rb.addWidget(self.rail); rb.addStretch()
        if side == "left":
            lay.addWidget(self.scroll); lay.addLayout(rb)
        else:
            lay.addLayout(rb); lay.addWidget(self.scroll)
        self.anim = QPropertyAnimation(self.scroll, b"maximumWidth", self); self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)   # wysuwanie/zwijanie panelu: szybki start, miękkie wyhamowanie
        self.anim.finished.connect(self._anim_done)
        self.user_collapsed = bool(store.settings.get("sidebar", {}).get(side, False))  # wybór użytkownika (zapisywany)
        self.collapsed = self.user_collapsed                                            # stan widoczny (może być wymuszony)
        self.scroll.setVisible(not self.collapsed); self._rail_icon()
        self._count = 0; self.frames = []
        self.setAcceptDrops(True)   # upuszczenie widgetu: zmiana kolejności albo przeniesienie z drugiego panelu
        self.marker = QFrame(self.inner); self.marker.setStyleSheet("background:#e6e6e6;border-radius:1px")
        self.marker.setFixedHeight(3); self.marker.hide()
        self.on_drop = None   # (wid, side, index) – ustawia WidgetHost

    def _drop_index(self, pos):
        y = self.inner.mapFrom(self, pos).y()
        for i, f in enumerate(self.frames):
            if f.isVisible() and y < f.y() + f.height() / 2:
                return i
        return len(self.frames)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasFormat(WIDGET_MIME):
            ev.acceptProposedAction()

    def dragMoveEvent(self, ev):
        if not ev.mimeData().hasFormat(WIDGET_MIME):
            return
        ev.acceptProposedAction(); i = self._drop_index(ev.position().toPoint())
        vis = [f for f in self.frames if f.isVisible()]
        if i < len(self.frames):
            y = self.frames[i].y() - 7
        else:
            y = (vis[-1].y() + vis[-1].height() + 5) if vis else 12
        self.marker.setGeometry(12, max(2, y), self.inner.width() - 24, 3); self.marker.show(); self.marker.raise_()

    def dragLeaveEvent(self, ev):
        self.marker.hide()

    def dropEvent(self, ev):
        self.marker.hide()
        if ev.mimeData().hasFormat(WIDGET_MIME) and self.on_drop is not None:
            wid = bytes(ev.mimeData().data(WIDGET_MIME)).decode()
            self.on_drop(wid, self.side, self._drop_index(ev.position().toPoint())); ev.acceptProposedAction()

    def has_widgets(self):
        return self._count > 0

    def _rail_icon(self):
        left = self.side == "left"
        kind = ("back" if left else "forward") if not self.collapsed else ("forward" if left else "back")
        self.rail.setIcon(glyph(kind, "#9a9a9a"))
        self.rail.setToolTip("Zwiń panel" if not self.collapsed else "Wysuń panel")

    def set_user_collapsed(self, c):
        self.user_collapsed = c
        self.store.settings.setdefault("sidebar", {})[self.side] = c; self.store.save_soon()

    def set_state(self, c, animate=True):
        """Ustawia widoczny stan (zwinięty/rozwinięty) – bez zmiany wyboru użytkownika."""
        if c == self.collapsed:
            return
        self.collapsed = c; self.anim.stop()
        if not animate:
            self.scroll.setMaximumWidth(self.W); self.scroll.setVisible(not c)
        elif c:
            self.anim.setStartValue(self.scroll.width()); self.anim.setEndValue(0); self.anim.start()
        else:
            self.scroll.setMaximumWidth(0); self.scroll.show()
            self.anim.setStartValue(0); self.anim.setEndValue(self.W); self.anim.start()
        self._rail_icon()

    def _anim_done(self):
        if self.collapsed:
            self.scroll.hide()
        self.scroll.setMaximumWidth(self.W)

    def set_widgets(self, ws):
        while self.col.count():
            self.col.takeAt(0)
        for w in ws:
            self.col.addWidget(w); w.show()
        self.col.addStretch(1)
        self._count = len(ws); self.frames = list(ws)


class WidgetHost(QObject):
    """Tworzy i usuwa widgety zgodnie z ustawieniami (widoczność, strona, kolejność, funkcje)."""

    def __init__(self, store, browser):
        super().__init__()
        self.store, self.browser = store, browser
        self.inst = {}
        self._media = None
        self.app_active = True
        self.left, self.right = Sidebar("left", store), Sidebar("right", store)
        self.left.rail_clicked.connect(browser.toggle_sidebar); self.right.rail_clicked.connect(browser.toggle_sidebar)
        self.left.on_drop = self.right.on_drop = self.drop
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self.sync)
        store.layout_changed.connect(lambda: self._t.start(30))

    def set_active(self, active):
        """Okno nieaktywne → wstrzymujemy odpytywanie API i timery widgetów (oszczędność baterii/CPU)."""
        self.app_active = active
        self.store.session.set_active(active)
        for w in list(self.inst.values()):
            w._sync_active()

    @property
    def media(self):
        if self._media is None:
            self._media = MediaSession()
        return self._media

    def enabled(self, wid):
        _, _, _, _, gate = WIDGETS[wid]; c = self.store.wcfg(wid)
        return c["on"] and (gate is None or self.store.feature(gate)) and self.store.feature(c["side"])

    def sync(self):
        for wid in WIDGETS:
            want = self.enabled(wid)
            if want and wid not in self.inst:
                self.inst[wid] = make_widget(wid, self.store, self)
            elif not want and wid in self.inst:
                w = self.inst.pop(wid); w.shutdown(); w.setParent(None); w.deleteLater()
        for sb in (self.left, self.right):
            ws = sorted((w for wid, w in self.inst.items() if self.store.wcfg(wid)["side"] == sb.side),
                        key=lambda w: self.store.wcfg(w.wid)["order"])
            sb.set_widgets(ws)
        self.browser.update_sidebars()

    def move(self, wid, delta):
        side = self.store.wcfg(wid)["side"]
        ids = self.store.side_order(side); on = [w for w in ids if self.store.wcfg(w)["on"]]
        i = on.index(wid) if wid in on else -1; j = i + delta
        if i < 0 or not 0 <= j < len(on):
            return
        a, b = ids.index(on[i]), ids.index(on[j]); ids[a], ids[b] = ids[b], ids[a]   # pomijamy niezainstalowane
        self.store.apply_layout(**{side: ids, ("right" if side == "left" else "left"):
                                   self.store.side_order("right" if side == "left" else "left")})

    def drop(self, wid, side, index):
        """Przeciągnięty widget ląduje w panelu `side` przed `index`-tym widocznym widgetem (lub na końcu)."""
        if wid not in WIDGETS:
            return
        sb = self.left if side == "left" else self.right
        before = sb.frames[index].wid if index < len(sb.frames) else None
        other = "right" if side == "left" else "left"
        a = [w for w in self.store.side_order(side) if w != wid]
        a.insert(a.index(before) if before in a else len(a), wid)
        b = [w for w in self.store.side_order(other) if w != wid]
        self.store.apply_layout(**{side: a, other: b})

    def flip(self, wid):
        side = self.store.wcfg(wid)["side"]; other = "right" if side == "left" else "left"
        a = [w for w in self.store.side_order(side) if w != wid]; b = self.store.side_order(other) + [wid]
        self.store.apply_layout(**{side: a, other: b})

    def refresh_all(self):
        for w in list(self.inst.values()):
            if w.running:
                w.refresh_now()

    def repaint_all(self):
        for w in self.inst.values():
            w.update()

    def shutdown_all(self):
        for w in list(self.inst.values()):
            w.shutdown()


# ======================================================================================
#  WIDGETY (każdy niezależny; tworzony dopiero po włączeniu, usuwany po wyłączeniu)
# ======================================================================================
def elide_lines(fm, full, width):
    return "\n".join(fm.elidedText(x, Qt.TextElideMode.ElideRight, max(20, width)) for x in full.split("\n"))


class ElideLabel(QLabel):
    """Etykieta skracająca długi tekst („…”) – nie rozpycha panelu (minimalna szerokość 0)."""
    def paintEvent(self, ev):
        if (self.wordWrap() or self.textFormat() == Qt.TextFormat.RichText
                or self.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction):
            return super().paintEvent(ev)
        p = QPainter(self); r = self.contentsRect()
        p.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        p.drawText(r, self.alignment(), self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, r.width()))

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())


class ElideButton(QPushButton):
    """Przycisk z długim tekstem (nagłówki RSS, maile, schowek): tekst jest skracany do szerokości panelu."""
    def __init__(self, text=""):
        super().__init__(); self._full = ""; self.setText(text)

    def setText(self, t):
        self._full = t; self._elide()

    def _elide(self):
        t = elide_lines(self.fontMetrics(), self._full, self.width() - 26)
        if t != QPushButton.text(self):
            QPushButton.setText(self, t)

    def resizeEvent(self, ev):
        super().resizeEvent(ev); self._elide()

    def minimumSizeHint(self):
        return QSize(40, super().minimumSizeHint().height())

    def sizeHint(self):
        return QSize(min(super().sizeHint().width(), 240), super().sizeHint().height())


class ElideCheck(QCheckBox):
    """Pole wyboru ze skracanym tekstem (listy zadań)."""
    def __init__(self, text=""):
        super().__init__(); self._full = ""; self.setText(text)

    def setText(self, t):
        self._full = t; self._elide()

    def _elide(self):
        t = elide_lines(self.fontMetrics(), self._full, self.width() - 36)
        if t != QCheckBox.text(self):
            QCheckBox.setText(self, t)

    def resizeEvent(self, ev):
        super().resizeEvent(ev); self._elide()

    def minimumSizeHint(self):
        return QSize(40, super().minimumSizeHint().height())

    def sizeHint(self):
        return QSize(min(super().sizeHint().width(), 240), super().sizeHint().height())


def shrinkable(combo):
    """Lista rozwijana bez wymuszania szerokości najdłuższą pozycją."""
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(5)
    combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    return combo


def lbl(text="", obj=None, wrap=False, align=None):
    w = QLabel(text) if wrap else ElideLabel(text)
    if obj:
        w.setObjectName(obj)
    if wrap:
        w.setWordWrap(True)
    if align:
        w.setAlignment(align)
    return w


def money(v, cur="$"):
    if v is None:
        return "–"
    s = f"{v:,.0f}" if v >= 1000 else f"{v:,.2f}" if v >= 1 else f"{v:.4f}"
    return f"{cur}{s}".replace(",", " ")


class StreakWidget(WidgetFrame):
    def build(self):
        l = self.lay
        row = QHBoxLayout(); row.setSpacing(8)
        self.num = lbl("0", "bignum"); self.unit = lbl("dni z rzędu", "muted2")
        row.addWidget(self.num); row.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignBottom); row.addStretch()
        l.addLayout(row)
        self.best = lbl("", "muted"); l.addWidget(self.best); l.addSpacing(4)
        self.strip = WeekStrip(self.store); l.addWidget(self.strip); l.addSpacing(4)
        l.addWidget(section("Aktywność"))
        self.map = Heatmap(self.store); l.addWidget(self.map, 0, Qt.AlignmentFlag.AlignHCenter)
        l.addSpacing(4)
        sep = QFrame(); sep.setObjectName("sep"); l.addWidget(sep)
        self.vals = {k: stat_row(l, t) for k, t in (("week", "Ten tydzień"), ("month", "Ten miesiąc"),
                                                    ("total", "Dni aktywne łącznie"), ("acts", "Wszystkie aktywności"))}
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self.refresh)

    def start(self):
        self.store.changed.connect(self._soon); self.refresh()

    def stop(self):
        safe_disconnect(self.store.changed, self._soon)

    def _soon(self):
        self._t.start(250)  # debounce: zdarzeń „changed” bywa dużo

    def refresh(self):
        cur, best = self.store.streak(); st = self.store.stats()
        self.num.setText(str(cur)); self.unit.setText(f"{dni(cur)} z rzędu")
        self.best.setText(f"Najdłuższa seria: {best} {dni(best)}")
        self.vals["week"].setText(f"{st['week']} z 7 dni"); self.vals["month"].setText(f"{st['month']} {dni(st['month'])}")
        self.vals["total"].setText(str(st["total"])); self.vals["acts"].setText(str(st["acts"]))
        self.strip.update(); self.map.update()

    refresh_now = refresh


class ClockWidget(WidgetFrame):
    def build(self):
        self.loc = QLocale(QLocale.Language.Polish)
        self.time = lbl("", "clock"); self.time.setTextFormat(Qt.TextFormat.RichText)
        self.date = lbl("", "muted2", wrap=True)
        self.lay.addWidget(self.time); self.lay.addWidget(self.date)
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick)

    def start(self):
        self.tick(); self.timer.start(1000)

    def stop(self):
        self.timer.stop()

    def tick(self):
        now = QDateTime.currentDateTime()
        self.time.setText(f"{now.toString('HH:mm')}<span style='color:#6b6b6b'>:{now.toString('ss')}</span>")
        txt = self.loc.toString(now.date(), "dddd, d MMMM yyyy")
        self.date.setText(txt[:1].upper() + txt[1:])


class WeatherWidget(WidgetFrame):
    DAYS = ["pon.", "wt.", "śr.", "czw.", "pt.", "sob.", "niedz."]

    def build(self):
        l = self.lay
        self.menu.addAction("Zmień miasto…", self.change_city)
        self.menu.addAction("Wykryj lokalizację automatycznie", self.auto_city)
        self.menu.addAction("Odśwież pogodę", self.refresh_now)
        self.city = lbl("Pogoda", "h3"); l.addWidget(self.city)
        row = QHBoxLayout(); row.setSpacing(10)
        self.icon = QLabel(); self.icon.setFixedSize(60, 60)
        col = QVBoxLayout(); col.setSpacing(0)
        self.temp = lbl("…", "temp"); self.desc = lbl("", "muted2", wrap=True)
        col.addWidget(self.temp); col.addWidget(self.desc)
        row.addWidget(self.icon); row.addLayout(col, 1); l.addLayout(row)
        self.det = {k: stat_row(l, t) for k, t in (("feels", "Odczuwalna"), ("wind", "Wiatr"),
                                                    ("hum", "Wilgotność"), ("mm", "Min / max"))}
        l.addSpacing(4); l.addWidget(section("Kolejne dni"))
        self.fc = []
        for _ in range(5):
            h = QHBoxLayout(); h.setSpacing(8)
            d = lbl("", "muted2"); d.setFixedWidth(48); ic = QLabel(); ic.setFixedSize(24, 24); r = lbl("", "h3")
            h.addWidget(d); h.addWidget(ic); h.addStretch(); h.addWidget(r); l.addLayout(h); self.fc.append((d, ic, r))
        self.timer = QTimer(self); self.timer.timeout.connect(self.store.fetch_weather)
        self.render()

    def start(self):
        self.store.weather_changed.connect(self.render)
        if not self.store.weather or time.time() - self.store.weather_ts > 600:
            self.store.fetch_weather()
        self.render(); self.timer.start(15 * 60 * 1000)

    def stop(self):
        self.timer.stop(); safe_disconnect(self.store.weather_changed, self.render)

    def refresh_now(self):
        self.desc.setText("Odświeżam…"); self.store.fetch_weather()

    def change_city(self):
        name, ok = QInputDialog.getText(self, "Pogoda", "Miasto:")
        if ok and name.strip():
            self.desc.setText("Szukam…"); self.store.set_city(name.strip())

    def auto_city(self):
        self.store.settings.pop("weather_city", None); self.store.save_settings(); self.store.fetch_weather()

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
        self.icon.setPixmap(weather_pixmap(kind).scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio,
                                                         Qt.TransformationMode.SmoothTransformation))
        self.city.setText(w["city"]); self.temp.setText(f"{round(w['temp'])}°C"); self.desc.setText(text)
        self.det["feels"].setText(f"{round(w['feels'])}°C"); self.det["wind"].setText(f"{round(w['wind'])} km/h")
        self.det["hum"].setText(f"{round(w['hum'])}%"); self.det["mm"].setText(f"{round(w['min'])}° / {round(w['max'])}°")
        for (d, ic, r), (day, code, lo, hi) in zip(self.fc, w.get("daily", [])):
            d.setText(self.DAYS[date.fromisoformat(day).weekday()])
            ic.setPixmap(weather_pixmap(WMO.get(code, ("", "cloud"))[1]).scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            r.setText(f"{round(lo)}° / {round(hi)}°")


# ---------------------------------------------------------------- Finanse
DEFAULT_WATCH = [{"k": "crypto", "id": "bitcoin", "label": "BTC", "name": "Bitcoin"},
                 {"k": "crypto", "id": "ethereum", "label": "ETH", "name": "Ethereum"},
                 {"k": "stock", "id": "AAPL", "label": "AAPL", "name": "Apple"},
                 {"k": "stock", "id": "NVDA", "label": "NVDA", "name": "NVIDIA"},
                 {"k": "stock", "id": "TSLA", "label": "TSLA", "name": "Tesla"}]
CUR_SYMBOLS = {"USD": "$", "PLN": "zł ", "EUR": "€", "GBP": "£"}


class MarketRow(QWidget):
    def __init__(self, item):
        super().__init__(); self.setObjectName("clear")
        h = QHBoxLayout(self); h.setContentsMargins(0, 3, 0, 3); h.setSpacing(8)
        left = QVBoxLayout(); left.setSpacing(0)
        left.addWidget(lbl(item["label"], "h3")); left.addWidget(lbl(item.get("name", ""), "muted"))
        self.spark = Sparkline(60, 26)
        right = QVBoxLayout(); right.setSpacing(0)
        self.price = lbl("…", "h3", align=Qt.AlignmentFlag.AlignRight); self.chg = lbl("", "muted", align=Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.price); right.addWidget(self.chg)
        h.addLayout(left, 1); h.addWidget(self.spark); h.addLayout(right)

    def set_data(self, price, chg, spark, cur="$"):
        self.price.setText(money(price, cur))
        if chg is None:
            self.chg.setText(""); return
        up = chg >= 0
        self.chg.setText(f"{'+' if up else '−'}{abs(chg):.2f}%")
        self.chg.setStyleSheet(f"color:{'#3ddc84' if up else '#ff5c5c'}; font-size:12px; background:transparent;")
        self.spark.set_data(spark or [], up)


class MarketsWidget(WidgetFrame):
    def build(self):
        self.menu.addAction("Dodaj akcję…", lambda: self.add("stock"))
        self.menu.addAction("Dodaj kryptowalutę…", lambda: self.add("crypto"))
        self.rm = self.menu.addMenu("Usuń z listy")
        self.rows_lay = QVBoxLayout(); self.rows_lay.setSpacing(0); self.lay.addLayout(self.rows_lay)
        self.skel = Skeleton(3); self.lay.addWidget(self.skel)
        self.note = lbl("Notowania: CoinGecko, Yahoo Finance.", "muted", wrap=True); self.lay.addWidget(self.note)
        self.rows, self.t_last = {}, 0
        self.timer = QTimer(self); self.timer.timeout.connect(self.fetch)
        self.rebuild()

    def items(self):
        return self.store.settings.get("watch") or DEFAULT_WATCH

    def rebuild(self):
        while self.rows_lay.count():
            w = self.rows_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.rows = {}
        for it in self.items():
            r = MarketRow(it); self.rows[(it["k"], it["id"])] = r; self.rows_lay.addWidget(r)
        self.rm.clear()
        for it in self.items():
            self.rm.addAction(it["label"], lambda _=False, it=it: self.remove(it))

    def add(self, kind):
        txt, ok = QInputDialog.getText(self, "Dodaj do listy",
                                       "Symbol giełdowy (np. AAPL, PKO.WA):" if kind == "stock"
                                       else "Id z CoinGecko (np. bitcoin, solana):")
        txt = txt.strip()
        if ok and txt:
            lst = list(self.items()); sym = txt.upper() if kind == "stock" else txt.lower()
            lst.append({"k": kind, "id": sym, "label": sym.upper()[:8], "name": "Akcja" if kind == "stock" else "Krypto"})
            self.store.settings["watch"] = lst; self.store.save_soon(); self.rebuild(); self.fetch()

    def remove(self, it):
        self.store.settings["watch"] = [x for x in self.items() if x is not it and x != it]
        self.store.save_soon(); self.rebuild()

    def start(self):
        if time.time() - self.t_last > 45:
            self.fetch()
        self.timer.start(60000)

    def stop(self):
        self.timer.stop()

    refresh_now = lambda self: self.fetch()

    def fetch(self):
        if not self.store.feature("markets"):
            return
        self.t_last = time.time(); self.skel.setVisible(True)
        ids = [i["id"] for i in self.items() if i["k"] == "crypto"]
        if ids:
            self.store.http("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&sparkline=true"
                            "&price_change_percentage=24h&ids=" + ",".join(ids), self.guard(self._crypto))
        for i in self.items():
            if i["k"] == "stock":
                self.store.http(f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(i['id'])}?range=1d&interval=5m",
                                self.guard(lambda j, e, s, sym=i["id"]: self._stock(sym, j)))

    def _crypto(self, j, err, status):
        self.skel.hide()
        if not isinstance(j, list):
            self.note.setText("Nie udało się pobrać kursów krypto."); return
        for c in j:
            r = self.rows.get(("crypto", c.get("id")))
            if r:
                sp = (c.get("sparkline_in_7d") or {}).get("price") or []
                r.set_data(c.get("current_price"), c.get("price_change_percentage_24h"), sp[-48:])

    def _stock(self, sym, j):
        self.skel.hide()
        r = self.rows.get(("stock", sym))
        try:
            res = j["chart"]["result"][0]; meta = res["meta"]
            price = meta["regularMarketPrice"]; prev = meta.get("chartPreviousClose") or meta.get("previousClose")
            closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
            if r:
                r.set_data(price, (price - prev) / prev * 100 if prev else None, closes,
                           CUR_SYMBOLS.get(meta.get("currency", "USD"), ""))
        except Exception:
            if r:
                r.price.setText("–"); r.chg.setText("brak danych")


class CurrencyWidget(WidgetFrame):
    CODES = ["PLN", "USD", "EUR", "GBP", "BTC"]

    def build(self):
        l = self.lay
        self.amount = QLineEdit("100"); self.amount.setObjectName("glassin"); self.amount.textChanged.connect(self.calc)
        row = QHBoxLayout(); row.setSpacing(6)
        self.a, self.b = shrinkable(QComboBox()), shrinkable(QComboBox())
        for c in self.CODES:
            self.a.addItem(c); self.b.addItem(c)
        self.a.setCurrentText("PLN"); self.b.setCurrentText("USD")
        self.a.currentTextChanged.connect(self.calc); self.b.currentTextChanged.connect(self.calc)
        sw = gicon(QToolButton(), "swap", 16); sw.setFixedSize(28, 28); sw.setToolTip("Zamień waluty")
        sw.clicked.connect(self.swap)
        row.addWidget(self.a, 1); row.addWidget(sw); row.addWidget(self.b, 1)
        self.res = lbl("–", "temp"); self.res.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.info = lbl("", "muted", wrap=True)
        l.addWidget(self.amount); l.addLayout(row); l.addWidget(self.res); l.addWidget(self.info)
        self.rates, self.t_last = {}, 0

    def swap(self):
        x, y = self.a.currentText(), self.b.currentText(); self.a.setCurrentText(y); self.b.setCurrentText(x)

    def start(self):
        if time.time() - self.t_last > 1800 or not self.rates:
            self.fetch()
        self.calc()

    def refresh_now(self):
        self.fetch()

    def fetch(self):
        self.t_last = time.time(); self.info.setText("Pobieram kursy…")
        self.store.http("https://open.er-api.com/v6/latest/EUR", self.guard(self._fiat))
        self.store.http("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=eur", self.guard(self._btc))

    def _fiat(self, j, err, status):
        try:
            r = j["rates"]; self.rates.update({c: float(r[c]) for c in ("PLN", "USD", "GBP")}); self.rates["EUR"] = 1.0
            self.info.setText("Kursy: open.er-api.com, CoinGecko")
        except Exception:
            self.info.setText("Nie udało się pobrać kursów walut.")
        self.calc()

    def _btc(self, j, err, status):
        try:
            self.rates["BTC"] = 1.0 / float(j["bitcoin"]["eur"])
        except Exception:
            pass
        self.calc()

    def calc(self, *_):
        a, b = self.a.currentText(), self.b.currentText()
        try:
            amt = float(self.amount.text().replace(" ", "").replace(",", "."))
            out = amt / self.rates[a] * self.rates[b]
        except (ValueError, KeyError, ZeroDivisionError):
            self.res.setText("–"); return
        self.res.setText((f"{out:.8f}".rstrip("0").rstrip(".") if b == "BTC" else f"{out:,.2f}".replace(",", " ")) + f" {b}")


# ---------------------------------------------------------------- Produktywność
class NotesWidget(WidgetFrame):
    def build(self):
        self.edit = QPlainTextEdit(); self.edit.setObjectName("note"); self.edit.setMinimumHeight(150)
        self.edit.setPlaceholderText("Szybkie notatki… (zapisują się automatycznie)")
        self.edit.setPlainText(self.store.settings.get("notes", ""))
        self.lay.addWidget(self.edit)
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self.save)
        self.edit.textChanged.connect(lambda: self._t.start(700))  # debounce autozapisu

    def save(self):
        self.store.settings["notes"] = self.edit.toPlainText(); self.store.save_soon()

    def teardown(self):
        if self._t.isActive():
            self._t.stop(); self.save()


class TodoWidget(WidgetFrame):
    def build(self):
        self.menu.addAction("Usuń ukończone", self.clear_done)
        self.inp = QLineEdit(); self.inp.setObjectName("glassin"); self.inp.setPlaceholderText("Dodaj zadanie i naciśnij Enter")
        self.inp.returnPressed.connect(self.add)
        self.rows = QVBoxLayout(); self.rows.setSpacing(2)
        self.lay.addWidget(self.inp); self.lay.addLayout(self.rows)
        self.items = [dict(x) for x in self.store.settings.get("todo", [])]
        self.render()

    def save(self):
        self.store.settings["todo"] = self.items; self.store.save_soon()

    def add(self):
        t = self.inp.text().strip()
        if t:
            self.items.insert(0, {"t": t, "d": False}); self.inp.clear(); self.save(); self.render()

    def clear_done(self):
        self.items = [x for x in self.items if not x["d"]]; self.save(); self.render()

    def render(self):
        while self.rows.count():
            w = self.rows.takeAt(0).widget()
            if w:
                w.deleteLater()
        for it in self.items[:12]:
            cb = ElideCheck(it["t"]); cb.setObjectName("todo"); cb.setChecked(it["d"]); cb.setToolTip(it["t"])
            cb.setStyleSheet("color:#7a7a7a; text-decoration:line-through;" if it["d"] else "")
            cb.toggled.connect(lambda v, it=it: self.toggled(it, v))
            self.rows.addWidget(cb)
        if not self.items:
            self.rows.addWidget(lbl("Brak zadań. Świetnie!", "muted"))

    def toggled(self, it, v):
        it["d"] = v; self.save(); QTimer.singleShot(0, self.render)


class PomodoroWidget(WidgetFrame):
    MODES = {"Praca": 25 * 60, "Przerwa": 5 * 60}

    def build(self):
        l = self.lay
        self.mode = "Praca"; self.left = self.MODES[self.mode]; self.end = None
        self.time = lbl("25:00", "clock", align=Qt.AlignmentFlag.AlignCenter)
        self.state = lbl("Praca · 25 min", "muted2", align=Qt.AlignmentFlag.AlignCenter)
        row = QHBoxLayout(); row.setSpacing(6)
        self.go = QPushButton("Start"); self.go.clicked.connect(self.toggle_run)
        rs = QPushButton("Reset"); rs.clicked.connect(self.reset)
        sw = QPushButton("Przerwa / praca"); sw.clicked.connect(self.switch)
        row.addWidget(self.go); row.addWidget(rs); l.addWidget(self.time); l.addWidget(self.state); l.addLayout(row); l.addWidget(sw)
        self.ui = QTimer(self); self.ui.timeout.connect(self.tick)           # odświeżanie widoku (tylko gdy widoczny)
        self.alarm = QTimer(self); self.alarm.setSingleShot(True); self.alarm.timeout.connect(self.finish)  # działa też w tle

    def start(self):
        self.tick()
        if self.end:
            self.ui.start(1000)

    def stop(self):
        self.ui.stop()

    def remaining(self):
        return max(0, int(round(self.end - time.monotonic()))) if self.end else self.left

    def tick(self):
        r = self.remaining(); self.time.setText(f"{r // 60:02d}:{r % 60:02d}")
        self.go.setText("Pauza" if self.end else "Start")
        self.state.setText(f"{self.mode} · {self.MODES[self.mode] // 60} min")

    def toggle_run(self):
        if self.end:
            self.left = self.remaining(); self.end = None; self.alarm.stop(); self.ui.stop()
        else:
            self.end = time.monotonic() + self.left; self.alarm.start(self.left * 1000)
            if self.running:
                self.ui.start(1000)
        self.tick()

    def reset(self):
        self.end = None; self.alarm.stop(); self.ui.stop(); self.left = self.MODES[self.mode]; self.tick()

    def switch(self):
        self.mode = "Przerwa" if self.mode == "Praca" else "Praca"; self.reset()

    def finish(self):
        QApplication.beep(); self.end = None; self.ui.stop()
        self.mode = "Przerwa" if self.mode == "Praca" else "Praca"; self.left = self.MODES[self.mode]
        self.tick(); self.state.setText(f"Koniec! Teraz: {self.mode.lower()}")

    def teardown(self):
        self.alarm.stop(); self.ui.stop()


class ClipboardWidget(WidgetFrame):
    def build(self):
        self.menu.addAction("Wyczyść historię", self.clear)
        self.rows = QVBoxLayout(); self.rows.setSpacing(3); self.lay.addLayout(self.rows)
        self.lay.addWidget(lbl("Historia tylko w pamięci – nie zapisuje się na dysku.", "muted", wrap=True))
        self.hist, self._self = [], False
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self.capture)
        self.cb = QApplication.clipboard(); self.cb.dataChanged.connect(self._soon)  # nasłuch zdejmowany w teardown()
        self.render()

    def _soon(self):
        self._t.start(150)

    def capture(self):
        if self._self:
            self._self = False; return
        t = self.cb.text().strip()
        if t and t == SECRET_CLIP[0]:   # hasło skopiowane przez menedżer haseł
            return
        if t and (not self.hist or self.hist[0] != t):
            self.hist = [t] + [h for h in self.hist if h != t][:7]; self.render()

    def clear(self):
        self.hist = []; self.render()

    def copy(self, t):
        self._self = True; self.cb.setText(t)

    def render(self):
        while self.rows.count():
            w = self.rows.takeAt(0).widget()
            if w:
                w.deleteLater()
        for t in self.hist:
            b = ElideButton(t.replace("\n", " ")[:42] + ("…" if len(t) > 42 else "")); b.setObjectName("clipitem")
            b.setToolTip("Kliknij, aby skopiować ponownie"); b.clicked.connect(lambda _=False, t=t: self.copy(t))
            self.rows.addWidget(b)
        if not self.hist:
            self.rows.addWidget(lbl("Skopiuj coś, a pojawi się tutaj.", "muted"))

    def teardown(self):
        safe_disconnect(self.cb.dataChanged, self._soon); self._t.stop()


def safe_eval(expr):
    """Bezpieczny kalkulator: tylko liczby, + - * / // % ** ( ) i wybrane funkcje (bez eval)."""
    expr = expr.replace(",", ".").replace("^", "**").replace("×", "*").replace("÷", "/")
    consts = {"pi": math.pi, "e": math.e}
    funcs = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log10,
             "ln": math.log, "abs": abs, "round": round}
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
           ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in ops:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 1000:
                raise ValueError("wykładnik za duży")
            return ops[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            return ev(n.operand) if isinstance(n.op, ast.UAdd) else -ev(n.operand)
        if isinstance(n, ast.Name) and n.id in consts:
            return consts[n.id]
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in funcs and not n.keywords:
            return funcs[n.func.id](*[ev(a) for a in n.args])
        raise ValueError("niedozwolone wyrażenie")
    return ev(ast.parse(expr.strip(), mode="eval"))


class CalcWidget(WidgetFrame):
    def build(self):
        self.inp = QLineEdit(); self.inp.setObjectName("glassin"); self.inp.setPlaceholderText("np. 2*(3+4) , sqrt(81) , 12%5")
        self.inp.returnPressed.connect(self.run); self.inp.textChanged.connect(self.live)
        self.res = lbl("", "temp"); self.res.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.hist = QVBoxLayout(); self.hist.setSpacing(2)
        self.lay.addWidget(self.inp); self.lay.addWidget(self.res); self.lay.addLayout(self.hist)
        self.log = []

    @staticmethod
    def fmt(v):
        return str(int(v)) if isinstance(v, float) and v.is_integer() and abs(v) < 1e15 else (f"{v:.10g}" if isinstance(v, float) else str(v))

    def live(self, t):
        try:
            self.res.setText("= " + self.fmt(safe_eval(t))) if t.strip() else self.res.setText("")
        except Exception:
            self.res.setText("")

    def run(self):
        t = self.inp.text()
        try:
            r = self.fmt(safe_eval(t))
        except Exception:
            self.res.setText("błąd"); return
        self.log = [(t, r)] + self.log[:3]; self.inp.setText(r)
        while self.hist.count():
            w = self.hist.takeAt(0).widget()
            if w:
                w.deleteLater()
        for a, b in self.log:
            x = lbl(f"{a} = {b}", "muted"); self.hist.addWidget(x)


class TranslateWidget(WidgetFrame):
    LANGS = [("pl", "Polski"), ("en", "Angielski"), ("de", "Niemiecki"), ("es", "Hiszpański"), ("fr", "Francuski"),
             ("it", "Włoski"), ("uk", "Ukraiński"), ("cs", "Czeski")]

    def build(self):
        self.src = QPlainTextEdit(); self.src.setObjectName("note"); self.src.setFixedHeight(70)
        self.src.setPlaceholderText("Wpisz tekst do przetłumaczenia…")
        row = QHBoxLayout(); row.setSpacing(6)
        self.a, self.b = shrinkable(QComboBox()), shrinkable(QComboBox())
        for c, n in self.LANGS:
            self.a.addItem(n, c); self.b.addItem(n, c)
        self.a.setCurrentIndex(0); self.b.setCurrentIndex(1)
        sw = gicon(QToolButton(), "swap", 16); sw.setFixedSize(28, 28); sw.clicked.connect(self.swap)
        row.addWidget(self.a, 1); row.addWidget(sw); row.addWidget(self.b, 1)
        self.out = lbl("", "muted2", wrap=True); self.out.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cp = QPushButton("Kopiuj wynik"); cp.clicked.connect(lambda: QApplication.clipboard().setText(self.out.text()))
        self.lay.addWidget(self.src); self.lay.addLayout(row); self.lay.addWidget(self.out); self.lay.addWidget(cp)
        self.seq = 0
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self.go)
        self.src.textChanged.connect(lambda: self._t.start(700))   # debounce: tłumaczy po przerwie w pisaniu
        self.a.currentIndexChanged.connect(lambda _: self._t.start(200)); self.b.currentIndexChanged.connect(lambda _: self._t.start(200))

    def swap(self):
        i, j = self.a.currentIndex(), self.b.currentIndex(); self.a.setCurrentIndex(j); self.b.setCurrentIndex(i)

    def go(self):
        t = self.src.toPlainText().strip()[:480]
        if not t:
            self.out.setText(""); return
        self.seq += 1; n = self.seq; self.out.setText("Tłumaczę…")
        pair = f"{self.a.currentData()}|{self.b.currentData()}"
        self.store.http("https://api.mymemory.translated.net/get?q=" + quote(t) + "&langpair=" + quote(pair),
                        self.guard(lambda j, e, s: self.done(n, j)))

    def done(self, n, j):
        if n != self.seq:
            return  # nieaktualna odpowiedź
        try:
            self.out.setText(html.unescape(j["responseData"]["translatedText"]))
        except Exception:
            self.out.setText("Nie udało się przetłumaczyć (limit lub brak sieci).")


# ---------------------------------------------------------------- System / media / wiadomości
def read_system(prev=[None]):
    """(cpu%, ram%, bateria%|None, ładowanie). psutil jeśli jest; inaczej /proc (Linux) lub ctypes (Windows)."""
    cpu = ram = bat = None; plug = False
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None); ram = psutil.virtual_memory().percent
        b = psutil.sensors_battery()
        if b:
            bat, plug = b.percent, b.power_plugged
        return cpu, ram, bat, plug
    except Exception:
        pass
    try:
        if sys.platform.startswith("linux"):
            vals = [int(x) for x in open("/proc/stat").readline().split()[1:8]]
            idle, tot = vals[3] + vals[4], sum(vals)
            if prev[0]:
                d_t, d_i = tot - prev[0][0], idle - prev[0][1]
                cpu = 100.0 * (1 - d_i / d_t) if d_t else 0.0
            prev[0] = (tot, idle)
            mem = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo") if ":" in l}
            ram = 100.0 * (1 - mem["MemAvailable"] / mem["MemTotal"])
            for b in Path("/sys/class/power_supply").glob("BAT*"):
                bat = float((b / "capacity").read_text()); plug = (b / "status").read_text().strip() != "Discharging"; break
        elif sys.platform == "win32":
            import ctypes
            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in ("a", "b", "c", "d", "e", "f", "g")]
            m = MS(); m.l = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)); ram = float(m.load)
            # procesor: GetSystemTimes (bezczynność / jądro / użytkownik) – różnica między kolejnymi odczytami
            ft = [ctypes.c_ulonglong() for _ in range(3)]
            if ctypes.windll.kernel32.GetSystemTimes(*[ctypes.byref(x) for x in ft]):
                idle, tot = ft[0].value, ft[1].value + ft[2].value    # czas jądra zawiera już czas bezczynności
                if prev[0]:
                    d_t, d_i = tot - prev[0][0], idle - prev[0][1]
                    cpu = max(0.0, min(100.0, 100.0 * (1 - d_i / d_t))) if d_t else 0.0
                prev[0] = (tot, idle)
            class PS(ctypes.Structure):   # bateria: GetSystemPowerStatus
                _fields_ = [("ac", ctypes.c_ubyte), ("flag", ctypes.c_ubyte), ("pct", ctypes.c_ubyte), ("saver", ctypes.c_ubyte),
                            ("life", ctypes.c_ulong), ("full", ctypes.c_ulong)]
            ps = PS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(ps)) and ps.pct != 255 and not ps.flag & 128:
                bat, plug = float(ps.pct), ps.ac == 1
    except Exception:
        pass
    return cpu, ram, bat, plug


_HAS_BATTERY = []


def power_status():
    """(jest bateria, zasilanie z sieci) – jednorazowy odczyt systemowy, bez odpytywania w tle."""
    try:
        if sys.platform == "win32":
            import ctypes
            class PS(ctypes.Structure):
                _fields_ = [("ac", ctypes.c_ubyte), ("flag", ctypes.c_ubyte), ("pct", ctypes.c_ubyte), ("saver", ctypes.c_ubyte),
                            ("life", ctypes.c_ulong), ("full", ctypes.c_ulong)]
            ps = PS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(ps)):
                return ps.pct != 255 and not ps.flag & 128, ps.ac != 0
        else:
            for b in Path("/sys/class/power_supply").glob("BAT*"):
                return True, (b / "status").read_text().strip() != "Discharging"
    except Exception:
        pass
    return False, True


def has_battery():
    if not _HAS_BATTERY:
        _HAS_BATTERY.append(power_status()[0])
    return _HAS_BATTERY[0]


def proc_memory(pid):
    """Pamięć prywatna procesu w bajtach (Windows: PrivateUsage, Linux: VmRSS) albo None."""
    if not pid:
        return None
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes as wt
            class PMC(ctypes.Structure):
                _fields_ = [("cb", wt.DWORD), ("faults", wt.DWORD)] + [(n, ctypes.c_size_t) for n in (
                    "peak_ws", "ws", "qpp", "qp", "qnpp", "qnp", "pagefile", "peak_pagefile", "private")]
            k = ctypes.windll.kernel32; k.OpenProcess.restype = wt.HANDLE
            h = k.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return None
            try:
                c = PMC(); c.cb = ctypes.sizeof(PMC)
                return c.private if k.K32GetProcessMemoryInfo(wt.HANDLE(h), ctypes.byref(c), c.cb) else None
            finally:
                k.CloseHandle(wt.HANDLE(h))
        for line in open(f"/proc/{int(pid)}/status"):
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except Exception:
        pass
    return None


def child_pids(pid):
    """Procesy potomne (silnik stron: GPU, sieć, strony) – migawka listy procesów Windows."""
    out = []
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes as wt
            class PE(ctypes.Structure):
                _fields_ = [("size", wt.DWORD), ("usage", wt.DWORD), ("pid", wt.DWORD), ("heap", ctypes.c_size_t),
                            ("mod", wt.DWORD), ("threads", wt.DWORD), ("ppid", wt.DWORD), ("prio", ctypes.c_long),
                            ("flags", wt.DWORD), ("exe", ctypes.c_wchar * 260)]
            k = ctypes.windll.kernel32; k.CreateToolhelp32Snapshot.restype = wt.HANDLE
            snap = k.CreateToolhelp32Snapshot(2, 0)
            e = PE(); e.size = ctypes.sizeof(PE)
            ok = k.Process32FirstW(wt.HANDLE(snap), ctypes.byref(e))
            while ok:
                if e.ppid == pid:
                    out.append(e.pid)
                ok = k.Process32NextW(wt.HANDLE(snap), ctypes.byref(e))
            k.CloseHandle(wt.HANDLE(snap))
        else:
            for p in Path("/proc").iterdir():
                if p.name.isdigit():
                    try:
                        if int((p / "stat").read_text().split(")")[1].split()[1]) == pid:
                            out.append(int(p.name))
                    except Exception:
                        pass
    except Exception:
        pass
    return out


class SystemWidget(WidgetFrame):
    def build(self):
        self.bars, self.rows = {}, {}
        for k, t in (("cpu", "Procesor"), ("ram", "Pamięć RAM"), ("bat", "Bateria")):
            box = QWidget(); box.setObjectName("clear"); bl = QVBoxLayout(box); bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(4)
            row = QHBoxLayout(); a = lbl(t, "muted2"); v = lbl("–", "h3")
            row.addWidget(a); row.addStretch(); row.addWidget(v); bl.addLayout(row)
            pb = QProgressBar(); pb.setRange(0, 100); pb.setTextVisible(False); pb.setFixedHeight(6); bl.addWidget(pb)
            self.lay.addWidget(box); self.bars[k] = (v, pb); self.rows[k] = box
        self.rows["bat"].setVisible(read_system()[2] is not None)   # komputer stacjonarny: bez wiersza baterii
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick)

    def start(self):
        read_system(); self.timer.start(2000); QTimer.singleShot(400, self.tick)

    def stop(self):
        self.timer.stop()

    def tick(self):
        cpu, ram, bat, plug = read_system()
        if self.rows["bat"].isVisibleTo(self) != (bat is not None):
            self.rows["bat"].setVisible(bat is not None)
        for k, val in (("cpu", cpu), ("ram", ram), ("bat", bat)):
            v, pb = self.bars[k]
            v.setText("–" if val is None else f"{val:.0f}%" + (" · ładuje" if k == "bat" and plug else ""))
            pb.setValue(int(val or 0))


TAB_JS_INFO = ("(function(){var m=navigator.mediaSession&&navigator.mediaSession.metadata;"
               "var e=[].slice.call(document.querySelectorAll('video,audio'));"
               "return JSON.stringify({t:m?m.title:'',a:m?m.artist:'',playing:e.some(function(x){return !x.paused&&!x.ended;}),n:e.length});})()")
TAB_JS_TOGGLE = ("(function(){var e=[].slice.call(document.querySelectorAll('video,audio'));"
                 "var p=e.filter(function(x){return !x.paused&&!x.ended;});"
                 "if(p.length){p.forEach(function(x){x.pause();});}else if(e.length){e[0].play();}})()")


class TabAudioRow(QWidget):
    def __init__(self, pane, tab):
        super().__init__(); self.setObjectName("clear"); self.pane, self.tab, self.web = pane, tab, None
        h = QHBoxLayout(self); h.setContentsMargins(0, 3, 0, 3); h.setSpacing(4)
        col = QVBoxLayout(); col.setSpacing(0)
        self.title = lbl("", "h3"); self.sub = lbl("", "muted"); col.addWidget(self.title); col.addWidget(self.sub)
        h.addLayout(col, 1)
        self.b_play, self.b_mute, self.b_go = QToolButton(), QToolButton(), QToolButton()
        for b, kind, tip, fn in ((self.b_play, "play", "Odtwarzaj / pauza", self.toggle), (self.b_mute, "volume", "Wycisz kartę", self.mute),
                                 (self.b_go, "external", "Przejdź do karty", self.go)):
            gicon(b, kind, 16); b.setToolTip(tip); b.setFixedSize(30, 30); b.clicked.connect(lambda _=False, f=fn: f()); h.addWidget(b)

    def page(self):
        return (self.web or self.tab.main).page()

    def toggle(self):
        self.page().runJavaScript(TAB_JS_TOGGLE); QTimer.singleShot(400, self.pane.refresh)

    def mute(self):
        self.page().setAudioMuted(not self.page().isAudioMuted()); self.pane.refresh()

    def go(self):
        br = self.pane.o.host.browser; br.bar.setCurrentIndex(br.stack.indexOf(self.tab))

    def update_from(self, web):
        self.web = web; page = web.page(); self.title.setText((web.title() or host_of(web.url().toString()) or "Karta")[:34])
        gicon(self.b_mute, "mute" if page.isAudioMuted() else "volume", 16)
        gicon(self.b_play, "pause" if page.recentlyAudible() else "play", 16)
        self.sub.setText("gra" if page.recentlyAudible() else "wstrzymano")
        page.runJavaScript(TAB_JS_INFO, 0, self.got)

    def got(self, res):
        try:
            d = json.loads(res); t = " – ".join(x for x in (d.get("a"), d.get("t")) if x)
            if t:
                self.title.setText(t[:34])
            self.sub.setText("gra" if d.get("playing") else "wstrzymano")
            gicon(self.b_play, "pause" if d.get("playing") else "play", 16)
        except Exception:
            pass


class TabsPane(QWidget):
    """Nasłuchuje, które karty odtwarzają dźwięk (YouTube, SoundCloud…), i pozwala je wyciszyć / zatrzymać."""

    def __init__(self, owner):
        super().__init__(); self.setObjectName("clear")
        self.o, self.rows, self.known = owner, {}, set()
        l = QVBoxLayout(self); l.setContentsMargins(0, 0, 0, 0); l.setSpacing(2)
        self.list = QVBoxLayout(); self.list.setSpacing(0)
        self.empty = lbl("Żadna karta nie odtwarza teraz dźwięku.", "muted2", wrap=True)
        l.addLayout(self.list); l.addWidget(self.empty)
        l.addWidget(lbl("Sterowanie działa dla stron z odtwarzaczem HTML5 (YouTube, SoundCloud i inne).", "muted", wrap=True))
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh)

    def start(self):
        self.o.host.browser.audio_changed.connect(self.refresh); self.timer.start(3000); self.refresh()

    def stop(self):
        self.timer.stop(); safe_disconnect(self.o.host.browser.audio_changed, self.refresh)

    def refresh(self):
        br = self.o.host.browser; live = {}
        for i in range(br.stack.count()):
            t = br.stack.widget(i); vs = t.views() if hasattr(t, "views") else []
            if not vs:
                continue
            web = next((w for w in vs if w.page().recentlyAudible()), vs[0])   # przy podziale ekranu: strona, która gra
            if web.page().recentlyAudible():
                self.known.add(t)
            if t in self.known:
                live[t] = web
        self.known &= set(live)
        for t in [t for t in self.rows if t not in live]:
            self.rows.pop(t).deleteLater()
        for t, web in live.items():
            r = self.rows.get(t)
            if r is None:
                r = self.rows[t] = TabAudioRow(self, t); self.list.addWidget(r)
            r.update_from(web)
        self.empty.setVisible(not live)


class LocalPane(QWidget):
    """Prosty odtwarzacz lokalnych plików audio (QtMultimedia ładowane dopiero tutaj)."""

    def __init__(self, owner):
        super().__init__(); self.setObjectName("clear"); self.o, self.ok = owner, False
        l = QVBoxLayout(self); l.setContentsMargins(0, 0, 0, 0); l.setSpacing(6)
        try:
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaMetaData
        except ImportError:
            l.addWidget(lbl("Brak modułu QtMultimedia.", "muted2")); return
        self.MP, self.MD = QMediaPlayer, QMediaMetaData
        self.player = QMediaPlayer(self); self.out = QAudioOutput(self); self.player.setAudioOutput(self.out)
        self.out.setVolume(0.6); self.files, self.idx = [], -1; self.ok = True
        top = QHBoxLayout(); top.setSpacing(10)
        self.cover = QLabel(); self.cover.setFixedSize(58, 58); self.cover.setObjectName("cover")
        info = QVBoxLayout(); info.setSpacing(0)
        self.song = lbl("Brak utworu", "h3", wrap=True); self.artist = lbl("Dodaj pliki audio przyciskiem +", "muted")
        info.addWidget(self.song); info.addWidget(self.artist)
        top.addWidget(self.cover); top.addLayout(info, 1); l.addLayout(top)
        self.pos = QSlider(Qt.Orientation.Horizontal); self.pos.setRange(0, 0)
        self.pos.sliderMoved.connect(self.player.setPosition); l.addWidget(self.pos)
        row = QHBoxLayout(); row.setSpacing(4)
        self.play_b = QToolButton()
        for b, kind, fn in ((QToolButton(), "prev", lambda: self.step(-1)), (self.play_b, "play", self.toggle),
                            (QToolButton(), "next", lambda: self.step(1))):
            gicon(b, kind, 20); b.setFixedSize(34, 34); b.clicked.connect(lambda _=False, f=fn: f()); row.addWidget(b)
        add = gicon(QToolButton(), "plus", 18); add.setFixedSize(34, 34); add.setToolTip("Dodaj pliki audio"); add.clicked.connect(self.add)
        row.addStretch(); row.addWidget(add); l.addLayout(row)
        self.player.positionChanged.connect(lambda p: self.pos.setValue(p) if not self.pos.isSliderDown() else None)
        self.player.durationChanged.connect(lambda d: self.pos.setRange(0, d))
        self.player.metaDataChanged.connect(self.meta)
        self.player.mediaStatusChanged.connect(lambda s: self.step(1) if s == self.MP.MediaStatus.EndOfMedia else None)
        self.player.playbackStateChanged.connect(lambda s: gicon(self.play_b, "pause" if s == self.MP.PlaybackState.PlayingState
                                                                 else "play", 20))

    def start(self): pass
    def stop(self): pass     # muzyka gra dalej po zwinięciu panelu

    def add(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Wybierz muzykę", str(Path.home()), "Audio (*.mp3 *.flac *.wav *.ogg *.m4a *.aac)")
        if fs:
            first = not self.files; self.files += fs
            if first:
                self.idx = 0; self.load(); self.player.play()

    def load(self):
        self.player.setSource(QUrl.fromLocalFile(self.files[self.idx])); self.song.setText(Path(self.files[self.idx]).stem)

    def step(self, d):
        if self.files:
            self.idx = (self.idx + d) % len(self.files); self.load(); self.player.play()

    def toggle(self):
        if not self.files:
            self.add(); return
        self.player.pause() if self.player.playbackState() == self.MP.PlaybackState.PlayingState else self.player.play()

    def meta(self):
        try:
            md = self.player.metaData()
            t = md.stringValue(self.MD.Key.Title); a = md.stringValue(self.MD.Key.ContributingArtist)
            if t:
                self.song.setText(t)
            self.artist.setText(a or "")
            img = md.value(self.MD.Key.ThumbnailImage) or md.value(self.MD.Key.CoverArtImage)
            if hasattr(img, "isNull") and not img.isNull():
                self.cover.setPixmap(QPixmap.fromImage(img).scaled(58, 58, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                                  Qt.TransformationMode.SmoothTransformation))
            else:
                self.cover.clear()
        except Exception:
            pass

    def teardown(self):
        if self.ok:
            self.player.stop()


APP_NAMES = {"msedge": "Edge", "chrome": "Chrome", "firefox": "Firefox", "308046b0af4a39cb": "Firefox", "brave": "Brave",
             "opera": "Opera", "zunemusic": "Odtwarzacz multimediów", "microsoft.zunemusic": "Odtwarzacz multimediów",
             "vlc": "VLC", "spotify": "Spotify", "python": "Luna", "pythonw": "Luna", "luna": "Luna"}


def app_label(aumid):
    """„SpotifyAB.SpotifyMusic_…!Spotify” / „Spotify.exe” / „MSEdge” → czytelna nazwa aplikacji."""
    a = (aumid or "").split("!")[-1]
    a = re.sub(r"\.exe$", "", a.split("\\")[-1], flags=re.I)
    return APP_NAMES.get(a.lower()) or ("Spotify" if "spotify" in (aumid or "").lower() else a[:1].upper() + a[1:])


class MediaSession(QObject):
    """Systemowe sterowanie multimediami Windows (SMTC) – to samo, co pokazuje nakładka głośności Windows.
    Działa z aplikacją Spotify (i innymi odtwarzaczami) bez logowania i bez kluczy. WinRT jest asynchroniczny, więc
    wszystko dzieje się w osobnym wątku z pętlą asyncio; zdarzenia systemu (zmiana utworu/stanu) przychodzą same –
    nic nie jest odpytywane w tle. Wyniki trafiają do wątku GUI sygnałami Qt (połączenie kolejkowane)."""
    updated = pyqtSignal(dict)
    cover_ready = pyqtSignal(bytes)
    available = _SMTC is not None

    def __init__(self):
        super().__init__()
        self.state, self.loop, self.mgr, self._subs = {}, None, None, 0
        self._sess = self._sess_tokens = self._mgr_tokens = None
        self._cover_key, self._pending = None, False
        self.updated.connect(self._keep)

    def _keep(self, st):
        self.state = st

    # --- cykl życia (nasłuch zdarzeń tylko, gdy jakiś widget jest widoczny) ---
    def register(self):
        self._subs += 1
        if self._subs == 1 and self.available:
            if self.loop is None:   # bezczynna pętla nie zużywa CPU; wątek żyje do końca programu
                self.loop = asyncio.new_event_loop()
                threading.Thread(target=self.loop.run_forever, name="luna-smtc", daemon=True).start()
            self._submit(self._attach())

    def unregister(self):
        self._subs = max(0, self._subs - 1)
        if self._subs == 0 and self.loop is not None:
            self._submit(self._detach())

    def _submit(self, coro):
        asyncio.run_coroutine_threadsafe(self._safe(coro), self.loop)

    async def _safe(self, coro):
        try:
            await coro
        except RuntimeError:      # obiekt Qt już usunięty (zamykanie Luny) – zatrzymujemy wątek po cichu
            self._bind(None); self.loop.stop()
        except Exception as e:    # błąd WinRT nie może zabić wątku ani programu
            print(f"SMTC: {e!r}", file=sys.stderr)
            try:
                self.updated.emit({"error": "Nie udało się odczytać odtwarzacza systemowego."})
            except RuntimeError:
                self.loop.stop()

    def _kick(self, *_):          # wywoływane z wątków WinRT – zbieramy serię zdarzeń w jeden odczyt
        if self.loop is not None and not self._pending:
            self._pending = True
            self.loop.call_soon_threadsafe(lambda: self.loop.call_later(0.15, lambda: self._submit(self._read())))

    async def _attach(self):
        if self.mgr is None:
            self.mgr = await _SMTC.request_async()
        if self._mgr_tokens is None:
            self._mgr_tokens = (self.mgr.add_sessions_changed(self._kick), self.mgr.add_current_session_changed(self._kick))
        await self._read()

    async def _detach(self):
        if self.mgr is not None and self._mgr_tokens:
            self.mgr.remove_sessions_changed(self._mgr_tokens[0]); self.mgr.remove_current_session_changed(self._mgr_tokens[1])
        self._mgr_tokens = None; self._bind(None)

    def _bind(self, s):
        """Nasłuch zdarzeń tylko na wybranej sesji (utwór, stan odtwarzania, pozycja)."""
        if s is not None and self._sess is not None and s.source_app_user_model_id == self._sess.source_app_user_model_id:
            return
        if self._sess is not None and self._sess_tokens:
            o, (a, b, c) = self._sess, self._sess_tokens
            o.remove_media_properties_changed(a); o.remove_playback_info_changed(b); o.remove_timeline_properties_changed(c)
        self._sess, self._sess_tokens = s, None
        if s is not None:
            self._sess_tokens = (s.add_media_properties_changed(self._kick), s.add_playback_info_changed(self._kick),
                                 s.add_timeline_properties_changed(self._kick))

    def _pick(self):
        """Najpierw Spotify, potem sesja, którą Windows uznaje za bieżącą, potem cokolwiek, co gra."""
        sessions = list(self.mgr.get_sessions()) if self.mgr else []
        for s in sessions:
            if "spotify" in (s.source_app_user_model_id or "").lower():
                return s
        cur = self.mgr.get_current_session() if self.mgr else None
        if cur is not None:
            return cur
        playing = [s for s in sessions if s.get_playback_info().playback_status == _SMTC_STATUS.PLAYING]
        return (playing or sessions or [None])[0]

    async def _read(self):
        self._pending = False
        if self._subs == 0 or self.mgr is None:
            return
        s = self._pick(); self._bind(s)
        if s is None:
            self.updated.emit({}); return
        p = await s.try_get_media_properties_async()
        pb = s.get_playback_info(); tl = s.get_timeline_properties(); ctl = pb.controls
        dur = (tl.end_time - tl.start_time).total_seconds()
        st = {"app": app_label(s.source_app_user_model_id), "title": p.title or "", "artist": p.artist or p.album_artist or "",
              "playing": pb.playback_status == _SMTC_STATUS.PLAYING, "prev": bool(ctl.is_previous_enabled),
              "next": bool(ctl.is_next_enabled), "toggle": bool(ctl.is_play_pause_toggle_enabled),
              "pos": tl.position.total_seconds(), "dur": dur if dur > 0 else 0.0,
              "at": time.time()}
        try:
            at = tl.last_updated_time.timestamp()     # kiedy odtwarzacz podał pozycję (do płynnego paska postępu)
            st["at"] = at if 1e9 < at <= time.time() else st["at"]
        except (AttributeError, OSError, ValueError):
            pass
        self.updated.emit(st)
        key = (st["app"], st["title"], st["artist"])
        if key != self._cover_key:
            self._cover_key = key
            data = b""
            if p.thumbnail is not None:
                stream = await p.thumbnail.open_read_async()
                reader = _DataReader(stream.get_input_stream_at(0)); n = await reader.load_async(stream.size)
                data = bytes(reader.read_buffer(n))
            self.cover_ready.emit(data)

    # --- sterowanie ---
    def cmd(self, name):
        """name: toggle_play_pause | skip_next | skip_previous."""
        if self.loop is not None:
            self._submit(self._cmd(name))

    async def _cmd(self, name):
        s = self._pick()
        if s is not None:
            await getattr(s, f"try_{name}_async")()


class SystemPane(QWidget):
    """Tryb „System”: aplikacja Spotify (lub inny odtwarzacz) przez systemowe sterowanie Windows – bez logowania."""

    def __init__(self, owner):
        super().__init__(); self.setObjectName("clear")
        self.o, self.st = owner, {}
        l = QVBoxLayout(self); l.setContentsMargins(0, 0, 0, 0); l.setSpacing(6)
        self.msg = lbl("", "muted2", wrap=True)
        self.card = QWidget(); self.card.setObjectName("clear")
        c = QVBoxLayout(self.card); c.setContentsMargins(0, 0, 0, 0); c.setSpacing(6)
        top = QHBoxLayout(); top.setSpacing(10)
        self.cover = QLabel(); self.cover.setFixedSize(58, 58); self.cover.setObjectName("cover")
        info = QVBoxLayout(); info.setSpacing(0)
        self.song = ElideLabel("Nic nie gra"); self.song.setObjectName("h3")
        self.artist = ElideLabel(""); self.artist.setObjectName("muted"); self.app = lbl("", "muted")
        for w in (self.song, self.artist, self.app):
            info.addWidget(w)
        top.addWidget(self.cover); top.addLayout(info, 1); c.addLayout(top)
        self.bar = QProgressBar(); self.bar.setRange(0, 1000); self.bar.setTextVisible(False); self.bar.setFixedHeight(5)
        c.addWidget(self.bar)
        row = QHBoxLayout(); row.setSpacing(4); row.addStretch(); self.btns = {}
        for key, kind, cmd in (("prev", "prev", "skip_previous"), ("toggle", "play", "toggle_play_pause"),
                               ("next", "next", "skip_next")):
            b = QToolButton(); b.setFixedSize(36, 36); b.setIconSize(QSize(20, 20)); b.setIcon(glyph(kind))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, x=cmd: self.media().cmd(x)); row.addWidget(b); self.btns[key] = b
        row.addStretch(); c.addLayout(row)
        l.addWidget(self.msg); l.addWidget(self.card)
        self.tick = QTimer(self); self.tick.timeout.connect(self.progress)   # tylko pasek postępu, bez zapytań

    def media(self):
        return self.o.host.media

    def start(self):
        m = self.media()
        if not m.available:
            self.card.hide(); self.msg.show()
            self.msg.setText("Sterowanie systemowe działa w Windows 10/11 – w tej instalacji brakuje pakietu "
                             "winrt-Windows.Media.Control." if sys.platform == "win32" else
                             "Sterowanie systemowe jest dostępne tylko w Windows. Użyj trybu Karty lub Spotify.")
            return
        m.updated.connect(self.show_state); m.cover_ready.connect(self.set_cover); m.register()
        self.show_state(m.state)

    def stop(self):
        m = self.media(); self.tick.stop()
        if m.available:
            safe_disconnect(m.updated, self.show_state); safe_disconnect(m.cover_ready, self.set_cover); m.unregister()

    def show_state(self, st):
        self.st = st
        if st.get("error") or not st:
            self.card.hide(); self.msg.show(); self.tick.stop()
            self.msg.setText(st.get("error") or "Nic nie gra. Włącz muzykę w aplikacji Spotify (albo innym odtwarzaczu) – "
                                                 "utwór pojawi się tu sam, bez logowania.")
            return
        self.msg.hide(); self.card.show()
        self.song.setText(st["title"] or "Bez tytułu"); self.artist.setText(st["artist"]); self.app.setText(st["app"])
        self.btns["toggle"].setIcon(glyph("pause" if st["playing"] else "play"))
        for k in ("prev", "next", "toggle"):
            self.btns[k].setEnabled(st[k])
        self.bar.setVisible(st["dur"] > 0); self.progress()
        if st["playing"] and st["dur"] > 0:
            self.tick.start(1000)
        else:
            self.tick.stop()

    def progress(self):
        st = self.st
        if not st.get("dur"):
            return
        pos = st["pos"] + (time.time() - st["at"] if st["playing"] else 0)
        self.bar.setValue(int(1000 * max(0.0, min(pos, st["dur"])) / st["dur"]))

    def set_cover(self, data):
        pm = QPixmap()
        if data and pm.loadFromData(data):
            self.cover.setPixmap(pm.scaled(58, 58, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                           Qt.TransformationMode.SmoothTransformation))
        else:
            self.cover.clear()


class AudioWidget(WidgetFrame):
    """Widget dźwięku: System (Spotify i inne odtwarzacze przez sterowanie Windows, bez logowania),
    Karty (dźwięk z otwartych kart) albo Pliki (lokalny odtwarzacz).
    Każdy tryb jest tworzony leniwie, a nieaktywne tryby nie mają timerów ani nasłuchiwaczy."""
    MODES = (("system", "System", SystemPane), ("tabs", "Karty", TabsPane),
             ("local", "Pliki", LocalPane))

    def build(self):
        row = QHBoxLayout(); row.setSpacing(4); group = QButtonGroup(self); self.btns, self.panes, self.mode = {}, {}, None
        for key, name, _ in self.MODES:
            b = QToolButton(); b.setObjectName("aipick"); b.setCheckable(True); b.setText(name)
            b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(lambda _=False, k=key: self.select(k))
            group.addButton(b); row.addWidget(b); self.btns[key] = b
        row.addStretch(); self.lay.addLayout(row)
        mode = self.store.settings.get("audio_mode")
        if mode not in self.btns:   # np. dawny tryb „Spotify” (logowanie) – teraz tryb System steruje aplikacją Spotify
            mode = "system" if MediaSession.available else "tabs"
        self.select(mode)

    def select(self, key):
        if key == self.mode:
            return
        if self.mode and self.running:
            self.panes[self.mode].stop()
        self.mode = key; self.store.settings["audio_mode"] = key; self.store.save_soon()
        if key not in self.panes:
            cls = {k: c for k, _, c in self.MODES}[key]; self.panes[key] = cls(self); self.lay.addWidget(self.panes[key])
        for k, p in self.panes.items():
            p.setVisible(k == key)
        self.btns[key].setChecked(True)
        if self.running:
            self.panes[key].start()

    def start(self):
        self.panes[self.mode].start()

    def stop(self):
        self.panes[self.mode].stop()

    def teardown(self):
        for p in self.panes.values():
            if hasattr(p, "teardown"):
                p.teardown()


RSS_FEEDS = [("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"), ("Hacker News", "https://hnrss.org/frontpage"),
             ("TVN24", "https://tvn24.pl/najnowsze.xml"), ("Niebezpiecznik", "https://feeds.feedburner.com/niebezpiecznik/")]


class RssWidget(WidgetFrame):
    def build(self):
        for n, u in RSS_FEEDS:
            self.menu.addAction("Źródło: " + n, lambda _=False, u=u: self.set_feed(u))
        self.menu.addAction("Własny adres RSS…", self.custom)
        self.rows = QVBoxLayout(); self.rows.setSpacing(6); self.lay.addLayout(self.rows)
        self.skel = Skeleton(4); self.lay.addWidget(self.skel); self.src = lbl("", "muted")
        self.lay.addWidget(self.src)
        self.t_last = 0; self.timer = QTimer(self); self.timer.timeout.connect(self.fetch)

    def feed(self):
        return self.store.settings.get("rss", RSS_FEEDS[0][1])

    def set_feed(self, u):
        self.store.settings["rss"] = u; self.store.save_soon(); self.fetch()

    def custom(self):
        u, ok = QInputDialog.getText(self, "Źródło RSS", "Adres kanału RSS/Atom:", text=self.feed())
        if ok and u.strip():
            self.set_feed(u.strip())

    def start(self):
        if time.time() - self.t_last > 300:
            self.fetch()
        self.timer.start(10 * 60 * 1000)

    def stop(self):
        self.timer.stop()

    refresh_now = lambda self: self.fetch()

    def fetch(self):
        self.t_last = time.time(); self.skel.show()
        self.store.http(self.feed(), self.guard(self.got), raw=True)

    def got(self, data, err, status):
        self.skel.hide()
        while self.rows.count():
            w = self.rows.takeAt(0).widget()
            if w:
                w.deleteLater()
        try:
            root = ET.fromstring(data); ns = "{http://www.w3.org/2005/Atom}"
            items = root.findall(".//item") or root.findall(f".//{ns}entry")
            for it in items[:5]:
                title = (it.findtext("title") or it.findtext(f"{ns}title") or "").strip()
                link = it.findtext("link") or ""
                if not link:
                    le = it.find(f"{ns}link"); link = le.get("href") if le is not None else ""
                b = ElideButton(title[:90]); b.setObjectName("newsitem"); b.setToolTip(title)
                b.clicked.connect(lambda _=False, u=link: u and self.host.browser.open_url_new_tab(u))
                self.rows.addWidget(b)
            host = host_of(self.feed()); self.src.setText(f"Źródło: {host}")
            if not items:
                raise ValueError
        except Exception:
            self.rows.addWidget(lbl("Nie udało się wczytać kanału RSS.", "muted2"))


ATOM = "{http://purl.org/atom/ns#}"
GMAIL_FEED = "https://mail.google.com/mail/u/0/feed/atom"
DISCORD_APP = "https://discord.com/channels/@me"
HOST_ALIAS = {"gmail.com": "mail.google.com", "inbox.google.com": "mail.google.com"}
# licznik w tytule karty: „(3) Discord”, „Odebrane (5) - … - Gmail”; 1–3 cyfry, żeby nie łapać lat w tytułach filmów
TITLE_COUNT = re.compile(r"^\((\d{1,3})\+?\)\s|\s\((\d{1,3})\+?\)\s+[-–|]")


class NoDiscordAppCheck(QWebEngineUrlRequestInterceptor):
    """Discord Web pyta lokalny port aplikacji Discord (127.0.0.1:6463–6472). Gdy aplikacja działa, zamiast klienta
    pokazuje ekran „Wykryto aplikację Discord” i czeka na kliknięcie – ukryta strona i Czat w widgecie stałyby wtedy
    w miejscu. Dla tych dwóch stron blokujemy to sprawdzenie (zwykłe karty działają bez zmian)."""

    def interceptRequest(self, info):
        u = info.requestUrl()
        if u.host() in ("127.0.0.1", "localhost") and 6463 <= u.port() <= 6472:
            info.block(True)


_NO_DISCORD_APP = []


def no_discord_app_check(page):
    if not _NO_DISCORD_APP:
        _NO_DISCORD_APP.append(NoDiscordAppCheck(QApplication.instance()))
    page.setUrlRequestInterceptor(_NO_DISCORD_APP[0])


class SessionBridge(QObject):
    """Połączenie przez sesję – bez kluczy OAuth. Logowanie odbywa się normalnie w karcie Luny (wspólny profil
    WebEngine), a most kopiuje ciasteczka wybranych usług do własnego QNetworkAccessManagera. Dzięki temu widgety
    i kafelki dostają dane jako zalogowany użytkownik. Źródła liczników: kanał Atom Gmaila (odpytywany tylko, gdy
    ktoś go potrzebuje i okno jest aktywne) oraz tytuły otwartych kart („(3) …”) – te bez żadnych zapytań."""
    changed = pyqtSignal()          # zmiana stanu logowania (Google/Discord) lub nowe dane Gmaila
    counts_changed = pyqtSignal()   # liczniki na kafelkach
    DOMAINS = ("google.com",)       # tylko te ciasteczka trafiają do mostu
    LOGIN = {"google": ("google.com", ("SID", "__Secure-1PSID", "__Secure-3PSID"))}
    POLLED = {"mail.google.com"}    # hosty z licznikiem odpytywanym w tle (nie znikają po zamknięciu karty)

    def __init__(self, store):
        super().__init__()
        self.store, self.active, self._subs = store, True, 0
        self.jar = QNetworkCookieJar()
        self.nam = QNetworkAccessManager(self); self.nam.setCookieJar(self.jar)
        self.counts, self._tab_host = {}, {}
        self.gmail = {"count": None, "items": [], "error": "", "ts": 0.0}
        self._busy = False; self._state = {}; self._dpage = None
        self._emit = QTimer(self); self._emit.setSingleShot(True); self._emit.timeout.connect(self._cookies_settled)
        self._poll = QTimer(self); self._poll.timeout.connect(self.poll)
        self._eval = QTimer(self); self._eval.setSingleShot(True); self._eval.timeout.connect(self._update_poll)
        for sig in (store.changed, store.layout_changed, store.features_changed):   # kafelki, widgety, funkcje
            sig.connect(lambda: self._eval.start(400))
        cs = get_profile().cookieStore()
        cs.cookieAdded.connect(self._added); cs.cookieRemoved.connect(self._removed)
        cs.loadAllCookies()

    # --- ciasteczka ---
    def _ours(self, c):
        d = c.domain().lstrip(".")
        return any(d == x or d.endswith("." + x) for x in self.DOMAINS)

    def _added(self, c):
        if self._ours(c):
            self.jar.insertCookie(c); self._emit.start(300)   # ciasteczka przychodzą seriami – jedna reakcja

    def _removed(self, c):
        if self._ours(c):
            self.jar.deleteCookie(c); self._emit.start(300)

    def _cookies_settled(self):
        state = {k: self.logged_in(k) for k in self.LOGIN}
        if state != self._state:
            self._state = state
            if not state.get("google"):
                self.gmail.update(count=None, items=[], error="", ts=0.0); self._set_count("mail.google.com", 0)
            self.changed.emit(); self._update_poll()

    def logged_in(self, svc):
        dom, names = self.LOGIN[svc]
        for c in self.jar.allCookies():
            d = c.domain().lstrip(".")
            if (d == dom or d.endswith("." + dom)) and bytes(c.name()).decode() in names:
                return True
        return False

    # --- liczniki kafelków ---
    @staticmethod
    def _host(url):
        h = host_of(url)
        return HOST_ALIAS.get(h, h)

    def count_for(self, url):
        return self.counts.get(self._host(url), 0)

    def _set_count(self, host, n):
        if self.counts.get(host, 0) != n:
            if n:
                self.counts[host] = n
            else:
                self.counts.pop(host, None)
            self.counts_changed.emit()

    def on_tab_title(self, tab, url, title):
        host = self._host(url)
        if host == "discord.com":
            self._discord_url(url)
        old = self._tab_host.get(id(tab))
        if old and old != host:
            self._drop(old, tab)
        self._tab_host[id(tab)] = host
        m = TITLE_COUNT.search(title or "")
        if m or host in self.counts:
            self._set_count(host, int(m.group(1) or m.group(2)) if m else 0)

    def forget_tab(self, tab):
        host = self._tab_host.pop(id(tab), None)
        if host:
            self._drop(host, tab)

    def _drop(self, host, tab):
        others = [t for k, t in self._tab_host.items() if k != id(tab) and t == host]
        polled = host in self.POLLED or (host == "discord.com" and self._dpage is not None)   # ukryty Discord liczy dalej
        if not polled and not others:
            self._set_count(host, 0)

    # --- Gmail (kanał Atom skrzynki odbiorczej) ---
    def register(self):
        self._subs += 1; self._update_poll()

    def unregister(self):
        self._subs = max(0, self._subs - 1); self._update_poll()

    def set_active(self, active):
        self.active = active; self._update_poll()

    def _wanted(self):
        tile = any(self._host(b["url"]) == "mail.google.com" for b in self.store.items)
        return self.active and (self._subs > 0 or tile) and self.logged_in("google")

    def _update_poll(self):
        self._update_discord()
        if self._wanted():
            if not self._poll.isActive():
                self._poll.start(180000)
                if time.time() - self.gmail["ts"] > 60:
                    self.poll()
        else:
            self._poll.stop()

    def poll(self):
        if self._busy or not self.logged_in("google"):
            return
        self._busy = True
        req = QNetworkRequest(QUrl(GMAIL_FEED))
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, get_profile().httpUserAgent())
        req.setTransferTimeout(15000)
        r = self.nam.get(req); r.finished.connect(lambda r=r: self._gmail_reply(r))

    # --- Discord (licznik wzmianek z tytułu klienta WWW: „(3) Discord | …”) ---
    def discord_logged_in(self):
        return bool(self.store.settings.get("discord", {}).get("web"))

    def _discord_url(self, url):
        """Każdy widok Discorda (karta, Czat w widgecie, ukryta strona) mówi, czy sesja jest aktywna."""
        path = QUrl(url).path()
        if path.startswith("/channels"):
            self._set_discord_web(True)
        elif path.startswith("/login"):
            self._set_discord_web(False)

    def _set_discord_web(self, on):
        if on != self.discord_logged_in():
            self.store.settings.setdefault("discord", {})["web"] = on; self.store.save_soon()
            if not on:
                self._set_count("discord.com", 0)
            self.changed.emit(); self._update_discord()

    def _discord_wanted(self):
        st = self.store
        used = any(self._host(b["url"]) == "discord.com" for b in st.items)
        return st.feature("discord_watch") and used and self.discord_logged_in()

    def _update_discord(self):
        if self._discord_wanted() and self._dpage is None:
            pg = self._dpage = QWebEnginePage(get_profile(), self)
            pg.setAudioMuted(True)      # dźwięki powiadomień tylko z widocznego Discorda
            no_discord_app_check(pg)
            pg.titleChanged.connect(lambda t: self.on_tab_title(pg, pg.url().toString(), t))
            pg.urlChanged.connect(lambda u: self._discord_url(u.toString()))
            pg.setUrl(QUrl(DISCORD_APP))
        elif not self._discord_wanted() and self._dpage is not None:
            pg, self._dpage = self._dpage, None
            self.forget_tab(pg); pg.deleteLater()

    def _gmail_reply(self, r):
        self._busy = False
        status = r.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        neterr = r.error() != QNetworkReply.NetworkError.NoError
        data = bytes(r.readAll()); r.deleteLater()
        try:
            root = ET.fromstring(data)
            if root.tag != ATOM + "feed":   # np. strona logowania, która akurat jest poprawnym XML-em
                raise ValueError
            count = int(root.findtext(ATOM + "fullcount") or 0)
            m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", root.findtext(ATOM + "title") or "")
            if m:
                self.gmail["email"] = m.group(0)
        except (ET.ParseError, ValueError):
            root = None
        if root is None:   # 401 albo strona logowania zamiast kanału
            self.gmail["error"] = ("need" if status in (401, 403) or (status == 200 and not neterr)
                                   else "Brak połączenia z Gmailem.")
            self.changed.emit(); return
        items = []
        for e in root.findall(ATOM + "entry")[:6]:
            link = e.find(ATOM + "link")
            when = None
            try:
                when = datetime.fromisoformat((e.findtext(ATOM + "issued") or e.findtext(ATOM + "modified") or "")
                                              .replace("Z", "+00:00")).astimezone()
            except ValueError:
                pass
            items.append({"from": e.findtext(ATOM + "author/" + ATOM + "name") or e.findtext(ATOM + "author/" + ATOM + "email") or "",
                          "subject": e.findtext(ATOM + "title") or "", "summary": e.findtext(ATOM + "summary") or "",
                          "url": link.get("href") if link is not None else "https://mail.google.com/mail/u/0/#inbox",
                          "when": when})
        self.gmail.update(count=count, items=items, error="", ts=time.time())
        self._set_count("mail.google.com", count); self.changed.emit()


# --- kod QR (czysty Python: tryb bajtowy, poziom korekcji M, wersje 1–40) ---
_QR_ECC = [-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28,
           28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28]
_QR_BLOCKS = [-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28,
              29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49]


def _qr_raw_modules(ver):
    r = (16 * ver + 128) * ver + 64
    if ver >= 2:
        n = ver // 7 + 2; r -= (25 * n - 10) * n - 55
        if ver >= 7:
            r -= 36
    return r


def _qr_data_codewords(ver):
    return _qr_raw_modules(ver) // 8 - _QR_ECC[ver] * _QR_BLOCKS[ver]


def _gf_mul(x, y):
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D); z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree):
    res = [0] * (degree - 1) + [1]; root = 1
    for _ in range(degree):
        for j in range(degree):
            res[j] = _gf_mul(res[j], root)
            if j + 1 < degree:
                res[j] ^= res[j + 1]
        root = _gf_mul(root, 0x02)
    return res


def _rs_remainder(data, div):
    res = [0] * len(div)
    for b in data:
        f = b ^ res.pop(0); res.append(0)
        for i, c in enumerate(div):
            res[i] ^= _gf_mul(c, f)
    return res


def qr_matrix(text, mask=None):
    """Macierz kodu QR (lista wierszy True = ciemny moduł) dla tekstu, np. adresu strony."""
    data = text.encode("utf-8")
    for ver in range(1, 41):
        cap = _qr_data_codewords(ver) * 8
        if 4 + (8 if ver < 10 else 16) + len(data) * 8 <= cap:
            break
    else:
        raise ValueError("Za długi tekst na kod QR")
    bits = []
    put = lambda v, n: bits.extend((v >> i) & 1 for i in range(n - 1, -1, -1))
    put(4, 4); put(len(data), 8 if ver < 10 else 16)
    for b in data:
        put(b, 8)
    put(0, min(4, cap - len(bits))); put(0, (-len(bits)) % 8)
    pad = 0xEC
    while len(bits) < cap:
        put(pad, 8); pad ^= 0xEC ^ 0x11
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    nb, ecl = _QR_BLOCKS[ver], _QR_ECC[ver]; raw = _qr_raw_modules(ver) // 8
    nshort, slen = nb - raw % nb, raw // nb; div = _rs_divisor(ecl); blocks = []; k = 0
    for i in range(nb):
        dat = words[k:k + slen - ecl + (0 if i < nshort else 1)]; k += len(dat)
        ecc = _rs_remainder(dat, div)
        blocks.append(dat + ([0] if i < nshort else []) + ecc)
    seq = [b[i] for i in range(len(blocks[0])) for j, b in enumerate(blocks) if i != slen - ecl or j >= nshort]
    size = ver * 4 + 17
    mod = [[False] * size for _ in range(size)]; fn = [[False] * size for _ in range(size)]

    def setf(x, y, dark):
        mod[y][x] = dark; fn[y][x] = True
    for i in range(size):
        setf(6, i, i % 2 == 0); setf(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < size and 0 <= y < size:
                    setf(x, y, max(abs(dx), abs(dy)) not in (2, 4))
    if ver > 1:
        n = ver // 7 + 2; step = (ver * 8 + n * 3 + 5) // (n * 4 - 4) * 2
        pos = [6] + sorted(size - 7 - i * step for i in range(n - 1))
        for i, a in enumerate(pos):
            for j, b in enumerate(pos):
                if (i, j) not in ((0, 0), (0, n - 1), (n - 1, 0)):
                    for dy in range(-2, 3):
                        for dx in range(-2, 3):
                            setf(a + dx, b + dy, max(abs(dx), abs(dy)) != 1)

    def format_bits(mask):
        d = mask; r = d   # poziom M = 00
        for _ in range(10):
            r = (r << 1) ^ ((r >> 9) * 0x537)
        v = (d << 10 | r) ^ 0x5412
        bit = lambda i: (v >> i) & 1 != 0
        for i in range(6):
            setf(8, i, bit(i))
        setf(8, 7, bit(6)); setf(8, 8, bit(7)); setf(7, 8, bit(8))
        for i in range(9, 15):
            setf(14 - i, 8, bit(i))
        for i in range(8):
            setf(size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            setf(8, size - 15 + i, bit(i))
        setf(8, size - 8, True)
    format_bits(0)
    if ver >= 7:
        r = ver
        for _ in range(12):
            r = (r << 1) ^ ((r >> 11) * 0x1F25)
        v = ver << 12 | r
        for i in range(18):
            b = (v >> i) & 1 != 0; a, c = size - 11 + i % 3, i // 3
            setf(a, c, b); setf(c, a, b)
    i = 0; right = size - 1; total = len(seq) * 8
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j; y = size - 1 - vert if ((right + 1) & 2) == 0 else vert
                if not fn[y][x] and i < total:
                    mod[y][x] = (seq[i >> 3] >> (7 - (i & 7))) & 1 != 0; i += 1
        right -= 2
    masks = [lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
             lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
             lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
             lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0]

    def apply(m):
        for y in range(size):
            for x in range(size):
                if not fn[y][x] and masks[m](x, y):
                    mod[y][x] = not mod[y][x]

    def penalty():   # ocena maski wg normy: serie, bloki 2×2, wzory podobne do znaczników narożników, równowaga
        s = 0
        for line in mod + [list(c) for c in zip(*mod)]:
            txt = "".join("1" if v else "0" for v in line)
            s += 40 * (txt.count("10111010000") + txt.count("00001011101"))
            run = 1
            for a, b in zip(line, line[1:]):
                if a == b:
                    run += 1
                else:
                    s += run - 2 if run >= 5 else 0; run = 1
            s += run - 2 if run >= 5 else 0
        for y in range(size - 1):
            for x in range(size - 1):
                if mod[y][x] == mod[y][x + 1] == mod[y + 1][x] == mod[y + 1][x + 1]:
                    s += 3
        dark = sum(map(sum, mod)); s += abs(dark * 20 - size * size * 10) // (size * size) * 10
        return s
    best = None
    for m in (range(8) if mask is None else [mask]):
        apply(m); format_bits(m); p = penalty()
        if best is None or p < best[0]:
            best = (p, m)
        apply(m)
    apply(best[1]); format_bits(best[1])
    return mod


def qr_pixmap(text, px=4, border=4, dark="#111111", light="#ffffff"):
    m = qr_matrix(text); n = len(m); S = (n + 2 * border) * px
    pm = QPixmap(S, S); pm.fill(QColor(light)); p = QPainter(pm)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(dark))
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                p.drawRect((x + border) * px, (y + border) * px, px, px)
    p.end()
    return pm


class ParcelsWidget(WidgetFrame):
    """Śledzenie przesyłek: InPost wprost w widgecie (publiczne API ShipX, bez logowania), pozostali przewoźnicy –
    jedno kliknięcie otwiera ich stronę śledzenia z numerem. Odświeża co 15 min, tylko gdy widget jest widoczny."""
    API = "https://api-shipx-pl.easypack24.net/v1/tracking/"
    STATUS_API = "https://api-shipx-pl.easypack24.net/v1/statuses?lang=pl_PL"
    LINKS = {"InPost": "https://inpost.pl/sledzenie-przesylek?number={}",
             "DPD": "https://tracktrace.dpd.com.pl/parcelDetails?typ=1&p1={}",
             "DHL": "https://www.dhl.com/pl-pl/home/sledzenie-przesylek.html?tracking-id={}",
             "Poczta Polska": "https://emonitoring.poczta-polska.pl/?numer={}",
             "GLS": "https://gls-group.com/PL/pl/sledzenie-paczek?match={}",
             "UPS": "https://www.ups.com/track?loc=pl_PL&tracknum={}",
             "Orlen Paczka": "https://www.orlenpaczka.pl/sledz-paczke/?numer={}"}
    READY = {"ready_to_pickup", "out_for_delivery", "ready_to_pickup_from_branch", "avizo"}
    STATUSES = {}

    def build(self):
        row = QHBoxLayout(); row.setSpacing(6)
        self.inp = QLineEdit(); self.inp.setObjectName("glassin"); self.inp.setPlaceholderText("Numer przesyłki")
        self.inp.returnPressed.connect(self.add)
        self.carrier = QComboBox(); self.carrier.addItems(["Auto"] + list(self.LINKS)); self.carrier.setFixedWidth(84)
        row.addWidget(self.inp, 1); row.addWidget(self.carrier); self.lay.addLayout(row)
        self.list = QVBoxLayout(); self.list.setSpacing(4); self.lay.addLayout(self.list)
        self.menu.addAction("Odśwież statusy", self.refresh_now)
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh_now)
        self.render()

    def items(self):
        return self.store.settings.setdefault("parcels", [])

    @staticmethod
    def detect(n):
        if re.fullmatch(r"\d{24}", n):
            return "InPost"
        if re.fullmatch(r"[A-Z]{2}\d{9}PL|\d{20}", n):
            return "Poczta Polska"
        if n.upper().startswith("1Z"):
            return "UPS"
        if re.fullmatch(r"\d{13}[A-Z]?|\d{14}", n):
            return "DPD"
        return "InPost"

    def add(self):
        n = re.sub(r"\s+", "", self.inp.text()).upper()
        if not n or any(p["n"] == n for p in self.items()):
            return
        c = self.carrier.currentText(); c = self.detect(n) if c == "Auto" else c
        self.items().insert(0, {"n": n, "c": c, "st": "", "code": "", "when": ""}); del self.items()[12:]
        self.store.save_soon(); self.inp.clear(); self.render(); self.refresh_now()

    def remove(self, n):
        self.store.settings["parcels"] = [p for p in self.items() if p["n"] != n]; self.store.save_soon(); self.render()

    def start(self):
        self.refresh_now(); self.timer.start(15 * 60 * 1000)

    def stop(self):
        self.timer.stop()

    def refresh_now(self):
        if not any(p["c"] == "InPost" for p in self.items()):
            return
        if not ParcelsWidget.STATUSES:
            self.store.http(self.STATUS_API, self.guard(self._statuses)); return
        for p in self.items():
            if p["c"] == "InPost":
                self.store.http(self.API + quote(p["n"]), self.guard(lambda j, e, s, n=p["n"]: self._got(n, j, s)))

    def _statuses(self, j, err, status):
        for it in (j or {}).get("items", []) if isinstance(j, dict) else []:
            ParcelsWidget.STATUSES[it.get("name")] = (it.get("title") or "").rstrip(".")
        if ParcelsWidget.STATUSES:
            self.refresh_now()

    def _got(self, n, j, status):
        p = next((x for x in self.items() if x["n"] == n), None)
        if p is None:
            return
        if isinstance(j, dict) and j.get("status"):
            p["code"] = j["status"]; p["st"] = self.STATUSES.get(j["status"], j["status"].replace("_", " "))
            det = (j.get("tracking_details") or [{}])[0]
            when = det.get("datetime") or j.get("updated_at") or ""
            p["when"] = when[8:10] + "." + when[5:7] + " " + when[11:16] if len(when) >= 16 else ""
        elif status == 404:
            p["st"], p["code"] = "Nie znaleziono – sprawdź numer", ""
        self.store.save_soon(); self.render()

    def render(self):
        while self.list.count():
            w = self.list.takeAt(0).widget()
            if w:
                w.deleteLater()
        ready = 0
        for p in self.items():
            box = QFrame(); box.setObjectName("mailitem"); v = QVBoxLayout(box); v.setContentsMargins(10, 6, 6, 6); v.setSpacing(1)
            top = QHBoxLayout(); top.setSpacing(4)
            top.addWidget(lbl(f"{p['c']} · {p['n']}", "h3"), 1)
            for kind, tip, fn in (("external", "Otwórz stronę śledzenia", lambda _=False, p=p: self.host.browser.open_url_new_tab(
                    self.LINKS.get(p["c"], self.LINKS["InPost"]).format(quote(p["n"])))),
                                  ("close", "Usuń z listy", lambda _=False, n=p["n"]: self.remove(n))):
                b = QToolButton(); b.setIcon(glyph(kind)); b.setIconSize(QSize(14, 14)); b.setFixedSize(22, 22); b.setToolTip(tip)
                b.clicked.connect(fn); top.addWidget(b)
            v.addLayout(top)
            if p["c"] == "InPost":
                txt = p["st"] or "Sprawdzanie…"
            else:
                txt = "Status na stronie przewoźnika (ikona obok)"
            st = lbl(txt + (f"  ·  {p['when']}" if p.get("when") else ""), "muted2", wrap=True)
            if p.get("code") in self.READY:
                st.setStyleSheet("color:#3ddc84"); ready += 1
            elif p.get("code") == "delivered":
                st.setStyleSheet("color:#8c8c8c")
            v.addWidget(st); self.list.addWidget(box)
        if not self.items():
            self.list.addWidget(lbl("Dodaj numer przesyłki – InPost pokaże status od razu.", "muted2", wrap=True))
        self.set_badge(ready)


class CountdownWidget(WidgetFrame):
    """Odliczanie dni, godzin i minut do wybranej daty (np. urlop, egzamin, premiera)."""

    def build(self):
        self.title = lbl("", "h3"); self.lay.addWidget(self.title)
        row = QHBoxLayout(); row.setSpacing(8); self.cells = []
        for name in ("dni", "godz.", "min"):
            col = QVBoxLayout(); col.setSpacing(0)
            n = lbl("–", "clock", align=Qt.AlignmentFlag.AlignCenter); t = lbl(name, "muted", align=Qt.AlignmentFlag.AlignCenter)
            col.addWidget(n); col.addWidget(t); row.addLayout(col, 1); self.cells.append(n)
        self.lay.addLayout(row)
        self.when = lbl("", "muted2", align=Qt.AlignmentFlag.AlignCenter); self.lay.addWidget(self.when)
        self.edit_box = QWidget(); self.edit_box.setObjectName("clear"); e = QVBoxLayout(self.edit_box); e.setContentsMargins(0, 4, 0, 0)
        self.name_in = QLineEdit(); self.name_in.setObjectName("glassin"); self.name_in.setPlaceholderText("Nazwa celu, np. Urlop")
        from PyQt6.QtWidgets import QDateTimeEdit
        self.dt = QDateTimeEdit(QDateTime.currentDateTime().addDays(7)); self.dt.setCalendarPopup(True)
        self.dt.setDisplayFormat("dd.MM.yyyy HH:mm")
        ok = QPushButton("Zapisz"); ok.clicked.connect(self.save)
        e.addWidget(self.name_in); e.addWidget(self.dt); e.addWidget(ok); self.lay.addWidget(self.edit_box)
        self.menu.addAction("Zmień cel…", lambda: self.edit_box.setVisible(True))
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick)
        cfg = self.store.settings.get("countdown")
        self.edit_box.setVisible(not cfg); self.tick()

    def save(self):
        self.store.settings["countdown"] = {"name": self.name_in.text().strip() or "Cel",
                                            "at": self.dt.dateTime().toString(Qt.DateFormat.ISODate)}
        self.store.save_soon(); self.edit_box.hide(); self.tick()

    def start(self):
        self.tick(); self.timer.start(15000)

    def stop(self):
        self.timer.stop()

    def tick(self):
        c = self.store.settings.get("countdown")
        if not c:
            self.title.setText("Ustaw datę, do której liczyć"); return
        at = QDateTime.fromString(c["at"], Qt.DateFormat.ISODate)
        self.title.setText(c["name"]); self.when.setText(QLocale(QLocale.Language.Polish).toString(at, "dddd, d MMMM yyyy, HH:mm"))
        secs = QDateTime.currentDateTime().secsTo(at)
        if secs <= 0:
            for cell in self.cells:
                cell.setText("0")
            self.when.setText("Cel osiągnięty – " + at.toString("d.MM.yyyy HH:mm")); return
        mins = secs // 60
        for cell, v in zip(self.cells, (mins // 1440, mins // 60 % 24, mins % 60)):
            cell.setText(str(v))


class PingWidget(WidgetFrame):
    """Opóźnienie sieci: czas połączenia z 8.8.8.8 (Google DNS, port 53) co 3 s – bez uruchamiania programu ping."""
    HOST, PORT = "8.8.8.8", 53

    def build(self):
        top = QHBoxLayout(); self.val = lbl("– ms", "temp"); self.q = lbl("", "muted2")
        top.addWidget(self.val); top.addStretch(); top.addWidget(self.q); self.lay.addLayout(top)
        self.spark = Sparkline(252, 40); self.lay.addWidget(self.spark)
        self.stats = lbl("", "muted2", wrap=True); self.lay.addWidget(self.stats)
        self.hist, self.lost, self.sent = [], 0, 0
        self.timer = QTimer(self); self.timer.timeout.connect(self.probe)
        self.sock = None

    def start(self):
        self.probe(); self.timer.start(3000)

    def stop(self):
        self.timer.stop()
        if self.sock is not None:
            self.sock.abort()

    def probe(self):
        from PyQt6.QtNetwork import QTcpSocket
        if self.sock is not None:   # poprzednia próba bez odpowiedzi = utracony pakiet
            self.sock.abort(); self.sock.deleteLater(); self.lost += 1; self.record(None)
        s = self.sock = QTcpSocket(self); t = QElapsedTimer(); t.start(); self.sent += 1

        def done():
            ms = t.nsecsElapsed() / 1e6; s.abort(); s.deleteLater()
            if self.sock is s:
                self.sock = None; self.record(ms)
        s.connected.connect(done); s.connectToHost(self.HOST, self.PORT)

    def record(self, ms):
        self.hist = (self.hist + [ms])[-40:]; ok = [v for v in self.hist if v is not None]
        if ms is not None:
            col = "#3ddc84" if ms < 50 else "#f0b232" if ms < 120 else "#ff5c5c"
            self.val.setText(f"{ms:.0f} ms"); self.q.setText(("Świetne" if ms < 50 else "Dobre" if ms < 120 else "Słabe") + " połączenie")
            self.q.setStyleSheet(f"color:{col}")
        else:
            self.val.setText("brak odp."); self.q.setText("Brak połączenia"); self.q.setStyleSheet("color:#ff5c5c")
        if ok:
            jit = sum(abs(a - b) for a, b in zip(ok, ok[1:])) / max(1, len(ok) - 1)
            self.stats.setText(f"średnio {sum(ok) / len(ok):.0f} ms · min {min(ok):.0f} · max {max(ok):.0f} · "
                               f"wahania {jit:.0f} ms · utracone {self.lost * 100 // max(1, self.sent)}%")
        self.spark.set_data([v if v is not None else (max(ok) if ok else 0) for v in self.hist],
                            not ok or ok[-1] <= sum(ok) / len(ok) * 1.2)


class PwQrWidget(WidgetFrame):
    """Generator silnych haseł i kod QR z adresu aktywnej karty (do szybkiego otwarcia strony na telefonie)."""

    def build(self):
        row = QHBoxLayout(); row.setSpacing(4)
        self.pw = QLineEdit(); self.pw.setObjectName("glassin"); self.pw.setReadOnly(True)
        self.len = QComboBox(); [self.len.addItem(str(n), n) for n in (12, 16, 20, 24, 32)]; self.len.setCurrentIndex(2)
        self.len.setFixedWidth(58); self.len.currentIndexChanged.connect(lambda _: self.new_pw())
        row.addWidget(self.pw, 1); row.addWidget(self.len); self.lay.addLayout(row)
        r2 = QHBoxLayout(); r2.setSpacing(6)
        for text, fn in (("Nowe hasło", self.new_pw), ("Kopiuj", lambda: copy_secret(self.pw.text()))):
            b = QPushButton(text); b.clicked.connect(lambda _=False, f=fn: f()); r2.addWidget(b)
        self.lay.addLayout(r2)
        sep = QFrame(); sep.setObjectName("sep"); self.lay.addWidget(sep)
        self.qr = QLabel(); self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter); self.qr.setMinimumHeight(60)
        self.qr_txt = lbl("", "muted", wrap=True, align=Qt.AlignmentFlag.AlignCenter)
        self.lay.addWidget(self.qr); self.lay.addWidget(self.qr_txt)
        r3 = QHBoxLayout(); r3.setSpacing(6)
        for text, fn in (("Z bieżącej karty", self.from_tab), ("Zapisz PNG", self.save_png)):
            b = QPushButton(text); b.clicked.connect(lambda _=False, f=fn: f()); r3.addWidget(b)
        self.lay.addLayout(r3)
        self.text = ""; self.new_pw()

    def start(self):
        self.from_tab()

    def new_pw(self):
        self.pw.setText(gen_password(self.len.currentData() or 20))

    def from_tab(self):
        web = self.host.browser.web()
        t = web.url().toString() if web is not None else ""
        if t and t != self.text:
            self.text = t; self.qr.setPixmap(qr_pixmap(t, px=3 if len(t) < 120 else 2))
            self.qr_txt.setText(t)
        elif not t:
            self.qr.clear(); self.qr_txt.setText("Otwórz stronę w karcie, aby utworzyć jej kod QR")

    def save_png(self):
        if not self.text:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz kod QR", str(Path(DOWNLOADS[0].folder() if DOWNLOADS else HOME) /
                                                                          "kod-qr.png"), "PNG (*.png)")
        if path:
            qr_pixmap(self.text, px=10).save(path, "PNG")


class ScreenPicker(QWidget):
    """Nakładka ze zrzutem jednego ekranu (razem z oknem Luny): lupa pod kursorem, klik = wybór koloru, Esc = anuluj.
    Na każdym monitorze jest osobna nakładka – kolor można pobrać z przeglądarki i z dowolnego innego miejsca."""
    picked = pyqtSignal(QColor)
    cancelled = pyqtSignal()

    def __init__(self, scr):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.shot = scr.grabWindow(0); self.img = self.shot.toImage(); self.dpr = self.shot.devicePixelRatio() or 1.0
        self.setGeometry(scr.geometry()); self.setCursor(Qt.CursorShape.CrossCursor); self.setMouseTracking(True)
        self.pos_ = self.mapFromGlobal(QCursor.pos()); self.inside = self.rect().contains(self.pos_)

    @staticmethod
    def pick_all(on_color):
        """Nakładki na wszystkich ekranach; wybór na jednym zamyka wszystkie."""
        ovs = [ScreenPicker(scr) for scr in QGuiApplication.screens()]
        def finish(c=None):
            for o in ovs:
                try:
                    o.close()
                except RuntimeError:
                    pass
            if c is not None:
                on_color(c)
        for o in ovs:
            o.picked.connect(finish); o.cancelled.connect(finish); o.show()
        ovs[0].activateWindow(); ovs[0].setFocus()
        return ovs

    def enterEvent(self, ev):
        self.inside = True; self.setFocus(); self.update()

    def leaveEvent(self, ev):
        self.inside = False; self.update()

    def color_at(self, pos):
        x = min(max(0, int(pos.x() * self.dpr)), self.img.width() - 1); y = min(max(0, int(pos.y() * self.dpr)), self.img.height() - 1)
        return self.img.pixelColor(x, y)

    def mouseMoveEvent(self, ev):
        self.pos_ = ev.position().toPoint(); self.inside = True; self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.picked.emit(self.color_at(ev.position().toPoint()))
        else:
            self.cancelled.emit()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()

    def paintEvent(self, ev):
        p = QPainter(self); p.drawPixmap(self.rect(), self.shot)
        p.fillRect(QRect(0, 0, self.width(), 30), QColor(17, 17, 17, 200)); p.setPen(QColor("#ececec"))
        p.drawText(QRect(0, 0, self.width(), 30), Qt.AlignmentFlag.AlignCenter,
                   "Kliknij, aby pobrać kolor (także z okna Luny) · Esc lub prawy przycisk – anuluj")
        if not self.inside:
            return
        c = self.color_at(self.pos_); x, y = self.pos_.x(), self.pos_.y()
        Z, N = 10, 11; box = QRect(x + 18, y + 18, Z * N, Z * N + 26)
        if box.right() > self.width():
            box.moveRight(x - 18)
        if box.bottom() > self.height():
            box.moveBottom(y - 18)
        src = self.img.copy(int(x * self.dpr) - N // 2, int(y * self.dpr) - N // 2, N, N)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.fillRect(box, QColor("#111111")); p.drawImage(QRect(box.x(), box.y(), Z * N, Z * N), src)
        p.setPen(QPen(QColor("#ffffff"), 1)); p.drawRect(box.x() + Z * (N // 2), box.y() + Z * (N // 2), Z, Z)
        p.drawRect(box.adjusted(0, 0, -1, -1))
        p.fillRect(QRect(box.x() + 6, box.bottom() - 19, 14, 14), c)
        p.drawText(QRect(box.x() + 26, box.bottom() - 22, box.width() - 30, 20), Qt.AlignmentFlag.AlignVCenter, c.name().upper())


class ColorPickerWidget(WidgetFrame):
    """Próbnik kolorów: kolor dowolnego piksela z ekranu, kody HEX / RGB / HSL do skopiowania i historia ostatnich kolorów."""

    def build(self):
        row = QHBoxLayout(); row.setSpacing(10)
        self.sw = QLabel(); self.sw.setFixedSize(54, 54); row.addWidget(self.sw)
        col = QVBoxLayout(); col.setSpacing(2); self.codes = {}
        for k in ("HEX", "RGB", "HSL"):
            b = QPushButton(""); b.setObjectName("mailitem"); b.setToolTip("Kliknij, aby skopiować")
            b.clicked.connect(lambda _=False, k=k: QGuiApplication.clipboard().setText(self.codes[k].text().split("  ", 1)[-1]))
            col.addWidget(b); self.codes[k] = b
        row.addLayout(col, 1); self.lay.addLayout(row)
        pick = QPushButton("Pobierz kolor z ekranu"); pick.clicked.connect(self.pick); self.lay.addWidget(pick)
        self.histrow = QHBoxLayout(); self.histrow.setSpacing(4); self.lay.addLayout(self.histrow)
        hist = self.store.settings.get("colors") or ["#ececec"]
        self.show_color(QColor(hist[0]), remember=False)

    def pick(self):
        """Zrzut ekranów razem z Luną (bez minimalizowania) – kolor z przeglądarki albo spoza niej."""
        menu = self.menu_btn.menu() if self.menu_btn.menu() else None
        if menu is not None:
            menu.hide()
        QTimer.singleShot(120, lambda: setattr(self, "_ovs", ScreenPicker.pick_all(self.guard(self.show_color))))

    def show_color(self, c, remember=True):
        self.sw.setStyleSheet(f"background:{c.name()}; border-radius:12px; border:1px solid #3a3a3a;")
        h, s, l, _ = c.getHslF()
        self.codes["HEX"].setText(f"HEX  {c.name().upper()}")
        self.codes["RGB"].setText(f"RGB  rgb({c.red()}, {c.green()}, {c.blue()})")
        self.codes["HSL"].setText(f"HSL  hsl({round(max(h, 0) * 360)}, {round(s * 100)}%, {round(l * 100)}%)")
        hist = self.store.settings.get("colors") or []
        if remember:
            hist = [c.name()] + [x for x in hist if x != c.name()][:7]
            self.store.settings["colors"] = hist; self.store.save_soon()
        while self.histrow.count():
            it = self.histrow.takeAt(0).widget()
            if it:
                it.deleteLater()
        for hx in hist[:8]:
            b = QToolButton(); b.setFixedSize(24, 24); b.setToolTip(hx.upper())
            b.setStyleSheet(f"background:{hx}; border-radius:6px; border:1px solid #3a3a3a;")
            b.clicked.connect(lambda _=False, hx=hx: self.show_color(QColor(hx), remember=False)); self.histrow.addWidget(b)
        self.histrow.addStretch()


UNITS = {   # kategoria → {jednostka: współczynnik do jednostki bazowej}
    "Długość": {"mm": 0.001, "cm": 0.01, "m": 1, "km": 1000, "cal": 0.0254, "stopa": 0.3048, "jard": 0.9144, "mila": 1609.344},
    "Masa": {"g": 0.001, "dag": 0.01, "kg": 1, "t": 1000, "uncja": 0.028349523, "funt": 0.45359237},
    "Objętość": {"ml": 0.001, "l": 1, "m³": 1000, "łyżeczka": 0.005, "szklanka": 0.25, "galon (US)": 3.785411784},
    "Prędkość": {"km/h": 1 / 3.6, "m/s": 1, "mph": 0.44704, "węzeł": 0.514444},
    "Dane": {"B": 1, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12, "KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3},
    "Temperatura": {"°C": None, "°F": None, "K": None},
}
ZONES = [("Warszawa", "Europe/Warsaw"), ("Londyn", "Europe/London"), ("Nowy Jork", "America/New_York"),
         ("Los Angeles", "America/Los_Angeles"), ("Tokio", "Asia/Tokyo"), ("Pekin", "Asia/Shanghai"), ("Dubaj", "Asia/Dubai"),
         ("Sydney", "Australia/Sydney"), ("Moskwa", "Europe/Moscow"), ("Kijów", "Europe/Kyiv"), ("UTC", "UTC")]


class ConverterWidget(WidgetFrame):
    """Konwerter jednostek (długość, masa, objętość, prędkość, dane, temperatura) i stref czasowych – bez internetu."""

    def build(self):
        self.cat = QComboBox(); self.cat.addItems(list(UNITS) + ["Strefy czasowe"]); self.lay.addWidget(self.cat)
        self.units = QWidget(); self.units.setObjectName("clear"); u = QVBoxLayout(self.units); u.setContentsMargins(0, 0, 0, 0)
        self.val = QLineEdit("1"); self.val.setObjectName("glassin")
        row = QHBoxLayout(); row.setSpacing(4); self.a = QComboBox(); self.b = QComboBox()
        sw = QToolButton(); sw.setIcon(glyph("swap")); sw.setIconSize(QSize(16, 16)); sw.setFixedSize(28, 28)
        sw.clicked.connect(lambda: (lambda i, j: (self.a.setCurrentIndex(j), self.b.setCurrentIndex(i)))(self.a.currentIndex(),
                                                                                                         self.b.currentIndex()))
        row.addWidget(self.a, 1); row.addWidget(sw); row.addWidget(self.b, 1)
        self.res = lbl("", "temp"); self.res.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        u.addWidget(self.val); u.addLayout(row); u.addWidget(self.res); self.lay.addWidget(self.units)
        self.zones = QWidget(); self.zones.setObjectName("clear"); z = QVBoxLayout(self.zones); z.setContentsMargins(0, 0, 0, 0)
        from PyQt6.QtWidgets import QDateTimeEdit
        self.when = QDateTimeEdit(QDateTime.currentDateTime()); self.when.setDisplayFormat("dd.MM.yyyy HH:mm")
        zr = QHBoxLayout(); zr.setSpacing(4); self.za = QComboBox(); self.zb = QComboBox()
        for name, _ in ZONES:
            self.za.addItem(name); self.zb.addItem(name)
        self.zb.setCurrentIndex(2); zr.addWidget(self.za, 1); zr.addWidget(lbl("→", "muted2")); zr.addWidget(self.zb, 1)
        self.zres = lbl("", "temp"); self.zall = lbl("", "muted2", wrap=True)
        z.addWidget(self.when); z.addLayout(zr); z.addWidget(self.zres); z.addWidget(self.zall); self.lay.addWidget(self.zones)
        for w in (self.val,):
            w.textChanged.connect(lambda _: self.calc())
        for w in (self.a, self.b):
            w.currentIndexChanged.connect(lambda _: self.calc())
        for w in (self.za, self.zb):
            w.currentIndexChanged.connect(lambda _: self.calc())
        self.when.dateTimeChanged.connect(lambda _: self.calc())
        self.cat.currentIndexChanged.connect(lambda _: self.set_cat())
        self.set_cat()

    def set_cat(self):
        c = self.cat.currentText(); tz = c == "Strefy czasowe"
        self.units.setVisible(not tz); self.zones.setVisible(tz)
        if not tz:
            for w in (self.a, self.b):
                w.blockSignals(True); w.clear(); w.addItems(list(UNITS[c])); w.blockSignals(False)
            self.b.setCurrentIndex(min(1, self.b.count() - 1))
        self.calc()

    def calc(self):
        c = self.cat.currentText()
        if c == "Strefy czasowe":
            from PyQt6.QtCore import QTimeZone
            src = QDateTime(self.when.dateTime().date(), self.when.dateTime().time(), QTimeZone(ZONES[self.za.currentIndex()][1].encode()))
            out = src.toTimeZone(QTimeZone(ZONES[self.zb.currentIndex()][1].encode()))
            self.zres.setText(out.toString("HH:mm") + (f"  ({out.toString('d.MM')})" if out.date() != src.date() else ""))
            self.zall.setText("  ·  ".join(f"{n} {src.toTimeZone(QTimeZone(z.encode())).toString('HH:mm')}"
                                           for n, z in ZONES[:6] if n != ZONES[self.za.currentIndex()][0]))
            return
        try:
            v = float(self.val.text().replace(",", ".").replace(" ", ""))
        except ValueError:
            self.res.setText(""); return
        a, b = self.a.currentText(), self.b.currentText()
        if c == "Temperatura":
            k = {"°C": v + 273.15, "°F": (v - 32) * 5 / 9 + 273.15, "K": v}[a]
            r = {"°C": k - 273.15, "°F": (k - 273.15) * 9 / 5 + 32, "K": k}[b]
        else:
            r = v * UNITS[c][a] / UNITS[c][b]
        self.res.setText(f"= {r:.6g} {b}".replace(".", ","))


class TextStatsWidget(WidgetFrame):
    """Licznik znaków i słów: znaki (ze spacjami i bez), słowa, zdania, akapity, szacowany czas czytania i mówienia."""

    def build(self):
        self.edit = QPlainTextEdit(); self.edit.setObjectName("note"); self.edit.setPlaceholderText("Wklej lub wpisz tekst…")
        self.edit.setFixedHeight(110); self.lay.addWidget(self.edit)
        from PyQt6.QtWidgets import QGridLayout
        g = QGridLayout(); g.setHorizontalSpacing(10); g.setVerticalSpacing(2); self.vals = {}
        for i, (k, t) in enumerate((("chars", "Znaki"), ("nospace", "Bez spacji"), ("words", "Słowa"), ("sent", "Zdania"),
                                    ("para", "Akapity"), ("read", "Czytanie"), ("speak", "Mówienie"), ("avg", "Śr. długość słowa"))):
            g.addWidget(lbl(t, "muted2"), i // 2, (i % 2) * 2); v = lbl("0", "h3"); g.addWidget(v, i // 2, (i % 2) * 2 + 1)
            self.vals[k] = v
        self.lay.addLayout(g)
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self.count)
        self.edit.textChanged.connect(lambda: self._t.start(150))
        clr = QPushButton("Wyczyść"); clr.clicked.connect(self.edit.clear); self.lay.addWidget(clr)

    @staticmethod
    def mmss(minutes):
        s = round(minutes * 60)
        return f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s"

    def count(self):
        t = self.edit.toPlainText(); words = re.findall(r"[\w'’-]+", t)
        v = {"chars": len(t), "nospace": len(re.sub(r"\s", "", t)), "words": len(words),
             "sent": len([s for s in re.split(r"[.!?…]+", t) if s.strip()]),
             "para": len([p for p in re.split(r"\n\s*\n", t) if p.strip()]),
             "read": self.mmss(len(words) / 200), "speak": self.mmss(len(words) / 130),
             "avg": f"{sum(map(len, words)) / len(words):.1f}" if words else "0"}
        for k, x in v.items():
            self.vals[k].setText(str(x))


WIDGET_INFO = {   # id: (ikona, kategoria, opis w katalogu)
    "streak": ("history", "Produktywność", "Seria dni z rzędu i kalendarz aktywności jak na GitHubie."),
    "todo": ("select", "Produktywność", "Prosta lista zadań do odhaczania."),
    "notes": ("app", "Produktywność", "Szybkie notatki zapisywane automatycznie."),
    "pomodoro": ("timer", "Produktywność", "Minutnik pracy w blokach 25 / 5 minut."),
    "countdown": ("timer", "Produktywność", "Odliczanie dni, godzin i minut do wybranej daty."),
    "calc": ("app", "Narzędzia", "Kalkulator – działania wpisywane jak tekst."),
    "translate": ("swap", "Narzędzia", "Tłumacz tekstu (MyMemory)."),
    "clipboard": ("copy", "Narzędzia", "Historia skopiowanych tekstów (tylko w pamięci, bez haseł)."),
    "convert": ("ruler", "Narzędzia", "Jednostki (długość, masa, temperatura…) i strefy czasowe – bez internetu."),
    "textstat": ("text", "Narzędzia", "Liczba znaków, słów, zdań i szacowany czas czytania."),
    "pwqr": ("qr", "Narzędzia", "Silne hasła i kod QR z adresu aktywnej karty."),
    "picker": ("droplet", "Narzędzia", "Kolor dowolnego piksela z ekranu – HEX, RGB, HSL."),
    "clock": ("history", "Informacje", "Godzina i data."),
    "weather": ("zoom", "Informacje", "Pogoda teraz i prognoza na 5 dni."),
    "markets": ("share", "Informacje", "Kryptowaluty i akcje z wykresami."),
    "currency": ("swap", "Informacje", "Przelicznik walut: PLN, USD, EUR, GBP, BTC."),
    "rss": ("bookmark", "Informacje", "Nagłówki z wybranych kanałów RSS."),
    "parcels": ("package", "Informacje", "Śledzenie przesyłek – InPost od razu w widgecie, DPD, DHL, Poczta Polska i inni."),
    "ping": ("signal", "System", "Opóźnienie sieci (ms do 8.8.8.8) i stabilność połączenia."),
    "system": ("tools", "System", "Użycie procesora, pamięci i baterii."),
    "audio": ("play", "Multimedia", "Spotify i inne odtwarzacze (sterowanie przez Windows), dźwięk z kart, pliki."),
}


class WidgetMarket(QDialog):
    """Rynek Widgetów: katalog modułów (instalacja do lewego lub prawego panelu) i lista zainstalowanych
    (kolejność, przeniesienie na drugą stronę, odinstalowanie). Nie tworzy żadnych widgetów – tylko zmienia układ;
    widget powstaje dopiero po dodaniu do panelu i jest niszczony od razu po odinstalowaniu."""

    def __init__(self, browser):
        super().__init__(browser); self.b, self.store = browser, browser.store
        self.setObjectName("settings"); self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setModal(True); self.resize(fit_size(960, 660)); self.setMinimumSize(fit_size(700, 480, 0.8))
        root = QVBoxLayout(self); root.setContentsMargins(1, 1, 1, 1); root.setSpacing(0)
        bar = DragBar(); bl = QHBoxLayout(bar); bl.setContentsMargins(18, 8, 8, 8)
        ic = QLabel(); ic.setPixmap(glyph("grid", "#ececec").pixmap(20, 20)); bl.addWidget(ic); bl.addSpacing(6)
        bl.addWidget(lbl("Rynek Widgetów", "h1")); bl.addSpacing(16)
        grp = QButtonGroup(self); self.tabs = {}
        for key, text in (("cat", "Katalog"), ("inst", "Zainstalowane")):
            t = QToolButton(); t.setObjectName("aipick"); t.setCheckable(True); t.setText(text)
            t.setCursor(Qt.CursorShape.PointingHandCursor); t.clicked.connect(lambda _=False, k=key: self.show_tab(k))
            grp.addButton(t); bl.addWidget(t); self.tabs[key] = t
        bl.addStretch()
        self.search = QLineEdit(); self.search.setObjectName("glassin"); self.search.setPlaceholderText("Szukaj widgetu…")
        self.search.setFixedWidth(220); self.search.textChanged.connect(lambda _: self.fill_catalog()); bl.addWidget(self.search)
        x = QToolButton(); x.setIcon(glyph("close")); x.setIconSize(QSize(22, 22)); x.setFixedSize(32, 32); x.clicked.connect(self.accept)
        bl.addWidget(x); root.addWidget(bar)
        self.stack = QStackedWidget(); self.stack.setObjectName("clear"); root.addWidget(self.stack, 1)
        # katalog
        self.cat_area = SmoothScroll(); self.cat_area.setWidgetResizable(True); self.cat_area.setFrameShape(QFrame.Shape.NoFrame)
        self.cat_area.viewport().setAutoFillBackground(False); self.stack.addWidget(self.cat_area)
        # zainstalowane
        inst = QWidget(); inst.setObjectName("clear"); il = QHBoxLayout(inst); il.setContentsMargins(20, 14, 20, 18); il.setSpacing(16)
        self.cols = {}
        for side, title in (("left", "Lewy panel"), ("right", "Prawy panel")):
            box = QFrame(); box.setObjectName("acc"); v = QVBoxLayout(box); v.setContentsMargins(14, 12, 14, 12); v.setSpacing(6)
            v.addWidget(lbl(title, "h3"))
            sa = SmoothScroll(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.Shape.NoFrame); sa.viewport().setAutoFillBackground(False)
            sa.setObjectName("clear"); sa.viewport().setObjectName("clear")
            holder = QWidget(); holder.setObjectName("clear"); col = QVBoxLayout(holder); col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(4); sa.setWidget(holder); v.addWidget(sa, 1); il.addWidget(box, 1); self.cols[side] = col
        self.stack.addWidget(inst)
        self.store.layout_changed.connect(self._changed)
        self.show_tab("cat")

    def done(self, r):
        safe_disconnect(self.store.layout_changed, self._changed); super().done(r)

    def _changed(self):
        QTimer.singleShot(0, lambda: (self.fill_catalog(), self.fill_installed()))

    def show_tab(self, key):
        self.tabs[key].setChecked(True); self.search.setVisible(key == "cat")
        self.stack.setCurrentIndex(0 if key == "cat" else 1)
        self.fill_catalog() if key == "cat" else self.fill_installed()

    def installed(self, wid):
        return self.store.wcfg(wid)["on"]

    # --- akcje ---
    def install(self, wid, side):
        st = self.store; gate = WIDGETS[wid][4]
        if gate and not st.feature(gate):                     # np. Gmail włącza integrację z Google
            st.settings.setdefault("features", {})[gate] = True; st.features_changed.emit()
        feats = st.settings.setdefault("features", {})
        if not feats.get(side, True):                           # panel był wyłączony – włącz go
            feats[side] = True; st.features_changed.emit()
        other = "right" if side == "left" else "left"
        ids = {s: [w for w in st.side_order(s) if w != wid] for s in ("left", "right")}
        ids[side].append(wid); st.set_wcfg(wid, on=True, collapsed=False, emit=False)
        st.apply_layout(ids["left"], ids["right"])
        sb = self.b.host.left if side == "left" else self.b.host.right
        if sb.user_collapsed:
            self.b.toggle_sidebar(side)
        self.b.notice.info(f"Dodano „{WIDGETS[wid][0]}” do {'lewego' if side == 'left' else 'prawego'} panelu.")

    def uninstall(self, wid):
        self.store.set_wcfg(wid, on=False)   # WidgetHost.sync niszczy obiekt: zatrzymuje timery i zapytania, zwalnia pamięć

    def move(self, wid, d):
        self.b.host.move(wid, d)

    def flip(self, wid):
        self.b.host.flip(wid)

    # --- widoki ---
    @staticmethod
    def _clear(layout):
        while layout.count():
            it = layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                WidgetMarket._clear(it.layout())

    def card(self, wid):
        title, _, _, _, gate = WIDGETS[wid]; kind, catg, desc = WIDGET_INFO.get(wid, ("app", "Inne", ""))
        c = QFrame(); c.setObjectName("mcard"); c.setFixedHeight(168)
        v = QVBoxLayout(c); v.setContentsMargins(14, 12, 14, 12); v.setSpacing(4)
        top = QHBoxLayout(); top.setSpacing(10)
        ic = QLabel(); ic.setPixmap(glyph(kind, "#ececec").pixmap(26, 26)); ic.setFixedSize(38, 38); ic.setObjectName("micon")
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter); top.addWidget(ic)
        tc = QVBoxLayout(); tc.setSpacing(0); tc.addWidget(lbl(title, "h3")); tc.addWidget(lbl(catg, "muted")); top.addLayout(tc, 1)
        v.addLayout(top)
        d = lbl(desc + (f" Włączy integrację: {FEATURES[gate][0]}." if gate and not self.store.feature(gate) else ""),
                "muted2", wrap=True)
        v.addWidget(d, 1)
        row = QHBoxLayout(); row.setSpacing(6)
        if self.installed(wid):
            side = self.store.wcfg(wid)["side"]
            st = lbl(f"Zainstalowany · {'lewy' if side == 'left' else 'prawy'} panel", "muted2"); st.setStyleSheet("color:#3ddc84")
            row.addWidget(st, 1)
            un = QPushButton("Odinstaluj"); un.clicked.connect(lambda _=False: self.uninstall(wid)); row.addWidget(un)
        else:
            for side, text in (("left", "+ Lewy panel"), ("right", "+ Prawy panel")):
                bt = QPushButton(text); bt.setObjectName("primary" if side == WIDGETS[wid][1] else "")
                bt.clicked.connect(lambda _=False, s=side: self.install(wid, s)); row.addWidget(bt, 1)
        v.addLayout(row)
        return c

    def fill_catalog(self):
        q = self.search.text().strip().lower()
        inner = QWidget(); inner.setObjectName("clear")
        from PyQt6.QtWidgets import QGridLayout
        outer = QVBoxLayout(inner); outer.setContentsMargins(20, 14, 20, 20); outer.setSpacing(10)
        n_inst = sum(1 for w in WIDGETS if self.installed(w))
        self.tabs["inst"].setText(f"Zainstalowane ({n_inst})")
        outer.addWidget(lbl("Dodaj widget do lewego albo prawego panelu. Niezainstalowane widgety nie zajmują pamięci "
                            "i nie wysyłają żadnych zapytań.", "muted2", wrap=True))
        cats = {}
        for wid in WIDGETS:
            kind, catg, desc = WIDGET_INFO.get(wid, ("app", "Inne", ""))
            if q and q not in (WIDGETS[wid][0] + " " + desc + " " + catg).lower():
                continue
            cats.setdefault(catg, []).append(wid)
        for catg in ("Produktywność", "Narzędzia", "Informacje", "System", "Multimedia", "Konta", "Inne"):
            if catg not in cats:
                continue
            outer.addWidget(lbl(catg.upper(), "cap"))
            g = QGridLayout(); g.setSpacing(10)
            for i, wid in enumerate(cats[catg]):
                g.addWidget(self.card(wid), i // 3, i % 3)
            for k in range(3):
                g.setColumnStretch(k, 1)
            outer.addLayout(g)
        if not cats:
            outer.addWidget(lbl("Nic nie znaleziono.", "muted2"))
        outer.addStretch(1)
        old = self.cat_area.takeWidget(); self.cat_area.setWidget(inner)
        if old is not None:
            old.deleteLater()

    def fill_installed(self):
        for side, col in self.cols.items():
            self._clear(col)
            ids = [w for w in self.store.side_order(side) if self.installed(w)]
            for i, wid in enumerate(ids):
                row = QFrame(); row.setObjectName("mrow"); h = QHBoxLayout(row); h.setContentsMargins(10, 6, 6, 6); h.setSpacing(4)
                ic = QLabel(); ic.setPixmap(glyph(WIDGET_INFO.get(wid, ("app",))[0]).pixmap(18, 18)); h.addWidget(ic)
                h.addWidget(lbl(WIDGETS[wid][0]), 1)
                for kind, tip, fn, ok in (("up", "W górę", lambda _=False, w=wid: self.move(w, -1), i > 0),
                                          ("chev_down", "W dół", lambda _=False, w=wid: self.move(w, 1), i < len(ids) - 1),
                                          ("swap", "Przenieś do " + ("prawego" if side == "left" else "lewego") + " panelu",
                                           lambda _=False, w=wid: self.flip(w), True),
                                          ("trash", "Odinstaluj", lambda _=False, w=wid: self.uninstall(w), True)):
                    bt = QToolButton(); bt.setIcon(glyph(kind)); bt.setIconSize(QSize(16, 16)); bt.setFixedSize(28, 28)
                    bt.setToolTip(tip); bt.clicked.connect(fn); h.addWidget(bt)
                    sp = bt.sizePolicy(); sp.setRetainSizeWhenHidden(True); bt.setSizePolicy(sp); bt.setVisible(ok)
                col.addWidget(row)
            if not ids:
                col.addWidget(lbl("Brak widgetów – dodaj je w Katalogu.", "muted2", wrap=True))
            col.addStretch(1)
        self.tabs["inst"].setText(f"Zainstalowane ({sum(1 for w in WIDGETS if self.installed(w))})")


WIDGET_CLASSES = {"streak": StreakWidget, "clock": ClockWidget, "weather": WeatherWidget, "markets": MarketsWidget,
                  "currency": CurrencyWidget, "notes": NotesWidget, "todo": TodoWidget, "pomodoro": PomodoroWidget,
                  "clipboard": ClipboardWidget, "calc": CalcWidget, "translate": TranslateWidget, "system": SystemWidget,
                  "audio": AudioWidget, "rss": RssWidget, "parcels": ParcelsWidget,
                  "countdown": CountdownWidget, "ping": PingWidget, "pwqr": PwQrWidget, "picker": ColorPickerWidget,
                  "convert": ConverterWidget, "textstat": TextStatsWidget}


def make_widget(wid, store, host):
    return WIDGET_CLASSES[wid](wid, store, host)


# ======================================================================================
#  USTAWIENIA (okno modalne, rozszerzalne przez rejestrowanie stron)
# ======================================================================================
SETTINGS_PAGES = []  # (id, tytuł, funkcja budująca stronę) – dodaj kolejną stronę dekoratorem @settings_page


def settings_page(pid, title):
    def deco(fn):
        SETTINGS_PAGES.append((pid, title, fn)); return fn
    return deco


def ui_images():
    """Przełącznik On/Off i okrągłe pole wyboru – rysowane raz do PNG (QSS potrzebuje plików)."""
    out = {}
    try:
        ICONS.mkdir(exist_ok=True)
        specs = {"sw_off": (36, 20), "sw_on": (36, 20), "ck_off": (20, 20), "ck_on": (20, 20)}
        for name, (w, h) in specs.items():
            f = ICONS / f"_{name}.png"
            if not f.exists():
                pm = QPixmap(w, h); pm.fill(Qt.GlobalColor.transparent)
                p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(Qt.PenStyle.NoPen)
                if name.startswith("sw"):
                    on = name == "sw_on"
                    p.setBrush(QColor("#ececec" if on else "#3a3a3a")); p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
                    p.setBrush(QColor("#111111" if on else "#bdbdbd")); p.drawEllipse(QPointF(w - 10 if on else 10, h / 2), 7, 7)
                else:
                    on = name == "ck_on"
                    if on:
                        p.setBrush(QColor("#ececec")); p.drawEllipse(1, 1, w - 2, h - 2)
                        p.setPen(QPen(QColor("#111111"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                        p.drawPolyline(QPolygonF([QPointF(6, 10.5), QPointF(9, 13.5), QPointF(14, 7)]))
                    else:
                        p.setPen(QPen(QColor("#5a5a5a"), 1.6)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(2, 2, w - 4, h - 4)
                p.end(); pm.save(str(f), "PNG")
            out[name] = f.as_posix()
    except OSError:
        pass
    return out


def switch_row(title, desc, checked, on_toggle):
    w = QWidget(); w.setObjectName("clear")
    h = QHBoxLayout(w); h.setContentsMargins(0, 8, 0, 8); h.setSpacing(14)
    col = QVBoxLayout(); col.setSpacing(2)
    col.addWidget(lbl(title, "h3")); col.addWidget(lbl(desc, "muted", wrap=True))
    cb = QCheckBox(); cb.setObjectName("switch"); cb.setChecked(checked); cb.toggled.connect(on_toggle)
    h.addLayout(col, 1); h.addWidget(cb, 0, Qt.AlignmentFlag.AlignVCenter)
    return w


def scroll_page(inner):
    sa = SmoothScroll(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.Shape.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.viewport().setAutoFillBackground(False); sa.setWidget(inner)
    return sa


def page_box(title, subtitle=""):
    w = QWidget(); w.setObjectName("clear")
    l = QVBoxLayout(w); l.setContentsMargins(24, 20, 24, 24); l.setSpacing(6)
    l.addWidget(lbl(title, "h1"))
    if subtitle:
        l.addWidget(lbl(subtitle, "muted2", wrap=True))
    l.addSpacing(8)
    return w, l


@settings_page("features", "Funkcje")
def page_features(dlg):
    w, l = page_box("Zarządzanie funkcjami", "Wyłączone moduły nie ładują zasobów ani nie wysyłają zapytań w tle. "
                                            "Zmiany zapisują się automatycznie.")
    for fid, (name, desc, _) in FEATURES.items():
        if fid == "battery_saver" and not has_battery():   # komputer stacjonarny – opcja niepotrzebna
            continue
        l.addWidget(switch_row(name, desc, dlg.store.feature(fid), lambda v, f=fid: dlg.store.set_feature(f, v)))
        sep = QFrame(); sep.setObjectName("sep"); l.addWidget(sep)
    l.addWidget(lbl("Język tłumaczenia", "h3"))
    l.addWidget(lbl("Na ten język Luna tłumaczy strony i zaznaczony tekst (z dowolnego języka).", "muted", wrap=True))
    lc = QComboBox()
    for code, name in sorted(LANGS.items(), key=lambda kv: fold(kv[1])):
        lc.addItem(name, code)
    lc.setCurrentIndex(max(0, lc.findData(translate_target(dlg.store))))
    lc.currentIndexChanged.connect(lambda _: (dlg.store.settings.__setitem__("translate_target", lc.currentData()),
                                              dlg.store.save_soon()))
    l.addWidget(lc, 0, Qt.AlignmentFlag.AlignLeft); l.addSpacing(10)
    clr = QPushButton("Wyczyść historię przeglądania"); clr.clicked.connect(lambda: dlg.store.clear_history())
    l.addSpacing(6); l.addWidget(clr, 0, Qt.AlignmentFlag.AlignLeft)
    l.addStretch(1)
    return scroll_page(w)


@settings_page("look", "Wygląd")
def page_look(dlg):
    w, l = page_box("Wygląd", "Tło jest grafiką wektorową (SVG) renderowaną w rozdzielczości ekranu – ostrą także na Retina/HiDPI. Skaluje się w trybie „cover”.")
    store = dlg.store
    combo = QComboBox()
    for key, name in (("image", "Wektorowe – ukośne arkusze i poświata (ostre na HiDPI)"), ("gradient", "Gradient"), ("solid", "Jednolite czarne")):
        combo.addItem(name, key)
    combo.setCurrentIndex(max(0, combo.findData(store.settings.get("bg", "image"))))

    def bg_changed(_):
        store.settings["bg"] = combo.currentData(); store.save_settings()
        BG.key = None; dlg.browser.bgframe._recompute(); dlg.host.repaint_all()
        for w in WINDOWS:
            w.bgframe._recompute(); w.host.repaint_all()
    combo.currentIndexChanged.connect(bg_changed)
    sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(60, 235); sl.setValue(GLASS_ALPHA[0])

    def glass(v):
        GLASS_ALPHA[0] = v; store.settings["glass"] = v; store.save_soon(); dlg.host.repaint_all()
    sl.valueChanged.connect(glass)
    l.addWidget(lbl("Tło", "h3")); l.addWidget(combo); l.addSpacing(10)
    l.addWidget(lbl("Nieprzezroczystość paneli (szkło)", "h3")); l.addWidget(sl); l.addSpacing(14)
    name, desc, _ = FEATURES["dark_pages"]
    l.addWidget(switch_row(name, desc + " Skrót: Ctrl+Shift+D.", store.feature("dark_pages"), lambda v: store.set_feature("dark_pages", v)))
    l.addWidget(lbl("Strony bez ciemnego trybu", "h3"))
    ex = QListWidget(); ex.setObjectName("wlist"); ex.setMaximumHeight(120); ex.viewport().setAutoFillBackground(False)
    ex.addItems(store.settings.get("dark_except", [])); l.addWidget(ex)
    rm = QPushButton("Usuń zaznaczoną (ciemny tryb wróci)")
    rm.clicked.connect(lambda: ex.currentItem() and (dlg.browser.set_dark_except(ex.currentItem().text(), False), ex.takeItem(ex.currentRow())))
    l.addWidget(rm, 0, Qt.AlignmentFlag.AlignLeft); l.addStretch(1)
    return scroll_page(w)


@settings_page("keys", "Skróty")
def page_keys(dlg):
    w, l = page_box("Skróty klawiszowe i gesty", "Można je wyłączyć w Funkcje → Skróty klawiszowe i gesty myszy.")
    for k, d in (("Ctrl + T", "Nowa karta"), ("Ctrl + W", "Zamknij kartę"), ("F5 / Ctrl + R", "Odśwież kartę lub widgety"),
                 ("Ctrl + Tab / Ctrl + Shift + Tab", "Następna / poprzednia karta"), ("Ctrl + L", "Pasek adresu"),
                 ("Ctrl + J", "Asystent AI"), ("Ctrl + ,", "Ustawienia"), ("Ctrl + \\", "Podział ekranu"), ("F9", "Tryb czytania"), ("Ctrl + Shift + L", "Przetłumacz stronę / pokaż oryginał"),
                 ("Ctrl + K", "Paleta poleceń: polecenia, karty, historia, ustawienia"), ("Ctrl + Shift + O", "Dodaj do „Do przeczytania”"), ("Ctrl + Shift + T", "Przywróć zamkniętą kartę"), ("Ctrl + Shift + Spacja", "Szukaj w kartach"), ("Shift + Esc", "Menedżer zadań"), ("Ctrl + Shift + S", "Zrzut fragmentu strony"), ("Ctrl + Shift + P", "Obraz w obrazie"),
                 ("Ctrl + Shift + G", "Dodaj kartę do grupy"), ("Ctrl + Shift + A / klik w logo", "Lista kart i grup"),
                 ("Ctrl + N / Ctrl + Shift + N", "Nowe okno / okno prywatne"), ("Ctrl + Shift + E", "Rynek Widgetów"), ("Ctrl + H", "Historia"), ("Ctrl + Shift + D", "Ciemny tryb stron"), ("Ctrl + F", "Znajdź na stronie"),
                 ("Ctrl + + / − / 0", "Powiększenie"), ("F11", "Pełny ekran"), ("Ctrl + P", "Drukuj"),
                 ("Ctrl + S", "Zapisz stronę"), ("Ctrl + Shift + Y", "Pobrane pliki"), ("Ctrl + Shift + Del", "Usuń dane przeglądania"),
                 ("F12 / Ctrl + U", "Narzędzia deweloperskie / źródło strony"),
                 ("Środkowy przycisk na karcie", "Zamyka kartę"), ("Środkowy przycisk na pustym pasku", "Nowa karta")):
        row = QHBoxLayout(); a = lbl(k, "h3"); b = lbl(d, "muted2")
        row.addWidget(a); row.addStretch(); row.addWidget(b); l.addLayout(row)
    l.addSpacing(14); l.addWidget(lbl("Wyszukiwanie w aplikacjach (pasek adresu)", "h2"))
    l.addWidget(lbl("Wpisz skrót i spację, potem szukany tekst – np. „yt koncert”, „sp lofi”, „ig #morze”, „tt @nazwa”. "
                    "Sam skrót otwiera aplikację.", "muted", wrap=True))
    keys = {}
    for k, app in APP_KEYWORDS.items():
        if k != app:
            keys.setdefault(app, []).append(k)
    for app, ks in keys.items():
        row = QHBoxLayout(); a = lbl("  /  ".join(ks), "h3"); b = lbl(APPS[app][0], "muted2")
        row.addWidget(a); row.addStretch(); row.addWidget(b); l.addLayout(row)
    l.addStretch(1)
    return scroll_page(w)


SECRET_CLIP = [""]   # hasło skopiowane przez Lunę – widget Schowek go nie zapamiętuje


def copy_secret(text):
    SECRET_CLIP[0] = text; QGuiApplication.clipboard().setText(text)


class NoticeBar(QFrame):
    """Pasek pod narzędziami: pytanie (np. „Zapisać hasło?”) z przyciskami albo krótka informacja."""

    def __init__(self):
        super().__init__(); self.setObjectName("notice"); self.hide()
        h = QHBoxLayout(self); h.setContentsMargins(16, 6, 10, 6); h.setSpacing(6)
        self.ic = QLabel(); self.ic.setPixmap(glyph("key", "#ececec").pixmap(18, 18)); self.ic.setFixedSize(20, 20)
        self.text = lbl("", "h3"); h.addWidget(self.ic); h.addWidget(self.text, 1)
        self.btns = QHBoxLayout(); self.btns.setSpacing(6); h.addLayout(self.btns)
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self.hide)

    def _clear(self):
        while self.btns.count():
            w = self.btns.takeAt(0).widget()
            if w:
                w.deleteLater()

    def set_icon(self, kind="key"):
        self.ic.setPixmap(glyph(kind, "#ececec").pixmap(18, 18))

    def ask(self, text, actions, icon="key"):
        self._t.stop(); self._clear(); self.text.setText(text); self.set_icon(icon)
        for label, fn, primary in actions:
            b = QPushButton(label)
            if primary:
                b.setObjectName("primary")
            b.clicked.connect(lambda _=False, f=fn: (self.hide(), f() if f else None))
            self.btns.addWidget(b)
        self.show()

    def info(self, text, ms=6000, icon="key"):
        self._clear(); self.text.setText(text); self.set_icon(icon); self.show(); self._t.start(ms)


@settings_page("tabs", "Karty i przestrzenie")
def page_tabs(dlg):
    w, l = page_box("Karty i przestrzenie", "Pionowe karty z grupami, przestrzenie robocze (np. Praca, Zakupy, Hobby), "
                                            "podział ekranu i usypianie nieaktywnych kart.")
    st, b = dlg.store, dlg.browser
    for fid in ("workspaces", "vertical_tabs", "restore_tabs", "sleep_tabs") + (("battery_saver",) if has_battery() else ()):
        name, desc, _ = FEATURES[fid]
        l.addWidget(switch_row(name, desc, st.feature(fid), lambda v, f=fid: st.set_feature(f, v)))
    combo = QComboBox()
    for m in (5, 15, 30, 60, 120):
        combo.addItem(f"po {m} min bez używania", m)
    combo.setCurrentIndex(max(0, combo.findData(int(st.settings.get("sleep_after", 15)))))
    combo.currentIndexChanged.connect(lambda _: (st.settings.__setitem__("sleep_after", combo.currentData()), st.save_soon()))
    l.addWidget(lbl("Usypiaj karty", "h3")); l.addWidget(combo); l.addSpacing(12)
    l.addWidget(lbl("Przestrzenie robocze", "h3"))
    l.addWidget(lbl("Każda przestrzeń ma własne karty – nie mieszają się. Przełączasz je ikoną obok logo na pasku kart.",
                    "muted", wrap=True))
    lw = QListWidget(); lw.setObjectName("wlist"); lw.setMaximumHeight(150); lw.viewport().setAutoFillBackground(False)

    def fill():
        lw.clear()
        for name in b.workspaces():
            n = sum(1 for t in b.all_tabs() if t.ws == name)
            lw.addItem(f"{name}  ·  {n} {'karta' if n == 1 else 'kart'}" + ("  (bieżąca)" if name == b.ws else ""))
    fill(); l.addWidget(lw)
    row = QHBoxLayout(); row.setSpacing(6)
    for text, fn in (("Nowa przestrzeń…", b.new_ws), ("Zmień nazwę bieżącej…", b.rename_ws), ("Usuń bieżącą", b.delete_ws)):
        bt = QPushButton(text); bt.clicked.connect(lambda _=False, f=fn: (f(), fill())); row.addWidget(bt)
    row.addStretch(); l.addLayout(row); l.addSpacing(12)
    l.addWidget(lbl("Podział ekranu", "h3"))
    l.addWidget(lbl("Ctrl+\\ albo prawy klik na karcie → Podziel ekran: dwie strony obok siebie w jednej karcie.", "muted", wrap=True))
    l.addStretch(1)
    return scroll_page(w)


@settings_page("privacy", "Prywatność")
def page_privacy(dlg):
    w, l = page_box("Prywatność i bezpieczeństwo", "Blokada śledzenia działa w silniku przeglądarki (bez wtyczek), "
                                                  "a kontenery izolują ciasteczka i logowania.")
    st, b = dlg.store, dlg.browser
    name, desc, _ = FEATURES["adblock"]
    l.addWidget(switch_row(name, desc, st.feature("adblock"), lambda v: st.set_feature("adblock", v)))
    sh = SHIELD[0] if SHIELD else None
    stat = lbl("", "muted2", wrap=True); l.addWidget(stat)
    last = {"ok": None}

    def when(ts):
        return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M") if ts else "jeszcze nie pobrano"

    def show_stat(ok=None):
        if ok is not None:
            last["ok"] = ok
        if sh is None:
            stat.setText("Blokada niedostępna."); return
        if sh.net is None:
            head = (f"Listy filtrów nie są jeszcze gotowe – działa podstawowa blokada ({len(sh.domains)} domen). "
                    "Pobranie i przygotowanie list trwa kilka sekund.")
        else:
            head = f"Aktywnych reguł: {sh.rules_total():,}".replace(",", " ") + f" · ostatnia aktualizacja: {when(sh.last_update())}"
        st_ = sh.status_text()
        ok_ = last["ok"]
        stat.setText(head + f" · zablokowano łącznie: {sh.total}" + (f"  ·  {st_}" if st_ else "")
                     + ("" if ok_ is None or st_ else ("  ·  zaktualizowano" if ok_ else "  ·  nie udało się zaktualizować")))
    show_stat()
    up = QPushButton("Zaktualizuj teraz"); up.clicked.connect(lambda: sh and sh.update_list(show_stat))
    l.addWidget(up, 0, Qt.AlignmentFlag.AlignLeft); l.addSpacing(8)
    if sh is not None:
        l.addWidget(lbl("Listy filtrów", "h3"))
        l.addWidget(lbl("Listy pobierają się automatycznie (zapytania warunkowe – tylko gdy się zmieniły) i są przygotowywane "
                        "w tle. Należą do ich autorów; Luna jedynie je stosuje.", "muted", wrap=True))
        rows = []

        def list_desc(x):
            n = sh.list_count(x["id"]); m = sh.meta.get(x["id"]) or {}
            return (f"{x['desc']} Licencja: {x['license']} · {x['homepage']} · reguł: " + f"{n:,}".replace(",", " ")
                    + f" · aktualizacja: {when(m.get('fetched'))}" + ("" if m.get("ok", True) else " (ostatnio bez połączenia)"))
        for x in adblock.catalog.filter_lists():
            on = x["id"] in sh.enabled_ids()
            row = switch_row(x["title"], list_desc(x), on, lambda v, i=x["id"]: sh.set_list_enabled(i, v))
            rows.append((row, x)); l.addWidget(row)
        psl = adblock.catalog.get("psl")
        l.addWidget(lbl(f"Rozpoznawanie domen: {psl['title']} ({psl['license']}, {psl['homepage']}).", "muted", wrap=True))
        l.addSpacing(10)
        l.addWidget(lbl("Moje filtry", "h3"))
        l.addWidget(lbl("Własne reguły w składni uBlock Origin / Adblock Plus, np. ||reklamy.example.com^ albo "
                        "example.com##.baner. Jedna reguła w wierszu, „!” zaczyna komentarz.", "muted", wrap=True))
        ed = QPlainTextEdit(); ed.setPlainText(sh.user_filters()); ed.setMinimumHeight(110); ed.setMaximumHeight(180)
        ed.setPlaceholderText("! moje reguły\n||reklamy.example.com^\nexample.com##.baner")
        l.addWidget(ed)
        sv = QPushButton("Zapisz i zastosuj")
        sv.clicked.connect(lambda: sh.set_user_filters(ed.toPlainText()))
        l.addWidget(sv, 0, Qt.AlignmentFlag.AlignLeft); l.addSpacing(8)

        def refresh():
            try:
                show_stat()
                for row, x in rows:
                    labels = row.findChildren(QLabel)
                    if len(labels) >= 2:
                        labels[1].setText(list_desc(x))
            except RuntimeError:   # strona ustawień już zamknięta
                safe_disconnect(sh.status_changed, refresh)
        sh.status_changed.connect(refresh)
        w.destroyed.connect(lambda _=None: safe_disconnect(sh.status_changed, refresh))
    l.addWidget(lbl("Strony z wyłączoną blokadą", "h3"))
    al = QListWidget(); al.setObjectName("wlist"); al.setMaximumHeight(110); al.viewport().setAutoFillBackground(False)
    al.addItems(st.settings.get("shield_allow", [])); l.addWidget(al)
    rm = QPushButton("Usuń zaznaczoną (włącz blokadę)")
    rm.clicked.connect(lambda: al.currentItem() and (b.shield_allow(al.currentItem().text(), False), al.takeItem(al.currentRow())))
    l.addWidget(rm, 0, Qt.AlignmentFlag.AlignLeft); l.addSpacing(10)
    l.addWidget(lbl("Domeny odblokowane na wybranych stronach", "h3"))
    l.addWidget(lbl("Dodajesz je z menu tarczy obok paska adresu: lista zablokowanych domen na bieżącej stronie.", "muted", wrap=True))
    el = QListWidget(); el.setObjectName("wlist"); el.setMaximumHeight(110); el.viewport().setAutoFillBackground(False)
    for site, doms in sorted((st.settings.get("shield_exc") or {}).items()):
        for d in doms:
            it = QListWidgetItem(f"{d}  na  {site}"); it.setData(Qt.ItemDataRole.UserRole, (site, d)); el.addItem(it)
    l.addWidget(el)
    erm = QPushButton("Usuń zaznaczony wyjątek (blokuj znowu)")

    def drop_exc():
        it = el.currentItem()
        if it and sh is not None:
            site, d = it.data(Qt.ItemDataRole.UserRole)
            sh.set_site_exception("https://" + site + "/", d, False); el.takeItem(el.currentRow())
    erm.clicked.connect(drop_exc)
    l.addWidget(erm, 0, Qt.AlignmentFlag.AlignLeft); l.addSpacing(14)
    if QWebEnginePermission is not None:
        l.addWidget(lbl("Uprawnienia stron", "h3"))
        l.addWidget(lbl("Kamera, mikrofon, udostępnianie ekranu, powiadomienia i lokalizacja – strona pyta raz, a Luna "
                        "pamięta decyzję. Usuń wpis, by strona zapytała ponownie.", "muted", wrap=True))
        pl = QListWidget(); pl.setObjectName("wlist"); pl.setMaximumHeight(140); pl.viewport().setAutoFillBackground(False)
        S = QWebEnginePermission.State

        def fill_perms():
            pl.clear()
            profs = [get_profile("")] + [p for k, p in _CONTAINER_PROFILES.items() if k != PRIVATE]
            for prof in profs:
                try:
                    perms = prof.listAllPermissions()
                except Exception:
                    perms = []
                for p in perms:
                    st_ = p.state()
                    if st_ not in (S.Granted, S.Denied):
                        continue
                    it = QListWidgetItem(f"{p.origin().host()}  ·  {perm_name(p.permissionType())}  ·  "
                                         + ("zezwolono" if st_ == S.Granted else "zablokowano"))
                    it.setData(Qt.ItemDataRole.UserRole, p); pl.addItem(it)
            if not pl.count():
                pl.addItem("Żadna strona jeszcze nie prosiła o uprawnienia.")
        fill_perms(); l.addWidget(pl)
        prm = QPushButton("Usuń zaznaczone (strona zapyta ponownie)")

        def drop_perm():
            it = pl.currentItem(); p = it.data(Qt.ItemDataRole.UserRole) if it else None
            if p is not None:
                p.reset(); fill_perms()
        prm.clicked.connect(drop_perm)
        l.addWidget(prm, 0, Qt.AlignmentFlag.AlignLeft); l.addSpacing(14)
    l.addWidget(lbl("Kontenery", "h3"))
    l.addWidget(lbl("Karta w kontenerze ma osobne ciasteczka i logowania – np. trzy konta w tym samym serwisie jednocześnie, "
                    "a serwisy z innych kontenerów nie widzą Twoich wizyt. Nową kartę w kontenerze otworzysz prawym "
                    "klikiem na przycisku +.", "muted", wrap=True))
    cl = QListWidget(); cl.setObjectName("wlist"); cl.setMaximumHeight(140); cl.viewport().setAutoFillBackground(False)

    def fill():
        cl.clear()
        for c in b.containers():
            it = QListWidgetItem(tab_icon(None, c["color"]), c["name"]); it.setData(Qt.ItemDataRole.UserRole, c["id"]); cl.addItem(it)
    fill(); l.addWidget(cl)

    def sel():
        it = cl.currentItem()
        return next((c for c in b.containers() if it and c["id"] == it.data(Qt.ItemDataRole.UserRole)), None)

    def rename():
        c = sel()
        if c:
            n, ok = QInputDialog.getText(dlg, "Zmień nazwę", "Nazwa kontenera:", text=c["name"])
            if ok and n.strip():
                c["name"] = n.strip(); st.save_soon(); fill(); b.tabs_changed()

    def delete():
        c = sel()
        if c and QMessageBox.question(dlg, "Luna", f"Usunąć kontener „{c['name']}”? Jego karty przejdą do zwykłego profilu, "
                                      "a zapisane w nim logowania zostaną usunięte.") == QMessageBox.StandardButton.Yes:
            b.containers().remove(c); st.save_soon()
            for t in b.all_tabs():
                if t.container == c["id"]:
                    b.reopen_in(t, "")
            prof = _CONTAINER_PROFILES.pop(c["id"], None)
            if prof is not None:
                prof.cookieStore().deleteAllCookies(); prof.clearHttpCache()
            fill()
    row = QHBoxLayout(); row.setSpacing(6)
    for text, fn in (("Nowy kontener…", lambda: (b.new_container(), fill())), ("Zmień nazwę…", rename), ("Usuń", delete)):
        bt = QPushButton(text); bt.clicked.connect(lambda _=False, f=fn: f()); row.addWidget(bt)
    row.addStretch(); l.addLayout(row)
    l.addStretch(1)
    return scroll_page(w)


@settings_page("passwords", "Hasła i aliasy")
def page_passwords(dlg):
    w, l = page_box("Hasła i aliasy e-mail", "Hasła są szyfrowane na tym komputerze (Windows DPAPI – tak jak w Chrome i Edge) "
                                            "i nigdzie nie są wysyłane. Luna proponuje zapis po zalogowaniu i sama wypełnia formularz.")
    st, b = dlg.store, dlg.browser
    v = VAULT[0] if VAULT else None
    name, desc, _ = FEATURES["passwords"]
    l.addWidget(switch_row(name, desc, st.feature("passwords"), lambda on: st.set_feature("passwords", on)))
    if v is None or not v.available():
        l.addWidget(lbl("Menedżer haseł wymaga Windows albo pakietu keyring (pip install keyring).", "muted2", wrap=True))
    elif v.error:
        l.addWidget(lbl(v.error, "muted2", wrap=True))
    flt = QLineEdit(); flt.setObjectName("glassin"); flt.setPlaceholderText("Szukaj strony lub loginu…"); l.addWidget(flt)
    lw = QListWidget(); lw.setObjectName("wlist"); lw.setMinimumHeight(170); lw.viewport().setAutoFillBackground(False)
    l.addWidget(lw)

    def fill():
        lw.clear()
        if v is None:
            return
        q = flt.text().lower().strip()
        for x in sorted(v.logins(), key=lambda x: x["origin"]):
            if q and q not in x["origin"].lower() and q not in x["user"].lower():
                continue
            it = QListWidgetItem(f"{QUrl(x['origin']).host()}   ·   {x['user'] or '(bez loginu)'}   ·   ••••••••"
                                 + ("   ·   2FA" if x.get("totp") else ""))
            it.setData(Qt.ItemDataRole.UserRole, (x["origin"], x["user"])); lw.addItem(it)
    flt.textChanged.connect(lambda _: fill()); fill()

    def cur():
        it = lw.currentItem()
        return v.find(*it.data(Qt.ItemDataRole.UserRole)) if it and v else None

    def show():
        x = cur()
        if x:
            lw.currentItem().setText(f"{QUrl(x['origin']).host()}   ·   {x['user'] or '(bez loginu)'}   ·   {x['pw']}")

    def remove():
        x = cur()
        if x and QMessageBox.question(dlg, "Luna", f"Usunąć hasło dla {QUrl(x['origin']).host()}?") == QMessageBox.StandardButton.Yes:
            v.remove(x["origin"], x["user"]); fill()
    def set_totp():
        x = cur()
        if not x:
            return
        key, ok = QInputDialog.getText(dlg, "Klucz 2FA", f"Klucz uwierzytelniania dwuskładnikowego dla {QUrl(x['origin']).host()}\n"
                                       "(tekstowy klucz z ustawień 2FA strony albo adres otpauth://… z kodu QR;\n"
                                       "puste pole usuwa klucz):", text=x.get("totp", ""))
        if not ok:
            return
        key = key.strip()
        if key and totp_code(key) is None:
            QMessageBox.warning(dlg, "Klucz 2FA", "To nie wygląda na poprawny klucz 2FA (Base32 albo otpauth://…)."); return
        x["totp"] = key; v.save(); fill()
        if key:
            c = totp_code(key)
            QMessageBox.information(dlg, "Klucz 2FA", f"Zapisano. Bieżący kod: {c[0][:3]} {c[0][3:]} (ważny {c[1]} s).\n"
                                                      "Kod znajdziesz w menu klucza na pasku i Luna zaproponuje jego wpisanie.")
    row = QHBoxLayout(); row.setSpacing(6)
    for text, fn in (("Pokaż", show), ("Kopiuj hasło", lambda: cur() and copy_secret(cur()["pw"])),
                     ("Kopiuj login", lambda: cur() and QGuiApplication.clipboard().setText(cur()["user"])),
                     ("Klucz 2FA…", set_totp), ("Usuń", remove)):
        bt = QPushButton(text); bt.clicked.connect(lambda _=False, f=fn: f()); row.addWidget(bt)
    row.addStretch(); l.addLayout(row)
    if v is not None and v.data.get("never"):
        nv = QPushButton(f"Wyczyść listę „Nigdy” ({len(v.data['never'])})")
        nv.clicked.connect(lambda: (v.data.__setitem__("never", []), v.save(), nv.hide())); l.addWidget(nv, 0, Qt.AlignmentFlag.AlignLeft)
    l.addSpacing(14); l.addWidget(lbl("Generator haseł", "h3"))
    g = QHBoxLayout(); g.setSpacing(6)
    out = QLineEdit(gen_password(int(st.settings.get("pw_len", 20)))); out.setObjectName("glassin"); out.setReadOnly(True)
    ln = QComboBox()
    for n in (12, 16, 20, 24, 32):
        ln.addItem(f"{n} znaków", n)
    ln.setCurrentIndex(max(0, ln.findData(int(st.settings.get("pw_len", 20)))))

    def regen():
        st.settings["pw_len"] = ln.currentData(); st.save_soon(); out.setText(gen_password(ln.currentData()))
    ln.currentIndexChanged.connect(lambda _: regen())
    nb = QPushButton("Nowe"); nb.clicked.connect(regen); cb = QPushButton("Kopiuj"); cb.clicked.connect(lambda: copy_secret(out.text()))
    g.addWidget(out, 1); g.addWidget(ln); g.addWidget(nb); g.addWidget(cb); l.addLayout(g)
    l.addSpacing(14); l.addWidget(lbl("Jednorazowe aliasy e-mail", "h3"))
    has_ddg = bool(v and v.data.get("ddg"))
    l.addWidget(lbl(("DuckDuckGo: połączono – aliasy @duck.com przekazują pocztę na Twoją skrzynkę i ukrywają prawdziwy adres."
                     if has_ddg else
                     "DuckDuckGo: niepołączono. Kliknij „Połącz DuckDuckGo”, zaloguj się w karcie i raz kliknij "
                     "„Generate Private Duck Address” – Luna zapamięta sesję. Do tego czasu Luna tworzy aliasy z plusem "
                     "(adres+strona@…), które pozwalają odfiltrować spam i wykryć wyciek."), "muted", wrap=True))
    row2 = QHBoxLayout(); row2.setSpacing(6)
    ddg = QPushButton("Rozłącz DuckDuckGo" if has_ddg else "Połącz DuckDuckGo")

    def ddg_act():
        if has_ddg:
            v.data["ddg"] = ""; v.save(); ddg.setText("Połącz DuckDuckGo")
        else:
            b.open_url_new_tab("https://duckduckgo.com/email/"); dlg.close()
    ddg.clicked.connect(ddg_act); row2.addWidget(ddg)
    base = QLineEdit(st.settings.get("alias_base", "")); base.setObjectName("glassin")
    base.setPlaceholderText("Adres do aliasów z plusem (np. ty@gmail.com)")
    base.editingFinished.connect(lambda: (st.settings.__setitem__("alias_base", base.text().strip()), st.save_soon()))
    row2.addWidget(base, 1); l.addLayout(row2)
    if VAULT and VAULT[0].available():
        imp = QPushButton("Importuj hasła, zakładki i historię z innej przeglądarki…")
        imp.clicked.connect(lambda: ImportDialog(dlg.browser).exec()); l.addSpacing(8); l.addWidget(imp, 0, Qt.AlignmentFlag.AlignLeft)
        l.addSpacing(14); leak_section(l, dlg)
        l.addSpacing(14); address_section(l, dlg)
    l.addStretch(1)
    return scroll_page(w)


def leak_section(l, dlg):
    """Sprawdzanie wycieków haseł (Have I Been Pwned, k-anonimowość: wysyłane jest 5 znaków skrótu SHA-1)."""
    l.addWidget(lbl("Wycieki haseł", "h3"))
    l.addWidget(lbl("Sprawdza, czy zapisane hasła pojawiły się w znanych wyciekach danych. Do serwisu Have I Been Pwned "
                    "trafia tylko 5 pierwszych znaków skrótu SHA-1 każdego hasła – nigdy samo hasło ani jego pełny skrót "
                    "(tak samo działa to w Firefoksie i Chrome).", "muted", wrap=True))
    out = lbl("", "muted2", wrap=True); l.addWidget(out)
    lst = QListWidget(); lst.setObjectName("wlist"); lst.setMaximumHeight(130); lst.viewport().setAutoFillBackground(False)
    lst.hide(); l.addWidget(lst)
    bt = QPushButton("Sprawdź wycieki haseł"); l.addWidget(bt, 0, Qt.AlignmentFlag.AlignLeft)

    def run():
        logins = [x for x in VAULT[0].logins() if x.get("pw")]
        if not logins:
            out.setText("Nie ma zapisanych haseł."); return
        bt.setEnabled(False); out.setText(f"Sprawdzam {len(logins)} haseł…"); lst.clear(); lst.hide()
        hashes = {}
        for x in logins:
            hashes.setdefault(hashlib.sha1(x["pw"].encode("utf-8")).hexdigest().upper(), []).append(x)
        prefixes = sorted({h[:5] for h in hashes})
        state = {"left": len(prefixes), "bad": [], "err": 0}

        def done_one():
            state["left"] -= 1
            if state["left"] > 0:
                return
            try:
                bt.setEnabled(True)
                if state["err"] and not state["bad"]:
                    out.setText("Nie udało się połączyć z Have I Been Pwned."); return
                if not state["bad"]:
                    out.setText(f"Żadne z {len(logins)} haseł nie występuje w znanych wyciekach."); return
                out.setText(f"Hasła z wycieków: {len(state['bad'])} – zmień je jak najszybciej:")
                for x, n in sorted(state["bad"], key=lambda t: -t[1]):
                    lst.addItem(f"{host_of(x['origin']) or x['origin']}  ·  {x['user']}  ·  w wyciekach {n:,} razy".replace(",", " "))
                lst.show()
            except RuntimeError:
                pass

        for pre in prefixes:
            def got(data, err, status, pre=pre):
                if status != 200 or not data:
                    state["err"] += 1
                else:
                    seen = {}
                    for ln in data.decode("ascii", "ignore").splitlines():
                        suf, _, cnt = ln.strip().partition(":")
                        if cnt.isdigit() and int(cnt) > 0:
                            seen[pre + suf.upper()] = int(cnt)
                    for h, xs in hashes.items():
                        if h.startswith(pre) and h in seen:
                            state["bad"] += [(x, seen[h]) for x in xs]
                done_one()
            dlg.store.http(f"https://api.pwnedpasswords.com/range/{pre}", got, headers={"Add-Padding": "true"},
                           timeout=20000, raw=True)
    bt.clicked.connect(run)


def address_section(l, dlg):
    """Adresy do autouzupełniania formularzy (zaszyfrowane razem z hasłami)."""
    l.addWidget(lbl("Adresy do formularzy", "h3"))
    l.addWidget(lbl("Luna zaproponuje wypełnienie formularza adresu (zakupy, dostawy); także z prawego przycisku w polu "
                    "tekstowym → Wypełnij adres. Dane są szyfrowane na tym komputerze jak hasła.", "muted", wrap=True))
    lst = QListWidget(); lst.setObjectName("wlist"); lst.setMaximumHeight(110); lst.viewport().setAutoFillBackground(False)
    l.addWidget(lst)

    def fill():
        lst.clear()
        for a in addresses():
            lst.addItem(f"{a.get('label') or 'Adres'}  ·  {a.get('first', '')} {a.get('last', '')}, {a.get('street', '')}, "
                        f"{a.get('postal', '')} {a.get('city', '')}")
    fill()
    row = QHBoxLayout(); row.setSpacing(6)

    def edit(i=None):
        cur = dict(addresses()[i]) if i is not None else {"country": "Polska"}
        d = QDialog(dlg); d.setWindowTitle("Adres"); f = QVBoxLayout(d); edits = {}
        for key, name in [("label", "Nazwa (np. Dom, Praca)")] + ADDR_FIELDS:
            f.addWidget(lbl(name, "muted2")); e = QLineEdit(cur.get(key, "")); f.addWidget(e); edits[key] = e
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Zapisz"); bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Anuluj")
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); f.addWidget(bb)
        if d.exec() == QDialog.DialogCode.Accepted:
            new = {k: e.text().strip() for k, e in edits.items()}
            lst_ = addresses()
            if i is None:
                lst_.append(new)
            else:
                lst_[i] = new
            VAULT[0].save(); fill()
    for text, fn in (("Dodaj adres", lambda: edit()),
                     ("Edytuj", lambda: lst.currentRow() >= 0 and edit(lst.currentRow())),
                     ("Usuń", lambda: lst.currentRow() >= 0 and (addresses().pop(lst.currentRow()), VAULT[0].save(), fill()))):
        b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
    row.addStretch(1); l.addLayout(row)


@settings_page("updates", "Aktualizacje")
def page_updates(dlg):
    w, l = page_box("Aktualizacje", "Luna aktualizuje się z repozytorium na GitHubie: pobiera nowe zmiany i uruchamia się "
                                    "ponownie z tymi samymi kartami.")
    st, up = dlg.store, updater()
    name, desc, _ = FEATURES["updates"]
    l.addWidget(switch_row(name, desc, st.feature("updates"), lambda v: st.set_feature("updates", v)))
    if not up.available():
        l.addWidget(lbl("Ta kopia Luny nie jest uruchomiona z repozytorium git (albo nie znaleziono programu git), "
                        "więc nie może się sama aktualizować.", "muted2", wrap=True))
        l.addStretch(1)
        return scroll_page(w)
    ver = up.version()
    l.addWidget(lbl("Bieżąca wersja: " + (ver or "nieznana"), "h3"))
    stat = lbl("", "muted2", wrap=True); l.addWidget(stat)
    row = QHBoxLayout(); row.setSpacing(6)
    chk = QPushButton("Sprawdź teraz"); upd = QPushButton("Zaktualizuj i uruchom ponownie"); upd.setObjectName("primary")
    login = QPushButton("Zaloguj do GitHuba")
    row.addWidget(chk); row.addWidget(upd); row.addWidget(login); row.addStretch(1); l.addLayout(row)
    l.addWidget(lbl("Repozytorium Luny jest prywatne, więc sprawdzanie wymaga jednorazowego logowania do GitHuba. "
                    "„Zaloguj do GitHuba” otwiera bezpieczne logowanie Git Credential Manager w przeglądarce; dane "
                    "logowania przechowuje Windows (Menedżer poświadczeń), nie Luna.", "muted", wrap=True))

    def show(s=None):
        s = s or up.state
        try:
            upd.setVisible(bool(s.get("behind")) and not s.get("dirty"))
            login.setVisible(s.get("auth") is False)
            chk.setEnabled(not up.busy)
            if up.busy:
                stat.setText("Sprawdzanie…")
            elif not s:
                stat.setText("Jeszcze nie sprawdzano w tej sesji.")
            elif s.get("error"):
                stat.setText("Nie udało się sprawdzić: " + s["error"] + ".")
            elif s.get("behind"):
                ch = "".join("\n• " + c for c in s.get("changes", [])[:5])
                stat.setText(f"Dostępna nowa wersja: {s['behind']} zm.{ch}"
                             + ("\nW folderze Luny są niezapisane zmiany – zaktualizuj przez GitHub Desktop." if s.get("dirty") else ""))
            else:
                stat.setText("Masz najnowszą wersję (sprawdzono " + datetime.fromtimestamp(s["checked"]).strftime("%H:%M") + ").")
        except RuntimeError:
            safe_disconnect(up.result, show)

    def run(interactive=False):
        up.check(interactive=interactive); show()
    chk.clicked.connect(lambda: run(False)); login.clicked.connect(lambda: run(True))
    upd.clicked.connect(lambda: (dlg.accept(), dlg.browser.apply_update()))
    up.result.connect(show)
    w.destroyed.connect(lambda _=None: safe_disconnect(up.result, show))
    show()
    l.addStretch(1)
    return scroll_page(w)


@settings_page("sync", "Synchronizacja")
def page_sync(dlg):
    w, l = page_box("Synchronizacja między komputerami", "Kafelki, zakładki, zakreślenia, „Do przeczytania”, hasła, adresy, "
                    "ustawienia i otwarte karty – przez folder synchronizowany z chmurą (OneDrive, Dysk Google, Dropbox). "
                    "Dane są zaszyfrowane hasłem synchronizacji, zanim trafią do folderu – usługa chmurowa widzi tylko szyfr.")
    st = dlg.store
    if not SYNC:
        SYNC.append(SyncManager(st))
    sm = SYNC[0]; c = sm.cfg()
    if not (VAULT and VAULT[0].available()):
        l.addWidget(lbl("Synchronizacja wymaga sejfu haseł (Windows).", "muted2", wrap=True)); l.addStretch(1)
        return scroll_page(w)
    on = QCheckBox("Synchronizuj ten komputer"); on.setChecked(bool(c.get("on"))); l.addWidget(on)
    l.addWidget(lbl("Folder (ten sam na wszystkich komputerach)", "h3"))
    row = QHBoxLayout(); fe = QLineEdit(c.get("folder", "")); fe.setObjectName("glassin"); fe.setReadOnly(True)
    pick = QPushButton("Wybierz…"); row.addWidget(fe, 1); row.addWidget(pick); l.addLayout(row)
    od = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if od and not c.get("folder"):
        l.addWidget(lbl(f"Podpowiedź: Twój OneDrive to {od}", "muted", wrap=True))

    def choose():
        d = QFileDialog.getExistingDirectory(dlg, "Folder synchronizacji", c.get("folder") or od or str(HOME))
        if d:
            c["folder"] = d; fe.setText(d); st.save_soon(); restart()
    pick.clicked.connect(choose)
    l.addWidget(lbl("Hasło synchronizacji", "h3"))
    l.addWidget(lbl("Takie samo na każdym komputerze. Zapisane w sejfie haseł tego komputera.", "muted", wrap=True))
    pw = QPushButton("Zmień hasło…" if sm.password() else "Ustaw hasło…"); l.addWidget(pw, 0, Qt.AlignmentFlag.AlignLeft)

    def set_pw():
        a, ok = QInputDialog.getText(dlg, "Hasło synchronizacji", "Hasło (min. 8 znaków):", QLineEdit.EchoMode.Password)
        if not ok:
            return
        if len(a) < 8:
            QMessageBox.warning(dlg, "Synchronizacja", "Hasło musi mieć co najmniej 8 znaków."); return
        b_, ok = QInputDialog.getText(dlg, "Hasło synchronizacji", "Powtórz hasło:", QLineEdit.EchoMode.Password)
        if not ok or a != b_:
            QMessageBox.warning(dlg, "Synchronizacja", "Hasła się różnią."); return
        VAULT[0].data["sync_pw"] = a; VAULT[0].save(); pw.setText("Zmień hasło…"); restart()
    pw.clicked.connect(set_pw)
    l.addWidget(lbl("Nazwa tego komputera", "h3"))
    ne = QLineEdit(c.get("name", "")); ne.setObjectName("glassin"); l.addWidget(ne)
    ne.editingFinished.connect(lambda: (c.__setitem__("name", ne.text().strip()[:40] or "Komputer"), st.save_soon()))
    stat = lbl("", "muted2", wrap=True); l.addWidget(stat)
    now_b = QPushButton("Synchronizuj teraz"); l.addWidget(now_b, 0, Qt.AlignmentFlag.AlignLeft)

    def show():
        try:
            if not c.get("on"):
                stat.setText("Wyłączona."); return
            missing = [x for x, ok in (("folder", c.get("folder") and os.path.isdir(c["folder"])), ("hasło", sm.password())) if not ok]
            if missing:
                stat.setText("Brakuje: " + ", ".join(missing) + "."); return
            f = lambda ts: datetime.fromtimestamp(ts).strftime("%d.%m %H:%M") if ts else "—"
            others = ", ".join(f"{n} ({f(t_)})" for n, t_, _ in sm.other_tabs()) or "jeszcze żaden"
            stat.setText(f"Wysłano: {f(c.get('last_write'))} · odebrano: {f(c.get('last_read'))} · inne komputery: {others}"
                         + (f"\n{sm.error}" if sm.error else ""))
        except RuntimeError:
            safe_disconnect(sm.changed, show)

    def restart():
        c["on"] = on.isChecked(); st.save_soon(); sm.start(); show()
    on.toggled.connect(lambda _: restart())
    now_b.clicked.connect(lambda: (sm.read_all(), sm.write(), show()))
    sm.changed.connect(show); w.destroyed.connect(lambda _=None: safe_disconnect(sm.changed, show))
    show(); l.addStretch(1)
    return scroll_page(w)


_ORDER = ["features", "tabs", "privacy", "passwords", "sync", "look", "keys", "updates"]
SETTINGS_PAGES.sort(key=lambda p: _ORDER.index(p[0]))


class DragBar(QWidget):
    def __init__(self):
        super().__init__(); self.setObjectName("setHead")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def mousePressEvent(self, ev):
        h = self.window().windowHandle()
        if ev.button() == Qt.MouseButton.LeftButton and h:
            h.startSystemMove()


ROW_SUB = Qt.ItemDataRole.UserRole + 1      # druga (szara) linia wiersza
ROW_SIDE = Qt.ItemDataRole.UserRole + 2     # krótki tekst po prawej (godzina, rozmiar, stan)
ROW_HEAD = Qt.ItemDataRole.UserRole + 3     # nagłówek grupy (dzień, strona)
ROW_PROG = Qt.ItemDataRole.UserRole + 4     # pasek postępu 0…1 (pobieranie)
ROW_INDENT = Qt.ItemDataRole.UserRole + 5   # wcięcie w pikselach (wiersze podrzędne)


def _font_step(f, n=1):
    f = QFont(f)
    if f.pixelSize() > 0:
        f.setPixelSize(max(9, f.pixelSize() - n))
    elif f.pointSizeF() > 0:
        f.setPointSizeF(max(7.0, f.pointSizeF() - n * 0.75))
    return f


class RowDelegate(QStyledItemDelegate):
    """Wspólny wygląd wierszy list w oknach Luny: ikona w zaokrąglonym kafelku, tytuł, szara druga linia,
    tekst po prawej, opcjonalny pasek postępu; nagłówki grup małymi literami kapitalikami."""

    def sizeHint(self, opt, idx):
        if idx.data(ROW_HEAD):
            return QSize(0, 34)
        return QSize(0, 54 if idx.data(ROW_SUB) else 40)

    def paint(self, p, opt, idx):
        p.save(); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(Qt.PenStyle.NoPen)
        r = QRectF(opt.rect).adjusted(2, 1, -2, -1); title = idx.data(Qt.ItemDataRole.DisplayRole) or ""
        if idx.data(ROW_HEAD):
            f = _font_step(opt.font, 2); f.setBold(True); f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
            p.setFont(f); p.setPen(QColor("#7d7d7d"))
            p.drawText(r.adjusted(12, 8, -12, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title.upper())
            p.restore(); return
        S = QStyle.StateFlag
        sel, hov = bool(opt.state & S.State_Selected), bool(opt.state & S.State_MouseOver)
        if sel or hov:
            p.setBrush(QColor("#2a2a2a" if sel else "#1a1a1a")); p.drawRoundedRect(r, 9, 9)
        x = r.left() + 10 + (idx.data(ROW_INDENT) or 0)
        ic = idx.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(ic, QIcon) and not ic.isNull():
            tile = QRectF(x, r.center().y() - 15, 30, 30)
            p.setBrush(QColor("#333333" if sel else "#1e1e1e")); p.drawRoundedRect(tile, 8, 8)
            ic.paint(p, tile.adjusted(7, 7, -7, -7).toRect()); x += 42
        right = r.right() - 12; side = idx.data(ROW_SIDE) or ""
        small = _font_step(opt.font, 1); sm = QFontMetrics(small)
        if side:
            sw = sm.horizontalAdvance(side) + 2
            p.setFont(small); p.setPen(QColor("#8c8c8c"))
            p.drawText(QRectF(right - sw, r.top(), sw, r.height()), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, side)
            right -= sw + 16
        tf = QFont(opt.font); ff = idx.data(Qt.ItemDataRole.FontRole)
        if isinstance(ff, QFont):
            tf.setBold(ff.bold())
        fg = idx.data(Qt.ItemDataRole.ForegroundRole)
        col = fg.color() if isinstance(fg, QBrush) else (fg if isinstance(fg, QColor) else QColor("#ffffff" if sel else "#e4e4e4"))
        fm = QFontMetrics(tf); w = max(10.0, right - x); sub = idx.data(ROW_SUB) or ""
        p.setFont(tf); p.setPen(col)
        el = Qt.TextElideMode.ElideRight; L = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        if sub:
            y = r.center().y() - (fm.height() + 2 + sm.height()) / 2
            p.drawText(QRectF(x, y, w, fm.height()), L, fm.elidedText(title, el, int(w)))
            p.setFont(small); p.setPen(QColor("#9a9a9a" if sel else "#858585"))
            p.drawText(QRectF(x, y + fm.height() + 2, w, sm.height()), L, sm.elidedText(sub, el, int(w)))
        else:
            p.drawText(QRectF(x, r.top(), w, r.height()), L, fm.elidedText(title, el, int(w)))
        prog = idx.data(ROW_PROG)
        if prog is not None:
            bw = r.right() - 12 - x; bar = QRectF(x, r.bottom() - 6, bw, 3)
            p.setBrush(QColor("#2a2a2a")); p.drawRoundedRect(bar, 1.5, 1.5)
            p.setBrush(QColor("#ececec")); p.drawRoundedRect(QRectF(x, bar.top(), bw * max(0.0, min(1.0, prog)), 3), 1.5, 1.5)
        p.restore()


def row_list(multi=False):
    """Lista w stylu okien Luny (wiersze RowDelegate)."""
    lst = QListWidget(); lst.setObjectName("histlist"); lst.viewport().setAutoFillBackground(False)
    lst.setItemDelegate(RowDelegate(lst)); lst.setMouseTracking(True); lst.setUniformItemSizes(False)
    lst.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    lst.setFrameShape(QFrame.Shape.NoFrame)
    if multi:
        lst.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    return lst


def row_item(title, sub="", side="", icon=None, data=None, tip="", indent=0):
    it = QListWidgetItem(title)
    if icon is not None:
        it.setIcon(icon)
    if sub:
        it.setData(ROW_SUB, sub)
    if side:
        it.setData(ROW_SIDE, side)
    if indent:
        it.setData(ROW_INDENT, indent)
    if data is not None:
        it.setData(Qt.ItemDataRole.UserRole, data)
    if tip:
        it.setToolTip(tip)
    return it


def head_item(text):
    it = QListWidgetItem(text); it.setData(ROW_HEAD, True); it.setFlags(Qt.ItemFlag.NoItemFlags)
    return it


class EmptyState(QWidget):
    """Pusty stan listy: ikona w kółku, tytuł i podpowiedź, co zrobić."""

    def __init__(self, kind, title, hint=""):
        super().__init__()
        v = QVBoxLayout(self); v.setContentsMargins(28, 28, 28, 28); v.setSpacing(4); v.addStretch(1)
        ring = QLabel(); ring.setObjectName("emptyicon"); ring.setFixedSize(56, 56); ring.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ring.setPixmap(glyph(kind, "#8c8c8c").pixmap(26, 26)); v.addWidget(ring, 0, Qt.AlignmentFlag.AlignHCenter); v.addSpacing(10)
        self.t = lbl(title, "h3"); self.t.setAlignment(Qt.AlignmentFlag.AlignCenter); v.addWidget(self.t)
        self.h = lbl(hint, "muted2", wrap=True); self.h.setAlignment(Qt.AlignmentFlag.AlignCenter); v.addWidget(self.h)
        self.h.setVisible(bool(hint)); v.addStretch(2)

    def set_text(self, title, hint=""):
        self.t.setText(title); self.h.setText(hint); self.h.setVisible(bool(hint))


class LunaDialog(QDialog):
    """Wspólny wygląd okien Luny (historia, pobrane, menedżer zadań, kopia, import…): bez systemowej ramki, ciemny
    nagłówek do przeciągania z ikoną, tytułem, opcjonalnym polem (np. wyszukiwarką) i krzyżykiem; pod nim opis, treść
    i przyciski na dole (główny – jasny). Esc zamyka; róg w prawym dolnym rogu zmienia rozmiar."""

    def __init__(self, parent, title, icon=None, size=(640, 520), subtitle="", modal=True):
        super().__init__(parent)
        self.setObjectName("settings"); self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True); self.setModal(modal)
        self.resize(fit_size(*size)); self.setMinimumSize(fit_size(min(size[0], 440), min(size[1], 260), 0.8))
        root = QVBoxLayout(self); root.setContentsMargins(1, 1, 1, 1); root.setSpacing(0)
        bar = DragBar(); self.head = QHBoxLayout(bar); self.head.setContentsMargins(18, 8, 8, 8); self.head.setSpacing(8)
        if icon is not None:
            ic = QLabel(); ic.setFixedSize(20, 20)
            ic.setPixmap(glyph(icon, "#ececec").pixmap(20, 20) if isinstance(icon, str) else icon)
            self.head.addWidget(ic); self.head.addSpacing(2)
        self.title_lbl = lbl(title, "h1"); self.head.addWidget(self.title_lbl); self.head.addSpacing(10)
        self.head.addStretch(1); self._sp = self.head.itemAt(self.head.count() - 1)
        self.xbtn = QToolButton(); self.xbtn.setIcon(glyph("close")); self.xbtn.setIconSize(QSize(20, 20)); self.xbtn.setFixedSize(32, 32)
        self.xbtn.setToolTip("Zamknij (Esc)"); self.xbtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.xbtn.clicked.connect(self.reject); self.head.addWidget(self.xbtn); root.addWidget(bar)
        self.body = QVBoxLayout(); self.body.setContentsMargins(20, 14, 20, 16); self.body.setSpacing(10)
        self.sub = lbl(subtitle, "muted2", wrap=True); self.body.addWidget(self.sub); self.sub.setVisible(bool(subtitle))
        root.addLayout(self.body, 1)
        self.grip = QSizeGrip(self); self.grip.setFixedSize(16, 16)

    def resizeEvent(self, ev):
        super().resizeEvent(ev); self.grip.move(self.width() - 17, self.height() - 17); self.grip.raise_()

    def head_widget(self, w, fill=False):
        """Pole w nagłówku przed krzyżykiem (fill – zajmuje wolne miejsce, np. wyszukiwarka)."""
        if fill and self._sp is not None:
            self.head.removeItem(self._sp); self._sp = None
        self.head.insertWidget(self.head.indexOf(self.xbtn), w, 1 if fill else 0)
        return w

    def panel(self, widget, empty_kind="app", empty_title="", empty_hint=""):
        """Lista / drzewo w zaokrąglonym panelu z pustym stanem (show_empty)."""
        fr = QFrame(); fr.setObjectName("dlgpanel"); lay = QVBoxLayout(fr); lay.setContentsMargins(6, 6, 6, 6)
        self._pstack = QStackedWidget(); self._pstack.setObjectName("clear")
        self.empty = EmptyState(empty_kind, empty_title, empty_hint)
        self._pstack.addWidget(widget); self._pstack.addWidget(self.empty); lay.addWidget(self._pstack)
        self.body.addWidget(fr, 1)
        return fr

    def show_empty(self, on, title=None, hint=None):
        if title is not None:
            self.empty.set_text(title, hint or "")
        self._pstack.setCurrentIndex(1 if on else 0)

    def section(self, text):
        w = lbl(text.upper(), "seclabel"); self.body.addWidget(w)
        return w

    def footer(self, left=(), right=()):
        """Przyciski na dole: (tekst, funkcja[, główny]) albo gotowy widżet; lewa grupa, odstęp, prawa grupa."""
        row = QHBoxLayout(); row.setSpacing(8); out = []
        for i, group in enumerate((left, right)):
            if i:
                row.addStretch(1)
            for spec in group:
                if isinstance(spec, QWidget):
                    row.addWidget(spec); continue
                b = QPushButton(spec[0]); b.setCursor(Qt.CursorShape.PointingHandCursor)
                if len(spec) > 2 and spec[2]:
                    b.setObjectName("primary")
                b.clicked.connect(lambda _=False, f=spec[1]: f()); row.addWidget(b); out.append(b)
        if not right:
            row.addStretch(1)
        self.body.addLayout(row)
        return out


def luna_confirm(parent, title, text, yes="Tak", icon="help"):
    """Pytanie w stylu Luny (zamiast systemowego okienka)."""
    d = LunaDialog(parent, title, icon, (460, 210))
    d.sub.setText(text); d.sub.setVisible(True); d.body.addStretch(1)
    d.footer(right=[("Anuluj", d.reject), (yes, d.accept, True)])
    return d.exec() == QDialog.DialogCode.Accepted


def luna_prompt(parent, title, label, text="", icon="edit"):
    """Pole tekstowe w stylu Luny (zamiast systemowego okienka); zwraca tekst albo None."""
    d = LunaDialog(parent, title, icon, (480, 230))
    d.sub.setText(label); d.sub.setVisible(True)
    e = QLineEdit(text); e.setObjectName("glassin"); e.selectAll(); d.body.addWidget(e); d.body.addStretch(1)
    ok, = d.footer(right=[("Anuluj", d.reject), ("Zapisz", d.accept, True)])[1:]
    e.returnPressed.connect(d.accept); ok.setEnabled(bool(text.strip()))
    e.textChanged.connect(lambda s: ok.setEnabled(bool(s.strip())))
    e.setFocus()
    return e.text().strip() if d.exec() == QDialog.DialogCode.Accepted and e.text().strip() else None


def human_size(n):
    if not n or n < 0:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024


class AboutDialog(LunaDialog):
    """O Lunie: logo, wersja silnika, linki."""

    def __init__(self, browser):
        super().__init__(browser, "O Lunie", "help", (460, 360))
        from PyQt6.QtWebEngineCore import qWebEngineChromiumVersion
        self.body.addStretch(1)
        lg = QLabel(); lg.setPixmap(logo_pixmap(64)); lg.setFixedSize(64, 64); self.body.addWidget(lg, 0, Qt.AlignmentFlag.AlignHCenter)
        t = lbl("Luna", "h1"); t.setAlignment(Qt.AlignmentFlag.AlignCenter); self.body.addWidget(t)
        for text, cls in (("Lekka przeglądarka z kafelkami, widgetami, blokadą reklam i asystentem AI.", "muted2"),
                          (f"Silnik: Chromium {qWebEngineChromiumVersion()} (Qt WebEngine)", "muted")):
            l_ = lbl(text, cls, wrap=True); l_.setAlignment(Qt.AlignmentFlag.AlignCenter); self.body.addWidget(l_)
        self.body.addStretch(1)
        self.footer(left=[("Polityka prywatności", lambda: (browser.open_url_new_tab(PRIVACY_URL), self.accept())),
                          ("Skróty klawiszowe", lambda: (self.accept(), browser.open_settings("keys")))],
                    right=[("OK", self.accept, True)])


class SettingsDialog(QDialog):
    def __init__(self, store, host, browser):
        super().__init__(browser)
        self.store, self.host, self.browser, self.built = store, host, browser, {}
        self.setObjectName("settings"); self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setModal(True); self.resize(fit_size(940, 640)); self.setMinimumSize(fit_size(660, 460, 0.8))
        root = QVBoxLayout(self); root.setContentsMargins(1, 1, 1, 1); root.setSpacing(0)
        bar = DragBar(); bl = QHBoxLayout(bar); bl.setContentsMargins(18, 8, 8, 8)
        lg = QLabel(); lg.setPixmap(logo_pixmap(20)); lg.setFixedSize(20, 20)
        bl.addWidget(lg); bl.addSpacing(6); bl.addWidget(lbl("Ustawienia", "h1")); bl.addStretch()
        x = QToolButton(); x.setIcon(glyph("close")); x.setIconSize(QSize(22, 22)); x.setFixedSize(32, 32); x.clicked.connect(self.accept)
        bl.addWidget(x); root.addWidget(bar)
        body = QHBoxLayout(); body.setSpacing(0); body.setContentsMargins(0, 0, 0, 0)
        self.nav = QListWidget(); self.nav.setObjectName("nav"); self.nav.setFixedWidth(190)
        for pid, title, _ in SETTINGS_PAGES:
            it = QListWidgetItem(title); it.setData(Qt.ItemDataRole.UserRole, pid); self.nav.addItem(it)
        self.stack = QStackedWidget(); self.stack.setObjectName("clear")
        body.addWidget(self.nav); body.addWidget(self.stack, 1); root.addLayout(body, 1)
        self.nav.currentRowChanged.connect(lambda r: self.show_page(self.nav.item(r).data(Qt.ItemDataRole.UserRole)) if r >= 0 else None)
        self.nav.setCurrentRow(0)

    def show_page(self, pid):
        if pid not in self.built:   # strony budowane leniwie – dopiero przy pierwszym wejściu
            for p, title, fn in SETTINGS_PAGES:
                if p == pid:
                    w = fn(self); self.built[pid] = w; self.stack.addWidget(w)
        self.stack.setCurrentWidget(self.built[pid])
        for i in range(self.nav.count()):
            if self.nav.item(i).data(Qt.ItemDataRole.UserRole) == pid and self.nav.currentRow() != i:
                self.nav.setCurrentRow(i)


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
        self.anim.setEasingCurve(QEasingCurve.Type.InOutSine)   # przenikanie podpisu bez „skoku” jasności
        self.anim.finished.connect(self._step)
        self.timer = QTimer(self); self.timer.timeout.connect(self.next)

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

    def showEvent(self, ev):
        self.timer.start(9000); super().showEvent(ev)

    def hideEvent(self, ev):
        self.timer.stop(); super().hideEvent(ev)

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


# ======================================================================================
#  INTELIGENTNY PASEK WYSZUKIWANIA (podpowiedzi: sieć + historia + kafelki + otwarte karty)
# ======================================================================================
SUGGEST_URLS = {   # punkty podpowiedzi wybranej wyszukiwarki; pozostałe używają DuckDuckGo (prywatnie)
    "Google": "https://suggestqueries.google.com/complete/search?client=chrome&q=",
    "DuckDuckGo": "https://duckduckgo.com/ac/?type=list&q=",
    "Brave": "https://search.brave.com/api/suggest?q=",
    "Bing": "https://api.bing.com/osjson.aspx?query=",
}
_GPIX = {}


def gpix(kind, color="#9a9a9a"):
    if (kind, color) not in _GPIX:
        _GPIX[(kind, color)] = glyph(kind, color).pixmap(16, 16)
    return _GPIX[(kind, color)]


class SuggestDelegate(QStyledItemDelegate):
    """Rysuje wiersz: ikona typu, tekst (skracany) i wskazówka po prawej – bez widgetów-wierszy (lekko)."""
    ROW = 36

    def sizeHint(self, opt, idx):
        return QSize(opt.rect.width(), self.ROW)

    def paint(self, p, opt, idx):
        d = idx.data(Qt.ItemDataRole.UserRole) or {}
        p.save(); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(opt.rect).adjusted(3, 1, -3, -1)
        if opt.state & QStyle.StateFlag.State_Selected:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(255, 255, 255, 34)); p.drawRoundedRect(r, 9, 9)
        elif opt.state & QStyle.StateFlag.State_MouseOver:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(255, 255, 255, 16)); p.drawRoundedRect(r, 9, 9)
        p.drawPixmap(int(r.left() + 10), int(r.center().y() - 8), gpix(d.get("icon", "search")))
        hint = d.get("hint", ""); fm = opt.fontMetrics
        hw = fm.horizontalAdvance(hint) + 6 if hint else 0
        tr = QRectF(r.left() + 36, r.top(), max(20.0, r.width() - 36 - hw - 14), r.height())
        p.setPen(QColor("#ececec"))
        p.drawText(tr, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   fm.elidedText(d.get("text", ""), Qt.TextElideMode.ElideRight, int(tr.width())))
        if hint:
            p.setPen(QColor("#7d7d85"))
            p.drawText(QRectF(r.right() - hw - 10, r.top(), hw, r.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, hint)
        p.restore()


class SuggestPopup(QFrame):
    """Okno podpowiedzi: zaokrąglone, z miękkim cieniem; nie przejmuje fokusu, więc pisanie nie jest przerywane."""
    activated = pyqtSignal(dict)

    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.owner = None
        self.setObjectName("sugg_popup"); self.setWindowTitle("Luna")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating); self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if sys.platform == "win32":   # bez systemowej animacji pojawiania się (na Windows miga wtedy czarny prostokąt);
            try:                      # dopiero po WA_TranslucentBackground – wcześniejszy winId() daje czarne tło zamiast przezroczystego
                import ctypes
                ctypes.windll.dwmapi.DwmSetWindowAttribute(int(self.winId()), 3, ctypes.byref(ctypes.c_int(1)), 4)
            except Exception:
                pass
        outer = QVBoxLayout(self); outer.setContentsMargins(12, 2, 12, 18)
        self.card = QFrame(); self.card.setObjectName("sugg_card")
        sh = QGraphicsDropShadowEffect(self.card); sh.setBlurRadius(30); sh.setOffset(0, 8); sh.setColor(QColor(0, 0, 0, 175))
        self.card.setGraphicsEffect(sh)
        cl = QVBoxLayout(self.card); cl.setContentsMargins(6, 6, 6, 6)
        self.list = QListWidget(); self.list.setObjectName("sugg_list"); self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setItemDelegate(SuggestDelegate(self.list)); self.list.setMouseTracking(True)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.viewport().setAutoFillBackground(False)
        self.list.itemClicked.connect(lambda it: self.activated.emit(it.data(Qt.ItemDataRole.UserRole)))
        cl.addWidget(self.list); outer.addWidget(self.card)

    def set_entries(self, entries):
        self.list.clear()
        for e in entries:
            it = QListWidgetItem(e["text"]); it.setData(Qt.ItemDataRole.UserRole, e); self.list.addItem(it)
        self.list.setFixedHeight(len(entries) * SuggestDelegate.ROW + 4)
        self.list.setCurrentRow(-1)

    def move_sel(self, d):
        n = self.list.count(); cur = self.list.currentRow()
        if n:
            self.list.setCurrentRow((cur + d) % n if cur >= 0 else (0 if d > 0 else n - 1))

    def current(self):
        it = self.list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it is not None and self.list.currentRow() >= 0 else None

    def show_below(self, edit):
        self.setFixedWidth(edit.width() + 24); self.adjustSize()
        self.move(edit.mapToGlobal(QPoint(-12, edit.height() - 2)))
        if not self.isVisible():
            self.show()
        self.raise_()


class SuggestController(QObject):
    """Podpowiedzi pod polem tekstowym. Sieć: zapytanie dopiero po 250 ms ciszy (debounce), poprzednie jest przerywane;
    historia, kafelki i otwarte karty są filtrowane lokalnie (natychmiast, bez sieci). Strzałki / Enter / Esc działają."""

    def __init__(self, edit, browser):
        super().__init__(edit)
        self.edit, self.br, self.store = edit, browser, browser.store
        self.net, self.seq, self.reply = [], 0, None
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.fetch_net)
        # chowanie z opóźnieniem: przy pisaniu lista bywa na chwilę pusta (zanim przyjdą podpowiedzi z sieci) –
        # bez tego okienko znikało i wracało przy każdej literze (mignięcie)
        self._hide_t = QTimer(self); self._hide_t.setSingleShot(True); self._hide_t.timeout.connect(self._hide_popup)
        edit.installEventFilter(self); edit.textEdited.connect(self.on_text)

    def _hide_popup(self):
        p = self.br._suggest
        if p is not None and p.owner is self:
            p.hide()

    @staticmethod
    def looks_like_url(t):
        return "://" in t or (" " not in t and "." in t)

    def visible(self):
        p = self.br._suggest
        return p is not None and p.isVisible() and p.owner is self

    def hide(self):
        self.timer.stop(); self._hide_t.stop(); self.abort(); self._hide_popup()

    def abort(self):
        self.seq += 1
        if self.reply is not None:
            try:
                self.reply.abort()
            except RuntimeError:
                pass
            self.reply = None

    def on_text(self, t):
        t = t.strip()
        if not t or not self.store.feature("suggest"):
            self.hide(); return
        self.abort(); self.net = [] if len(t) < 2 else self.net
        self.rebuild()
        if self.store.feature("suggest_net") and len(t) >= 2 and not self.looks_like_url(t):
            self.timer.start(250)    # debounce – zapytanie po 250 ms bez pisania

    def fetch_net(self):
        t = self.edit.text().strip()
        if not t or not self.store.feature("suggest") or not self.store.feature("suggest_net"):
            return
        self.seq += 1; n = self.seq
        app = app_match(t)
        if app is not None:
            if not app[2] or app[2][0] in "@#":
                return
            t = app[2]
        url = SUGGEST_URLS.get(CURRENT[0], SUGGEST_URLS["DuckDuckGo"]) + quote(t)
        self.reply = self.store.http(url, lambda j, e, s: self.got_net(n, j), timeout=6000)

    def got_net(self, n, j):
        try:
            if n != self.seq or not self.edit.hasFocus():
                return
            if isinstance(j, list) and len(j) > 1 and isinstance(j[1], list):
                self.net = [x for x in j[1][:6] if isinstance(x, str)]
                self.rebuild()
        except RuntimeError:     # pole zostało już usunięte (zamknięta karta)
            pass

    def entries(self, q):
        app = app_match(q)
        if app is not None:   # słowo kluczowe aplikacji: najpierw wyszukiwanie w niej, podpowiedzi też do niej
            name, url, aq = app
            out = [{"type": "url", "text": f"Szukaj w {name}: {aq}" if aq else f"Otwórz {name}", "hint": "Enter",
                    "icon": "search" if aq else "external", "url": url}]
            if aq and aq[0] not in "@#":
                key = q.split(None, 1)[0]
                for s in self.net[:7]:
                    if s.lower() != aq.lower():
                        out.append({"type": "url", "text": s, "hint": name, "icon": "search", "url": normalize(f"{key} {s}")})
            return out
        ql = q.lower(); out = [{"type": "go", "text": q, "hint": "Enter", "icon": "search"}]; urls = set()
        cur = self.br.stack.currentWidget(); tabs = 0
        for i in range(self.br.stack.count()):
            t = self.br.stack.widget(i); web = getattr(t, "web", None)
            if web is None or t is cur or tabs >= 2:
                continue
            title, url = web.title() or "", web.url().toString()
            if ql in title.lower() or ql in url.lower():
                out.append({"type": "tab", "text": title or url, "hint": "Karta", "icon": "tabs", "index": i})
                tabs += 1; urls.add(url)
        apps = 0
        for b in self.store.items:
            if apps < 2 and (ql in b["name"].lower() or ql in host_of(b["url"])):
                out.append({"type": "url", "text": b["name"], "hint": "Kafelek", "icon": "app", "url": b["url"]})
                apps += 1; urls.add(b["url"])
        hist = 0
        for h in self.store.history:
            if hist >= 4:
                break
            if h["url"] not in urls and (ql in h["name"].lower() or ql in h["url"].lower()):
                out.append({"type": "url", "text": h["name"] or h["url"], "hint": host_of(h["url"]), "icon": "history", "url": h["url"]})
                hist += 1
        for s in self.net:
            if s.lower() != ql and len(out) < 10:
                out.append({"type": "search", "text": s, "hint": CURRENT[0], "icon": "search"})
        return out

    def rebuild(self):
        q = self.edit.text().strip(); es = self.entries(q) if q else []
        if len(es) < 2:
            if self.visible() and q and not self._hide_t.isActive():
                self._hide_t.start(400)   # podpowiedzi z sieci zwykle zdążą – okienko zostaje bez mrugania
            elif not q:
                self._hide_popup()
            return
        self._hide_t.stop()
        p = self.br.suggest_popup(); p.owner = self; p.set_entries(es); p.show_below(self.edit)

    def choose(self, e):
        self.hide(); kind = e.get("type"); tab = self.br.cur()
        if kind == "tab":
            self.br.bar.setCurrentIndex(e["index"])
        elif kind == "url":
            tab.go(e["url"])
        elif kind == "search":
            tab.go(ENGINES[CURRENT[0]] + quote(e["text"]))
        elif not self.br.ai_login_link(self.edit.text()):
            tab.go(self.edit.text())
        if self.edit is not self.br.address:
            self.edit.clear()

    def eventFilter(self, obj, ev):
        if obj is not self.edit:
            return False
        t = ev.type()
        if t == QEvent.Type.FocusOut:
            self.hide()
        elif t == QEvent.Type.KeyPress and self.store.feature("suggest"):
            k = ev.key(); p = self.br._suggest
            if self.visible():
                if k == Qt.Key.Key_Down:
                    p.move_sel(1); return True
                if k == Qt.Key.Key_Up:
                    p.move_sel(-1); return True
                if k == Qt.Key.Key_Escape:
                    self.hide(); return True
                if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and p.current() is not None:
                    self.choose(p.current()); return True
            elif k == Qt.Key.Key_Down and self.edit.text().strip():
                self.rebuild(); return True
        return False


class HomePage(QWidget):
    opened = pyqtSignal(str)

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        outer = QHBoxLayout(self); outer.setContentsMargins(24, 0, 24, 0)
        content = QWidget(); content.setObjectName("clear"); content.setMaximumWidth(940)
        outer.addStretch(1); outer.addWidget(content, 100); outer.addStretch(1)
        lay = QVBoxLayout(content); lay.setContentsMargins(0, 26, 0, 14); lay.setSpacing(10)

        logo = QLabel(); logo.setPixmap(logo_pixmap(46)); logo.setFixedSize(46, 46)
        brand = QLabel("Luna"); brand.setObjectName("brand")
        brow = QHBoxLayout(); brow.setSpacing(12)
        brow.addStretch(); brow.addWidget(logo); brow.addWidget(brand); brow.addStretch()
        head = Caption()
        lay.addLayout(brow); lay.addWidget(head); lay.addSpacing(8)

        self.search = QLineEdit(); self.search.setObjectName("search")
        self.search.addAction(glyph("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.returnPressed.connect(self.do_search)
        self.search.setMaximumWidth(680); self.search.setMinimumWidth(320)   # szerokość dopasowana w resizeEvent
        lay.addWidget(self.search, 0, Qt.AlignmentFlag.AlignHCenter)

        center = lay
        top = QHBoxLayout()
        title = QLabel("Aplikacje"); title.setObjectName("h1")
        self.count = QLabel(); self.count.setObjectName("muted")
        add = gicon(QPushButton(), "plus", 18); add.setObjectName("round"); add.setFixedSize(34, 34); add.setToolTip("Dodaj aplikację")
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
        self.recent.itemClicked.connect(lambda it: it.data(Qt.ItemDataRole.UserRole) and self.opened.emit(it.data(Qt.ItemDataRole.UserRole)))
        center.addWidget(self.recent, 2)

        self.grid.viewport().setAutoFillBackground(False); self.recent.viewport().setAutoFillBackground(False)
        self._dirty = False
        self._rt = QTimer(self); self._rt.setSingleShot(True); self._rt.timeout.connect(self.refresh)
        self.store.changed.connect(self._soon)
        self.store.session.counts_changed.connect(self._soon)
        self.refresh()

    def _soon(self):
        """Odświeżanie kafelków tylko gdy strona jest widoczna; w tle jedynie znacznik „do odświeżenia”."""
        if self.isVisible():
            self._rt.start(120)
        else:
            self._dirty = True

    def attach_suggest(self, browser):
        self.sugg = SuggestController(self.search, browser)
        self.search.returnPressed.connect(lambda: self.sugg.hide())

    def showEvent(self, ev):
        super().showEvent(ev)
        if self._dirty:
            self.refresh()

    def refresh(self):
        self._dirty = False
        self.search.setPlaceholderText(f"Szukaj w {CURRENT[0]} lub wpisz adres…")
        n = len(self.store.items)
        self.count.setText(f"{n} {plural(n)}")
        self.grid.blockSignals(True); self.grid.clear()
        for b in self.store.items:
            it = QListWidgetItem(make_icon(b["name"], b["url"], self.store.session.count_for(b["url"])), b["name"])
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
        if not self.store.recent:
            it = QListWidgetItem("Tu pojawią się ostatnio odwiedzane strony."); it.setFlags(Qt.ItemFlag.NoItemFlags)
            it.setForeground(QColor("#6f6f6f")); self.recent.addItem(it)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)   # pole wyszukiwania: szerokie, ale z marginesem po bokach
        self.search.setFixedWidth(max(320, min(680, self.width() - 140)))

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


class DownloadManager(QObject):
    """Pobieranie plików ze wszystkich profili (także kontenerów i okien prywatnych) do folderu Pobrane."""
    started = pyqtSignal(str)
    changed = pyqtSignal()

    def __init__(self):
        super().__init__(QApplication.instance())   # żyje tak długo jak aplikacja (wszystkie okna)
        self.items = []

    def folder(self):
        from PyQt6.QtCore import QStandardPaths
        return QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation) or str(HOME)

    def on_request(self, req):
        try:   # kopia offline „Do przeczytania” – zapis do własnego folderu, bez listy pobranych
            if req.isSavePageDownload() and Path(req.downloadDirectory()).resolve() == OFFLINE_DIR.resolve():
                if req.state() == QWebEngineDownloadRequest.DownloadState.DownloadRequested:
                    req.accept()
                return
        except Exception:
            pass
        if req.state() != QWebEngineDownloadRequest.DownloadState.DownloadRequested:
            return
        req.setDownloadDirectory(self.folder())
        req.receivedBytesChanged.connect(self.changed); req.stateChanged.connect(lambda _: self.changed.emit())
        req.accept(); self.items.insert(0, req); del self.items[50:]
        self.started.emit(req.downloadFileName()); self.changed.emit()

    def path(self, req):
        return str(Path(req.downloadDirectory()) / req.downloadFileName())


DOWNLOADS = []


def show_in_folder(path):
    """Eksplorator z zaznaczonym plikiem (funkcja powłoki Windows – bez uruchamiania osobnego programu)."""
    p = Path(path)
    if sys.platform == "win32" and p.exists():
        try:
            import ctypes
            sh = ctypes.windll.shell32; sh.ILCreateFromPathW.restype = ctypes.c_void_p
            pidl = sh.ILCreateFromPathW(str(p))
            if pidl:
                try:
                    if sh.SHOpenFolderAndSelectItems(ctypes.c_void_p(pidl), 0, None, 0) == 0:
                        return
                finally:
                    sh.ILFree(ctypes.c_void_p(pidl))
        except Exception:
            pass
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent if p.exists() else p)))


def download_icon(frac=None, done=False):
    """Ikona pobierania: strzałka + pierścień postępu (frac 0..1); po zakończeniu – pełny pierścień i kropka."""
    S = 44; pm = QPixmap(S, S); pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#c9c9c9"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin); p.setPen(pen)
    p.drawLine(22, 12, 22, 27); p.drawPolyline(QPolygonF([QPointF(16, 21), QPointF(22, 27), QPointF(28, 21)])); p.drawLine(15, 32, 29, 32)
    r = QRectF(5, 5, 34, 34)
    if frac is not None or done:
        p.setPen(QPen(QColor("#2e2e2e"), 3)); p.drawEllipse(r)
        p.setPen(QPen(QColor("#ffffff"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(r, 90 * 16, -int(360 * 16 * (1.0 if done else max(0.03, min(1.0, frac or 0)))))
    p.end()
    return QIcon(pm)


class RegionPicker(QWidget):
    """Zaznaczanie fragmentu strony myszą na nieruchomym zrzucie (Esc – anuluj)."""
    picked = pyqtSignal(QPixmap)

    def __init__(self, pm, rect):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.pm, self.a, self.b = pm, None, None
        self.setGeometry(rect); self.setCursor(Qt.CursorShape.CrossCursor); self.setMouseTracking(True)

    def sel(self):
        return QRect(self.a, self.b).normalized() if self.a is not None and self.b is not None else QRect()

    def paintEvent(self, ev):
        p = QPainter(self); p.drawPixmap(self.rect(), self.pm)
        p.fillRect(self.rect(), QColor(0, 0, 0, 120)); s = self.sel()
        if not s.isEmpty():
            dpr = self.pm.devicePixelRatio()
            p.drawPixmap(s, self.pm, QRectF(s.x() * dpr, s.y() * dpr, s.width() * dpr, s.height() * dpr))
            p.setPen(QPen(QColor("#ffffff"), 1)); p.drawRect(s.adjusted(0, 0, -1, -1))
            p.setPen(QColor("#ffffff")); p.drawText(s.x() + 4, max(14, s.y() - 6), f"{s.width()} × {s.height()}")
        else:
            p.setPen(QColor("#e6e6e6")); p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                                                    "Zaznacz myszą fragment strony  ·  Esc – anuluj")
        p.end()

    def mousePressEvent(self, ev):
        self.a = self.b = ev.position().toPoint(); self.update()

    def mouseMoveEvent(self, ev):
        if self.a is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            self.b = ev.position().toPoint(); self.update()

    def mouseReleaseEvent(self, ev):
        s = self.sel(); self.close()
        if s.width() > 4 and s.height() > 4:
            dpr = self.pm.devicePixelRatio()
            out = self.pm.copy(QRect(int(s.x() * dpr), int(s.y() * dpr), int(s.width() * dpr), int(s.height() * dpr)))
            out.setDevicePixelRatio(dpr); self.picked.emit(out)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            self.close()


SHOT_FIXED_JS = r"""(function(on){ // ukrycie pływających nagłówków przy sklejaniu całej strony (od drugiego kadru)
  if (on) { window.__lunaFixed = [];
    for (const e of document.querySelectorAll('body *')) { const p = getComputedStyle(e).position;
      if (p === 'fixed' || p === 'sticky') { window.__lunaFixed.push([e, e.style.visibility]); e.style.visibility = 'hidden'; } } }
  else { for (const [e, v] of (window.__lunaFixed || [])) e.style.visibility = v; window.__lunaFixed = []; }
})(%ON%)"""


PIP_FIND_JS = r"""(function(){ // największy film na stronie: pauza w karcie, zaznaczenie (do wznowienia), czas i adres
  const vs = [...document.querySelectorAll('video')].filter(v => v.readyState > 0 || v.currentSrc)
    .sort((a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight);
  const v = vs[0]; if (!v) return null;
  const t = v.currentTime || 0; v.pause(); v.setAttribute('data-luna-pip', '1');
  return JSON.stringify({t: t, url: location.href, title: document.title});
})()"""

PIP_FIT_JS = r"""(function(t){ // okienko: sam film na czarnym tle, od zadanego momentu
  let n = 0;
  const go = () => {
    const v = [...document.querySelectorAll('video')].sort((a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight)[0];
    if (!v) { if (++n < 40) setTimeout(go, 400); return; }
    for (let e = v.parentElement; e; e = e.parentElement)
      for (const p of ['transform', 'filter', 'contain', 'perspective']) e.style.setProperty(p, 'none', 'important');
    v.style.cssText += ';position:fixed!important;inset:0!important;width:100vw!important;height:100vh!important;' +
      'max-width:none!important;max-height:none!important;z-index:2147483647!important;background:#000!important;object-fit:contain!important';
    const ov = document.createElement('div'); ov.style.cssText = 'position:fixed;inset:0;background:#000;z-index:2147483646';
    document.body.appendChild(ov); document.documentElement.style.overflow = 'hidden';
    if (t > 0 && Math.abs(v.currentTime - t) > 2) v.currentTime = t;
    v.play().catch(() => {}); window.__lunaV = v;
  };
  go();
})(%T%)"""

PIP_YT_HTML = """<!doctype html><html><body style="margin:0;background:#000;overflow:hidden">
<iframe id="f" src="https://www.youtube.com/embed/%ID%?start=%T%&autoplay=1&enablejsapi=1&origin=https://luna.local"
 style="border:0;width:100vw;height:100vh" allow="autoplay; encrypted-media; fullscreen"></iframe>
<script>window.__t = -1;
addEventListener('message', e => { try { const d = JSON.parse(e.data); if (d.info && typeof d.info.currentTime === 'number') window.__t = d.info.currentTime; } catch (_) {} });
const f = document.getElementById('f');
f.addEventListener('load', () => { const s = () => f.contentWindow.postMessage(JSON.stringify({event: 'listening', id: 1, channel: 'widget'}), '*'); s(); setInterval(s, 2000); });
</script></body></html>"""


def youtube_id(url):
    m = re.search(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/)|youtu\.be/)([\w-]{11})", url or "")
    return m.group(1) if m else ""


class PipWindow(QFrame):
    """Obraz w obrazie: małe okno zawsze na wierzchu z samym filmem; zamknięcie wznawia film w karcie od tego miejsca."""

    def __init__(self, browser, src, info):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.b, self.src, self.yt, self._closing = browser, src, youtube_id(info.get("url", "")), False
        self.setObjectName("pip"); self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setStyleSheet("QFrame#pip{background:#000;border:1px solid #2c2c2c} QWidget#piphead{background:#111}")
        self.setWindowTitle("Luna – obraz w obrazie"); self.setWindowIcon(app_icon())
        v = QVBoxLayout(self); v.setContentsMargins(1, 1, 1, 1); v.setSpacing(0)
        head = QWidget(); head.setObjectName("piphead"); head.setFixedHeight(28); head.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        h = QHBoxLayout(head); h.setContentsMargins(10, 0, 4, 0); h.setSpacing(2)
        t = QLabel(); t.setObjectName("splittitle"); t.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        t.setText(info.get("title") or "Film"); h.addWidget(t, 1)
        for kind, tip, fn in (("external", "Wróć do karty z filmem", self.back), ("close", "Zamknij (film wróci do karty)", self.finish)):
            bt = QToolButton(); bt.setObjectName("splitbtn"); bt.setIcon(glyph(kind, "#9a9a9a")); bt.setIconSize(QSize(15, 15))
            bt.setFixedSize(24, 24); bt.setToolTip(tip); bt.clicked.connect(lambda _=False, f=fn: f()); h.addWidget(bt)
        head.mousePressEvent = lambda ev: self.windowHandle().startSystemMove() if ev.button() == Qt.MouseButton.LeftButton else None
        v.addWidget(head)
        self.web = WebView(container=src.container)
        A = QWebEngineSettings.WebAttribute
        self.web.settings().setAttribute(A.PlaybackRequiresUserGesture, False)
        v.addWidget(self.web, 1)
        from PyQt6.QtWidgets import QSizeGrip
        self.grip = QSizeGrip(self); self.grip.setFixedSize(16, 16)
        t0 = max(0, int(info.get("t") or 0))
        if self.yt:
            self.web.setHtml(PIP_YT_HTML.replace("%ID%", self.yt).replace("%T%", str(t0)), QUrl("https://luna.local/"))
        else:
            self.web.loadFinished.connect(lambda ok: self.web.page().runJavaScript(
                PIP_FIT_JS.replace("%T%", str(info.get("t") or 0)), QWebEngineScript.ScriptWorldId.ApplicationWorld))
            self.web.setUrl(QUrl(info["url"]))
        a = cur_screen().availableGeometry(); self.resize(480, 298)
        self.move(a.right() - self.width() - 24, a.bottom() - self.height() - 24)

    def resizeEvent(self, ev):
        super().resizeEvent(ev); self.grip.move(self.width() - 17, self.height() - 17); self.grip.raise_()

    def _time(self, cb):
        js = "window.__t" if self.yt else "(window.__lunaV || document.querySelector('video') || {currentTime: -1}).currentTime"
        self.web.page().runJavaScript(js, QWebEngineScript.ScriptWorldId.MainWorld if self.yt else
                                      QWebEngineScript.ScriptWorldId.ApplicationWorld, cb)

    def finish(self, show_tab=False):
        if self._closing:
            return
        self._closing = True
        QTimer.singleShot(1500, self.close)   # zabezpieczenie, gdyby strona nie odpowiedziała

        def got(t):
            try:
                self.b.pip_closed(self.src, t if isinstance(t, (int, float)) else -1, show_tab)
            except RuntimeError:
                pass
            self.close()
        self._time(got)

    def back(self):
        self.finish(True)

    def closeEvent(self, ev):
        if not self._closing:   # zamknięcie z systemu (np. Alt+F4) – też wznów film w karcie
            self._closing = True
            try:
                self.b.pip_closed(self.src, -1, False)
            except RuntimeError:
                pass
        self.web.setUrl(QUrl("about:blank")); super().closeEvent(ev)


class BackupDialog(LunaDialog):
    """Kopia zapasowa: utworzenie pliku .lunabak (hasło) albo przywrócenie z niego (Luna uruchamia się ponownie)."""

    def __init__(self, browser):
        super().__init__(browser, "Kopia zapasowa", "save", (620, 400),
                         "Jeden plik z kafelkami, ustawieniami, widgetami, kartami, historią, ikonami stron i hasłami, "
                         "zaszyfrowany hasłem, które podasz – bez niego nikt go nie odczyta.")
        self.b = browser
        row = QHBoxLayout(); row.setSpacing(12)
        for kind, title, text, btn, fn, primary in (
                ("save", "Utwórz kopię", "Zapisz plik .lunabak, np. na pendrive albo w chmurze.", "Utwórz kopię…", self.create, True),
                ("reload", "Przywróć z kopii", "Wczytaj plik .lunabak i podaj to samo hasło. Luna uruchomi się ponownie.",
                 "Przywróć z kopii…", self.restore, False)):
            card = QFrame(); card.setObjectName("optcard"); cv = QVBoxLayout(card); cv.setContentsMargins(16, 16, 16, 16); cv.setSpacing(6)
            ti = QLabel(); ti.setObjectName("tileicon"); ti.setFixedSize(40, 40); ti.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ti.setPixmap(glyph(kind, "#ececec").pixmap(20, 20)); cv.addWidget(ti); cv.addSpacing(4)
            cv.addWidget(lbl(title, "h3")); cv.addWidget(lbl(text, "muted2", wrap=True)); cv.addStretch(1)
            b = QPushButton(btn); b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(lambda _=False, f=fn: f())
            if primary:
                b.setObjectName("primary")
            cv.addWidget(b); row.addWidget(card, 1)
        self.body.addLayout(row, 1)
        self.body.addWidget(lbl("Konta Google, Spotify i Discord trzeba po przywróceniu połączyć ponownie (logowania stron "
                                "zostają w profilu tamtego komputera).", "muted", wrap=True))

    def _password(self, title, confirm):
        p, ok = QInputDialog.getText(self, title, "Hasło kopii (min. 8 znaków):", QLineEdit.EchoMode.Password)
        if not ok:
            return None
        if len(p) < 8:
            QMessageBox.warning(self, title, "Hasło musi mieć co najmniej 8 znaków."); return None
        if confirm:
            p2, ok = QInputDialog.getText(self, title, "Powtórz hasło:", QLineEdit.EchoMode.Password)
            if not ok:
                return None
            if p2 != p:
                QMessageBox.warning(self, title, "Hasła się różnią."); return None
        return p

    def create(self):
        st = self.b.store
        name = f"Luna-kopia-{date.today().isoformat()}.lunabak"
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz kopię zapasową", str(Path(DOWNLOADS[0].folder()) / name),
                                              "Kopia Luny (*.lunabak)")
        if not path:
            return
        pw = self._password("Utwórz kopię", True)
        if pw is None:
            return
        if self.b.primary:
            st.settings["session"] = self.b.session_data()
        icons = {}
        if ICONS.exists():
            for f in ICONS.iterdir():
                if f.is_file() and f.stat().st_size < 256 * 1024:
                    icons[f.name] = base64.b64encode(f.read_bytes()).decode()
        vault = VAULT[0].data if VAULT and VAULT[0].available() else None
        payload = {"v": 1, "created": datetime.now().isoformat(timespec="seconds"), "items": st.items, "recent": st.recent,
                   "history": st.history, "settings": st.settings, "vault": vault, "icons": icons}
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            Path(path).write_bytes(backup_encrypt(payload, pw))
        except OSError as e:
            QApplication.restoreOverrideCursor(); QMessageBox.warning(self, "Kopia zapasowa", f"Nie udało się zapisać pliku: {e}"); return
        QApplication.restoreOverrideCursor()
        n = len(vault["logins"]) if vault else 0
        self.b.notice.ask(f"Kopia zapisana: {Path(path).name} (kafelki: {len(st.items)}, hasła: {n})",
                          [("Pokaż w folderze", lambda: show_in_folder(path), True), ("OK", None, False)], icon="save")
        self.accept()

    def restore(self):
        path, _ = QFileDialog.getOpenFileName(self, "Przywróć z kopii", DOWNLOADS[0].folder(), "Kopia Luny (*.lunabak)")
        if not path:
            return
        pw = self._password("Przywróć z kopii", False)
        if pw is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            data = backup_decrypt(Path(path).read_bytes(), pw)
        except (ValueError, OSError) as e:
            QApplication.restoreOverrideCursor(); QMessageBox.warning(self, "Przywróć z kopii", str(e)); return
        QApplication.restoreOverrideCursor()
        logins = len((data.get("vault") or {}).get("logins", []))
        if QMessageBox.question(self, "Przywróć z kopii",
                                f"Kopia z {data.get('created', '?').replace('T', ' ')}: kafelki {len(data.get('items', []))}, "
                                f"hasła {logins}.\n\nObecne kafelki, ustawienia, karty, historia i hasła zostaną zastąpione. "
                                "Luna uruchomi się ponownie. Kontynuować?") != QMessageBox.StandardButton.Yes:
            return
        apply_backup(data); self.accept(); restart_luna(self.b)


def apply_backup(data):
    """Zapis przywróconych danych na dysk; hasła szyfrowane od nowa kluczem tego komputera."""
    Store._write(DATA, data.get("items", [])); Store._write(RECENT, data.get("recent", []))
    Store._write(HIST, data.get("history", [])); Store._write(SETTINGS, data.get("settings", {}))
    ICONS.mkdir(exist_ok=True)
    for name, b64 in (data.get("icons") or {}).items():
        if re.fullmatch(r"[\w.\-]+", name):   # tylko proste nazwy plików (bez ścieżek)
            try:
                (ICONS / name).write_bytes(base64.b64decode(b64))
            except (OSError, ValueError):
                pass
    if VAULT and VAULT[0].available() and isinstance(data.get("vault"), dict):
        VAULT[0].data = {"logins": [], "never": [], "ddg": ""}; VAULT[0].data.update(data["vault"]); VAULT[0].save()
    FROZEN[0] = True


# --- tłumaczenie całej strony na polski: tekst zbiera skrypt w świecie aplikacji (niewidoczny dla strony, bez CSP),
# tłumaczy Luna przez sieć Qt, wynik wraca do tych samych węzłów tekstu; oryginał można przywrócić ---
TR_COLLECT = r"""(function(){
var S=window.__ltr||(window.__ltr={nodes:[],orig:[]});
var skip={SCRIPT:1,STYLE:1,NOSCRIPT:1,CODE:1,PRE:1,TEXTAREA:1,KBD:1,SAMP:1,VAR:1,svg:1,SVG:1,MATH:1,IFRAME:1,INPUT:1,SELECT:1,OPTION:1};
var out=[],start=S.nodes.length,root=document.body;if(!root)return JSON.stringify({start:start,texts:[]});
var tw=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:function(n){
 var v=n.nodeValue;if(n.__lt||!v||v.length>4000||!/[A-Za-zÀ-ɏͰ-ӿ぀-ヿ一-鿿가-힯]/.test(v))return 2;
 for(var p=n.parentElement;p;p=p.parentElement){if(skip[p.tagName]||p.isContentEditable||p.getAttribute('translate')==='no'||(p.classList&&p.classList.contains('notranslate')))return 2;}
 return 1;}});
var n;while((n=tw.nextNode())&&out.length<2500){n.__lt=1;S.nodes.push(n);S.orig.push(n.nodeValue);out.push(n.nodeValue);}
return JSON.stringify({start:start,texts:out});})()"""
TR_APPLY = "(function(d){var S=window.__ltr;if(!S)return;for(var i=0;i<d.t.length;i++){var n=S.nodes[d.s+i];" \
           "if(n&&typeof d.t[i]==='string'&&n.nodeValue===S.orig[d.s+i])n.nodeValue=d.t[i];}})(%s)"
TR_RESTORE = "(function(){var S=window.__ltr;if(!S)return;for(var i=0;i<S.nodes.length;i++){var n=S.nodes[i];" \
             "if(n){n.nodeValue=S.orig[i];n.__lt=0;}}window.__ltr=null;})()"
TR_URL = "https://translate.googleapis.com/translate_a/t?client=gtx&sl=auto&tl=%s"
# wszystkie języki Tłumacza Google (kod → nazwa po polsku); język docelowy wybiera użytkownik (domyślnie polski)
LANGS = {
    "af": "afrikaans", "sq": "albański", "am": "amharski", "en": "angielski", "ar": "arabski", "az": "azerski",
    "eu": "baskijski", "be": "białoruski", "bn": "bengalski", "my": "birmański", "bs": "bośniacki", "bg": "bułgarski",
    "ceb": "cebuański", "zh-CN": "chiński (uproszczony)", "zh-TW": "chiński (tradycyjny)", "hr": "chorwacki",
    "cs": "czeski", "da": "duński", "eo": "esperanto", "et": "estoński", "tl": "filipiński", "fi": "fiński",
    "fr": "francuski", "fy": "fryzyjski", "gl": "galicyjski", "el": "grecki", "ka": "gruziński", "gu": "gudżarati",
    "ha": "hausa", "haw": "hawajski", "iw": "hebrajski", "hi": "hindi", "es": "hiszpański", "hmn": "hmong",
    "ig": "igbo", "id": "indonezyjski", "ga": "irlandzki", "is": "islandzki", "ja": "japoński", "jv": "jawajski",
    "yi": "jidysz", "yo": "joruba", "kn": "kannada", "ca": "kataloński", "kk": "kazachski", "km": "khmerski",
    "rw": "kinyarwanda", "ky": "kirgiski", "ko": "koreański", "co": "korsykański", "ht": "kreolski haitański",
    "ku": "kurdyjski", "lo": "laotański", "la": "łaciński", "lt": "litewski", "lb": "luksemburski", "lv": "łotewski",
    "mk": "macedoński", "mg": "malgaski", "ml": "malajalam", "ms": "malajski", "mt": "maltański", "mi": "maoryski",
    "mr": "marathi", "mn": "mongolski", "ne": "nepalski", "nl": "niderlandzki", "de": "niemiecki", "ny": "njandża",
    "no": "norweski", "or": "orija", "hy": "ormiański", "ps": "paszto", "pa": "pendżabski", "fa": "perski",
    "pl": "polski", "pt": "portugalski", "ru": "rosyjski", "ro": "rumuński", "sm": "samoański", "sr": "serbski",
    "sn": "shona", "sd": "sindhi", "sk": "słowacki", "sl": "słoweński", "so": "somalijski", "st": "sotho",
    "sw": "suahili", "su": "sundajski", "si": "syngaleski", "gd": "szkocki gaelicki", "sv": "szwedzki",
    "tg": "tadżycki", "th": "tajski", "ta": "tamilski", "tt": "tatarski", "te": "telugu", "tr": "turecki",
    "tk": "turkmeński", "ug": "ujgurski", "uk": "ukraiński", "ur": "urdu", "uz": "uzbecki", "cy": "walijski",
    "hu": "węgierski", "vi": "wietnamski", "it": "włoski", "xh": "xhosa", "zu": "zulu"}
_LANG_ALIAS = {"he": "iw", "zh": "zh-CN", "zh-hans": "zh-CN", "zh-hant": "zh-TW", "zh-hk": "zh-TW", "nb": "no",
               "nn": "no", "fil": "tl", "jw": "jv", "mni": "", "zh-cn": "zh-CN", "zh-tw": "zh-TW"}


def lang_code(tag):
    """Atrybut lang strony / kod z tłumacza → kod z LANGS albo "" (nieznany)."""
    t = str(tag or "").strip().replace("_", "-")
    if not t:
        return ""
    low = t.lower()
    if low in _LANG_ALIAS:
        return _LANG_ALIAS[low]
    if t in LANGS:
        return t
    base = low.split("-")[0]
    return _LANG_ALIAS.get(base, base if base in LANGS else "")


def lang_name(code):
    return LANGS.get(lang_code(code) or code, code or "nieznany")


def translate_target(store):
    c = store.settings.get("translate_target", "pl")
    return c if c in LANGS else "pl"


def translate_texts(store, texts, target, cb):
    """Tłumaczy listę tekstów (dowolny język źródłowy) → cb(lista|None, wykryty_kod)."""
    body = "&".join("q=" + quote(t, safe="") for t in texts).encode("ascii")
    req = QNetworkRequest(QUrl(TR_URL % quote(target, safe="")))
    req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/x-www-form-urlencoded;charset=utf-8")
    req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "Mozilla/5.0")
    req.setTransferTimeout(20000)
    r = store.nam.post(req, body)

    def done():
        data = bytes(r.readAll()); ok = r.error() == QNetworkReply.NetworkError.NoError; r.deleteLater()
        try:
            j = json.loads(data.decode("utf-8")) if ok else None
        except (ValueError, UnicodeDecodeError):
            j = None
        if not isinstance(j, list):
            cb(None, ""); return
        if len(texts) == 1 and j and isinstance(j[0], str):
            j = [j]
        out, src = [], ""
        for item in j:
            if isinstance(item, list) and item:
                out.append(html.unescape(str(item[0]))); src = src or (str(item[1]) if len(item) > 1 else "")
            elif isinstance(item, str):
                out.append(html.unescape(item))
            else:
                out.append(None)
        cb(out, src)
    r.finished.connect(done)
    return r


class PageTranslator(QObject):
    """Tłumaczy jedną stronę (widok) na polski; doczytuje nowe treści co 2,5 s, dopóki tłumaczenie jest włączone."""
    status = pyqtSignal(str)

    def __init__(self, store, web):
        super().__init__(web)
        self.store, self.web = store, web
        self.active, self.queue, self.busy, self.done_items, self.failed = False, [], False, 0, False
        self.target = "pl"
        self._t = QTimer(self); self._t.setInterval(2500); self._t.timeout.connect(self._collect)
        web.urlChanged.connect(self._navigated)
        self._url = web.url().toString(QUrl.UrlFormattingOption.RemoveFragment)

    def _navigated(self, u):
        if u.toString(QUrl.UrlFormattingOption.RemoveFragment) != self._url:   # nowa strona: tłumaczenie od nowa (na prośbę)
            self.active = False; self._t.stop(); self.queue.clear()

    def start(self, target=None):
        self.target = target or translate_target(self.store)
        self.active, self.failed, self.done_items = True, False, 0
        self._url = self.web.url().toString(QUrl.UrlFormattingOption.RemoveFragment)
        self._collect(); self._t.start()

    def restore(self):
        self.active = False; self._t.stop(); self.queue.clear()
        self.web.page().runJavaScript(TR_RESTORE, QWebEngineScript.ScriptWorldId.ApplicationWorld)

    def _collect(self):
        if not self.active:
            return
        try:
            self.web.page().runJavaScript(TR_COLLECT, QWebEngineScript.ScriptWorldId.ApplicationWorld, self._got)
        except RuntimeError:
            self._t.stop()

    def _got(self, res):
        try:
            d = json.loads(res) if isinstance(res, str) else None
        except ValueError:
            d = None
        if not d or not d.get("texts") or not self.active:
            return
        start, texts = int(d["start"]), d["texts"]
        batch, size, i0 = [], 0, 0
        for i, t in enumerate(texts):
            core = t.strip()
            if batch and (size + len(core) > 3500 or len(batch) >= 120):
                self.queue.append((start + i0, texts[i0:i])); batch, size, i0 = [], 0, i
            batch.append(core); size += len(core) + 3
        if batch:
            self.queue.append((start + i0, texts[i0:]))
        self._next()

    def _next(self):
        if self.busy or not self.queue or not self.active:
            if not self.queue and not self.busy and self.active:
                self.status.emit("done")
            return
        self.busy = True
        s, texts = self.queue.pop(0)
        translate_texts(self.store, [t.strip() for t in texts], self.target,
                        lambda res, src, s=s, texts=texts: self._reply(res, s, texts))

    def _reply(self, res, s, texts):
        self.busy = False
        out = None
        if res is not None:
            out = []
            for tr, orig in zip(res, texts):
                if tr is None:
                    out.append(None); continue
                lead = orig[:len(orig) - len(orig.lstrip())]; trail = orig[len(orig.rstrip()):]
                out.append(lead + tr + trail)
        if out is None:
            self.failed = True; self.queue.clear(); self.status.emit("error"); return
        try:
            self.web.page().runJavaScript(TR_APPLY % json.dumps({"s": s, "t": out}, ensure_ascii=False),
                                          QWebEngineScript.ScriptWorldId.ApplicationWorld)
        except RuntimeError:
            return
        self.done_items += len(out)
        self._next()


def translator_for(store, web):
    tr = getattr(web, "_translator", None)
    if tr is None:
        tr = PageTranslator(store, web); web._translator = tr
    return tr


# --- czysty link: bez parametrów śledzących (utm_*, fbclid, gclid…) ---
_TRACK_PARAMS = re.compile(r"^(utm_\w+|fbclid|gclid|dclid|gbraid|wbraid|msclkid|mc_eid|mc_cid|yclid|_hsenc|_hsmi|igshid|"
                           r"igsh|si|ref_src|ref_url|spm|scm|_ga|_gl|vero_id|oly_\w+|wickedid|twclid|ttclid|srsltid)$", re.I)


def clean_url(url):
    try:
        p = urllib.parse.urlsplit(url)
        q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if not _TRACK_PARAMS.match(k)]
        return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urlencode(q, doseq=True), p.fragment))
    except ValueError:
        return url


class TranslatePopup(QFrame):
    """Tłumaczenie zaznaczonego tekstu z dowolnego języka na wybrany (lista wszystkich języków)."""

    def __init__(self, browser, text, pos):
        super().__init__(browser, Qt.WindowType.Popup); self.b, self.text = browser, text
        self.setObjectName("tabpop"); self.setFixedWidth(460)
        v = QVBoxLayout(self); v.setContentsMargins(12, 12, 12, 12); v.setSpacing(8)
        row = QHBoxLayout(); self.src = lbl("Tłumaczenie…", "muted2"); row.addWidget(self.src, 1)
        row.addWidget(lbl("na:", "muted2"))
        self.combo = QComboBox()
        for code, name in sorted(LANGS.items(), key=lambda kv: fold(kv[1])):
            self.combo.addItem(name, code)
        self.combo.setCurrentIndex(max(0, self.combo.findData(translate_target(browser.store))))
        self.combo.currentIndexChanged.connect(self._lang); row.addWidget(self.combo); v.addLayout(row)
        self.out = QPlainTextEdit(); self.out.setReadOnly(True); self.out.setMinimumHeight(110); self.out.setMaximumHeight(260)
        v.addWidget(self.out)
        bb = QHBoxLayout(); cp = QPushButton("Kopiuj"); cp.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.out.toPlainText()))
        bb.addStretch(1); bb.addWidget(cp); v.addLayout(bb)
        self.move(pos); self.show(); self.run()

    def _lang(self, _):
        self.b.store.settings["translate_target"] = self.combo.currentData(); self.b.store.save_soon(); self.run()

    def run(self):
        self.out.setPlainText("Tłumaczę…")

        def got(res, src):
            try:
                if res is None:
                    self.out.setPlainText("Nie udało się połączyć z Tłumaczem Google."); return
                self.out.setPlainText(res[0] or "")
                self.src.setText("Wykryty język: " + (lang_name(src) if src else "nieznany"))
            except RuntimeError:
                pass
        translate_texts(self.b.store, [self.text[:4500]], self.combo.currentData(), got)


def show_qr(parent, url):
    d = QDialog(parent); d.setWindowTitle("Kod QR"); v = QVBoxLayout(d)
    q = QLabel(); q.setPixmap(qr_pixmap(url, px=5)); q.setAlignment(Qt.AlignmentFlag.AlignCenter); v.addWidget(q)
    t = lbl(url[:120], "muted2", wrap=True); v.addWidget(t)
    bt = QPushButton("Kopiuj link"); bt.clicked.connect(lambda: QGuiApplication.clipboard().setText(url)); v.addWidget(bt)
    d.exec()


# --- zakreślenia i notatki na stronach: zapis tekstu z kontekstem (prefiks/sufiks), odtwarzane po powrocie na stronę ---
HIGHLIGHTS = HOME / ".luna_zakreslenia.json"
HL_COLORS = [("Żółty", "#fff176"), ("Zielony", "#a5d6a7"), ("Różowy", "#f8bbd0"), ("Niebieski", "#90caf9")]
HL_LIB = r"""var LHL=window.__lhl||(window.__lhl={});
LHL.nodes=function(){var a=[];if(!document.body)return a;var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,{acceptNode:function(n){var p=n.parentElement;if(!p)return 2;var t=p.tagName;return(t==='SCRIPT'||t==='STYLE'||t==='NOSCRIPT'||t==='TEXTAREA')?2:1}});var n;while(n=w.nextNode())a.push(n);return a};
LHL.wrap=function(r,id,color,note){var root=r.commonAncestorContainer;if(root.nodeType===3)root=root.parentNode;var nodes=[],it=document.createTreeWalker(root,NodeFilter.SHOW_TEXT),n;while(n=it.nextNode()){if(r.intersectsNode(n))nodes.push(n)}
 var sc=r.startContainer,so=r.startOffset,ec=r.endContainer,eo=r.endOffset;
 nodes.forEach(function(t){var s=(t===sc)?so:0,e=(t===ec)?eo:t.nodeValue.length;if(e<=s||!t.nodeValue.slice(s,e).length)return;var mid=t;if(s>0)mid=t.splitText(s);if(e-s<mid.nodeValue.length)mid.splitText(e-s);
  var m=document.createElement('mark');m.setAttribute('data-lhl',id);m.style.cssText='background:'+color+'!important;color:#111!important;border-radius:2px;padding:0;cursor:'+(note?'help':'auto');if(note)m.title=note;mid.parentNode.insertBefore(m,mid);m.appendChild(mid);});};
LHL.find=function(h){var nodes=LHL.nodes(),full='',idx=[];nodes.forEach(function(n){idx.push(full.length);full+=n.nodeValue});var pos=-1,from=0,best=-1;
 while((pos=full.indexOf(h.text,from))>=0){if(best<0)best=pos;if((h.prefix&&full.slice(Math.max(0,pos-h.prefix.length),pos)===h.prefix)||(h.suffix&&full.slice(pos+h.text.length,pos+h.text.length+h.suffix.length)===h.suffix)){best=pos;break}from=pos+1}
 if(best<0)return null;var a=best,b=best+h.text.length,r=document.createRange(),ok1=false,ok2=false;
 for(var i=0;i<nodes.length;i++){var st=idx[i],ln=nodes[i].nodeValue.length;if(!ok1&&a<st+ln){r.setStart(nodes[i],a-st);ok1=true}if(ok1&&b<=st+ln){r.setEnd(nodes[i],b-st);ok2=true;break}}return ok1&&ok2?r:null};
"""
HL_CAPTURE = HL_LIB + r"""(function(color,note){var s=getSelection();if(!s||s.isCollapsed||!s.rangeCount)return '';var r=s.getRangeAt(0);
var nodes=LHL.nodes(),full='',a=-1,b=-1;for(var i=0;i<nodes.length;i++){var n=nodes[i];if(n===r.startContainer)a=full.length+r.startOffset;if(n===r.endContainer)b=full.length+r.endOffset;full+=n.nodeValue}
var text=(a>=0&&b>a)?full.slice(a,b):s.toString();if(!text.trim())return '';var id='h'+Date.now().toString(36)+Math.random().toString(36).slice(2,6);
var res={id:id,text:text,prefix:a>=0?full.slice(Math.max(0,a-40),a):'',suffix:b>=0?full.slice(b,b+40):''};LHL.wrap(r,id,color,note);s.removeAllRanges();return JSON.stringify(res)})(%s,%s)"""
HL_APPLY = HL_LIB + r"""(function(items){var n=0;items.forEach(function(h){if(document.querySelector('mark[data-lhl="'+h.id+'"]')){n++;return}var r=LHL.find(h);if(r){LHL.wrap(r,h.id,h.color,h.note);n++}});return n})(%s)"""
HL_REMOVE = r"""(function(id){document.querySelectorAll('mark[data-lhl="'+id+'"]').forEach(function(m){var p=m.parentNode;while(m.firstChild)p.insertBefore(m.firstChild,m);p.removeChild(m);p.normalize()})})(%s)"""
HL_HOVER = r"""(function(){var m=document.querySelectorAll('mark[data-lhl]:hover');return m.length?m[m.length-1].getAttribute('data-lhl'):''})()"""


class Highlights:
    _data = None

    @staticmethod
    def key(url):
        u = clean_url(url).split("#", 1)[0]
        return u[:-1] if u.endswith("/") and u.count("/") > 3 else u

    @classmethod
    def data(cls):
        if cls._data is None:
            try:
                d = json.loads(HIGHLIGHTS.read_text(encoding="utf-8"))
                cls._data = d if isinstance(d, dict) else {}
            except (OSError, ValueError):
                cls._data = {}
        return cls._data

    @classmethod
    def save(cls):
        try:
            tmp = HIGHLIGHTS.with_suffix(".tmp"); tmp.write_text(json.dumps(cls.data(), ensure_ascii=False), encoding="utf-8")
            tmp.replace(HIGHLIGHTS)
        except OSError:
            pass
        sync_touch()

    @classmethod
    def for_url(cls, url):
        return cls.data().get(cls.key(url), [])

    @classmethod
    def add(cls, url, item, title=""):
        lst = cls.data().setdefault(cls.key(url), [])
        item.update(t=int(time.time()), title=title[:200]); lst.append(item); cls.save()

    @classmethod
    def remove(cls, url, hid):
        k = cls.key(url); lst = [h for h in cls.data().get(k, []) if h.get("id") != hid]
        if lst:
            cls.data()[k] = lst
        else:
            cls.data().pop(k, None)
        cls.save()

    @classmethod
    def set_note(cls, url, hid, note):
        for h in cls.data().get(cls.key(url), []):
            if h.get("id") == hid:
                h["note"] = note
        cls.save()


def apply_highlights(view):
    """Po wczytaniu strony: odtwórz zapisane zakreślenia (dwa podejścia – także dla treści doczytywanej skryptami)."""
    try:
        items = Highlights.for_url(view.url().toString())
    except RuntimeError:
        return
    if not items:
        return
    src = HL_APPLY % json.dumps(items, ensure_ascii=False)
    for ms in (0, 2500):
        QTimer.singleShot(ms, lambda: _safe_js(view, src))


def _safe_js(view, src, cb=None):
    try:
        if cb is None:
            view.page().runJavaScript(src, QWebEngineScript.ScriptWorldId.ApplicationWorld)
        else:
            view.page().runJavaScript(src, QWebEngineScript.ScriptWorldId.ApplicationWorld, cb)
    except RuntimeError:
        pass


# --- autouzupełnianie adresów (dane zaszyfrowane w sejfie haseł) ---
ADDR_FIELDS = [("first", "Imię"), ("last", "Nazwisko"), ("company", "Firma"), ("street", "Ulica i numer"),
               ("line2", "Lokal / dodatkowe"), ("postal", "Kod pocztowy"), ("city", "Miejscowość"),
               ("country", "Kraj"), ("tel", "Telefon"), ("email", "E-mail")]
ADDR_JS = r"""(function(A,fill){var el=document.activeElement;var root=(el&&el.form)||document;
var map=[['email',/e-?mail/],['tel',/(^|\W)tel|phone|telefon|kom[oó]rk|mobile/],['postal',/postal|zip|kod.?poczt|post.?code/],
['city',/city|locality|address-level2|miasto|miejscowo|town/],['country',/country|kraj|pa[nń]stw/],['first',/given|first|fname|imi[eę](?!.*nazw)/],
['last',/family|last|lname|surname|nazwisk/],['line2',/address-line2|addr(ess)?.?2|lokal|mieszkani|apartment/],
['company',/organi[sz]ation|company|firma/],['street',/street|address-line1|addr(ess)?.?1|ulica|adres|address/]];
var n=0,kinds={};root.querySelectorAll('input,select,textarea').forEach(function(i){var t=(i.type||'').toLowerCase();if(t==='hidden'||t==='password'||t==='checkbox'||t==='radio'||t==='submit'||i.disabled||i.readOnly)return;
var r=i.getBoundingClientRect();if(!r.width||!r.height)return;var lab='';if(i.id){var l=document.querySelector('label[for="'+CSS.escape(i.id)+'"]');if(l)lab=l.textContent}if(!lab&&i.closest('label'))lab=i.closest('label').textContent;
var ac=(i.getAttribute('autocomplete')||'').toLowerCase().replace(/^(shipping|billing|section-\S+)\s+/g,'');var key=(ac+' '+(i.name||'')+' '+(i.id||'')+' '+(i.placeholder||'')+' '+(i.getAttribute('aria-label')||'')+' '+lab).toLowerCase();
var k=null;if(ac==='name')k='full';for(var j=0;!k&&j<map.length;j++){if(map[j][1].test(ac))k=map[j][0]}for(var j=0;!k&&j<map.length;j++){if(map[j][1].test(key))k=map[j][0]}
if(!k)return;kinds[k]=1;if(!fill||A[k]==null||A[k]==='')return;var v=String(A[k]);
if(i.tagName==='SELECT'){var o=Array.prototype.find.call(i.options,function(o){return o.value.toLowerCase()===v.toLowerCase()||o.text.trim().toLowerCase()===v.toLowerCase()});if(!o)return;i.value=o.value}
else{var d=Object.getOwnPropertyDescriptor(i.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value');d.set.call(i,v)}
i.dispatchEvent(new Event('input',{bubbles:true}));i.dispatchEvent(new Event('change',{bubbles:true}));n++});
return JSON.stringify({filled:n,address:!!(kinds.street&&(kinds.postal||kinds.city)),kinds:Object.keys(kinds)})})(%s,%s)"""


def addresses():
    v = VAULT[0] if VAULT and VAULT[0].available() else None
    return v.data.setdefault("addresses", []) if v is not None else []


def address_values(a):
    d = dict(a); d["full"] = (a.get("first", "") + " " + a.get("last", "")).strip()
    return d


def fill_address(view, a, cb=None):
    _safe_js(view, ADDR_JS % (json.dumps(address_values(a), ensure_ascii=False), "true"), cb)


# --- YouTube: pomijanie fragmentów sponsorowanych (otwarta baza SponsorBlock; zapytanie po 4 znakach skrótu SHA-256
# identyfikatora filmu – serwis nie wie, który film oglądasz) ---
SB_CATS = {"sponsor": "fragment sponsorowany", "selfpromo": "autopromocję", "interaction": "prośbę o subskrypcję"}
SB_JS = r"""(function(segs,vid,key){var S=window.__lsb||(window.__lsb={});S.segs=segs;S.vid=vid;if(S.on)return;S.on=true;S.last=0;
document.addEventListener('timeupdate',function(e){var v=e.target;if(!(v instanceof HTMLMediaElement)||!S.segs.length)return;
var cur=new URLSearchParams(location.search).get('v')||(location.pathname.match(/\/(?:shorts|live)\/([\w-]{11})/)||[])[1];
if(cur!==S.vid)return;var t=v.currentTime;for(var i=0;i<S.segs.length;i++){var s=S.segs[i];if(t>=s[0]&&t<s[1]-0.4){
if(Date.now()-S.last<800)return;S.last=Date.now();v.currentTime=s[1];console.log(key+'sb:'+JSON.stringify({c:s[2],d:Math.round(s[1]-t)}));return}}},true)})(%s,%s,%s)"""


def youtube_id(u):
    q = u if isinstance(u, QUrl) else QUrl(u)
    h = q.host().lower()
    if h.endswith("youtu.be"):
        vid = q.path().strip("/")[:11]
    elif h.endswith("youtube.com"):
        vid = urllib.parse.parse_qs(q.query()).get("v", [""])[0]
        if not vid:
            m = re.match(r"^/(?:shorts|live|embed)/([\w-]{11})", q.path())
            vid = m.group(1) if m else ""
    else:
        return ""
    return vid if re.fullmatch(r"[\w-]{11}", vid or "") else ""


class SponsorBlock:
    cache = {}

    @classmethod
    def segments(cls, store, vid, cb):
        if vid in cls.cache:
            cb(cls.cache[vid]); return
        pre = hashlib.sha256(vid.encode()).hexdigest()[:4]
        cats = quote(json.dumps(list(SB_CATS)), safe="")

        def got(data, err, status):
            segs = []
            if status == 200 and data:
                try:
                    for v in json.loads(data.decode("utf-8")):
                        if v.get("videoID") == vid:
                            for s in v.get("segments", []):
                                a, b = s.get("segment", [0, 0])[:2]
                                if s.get("actionType", "skip") == "skip" and s.get("category") in SB_CATS and b > a:
                                    segs.append([float(a), float(b), s["category"]])
                except (ValueError, TypeError, AttributeError):
                    pass
            cls.cache[vid] = sorted(segs)
            cb(cls.cache[vid])
        store.http(f"https://sponsor.ajay.app/api/skipSegments/{pre}?categories={cats}&actionTypes=%5B%22skip%22%5D",
                   got, timeout=10000, raw=True)


# --- import z Brave / Chrome / Edge: zakładki, historia, hasła (Windows) ---
BOOKMARKS = HOME / ".luna_zakladki.json"
CHROMIUM_BROWSERS = [("Brave", ("BraveSoftware", "Brave-Browser")), ("Chrome", ("Google", "Chrome")),
                     ("Edge", ("Microsoft", "Edge")), ("Vivaldi", ("Vivaldi",)), ("Opera", ())]


def aes_gcm(key, nonce, data, tag=b"", decrypt=True):
    """AES-GCM przez Windows CNG (bcrypt.dll) – bez zewnętrznych bibliotek. Szyfrowanie → (szyfrogram, znacznik)."""
    import ctypes
    from ctypes import wintypes
    bc = ctypes.windll.bcrypt

    class INFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.ULONG), ("dwInfoVersion", wintypes.ULONG), ("pbNonce", ctypes.c_void_p),
                    ("cbNonce", wintypes.ULONG), ("pbAuthData", ctypes.c_void_p), ("cbAuthData", wintypes.ULONG),
                    ("pbTag", ctypes.c_void_p), ("cbTag", wintypes.ULONG), ("pbMacContext", ctypes.c_void_p),
                    ("cbMacContext", wintypes.ULONG), ("cbAAD", wintypes.ULONG), ("cbData", ctypes.c_ulonglong),
                    ("dwFlags", wintypes.ULONG)]
    alg, hkey = ctypes.c_void_p(), ctypes.c_void_p()
    if bc.BCryptOpenAlgorithmProvider(ctypes.byref(alg), ctypes.c_wchar_p("AES"), None, 0):
        raise OSError("AES")
    try:
        mode = ctypes.create_unicode_buffer("ChainingModeGCM")
        if bc.BCryptSetProperty(alg, ctypes.c_wchar_p("ChainingMode"), mode, ctypes.sizeof(mode), 0):
            raise OSError("GCM")
        kb = ctypes.create_string_buffer(bytes(key), len(key))
        if bc.BCryptGenerateSymmetricKey(alg, ctypes.byref(hkey), None, 0, kb, len(key), 0):
            raise OSError("klucz")
        try:
            nb = ctypes.create_string_buffer(bytes(nonce), len(nonce))
            tb = ctypes.create_string_buffer(bytes(tag) if decrypt else b"\0" * 16, 16)
            info = INFO(); info.cbSize = ctypes.sizeof(INFO); info.dwInfoVersion = 1
            info.pbNonce = ctypes.cast(nb, ctypes.c_void_p); info.cbNonce = len(nonce)
            info.pbTag = ctypes.cast(tb, ctypes.c_void_p); info.cbTag = 16
            src = ctypes.create_string_buffer(bytes(data), max(1, len(data)))
            out = ctypes.create_string_buffer(max(1, len(data))); got = wintypes.ULONG()
            fn = bc.BCryptDecrypt if decrypt else bc.BCryptEncrypt
            st = fn(hkey, src, len(data), ctypes.byref(info), None, 0, out, len(data), ctypes.byref(got), 0)
            if st:
                raise ValueError("AES-GCM: błąd 0x%08x" % (st & 0xFFFFFFFF))
            res = out.raw[:got.value]
            return res if decrypt else (res, tb.raw)
        finally:
            bc.BCryptDestroyKey(hkey)
    finally:
        bc.BCryptCloseAlgorithmProvider(alg, 0)


def chromium_profiles():
    """[(nazwa do pokazania, katalog User Data, katalog profilu)] zainstalowanych przeglądarek na bazie Chromium."""
    out, local = [], Path(os.environ.get("LOCALAPPDATA", ""))
    roam = Path(os.environ.get("APPDATA", ""))
    for name, parts in CHROMIUM_BROWSERS:
        root = (roam / "Opera Software" / "Opera Stable") if name == "Opera" else local.joinpath(*parts, "User Data")
        if not root.is_dir():
            continue
        names = {}
        try:
            ls = json.loads((root / "Local State").read_text(encoding="utf-8"))
            names = {k: v.get("name", k) for k, v in ((ls.get("profile") or {}).get("info_cache") or {}).items()}
        except (OSError, ValueError, AttributeError):
            pass
        cands = [root] if name == "Opera" else [p for p in root.iterdir() if p.is_dir() and (p.name == "Default" or p.name.startswith("Profile "))]
        for p in sorted(cands):
            if (p / "Bookmarks").exists() or (p / "History").exists() or (p / "Login Data").exists():
                label = name + ("" if name == "Opera" else f" – {names.get(p.name, p.name)}")
                out.append((label, root, p))
    return out


def _copy_db(path):
    import shutil, tempfile
    d = tempfile.mkdtemp(prefix="luna_imp_"); dst = os.path.join(d, "db")
    shutil.copy2(str(path), dst)
    return dst


def import_bookmarks(profile):
    try:
        j = json.loads((Path(profile) / "Bookmarks").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []

    def walk(node, folder):
        if node.get("type") == "url":
            if str(node.get("url", "")).startswith(("http://", "https://")):
                out.append({"title": node.get("name") or node["url"], "url": node["url"], "folder": folder})
        elif node.get("type") == "folder":
            sub = (folder + " / " if folder else "") + (node.get("name") or "")
            for ch in node.get("children", []) or []:
                walk(ch, sub)
    names = {"bookmark_bar": "Pasek zakładek", "other": "Inne zakładki", "synced": "Zakładki na telefonie"}
    for key, node in (j.get("roots") or {}).items():
        if isinstance(node, dict):
            for ch in node.get("children", []) or []:
                walk(ch, names.get(key, key))
    return out


def import_history(profile, limit=1000):
    import sqlite3
    p = Path(profile) / "History"
    if not p.exists():
        return []
    db = sqlite3.connect(_copy_db(p))
    try:
        rows = db.execute("SELECT url, title, last_visit_time FROM urls WHERE hidden=0 AND url LIKE 'http%' "
                          "ORDER BY last_visit_time DESC LIMIT ?", (limit,)).fetchall()
    finally:
        db.close()
    return [{"name": (t or "")[:200], "url": u, "t": int(max(0, lv / 1e6 - 11644473600))} for u, t, lv in rows]


def import_passwords(root, profile):
    """(lista {origin,user,pw}, liczba pominiętych v20). v10/v11: AES-GCM kluczem z „Local State” (DPAPI);
    v20 (szyfrowanie związane z aplikacją, nowy Chrome) da się odczytać tylko w tej przeglądarce → eksport CSV."""
    import sqlite3
    p = Path(profile) / "Login Data"
    if not p.exists():
        return [], 0
    ls = json.loads((Path(root) / "Local State").read_text(encoding="utf-8"))
    enc = base64.b64decode(ls["os_crypt"]["encrypted_key"])
    key = _dpapi(enc[5:] if enc.startswith(b"DPAPI") else enc, False)
    db = sqlite3.connect(_copy_db(p))
    try:
        rows = db.execute("SELECT origin_url, username_value, password_value FROM logins WHERE blacklisted_by_user=0").fetchall()
    finally:
        db.close()
    out, v20 = [], 0
    for origin, user, pv in rows:
        pv = bytes(pv or b"")
        try:
            if pv[:3] in (b"v10", b"v11"):
                pw = aes_gcm(key, pv[3:15], pv[15:-16], pv[-16:]).decode("utf-8")
            elif pv[:3] == b"v20":
                v20 += 1; continue
            elif pv:
                pw = _dpapi(pv, False).decode("utf-8")   # bardzo stare wersje
            else:
                continue
        except (ValueError, OSError, UnicodeDecodeError):
            continue
        if origin and pw:
            out.append({"origin": origin_of(origin), "user": user or "", "pw": pw})
    return out, v20


def import_passwords_csv(path):
    """Eksport haseł z Chrome/Brave/Edge/Firefox (kolumny name/url/username/password)."""
    import csv
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            r = {(k or "").strip().lower(): (v or "") for k, v in r.items()}
            url, pw = r.get("url") or r.get("origin") or "", r.get("password", "")
            if url.startswith(("http://", "https://")) and pw:
                out.append({"origin": origin_of(url), "user": r.get("username") or r.get("login") or "", "pw": pw})
    return out


class Bookmarks:
    _items = None

    @classmethod
    def items(cls):
        if cls._items is None:
            try:
                d = json.loads(BOOKMARKS.read_text(encoding="utf-8"))
                cls._items = d if isinstance(d, list) else []
            except (OSError, ValueError):
                cls._items = []
        return cls._items

    @classmethod
    def add_many(cls, new):
        have = {b["url"] for b in cls.items()}
        n = 0
        for b in new:
            if b["url"] not in have:
                cls.items().append(b); have.add(b["url"]); n += 1
        try:
            tmp = BOOKMARKS.with_suffix(".tmp"); tmp.write_text(json.dumps(cls.items(), ensure_ascii=False), encoding="utf-8")
            tmp.replace(BOOKMARKS)
        except OSError:
            pass
        sync_touch()
        return n


class ImportDialog(LunaDialog):
    """Import zakładek, historii i haseł z innej przeglądarki (albo hasła z pliku CSV)."""

    def __init__(self, browser):
        super().__init__(browser, "Import z innej przeglądarki", "download", (580, 470),
                         "Zakładki, historia i hasła z Brave, Chrome, Edge, Vivaldi albo Opery na tym komputerze. Dane "
                         "zostają na tym komputerze; hasła są od razu szyfrowane w sejfie Luny.")
        self.b = browser
        self.section("Przeglądarka")
        self.combo = QComboBox(); self.profiles = chromium_profiles()
        for label, root, prof in self.profiles:
            self.combo.addItem(label)
        if not self.profiles:
            self.combo.addItem("Nie znaleziono innych przeglądarek"); self.combo.setEnabled(False)
        self.body.addWidget(self.combo); self.body.addSpacing(4)
        self.section("Co zaimportować")
        self.cb = {}
        for key, text in (("bookmarks", "Zakładki"), ("history", "Historia (ostatnie 1000 stron)"), ("passwords", "Hasła")):
            c = QCheckBox(text); c.setChecked(True); self.body.addWidget(c); self.cb[key] = c
        if not (VAULT and VAULT[0].available()):
            self.cb["passwords"].setChecked(False); self.cb["passwords"].setEnabled(False)
        self.body.addStretch(1)
        self.out = lbl("Najlepiej zamknij tamtą przeglądarkę przed importem.", "muted2", wrap=True); self.body.addWidget(self.out)
        go, _csv, _close = self.footer(left=[("Importuj", self.run, True), ("Hasła z pliku CSV…", self.run_csv)],
                                       right=[("Zamknij", self.accept)])
        go.setEnabled(bool(self.profiles))

    def _save_passwords(self, lst):
        v = VAULT[0]; n = 0
        for x in lst:
            cur = v.find(x["origin"], x["user"])
            if cur is None or cur.get("pw") != x["pw"]:
                if cur is None:
                    v.data["logins"].append({"origin": x["origin"], "user": x["user"], "pw": x["pw"], "ts": int(time.time())})
                else:
                    cur.update(pw=x["pw"], ts=int(time.time()))
                n += 1
        if n:
            v.save()
        return n

    def run(self):
        if not self.profiles:
            return
        label, root, prof = self.profiles[self.combo.currentIndex()]
        msg = []
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if self.cb["bookmarks"].isChecked():
                bm = import_bookmarks(prof); n = Bookmarks.add_many(bm)
                msg.append(f"zakładki: {n} nowych (z {len(bm)})")
            if self.cb["history"].isChecked():
                try:
                    h = import_history(prof)
                    st = self.b.store; seen = {x["url"] for x in st.history}
                    st.history = sorted(st.history + [x for x in h if x["url"] not in seen], key=lambda x: -x.get("t", 0))[:1000]
                    st._write(HIST, st.history)
                    msg.append(f"historia: {len([x for x in h if x['url'] not in seen])} stron")
                except Exception as e:
                    msg.append(f"historia: błąd ({e.__class__.__name__})")
            if self.cb["passwords"].isChecked():
                try:
                    pw, v20 = import_passwords(root, prof)
                    n = self._save_passwords(pw)
                    msg.append(f"hasła: {n} zapisanych")
                    if v20:
                        msg.append(f"{v20} haseł jest zaszyfrowanych tylko dla tamtej przeglądarki (nowy Chrome) – wyeksportuj "
                                   "je tam do pliku CSV (Ustawienia → Hasła → Eksportuj) i użyj „Hasła z pliku CSV…”, potem usuń plik")
                except Exception as e:
                    msg.append(f"hasła: nie udało się odczytać ({e.__class__.__name__})")
        finally:
            QApplication.restoreOverrideCursor()
        self.out.setText(f"{label}: " + "; ".join(msg) + ".")

    def run_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Plik CSV z hasłami", str(HOME), "CSV (*.csv)")
        if not path:
            return
        try:
            n = self._save_passwords(import_passwords_csv(path))
            self.out.setText(f"Zaimportowano hasła z pliku: {n}. Usuń teraz ten plik CSV – zawiera hasła jawnym tekstem.")
        except (OSError, ValueError, UnicodeDecodeError) as e:
            self.out.setText(f"Nie udało się odczytać pliku: {e}")


SPEED_JS = r"""(function(r){var n=0;document.querySelectorAll('video,audio').forEach(function(v){v.playbackRate=r;n++});return n})(%s)"""


# --- kody 2FA (TOTP, RFC 6238 – jak Google Authenticator): klucz Base32 albo adres otpauth:// ---
def totp_code(secret, now=None):
    """(kod, sekundy do zmiany) albo None dla niepoprawnego klucza."""
    import hmac
    import struct
    digits, period, algo = 6, 30, "sha1"
    s = (secret or "").strip()
    if s.lower().startswith("otpauth://"):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(s).query)
        s = (q.get("secret") or [""])[0]
        try:
            digits = int((q.get("digits") or ["6"])[0]); period = int((q.get("period") or ["30"])[0])
        except ValueError:
            return None
        algo = (q.get("algorithm") or ["SHA1"])[0].lower()
    s = s.replace(" ", "").replace("-", "").upper()
    if not s or algo not in ("sha1", "sha256", "sha512") or not (6 <= digits <= 8) or period <= 0:
        return None
    try:
        key = base64.b32decode(s + "=" * (-len(s) % 8))
    except (ValueError, TypeError):
        return None
    if len(key) < 5:
        return None
    t = int(now if now is not None else time.time())
    mac = hmac.new(key, struct.pack(">Q", t // period), getattr(hashlib, algo)).digest()
    o = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[o:o + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits), period - t % period


OTP_FILL_JS = r"""(function(code,fill){var c=[].slice.call(document.querySelectorAll('input')).filter(function(i){
var t=(i.type||'').toLowerCase();if(t==='hidden'||t==='password'||t==='checkbox'||t==='radio'||i.disabled||i.readOnly)return false;var r=i.getBoundingClientRect();if(!r.width||!r.height)return false;
var ac=(i.getAttribute('autocomplete')||'').toLowerCase();var k=(i.name+' '+i.id+' '+(i.placeholder||'')+' '+(i.getAttribute('aria-label')||'')).toLowerCase();
return ac==='one-time-code'||/otp|totp|2fa|mfa|one.?time|verification.?code|auth.?code|security.?code|kod.?(weryf|jednoraz|uwierz|sms|z.?aplik)|(^|\s)code(\s|$)/.test(k)});
if(!c.length)return 0;if(!fill)return c.length;var i=c[0];var d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');d.set.call(i,code);
i.dispatchEvent(new Event('input',{bubbles:true}));i.dispatchEvent(new Event('change',{bubbles:true}));i.focus();return 1})(%s,%s)"""


class CompactHover(QObject):
    """Tryb kompaktowy: pasek narzędzi wysuwa się, gdy mysz jest nad paskiem kart, i chowa 0,7 s po jej zjechaniu
    (nie chowa się przy pisaniu w pasku adresu ani przy otwartym menu). Tylko zdarzenia – bez odpytywania."""

    def __init__(self, browser):
        super().__init__(browser); self.b = browser
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self._maybe_hide)

    def eventFilter(self, obj, ev):
        if self.b.store.settings.get("compact"):
            t = ev.type()
            if t == QEvent.Type.Enter:
                self._t.stop(); self.b._tool.show()
            elif t == QEvent.Type.Leave:
                self.hide_later()
        return False

    def hide_later(self):
        self._t.start(700)

    def _maybe_hide(self):
        b = self.b
        if not b.store.settings.get("compact"):
            return
        under = b._tool.underMouse() or b._strip.underMouse()
        busy = b.address.hasFocus() or QApplication.activePopupWidget() is not None
        if under or busy:
            self._t.start(700); return
        b._tool.hide()


# --- ochrona logowania: domeny udające znane serwisy (literówki, podmienione litery, znak z innego alfabetu,
# marka w subdomenie cudzej domeny). Znane = zapisane w sejfie haseł + popularne serwisy w Polsce i na świecie ---
LOGIN_DOMAINS = {
    "pkobp.pl", "ipko.pl", "mbank.pl", "santander.pl", "ing.pl", "ingbank.pl", "pekao24.pl", "pekao.com.pl", "aliorbank.pl",
    "bankmillennium.pl", "credit-agricole.pl", "bnpparibas.pl", "citibank.pl", "velobank.pl", "nestbank.pl", "bosbank.pl",
    "revolut.com", "paypal.com", "allegro.pl", "olx.pl", "inpost.pl", "poczta-polska.pl", "gov.pl", "podatki.gov.pl",
    "zus.pl", "epuap.gov.pl", "mojeid.pl", "google.com", "gmail.com", "youtube.com", "facebook.com", "instagram.com",
    "microsoft.com", "live.com", "outlook.com", "office.com", "apple.com", "icloud.com", "amazon.com", "amazon.pl",
    "netflix.com", "steampowered.com", "steamcommunity.com", "discord.com", "x.com", "twitter.com", "linkedin.com",
    "github.com", "dropbox.com", "wp.pl", "onet.pl", "interia.pl", "o2.pl", "blik.com", "przelewy24.pl", "payu.pl"}
_CONFUSABLE = str.maketrans({"а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j",
                             "ѕ": "s", "ԁ": "d", "ɡ": "g", "ӏ": "l", "ο": "o", "α": "a", "ν": "v", "ρ": "p", "ι": "i",
                             "κ": "k", "т": "t", "м": "m", "н": "h", "в": "b", "ł": "l"})


def _norm_label(s):
    import unicodedata
    s = s.translate(_CONFUSABLE)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    for a, b in (("rn", "m"), ("vv", "w"), ("0", "o"), ("1", "l"), ("3", "e"), ("5", "s"), ("-", "")):
        s = s.replace(a, b)
    return s


def _lev1(a, b):
    """Odległość edycyjna ≤ 1 (zamiana, wstawienie, usunięcie jednego znaku albo przestawienie sąsiednich)."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        d = [i for i in range(len(a)) if a[i] != b[i]]
        return len(d) == 1 or (len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]])
    if len(a) > len(b):
        a, b = b, a
    for i in range(len(b)):
        if b[:i] + b[i + 1:] == a:
            return True
    return False


def lookalike(host, known):
    """Znana domena, pod którą host się podszywa, albo "" (host bezpieczny lub sam jest znaną domeną)."""
    host = (host or "").lower().strip(".")
    try:
        uni = host.encode("ascii").decode("idna") if "xn--" in host else host
    except UnicodeError:
        uni = host
    reg = base_domain(uni)
    if reg in known or any(host == k or host.endswith("." + k) for k in known):
        return ""
    label, _, tld = reg.partition(".")
    nl = _norm_label(label)
    for k in sorted(known):
        kl, _, ktld = k.partition(".")
        if len(kl) < 4:
            continue
        if uni != host and (nl == _norm_label(kl)) and tld == ktld:   # znak z innego alfabetu (homograf)
            return k
        if ("." + k + ".") in ("." + uni + ".") or (k + "-") in uni or ("-" + k) in uni.split(".")[0]:   # marka w cudzej domenie
            return k
        # literówka / podmienione znaki w tej samej końcówce domeny (ta sama marka w innej końcówce, np. github.io,
        # amazon.de, bywa prawdziwa – nie ostrzegamy)
        if len(kl) >= 5 and tld == ktld and label != kl and (nl == _norm_label(kl) or _lev1(nl, _norm_label(kl))):
            return k
    return ""


# --- „Ukryj ten element”: wskazanie, podświetlenie, selektor CSS (krótki i stabilny), ukrycie ---
PICK_JS = r"""(function(x,y,up){var L=window.__lpick||(window.__lpick={});var el=(x===null)?L.el:document.elementFromPoint(x,y);if(!el)return '';
for(var i=0;i<up&&el.parentElement&&el.parentElement!==document.body&&el.parentElement!==document.documentElement;i++)el=el.parentElement;L.el=el;
function okc(c){return /^[a-zA-Z][\w-]{1,40}$/.test(c)&&!/\d{4,}/.test(c)&&!/^(css|sc|jsx|svelte|ng)-/.test(c)}
function part(e){if(e.id&&/^[a-zA-Z][\w-]{1,40}$/.test(e.id)&&!/\d{3,}/.test(e.id))return '#'+CSS.escape(e.id);var s=e.tagName.toLowerCase();
var c=[].filter.call(e.classList,okc).slice(0,3);if(c.length)s+='.'+c.map(function(z){return CSS.escape(z)}).join('.');return s}
function sel(e){var path=[],n=e;for(var i=0;i<5&&n&&n.nodeType===1&&n!==document.body&&n!==document.documentElement;i++){var p=part(n);path.unshift(p);
var s=path.join(' > ');try{var m=document.querySelectorAll(s);if(m.length===1&&m[0]===e)return s}catch(z){}if(p[0]==='#')break;n=n.parentElement}
var s=path.join(' > ');try{var m=document.querySelectorAll(s);if(m.length<=4)return s}catch(z){}var t=e,k=1;while((t=t.previousElementSibling))if(t.tagName===e.tagName)k++;
path[path.length-1]+=':nth-of-type('+k+')';return path.join(' > ')}
var o=L.ov||(L.ov=document.createElement('div'));o.style.cssText='position:fixed;z-index:2147483647;pointer-events:none;background:rgba(255,92,92,.22);outline:2px solid #ff5c5c;border-radius:3px';
var r=el.getBoundingClientRect();o.style.left=r.left+'px';o.style.top=r.top+'px';o.style.width=r.width+'px';o.style.height=r.height+'px';(document.body||document.documentElement).appendChild(o);
var s=sel(el),n=1;try{n=document.querySelectorAll(s).length}catch(z){}return JSON.stringify({sel:s,w:Math.round(r.width),h:Math.round(r.height),n:n})})(%s,%d)"""
PICK_CANCEL_JS = r"""(function(){var L=window.__lpick;if(L&&L.ov&&L.ov.parentNode)L.ov.parentNode.removeChild(L.ov)})()"""
PICK_HIDE_JS = r"""(function(s){try{document.querySelectorAll(s).forEach(function(e){e.style.setProperty('display','none','important')})}catch(z){}
var L=window.__lpick;if(L&&L.ov&&L.ov.parentNode)L.ov.parentNode.removeChild(L.ov)})(%s)"""

# --- podgląd linku: Shift+klik otwiera stronę w pływającym okienku zamiast nowej karty ---
PEEK_JS = r"""document.addEventListener('click',function(e){if(!e.shiftKey||e.button!==0||e.ctrlKey||e.altKey||e.metaKey)return;
var a=e.target&&e.target.closest&&e.target.closest('a[href]');if(!a||!/^https?:/.test(a.href))return;e.preventDefault();e.stopImmediatePropagation();
console.log('%K%peek:'+a.href)},true);"""


class PeekOverlay(QWidget):
    """Pływające okienko z podglądem linku nad stroną; Esc / klik obok zamyka, przyciski: do karty albo do podziału."""

    def __init__(self, browser):
        super().__init__(browser.centralWidget()); self.b = browser; self.url = ""; self.container = ""
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("PeekOverlay{background:rgba(0,0,0,150);}")
        self.card = QFrame(self); self.card.setObjectName("tabpop")
        sh = QGraphicsDropShadowEffect(self.card); sh.setBlurRadius(40); sh.setOffset(0, 10); sh.setColor(QColor(0, 0, 0, 200))
        self.card.setGraphicsEffect(sh)
        v = QVBoxLayout(self.card); v.setContentsMargins(8, 8, 8, 8); v.setSpacing(6)
        head = QHBoxLayout(); self.title = lbl("", "h3"); head.addWidget(self.title, 1)
        for kind, tip, fn in (("plus", "Otwórz w nowej karcie", self.to_tab), ("split", "Otwórz w podziale ekranu", self.to_split),
                              ("close", "Zamknij podgląd (Esc)", self.close_peek)):
            b = QToolButton(); b.setIcon(glyph(kind)); b.setIconSize(QSize(20, 20)); b.setFixedSize(30, 30); b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(lambda _=False, f=fn: f()); head.addWidget(b)
        v.addLayout(head)
        self.view = None; self._v = v
        QShortcut(QKeySequence("Esc"), self, activated=self.close_peek)
        self.hide()

    def open(self, url, container=""):
        self.url, self.container = url, container
        if self.view is None or self.view.container != container:
            if self.view is not None:
                self.view.deleteLater()
            self.view = WebView(container=container)
            self.view.link_requested.connect(lambda u: self.b.open_url_new_tab(u, self.container))
            self.view.titleChanged.connect(lambda t: self.title.setText(t[:90]))
            self._v.addWidget(self.view, 1)
        self.title.setText(host_of(url)); self.view.setUrl(QUrl(url))
        self.setGeometry(self.parentWidget().rect()); self._place(); self.show(); self.raise_(); self.view.setFocus()

    def _place(self):
        r = self.rect(); w, h = int(r.width() * 0.78), int(r.height() * 0.84)
        self.card.setGeometry((r.width() - w) // 2, (r.height() - h) // 2 + 10, w, h)

    def resizeEvent(self, ev):
        super().resizeEvent(ev); self._place()

    def mousePressEvent(self, ev):
        if not self.card.geometry().contains(ev.position().toPoint()):
            self.close_peek()

    def current_url(self):
        return self.view.url().toString() if self.view is not None and self.view.url().isValid() else self.url

    def close_peek(self):
        self.hide()
        if self.view is not None:
            self.view.setUrl(QUrl("about:blank"))   # zwolnij stronę (dźwięk, pamięć)

    def to_tab(self):
        u = self.current_url(); self.close_peek(); self.b.open_url_new_tab(u, self.container)

    def to_split(self):
        u = self.current_url(); self.close_peek(); self.b.open_in_split(u)


# --- synchronizacja między komputerami: każdy komputer zapisuje własny zaszyfrowany plik w folderze synchronizowanym
# przez OneDrive / Dysk Google / Dropbox, a czyta pliki pozostałych (bez serwera Luny, bez konfliktów zapisu) ---
SYNC_SETTINGS = ["features", "engine", "translate_target", "zoom_sites", "shield_allow", "shield_exc", "adblock_user",
                 "adblock_lists", "dark_except", "workspaces", "containers", "toolbar_pins", "webapps", "phish_trust",
                 "translate_never", "reader", "sleep_after"]
SYNC = []


def sync_touch():
    """Wywoływane przy zapisie danych – zaplanuj wysłanie zmian (20 s ciszy)."""
    if SYNC:
        SYNC[0].touch()


class SyncManager(QObject):
    changed = pyqtSignal()
    DIR = "Luna-sync"

    def __init__(self, store):
        super().__init__(QApplication.instance()); self.store = store
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self.write)
        self.watcher = None; self.remote = {}; self.error = ""; self._applying = False
        st = store.settings.setdefault("sync", {})
        st.setdefault("device", secrets.token_hex(6))
        st.setdefault("name", os.environ.get("COMPUTERNAME", "Ten komputer").title())

    # --- konfiguracja ---
    def cfg(self):
        return self.store.settings.setdefault("sync", {})

    def password(self):
        v = VAULT[0] if VAULT and VAULT[0].available() else None
        return v.data.get("sync_pw", "") if v else ""

    def enabled(self):
        c = self.cfg()
        return bool(c.get("on") and c.get("folder") and os.path.isdir(c["folder"]) and self.password())

    def folder(self):
        return os.path.join(self.cfg()["folder"], self.DIR)

    def start(self):
        if not self.enabled():
            return
        os.makedirs(self.folder(), exist_ok=True)
        if self.watcher is None:
            from PyQt6.QtCore import QFileSystemWatcher
            self.watcher = QFileSystemWatcher(self)
            self.watcher.directoryChanged.connect(lambda _: QTimer.singleShot(1500, self.read_all))
        if self.folder() not in self.watcher.directories():
            self.watcher.addPath(self.folder())
        self.read_all(); self.touch(5000)

    def touch(self, ms=20000):
        if self.enabled() and not self._applying:
            self._t.start(ms)

    # --- dane lokalne ---
    def collections(self):
        v = VAULT[0] if VAULT and VAULT[0].available() else None
        return {"tiles": self.store.items, "bookmarks": Bookmarks.items(), "highlights": Highlights.data(),
                "readlater": [dict(x) for x in ReadLater.get().items], "addresses": v.data.get("addresses", []) if v else [],
                "settings": {k: self.store.settings[k] for k in SYNC_SETTINGS if k in self.store.settings}}

    @staticmethod
    def _hash(x):
        return hashlib.sha1(json.dumps(x, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def _stamp(self, cols):
        """Czas ostatniej zmiany każdej kolekcji (zmiana skrótu = teraz)."""
        state = self.cfg().setdefault("state", {}); now = int(time.time()); out = {}
        for k, val in cols.items():
            h = self._hash(val); s = state.get(k) or {}
            if s.get("hash") != h:
                s = {"hash": h, "mtime": now}; state[k] = s
            out[k] = s["mtime"]
        return out

    def write(self):
        if not self.enabled():
            return
        try:
            cols = self.collections(); mt = self._stamp(cols)
            v = VAULT[0]
            payload = {"v": 1, "device": self.cfg()["device"], "name": self.cfg()["name"], "t": int(time.time()),
                       "cols": cols, "mtime": mt, "logins": v.logins(), "deleted": v.data.get("deleted", {}),
                       "tabs": self._tabs()}
            blob = backup_encrypt(payload, self.password())
            path = os.path.join(self.folder(), self.cfg()["device"] + ".lunasync"); tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(blob)
            os.replace(tmp, path)
            self.cfg()["last_write"] = int(time.time()); self.error = ""; self.store.save_soon()
        except (OSError, ValueError) as e:
            self.error = f"Nie udało się zapisać: {e}"
        self.changed.emit()

    @staticmethod
    def _tabs():
        out = []
        for w in WINDOWS:
            try:
                if not w.private:
                    out += [{"url": d["url"], "title": d.get("title", "")} for d in w.session_data()["tabs"] if d.get("url")]
            except (RuntimeError, AttributeError):
                pass
        return out[:100]

    # --- dane z innych komputerów ---
    def read_all(self):
        if not self.enabled():
            return
        seen = self.cfg().setdefault("seen", {})
        try:
            files = [f for f in os.listdir(self.folder()) if f.endswith(".lunasync") and not f.startswith(self.cfg()["device"])]
        except OSError:
            return
        for f in files:
            p = os.path.join(self.folder(), f)
            try:
                mt = os.stat(p).st_mtime_ns
                if seen.get(f) == mt and f in self.remote:
                    continue
                data = backup_decrypt(open(p, "rb").read(), self.password())
            except ValueError:
                self.error = f"Plik {f}: inne hasło synchronizacji – ustaw to samo hasło na wszystkich komputerach."; continue
            except OSError:
                continue
            seen[f] = mt; self.remote[f] = data
            self.merge(data)
        self.cfg()["last_read"] = int(time.time()); self.store.save_soon(); self.changed.emit()

    def merge(self, r):
        """Kolekcje: nowsza wygrywa w całości. Hasła: wpis po wpisie (nowszy wygrywa), usunięcia przenoszone."""
        self._applying = True
        try:
            state = self.cfg().setdefault("state", {}); cols = r.get("cols") or {}; mts = r.get("mtime") or {}
            local = self.collections(); self._stamp(local)
            changed_settings = False
            for k, val in cols.items():
                if k not in local or int(mts.get(k, 0)) <= int((state.get(k) or {}).get("mtime", 0)):
                    continue
                if k == "tiles":
                    self.store.items = val; self.store.save()
                elif k == "bookmarks":
                    Bookmarks._items = list(val); Bookmarks.add_many([])
                elif k == "highlights":
                    Highlights._data = dict(val); Highlights.save()
                elif k == "readlater":
                    rl = ReadLater.get(); rl.items = list(val); rl.save()
                elif k == "addresses" and VAULT and VAULT[0].available():
                    VAULT[0].data["addresses"] = list(val); VAULT[0].save()
                elif k == "settings":
                    self.store.settings.update({x: y for x, y in val.items() if x in SYNC_SETTINGS}); changed_settings = True
                state[k] = {"hash": self._hash(val), "mtime": int(mts[k])}
            if VAULT and VAULT[0].available():
                self._merge_logins(r.get("logins") or [], r.get("deleted") or {})
            if changed_settings:
                self.store.save_settings(); self.store.features_changed.emit()
        finally:
            self._applying = False

    @staticmethod
    def _merge_logins(remote, rdel):
        v = VAULT[0]; dele = v.data.setdefault("deleted", {}); changed = False
        for k, ts in rdel.items():
            if int(ts) > int(dele.get(k, 0)):
                dele[k] = int(ts); changed = True
        for k, ts in list(dele.items()):
            o, _, u = k.partition("\n")
            x = v.find(o, u)
            if x and int(x.get("ts", 0)) < int(ts):
                v.data["logins"] = [y for y in v.data["logins"] if y is not x]; changed = True
        for x in remote:
            k = x["origin"] + "\n" + x["user"]
            if int(dele.get(k, 0)) >= int(x.get("ts", 0)):
                continue
            cur = v.find(x["origin"], x["user"])
            if cur is None:
                v.data["logins"].append(dict(x)); changed = True
            elif int(x.get("ts", 0)) > int(cur.get("ts", 0)):
                cur.update(x); changed = True
        if changed:
            v.save()

    def other_tabs(self):
        """[(nazwa komputera, czas, [karty])] z innych komputerów."""
        return sorted(((d.get("name", "?"), d.get("t", 0), d.get("tabs", [])) for d in self.remote.values()),
                      key=lambda x: -x[1])


def parse_changes(raw):
    """Wpisy z `git log --format=%h%x1f%cd%x1f%s%x1f%b%x1e` → [{hash, date, title, points}] (punkty z linii „- …”)."""
    out = []
    for rec in raw.split("\x1e"):
        parts = rec.strip("\n").split("\x1f")
        if len(parts) < 4 or not parts[2].strip():
            continue
        points, para = [], []
        for ln in parts[3].splitlines():
            s = ln.strip()
            if not s or s.lower().startswith(("co-authored-by", "signed-off-by")):
                continue
            if ln.startswith("- "):
                points.append(s[2:])
            elif points and ln.startswith("  "):
                points[-1] += " " + s
            else:
                para.append(s)
        out.append({"hash": parts[0].strip(), "date": parts[1].strip(), "title": parts[2].strip(), "points": points,
                    "note": " ".join(para)})
    return out


class WhatsNewDialog(LunaDialog):
    """Co nowego w Lunie: lista zmian z opisów aktualizacji (najnowsze na górze)."""

    def __init__(self, browser, changes, subtitle=""):
        super().__init__(browser, "Co nowego w Lunie", "star", (640, 600), subtitle)
        area = QScrollArea(); area.setWidgetResizable(True); area.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget(); inner.setObjectName("clear"); v = QVBoxLayout(inner); v.setContentsMargins(4, 4, 10, 4); v.setSpacing(6)
        for i, c in enumerate(changes):
            if i:
                v.addSpacing(10)
            card = QFrame(); card.setObjectName("optcard"); cv = QVBoxLayout(card); cv.setContentsMargins(16, 14, 16, 14); cv.setSpacing(6)
            cv.addWidget(lbl(c["date"], "seclabel")); cv.addWidget(lbl(c["title"], "h3", wrap=True))
            for pt in c["points"]:
                row = QHBoxLayout(); row.setSpacing(8); dot = lbl("•", "muted2"); dot.setAlignment(Qt.AlignmentFlag.AlignTop)
                row.addWidget(dot); row.addWidget(lbl(pt, "muted2", wrap=True), 1); cv.addLayout(row)
            if c.get("note") and not c["points"]:
                cv.addWidget(lbl(c["note"], "muted2", wrap=True))
            v.addWidget(card)
        if not changes:
            v.addWidget(EmptyState("star", "Brak opisu zmian", "Ta wersja Luny nie została uruchomiona z repozytorium git."))
        v.addStretch(1); area.setWidget(inner); self.body.addWidget(area, 1)
        self.footer(right=[("Świetnie", self.accept, True)])


class Updater(QObject):
    """Aktualizacje Luny uruchamianej z repozytorium git (python luna.py): w tle `git fetch` (bez okienek logowania),
    a gdy na GitHubie są nowe zmiany – pasek „Dostępna nowa wersja” i aktualizacja jednym kliknięciem (git pull
    --ff-only + ponowne uruchomienie). Logowanie do prywatnego repozytorium: jednorazowo przez Git Credential Manager
    (przycisk w Ustawienia → Aktualizacje), dane logowania przechowuje Windows – Luna ich nie widzi."""
    result = pyqtSignal(dict)
    news = pyqtSignal(list, str)   # zmiany od ostatnio oglądanej wersji, bieżący commit
    EVERY_H = 12

    def changes_since(self, seen, limit=5):
        """W wątku: opisy zmian od commitu `seen` (albo `limit` ostatnich) → sygnał news(lista, HEAD)."""
        if not self.available():
            return
        import threading

        def work():
            try:
                rc, head, _ = self._run(["rev-parse", "HEAD"], timeout=10)
                if rc != 0:
                    return
                fmt = "--format=%h%x1f%cd%x1f%s%x1f%b%x1e"
                rng = [f"{seen}..HEAD", "-n", "30"] if seen else ["-n", str(limit)]
                if seen == head:
                    self.news.emit([], head); return
                rc, out, _ = self._run(["log", fmt, "--date=format:%d.%m.%Y"] + rng, timeout=15)
                if rc != 0 and seen:   # nieznany commit (np. po przepisaniu historii) – kilka ostatnich
                    rc, out, _ = self._run(["log", fmt, "--date=format:%d.%m.%Y", "-n", str(limit)], timeout=15)
                self.news.emit(parse_changes(out) if rc == 0 else [], head)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def __init__(self):
        super().__init__(QApplication.instance())
        self.repo = Path(__file__).resolve().parent
        self.git = self._find_git()
        self.state = {}
        self.busy = False
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(lambda: self.check())

    def available(self):
        return (not getattr(sys, "frozen", False)) and (self.repo / ".git").exists() and bool(self.git)

    @staticmethod
    def _find_git():
        import shutil, glob
        g = shutil.which("git")
        if g:
            return g
        cands = sorted(glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "GitHubDesktop", "app-*",
                                              "resources", "app", "git", "cmd", "git.exe")))
        return cands[-1] if cands else None

    def _run(self, args, interactive=False, timeout=60):
        import subprocess
        env = dict(os.environ)
        if not interactive:
            env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
        flags = 0x08000000 if (sys.platform == "win32" and not interactive) else 0   # CREATE_NO_WINDOW
        p = subprocess.run([self.git, "-C", str(self.repo)] + args, capture_output=True, text=True, env=env,
                           timeout=timeout, creationflags=flags, stdin=subprocess.DEVNULL)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()

    def version(self):
        """„a91ed8e z 06.11.2026” – bieżąca wersja (bez sieci)."""
        if not self.available():
            return ""
        try:
            rc, out, _ = self._run(["log", "-1", "--format=%h %cd", "--date=format:%d.%m.%Y"], timeout=10)
            return out.replace(" ", " z ", 1) if rc == 0 else ""
        except Exception:
            return ""

    def check(self, interactive=False):
        """W wątku: fetch + porównanie z gałęzią na GitHubie. Wynik w sygnale result (wątek GUI)."""
        if self.busy or not self.available():
            return
        self.busy = True
        import threading

        def work():
            st = {"checked": time.time(), "behind": 0, "dirty": False, "error": "", "auth": True}
            try:
                rc, _, err = self._run(["fetch", "--quiet", "origin"], interactive=interactive, timeout=180 if interactive else 60)
                if rc != 0:
                    st["auth"] = not re.search(r"could not read Username|Authentication failed|interactivity|403|401", err, re.I)
                    st["error"] = "brak logowania do GitHuba" if not st["auth"] else (err.splitlines() or ["błąd git"])[-1][:160]
                else:
                    rc, out, _ = self._run(["rev-list", "--count", "HEAD..@{u}"], timeout=20)
                    st["behind"] = int(out) if rc == 0 and out.isdigit() else 0
                    rc, out, _ = self._run(["status", "--porcelain", "--untracked-files=no"], timeout=20)
                    st["dirty"] = rc == 0 and bool([ln for ln in out.splitlines() if not ln.endswith(".pyc")])
                    if st["behind"]:
                        rc, out, _ = self._run(["log", "--format=%s", "HEAD..@{u}", "-n", "5"], timeout=20)
                        st["changes"] = out.splitlines() if rc == 0 else []
            except Exception as e:
                st["error"] = str(e)[:160]
            self.result.emit(st)
        threading.Thread(target=work, daemon=True).start()

    def _done(self, st):
        self.busy = False; self.state = st
        self._t.start(self.EVERY_H * 3600 * 1000)

    def pull(self):
        """git pull --ff-only; (ok, komunikat)."""
        try:
            rc, out, err = self._run(["pull", "--ff-only", "--quiet"], timeout=120)
            return rc == 0, (err or out)[-200:]
        except Exception as e:
            return False, str(e)[:200]


UPDATER = []


def updater():
    if not UPDATER:
        u = Updater(); u.result.connect(u._done); UPDATER.append(u)
    return UPDATER[0]


def restart_luna(browser):
    """Nowy proces Luny (bez okna konsoli) i zamknięcie bieżącego."""
    from PyQt6.QtCore import QProcess
    if getattr(sys, "frozen", False):
        prog, args = sys.executable, sys.argv[1:]
    else:
        exe = Path(sys.executable); w = exe.with_name("pythonw.exe")
        prog, args = (str(w) if w.exists() else str(exe)), [str(Path(sys.argv[0]).resolve())] + sys.argv[1:]
    args = [a for a in args if not a.startswith("--luna-wait=")] + [f"--luna-wait={os.getpid()}"]   # poczeka na ten proces
    QProcess.startDetached(prog, args)
    browser.quit_all()


class TaskManager(LunaDialog):
    """Menedżer zadań Luny: pamięć procesów stron i silnika, uśpij / zamknij / przejdź. Odświeża się tylko, gdy jest otwarty."""

    def __init__(self, browser):
        super().__init__(browser, "Menedżer zadań", "tools", (760, 520),
                         "Pamięć zajmowana przez karty i silnik Luny. Karty tej samej witryny mogą dzielić jeden proces.")
        self.b = browser
        self.tree = QTreeWidget(); self.tree.setObjectName("vtabs"); self.tree.setRootIsDecorated(False)
        self.tree.setHeaderLabels(["Karta", "Stan", "Pamięć"]); self.tree.setIconSize(QSize(16, 16))
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, self.tree.header().ResizeMode.Stretch)
        for c in (1, 2):
            self.tree.header().setSectionResizeMode(c, self.tree.header().ResizeMode.ResizeToContents)
        self.tree.itemDoubleClicked.connect(lambda *_: self.go())
        self.panel(self.tree, "tools")
        self.total = lbl("", "muted2")
        self.b_go, self.b_sleep, self.b_close = self.footer(
            left=[("Przejdź do karty", self.go, True), ("Uśpij", self.sleep), ("Zamknij kartę", self.close_tab)], right=[self.total])
        self.tree.currentItemChanged.connect(lambda *_: self.buttons())
        self.rows = []; self.timer = QTimer(self); self.timer.timeout.connect(self.fill); self.timer.start(2000); self.fill()

    def done(self, r):
        self.timer.stop(); super().done(r)

    @staticmethod
    def mb(n):
        return "–" if n is None else f"{n / 1048576:.0f} MB"

    def fill(self):
        b = self.b; sel = self.rows[self.tree.indexOfTopLevelItem(self.tree.currentItem())] \
            if self.tree.currentItem() is not None and self.tree.indexOfTopLevelItem(self.tree.currentItem()) < len(self.rows) else None
        tabs = [t for w in [b] + [x for x in WINDOWS if isinstance(x, Browser)] for t in w.all_tabs()]
        pids = {}
        for t in tabs:
            for v in t.views():
                try:
                    p = v.page().renderProcessPid()
                except RuntimeError:
                    p = 0
                if p:
                    pids.setdefault(p, set()).add(t)
        mem = {p: proc_memory(p) for p in pids}
        me = os.getpid(); engine = [p for p in child_pids(me) if p not in pids]
        core = sum(x for x in [proc_memory(me)] + [proc_memory(p) for p in engine] if x)
        self.tree.clear(); self.rows = []; total = core
        it = QTreeWidgetItem(["Luna (okno, silnik, grafika)", "", self.mb(core)]); it.setIcon(0, QIcon(logo_pixmap(32)))
        self.tree.addTopLevelItem(it); self.rows.append(None)
        for p, m in mem.items():
            total += m or 0
        for t in tabs:
            ps = {v.page().renderProcessPid() for v in t.views()} - {0}
            if t.asleep or t.pending or not ps:
                state, m = "uśpiona" if (t.asleep or t.pending) else "ekran główny", "0 MB"
            else:
                shared = max(len(pids.get(p, ())) for p in ps)
                state = "aktywna" if t is b.cur() else ("gra dźwięk" if t.audible() else "w tle")
                m = self.mb(sum(mem.get(p) or 0 for p in ps)) + (f"  (wspólnie z {shared - 1})" if shared > 1 else "")
            name = t.title_text or ("Ekran główny" if t.main is None else t.main.url().toString())
            if t.sides:
                name += "  (podzielony ekran)"
            row = QTreeWidgetItem([name, state, m]); row.setIcon(0, tab_icon(t.icon, None, t.asleep or bool(t.pending)))
            self.tree.addTopLevelItem(row); self.rows.append(t)
            if t is sel:
                self.tree.setCurrentItem(row)
        self.total.setText(f"Razem: {self.mb(total)}  ·  procesów stron: {len(pids)}")
        self.buttons()

    def cur_tab(self):
        it = self.tree.currentItem()
        i = self.tree.indexOfTopLevelItem(it) if it is not None else -1
        t = self.rows[i] if 0 <= i < len(self.rows) else None
        return t if t is not None and t.window() is not None else None

    def owner(self, t):
        w = t.window()
        return w if isinstance(w, Browser) else self.b

    def buttons(self):
        t = self.cur_tab(); ok = t is not None
        self.b_go.setEnabled(ok); self.b_close.setEnabled(ok)
        self.b_sleep.setEnabled(ok and not t.asleep and not t.pending and t.main is not None and t is not self.owner(t).cur())

    def go(self):
        t = self.cur_tab()
        if t is not None:
            w = self.owner(t)
            if t.ws != w.ws and w.store.feature("workspaces"):
                w.switch_ws(t.ws)
            w.activate(t); w.raise_(); w.activateWindow()

    def sleep(self):
        t = self.cur_tab()
        if t is not None:
            self.owner(t).sleep_now(t); QTimer.singleShot(300, self.fill)

    def close_tab(self, *_):
        t = self.cur_tab()
        if t is not None:
            self.owner(t).close_tab(t); QTimer.singleShot(300, self.fill)


class DownloadsDialog(LunaDialog):
    """Lista pobranych plików: postęp, otwarcie pliku lub folderu, anulowanie."""

    def __init__(self, browser):
        super().__init__(browser, "Pobrane pliki", "download", (620, 480), f"Folder: {DOWNLOADS[0].folder()}")
        self.dm = DOWNLOADS[0]
        self.list = row_list(); self.list.itemDoubleClicked.connect(lambda _: self.open_file())
        self.list.currentRowChanged.connect(lambda _: self.buttons())
        self.panel(self.list, "download", "Brak pobranych plików", "Pliki pobrane w tej sesji pojawią się tutaj.")
        self.b_open, self.b_show, self.b_cancel, _ = self.footer(
            left=[("Otwórz plik", self.open_file, True), ("Pokaż w folderze", self.open_folder), ("Anuluj pobieranie", self.cancel)],
            right=[("Otwórz folder Pobrane", lambda: self._open(self.dm.folder()))])
        self._icons = QFileIconProvider()
        self.dm.changed.connect(self.fill); self.fill()

    def done(self, r):
        safe_disconnect(self.dm.changed, self.fill); super().done(r)

    def fill(self):
        cur = self.list.currentRow(); self.list.clear()
        S = QWebEngineDownloadRequest.DownloadState
        for req in self.dm.items:
            st = req.state(); tot = req.totalBytes(); got = req.receivedBytes(); prog = None
            if st == S.DownloadInProgress:
                info = (f"{human_size(got)} z {human_size(tot)}" if tot > 0 else human_size(got)) or "zaczynam…"
                side = f"{got * 100 // tot}%" if tot > 0 else ""; prog = got / tot if tot > 0 else 0.0
            else:
                info = {S.DownloadCompleted: "Gotowe", S.DownloadCancelled: "Anulowane",
                        S.DownloadInterrupted: "Przerwane"}.get(st, "")
                side = human_size(tot or got) if st == S.DownloadCompleted else ""
            path = self.dm.path(req)
            ic = self._icons.icon(QFileInfo(path)) if st == S.DownloadCompleted and os.path.exists(path) else glyph("download")
            it = row_item(req.downloadFileName(), info, side, ic, tip=path)
            if prog is not None:
                it.setData(ROW_PROG, prog)
            if st in (S.DownloadCancelled, S.DownloadInterrupted):
                it.setForeground(QColor("#8c8c8c"))
            self.list.addItem(it)
        self.show_empty(not self.dm.items)
        if self.dm.items:
            self.list.setCurrentRow(max(0, min(cur, len(self.dm.items) - 1)))
        self.buttons()

    def buttons(self):
        r = self.sel(); S = QWebEngineDownloadRequest.DownloadState
        self.b_open.setEnabled(r is not None and r.state() == S.DownloadCompleted)
        self.b_cancel.setEnabled(r is not None and r.state() == S.DownloadInProgress)

    def sel(self):
        r = self.list.currentRow()
        return self.dm.items[r] if 0 <= r < len(self.dm.items) else None

    def _open(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_file(self):
        r = self.sel()
        if r is not None and r.state() == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self._open(self.dm.path(r))

    def open_folder(self):
        r = self.sel()
        show_in_folder(self.dm.path(r)) if r is not None else self._open(self.dm.folder())

    def cancel(self):
        r = self.sel()
        if r is not None and r.state() == QWebEngineDownloadRequest.DownloadState.DownloadInProgress:
            r.cancel()


class FindBar(QFrame):
    """Znajdź na stronie (Ctrl+F): liczba trafień, poprzednie / następne, Esc zamyka."""

    def __init__(self, browser):
        super().__init__(); self.b = browser; self.setObjectName("notice"); self.hide()
        h = QHBoxLayout(self); h.setContentsMargins(16, 5, 10, 5); h.setSpacing(6)
        ic = QLabel(); ic.setPixmap(glyph("search", "#ececec").pixmap(18, 18)); h.addWidget(ic)
        self.edit = QLineEdit(); self.edit.setObjectName("splitaddr"); self.edit.setPlaceholderText("Znajdź na stronie…")
        self.edit.setMaximumWidth(340); self.edit.textChanged.connect(lambda _: self.find())
        self.edit.returnPressed.connect(lambda: self.find())
        self.count = lbl("", "muted2"); h.addWidget(self.edit); h.addWidget(self.count); h.addStretch()
        for kind, tip, fn in (("forward", "Następne (Enter)", lambda: self.find()),
                              ("back", "Poprzednie (Shift+Enter)", lambda: self.find(True)), ("close", "Zamknij (Esc)", self.close_bar)):
            b = QToolButton(); b.setIcon(glyph(kind)); b.setIconSize(QSize(16, 16)); b.setFixedSize(26, 26); b.setToolTip(tip)
            b.clicked.connect(lambda _=False, f=fn: f()); h.addWidget(b)
        QShortcut(QKeySequence("Escape"), self.edit, self.close_bar)
        QShortcut(QKeySequence("Shift+Return"), self.edit, lambda: self.find(True))

    def view(self):
        t = self.b.cur()
        return t.web if t is not None and t.web is not None and not t.on_home() else None

    def open(self):
        self.show(); self.edit.setFocus(); self.edit.selectAll()
        if self.edit.text():
            self.find()

    def find(self, back=False):
        v = self.view()
        if v is None:
            self.count.setText("Brak strony"); return
        flags = QWebEnginePage.FindFlag.FindBackward if back else QWebEnginePage.FindFlag(0)

        def res(r):
            n = r.numberOfMatches()
            self.count.setText(f"{r.activeMatch()} z {n}" if n else ("Brak wyników" if self.edit.text() else ""))
        v.page().findText(self.edit.text(), flags, res)

    def close_bar(self):
        v = self.view()
        if v is not None:
            v.page().findText("")
        self.hide()


class HistoryDialog(LunaDialog):
    """Pełna historia (Ctrl+H): wyszukiwanie po tytule i adresie, grupy według dni, otwieranie, kopiowanie i usuwanie wpisów."""
    MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września",
              "października", "listopada", "grudnia"]

    def __init__(self, browser):
        super().__init__(browser, "Historia", "history", (860, 660))
        self.b, self.store = browser, browser.store; self._icons = {}
        self.search = QLineEdit(); self.search.setObjectName("glassin"); self.search.setPlaceholderText("Szukaj w historii (tytuł lub adres)…")
        self.search.setClearButtonEnabled(True); self.search.textChanged.connect(lambda _: self._t.start(150))
        self.head_widget(self.search, True)
        self.count = lbl("", "muted2"); self.body.addWidget(self.count)
        self.list = row_list(True); self.list.itemActivated.connect(lambda it: self.open(it))
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.list.customContextMenuRequested.connect(self.menu)
        self.panel(self.list, "history")
        self.footer(left=[("Otwórz", lambda: [self.open(i) for i in self.selected()], True), ("Usuń zaznaczone", self.remove_selected)],
                    right=[("Wyczyść całą historię…", self.clear_all)])
        QShortcut(QKeySequence("Delete"), self.list, self.remove_selected)
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: (self.search.setFocus(), self.search.selectAll()))
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self.fill)
        self.fill(); self.search.setFocus()

    def day_label(self, t):
        if not t:
            return "Wcześniej"
        d = datetime.fromtimestamp(t).date(); today = date.today()
        if d == today:
            return "Dziś"
        if d == today - timedelta(days=1):
            return "Wczoraj"
        name = f"{d.day} {self.MONTHS[d.month - 1]}"
        return name + (f" {d.year}" if d.year != today.year else "")

    def icon(self, url):
        h = host_of(url)
        if h not in self._icons:
            path = icon_path(url)
            self._icons[h] = QIcon(str(path)) if path.exists() else glyph("app", "#8c8c8c")
        return self._icons[h]

    def fill(self):
        q = self.search.text().strip().lower(); words = q.split()
        self.list.clear(); shown = 0; last = None
        for h in self.store.history:
            hay = (h.get("name", "") + " " + h["url"]).lower()
            if words and not all(w in hay for w in words):
                continue
            day = self.day_label(h.get("t"))
            if day != last:
                self.list.addItem(head_item(day)); last = day
            when = datetime.fromtimestamp(h["t"]).strftime("%H:%M") if h.get("t") else ""
            addr = h["url"].split("://", 1)[-1].rstrip("/")
            self.list.addItem(row_item(h.get("name") or host_of(h["url"]), addr, when, self.icon(h["url"]), h["url"], h["url"]))
            shown += 1
        total = len(self.store.history)
        self.count.setText(f"Znaleziono {shown} z {total}" if q else f"{total} {'strona' if total == 1 else 'stron'} w historii")
        self.count.setVisible(bool(total))
        if q:
            self.show_empty(not shown, "Brak wyników", f"Nic w historii nie pasuje do „{self.search.text().strip()}”.")
        else:
            self.show_empty(not shown, "Historia jest pusta", "Odwiedzone strony pojawią się tutaj, pogrupowane według dni.")

    def selected(self):
        return [i for i in self.list.selectedItems() if i.data(Qt.ItemDataRole.UserRole)]

    def open(self, it, same_tab=False):
        url = it.data(Qt.ItemDataRole.UserRole) if it is not None else None
        if not url:
            return
        if same_tab:
            self.b.cur().go(url)
        else:
            self.b.open_url_new_tab(url)
        self.accept()

    def menu(self, pos):
        it = self.list.itemAt(pos)
        if it is None or not it.data(Qt.ItemDataRole.UserRole):
            return
        if not it.isSelected():
            self.list.clearSelection(); it.setSelected(True)
        url = it.data(Qt.ItemDataRole.UserRole); host = host_of(url); m = QMenu(self)
        m.addAction(glyph("plus"), "Otwórz w nowej karcie", lambda: self.open(it))
        m.addAction(glyph("external"), "Otwórz w bieżącej karcie", lambda: self.open(it, True))
        m.addAction(glyph("copy"), "Kopiuj link", lambda: QGuiApplication.clipboard().setText(url))
        m.addSeparator()
        m.addAction(glyph("trash"), "Usuń z historii", self.remove_selected)
        m.addAction(glyph("trash"), f"Usuń wszystko z {host}", lambda: self.remove(lambda h: host_of(h["url"]) == host))
        m.exec(self.list.viewport().mapToGlobal(pos))

    def remove(self, pred):
        self.store.remove_history(pred); self.fill()

    def remove_selected(self):
        urls = {i.data(Qt.ItemDataRole.UserRole) for i in self.selected()}
        if urls:
            self.remove(lambda h: h["url"] in urls)

    def clear_all(self):
        if luna_confirm(self, "Wyczyścić historię?", "Cała historia przeglądania i sekcja „Ostatnie” zostaną usunięte. "
                        "Tej operacji nie można cofnąć.", "Wyczyść", "trash"):
            self.store.clear_history(); self.fill()


class ClearDataDialog(LunaDialog):
    """Usuń dane przeglądania (Ctrl+Shift+Del): historia, ciasteczka i dane stron, pamięć podręczna, hasła."""

    def __init__(self, browser):
        super().__init__(browser, "Usuń dane przeglądania", "trash", (520, 440),
                         "Wybierz, co usunąć z tego komputera. Tej operacji nie można cofnąć.")
        self.b = browser; self.opts = {}
        for key, text, hint, on in (
                ("history", "Historia przeglądania", "Odwiedzone strony i sekcja „Ostatnie” na ekranie głównym.", True),
                ("cookies", "Ciasteczka i dane stron", "Wylogowuje ze stron – także w kontenerach.", False),
                ("cache", "Obrazy i pliki w pamięci podręcznej", "Strony wczytają się raz trochę wolniej.", True),
                ("passwords", "Zapisane hasła", "Usuwa wszystkie hasła z sejfu Luny.", False)):
            box = QVBoxLayout(); box.setSpacing(0); box.setContentsMargins(0, 0, 0, 4)
            cb = QCheckBox(text); cb.setChecked(on); box.addWidget(cb); self.opts[key] = cb
            h = lbl(hint, "muted", wrap=True); h.setContentsMargins(30, 0, 0, 0); box.addWidget(h); self.body.addLayout(box)
        self.body.addStretch(1)
        self.footer(right=[("Anuluj", self.reject), ("Usuń dane", self.run, True)])

    def run(self):
        profs = [get_profile()] + list(_CONTAINER_PROFILES.values())
        if self.opts["history"].isChecked():
            self.b.store.clear_history()
            for p in profs:
                p.clearAllVisitedLinks()
        if self.opts["cookies"].isChecked():
            for p in profs:
                p.cookieStore().deleteAllCookies()
        if self.opts["cache"].isChecked():
            for p in profs:
                p.clearHttpCache()
        if self.opts["passwords"].isChecked() and VAULT and VAULT[0].available():
            VAULT[0].data["logins"] = []; VAULT[0].save()
        self.b.notice.info("Dane przeglądania zostały usunięte."); self.accept()


class MenuRow(QWidget):
    """Wiersz menu z ikoną, etykietą i własnymi kontrolkami po prawej (Powiększ, Pasek boczny)."""

    def __init__(self, kind, text):
        super().__init__(); self.setObjectName("menurow")
        self.h = QHBoxLayout(self); self.h.setContentsMargins(4, 3, 12, 3); self.h.setSpacing(6)
        ic = QLabel(); ic.setPixmap(glyph(kind).pixmap(18, 18)); ic.setFixedSize(20, 20)
        self.h.addWidget(ic); self.h.addSpacing(2); self.h.addWidget(lbl(text)); self.h.addStretch(1)

    def button(self, text="", kind=None, tip="", fn=None, checked=None):
        b = QToolButton(); b.setObjectName("menuchip"); b.setCursor(Qt.CursorShape.PointingHandCursor)
        if kind:
            b.setIcon(glyph(kind)); b.setIconSize(QSize(16, 16))
        if text:
            b.setText(text)
        if checked is not None:
            b.setCheckable(True); b.setChecked(checked)
        b.setToolTip(tip)
        if fn:
            b.clicked.connect(lambda _=False: fn())
        self.h.addWidget(b)
        return b


class MenuSearch(QFrame):
    """Pierwszy wiersz menu Luny: „Szukaj poleceń i ustawień” – otwiera paletę poleceń (Ctrl+K)."""

    def __init__(self, fn):
        super().__init__(); self.setObjectName("menusearchrow"); self.fn = fn
        self.setCursor(Qt.CursorShape.PointingHandCursor); self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        h = QHBoxLayout(self); h.setContentsMargins(10, 7, 10, 7); h.setSpacing(8)
        ic = QLabel(); ic.setPixmap(glyph("search", "#8c8c8c").pixmap(16, 16)); h.addWidget(ic)
        h.addWidget(lbl("Szukaj poleceń i ustawień…", "muted2"), 1); h.addWidget(lbl("Ctrl+K", "muted"))

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.fn()


def menu_section(menu, text):
    """Podpis grupy w menu (zamiast samej kreski) – łatwiej znaleźć opcję."""
    w = QLabel(text.upper()); w.setObjectName("menusec")
    a = QWidgetAction(menu); a.setDefaultWidget(w); a.setEnabled(False); menu.addAction(a)
    return a


def menu_row_action(menu, row):
    a = QWidgetAction(menu); a.setDefaultWidget(row); menu.addAction(a)
    return a


# ikony, które można przypiąć do paska obok wyszukiwarki (reszta trafia do menu burgera)
TOOL_ITEMS = [("shield", "Blokada reklam i śledzenia"), ("key", "Hasła i aliasy"), ("split", "Podział ekranu"),
              ("reader", "Tryb czytania"), ("star", "Dodaj do ekranu głównego"), ("ai", "Asystent AI"),
              ("apps", "Panel aplikacji (komunikatory)"), ("gear", "Ustawienia")]
TOOL_DEFAULT = ["shield", "key", "reader", "star", "ai", "apps"]
PRIVATE = "__prywatne__"
PRIVACY_URL = "https://z4k0lzakol.github.io/Luna/privacy.html"   # GitHub Pages z folderu docs/ (wymagane przez Google)
ZOOMS = [0.25, 0.33, 0.5, 0.67, 0.75, 0.8, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0, 5.0]
WINDOWS = []   # dodatkowe okna (zwykłe i prywatne) – referencje, żeby nie zniknęły


# Tryb czytania: nakładka w zamkniętym Shadow DOM (style strony jej nie psują), treść wyciągnięta heurystycznie
# (articleBody / <article> / kontener z największą ilością akapitów), bez przeładowania strony. Wywołanie ponowne zamyka.
READER_JS = r"""(function(){
const K = %K%, P = %P%, ID = '__luna_reader';
const say = o => console.log(K + 'reader:' + JSON.stringify(o));
const old = document.getElementById(ID);
if (old && old.__close) { old.__close(); return 'off'; }
const BAD = /comment|share|social|related|promo|advert|sponsor|sidebar|newsletter|subscribe|cookie|consent|footer|navbar|nav-|menu|banner|popup|modal|breadcrumb|recommend|outbrain|taboola|paywall|toolbar/i;
const tl = e => ((e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim()).length;
const cls = e => (e.id || '') + ' ' + (typeof e.className === 'string' ? e.className : '');
function pick() {
  const ab = document.querySelector('[itemprop="articleBody"]');
  if (ab && tl(ab) > 400) return ab;
  const arts = [...document.querySelectorAll('article')].filter(a => tl(a) > 400);
  if (arts.length === 1) return arts[0];
  const sc = new Map();
  for (const p of document.querySelectorAll('p, pre, blockquote')) {
    const t = (p.innerText || '').trim(); if (t.length < 60) continue;
    const s = 1 + Math.min(3, Math.floor(t.length / 100)) + (t.split(',').length - 1) * 0.3;
    let e = p.parentElement, k = 1;
    for (let d = 0; e && d < 3; d++, e = e.parentElement) {
      sc.set(e, (sc.get(e) || 0) + s * k * (BAD.test(cls(e)) ? 0.2 : 1)); k = d === 0 ? 0.5 : 0.33;
    }
  }
  let best = null, bs = 0;
  for (const [e, s] of sc) {
    const links = [...e.querySelectorAll('a')].reduce((n, a) => n + (a.innerText || '').length, 0);
    const v = s * (1 - Math.min(0.9, links / (tl(e) || 1)));
    if (v > bs) { bs = v; best = e; }
  }
  if (bs <= 8) {
    if (arts[0]) return arts[0];
    // stare strony bez <p> (tekst rozdzielony <br>): element z największą ilością własnego tekstu
    let top = null, tn = 0;
    for (const e of document.querySelectorAll('td, div, font, section, main, center, span')) {
      let n = 0;
      for (const ch of e.childNodes) if (ch.nodeType === 3) n += ch.textContent.trim().length;
      if (n > tn) { tn = n; top = e; }
    }
    return tn > 1000 ? top : null;
  }
  // treść podzielona na sekcje (np. dokumentacja): idziemy w górę, dopóki rodzic dokłada akapitów, a nie linków
  const ptext = e => [...e.querySelectorAll('p, pre, blockquote, li')].reduce((n, p) => n + (p.innerText || '').length, 0);
  const ldens = e => [...e.querySelectorAll('a')].reduce((n, a) => n + (a.innerText || '').length, 0) / (tl(e) || 1);
  let pb = ptext(best);
  for (let up = best.parentElement; up && up !== document.body && up !== document.documentElement; up = up.parentElement) {
    const pu = ptext(up);
    if (pu < pb * 1.25 || ldens(up) > 0.35 || BAD.test(cls(up))) break;
    best = up; pb = pu;
  }
  return best;
}
const src = pick();
if (!src) { say({state: 'none'}); return 'none'; }
const all = src.querySelectorAll('*');
if (all.length < 30000) for (const e of all) {      // ukryte elementy i leniwe obrazki – zaznaczamy na oryginale
  const cs = getComputedStyle(e);
  if (cs.display === 'none' || cs.visibility === 'hidden') e.setAttribute('data-luna-x', '1');
  else if (e.tagName === 'IMG') e.setAttribute('data-luna-src', e.currentSrc || e.src || e.dataset.src || e.dataset.lazySrc || '');
}
const c = src.cloneNode(true);
for (const e of all) { e.removeAttribute('data-luna-x'); e.removeAttribute('data-luna-src'); }
c.querySelectorAll('[data-luna-x],script,style,noscript,iframe,form,button,input,select,textarea,nav,aside,footer,object,embed,canvas,dialog,[role="navigation"],[role="complementary"],[aria-hidden="true"]').forEach(e => e.remove());
c.querySelectorAll('*').forEach(e => { if (BAD.test(cls(e)) && (e.textContent || '').length < 1500) e.remove(); });
c.querySelectorAll('svg').forEach(e => { if (!e.closest('figure')) e.remove(); });
const KEEP = {A: ['href'], IMG: ['alt'], TD: ['colspan', 'rowspan'], TH: ['colspan', 'rowspan']};
for (const e of [c, ...c.querySelectorAll('*')]) {
  const s = e.getAttribute('data-luna-src'), h = e.getAttribute('href');
  for (const a of [...e.attributes]) if (!(KEEP[e.tagName] || []).includes(a.name)) e.removeAttribute(a.name);
  if (e.tagName === 'IMG') { if (s) e.setAttribute('src', s); else e.remove(); }
  if (e.tagName === 'A' && h) { try { e.setAttribute('href', new URL(h, location.href).href); } catch (_) {} e.setAttribute('target', '_blank'); }
}
c.querySelectorAll('div, span, section, p').forEach(e => { if (!e.textContent.trim() && !e.querySelector('img, video, picture')) e.remove(); });
const meta = n => (document.querySelector(`meta[property="${n}"], meta[name="${n}"]`) || {}).content || '';
let title = (meta('og:title') || document.title || '').trim();
for (const h of document.querySelectorAll('h1')) {   // nagłówek strony zamiast tytułu z dopiskiem („– Wikipedia, wolna…”)
  const t = (h.textContent || '').replace(/\[[^\]]*\]/g, '').replace(/\s+/g, ' ').trim();   // bez „[edytuj]”
  if (t.length > 2 && t.length < 200 && (!title || title.includes(t))) { title = t; break; }
}
const h1 = c.querySelector('h1');
if (h1 && title && (title.includes(h1.textContent.trim()) || h1.textContent.trim().includes(title))) h1.remove();
const words = (c.textContent.match(/\S+/g) || []).length;
const site = meta('og:site_name') || location.hostname.replace(/^www\./, '');
const author = meta('author');

const host = document.createElement('div'); host.id = ID;
host.style.cssText = 'all:initial !important;position:fixed !important;inset:0 !important;z-index:2147483647 !important;';
const root = host.attachShadow({mode: 'closed'});
const css = `
.wrap{position:fixed;inset:0;overflow:auto;background:#0b0b0b;color:#d4d4d4;font-size:var(--s);line-height:1.72;font-family:var(--f);
  scrollbar-color:#333 transparent;outline:none;-webkit-font-smoothing:antialiased}
.doc{max-width:var(--w);margin:0 auto;padding:76px 28px 140px;box-sizing:border-box}
.meta{color:#7c7c7c;font:13px/1.5 'Segoe UI',system-ui,sans-serif;margin:0 0 14px;letter-spacing:.02em}
h1.t{font-size:1.85em;line-height:1.22;color:#f2f2f2;margin:0 0 30px;font-weight:700}
.body h1,.body h2,.body h3,.body h4,.body h5{color:#ececec;line-height:1.3;margin:1.6em 0 .6em}
.body h1{font-size:1.5em}.body h2{font-size:1.3em}.body h3{font-size:1.12em}
.body p{margin:0 0 1.1em}
.body a{color:#8ab4ff;text-decoration:none;border-bottom:1px solid rgba(138,180,255,.3)}
.body a:hover{border-bottom-color:#8ab4ff}
.body img,.body video,.body picture{max-width:100%;height:auto;border-radius:10px;display:block;margin:1.3em auto}
.body figure{margin:1.4em 0}.body figcaption{color:#8a8a8a;font-size:.8em;text-align:center;margin-top:-.6em}
.body blockquote{border-left:3px solid #343434;margin:1.3em 0;padding:.1em 0 .1em 1.1em;color:#bcbcbc}
.body pre,.body code{font-family:'Cascadia Mono',Consolas,monospace;font-size:.84em;background:#161616;border-radius:6px}
.body code{padding:.1em .35em}.body pre{padding:14px 16px;overflow:auto}.body pre code{padding:0;background:none}
.body table{border-collapse:collapse;width:100%;font-size:.88em;margin:1.2em 0}
.body td,.body th{border:1px solid #262626;padding:6px 9px;text-align:left}
.body ul,.body ol{padding-left:1.4em}.body li{margin:.3em 0}.body hr{border:none;border-top:1px solid #262626;margin:2em 0}
.bar{position:fixed;top:14px;right:22px;display:flex;gap:2px;background:rgba(20,20,20,.94);border:1px solid #262626;border-radius:12px;padding:4px}
.bar button{all:unset;width:32px;height:32px;display:grid;place-items:center;border-radius:8px;cursor:pointer;color:#b8b8b8}
.bar button:hover{background:#262626;color:#fff}
.bar svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.sep{width:1px;background:#2a2a2a;margin:6px 3px}`;
try { const sh = new CSSStyleSheet(); sh.replaceSync(css); root.adoptedStyleSheets = [sh]; }
catch (_) { const st = document.createElement('style'); st.textContent = css; root.appendChild(st); }
const el = (tag, cl, txt) => { const e = document.createElement(tag); if (cl) e.className = cl; if (txt) e.textContent = txt; return e; };
const wrap = el('div', 'wrap'); wrap.tabIndex = -1;
const bar = el('div', 'bar'), doc = el('article', 'doc');
const prefs = {size: +P.size || 19, serif: P.serif !== false, width: +P.width || 720};
const apply = () => {
  wrap.style.setProperty('--s', prefs.size + 'px'); wrap.style.setProperty('--w', prefs.width + 'px');
  wrap.style.setProperty('--f', prefs.serif ? "Georgia,'Times New Roman',serif" : "'Segoe UI',system-ui,sans-serif");
};
const btn = (d, tip, fn) => {
  const b = el('button'); b.title = tip;
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('viewBox', '0 0 24 24');
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'path'); p.setAttribute('d', d); s.appendChild(p); b.appendChild(s);
  b.addEventListener('click', ev => { ev.stopPropagation(); fn(); }); bar.appendChild(b);
};
const save = () => { apply(); say({state: 'on', prefs}); };
btn('M3 18 8 7l5 11M5 14h6M16 12h5', 'Mniejsza czcionka', () => { prefs.size = Math.max(14, prefs.size - 1); save(); });
btn('M3 18 8 7l5 11M5 14h6M16 12h5M18.5 9.5v5', 'Większa czcionka', () => { prefs.size = Math.min(30, prefs.size + 1); save(); });
btn('M5 7V5h14v2M12 5v14M9 19h6', 'Czcionka szeryfowa / bezszeryfowa', () => { prefs.serif = !prefs.serif; save(); });
btn('M4 12h16M7 9l-3 3 3 3M17 9l3 3-3 3', 'Szerokość tekstu', () => {
  const W = [600, 720, 880, 1040]; prefs.width = W[(W.indexOf(prefs.width) + 1) % W.length] || 720; save(); });
bar.appendChild(el('div', 'sep'));
btn('M6 6l12 12M18 6 6 18', 'Zamknij tryb czytania (Esc)', () => close());
const m = [site, author, words ? Math.max(1, Math.round(words / 200)) + ' min czytania' : ''].filter(Boolean).join('  ·  ');
doc.appendChild(el('div', 'meta', m)); if (title) doc.appendChild(el('h1', 't', title));
const body = el('div', 'body'); body.appendChild(c); doc.appendChild(body);
wrap.appendChild(doc); root.appendChild(wrap); root.appendChild(bar);
const de = document.documentElement, bd = document.body, ov = [de.style.overflow, bd ? bd.style.overflow : ''];
const key = ev => { if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); close(); } };
function close() {
  window.removeEventListener('keydown', key, true); host.remove();
  de.style.overflow = ov[0]; if (bd) bd.style.overflow = ov[1]; say({state: 'off'});
}
host.__close = close; apply();
de.appendChild(host); de.style.overflow = 'hidden'; if (bd) bd.style.overflow = 'hidden';
window.addEventListener('keydown', key, true); wrap.focus({preventScroll: true});
say({state: 'on'});
return 'on';
})()"""


PAGE_BG_JS = r"""(function(){
 function bg(e){ if (!e) return ''; var v = getComputedStyle(e).backgroundColor;
   return (v && v !== 'transparent' && !/rgba\([^)]*,\s*0\)$/.test(v)) ? v : ''; }
 return bg(document.body) || bg(document.documentElement) || '';
})()"""


def css_color(v):
    """„rgb(…)” / „rgba(…)” z CSS → QColor; brak tła = kolor podkładu kart Luny (#111111), półprzezroczyste – zmieszane z nim."""
    base = QColor("#111111")
    nums = [float(x) for x in re.findall(r"[\d.]+", v or "")]
    if len(nums) < 3:
        return base
    a = nums[3] if len(nums) > 3 else 1.0
    mix = lambda c, b: int(round(c * a + b * (1 - a)))
    return QColor(mix(nums[0], base.red()), mix(nums[1], base.green()), mix(nums[2], base.blue()))


def status_icon(icon, dot=None):
    """Ikona z kolorową kropką stanu w prawym dolnym rogu (np. konto Google: połączono / logowanie)."""
    S = 44
    pm = QPixmap(S, S); pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.drawPixmap(0, 0, icon.pixmap(S, S))
    if dot:
        p.setPen(QPen(QColor("#111111"), 3)); p.setBrush(QColor(dot)); p.drawEllipse(29, 29, 13, 13)
    p.end()
    return QIcon(pm)


def tab_icon(icon, color=None, asleep=False):
    """Ikona karty: favicon (albo kropka) + kolorowa kropka kontenera; uśpiona karta – przygaszona."""
    S = 32
    pm = QPixmap(S, S); pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if asleep:
        p.setOpacity(0.4)
    if icon is not None and not icon.isNull():
        p.drawPixmap(2, 2, icon.pixmap(28, 28))
    else:
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#5a5a5a")); p.drawEllipse(9, 9, 14, 14)
    p.setOpacity(1.0)
    if color:
        p.setPen(QPen(QColor("#111111"), 2)); p.setBrush(QColor(color)); p.drawEllipse(19, 19, 12, 12)
    p.end()
    return QIcon(pm)


class _DropFilter(QObject):
    """Przyjmuje przeciąganie danego typu na zwykły widżet (np. przycisk) i wywołuje fn() po upuszczeniu."""

    def __init__(self, mime, fn, target):
        super().__init__(target); self.mime, self.fn = mime, fn; target.installEventFilter(self)

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t in (QEvent.Type.DragEnter, QEvent.Type.DragMove) and ev.mimeData().hasFormat(self.mime):
            ev.acceptProposedAction(); return True
        if t == QEvent.Type.Drop and ev.mimeData().hasFormat(self.mime):
            ev.acceptProposedAction(); data = bytes(ev.mimeData().data(self.mime))
            QTimer.singleShot(0, lambda: self.fn(data)); return True
        return False


class _Null:
    """Właściciel zastępczy dla widoku zamkniętej karty: każde odwołanie i wywołanie jest pustą operacją."""
    def __getattr__(self, name):
        return self

    def __call__(self, *a, **k):
        return self

    def __bool__(self):
        return False


_NULL = _Null()


class SplitHandle(QSplitterHandle):
    """Uchwyt podziału: cienka pigułka pośrodku, jaśniejsza pod kursorem; dwuklik wyrównuje strony 50/50."""

    def __init__(self, o, parent):
        super().__init__(o, parent); self.setMouseTracking(True); self._hot = False

    def enterEvent(self, ev):
        self._hot = True; self.update(); super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._hot = False; self.update(); super().leaveEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        s = self.splitter(); n = sum(s.sizes()); s.setSizes([n // 2, n - n // 2])

    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#8a8a8a" if self._hot else "#2e2e2e"))
        w, h = self.width(), self.height()
        if self.orientation() == Qt.Orientation.Horizontal:
            p.drawRoundedRect(QRectF((w - 4) / 2, (h - 40) / 2, 4, 40), 2, 2)
        else:
            p.drawRoundedRect(QRectF((w - 40) / 2, (h - 4) / 2, 40, 4), 2, 2)
        p.end()


class SplitView(QSplitter):
    def __init__(self, o):
        super().__init__(o); self.setObjectName("split"); self.setChildrenCollapsible(False); self.setHandleWidth(10)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def createHandle(self):
        return SplitHandle(self.orientation(), self)


class SplitSide(QFrame):
    """Jedna strona podziału ekranu: cienki nagłówek (ikona, tytuł, akcje) i strona WWW – albo, gdy jeszcze pusta,
    wybór karty do dołączenia / pole adresu. Kliknięcie w stronę czyni ją aktywną (pasek adresu działa na nią)."""

    def __init__(self, tab, view=None):
        super().__init__(); self.tab, self.view = tab, None
        self.setObjectName("splitside"); self.setProperty("active", False); self.setMinimumSize(220, 160)
        self.setAcceptDrops(True)
        v = QVBoxLayout(self); v.setContentsMargins(1, 0, 1, 1); v.setSpacing(0); self.v = v
        head = QWidget(); head.setObjectName("splithead"); head.setFixedHeight(30)
        h = QHBoxLayout(head); h.setContentsMargins(10, 2, 4, 0); h.setSpacing(2)
        self.ic = QLabel(); self.ic.setFixedSize(16, 16); self.ic.setScaledContents(True)
        self.title = QLabel("Nowa strona"); self.title.setObjectName("splittitle")
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        h.addWidget(self.ic); h.addSpacing(6); h.addWidget(self.title, 1)
        self.b_add = self._b(h, "plus", "Dodaj trzecią stronę", lambda: tab.add_side())
        self.b_swap = self._b(h, "swap", "Zamień strony miejscami", lambda: tab.swap_split(self))
        self.b_sync = self._b(h, "scrollsync", "Przewijaj strony razem", lambda: tab.set_scroll_sync(not tab.scroll_sync))
        self.b_turn = self._b(h, "splitv", "Układ pionowy / poziomy", lambda: tab.turn_split())
        self.b_out = self._b(h, "external", "Odłącz do osobnej karty", lambda: tab.detach_side(self))
        self._b(h, "close", "Zamknij tę stronę", lambda: tab.close_side(self))
        v.addWidget(head); self.picker = None
        if view is not None:
            self.set_view(view)
        else:
            self._make_picker()

    def _b(self, h, kind, tip, fn):
        b = QToolButton(); b.setObjectName("splitbtn"); b.setIcon(glyph(kind, "#9a9a9a")); b.setIconSize(QSize(15, 15))
        b.setFixedSize(26, 26); b.setToolTip(tip); b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda: fn()); h.addWidget(b)
        return b

    def mousePressEvent(self, ev):
        self.tab.set_active_side(self); super().mousePressEvent(ev)

    def dragEnterEvent(self, ev):   # karta upuszczona na nagłówek lub pustą stronę podziału
        if ev.mimeData().hasFormat(TAB_MIME):
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        if ev.mimeData().hasFormat(TAB_MIME):
            ev.acceptProposedAction(); t = self.tab.browser.tab_from_mime(ev.mimeData())
            if t is not None:
                QTimer.singleShot(0, lambda: self.tab.adopt_tab(self, t))

    def set_active(self, on):
        if self.property("active") != on:
            self.setProperty("active", on); self.style().unpolish(self); self.style().polish(self)
            self.title.style().unpolish(self.title); self.title.style().polish(self.title)

    def set_view(self, view):
        if self.picker is not None:
            self.picker.deleteLater(); self.picker = None
        self.view = view; view.setParent(self); self.v.addWidget(view, 1); view.show()
        self.refresh()

    def take_view(self):
        w, self.view = self.view, None
        if w is not None:
            self.v.removeWidget(w); w.setParent(None)
        return w

    def refresh(self):
        w = self.view
        t = (w.title() or host_of(w.url().toString())) if w is not None else ""
        self.title.setText(t or "Nowa strona"); self.title.setToolTip(t)
        ic = w.icon() if w is not None else QIcon()
        self.ic.setPixmap((ic if not ic.isNull() else glyph("app", "#6f6f6f")).pixmap(32, 32))
        sides = self.tab.sides or []
        i = sides.index(self) if self in sides else 0; j = i + 1 if i + 1 < len(sides) else i - 1
        self.b_swap.setEnabled(0 <= j < len(sides) and self.view is not None and sides[j].view is not None)
        self.b_swap.setToolTip("Zamień strony miejscami" if len(sides) < 3 else
                               ("Zamień z prawą stroną" if j > i else "Zamień z lewą stroną"))
        self.b_add.setVisible(len(sides) < Tab.MAX_SIDES and self is sides[-1] if sides else False)
        on = bool(self.tab.scroll_sync)
        self.b_sync.setIcon(glyph("scrollsync", "#ffffff" if on else "#9a9a9a"))
        self.b_sync.setProperty("on", on); self.b_sync.style().unpolish(self.b_sync); self.b_sync.style().polish(self.b_sync)
        self.b_sync.setToolTip("Wspólne przewijanie: włączone (kliknij, aby wyłączyć)" if on else "Przewijaj strony razem")
        vert = self.tab.split is not None and self.tab.split.orientation() == Qt.Orientation.Vertical
        self.b_turn.setIcon(glyph("split" if vert else "splitv", "#9a9a9a")); self.b_out.setVisible(w is not None)

    def _make_picker(self):
        """Pusta strona podziału: pole adresu i lista otwartych kart (wybrana karta przechodzi tu bez przeładowania)."""
        pk = QWidget(); pk.setObjectName("clear"); self.picker = pk
        l = QVBoxLayout(pk); l.setContentsMargins(18, 14, 18, 14); l.setSpacing(10)
        self.addr = QLineEdit(); self.addr.setObjectName("splitaddr"); self.addr.setPlaceholderText("Wpisz adres lub wyszukaj…")
        self.addr.addAction(glyph("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.addr.returnPressed.connect(lambda: self.tab.load_side(self, self.addr.text()) if self.addr.text().strip() else None)
        l.addWidget(self.addr)
        lst = QListWidget(); lst.setObjectName("splitlist"); lst.setIconSize(QSize(16, 16))
        lst.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lst.setTextElideMode(Qt.TextElideMode.ElideRight)
        others = self.tab.browser.split_candidates(self.tab); self.picks = [o for o, _ in others]
        for i, (o, url) in enumerate(others):
            it = QListWidgetItem(tab_icon(o.icon), o.title_text or url); it.setToolTip(url)
            it.setData(Qt.ItemDataRole.UserRole, i); lst.addItem(it)
        lst.itemClicked.connect(lambda it: self.tab.adopt_tab(self, self.picks[it.data(Qt.ItemDataRole.UserRole)]))
        l.addWidget(lbl("Otwarte karty" if others else "Brak innych otwartych kart – wpisz adres powyżej.", "cap"))
        l.addWidget(lst, 1); lst.setVisible(bool(others))
        if not others:
            l.addStretch()
        self.v.addWidget(pk, 1); self.refresh()
        QTimer.singleShot(0, self.addr.setFocus)


class TabPanel(QWidget):
    """Pionowe karty po lewej: pełne tytuły, zwijane grupy (foldery projektów), tylko karty bieżącej przestrzeni."""
    W = 248

    def __init__(self, browser):
        super().__init__(); self.b = browser
        self.setObjectName("tabpanel"); self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(self.W)
        v = QVBoxLayout(self); v.setContentsMargins(8, 10, 8, 8); v.setSpacing(6)
        head = QHBoxLayout(); head.setSpacing(4)
        self.title = lbl("", "cap"); head.addWidget(self.title, 1)
        g = QToolButton(); g.setIcon(glyph("folder")); g.setIconSize(QSize(18, 18)); g.setFixedSize(28, 28)
        g.setToolTip("Nowa grupa z bieżącej karty"); g.clicked.connect(lambda: self.b.group_dialog(self.b.cur()))
        n = QToolButton(); n.setIcon(glyph("plus")); n.setIconSize(QSize(18, 18)); n.setFixedSize(28, 28)
        n.setToolTip("Nowa karta (Ctrl+T) – prawy klik: w kontenerze"); n.clicked.connect(lambda: self.b.new_tab())
        n.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        n.customContextMenuRequested.connect(lambda _: self.b.container_menu(n.mapToGlobal(QPoint(0, n.height()))))
        head.addWidget(g); head.addWidget(n); v.addLayout(head)
        self.tree = QTreeWidget(); self.tree.setObjectName("vtabs"); self.tree.setHeaderHidden(True)
        self.tree.setIndentation(12); self.tree.setIconSize(QSize(16, 16)); self.tree.setRootIsDecorated(True)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree.setTextElideMode(Qt.TextElideMode.ElideRight); self.tree.viewport().setAutoFillBackground(False)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.itemClicked.connect(self._clicked)
        self.tree.itemExpanded.connect(lambda it: self._fold(it, False)); self.tree.itemCollapsed.connect(lambda it: self._fold(it, True))
        v.addWidget(self.tree, 1)
        self.tabs = {}   # id(pozycja) → karta (odbudowywane przy każdej zmianie)

    def rebuild(self):
        b = self.b; self.tree.blockSignals(True); self.tree.clear(); self.tabs = {}; groups = {}; cur = b.cur(); sel = None
        folded = b.store.settings.get("tab_groups", {})
        self.title.setText(b.ws.upper() if b.store.feature("workspaces") else "KARTY")
        for i in range(b.stack.count()):
            t = b.stack.widget(i)
            if not b.in_view(t):
                continue
            parent = self.tree.invisibleRootItem()
            if t.group:
                if t.group not in groups:
                    g = QTreeWidgetItem([t.group]); g.setData(0, Qt.ItemDataRole.UserRole, ("g", t.group))
                    f = g.font(0); f.setBold(True); g.setFont(0, f); g.setIcon(0, glyph("folder", "#9a9a9a"))
                    self.tree.addTopLevelItem(g); groups[t.group] = g
                parent = groups[t.group]
            it = QTreeWidgetItem([t.title_text or "Ekran główny"]); parent.addChild(it)
            it.setIcon(0, tab_icon(t.icon, b.container_color(t.container), t.asleep or t.pending))
            tip = t.title_text or "Ekran główny"
            if t.container:
                tip += f"\nKontener: {b.container_name(t.container)}"
            if t.asleep or t.pending:
                it.setForeground(0, QColor("#6f6f6f")); tip += "\nUśpiona – wybudzi się po kliknięciu"
            it.setToolTip(0, tip); self.tabs[id(it)] = t
            if t is cur:
                sel = it
        for name, g in groups.items():
            g.setText(0, f"{name}  ·  {g.childCount()}"); g.setExpanded(not folded.get(name, False))
        if sel is not None:
            self.tree.setCurrentItem(sel)
        self.tree.blockSignals(False)

    def _clicked(self, it, col=0):
        t = self.tabs.get(id(it))
        if t is not None:
            self.b.activate(t)

    def _fold(self, it, folded):
        d = it.data(0, Qt.ItemDataRole.UserRole)
        if d and d[0] == "g":
            self.b.store.settings.setdefault("tab_groups", {})[d[1]] = folded; self.b.store.save_soon()

    def _menu(self, pos):
        it = self.tree.itemAt(pos)
        if it is None:
            return
        gp = self.tree.viewport().mapToGlobal(pos)
        d = it.data(0, Qt.ItemDataRole.UserRole)
        if d and d[0] == "g":
            self.b.group_menu(d[1], gp)
        elif id(it) in self.tabs:
            self.b.tab_menu(self.tabs[id(it)], gp)


class TabPreview(QFrame):
    """Podgląd karty po najechaniu: tytuł, adres/informacje i miniatura zrobiona przy ostatnim opuszczeniu karty."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("tabprev"); self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet("QFrame#tabprev{background:#141414;border:1px solid #2c2c2c;border-radius:10px}"
                           "QLabel{background:transparent}")
        v = QVBoxLayout(self); v.setContentsMargins(10, 8, 10, 10); v.setSpacing(4)
        self.title = lbl("", "h3"); self.info = lbl("", "muted2"); self.img = QLabel()
        for x in (self.title, self.info):
            x.setMaximumWidth(260)
        v.addWidget(self.title); v.addWidget(self.info); v.addWidget(self.img)

    def show_for(self, t, title, info, pos):
        fm = self.title.fontMetrics()
        self.title.setText(fm.elidedText(title, Qt.TextElideMode.ElideRight, 260))
        self.info.setText("\n".join(self.info.fontMetrics().elidedText(x, Qt.TextElideMode.ElideRight, 260) for x in info if x))
        self.info.setVisible(bool(self.info.text()))
        th = getattr(t, "thumb", None)
        self.img.setVisible(th is not None and not th.isNull())
        if th is not None:
            self.img.setPixmap(th)
        self.adjustSize(); self.move(pos); self.show()


class TabSearch(QFrame):
    """Szybkie wyszukiwanie kart (Ctrl+Shift+Spacja): kilka liter → Enter przenosi do karty, także z innej przestrzeni."""

    def __init__(self, browser):
        super().__init__(browser, Qt.WindowType.Popup); self.b = browser
        self.setObjectName("tabpop"); self.setFixedWidth(560)
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10); v.setSpacing(8)
        self.edit = QLineEdit(); self.edit.setObjectName("splitaddr"); self.edit.setPlaceholderText("Szukaj w otwartych kartach…")
        self.edit.addAction(glyph("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.edit.textChanged.connect(self.fill); self.edit.installEventFilter(self)
        self.list = QListWidget(); self.list.setObjectName("splitlist"); self.list.setIconSize(QSize(16, 16))
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.list.itemActivated.connect(self.choose); self.list.itemClicked.connect(self.choose)
        v.addWidget(self.edit); v.addWidget(self.list)
        self.tabs = []

    def open(self):
        self.edit.clear(); self.fill("")
        g = self.b.geometry(); self.move(g.x() + (g.width() - self.width()) // 2, g.y() + 90)
        self.show(); self.edit.setFocus()

    def fill(self, q):
        b = self.b; words = q.lower().split(); self.list.clear(); self.tabs = []
        multi = b.store.feature("workspaces") and len(b.workspaces()) > 1
        for t in b.all_tabs():
            url = t.pending or (t.main.url().toString() if t.main is not None and not t.on_home() else "")
            title = t.title_text or ("Ekran główny" if not url else url)
            hay = f"{title} {url} {t.ws} {t.group}".lower()
            if words and not all(w in hay for w in words):
                continue
            extra = "  ·  ".join(x for x in (host_of(url), t.ws if multi else "", t.group) if x)
            it = QListWidgetItem(tab_icon(t.icon, b.container_color(t.container), t.asleep or bool(t.pending)),
                                 title + (f"      {extra}" if extra else ""))
            it.setToolTip(url or title); self.list.addItem(it); self.tabs.append(t)
            if t is b.cur():
                f = it.font(); f.setBold(True); it.setFont(f)
        self.list.setCurrentRow(0 if self.tabs else -1)
        rows = min(10, max(1, self.list.count()))
        self.list.setFixedHeight(rows * 34 + 6); self.adjustSize()

    def eventFilter(self, obj, ev):
        if obj is self.edit and ev.type() == QEvent.Type.KeyPress:
            k = ev.key(); n = self.list.count()
            if k in (Qt.Key.Key_Down, Qt.Key.Key_Up) and n:
                self.list.setCurrentRow((self.list.currentRow() + (1 if k == Qt.Key.Key_Down else -1)) % n); return True
            if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                it = self.list.currentItem()
                if it is not None:
                    self.choose(it)
                return True
        return super().eventFilter(obj, ev)

    def choose(self, it):
        i = self.list.row(it)
        if 0 <= i < len(self.tabs):
            t = self.tabs[i]; self.hide()
            if t in self.b.all_tabs():
                if t.ws != self.b.ws and self.b.store.feature("workspaces"):
                    self.b.switch_ws(t.ws)
                self.b.activate(t)


def fold(s):
    """Do wyszukiwania: małe litery bez polskich znaków („Tłumacz” ~ „tlumacz”)."""
    import unicodedata
    s = (s or "").lower().replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


class CommandPalette(QFrame):
    """Paleta poleceń (Ctrl+K): jedno pole do szukania poleceń Luny, otwartych kart, historii, kafelków
    i ustawień. Enter wykonuje; tekst bez dopasowań → otwórz adres albo szukaj w sieci."""

    def __init__(self, browser):
        super().__init__(browser, Qt.WindowType.Popup); self.b = browser
        self.setObjectName("tabpop"); self.setFixedWidth(620)
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 10); v.setSpacing(8)
        self.edit = QLineEdit(); self.edit.setObjectName("splitaddr")
        self.edit.setPlaceholderText("Polecenie, karta, strona z historii albo ustawienie…")
        self.edit.addAction(glyph("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.edit.textChanged.connect(self.fill); self.edit.installEventFilter(self)
        self.list = QListWidget(); self.list.setObjectName("splitlist"); self.list.setIconSize(QSize(16, 16))
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.list.itemActivated.connect(self.choose); self.list.itemClicked.connect(self.choose)
        v.addWidget(self.edit); v.addWidget(self.list)
        self.entries, self.shown = [], []

    def open(self):
        self.entries = self.b.palette_entries()
        self.edit.clear(); self.fill("")
        g = self.b.geometry(); self.move(g.x() + (g.width() - self.width()) // 2, g.y() + 80)
        self.show(); self.edit.setFocus()

    def fill(self, q):
        words = fold(q).split(); self.list.clear(); self.shown = []
        scored = []
        for i, e in enumerate(self.entries):
            hay = e["hay"]
            if words and not all(w in hay for w in words):
                continue
            # wyżej: dopasowanie od początku tytułu, polecenia przed kartami przed historią
            title = fold(e["title"])
            score = (0 if words and title.startswith(words[0]) else 1, e["rank"], i)
            scored.append((score, e))
        if not words:
            scored = [s for s in scored if s[1]["kind"] in ("cmd", "tab")]
        scored.sort(key=lambda x: x[0])
        for _, e in scored[:40]:
            text = e["title"] + (f"      {e['sub']}" if e.get("sub") else "")
            it = QListWidgetItem(e["icon"], text); it.setToolTip(e.get("tip") or e["title"])
            self.list.addItem(it); self.shown.append(e)
        if q.strip():
            u = q.strip()
            is_url = ("." in u and " " not in u) or u.startswith(("http://", "https://"))
            it = QListWidgetItem(glyph("external" if is_url else "search"),
                                 ("Otwórz: " if is_url else "Szukaj w sieci: ") + u)
            self.list.addItem(it)
            self.shown.append({"kind": "go", "title": u, "fn": lambda u=u: self.b.palette_go(u)})
        self.list.setCurrentRow(0 if self.shown else -1)
        rows = min(12, max(1, self.list.count()))
        self.list.setFixedHeight(rows * 34 + 6); self.adjustSize()

    def eventFilter(self, obj, ev):
        if obj is self.edit and ev.type() == QEvent.Type.KeyPress:
            k = ev.key(); n = self.list.count()
            if k in (Qt.Key.Key_Down, Qt.Key.Key_Up) and n:
                self.list.setCurrentRow((self.list.currentRow() + (1 if k == Qt.Key.Key_Down else -1)) % n); return True
            if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                it = self.list.currentItem()
                if it is not None:
                    self.choose(it)
                return True
        return super().eventFilter(obj, ev)

    def choose(self, it):
        i = self.list.row(it)
        if 0 <= i < len(self.shown):
            e = self.shown[i]; self.hide()
            QTimer.singleShot(0, e["fn"])


# --- „Do przeczytania”: lista stron na później z kopią offline (jeden plik MHTML, otwierany bez internetu) ---
READLATER = HOME / ".luna_do_przeczytania.json"
OFFLINE_DIR = HOME / ".luna_offline"


class ReadLater(QObject):
    changed = pyqtSignal()
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None:
            cls._inst = ReadLater()
        return cls._inst

    def __init__(self):
        super().__init__(QApplication.instance())
        try:
            d = json.loads(READLATER.read_text(encoding="utf-8"))
            self.items = d if isinstance(d, list) else []
        except (OSError, ValueError):
            self.items = []

    def save(self):
        try:
            tmp = READLATER.with_suffix(".tmp"); tmp.write_text(json.dumps(self.items, ensure_ascii=False), encoding="utf-8")
            tmp.replace(READLATER)
        except OSError:
            pass
        self.changed.emit(); sync_touch()

    def find(self, url):
        return next((x for x in self.items if x["url"] == url), None)

    def offline_path(self, it):
        return OFFLINE_DIR / f"{it['id']}.mhtml"

    def add(self, web):
        """Dodaje stronę widoku i zapisuje jej kopię offline. Zwraca wpis."""
        url = web.url().toString(QUrl.UrlFormattingOption.RemoveFragment)
        it = self.find(url)
        if it is None:
            it = {"id": secrets.token_hex(6), "url": url, "title": (web.title() or host_of(url))[:200],
                  "t": int(time.time()), "read": False}
            self.items.insert(0, it)
        else:
            it["read"] = False
        try:
            OFFLINE_DIR.mkdir(exist_ok=True)
            web.page().save(str(self.offline_path(it)), QWebEngineDownloadRequest.SavePageFormat.MimeHtmlSaveFormat)
        except Exception:
            pass
        self.save()
        return it

    def set_read(self, it, read=True):
        it["read"] = bool(read); self.save()

    def remove(self, it):
        self.items = [x for x in self.items if x["id"] != it["id"]]
        try:
            self.offline_path(it).unlink()
        except OSError:
            pass
        self.save()

    def unread(self):
        return [x for x in self.items if not x.get("read")]


class ReadLaterDialog(LunaDialog):
    """Lista „Do przeczytania”: otwórz (online albo kopię offline), oznacz jako przeczytane, usuń."""

    def __init__(self, browser):
        super().__init__(browser, "Do przeczytania", "book", (700, 560),
                         "Strony odłożone na później. Kopia offline (tekst i obrazki, bez skryptów strony) otwiera się "
                         "bez internetu, np. w podróży.")
        self.b = browser; self.rl = ReadLater.get()
        self.list = row_list(); self.list.itemDoubleClicked.connect(lambda _: self.open_sel(False))
        self.list.currentItemChanged.connect(lambda *_: self.buttons())
        self.panel(self.list, "book", "Lista jest pusta",
                   "Dodaj stronę skrótem Ctrl+Shift+O albo z menu: Do przeczytania → Dodaj tę stronę.")
        self.b_open, self.b_off, self.b_read, self.b_rm = self.footer(
            left=[("Otwórz", lambda: self.open_sel(False), True), ("Otwórz offline", lambda: self.open_sel(True)),
                  ("Oznacz jako przeczytane", self.toggle_read)], right=[("Usuń", self.remove_sel)])
        self.fill()

    def fill(self):
        self.list.clear(); last = None
        for it in sorted(self.rl.items, key=lambda x: (bool(x.get("read")), -x.get("t", 0))):
            grp = "Przeczytane" if it.get("read") else "Do przeczytania"
            if grp != last:
                self.list.addItem(head_item(grp)); last = grp
            when = datetime.fromtimestamp(it.get("t", 0)).strftime("%d.%m %H:%M")
            off = self.rl.offline_path(it).exists()
            li = row_item(it["title"], host_of(it["url"]) + ("  ·  kopia offline" if off else ""), when,
                          mini_icon(it["title"], it["url"]), it["id"], it["url"])
            if not it.get("read"):
                f = li.font(); f.setBold(True); li.setFont(f)
            else:
                li.setForeground(QColor("#9a9a9a"))
            self.list.addItem(li)
        self.show_empty(not self.rl.items)
        if self.rl.items and self.list.count() > 1:
            self.list.setCurrentRow(1)
        self.buttons()

    def buttons(self):
        it = self._sel(); ok = it is not None
        for b in (self.b_open, self.b_read, self.b_rm):
            b.setEnabled(ok)
        self.b_off.setEnabled(ok and self.rl.offline_path(it).exists())
        self.b_read.setText("Oznacz jako nieprzeczytane" if ok and it.get("read") else "Oznacz jako przeczytane")

    def _sel(self):
        li = self.list.currentItem(); iid = li.data(Qt.ItemDataRole.UserRole) if li else None
        return next((x for x in self.rl.items if x["id"] == iid), None)

    def open_sel(self, offline):
        it = self._sel()
        if it is None:
            return
        self.b.open_read_later(it, offline); self.fill()

    def toggle_read(self):
        it = self._sel()
        if it is not None:
            self.rl.set_read(it, not it.get("read")); self.fill()

    def remove_sel(self):
        it = self._sel()
        if it is not None:
            self.rl.remove(it); self.fill()


class HighlightsDialog(LunaDialog):
    """Wszystkie zakreślenia i notatki: strona → fragmenty; dwuklik otwiera stronę."""

    def __init__(self, browser):
        super().__init__(browser, "Zakreślenia i notatki", "edit", (720, 580),
                         "Zakreślenia wracają, gdy otworzysz stronę ponownie. Dwuklik otwiera stronę.")
        self.b = browser
        self.tree = row_list(); self.tree.itemDoubleClicked.connect(self._open)
        self.panel(self.tree, "edit", "Brak zakreśleń", "Zaznacz tekst na stronie → prawy przycisk → Zakreśl.")
        self.footer(left=[("Otwórz stronę", lambda: self._open(self.tree.currentItem()), True)],
                    right=[("Usuń zaznaczone", self._remove)])
        self.fill()

    def fill(self):
        self.tree.clear()
        data = Highlights.data()
        for url, items in sorted(data.items(), key=lambda kv: -max((h.get("t", 0) for h in kv[1]), default=0)):
            n = len(items)
            self.tree.addItem(row_item(items[0].get("title") or url, host_of(url),
                                       f"{n} {'zakreślenie' if n == 1 else ('zakreślenia' if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else 'zakreśleń')}",
                                       mini_icon(items[0].get("title") or url, url), (url, None), url))
            for h in items:
                txt = h.get("text", "").replace("\n", " ")
                self.tree.addItem(row_item("„" + txt[:160] + ("…" if len(txt) > 160 else "") + "”", h.get("note", "")[:120], "",
                                           tab_icon(None, h.get("color", "#fff176")), (url, h.get("id")), indent=26))
        self.show_empty(not data)

    def _open(self, it):
        d = it.data(Qt.ItemDataRole.UserRole) if it else None
        if d:
            self.b.open_url_new_tab(d[0]); self.accept()

    def _remove(self):
        it = self.tree.currentItem(); d = it.data(Qt.ItemDataRole.UserRole) if it else None
        if not d:
            return
        url, hid = d
        if hid:
            Highlights.remove(url, hid)
        else:
            Highlights.data().pop(Highlights.key(url), None); Highlights.save()
        self.fill()


class Tab(QStackedWidget):
    """Karta: ekran główny, a po wejściu na stronę – widok WWW (tworzony leniwie). Należy do przestrzeni roboczej,
    opcjonalnie do grupy i kontenera; może mieć podział ekranu (druga strona obok) i może zostać uśpiona."""

    def __init__(self, store, browser, ws="", group="", container=""):
        super().__init__()
        self.browser, self._main = browser, None
        self.ws, self.group, self.container = ws, group, container
        self.title_text, self.icon, self.split, self.sides, self._act = "", None, None, None, 0
        self.asleep, self.pending, self.pending_split, self.last_active = False, "", None, time.time()
        self.pinned = False
        self.scroll_sync = False   # podział ekranu: strony przewijają się razem
        self.home = HomePage(store)
        self.addWidget(self.home)
        self.home.attach_suggest(browser)
        self.home.opened.connect(self.go)

    @property
    def main(self):
        """Główna (lewa / górna) strona karty – od niej karta bierze tytuł i ikonę, ją zapisuje sesja."""
        return self._main

    @property
    def web(self):
        """Strona, na którą działają pasek adresu i przyciski: przy podziale ekranu – aktywna (ostatnio kliknięta);
        gdy aktywna strona podziału jest jeszcze pusta, polecenia (drukuj, powiększ, czytanie…) działają na drugą."""
        if not self.sides:
            return self._main
        v = self.sides[self._act].view if 0 <= self._act < len(self.sides) else None
        return v if v is not None else next((s.view for s in self.sides if s.view is not None), None)

    def side_empty(self):
        """Aktywna strona podziału czeka na wybór (pasek adresu pokazuje wtedy puste pole)."""
        return bool(self.sides) and 0 <= self._act < len(self.sides) and self.sides[self._act].view is None

    def _web_widget(self):
        return self.split if self.split is not None else self._main

    def _new_view(self):
        """Sygnały kierujemy przez v.owner, więc widok można przenieść do innej karty bez przeładowania strony."""
        v = WebView(container=self.container); v.owner = self
        v.link_requested.connect(lambda u, v=v: v.owner.browser.open_url_new_tab(u, v.owner.container))
        v.page().recentlyAudibleChanged.connect(lambda _, v=v: v.owner.browser.audio_changed.emit())
        v.titleChanged.connect(lambda t, v=v: v.owner._view_title(v, t))
        v.urlChanged.connect(lambda u, v=v: v.owner._view_url(v, u))
        v.iconChanged.connect(lambda i, v=v: v.owner._view_icon(v, i))
        v.loadFinished.connect(lambda ok, v=v: v.owner.browser.on_loaded(v.owner, ok, v))
        v.loadStarted.connect(lambda v=v: v.owner.browser.on_load_started(v.owner, v))
        v.urlChanged.connect(lambda u, v=v: v.owner.browser.on_view_url(v, u))   # też nawigacje SPA (YouTube)
        v.page().sb_skipped.connect(lambda d, v=v: v.owner.browser.on_sponsor_skipped(v, d))
        v.page().peek_requested.connect(lambda u, v=v: v.owner.browser.peek(u, v.container))
        v.page().pw_captured.connect(lambda d, v=v: v.owner.browser.on_pw(d))
        v.page().reader_state.connect(lambda d, v=v: v.owner.browser.on_reader(v, d))
        return v

    def _view_title(self, v, t):
        if v is self._main:
            self.browser.on_title(self, t)
        self._side_refresh(v)

    def _view_url(self, v, u):
        if v is self.web and not self.side_empty():
            self.browser.on_url(self, u)
        self._side_refresh(v)

    def _view_icon(self, v, i):
        if v is self._main:
            self.browser.on_icon(self, i)
        self._side_refresh(v)

    def _sync_main(self):
        """Główna strona karty = lewa/górna strona podziału (po podmianie tej strony – nowy tytuł i ikona karty)."""
        if self.sides and self.sides[0].view is not self._main:
            self._main = self.sides[0].view
            if self._main is not None:
                self.browser.on_title(self, self._main.title()); self.browser.on_icon(self, self._main.icon())

    def _side_refresh(self, v):
        for s in self.sides or []:
            if s.view is v:
                s.refresh()

    def go(self, url):
        self.pending = ""
        if self.sides:   # podział ekranu: adres trafia do aktywnej strony
            s = self.sides[self._act]
            if s.view is None:
                self.load_side(s, url)
            else:
                s.view.setUrl(QUrl(normalize(url))); self.setCurrentWidget(self.split)
            self.browser.update_sidebars_soon(); return
        if self._main is None:
            self._main = self._new_view(); self.addWidget(self._main)
        self._main.setUrl(QUrl(normalize(url)))
        self.setCurrentWidget(self._web_widget())
        self.browser.update_sidebars_soon()

    def adopt_view(self, v):
        """Przyjmuje gotową stronę z innej karty (bez przeładowania)."""
        v.owner = self; self._main = v; self.addWidget(v); self.setCurrentWidget(v)
        self.browser.on_title(self, v.title()); self.browser.on_icon(self, v.icon())

    def show_home(self):
        self.setCurrentWidget(self.home)
        self.browser.update_sidebars_soon()

    def show_web(self):
        if self._web_widget() is not None:
            self.setCurrentWidget(self._web_widget())

    def on_home(self):
        return self.currentWidget() is self.home

    # --- podział ekranu (dwie równorzędne strony w jednej karcie) ---
    def split_with(self, url="", vertical=None):
        if self._main is None:
            return
        if self.split is None:
            if vertical is None:   # wąskie okno albo monitor w pionie → strony jedna pod drugą
                vertical = self.width() < self.height() * 0.9
            self.split = SplitView(Qt.Orientation.Vertical if vertical else Qt.Orientation.Horizontal); self.sides = []
            self.removeWidget(self._main)
            a = SplitSide(self, self._main); self.sides.append(a); b = SplitSide(self); self.sides.append(b)
            self.split.addWidget(a); self.split.addWidget(b); self.split.setSizes([10000, 10000])
            self.addWidget(self.split); self._act = -1; self.set_active_side(b)
        if url:
            s = self.sides[1]
            self.load_side(s, url) if s.view is None else s.view.setUrl(QUrl(normalize(url)))
        self.setCurrentWidget(self.split)
        for s in self.sides:
            s.refresh()
        self.browser.sync_address(); self.browser.update_sidebars_soon(); self.browser.decorate(self)

    MAX_SIDES = 3   # podział ekranu: 2 albo 3 strony

    def set_scroll_sync(self, on):
        self.scroll_sync = bool(on) and bool(self.sides)
        for s in self.sides or []:
            if s.view is not None:
                self._scroll_js(s.view)
            s.refresh()

    def _scroll_js(self, v):
        _safe_js(v, SCROLL_SYNC_JS.replace("%K%", json.dumps(PW_KEY)) if self.scroll_sync else SCROLL_SYNC_OFF_JS)

    def sync_scroll_from(self, v, r):
        if not self.scroll_sync or not self.sides:
            return
        r = max(0.0, min(1.0, r))
        for s in self.sides:
            if s.view is not None and s.view is not v:
                _safe_js(s.view, f"window.__lunaSS && window.__lunaSS.set({r:.5f});")

    def add_side(self, url=""):
        """Kolejna (trzecia) strona podziału: pusta (wybór karty / adres) albo od razu z adresem."""
        if self.split is None or not self.sides or len(self.sides) >= self.MAX_SIDES:
            return None
        s = SplitSide(self); self.sides.append(s); self.split.addWidget(s)
        self.split.setSizes([10000] * len(self.sides)); self._act = -1; self.set_active_side(s)
        if url:
            self.load_side(s, url)
        for x in self.sides:
            x.refresh()
        self.browser.sync_address(); self.browser.update_sidebars_soon(); self.browser.decorate(self)
        return s

    def _drop_side(self, side):
        """Usuwa (już pustą) stronę podziału; gdy zostaje jedna strona – koniec podziału."""
        if len(self.sides) <= 2:
            self._dissolve(self._other(side)); return
        i = self.sides.index(side)
        cur = self.sides[self._act] if 0 <= self._act < len(self.sides) else None
        self.sides.remove(side); side.setParent(None); side.deleteLater()
        self.split.setSizes([10000] * len(self.sides))
        self._act = -1; self.set_active_side(cur if cur in self.sides else self.sides[max(0, i - 1)])
        self._sync_main()
        for s in self.sides:
            s.refresh()
        b = self.browser; b.sync_address(); b.decorate(self); b.update_sidebars_soon(); b.update_page_bg()

    def set_active_side(self, side):
        if not self.sides or side not in self.sides:
            return
        i = self.sides.index(side)
        if i != self._act:
            self._act = i
            for k, s in enumerate(self.sides):
                s.set_active(k == i)
            self.browser.split_focus_changed(self)

    def load_side(self, side, url):
        v = self._new_view(); side.set_view(v); v.setUrl(QUrl(normalize(url))); self._sync_main()
        self._act = -1; self.set_active_side(side); v.setFocus()
        for s in self.sides:
            s.refresh()

    def adopt_tab(self, side, o):
        """Przenosi kartę o na wskazaną stronę podziału: ta sama strona, bez przeładowania (inny kontener – wczytuje adres)."""
        b = self.browser
        if not self.sides or side not in self.sides or o is self or o not in b.all_tabs() or o.split is not None:
            return
        url = o.pending or (o.main.url().toString() if o.main is not None and not o.on_home() else "")
        if not url:
            return
        self._clear_side(side)
        if o.main is not None and not o.pending and not o.on_home() and o.container == self.container:
            v = o._main; o.removeWidget(v); o._main = None; v.setParent(None); v.owner = self
            if o.asleep:
                try:
                    v.page().setLifecycleState(QWebEnginePage.LifecycleState.Active)
                except Exception:
                    pass
            side.set_view(v); self._sync_main(); self._act = -1; self.set_active_side(side)
        else:
            self.load_side(side, url)
        b.close_tab(o, remember=False); self.setCurrentWidget(self.split); b.activate(self)
        for s in self.sides:
            s.refresh()
        b.sync_address(); b.decorate(self)

    def _clear_side(self, side):
        """Strona zajęta → jej dotychczasowa zawartość przechodzi do osobnej karty (nic nie ginie)."""
        v = side.take_view()
        if v is not None:
            self._to_new_tab(v)

    def _to_new_tab(self, v):
        b = self.browser
        t2 = b.new_tab(container=self.container, ws=self.ws, group=self.group, activate=False)
        b.bar.moveTab(b.stack.indexOf(t2), b.stack.indexOf(self) + 1); t2.adopt_view(v)
        return t2

    def _other(self, side):
        return self.sides[1] if self.sides[0] is side else self.sides[0]

    def detach_side(self, side):
        if not self.sides or side not in self.sides:
            return
        v = side.take_view(); self._drop_side(side)
        if v is not None:
            self._to_new_tab(v)

    def close_side(self, side):
        if not self.sides or side not in self.sides:
            return
        v = side.take_view(); self._drop_side(side)
        if v is not None:
            v.deleteLater()

    def unsplit(self):
        if self.sides:
            self.close_side(self.sides[-1])

    def _dissolve(self, keep_side):
        sp, keep = self.split, keep_side.take_view()
        if self.scroll_sync and keep is not None:
            _safe_js(keep, SCROLL_SYNC_OFF_JS)
        self.scroll_sync = False
        self.split, self.sides, self._act = None, None, 0
        self.removeWidget(sp); sp.deleteLater(); self._main = keep
        b = self.browser
        if keep is not None:
            self.addWidget(keep); self.setCurrentWidget(keep)
            b.on_title(self, keep.title()); b.on_icon(self, keep.icon()); keep.setFocus()
        else:
            self.title_text, self.icon = "", None; self.show_home()
            b.set_tab_text(self, "Ekran główny")
        b.decorate(self); b.sync_address(); b.update_sidebars_soon(); b.tabs_changed()

    def swap_split(self, side=None):
        """Zamienia stronę miejscami z sąsiednią (przy dwóch stronach – po prostu obie)."""
        if not self.sides:
            return
        i = self.sides.index(side) if side in self.sides else 0
        j = i + 1 if i + 1 < len(self.sides) else i - 1
        if j < 0 or self.sides[i].view is None or self.sides[j].view is None:
            return
        cur = self.sides[self._act] if 0 <= self._act < len(self.sides) else None
        sz = self.split.sizes()
        self.sides[i], self.sides[j] = self.sides[j], self.sides[i]
        for k, s in enumerate(self.sides):
            self.split.insertWidget(k, s)
        self.split.setSizes(sz)
        self._act = self.sides.index(cur) if cur in self.sides else 0; self._main = self.sides[0].view
        self.browser.on_title(self, self._main.title()); self.browser.on_icon(self, self._main.icon())
        self.browser.decorate(self)

    def turn_split(self):
        if self.split is not None:
            h = self.split.orientation() == Qt.Orientation.Horizontal
            self.split.setOrientation(Qt.Orientation.Vertical if h else Qt.Orientation.Horizontal)
            self.split.setSizes([10000] * len(self.sides))
            for s in self.sides:
                s.refresh()

    def split_state(self):
        """Do zapisu sesji: adres drugiej strony i układ (pionowy?)."""
        if self.sides and self.sides[1].view is not None:
            u = self.sides[1].view.url().toString()
            more = [s.view.url().toString() for s in self.sides[2:] if s.view is not None]
            return {"url": u, "more": [m for m in more if m], "v": self.split.orientation() == Qt.Orientation.Vertical} if u else None
        return self.pending_split

    # --- usypianie (zwalnia RAM; strona wczyta się ponownie po powrocie) ---
    def views(self):
        return [w for w in ([s.view for s in self.sides] if self.sides else [self._main]) if w is not None]

    def audible(self):
        return any(w.page().recentlyAudible() for w in self.views())

    def sleep(self):
        if self.asleep or not self.views() or self.audible():
            return
        for w in self.views():
            try:
                w.page().setLifecycleState(QWebEnginePage.LifecycleState.Discarded)
            except Exception:
                return
        self.asleep = True

    def wake(self):
        self.last_active = time.time()
        if self.pending:
            self.go(self.pending)
            ps, self.pending_split = self.pending_split, None
            if isinstance(ps, dict) and ps.get("url"):   # przywrócony podział ekranu z poprzedniej sesji
                self.split_with(ps["url"], bool(ps.get("v")))
                for u in (ps.get("more") or [])[:self.MAX_SIDES - 2]:
                    self.add_side(u)
                if self.sides:
                    self.set_active_side(self.sides[0])
        if self.asleep:
            self.asleep = False
            for w in self.views():
                try:
                    w.page().setLifecycleState(QWebEnginePage.LifecycleState.Active)
                except Exception:
                    pass


class Assistant(QWidget):
    """Panel boczny ze stronami-usługami (własne logowanie, sesja zapamiętana). Bazowo: asystent AI – ChatGPT, Claude,
    Gemini i DeepSeek; podklasa WebAppsPanel używa tego samego układu dla komunikatorów i dowolnych stron."""
    KEY, DEFAULT, ICON_ONLY = "ai_provider", "ChatGPT", False

    def providers(self):
        return PROVIDERS

    def __init__(self, store, browser):
        super().__init__()
        self.store, self.browser = store, browser
        self.views, self.picks = {}, {}
        self.setObjectName("assistant"); self.setFixedWidth(440)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        head = QWidget(); head.setObjectName("aihead")
        h = QVBoxLayout(head); h.setContentsMargins(12, 10, 12, 8); h.setSpacing(6)
        self.pick_row = QHBoxLayout(); self.pick_row.setSpacing(4)
        self.group = QButtonGroup(self); self.group.setExclusive(True)
        self.build_picks()
        h.addLayout(self.pick_row)

        tools = QHBoxLayout(); tools.setSpacing(2)
        self.hint = QLabel(self.hint_text()); self.hint.setObjectName("muted")
        tools.addWidget(self.hint); tools.addStretch()
        for kind, tip, fn in self.tool_defs():
            tb = QToolButton(); tb.setIcon(glyph(kind)); tb.setIconSize(QSize(22, 22)); tb.setFixedSize(30, 30)
            tb.setToolTip(tip); tb.setCursor(Qt.CursorShape.PointingHandCursor)
            tb.clicked.connect(lambda _=False, f=fn: f()); tools.addWidget(tb)
        h.addLayout(tools)
        self.extra_tools(h)
        lay.addWidget(head)

        self.stack = QStackedWidget(); lay.addWidget(self.stack, 1)
        self._ri = QTimer(self); self._ri.setSingleShot(True); self._ri.timeout.connect(self.refresh_icons)
        store.changed.connect(lambda: self._ri.start(400))

    # --- do nadpisania w podklasach ---
    def hint_text(self):
        return "Zaloguj się raz – Luna zapamięta sesję."

    def tool_defs(self):
        return (("key", "Zaloguj linkiem z e-maila (np. Claude) – wklej link, otworzy się tutaj", self.login_link),
                ("reload", "Odśwież", self.reload), ("external", "Otwórz w zwykłej karcie", self.open_tab),
                ("copy", "Skopiuj treść otwartej strony (do wklejenia w czacie)", self.copy_page))

    def provider_for(self, url):
        """Usługa z panelu, do której należy adres (np. link logowania claude.ai → Claude)."""
        dom = base_domain(QUrl(url).host())
        return next((n for n, u in self.providers().items() if dom and base_domain(QUrl(u).host()) == dom), None)

    def open_in_panel(self, url):
        """Otwiera adres w stronie panelu (ta sama sesja co panel) – np. link logowania z e-maila."""
        name = self.provider_for(url) or self.provider()
        if not name:
            return
        self.select(name); v = self.views.get(name)
        if v is not None:
            v.setUrl(QUrl(url))

    def login_link(self):
        """Logowanie linkiem z e-maila (Claude i inne): link otwarty w zwykłej przeglądarce loguje tamtą przeglądarkę,
        więc wklejamy go tutaj – sesja zapisze się w Lunie."""
        clip = QGuiApplication.clipboard().text().strip()
        text = clip if clip.startswith("https://") and " " not in clip and len(clip) < 4000 else ""
        url = luna_prompt(self.window(), "Logowanie linkiem z e-maila",
                          "Poproś usługę o link logowania (np. Claude: „Kontynuuj z e-mailem”), skopiuj link z wiadomości "
                          "(prawy przycisk na przycisku w mailu → Kopiuj adres linku) i wklej go tutaj.", text, "key")
        if url and url.startswith(("https://", "http://")):
            self.open_in_panel(url)

    def extra_tools(self, h):
        """AI znające stronę: podsumowanie, pytania o stronę, porównanie kart (treść trafia do czatu wybranej usługi)."""
        row = QHBoxLayout(); row.setSpacing(4)
        for text, tip, mode in (("Podsumuj stronę", "Wyślij treść bieżącej strony do czatu z prośbą o podsumowanie", "summary"),
                                ("Zapytaj o stronę", "Wklej treść strony do czatu – dopisz swoje pytanie i wyślij", "ask"),
                                ("Porównaj karty", "Porównanie otwartych kart (np. produktów, ofert, artykułów)", "compare")):
            b = QPushButton(text); b.setToolTip(tip); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, m=mode: self.browser.ai_ask(m)); row.addWidget(b)
        row.addStretch(); h.addLayout(row)

    def build_picks(self):
        while self.pick_row.count():
            w = self.pick_row.takeAt(0).widget()
            if w is not None:
                self.group.removeButton(w); w.deleteLater()
        self.picks = {}
        for name, url in self.providers().items():
            b = QToolButton(); b.setObjectName("aipick"); b.setCheckable(True)
            b.setIcon(mini_icon(name, url)); b.setIconSize(QSize(16, 16)); b.setToolTip(name)
            if self.ICON_ONLY:
                b.setFixedSize(34, 30)
            else:
                b.setText(name); b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=name: self.select(n))
            b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda _=None, n=name, b=b: self.pick_menu(n, b))
            self.group.addButton(b); self.pick_row.addWidget(b); self.picks[name] = b
        self.after_picks()
        self.pick_row.addStretch()

    def after_picks(self):
        pass

    def pick_menu(self, name, btn):
        pass

    def release(self):
        """Zwalnia strony z pamięci (po wyłączeniu funkcji)."""
        for v in self.views.values():
            self.stack.removeWidget(v); v.deleteLater()
        self.views.clear()

    def provider(self):
        p = self.store.settings.get(self.KEY, self.DEFAULT)
        provs = self.providers()
        return p if p in provs else (self.DEFAULT if self.DEFAULT in provs else next(iter(provs), ""))

    def refresh_icons(self):
        provs = self.providers()
        for name, b in self.picks.items():
            if name in provs:
                b.setIcon(mini_icon(name, provs[name]))

    def ensure(self):
        """Wywoływane przy otwarciu panelu: ładuje aktualnie wybraną stronę."""
        if self.provider():
            self.select(self.provider())

    def select(self, name):
        provs = self.providers()
        if name not in provs:
            return
        self.store.settings[self.KEY] = name; self.store.save_settings()
        v = self.views.get(name)
        if v is None:
            v = WebView(); v._ready = False
            v.link_requested.connect(self.browser.open_url_new_tab)
            v.loadFinished.connect(lambda ok, v=v: setattr(v, "_ready", True))
            v.setUrl(QUrl(provs[name]))
            self.views[name] = v; self.stack.addWidget(v)
        self.stack.setCurrentWidget(v)
        if name in self.picks:
            self.picks[name].setChecked(True)

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


WEBAPPS_DEFAULT = [["WhatsApp", "https://web.whatsapp.com/"], ["Messenger", "https://www.messenger.com/"],
                   ["Telegram", "https://web.telegram.org/a/"], ["Instagram", "https://www.instagram.com/direct/inbox/"],
                   ["Discord", "https://discord.com/channels/@me"]]
WEBAPPS_ADDED = ["Discord"]   # dopisywane raz do list zapisanych wcześniej (użytkownik może je potem usunąć)


class WebAppsPanel(Assistant):
    """Panel aplikacji (przycisk na pasku jak asystent AI): komunikatory i dowolne strony przypięte z boku.
    Strony działają w tle (powiadomienia o wiadomościach); „Zwolnij pamięć” zamyka wybraną aplikację."""
    KEY, DEFAULT, ICON_ONLY = "webapp_current", "WhatsApp", True

    def providers(self):
        lst = self.store.settings.get("webapps")
        if isinstance(lst, list):
            known = self.store.settings.setdefault("webapps_known", [])
            for name in WEBAPPS_ADDED:
                if name not in known:
                    known.append(name)
                    if not any(x[0] == name for x in lst if isinstance(x, list) and x):
                        lst.append(next(list(x) for x in WEBAPPS_DEFAULT if x[0] == name))
                    self.store.save_soon()
        if not isinstance(lst, list):
            lst = WEBAPPS_DEFAULT
        return {n: u for n, u in lst if isinstance(n, str) and isinstance(u, str)}

    def hint_text(self):
        return "Komunikatory i strony z boku. Prawy przycisk na ikonie: usuń."

    def tool_defs(self):
        return (("reload", "Odśwież", self.reload), ("external", "Otwórz w zwykłej karcie", self.open_tab),
                ("trash", "Zwolnij pamięć tej aplikacji (zamknij ją do następnego kliknięcia)", self.close_current))

    def extra_tools(self, h):
        pass

    def after_picks(self):
        add = QToolButton(); add.setObjectName("aipick"); add.setIcon(glyph("plus")); add.setFixedSize(34, 30)
        add.setToolTip("Dodaj stronę do panelu"); add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.clicked.connect(self.add_app); self.pick_row.addWidget(add)

    def _save(self, provs):
        self.store.settings["webapps"] = [[n, u] for n, u in provs.items()]; self.store.save_soon()

    def add_app(self):
        t = self.browser.cur()
        cur = t.web.url().toString() if t and t.web and not t.on_home() else "https://"
        url, ok = QInputDialog.getText(self, "Dodaj do panelu aplikacji", "Adres strony:", text=cur)
        if not ok or not url.strip():
            return
        url = url.strip() if "://" in url else "https://" + url.strip()
        name, ok = QInputDialog.getText(self, "Dodaj do panelu aplikacji", "Nazwa:", text=host_of(url).split(".")[0].capitalize())
        if not ok or not name.strip():
            return
        provs = self.providers(); provs[name.strip()[:30]] = url; self._save(provs)
        self.build_picks(); self.select(name.strip()[:30])

    def pick_menu(self, name, btn):
        m = QMenu(self)
        m.addAction("Zwolnij pamięć", lambda: self.close_app(name))
        m.addAction("Usuń z panelu", lambda: self.remove_app(name))
        m.exec(QCursor.pos())

    def close_app(self, name):
        v = self.views.pop(name, None)
        if v is not None:
            self.stack.removeWidget(v); v.deleteLater()

    def close_current(self):
        cur = next((n for n, v in self.views.items() if v is self.stack.currentWidget()), None)
        if cur:
            self.close_app(cur)
            QToolTip.showText(QCursor.pos(), f"Zamknięto {cur} – otworzy się ponownie po kliknięciu.", self)

    def remove_app(self, name):
        self.close_app(name)
        provs = self.providers(); provs.pop(name, None); self._save(provs)
        self.build_picks()
        if self.providers():
            self.ensure()


# --- AI znające stronę: treść główna strony (bez menu i stopki), wklejana do czatu wybranej usługi ---
PAGE_TEXT_JS = r"""(function(){var m=document.querySelector('article')||document.querySelector('main,[role=main]')||document.body;
var t=(m&&m.innerText||'').replace(/\n{3,}/g,'\n\n').trim();if(t.length<400&&document.body)t=document.body.innerText.replace(/\n{3,}/g,'\n\n').trim();
return JSON.stringify({title:document.title,url:location.href,text:t.slice(0,%d)})})()"""
CHAT_INPUT_JS = r"""(function(){var c=[].slice.call(document.querySelectorAll('textarea,[contenteditable="true"],[contenteditable=""]')).filter(function(e){
var r=e.getBoundingClientRect();return r.width>80&&r.height>10&&getComputedStyle(e).visibility!=='hidden'&&!e.disabled});
if(!c.length)return false;c.sort(function(a,b){return b.getBoundingClientRect().bottom-a.getBoundingClientRect().bottom});var e=c[0];e.focus();
try{if(e.tagName==='TEXTAREA'){e.setSelectionRange(e.value.length,e.value.length)}else{var s=getSelection(),r=document.createRange();r.selectNodeContents(e);r.collapse(false);s.removeAllRanges();s.addRange(r)}}catch(x){}
return true})()"""
AI_PROMPTS = {
    "summary": "Podsumuj po polsku najważniejsze informacje z poniższej strony: maksymalnie 8 krótkich punktów, a na końcu "
               "jedno zdanie, czy warto przeczytać całość.\n\nStrona: {title}\n{url}\n\n{text}",
    "ask": "Poniżej jest treść strony, którą czytam. Odpowiadaj na moje pytania na jej podstawie, po polsku.\n\n"
           "Strona: {title}\n{url}\n\n{text}\n\nMoje pytanie: ",
    "compare": "Porównaj po polsku poniższe strony (np. produkty, oferty albo artykuły): najważniejsze podobieństwa, różnice "
               "(najlepiej w tabeli) i co polecasz – z krótkim uzasadnieniem.\n\n{pages}",
    "explain": "Wyjaśnij prosto, po polsku, ten fragment ze strony „{title}” ({url}):\n\n„{text}”"}


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


class SplitDropOverlay(QWidget):
    """Podgląd podziału ekranu podczas przeciągania karty z paska: nad stroną widać dwie połowy – ta pod kursorem
    podświetla się z nazwą przeciąganej karty („upuść tutaj”), druga pokazuje obecną stronę. Puszczenie poza
    stroną nic nie zmienia. Przy istniejącym podziale – podświetla stronę podziału, którą karta zastąpi."""

    def __init__(self, browser):
        super().__init__(browser.stack.parentWidget()); self.b = browser
        self.setAcceptDrops(True); self.hide()
        self.T = self.t = None; self.zone = -1; self.msg = ""; self.vertical = False

    def start(self, T, t):
        """T – karta na ekranie (zostanie podzielona), t – przeciągana karta."""
        self.T, self.t, self.zone = T, t, -1
        url = t.pending or (t.main.url().toString() if t.main is not None and not t.on_home() else "")
        self.msg = ""
        if T is None or T is t:
            self.msg = "Przejdź najpierw na kartę, z którą chcesz podzielić ekran"
        elif T.main is None or (T.on_home() and not T.sides):
            self.msg = "Na tej karcie nie ma strony – otwórz stronę, aby podzielić ekran"
        elif not url or t.split is not None:
            self.msg = "Tej karty nie da się dołożyć do podziału" if t.split is not None else "Przeciągana karta nie ma strony"
        self.vertical = bool(T is not None and not T.sides and T.width() < T.height() * 0.9)
        self.setGeometry(self.b.stack.geometry()); self.raise_(); self.show(); self.update()

    def stop(self):
        self.hide(); self.T = self.t = None; self.zone = -1

    def _vert(self):
        T = self.T
        if T is not None and T.sides and T.split is not None:
            return T.split.orientation() == Qt.Orientation.Vertical
        return self.vertical

    def zones(self):
        """Strefy (prostokąt, rodzaj): ("half", i) bez podziału; ("side", i) – zastąp stronę i; ("add", n) – dodaj stronę."""
        r = QRectF(self.rect()).adjusted(12, 12, -12, -12)
        T = self.T; vert = self._vert()
        if T is not None and T.sides and T.split is not None:
            out = []
            for i, s in enumerate(T.sides):
                o = self.mapFromGlobal(s.mapToGlobal(QPoint(0, 0)))
                out.append((QRectF(o.x(), o.y(), s.width(), s.height()).adjusted(6, 6, -6, -6), ("side", i)))
            if len(T.sides) < Tab.MAX_SIDES:   # pasek na końcu: „dodaj jako trzecią stronę”
                last, k = out[-1]
                if vert:
                    hh = max(90.0, r.height() * 0.24)
                    add = QRectF(r.left(), r.bottom() - hh, r.width(), hh)
                    last = QRectF(last.left(), last.top(), last.width(), max(0.0, add.top() - 12 - last.top()))
                else:
                    ww = max(150.0, r.width() * 0.24)
                    add = QRectF(r.right() - ww, r.top(), ww, r.height())
                    last = QRectF(last.left(), last.top(), max(0.0, add.left() - 12 - last.left()), last.height())
                out[-1] = (last, k); out.append((add, ("add", len(T.sides))))
            return out
        if vert:
            h = (r.height() - 12) / 2
            return [(QRectF(r.left(), r.top(), r.width(), h), ("half", 0)), (QRectF(r.left(), r.top() + h + 12, r.width(), h), ("half", 1))]
        w = (r.width() - 12) / 2
        return [(QRectF(r.left(), r.top(), w, r.height()), ("half", 0)), (QRectF(r.left() + w + 12, r.top(), w, r.height()), ("half", 1))]

    def _zone_at(self, pos):
        """Indeks strefy pod kursorem – strefy obejmują całą szerokość/wysokość (bez martwych marginesów: kursor
        wjeżdża od góry, z paska kart); granica między strefami w połowie odstępu."""
        if self.msg or not self.rect().contains(pos):
            return -1
        zs = [z for z, _ in self.zones()]
        vert = self._vert(); c = pos.y() if vert else pos.x()
        best = -1
        for i, z in enumerate(zs):
            if z.isEmpty():
                continue
            lo, hi = (z.top(), z.bottom()) if vert else (z.left(), z.right())
            nxt = next((zs[j] for j in range(i + 1, len(zs)) if not zs[j].isEmpty()), None)
            if nxt is None or c < (hi + ((nxt.top() if vert else nxt.left()))) / 2:
                return i
            best = i
        return best

    def dragEnterEvent(self, ev):
        # wejście trzeba przyjąć zawsze – odrzucone wejście = Qt nie przyśle już ruchów ani upuszczenia
        if ev.mimeData().hasFormat(TAB_MIME):
            ev.acceptProposedAction(); self._move(ev, True)

    def dragMoveEvent(self, ev):
        if ev.mimeData().hasFormat(TAB_MIME):
            self._move(ev)

    def _move(self, ev, enter=False):
        z = self._zone_at(ev.position().toPoint())
        if z >= 0:
            ev.acceptProposedAction()
        elif not enter:
            ev.ignore()
        if z != self.zone:
            self.zone = z; self.update()

    def dragLeaveEvent(self, ev):
        self.zone = -1; self.update()

    def dropEvent(self, ev):
        i = self._zone_at(ev.position().toPoint()); T, t = self.T, self.t
        if i < 0 or T is None or t is None:
            ev.ignore(); return
        z = self.zones()[i][1][1]
        ev.acceptProposedAction(); vert = self.vertical; self.stop()
        QTimer.singleShot(0, lambda: self.b.split_drop(T, t, z, vert))

    @staticmethod
    def _title(tab):
        if tab is None:
            return ""
        return tab.title_text or (host_of(tab.pending) if tab.pending else "Ekran główny")

    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 150))
        f = QFont(self.font()); f.setPixelSize(15); f.setWeight(QFont.Weight.DemiBold)
        small = QFont(self.font()); small.setPixelSize(13)
        if self.msg:
            r = QRectF(self.rect()); box = QRectF(r.center().x() - 240, r.center().y() - 46, 480, 92)
            p.setPen(QPen(QColor("#333333"), 1)); p.setBrush(QColor("#161616")); p.drawRoundedRect(box, 14, 14)
            p.setPen(QColor("#ececec")); p.setFont(f)
            p.drawText(box.adjusted(20, 14, -20, -40), Qt.AlignmentFlag.AlignCenter, "Nie można tu podzielić ekranu")
            p.setPen(QColor("#9a9a9a")); p.setFont(small)
            p.drawText(box.adjusted(20, 44, -20, -12), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.msg)
            return
        split = bool(self.T is not None and self.T.sides)
        names = (["Góra", "Dół"] if self._vert() else ["Lewa strona", "Prawa strona"])
        for i, (z, kind) in enumerate(self.zones()):
            if z.isEmpty():
                continue
            hot = i == self.zone
            if hot:
                p.setPen(QPen(QColor("#ececec"), 2)); p.setBrush(QColor(236, 236, 236, 34))
            else:
                pen = QPen(QColor(255, 255, 255, 60), 1.4); pen.setStyle(Qt.PenStyle.DashLine); p.setPen(pen)
                p.setBrush(QColor(20, 20, 20, 150))
            p.drawRoundedRect(z, 16, 16)
            # treść strefy: ikona, tytuł, podpis
            if hot:
                head = self._title(self.t)
                sub = ("Upuść, aby dodać jako trzecią stronę" if kind[0] == "add" else
                       "Upuść, aby zastąpić tę stronę" if split else "Upuść, aby otworzyć tutaj")
                icon = tab_icon(self.t.icon if self.t else None)
            elif kind[0] == "add":
                head, sub, icon = "Trzecia strona", "Upuść tutaj, aby dodać", glyph("plus", "#ececec")
            elif split:
                side = self.T.sides[kind[1]]; v = side.view
                head, sub = (v.title() if v is not None else "Pusta strona"), "Przeciągnij tutaj, aby zastąpić"
                icon = tab_icon(v.icon() if v is not None else None)
            elif self.zone >= 0:
                head, sub = self._title(self.T), "Obecna strona"
                icon = tab_icon(self.T.icon)
            else:
                head, sub = names[kind[1]], "Przeciągnij kartę na połowę ekranu"
                icon = glyph("split", "#ececec")
            c = z.center(); tile = QRectF(c.x() - 26, c.y() - 58, 52, 52)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#2a2a2a" if hot else "#1c1c1c")); p.drawRoundedRect(tile, 14, 14)
            icon.paint(p, tile.adjusted(14, 14, -14, -14).toRect())
            fm = QFontMetrics(f); w = int(max(60, min(z.width() - 24, 420)))
            p.setFont(f); p.setPen(QColor("#ffffff" if hot else "#c9c9c9"))
            p.drawText(QRectF(c.x() - w / 2, c.y() + 6, w, 24), Qt.AlignmentFlag.AlignCenter, fm.elidedText(head, Qt.TextElideMode.ElideRight, w))
            p.setFont(small); p.setPen(QColor("#b0b0b0" if hot else "#7d7d7d"))
            p.drawText(QRectF(c.x() - w / 2, c.y() + 32, w, 20), Qt.AlignmentFlag.AlignCenter, sub)


class TabBar(QTabBar):
    """Pasek kart: środkowy przycisk myszy zamyka kartę (na pustym miejscu paska – nowa karta)."""
    middle_close = pyqtSignal(int)
    middle_new = pyqtSignal()
    hover_tab = pyqtSignal(int)    # najechanie na kartę (po krótkiej chwili) → podgląd; -1 = koniec
    drag_out = pyqtSignal(int)     # karta wyciągnięta w dół/górę z paska → przeciąganie na stronę lub przestrzeń
    pinned_fn = None   # indeks → czy karta przypięta (wąska, sama ikona)

    def __init__(self):
        super().__init__(); self.setMouseTracking(True); self._hov = -1; self._press_i = -1
        self._ht = QTimer(self); self._ht.setSingleShot(True); self._ht.timeout.connect(lambda: self.hover_tab.emit(self._hov))

    def mouseMoveEvent(self, ev):
        y = ev.position().y()
        if self._press_i >= 0 and ev.buttons() & Qt.MouseButton.LeftButton and (y < -28 or y > self.height() + 28):
            self._press_i = -1
            from PyQt6.QtGui import QMouseEvent   # kończymy wewnętrzne przesuwanie karty, zanim zacznie się przeciąganie
            super().mouseReleaseEvent(QMouseEvent(QEvent.Type.MouseButtonRelease, ev.position(), ev.globalPosition(),
                                                  Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
            self.hover_tab.emit(-1); self.drag_out.emit(self.currentIndex()); return
        i = self.tabAt(ev.position().toPoint())
        if i != self._hov:
            self._hov = i; self.hover_tab.emit(-1)
            if i >= 0 and not (ev.buttons() & Qt.MouseButton.LeftButton):
                self._ht.start(450)
        g = getattr(self, "_grab", None)
        if g is not None and self._press_i >= 0 and ev.buttons() & Qt.MouseButton.LeftButton:
            # przesuwana karta zostaje w obrębie paska: bez tego Qt rysował ją poza paskiem (znikała przy skrajnej prawej)
            x = ev.position().x(); cx = min(max(x, g[0]), self.width() - 1 - g[1])
            if cx != x:
                from PyQt6.QtGui import QMouseEvent
                d = cx - x
                ev = QMouseEvent(ev.type(), QPointF(cx, ev.position().y()), QPointF(ev.globalPosition().x() + d, ev.globalPosition().y()),
                                 ev.button(), ev.buttons(), ev.modifiers())
        super().mouseMoveEvent(ev)

    def leaveEvent(self, ev):
        self._hov = -1; self._ht.stop(); self.hover_tab.emit(-1); super().leaveEvent(ev)

    def event(self, ev):
        if ev.type() == QEvent.Type.ToolTip:   # zamiast dymka – podgląd karty (z tymi samymi informacjami)
            return True
        return super().event(ev)

    CLOSE_W = 26     # krzyżyk 18 px + 8 px odstępu od prawej krawędzi karty
    MAX_W = 194      # jak max-width w arkuszu stylów (190) + marginesy

    def tabSizeHint(self, i):
        s = super().tabSizeHint(i)
        if self.pinned_fn is not None and self.pinned_fn(i):
            return QSize(44, s.height())
        # szerokość z faktycznego tekstu (pogrubionego, jak na aktywnej karcie) + ikona + krzyżyk – bez pustego miejsca
        # między tytułem a krzyżykiem (Qt centrował tekst w nadmiarowej szerokości)
        f = QFont(self.font()); f.setWeight(QFont.Weight.DemiBold)
        tw = QFontMetrics(f).horizontalAdvance(self.tabText(i))
        btn = self.tabButton(i, QTabBar.ButtonPosition.RightSide)
        w = 14 + (22 if not self.tabIcon(i).isNull() else 0) + tw + 8 + (btn.width() if btn is not None else 10) + 4
        return QSize(max(60, min(self.MAX_W, w)), s.height())

    def minimumTabSizeHint(self, i):
        s = super().minimumTabSizeHint(i)
        return QSize(44, s.height()) if self.pinned_fn is not None and self.pinned_fn(i) else s

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.MiddleButton:   # QTabBar ignoruje środkowy przycisk – wciśnięcie trafiało do paska
            ev.accept(); return                          # tytułu (= nowa karta), więc kółko zamykało kartę I otwierało nową
        self._press_i = self.tabAt(ev.position().toPoint()) if ev.button() == Qt.MouseButton.LeftButton else -1
        self._grab = None
        if self._press_i >= 0:   # gdzie chwycono kartę: odstęp kursora od jej lewej i prawej krawędzi
            r = self.tabRect(self._press_i); x = ev.position().x()
            self._grab = (x - r.left(), r.right() - x)
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._press_i = -1
        if ev.button() == Qt.MouseButton.MiddleButton:
            i = self.tabAt(ev.position().toPoint())
            self.middle_close.emit(i) if i >= 0 else self.middle_new.emit()
            ev.accept(); return
        super().mouseReleaseEvent(ev)


class TitleStrip(QWidget):
    """Pasek kart pełni też rolę paska tytułu: przeciąganie okna, dwuklik = maksymalizacja."""
    middle_new = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("strip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.MiddleButton:
            self.middle_new.emit(); return
        h = self.window().windowHandle()
        if ev.button() == Qt.MouseButton.LeftButton and h:
            h.startSystemMove()

    def mouseDoubleClickEvent(self, ev):
        w = self.window()
        w.showNormal() if w.isMaximized() else w.showMaximized()


class Browser(QMainWindow):
    audio_changed = pyqtSignal()   # któraś karta zaczęła/przestała odtwarzać dźwięk
    MIN_CENTER, HARD_CENTER = 480, 300   # minimalna szerokość środka (px) przy automatycznym zwijaniu paneli

    def __init__(self, store=None, private=False):
        super().__init__()
        self.primary, self.private = store is None and not private, private   # główne okno zapisuje sesję kart
        self._was_max, self._zoom_lbl = False, None
        self._laid, self._pinned, self._suggest = False, None, None
        self._prev_tab, self._ws_last, self._last_user, self._pw_pending, self._popup_from = None, {}, {}, None, None
        self._closed = []   # ostatnio zamknięte karty (uśpione widoki z historią) – Ctrl+Shift+T
        self._on_batt = has_battery() and not power_status()[1]
        self.setWindowTitle("Luna – okno prywatne" if private else "Luna"); self.setWindowIcon(app_icon())
        scr = cur_screen().availableGeometry()   # rozmiar w pikselach logicznych (z uwzględnieniem skalowania)
        # okno ~82% ekranu (duże monitory nie dostają „okienka”), małe ekrany – prawie cały ekran
        self.resize(min(1680, int(scr.width() * (0.96 if scr.width() < 1400 else 0.82))),
                    min(1050, int(scr.height() * (0.94 if scr.height() < 800 else 0.86))))
        self.move(scr.center() - self.rect().center())
        self.setMinimumSize(min(560, scr.width()), min(420, scr.height()))
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)  # bez ramki systemowej
        self.store = store or Store()
        if self.primary:
            self._restore_geometry(scr)

        central = Frame(); v = QVBoxLayout(central); self.frame_layout = v
        v.setContentsMargins(5, 5, 5, 5); v.setSpacing(0)

        # --- pasek kart (jednocześnie pasek tytułu) ---
        strip = TitleStrip(); strip.middle_new.connect(lambda: self.mmb_new())
        sl = QHBoxLayout(strip); sl.setContentsMargins(10, 5, 6, 4); sl.setSpacing(6)
        self.bar = TabBar(); self.bar.setExpanding(False); self.bar.setMovable(True); self.bar.setFixedHeight(34)
        self.bar.setDrawBase(False); self.bar.setElideMode(Qt.TextElideMode.ElideRight)
        self.bar.currentChanged.connect(self.on_tab_changed)
        self.bar.tabMoved.connect(self.on_tab_moved)
        self.bar.middle_close.connect(lambda i: self.store.feature("shortcuts") and not self.stack.widget(i).pinned
                                      and self.close_tab(self.stack.widget(i)))   # przypiętej kółko nie zamyka
        self.bar.pinned_fn = lambda i: 0 <= i < self.stack.count() and self.stack.widget(i).pinned
        self._preview = None; self.bar.hover_tab.connect(self._tab_hover)
        self._dragging = None; self.bar.drag_out.connect(self._drag_tab_out)
        self.bar.middle_new.connect(lambda: self.mmb_new())
        self.bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.bar.customContextMenuRequested.connect(self._bar_menu)
        self.logo_btn = QToolButton(); self.logo_btn.setObjectName("logo"); self.logo_btn.setIcon(QIcon(logo_pixmap(44)))
        self.logo_btn.setIconSize(QSize(22, 22)); self.logo_btn.setFixedSize(28, 28)
        self.logo_btn.setCursor(Qt.CursorShape.PointingHandCursor)   # klikalne logo = karty i grupy
        self.logo_btn.setToolTip("Karty i grupy (Ctrl+Shift+A)"); self.logo_btn.clicked.connect(self.toggle_tab_popup)
        sl.addWidget(self.logo_btn); sl.addSpacing(2)
        if private:
            pv = QLabel("  Prywatne  "); pv.setObjectName("privchip"); pv.setToolTip("Okno prywatne: bez historii, ciasteczka "
                                                                                  "znikają po zamknięciu")
            sl.addWidget(pv); sl.addSpacing(4)
        self.ws = self.store.settings.get("ws_current") if self.store.settings.get("ws_current") in self.workspaces() \
            else self.workspaces()[0]
        self.ws_btn = QToolButton(); self.ws_btn.setObjectName("acct"); self.ws_btn.setIcon(glyph("layers"))   # sama ikona, lista po kliknięciu
        self.ws_btn.setIconSize(QSize(18, 18)); self.ws_btn.setFixedSize(30, 30)
        self.ws_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup); self.ws_btn.setToolTip("Przestrzeń robocza")
        self.ws_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        wm = QMenu(self.ws_btn); wm.aboutToShow.connect(self.ws_menu); self.ws_btn.setMenu(wm)
        self.ws_btn.setAcceptDrops(True); self._ws_drop = _DropFilter(TAB_MIME, self._drop_tab_on_ws, self.ws_btn)   # karta → przestrzeń
        sl.addWidget(self.ws_btn); sl.addSpacing(4)
        self.plus_btn = self.btn("plus", "Nowa karta (Ctrl+T) – prawy klik: w kontenerze", self.new_tab, 30)
        self.plus_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.plus_btn.customContextMenuRequested.connect(
            lambda _: self.container_menu(self.plus_btn.mapToGlobal(QPoint(0, self.plus_btn.height()))))
        sl.addWidget(self.bar); sl.addWidget(self.plus_btn)
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
        self.addr_sugg = SuggestController(self.address, self)
        self.address.returnPressed.connect(lambda: self.addr_sugg.hide())
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
        self.shield_btn = self.btn("shield", "Blokada reklam i śledzenia", lambda: None)
        self.key_btn = self.btn("key", "Hasła i aliasy e-mail", lambda: None)
        for b_, fn in ((self.shield_btn, self.shield_menu), (self.key_btn, self.key_menu)):
            b_.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup); b_.setObjectName("acct")
            mm = QMenu(b_); mm.aboutToShow.connect(fn); b_.setMenu(mm); tl.addWidget(b_)
        self.split_btn = self.btn("split", "Podziel ekran (Ctrl+\\)", self.split_current)
        tl.addWidget(self.split_btn)
        self.reader_btn = self.btn("book", "Tryb czytania (F9)", self.toggle_reader)
        tl.addWidget(self.reader_btn)
        self.star_btn = self.btn("star", "Dodaj stronę do ekranu głównego", self.pin_current)
        tl.addWidget(self.star_btn)
        self.ai_btn = self.btn("assistant", "Asystent AI (Ctrl+J)", self.toggle_assistant)
        tl.addWidget(self.ai_btn)
        self.apps_btn = self.btn("chat", "Panel aplikacji: komunikatory i strony z boku (Ctrl+Shift+K)", self.toggle_webapps)
        tl.addWidget(self.apps_btn)
        self.gear_btn = self.btn("gear", "Ustawienia (Ctrl+,)", self.open_settings)
        tl.addWidget(self.gear_btn)
        self.dl_btn = self.btn("menu", "Pobrane pliki", lambda: None)   # pojawia się przy pierwszym pobraniu w tej sesji
        self.dl_btn.setObjectName("acct"); self.dl_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        dmn = QMenu(self.dl_btn); dmn.aboutToShow.connect(self.downloads_menu); self.dl_btn.setMenu(dmn)
        self.dl_btn.setIcon(download_icon()); self.dl_btn.hide(); tl.addWidget(self.dl_btn)
        self._dl_t = QTimer(self); self._dl_t.setSingleShot(True); self._dl_t.timeout.connect(self.update_dl_btn)
        DOWNLOADS[0].changed.connect(self._dl_changed); self.update_dl_btn()
        self.burger =self.btn("menu", "Menu Luny", lambda: None)   # skrajnie po prawej
        self.burger.setObjectName("acct"); self.burger.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        bmn = QMenu(self.burger); bmn.setObjectName("burger"); bmn.aboutToShow.connect(self.burger_menu); self.burger.setMenu(bmn)
        tl.addSpacing(2); tl.addWidget(self.burger)
        self._tool_lay, self._compact = tl, None
        self._dense = [w for w in (tl.itemAt(i).widget() for i in range(tl.count()))
                       if isinstance(w, QToolButton)]
        self.tool_btns = {"shield": self.shield_btn, "key": self.key_btn, "split": self.split_btn, "reader": self.reader_btn,
                          "star": self.star_btn,
                          "ai": self.ai_btn, "apps": self.apps_btn, "gear": self.gear_btn}
        v.addWidget(tool)
        self._strip, self._tool = strip, tool
        self._compact_hover = CompactHover(self)   # tryb kompaktowy: pasek narzędzi wysuwa się po najechaniu na karty
        strip.installEventFilter(self._compact_hover); tool.installEventFilter(self._compact_hover)
        self.notice = NoticeBar(); v.addWidget(self.notice)
        self.find_bar = FindBar(self); v.addWidget(self.find_bar)

        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding); self.stack.setMinimumWidth(0)
        self.bgframe = BgFrame()
        body = QHBoxLayout(self.bgframe); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(0)
        self.host = WidgetHost(self.store, self)
        self._state_cb = lambda st: self.host.set_active(st == Qt.ApplicationState.ApplicationActive)
        QGuiApplication.instance().applicationStateChanged.connect(self._state_cb)
        QApplication.instance().focusChanged.connect(self._focus_changed)   # podział ekranu: aktywna strona = kliknięta
        self.assistant = Assistant(self.store, self); self.assistant.hide()
        self.webapps = WebAppsPanel(self.store, self); self.webapps.hide()
        self.tabpanel = TabPanel(self); self.body = body
        self.tab_popup = QFrame(self, Qt.WindowType.Popup); self.tab_popup.setObjectName("tabpop")   # lista kart z przycisku na pasku
        QVBoxLayout(self.tab_popup).setContentsMargins(1, 1, 1, 1)
        body.addWidget(self.tabpanel); body.addWidget(self.host.left); body.addWidget(self.stack, 1); body.addWidget(self.host.right)
        body.addWidget(self.assistant); body.addWidget(self.webapps)
        v.addWidget(self.bgframe, 1)
        self.setCentralWidget(central)
        # drobne odświeżenia UI z debouncingiem (zdarzeń „changed” jest dużo: ikony, ładowanie stron)
        self._ui_t = QTimer(self); self._ui_t.setSingleShot(True); self._ui_t.timeout.connect(self._ui_refresh)
        self.store.changed.connect(lambda: self._ui_t.start(150))
        self._sb_t = QTimer(self); self._sb_t.setSingleShot(True); self._sb_t.timeout.connect(self.update_sidebars)
        self._tabs_t = QTimer(self); self._tabs_t.setSingleShot(True); self._tabs_t.timeout.connect(self._apply_tabs)
        self._sleep_t = QTimer(self); self._sleep_t.timeout.connect(self._sleep_tick); self._sleep_t.start(60000)
        if self.windowState() & Qt.WindowState.WindowMaximized:   # okno przywrócone jako zmaksymalizowane
            self.frame_layout.setContentsMargins(0, 0, 0, 0); self.max_btn.setIcon(glyph("restore"))
        self.update_engine_ui()
        self.setup_shortcuts()
        if self.store.settings.get("compact"):
            self._tool.hide()
        self.store.features_changed.connect(self.apply_features)
        if self.primary:
            # poprzednie uruchomienie nie zamknęło się poprawnie (awaria, wyłączenie prądu) – zachowaj jego karty
            crashed = bool(self.store.settings.get("running"))
            prev = dict(self.store.settings.get("session") or {})
            self.restore_session()
            self.store.settings["running"] = True; self.store.save_soon()
            if crashed and not self.store.feature("restore_tabs") and prev.get("tabs"):
                n = len(prev["tabs"])
                QTimer.singleShot(800, lambda: self.notice.ask(
                    f"Luna nie zamknęła się poprawnie. Przywrócić karty z poprzedniej sesji ({n})?",
                    [("Przywróć karty", lambda: self.restore_session(prev), True), ("Nie", None, False)], icon="reload"))
        else:
            self.new_tab()
        DOWNLOADS[0].started.connect(self.on_download)
        self.apply_features(); self.host.sync()
        if SHIELD:
            QTimer.singleShot(8000, SHIELD[0].maybe_update)   # lista domen raz w tygodniu, po starcie
        if self.primary and not SYNC:
            SYNC.append(SyncManager(self.store)); QTimer.singleShot(5000, SYNC[0].start)
        up = updater()
        up.result.connect(self.on_update_result)
        if self.primary and len(WINDOWS) <= 1 and up.available():   # po aktualizacji: „Co nowego” (raz na wersję)
            up.news.connect(self._startup_news)
            QTimer.singleShot(3000, lambda: up.changes_since(self.store.settings.get("seen_head", "")))
        if len(WINDOWS) <= 1 and self.store.feature("updates") and up.available() and not up.state:
            QTimer.singleShot(20000, lambda: self.store.feature("updates") and up.check())   # po starcie, w tle
        self.store.ensure_fonts()

    def _startup_news(self, changes, head):
        up = updater(); safe_disconnect(up.news, self._startup_news)
        first = not self.store.settings.get("seen_head")
        self.store.settings["seen_head"] = head; self.store.save_settings()
        if changes and not first:   # pierwsze uruchomienie – tylko zapamiętujemy wersję
            n = len(changes)
            self.notice.ask(f"Luna została zaktualizowana – {n} {'nowa zmiana' if n == 1 else ('nowe zmiany' if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else 'nowych zmian')}.",
                            [("Co nowego?", lambda: WhatsNewDialog(self, changes, up.version()).exec(), True), ("Później", None, False)],
                            icon="star")

    def show_whats_new(self):
        up = updater()
        if not up.available():
            WhatsNewDialog(self, []).exec(); return

        def got(changes, head):
            safe_disconnect(up.news, got); WhatsNewDialog(self, changes, f"Ostatnie zmiany  ·  wersja {up.version()}").exec()
        up.news.connect(got); up.changes_since("", 6)

    # --- położenie okna między uruchomieniami (dopasowane do aktualnych monitorów) ---
    def _restore_geometry(self, scr):
        g = self.store.settings.get("window")
        if not isinstance(g, dict):
            if scr.width() < 1280 or scr.height() < 720:   # mały ekran laptopa: od razu cały ekran
                self.setWindowState(Qt.WindowState.WindowMaximized)
            return
        try:
            r = QRect(int(g["x"]), int(g["y"]), int(g["w"]), int(g["h"]))
        except (KeyError, TypeError, ValueError):
            r = None
        s = QGuiApplication.screenAt(r.center()) if r is not None else None
        if s is not None:   # monitor odłączony / zmieniona rozdzielczość → zostaje rozmiar domyślny
            a = s.availableGeometry(); w, h = min(r.width(), a.width()), min(r.height(), a.height())
            self.resize(w, h)
            self.move(max(a.left(), min(r.x(), a.right() - w + 1)), max(a.top(), min(r.y(), a.bottom() - h + 1)))
        if g.get("max"):
            self.setWindowState(Qt.WindowState.WindowMaximized)

    def _save_geometry(self):
        full = self.isMaximized() or self.isFullScreen()
        r = self.normalGeometry() if full else self.geometry()
        g = dict(self.store.settings.get("window") or {}) if isinstance(self.store.settings.get("window"), dict) else {}
        if r.width() >= 300 and r.height() >= 200:
            g.update(x=r.x(), y=r.y(), w=r.width(), h=r.height())
        g["max"] = self.isMaximized()
        self.store.settings["window"] = g

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
            a = menu.addAction(mini_icon(name, ENGINES[name]), name); a.setCheckable(True); a.setChecked(name == cur)
            a.triggered.connect(lambda _=False, n=name: QTimer.singleShot(0, lambda: self.store.set_engine(n)))
        self.chip.adjustSize()
        self.address.setTextMargins(0, 0, self.chip.sizeHint().width() + 12, 0)

    def _ui_refresh(self):
        self.update_engine_ui(); self.update_star()

    def setup_shortcuts(self):
        defs = [("Ctrl+T", self.new_tab), ("Ctrl+W", lambda: self.close_tab(self.cur())),
                ("F5", self.reload_current), ("Ctrl+R", self.reload_current),
                ("Ctrl+Tab", lambda: self.cycle_tab(1)), ("Ctrl+Shift+Tab", lambda: self.cycle_tab(-1)),
                ("Ctrl+Backtab", lambda: self.cycle_tab(-1)), ("Ctrl+PgDown", lambda: self.cycle_tab(1)),
                ("Ctrl+PgUp", lambda: self.cycle_tab(-1)), ("Ctrl+J", self.toggle_assistant),
                ("Ctrl+,", self.open_settings), ("Ctrl+\\", self.split_current),
                ("F9", self.toggle_reader), ("Ctrl+Alt+R", self.toggle_reader), ("Ctrl+Shift+T", self.restore_closed),
                ("Ctrl+Shift+L", self.translate_page), ("Ctrl+Shift+K", self.toggle_webapps), ("Ctrl+K", self.palette), ("Ctrl+Shift+O", self.read_later_add),
                ("Ctrl+Shift+Space", self.search_tabs), ("Shift+Esc", self.task_manager),
                ("Ctrl+Shift+S", lambda: self.screenshot("region")), ("Ctrl+Shift+P", self.pip),
                ("Ctrl+Shift+G", lambda: self.group_dialog(self.cur())), ("Ctrl+Shift+A", self.toggle_tab_popup),
                ("Ctrl+N", self.new_window), ("Ctrl+Shift+E", self.open_market), ("Ctrl+H", self.show_history), ("Ctrl+Shift+D", self.toggle_dark), ("Ctrl+Shift+N", lambda: self.new_window(True)),
                ("Ctrl+Shift+Y", self.show_downloads), ("Ctrl+Shift+Del", self.clear_data), ("Ctrl+P", self.print_page),
                ("Ctrl+F", self.find_bar.open), ("Ctrl+S", self.save_page), ("F12", self.devtools), ("Ctrl+U", self.view_source),
                ("F11", self.toggle_fullscreen), ("Ctrl+=", lambda: self.zoom(1)), ("Ctrl++", lambda: self.zoom(1)),
                ("Ctrl+-", lambda: self.zoom(-1)), ("Ctrl+0", lambda: self.zoom(0)), ("Ctrl+D", self.pin_current),
                ("Ctrl+L", lambda: (self.reveal_toolbar(), self.address.setFocus(), self.address.selectAll())),
                ("Ctrl+Shift+F", self.toggle_compact)]
        self.shortcuts = [QShortcut(QKeySequence(k), self, fn) for k, fn in defs]

    def apply_features(self):
        """Włącza/wyłącza moduły zgodnie z przełącznikami (wyłączone nie zajmują zasobów)."""
        on = self.store.feature("shortcuts")
        for sc in self.shortcuts:
            sc.setEnabled(on)
        ai = self.store.feature("assistant")
        self.ai_btn.setVisible(ai)
        if not ai:
            self.assistant.hide(); self.assistant.release()
        if not self.store.feature("webapps"):
            self.webapps.hide(); self.webapps.release()
        self.ws_btn.setVisible(self.store.feature("workspaces"))
        self.apply_dark()
        vt = self.store.feature("vertical_tabs")
        self.dock_tabpanel(vt); self.bar.setVisible(not vt); self.plus_btn.setVisible(not vt); self.apply_pins()
        if SHIELD:
            SHIELD[0].reload()
        bf = self.store.feature("instant_back")
        if bf != BFCACHE["on"] or not getattr(self, "_bf_init", False):
            self._bf_init = True; BFCACHE["on"] = bf
            for p in all_profiles():
                apply_bfcache(p)
        sp = self.store.feature("spellcheck")
        if sp != SPELL["on"] or not getattr(self, "_spell_init", False):
            self._spell_init = True; SPELL["on"] = sp
            for p in all_profiles():
                apply_spellcheck(p)
            if sp and len(spell_langs()) < len(DICTS):   # pierwsze uruchomienie: pobierz słowniki w tle, po starcie
                QTimer.singleShot(6000, lambda: ensure_dictionaries(self.store))
        self.update_shield(); self.tabs_changed()
        self.update_sidebars()

    # --- podpowiedzi wyszukiwania (jedno współdzielone okno) ---
    def suggest_popup(self):
        if self._suggest is None:
            self._suggest = SuggestPopup(); self._suggest.activated.connect(self._suggest_choose)
        return self._suggest

    def _suggest_choose(self, entry):
        p = self._suggest
        if p is not None and p.owner is not None:
            p.owner.choose(entry)

    def hide_suggest(self):
        if self._suggest is not None and self._suggest.isVisible():
            self._suggest.hide()

    def moveEvent(self, ev):
        super().moveEvent(ev); self.hide_suggest()

    # --- responsywne panele boczne ---
    def update_sidebars(self, prefer=None):
        """Panele nigdy nie wystają poza okno: gdy brakuje miejsca, zwijają się do szyn (drawer); panel wskazany
        przez użytkownika ma pierwszeństwo. Zwraca zbiór paneli, które mogą być rozwinięte."""
        t = self.cur()
        ok = bool(t and t.on_home()) or self.store.feature("everywhere")
        sbs = [sb for sb in (self.host.left, self.host.right)
               if self.store.feature(sb.side) and ok and sb.has_widgets()]
        for sb in (self.host.left, self.host.right):
            sb.setVisible(sb in sbs)
        side = self.assistant if self.assistant.isVisible() else (self.webapps if self.webapps.isVisible() else None)
        if side is not None:   # panel asystenta / aplikacji też się dopasowuje do szerokości okna
            side.setFixedWidth(max(300, min(440, int(self.width() * 0.36))))
        total = self.width() - 12 - (side.width() if side is not None else 0)
        rails = len(sbs) * Sidebar.RAIL
        cap = max(0, int((total - rails - self.MIN_CENTER) // Sidebar.W))
        prefer = prefer or self._pinned     # panel otwarty ręcznie zostaje otwarty, dopóki mieści się w oknie
        wants = sorted((sb for sb in sbs if not sb.user_collapsed), key=lambda sb: sb.side != prefer)
        if prefer and cap == 0 and any(sb.side == prefer for sb in wants):   # jawna prośba: pozwól zmniejszyć środek
            cap = max(0, int((total - rails - self.HARD_CENTER) // Sidebar.W))
        keep = set(wants[:cap])
        for sb in sbs:
            sb.set_state(sb not in keep, animate=self._laid)
        self._laid = True
        self.update_page_bg()
        return keep

    def update_page_bg(self):
        """Na stronie WWW tło pod panelami bocznymi przyjmuje kolor strony; na ekranie głównym zostaje tło Luny.
        Podział ekranu w poziomie: lewy panel – kolor lewej strony, prawy – prawej (nie aktywnej)."""
        t = self.cur()
        web = t.web if t is not None and t.web is not None and not t.on_home() else None
        if web is None or not self.store.feature("panel_page_bg"):
            self.bgframe.set_page_color(None); return
        views = [web]
        if t.sides and t.split is not None and t.split.orientation() == Qt.Orientation.Horizontal:
            ends = [s.view for s in (t.sides[0], t.sides[-1])]
            views = [v if v is not None else web for v in ends]
        got_c = [None] * len(views); self._bg_req = req = object()

        def fix(v, val):
            c = css_color(val)
            if dark_for(v.url().toString()) and c.lightnessF() > 0.5:
                c = QColor("#121212")   # tak silnik maluje jasne tło w ciemnym trybie
            return c

        def got(k, v, val):
            try:
                if req is not self._bg_req or t is not self.cur() or t.on_home():
                    return
                got_c[k] = fix(v, val)
                if all(c is not None for c in got_c):
                    self.bgframe.set_page_color(got_c[0], got_c[-1] if len(got_c) > 1 else None)
            except RuntimeError:   # okno zamknięte, zanim strona odpowiedziała
                pass
        for k, v in enumerate(views):
            v.page().runJavaScript(PAGE_BG_JS, QWebEngineScript.ScriptWorldId.ApplicationWorld,
                                   lambda val, k=k, v=v: got(k, v, val))

    def toggle_sidebar(self, side):
        sb = self.host.left if side == "left" else self.host.right
        open_it = sb.collapsed
        sb.set_user_collapsed(not open_it)
        self._pinned = side if open_it else (None if self._pinned == side else self._pinned)
        keep = self.update_sidebars(prefer=side if open_it else None)
        if open_it and sb not in keep:
            QToolTip.showText(QCursor.pos(), "Za mało miejsca – powiększ okno albo zamknij asystenta.", self)

    def update_sidebars_soon(self):
        self._sb_t.start(40)

    def resizeEvent(self, ev):
        super().resizeEvent(ev); self._sb_t.start(120); self._apply_density()

    def _apply_density(self):
        """Wąskie okno (mały laptop, pół ekranu): mniejsze przyciski i marginesy paska, węższy panel kart."""
        c = self.width() < 1000
        if not hasattr(self, "_dense") or c == self._compact:
            return
        self._compact = c; s = 32 if c else 38
        for b in self._dense:
            b.setFixedSize(s, s); b.setIconSize(QSize(s - 8, s - 8))
        self._tool_lay.setContentsMargins(*((8, 5, 8, 5) if c else (12, 8, 12, 8))); self._tool_lay.setSpacing(2 if c else 4)
        if self.store.feature("vertical_tabs"):
            self.tabpanel.setFixedWidth(self._tabpanel_w())

    def _tabpanel_w(self):
        return 204 if self._compact else TabPanel.W

    def open_settings(self, page=None):
        dlg = SettingsDialog(self.store, self.host, self)
        dlg.show_page(page if isinstance(page, str) else "features"); dlg.exec()

    def mmb_new(self):
        if self.store.feature("shortcuts"):
            self.new_tab()

    def reload_current(self):
        t = self.cur()
        if t and t.web and not t.on_home():
            t.web.reload()
        else:
            self.host.refresh_all(); self.store.changed.emit()

    def refresh_close_icons(self):
        cur = self.bar.currentIndex()
        for i in range(self.bar.count()):
            h = self.bar.tabButton(i, QTabBar.ButtonPosition.RightSide)
            b = h.findChild(QToolButton) if h is not None else None   # krzyżyk w opakowaniu z marginesem
            if b is not None:
                b.setIcon(glyph("close", "#2a2a2a" if i == cur else "#8c8c8c"))

    def update_star(self):
        t = self.cur()
        pinned = False
        if t and t.web and not t.on_home():
            h = host_of(t.web.url().toString())
            pinned = bool(h) and any(host_of(b["url"]) == h for b in self.store.items)
        self.star_btn.setIcon(glyph("starfill" if pinned else "star"))

    def toggle_assistant(self):
        if not self.store.feature("assistant"):
            return
        show = not self.assistant.isVisible()
        if show and self.webapps.isVisible():   # jeden panel boczny naraz
            self.webapps.hide(); self.apps_btn.setIcon(glyph("chat"))
        self.assistant.setVisible(show)
        self.ai_btn.setIcon(glyph("assistantfill" if show else "assistant"))
        if show:
            self.assistant.ensure()
        self.update_sidebars_soon()

    def toggle_webapps(self):
        if not self.store.feature("webapps"):
            return
        show = not self.webapps.isVisible()
        if show and self.assistant.isVisible():
            self.assistant.hide(); self.ai_btn.setIcon(glyph("assistant"))
        self.webapps.setVisible(show)
        self.apps_btn.setIcon(glyph("chatfill" if show else "chat"))
        if show:
            self.webapps.ensure()
        self.update_sidebars_soon()

    AI_LOGIN_LINKS = (("claude.ai", "/magic-link"), ("claude.com", "/magic-link"))

    def ai_login_link(self, url):
        """Link logowania usługi AI (np. claude.ai/magic-link z e-maila) → otwiera się w panelu AI, nie w karcie,
        żeby to panel był zalogowany. Zwraca True, gdy link został przejęty."""
        q = QUrl(url if "://" in url else "https://" + url)
        host = q.host().lower(); path = q.path()
        if not self.store.feature("assistant") or not any(host.endswith(h) and path.startswith(p) for h, p in self.AI_LOGIN_LINKS):
            return False
        if not self.assistant.isVisible():
            self.toggle_assistant()
        self.assistant.open_in_panel(q.toString())
        self.notice.info("Link logowania otwarty w panelu AI – sesja zostanie zapamiętana.", 5000, "key")
        return True

    def open_url_new_tab(self, url, container=""):
        if self.ai_login_link(url):
            return
        c = self.cur()   # link z karty w grupie trafia do tej samej grupy
        g = c.group if c is not None and c.container == container else ""
        self.new_tab(container=container, group=g).go(url)

    def closeEvent(self, ev):
        safe_disconnect(QGuiApplication.instance().applicationStateChanged, self._state_cb)   # sprzątanie nasłuchiwaczy
        safe_disconnect(QApplication.instance().focusChanged, self._focus_changed)
        self.hide_suggest(); self.host.shutdown_all()
        if self._preview is not None:
            self._preview.deleteLater(); self._preview = None
        try:
            DOWNLOADS[0].started.disconnect(self.on_download)
        except (TypeError, RuntimeError):
            pass
        safe_disconnect(DOWNLOADS[0].changed, self._dl_changed)
        if self.primary:
            self.store.settings["session"] = self.session_data(); self._save_geometry()
            self.store.settings["running"] = False   # poprawne zamknięcie (brak pytania o przywrócenie kart)
            if SYNC and SYNC[0].enabled():
                SYNC[0].write()
        self.store.save_settings()
        super().closeEvent(ev)

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

    # --- pasek narzędzi: przypięte ikony i menu burgera ---
    def pins(self):
        p = self.store.settings.get("toolbar_pins")
        if not isinstance(p, list):
            return list(TOOL_DEFAULT)
        known = self.store.settings.setdefault("toolbar_known", [k for k, _ in TOOL_ITEMS if k != "apps"])
        new = [k for k in TOOL_DEFAULT if k not in known]   # nowe ikony (np. panel aplikacji) – raz przypięte domyślnie
        if new:
            p = p + [k for k in new if k not in p]; known += new
            self.store.settings["toolbar_pins"] = [k for k, _ in TOOL_ITEMS if k in p]; self.store.save_soon()
        return p

    def set_pin(self, key, on):
        p = [k for k in self.pins() if k != key] + ([key] if on else [])
        self.store.settings["toolbar_pins"] = [k for k, _ in TOOL_ITEMS if k in p]; self.store.save_soon()
        self.apply_pins()

    def apply_pins(self):
        """Ikony przypięte widać obok wyszukiwarki; pozostałe są w menu burgera (skrajnie po prawej)."""
        p = set(self.pins())
        allowed = {"ai": self.store.feature("assistant"), "apps": self.store.feature("webapps")}
        for key, btn in self.tool_btns.items():
            btn.setVisible(key in p and allowed.get(key, True))

    def act(self, menu, kind, text, fn=None, shortcut=None, enabled=True):
        a = menu.addAction(glyph(kind), text)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut)); a.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        if fn:
            a.triggered.connect(lambda _=False: fn())
        a.setEnabled(enabled)
        return a

    def web(self):
        t = self.cur()
        return t.web if t is not None and t.web is not None and not t.on_home() else None

    def burger_menu(self):
        m = self.burger.menu(); m.clear(); web = self.web()
        menu_row_action(m, MenuSearch(lambda: (m.close(), QTimer.singleShot(0, self.palette))))
        hidden = [k for k, _ in TOOL_ITEMS if k not in self.pins() and k not in ("gear", "split", "key", "reader")]
        if hidden:   # ikony schowane z paska (podział, hasła i czytanie mają stałe miejsca niżej)
            names = dict(TOOL_ITEMS)
            for k in hidden:
                if k == "shield":
                    sm = m.addMenu(glyph("shield"), names[k]); sm.aboutToShow.connect(lambda sm=sm: self.shield_menu(sm))
                elif k == "star":
                    self.act(m, "star", "Dodaj do ekranu głównego", self.pin_current, "Ctrl+D", web is not None)
                elif k == "ai" and self.store.feature("assistant"):
                    self.act(m, "assistant", "Asystent AI", self.toggle_assistant, "Ctrl+J")
                elif k == "apps" and self.store.feature("webapps"):
                    self.act(m, "chat", "Panel aplikacji", self.toggle_webapps, "Ctrl+Shift+K")
        # 1. karty i okna
        menu_section(m, "Karty i okna")
        self.act(m, "plus", "Nowa karta", self.new_tab, "Ctrl+T")
        self.act(m, "window", "Nowe okno", self.new_window, "Ctrl+N")
        self.act(m, "private", "Nowe okno prywatne", lambda: self.new_window(True), "Ctrl+Shift+N")
        self.act(m, "search", "Szukaj w kartach…", self.search_tabs, "Ctrl+Shift+Space")
        on = bool(self.cur() and self.cur().sides)
        self.act(m, "split", "Zakończ podział ekranu" if on else "Podziel ekran",
                 self.split_current, "Ctrl+\\", on or web is not None)
        lm = m.addMenu(glyph("layouts"), "Układy podziału"); lm.aboutToShow.connect(lambda: self.layouts_menu(lm))
        self.layouts_menu(lm)
        if SYNC and SYNC[0].enabled() and SYNC[0].remote:
            om = m.addMenu(glyph("window"), "Karty z innych komputerów")
            for name, ts, tabs in SYNC[0].other_tabs():
                sm_ = om.addMenu(f"{name} ({len(tabs)})")
                for d_ in tabs[:40]:
                    sm_.addAction(mini_icon(d_.get("title") or d_["url"], d_["url"]), (d_.get("title") or d_["url"])[:60]).triggered.connect(
                        lambda _=False, u=d_["url"]: self.open_url_new_tab(u))
        # 2. twoje rzeczy
        menu_section(m, "Twoje rzeczy")
        hm = m.addMenu(glyph("history"), "Historia")
        self.act(hm, "history", "Pełna historia…", self.show_history, "Ctrl+H")
        self.act(hm, "reload", "Przywróć zamkniętą kartę", self.restore_closed, "Ctrl+Shift+T", bool(self._closed))
        if self._closed:
            cm = hm.addMenu(glyph("tabs"), "Ostatnio zamknięte")
            for i in range(len(self._closed) - 1, -1, -1):
                d = self._closed[i]
                cm.addAction(tab_icon(d["icon"]), (d["title"] or d["url"])[:48], lambda i=i: self.restore_closed(i))
        hm.addSeparator()
        for r in self.store.recent[:10]:
            self.act(hm, "history", (r["name"] or r["url"])[:48], lambda u=r["url"]: self.open_url_new_tab(u))
        if not self.store.recent:
            hm.addAction("Brak historii").setEnabled(False)
        hm.addSeparator(); self.act(hm, "trash", "Usuń dane przeglądania…", self.clear_data, "Ctrl+Shift+Del")
        bm = m.addMenu(glyph("bookmark"), "Zakładki i listy")
        self.act(bm, "star", "Dodaj tę stronę do ekranu głównego", self.pin_current, "Ctrl+D", web is not None)
        bm.addSeparator()
        for it in self.store.items[:20]:
            bm.addAction(mini_icon(it["name"], it["url"]), it["name"]).triggered.connect(
                lambda _=False, u=it["url"]: self.open_url_new_tab(u))
        imp = Bookmarks.items()
        if imp:   # zaimportowane z innej przeglądarki – według folderów
            bm.addSeparator(); folders = {}
            for b_ in imp:
                folders.setdefault(b_.get("folder") or "Zakładki", []).append(b_)
            for name in list(folders)[:25]:
                fm_ = bm.addMenu(glyph("folder"), name[:60])
                for b_ in folders[name][:60]:
                    fm_.addAction(mini_icon(b_["title"], b_["url"]), b_["title"][:70]).triggered.connect(
                        lambda _=False, u=b_["url"]: self.open_url_new_tab(u))
        bm.addSeparator(); self.act(bm, "download", "Importuj z innej przeglądarki…", lambda: ImportDialog(self).exec())
        rl = m.addMenu(glyph("book"), "Do przeczytania"); rl.aboutToShow.connect(lambda: self.read_later_menu(rl))
        self.act(m, "edit", "Zakreślenia i notatki…", self.show_highlights)
        self.act(m, "download", "Pobrane pliki", self.show_downloads, "Ctrl+Shift+Y")
        pw = m.addMenu(glyph("key"), "Hasła i autouzupełnianie")
        pw.aboutToShow.connect(lambda: self.key_menu(pw))
        # 3. ta strona
        menu_section(m, "Ta strona")
        zr = MenuRow("zoom", "Powiększ")
        zr.button(kind="min", tip="Pomniejsz (Ctrl+-)", fn=lambda: self.zoom(-1))
        self._zoom_lbl = zr.button(f"{round((web.zoomFactor() if web else 1) * 100)}%", tip="Przywróć 100% (Ctrl+0)",
                                   fn=lambda: self.zoom(0))
        self._zoom_lbl.setMinimumWidth(52)
        zr.button(kind="plus", tip="Powiększ (Ctrl++)", fn=lambda: self.zoom(1))
        sep = QFrame(); sep.setObjectName("vsep"); sep.setFixedSize(1, 22); zr.h.addWidget(sep)
        zr.button(kind="fullscreen", tip="Pełny ekran (F11)", fn=lambda: (m.close(), self.toggle_fullscreen()))
        menu_row_action(m, zr)
        rd = self.act(m, "book", "Tryb czytania", self.toggle_reader, "F9", web is not None)
        rd.setCheckable(True); rd.setChecked(bool(web is not None and getattr(web, "reader_on", False)))
        tr_on = bool(web is not None and getattr(getattr(web, "_translator", None), "active", False))
        self.act(m, "swap", "Pokaż oryginał strony" if tr_on else "Przetłumacz stronę na polski", self.translate_page,
                 "Ctrl+Shift+L", web is not None)
        self.act(m, "external", "Obraz w obrazie (film w okienku)", self.pip, "Ctrl+Shift+P", web is not None)
        dk = self.act(m, "moon", "Ciemny tryb stron", self.toggle_dark, "Ctrl+Shift+D")
        dk.setCheckable(True); dk.setChecked(self.store.feature("dark_pages"))
        if web is not None and self.store.feature("dark_pages"):
            dom = base_domain(web.url().host())
            ex = self.act(m, "sun", f"Bez ciemnego trybu na {dom}", lambda d=dom: self.set_dark_except(d, d not in DARK["except"]))
            ex.setCheckable(True); ex.setChecked(dom in DARK["except"])
        self.act(m, "print", "Drukuj…", self.print_page, "Ctrl+P", web is not None)
        fm = m.addMenu(glyph("search"), "Znajdź i edytuj"); fm.setEnabled(web is not None)
        self.act(fm, "search", "Znajdź na stronie…", self.find_bar.open, "Ctrl+F")
        fm.addSeparator()
        if web is not None:
            for kind, text, action, sc in (("cut", "Wytnij", QWebEnginePage.WebAction.Cut, "Ctrl+X"),
                                           ("copy", "Kopiuj", QWebEnginePage.WebAction.Copy, "Ctrl+C"),
                                           ("paste", "Wklej", QWebEnginePage.WebAction.Paste, "Ctrl+V"),
                                           ("select", "Zaznacz wszystko", QWebEnginePage.WebAction.SelectAll, "Ctrl+A")):
                self.act(fm, kind, text, lambda a=action: web.page().triggerAction(a), sc)
        sm = m.addMenu(glyph("share"), "Zapisz, zrzut ekranu, udostępnij"); sm.setEnabled(web is not None)
        self.act(sm, "save", "Zapisz stronę jako…", self.save_page, "Ctrl+S")
        self.act(sm, "print", "Zapisz jako PDF…", self.save_pdf)
        self.act(sm, "copy", "Kopiuj link", lambda: web and QGuiApplication.clipboard().setText(web.url().toString()))
        sm.addSeparator()
        self.act(sm, "copy", "Zrzut: widoczna część", lambda: self.screenshot("visible"))
        self.act(sm, "copy", "Zrzut: cała strona", lambda: self.screenshot("full"))
        self.act(sm, "copy", "Zrzut: zaznaczony fragment…", lambda: self.screenshot("region"), "Ctrl+Shift+S")
        # 4. luna
        menu_section(m, "Dostosuj Lunę")
        self.act(m, "grid", "Rynek Widgetów", self.open_market, "Ctrl+Shift+E")
        em = m.addMenu(glyph("puzzle"), "Rozszerzenia"); em.aboutToShow.connect(lambda: self.extensions_menu(em))
        cp = self.act(m, "eye", "Tryb kompaktowy (pasek adresu schowany)", self.toggle_compact, "Ctrl+Shift+F")
        cp.setCheckable(True); cp.setChecked(bool(self.store.settings.get("compact")))
        pm = m.addMenu(glyph("pin"), "Ikony na pasku")
        for key, name in TOOL_ITEMS:
            a = pm.addAction(name); a.setCheckable(True); a.setChecked(key in self.pins())
            a.toggled.connect(lambda on, k=key: self.set_pin(k, on))
        tm = m.addMenu(glyph("tools"), "Więcej narzędzi")
        self.act(tm, "tools", "Menedżer zadań", self.task_manager, "Shift+Esc")
        self.act(tm, "trash", "Usuń dane przeglądania…", self.clear_data, "Ctrl+Shift+Del")
        self.act(tm, "save", "Kopia zapasowa…", lambda: BackupDialog(self).exec())
        self.act(tm, "download", "Importuj z innej przeglądarki…", lambda: ImportDialog(self).exec())
        tm.addSeparator()
        self.act(tm, "tabs", "Karty i grupy", self.toggle_tab_popup, "Ctrl+Shift+A")
        self.act(tm, "layers", "Przestrzenie robocze…", lambda: self.open_settings("tabs"))
        self.act(tm, "shield", "Prywatność…", lambda: self.open_settings("privacy"))
        tm.addSeparator()
        self.act(tm, "tools", "Narzędzia deweloperskie", self.devtools, "F12", web is not None)
        self.act(tm, "app", "Wyświetl źródło strony", self.view_source, "Ctrl+U", web is not None)
        m.addSeparator()
        # 5. systemowe
        hp = m.addMenu(glyph("help"), "Pomoc")
        self.act(hp, "star", "Co nowego w Lunie", self.show_whats_new)
        self.act(hp, "search", "Wszystkie polecenia…", self.palette, "Ctrl+K")
        self.act(hp, "app", "Skróty klawiszowe", lambda: self.open_settings("keys"))
        self.act(hp, "help", "O Lunie", self.about)
        self.act(hp, "shield", "Polityka prywatności", lambda: self.open_url_new_tab(PRIVACY_URL))
        self.act(m, "gear", "Ustawienia", self.open_settings, "Ctrl+,")
        self.act(m, "exit", "Zakończ", self.quit_all)

    # --- akcje menu ---
    def new_window(self, private=False):
        w = Browser(self.store, private=private); w.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        WINDOWS.append(w); w.destroyed.connect(lambda _=None, w=w: WINDOWS.remove(w) if w in WINDOWS else None)
        w.show()

    def apply_dark(self):
        """Ciemny tryb z ustawień → wszystkie otwarte strony (w każdym oknie) od razu, bez przeładowania."""
        DARK["on"] = self.store.feature("dark_pages")
        DARK["except"] = set(self.store.settings.get("dark_except", []))
        for pg in list(LUNA_PAGES):
            try:
                pg.apply_dark()
            except RuntimeError:
                pass
        QTimer.singleShot(300, self.update_page_bg)

    def set_dark_except(self, dom, on):
        lst = [d for d in self.store.settings.get("dark_except", []) if d != dom] + ([dom] if on else [])
        self.store.settings["dark_except"] = lst; self.store.save_soon()
        for w in [self] + WINDOWS:
            w.apply_dark()

    def toggle_dark(self):
        self.store.set_feature("dark_pages", not self.store.feature("dark_pages"))

    # --- tłumaczenie strony (Ctrl+Shift+L; ponowne wywołanie przywraca oryginał) ---
    def translate_page(self):
        web = self.web()
        if web is None or not web.url().scheme().startswith("http"):
            return
        tr = translator_for(self.store, web)
        if tr.active:
            tr.restore(); self.notice.info("Przywrócono oryginalny tekst strony.", 3000, "swap"); return
        safe_disconnect(tr.status, self._translate_status)
        tr.status.connect(self._translate_status)
        tgt = translate_target(self.store)
        self.notice.info(f"Tłumaczę stronę na: {LANGS[tgt]}…", 15000, "swap")
        tr.start(tgt)

    def _translate_status(self, st):
        if st == "error":
            self.notice.info("Nie udało się przetłumaczyć strony (brak połączenia z Tłumaczem Google).", 6000, "swap")
        elif st == "done" and self.notice.isVisible() and self.notice.text.text().startswith("Tłumaczę"):
            self.notice.ask(f"Strona przetłumaczona na: {LANGS[translate_target(self.store)]}.",
                            [("Pokaż oryginał", self.translate_page, False), ("OK", None, False)], icon="swap")

    def offer_translation(self, web):
        """Po wczytaniu: strona deklaruje obcy język (atrybut lang) → pytanie, czy przetłumaczyć."""
        if not self.store.feature("translate_offer") or web is None or not web.url().scheme().startswith("http"):
            return
        host = base_domain(web.url().host())
        if host in self.store.settings.get("translate_never", []):
            return

        def got(lang):
            code, tgt = lang_code(lang), translate_target(self.store)
            if not code or code.split("-")[0] == tgt.split("-")[0] or web is not self.web():
                return
            if getattr(getattr(web, "_translator", None), "active", False):
                return
            if self.notice.isVisible() and self.notice.btns.count():   # inne pytanie (np. zapis hasła) ma pierwszeństwo
                return
            self.notice.ask(f"Język strony: {LANGS[code]}. Przetłumaczyć ją na: {LANGS[tgt]}?",
                            [("Przetłumacz", self.translate_page, True),
                             ("Nigdy na tej stronie", lambda: self._translate_never(host), False), ("Nie", None, False)],
                            icon="swap")
        try:
            web.page().runJavaScript("document.documentElement.lang", QWebEngineScript.ScriptWorldId.ApplicationWorld, got)
        except RuntimeError:
            pass

    def _translate_never(self, host):
        lst = [h for h in self.store.settings.get("translate_never", []) if h != host] + [host]
        self.store.settings["translate_never"] = lst; self.store.save_soon()

    # --- tryb czytania (nakładka na stronę; ponowne wywołanie zamyka) ---
    def toggle_reader(self):
        web = self.web()
        if web is None:
            return
        prefs = self.store.settings.get("reader") if isinstance(self.store.settings.get("reader"), dict) else {}
        js = READER_JS.replace("%K%", json.dumps(PW_KEY)).replace("%P%", json.dumps(prefs))

        def done(res):
            try:
                if res == "none":
                    self.notice.info("Na tej stronie nie znaleziono artykułu do czytania.")
            except RuntimeError:
                pass
        web.page().runJavaScript(js, QWebEngineScript.ScriptWorldId.ApplicationWorld, done)

    def on_reader(self, view, d):
        view.reader_on = d.get("state") == "on"
        if isinstance(d.get("prefs"), dict):
            self.store.settings["reader"] = {k: d["prefs"][k] for k in ("size", "serif", "width") if k in d["prefs"]}
            self.store.save_soon()
        if view is self.web():
            self.update_reader_btn()

    def update_reader_btn(self):
        web = self.web(); on = bool(web is not None and getattr(web, "reader_on", False))
        if self.reader_btn.property("on") != on:
            self.reader_btn.setProperty("on", on); self.reader_btn.setIcon(glyph("book", "#ffffff" if on else "#c9c9c9"))
            self.reader_btn.setToolTip("Zamknij tryb czytania (F9)" if on else "Tryb czytania (F9)")

    def open_market(self, tab="cat"):
        dlg = WidgetMarket(self); dlg.show_tab(tab); dlg.exec()

    # --- aktualizacje Luny (git) ---
    def on_update_result(self, st):
        if not WINDOWS or WINDOWS[0] is not self or not st.get("behind"):
            return
        n = st["behind"]
        if st.get("dirty"):
            self.notice.ask(f"Dostępna nowa wersja Luny ({n} zm.), ale w folderze Luny są niezapisane zmiany – "
                            "zaktualizuj przez GitHub Desktop.", [("OK", None, False)], icon="app")
            return
        self.notice.ask(f"Dostępna nowa wersja Luny ({n} {'zmiana' if n == 1 else 'zmian'}).",
                        [("Zaktualizuj i uruchom ponownie", self.apply_update, True), ("Później", None, False)], icon="app")

    def apply_update(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok, msg = updater().pull()
        finally:
            QApplication.restoreOverrideCursor()
        if ok:
            restart_luna(self)
        else:
            self.notice.ask("Nie udało się zaktualizować Luny: " + (msg or "błąd git"), [("OK", None, False)], icon="app")

    def quit_all(self):
        for w in list(WINDOWS):
            w.close()
        self.close()

    def sidebar_mode(self):
        f = self.store.feature
        if not (f("left") or f("right")):
            return "off"
        return "on" if f("everywhere") else "auto"

    def set_sidebar_mode(self, mode):
        """Włączone: panele z widgetami także na stronach; Automatyczne ukrywanie: tylko na ekranie głównym; Wył.: bez paneli."""
        st = self.store; feats = st.settings.setdefault("features", {})
        feats["left"] = feats["right"] = mode != "off"
        feats["everywhere"] = mode == "on"
        st.save_settings(); st.features_changed.emit(); st.layout_changed.emit()

    def zoom(self, step):
        web = self.web()
        if web is None:
            return
        z = web.zoomFactor()
        if step == 0:
            z = 1.0
        else:
            i = min(range(len(ZOOMS)), key=lambda k: abs(ZOOMS[k] - z))
            z = ZOOMS[max(0, min(len(ZOOMS) - 1, i + step))]
        web.setZoomFactor(z)
        host = web.url().host().lower()
        if host and not self.private:   # powiększenie zapamiętane dla tej witryny
            zs = self.store.settings.setdefault("zoom_sites", {})
            if abs(z - 1.0) < 0.01:
                zs.pop(host, None)
            else:
                zs[host] = round(z, 2)
            self.store.save_soon()
        if getattr(self, "_zoom_lbl", None) is not None:
            try:
                self._zoom_lbl.setText(f"{round(z * 100)}%")
            except RuntimeError:
                self._zoom_lbl = None
        QToolTip.showText(QCursor.pos(), f"Powiększenie: {round(z * 100)}%" + (f" (zapamiętane dla {host})" if host and abs(z - 1) > .01 else ""), self)

    # --- YouTube: SponsorBlock ---
    def on_view_url(self, view, u, reinject=False):
        if not self.store.feature("sponsorblock"):
            return
        vid = youtube_id(u)
        if not vid or (getattr(view, "_sb_vid", "") == vid and not reinject):
            return
        view._sb_vid = vid

        def got(segs):
            try:
                if getattr(view, "_sb_vid", "") == vid:
                    _safe_js(view, SB_JS % (json.dumps(segs), json.dumps(vid), json.dumps(PW_KEY)))
            except RuntimeError:
                pass
        SponsorBlock.segments(self.store, vid, got)

    def on_sponsor_skipped(self, view, d):
        if view is self.web():
            self.notice.info(f"Pominięto {SB_CATS.get(d.get('c'), 'fragment sponsorowany')} ({d.get('d', 0)} s) – SponsorBlock.",
                             3500, "play")

    def apply_site_zoom(self, view):
        """Po wczytaniu: powiększenie zapamiętane dla witryny (albo 100%, gdy przechodzimy na inną witrynę)."""
        try:
            host = view.url().host().lower()
            z = float((self.store.settings.get("zoom_sites") or {}).get(host, 1.0))
            if abs(view.zoomFactor() - z) > 0.01:
                view.setZoomFactor(z)
        except (RuntimeError, ValueError, TypeError):
            pass

    def offer_address(self, view):
        """Strona z formularzem adresu (ulica + kod/miasto) → pytanie, czy wypełnić zapisanym adresem."""
        adr = addresses()
        if not adr or view is not self.web():
            return

        def got(res):
            try:
                r = json.loads(res) if res else {}
            except ValueError:
                r = {}
            if not r.get("address") or view is not self.web():
                return
            if self.notice.isVisible() and self.notice.btns.count():
                return
            u = view.url().toString()
            if getattr(view, "_addr_offered", "") == u:
                return
            view._addr_offered = u
            a = adr[0]
            acts = [(f"Wypełnij: {a.get('label') or a.get('street') or 'adres'}", lambda: fill_address(view, a), True)]
            if len(adr) > 1:
                acts.append(("Inny adres…", lambda: self._pick_address(view), False))
            self.notice.ask("Ta strona ma formularz adresu. Wypełnić zapisanym adresem?", acts + [("Nie", None, False)],
                            icon="home")
        for ms in (600, 3000):   # formularze dorysowywane skryptami
            QTimer.singleShot(ms, lambda: _safe_js(view, ADDR_JS % ("{}", "false"), got))

    def _pick_address(self, view):
        names = [a.get("label") or a.get("street") or f"Adres {i + 1}" for i, a in enumerate(addresses())]
        n, ok = QInputDialog.getItem(self, "Wypełnij adres", "Adres:", names, 0, False)
        if ok:
            fill_address(view, addresses()[names.index(n)])

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized() if self._was_max else self.showNormal()
        else:
            self._was_max = self.isMaximized(); self.showFullScreen()

    def show_downloads(self):
        DownloadsDialog(self).exec()

    # --- obraz w obrazie (własne okienko – silnik Qt nie ma wbudowanego PiP) ---
    def pip(self):
        web = self.web()
        if web is None:
            return

        def got(res):
            try:
                info = json.loads(res) if res else None
            except ValueError:
                info = None
            if not info:
                self.notice.info("Na tej stronie nie ma filmu do obrazu w obrazie.", icon="app"); return
            old = getattr(self, "_pip", None)
            if old is not None:
                try:
                    old.finish()
                except RuntimeError:
                    pass
            self._pip = PipWindow(self, web, info); self._pip.destroyed.connect(lambda *_: setattr(self, "_pip", None))
            self._pip.show()
        web.page().runJavaScript(PIP_FIND_JS, QWebEngineScript.ScriptWorldId.ApplicationWorld, got)

    def pip_closed(self, view, t, show_tab=False):
        """Film wraca do karty: od momentu, w którym skończył się w okienku, i gra dalej."""
        try:
            # wznowienie przychodzi z okienka, nie z kliknięcia na tej stronie – na chwilę zdejmujemy wymóg gestu
            A = QWebEngineSettings.WebAttribute; s = view.page().settings()
            s.setAttribute(A.PlaybackRequiresUserGesture, False)
            QTimer.singleShot(3000, lambda: s.setAttribute(A.PlaybackRequiresUserGesture, True))
            js = ("(function(t){ const v = document.querySelector('video[data-luna-pip]'); if (!v) return;"
                  " v.removeAttribute('data-luna-pip'); const yt = document.getElementById('movie_player');"
                  " if (yt && yt.seekTo && yt.playVideo) { if (t >= 0) yt.seekTo(t, true); yt.playVideo(); return; }"   # odtwarzacz YouTube
                  " if (t >= 0) v.currentTime = t; v.play().catch(() => {}); })(%s)" % float(t))
            view.page().runJavaScript(js, QWebEngineScript.ScriptWorldId.MainWorld)
            if show_tab:
                tab = view.owner
                if tab in self.all_tabs():
                    self.activate(tab); self.raise_(); self.activateWindow()
        except (RuntimeError, AttributeError):
            pass

    # --- zrzut strony: widoczna część / cała strona (przewijanie i sklejanie) / fragment; schowek + PNG w Obrazy\Luna ---
    def screenshot(self, mode="visible"):
        web = self.web()
        if web is None:
            return
        if mode == "visible":
            self._shot_done(web.grab())
        elif mode == "region":
            pm = web.grab(); r = QRect(web.mapToGlobal(QPoint(0, 0)), web.size())
            self._picker = RegionPicker(pm, r); self._picker.picked.connect(self._shot_done)
            self._picker.show(); self._picker.activateWindow(); self._picker.setFocus()
        else:
            js = "JSON.stringify([document.documentElement.scrollHeight, window.innerHeight, window.scrollY])"
            web.page().runJavaScript(js, QWebEngineScript.ScriptWorldId.ApplicationWorld, lambda r: self._full_shot(web, r))

    def _full_shot(self, web, res):
        try:
            total, inner, y0 = json.loads(res)
        except Exception:
            self._shot_done(web.grab()); return
        if total <= inner + 2:
            self._shot_done(web.grab()); return
        k = web.height() / max(1, inner)                      # piksele widoku na piksel CSS (powiększenie strony)
        total = min(total, int(20000 / k)); first = web.grab(); dpr = first.devicePixelRatio()
        img = QImage(int(web.width() * dpr), int(total * k * dpr), QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(QColor("#111111")); st = {"y": 0, "img": img}
        world = QWebEngineScript.ScriptWorldId.ApplicationWorld
        self.notice.info("Robię zrzut całej strony…", 20000, "copy")

        def step():
            web.page().runJavaScript(f"window.scrollTo({{top:{st['y']}, behavior:'instant'}}); window.scrollY", world,
                                     lambda sy: QTimer.singleShot(260, lambda: grab(sy)))

        def grab(sy):
            try:
                pm = web.grab()
            except RuntimeError:
                return
            p = QPainter(st["img"]); p.drawImage(0, int((sy or 0) * k * dpr), pm.toImage()); p.end()
            if st["y"] == 0:
                web.page().runJavaScript(SHOT_FIXED_JS.replace("%ON%", "true"), world)
            if (sy or 0) + inner >= total or st["y"] > total:
                web.page().runJavaScript(SHOT_FIXED_JS.replace("%ON%", "false"), world)
                web.page().runJavaScript(f"window.scrollTo({{top:{y0}, behavior:'instant'}})", world)
                out = QPixmap.fromImage(st["img"]); out.setDevicePixelRatio(dpr); self._shot_done(out); return
            st["y"] += inner; step()
        step()

    def _shot_done(self, pm):
        if pm is None or pm.isNull():
            return
        QGuiApplication.clipboard().setPixmap(pm)
        from PyQt6.QtCore import QStandardPaths
        folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation) or HOME) / "Luna"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"Luna {datetime.now().strftime('%Y-%m-%d %H.%M.%S')}.png"; pm.save(str(path), "PNG")
        except OSError:
            self.notice.info("Zrzut jest w schowku (nie udało się zapisać pliku).", icon="copy"); return
        self.notice.ask(f"Zrzut zapisany i skopiowany: {path.name}",
                        [("Otwórz", lambda p=str(path): QDesktopServices.openUrl(QUrl.fromLocalFile(p)), True),
                         ("Pokaż w folderze", lambda p=str(path): show_in_folder(p), False), ("OK", None, False)], icon="copy")

    # --- pobieranie na pasku: pierścień postępu, lista z „Otwórz” / „Pokaż w folderze” ---
    def _dl_changed(self):
        if not self._dl_t.isActive():
            self._dl_t.start(250)   # bajty przychodzą bardzo często – odświeżamy ikonę najwyżej 4× na sekundę

    def update_dl_btn(self):
        dm = DOWNLOADS[0]; S = QWebEngineDownloadRequest.DownloadState
        if not dm.items:
            self.dl_btn.hide(); return
        act = [r for r in dm.items if r.state() == S.DownloadInProgress]
        if act:
            tot = sum(r.totalBytes() for r in act if r.totalBytes() > 0); got = sum(r.receivedBytes() for r in act if r.totalBytes() > 0)
            frac = got / tot if tot else 0.05
            self.dl_btn.setIcon(download_icon(frac)); self.dl_btn.setToolTip(f"Pobieranie: {len(act)} · {round(frac * 100)}%")
        else:
            self.dl_btn.setIcon(download_icon(done=True)); self.dl_btn.setToolTip("Pobrane pliki")
        self.dl_btn.show()

    def downloads_menu(self):
        m = self.dl_btn.menu(); m.clear(); dm = DOWNLOADS[0]; S = QWebEngineDownloadRequest.DownloadState
        for r in dm.items[:8]:
            st, tot, got = r.state(), r.totalBytes(), r.receivedBytes()
            info = (f"{got * 100 // tot}%" if tot > 0 else f"{got // 1024} KB") if st == S.DownloadInProgress else \
                {S.DownloadCompleted: "gotowe", S.DownloadCancelled: "anulowane", S.DownloadInterrupted: "przerwane"}.get(st, "")
            sm = m.addMenu(glyph("download"), f"{r.downloadFileName()[:40]}   ·   {info}")
            path = dm.path(r)
            self.act(sm, "external", "Otwórz", lambda p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)), enabled=st == S.DownloadCompleted)
            self.act(sm, "folder", "Pokaż w folderze", lambda p=path: show_in_folder(p))
            if st == S.DownloadInProgress:
                self.act(sm, "close", "Anuluj", r.cancel)
        m.addSeparator()
        self.act(m, "download", "Wszystkie pobrane…", self.show_downloads, "Ctrl+Shift+Y")

    def on_download(self, name):
        if self.isActiveWindow():
            self.notice.ask(f"Pobieranie: {name}", [("Pokaż pobrane", self.show_downloads, True), ("OK", None, False)],
                            icon="download")

    def clear_data(self):
        ClearDataDialog(self).exec()

    def show_history(self):
        HistoryDialog(self).exec()

    def extensions_menu(self, m):
        m.clear(); mgr = get_profile().extensionManager()
        exts = list(mgr.extensions()) if mgr is not None else []
        from PyQt6.QtCore import QLibraryInfo
        res = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.DataPath)) / "resources"
        for e in exts:
            # wbudowane w silnik (czytnik PDF, usługi Hangouts) leżą w zasobach Qt – ich przełączenie wywraca Qt
            if not e.isInstalled() and (not e.path() or Path(e.path()).parent.resolve() == res.resolve()):
                m.addAction(glyph("puzzle"), f"{e.name() or e.id()} (wbudowane)").setEnabled(False)
                continue
            sm = m.addMenu(glyph("puzzle"), e.name() or e.id())
            a = sm.addAction("Włączone"); a.setCheckable(True); a.setChecked(e.isEnabled())
            a.toggled.connect(lambda on, e=e: mgr.setExtensionEnabled(e, on))
            sm.addAction("Usuń", lambda e=e: mgr.uninstallExtension(e) if e.isInstalled() else mgr.unloadExtension(e))
        if not exts:
            m.addAction("Brak rozszerzeń").setEnabled(False)
        m.addSeparator()
        self.act(m, "plus", "Zainstaluj z pliku (.zip / .crx)…", lambda: self.install_extension(False), enabled=mgr is not None)
        self.act(m, "folder", "Wczytaj rozpakowane (folder)…", lambda: self.install_extension(True), enabled=mgr is not None)
        m.addAction("Sklep Chrome nie działa w silniku Qt – rozszerzenia instaluje się z pliku").setEnabled(False)

    def install_extension(self, folder):
        mgr = get_profile().extensionManager()
        if folder:
            path = QFileDialog.getExistingDirectory(self, "Folder rozszerzenia (z plikiem manifest.json)")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Rozszerzenie", "", "Rozszerzenia (*.zip *.crx)")
        if path:
            (mgr.installExtension if not folder else mgr.loadExtension)(path)
            self.notice.info("Rozszerzenie dodane – działa na nowo wczytanych stronach.")

    def print_page(self):
        web = self.web()
        if web is None:
            return
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        self._printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dlg = QPrintDialog(self._printer, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            web.printFinished.connect(lambda ok: self.notice.info("Wydrukowano." if ok else "Nie udało się wydrukować."))
            web.print(self._printer)

    def _save_name(self, ext):
        web = self.web(); name = re.sub(r'[\\/:*?"<>|]+', " ", web.title() or host_of(web.url().toString()) or "strona").strip()
        return str(Path(DOWNLOADS[0].folder() if DOWNLOADS else HOME) / f"{name[:80]}.{ext}")

    def save_page(self):
        web = self.web()
        if web is None:
            return
        path, flt = QFileDialog.getSaveFileName(self, "Zapisz stronę", self._save_name("mhtml"),
                                                "Cała strona w jednym pliku (*.mhtml);;Tylko HTML (*.html)")
        if path:
            F = QWebEngineDownloadRequest.SavePageFormat
            web.page().save(path, F.MimeHtmlSaveFormat if path.lower().endswith(".mhtml") else F.SingleHtmlSaveFormat)

    def save_pdf(self):
        web = self.web()
        if web is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz jako PDF", self._save_name("pdf"), "PDF (*.pdf)")
        if path:
            web.page().pdfPrintingFinished.connect(lambda p, ok: self.notice.info(f"Zapisano PDF: {Path(p).name}" if ok else
                                                                                  "Nie udało się zapisać PDF."))
            web.page().printToPdf(path)

    def devtools(self):
        web = self.web()
        if web is None:
            return
        dv = QWebEngineView(); dv.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dv.setWindowTitle("Narzędzia deweloperskie – " + (web.title() or "")); dv.setWindowIcon(app_icon()); dv.resize(1000, 700)
        web.page().setDevToolsPage(dv.page()); POPUPS.append(dv)
        dv.destroyed.connect(lambda _=None, d=dv: POPUPS.remove(d) if d in POPUPS else None); dv.show()

    def view_source(self):
        web = self.web()
        if web is not None:
            self.open_url_new_tab("view-source:" + web.url().toString(), self.cur().container)

    def about(self):
        AboutDialog(self).exec()

    def open_google(self, url):
        """Strony Google: w karcie Luny, gdy jest tam sesja Google; inaczej w zwykłej przeglądarce (Google blokuje logowanie
        w osadzonym silniku, więc karta Luny pokazałaby tylko ekran logowania)."""
        if self.store.session.logged_in("google"):
            self.open_url_new_tab(url)
        else:
            QDesktopServices.openUrl(QUrl(url))

    # --- karty ---
    def new_tab(self, container="", ws=None, group="", title="", lazy_url="", activate=True):
        container = PRIVATE if self.private else (container if container in self.container_ids() else "")
        t = Tab(self.store, self, ws or self.ws, group or "", container)
        self.stack.addWidget(t)
        i = self.bar.addTab((title or "Ekran główny")[:26])
        self._close_btn(t, True)
        if lazy_url:   # przywrócona karta: strona wczyta się dopiero po wejściu na kartę
            t.pending, t.title_text = lazy_url, title
        self.decorate(t)
        if activate:
            self.bar.setCurrentIndex(i)
        self.refresh_close_icons(); self.tabs_changed()
        return t

    def _close_btn(self, t, on):
        i = self.stack.indexOf(t)
        if i < 0:
            return
        holder = None
        if on:
            # Qt stawia przycisk karty przy samej zewnętrznej krawędzi (ignoruje padding) – opakowanie z marginesem
            # przesuwa krzyżyk do środka zaokrąglonego końca karty, więc nie wystaje
            holder = QWidget(); holder.setObjectName("clear"); holder.setFixedSize(TabBar.CLOSE_W, 18)
            holder.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            cb = QToolButton(holder); cb.setObjectName("tabclose"); cb.setFixedSize(18, 18); cb.setIconSize(QSize(12, 12))
            cb.move(0, 0)
            cb.setIcon(glyph("close", "#8c8c8c")); cb.setCursor(Qt.CursorShape.PointingHandCursor); cb.setToolTip("Zamknij kartę")
            cb.clicked.connect(lambda: self.close_tab(t))
        self.bar.setTabButton(i, QTabBar.ButtonPosition.RightSide, holder)

    def set_tab_text(self, t, text):
        """Tytuł na pasku kart; przypięta karta pokazuje samą ikonę (tytuł w podpowiedzi)."""
        i = self.stack.indexOf(t)
        if i >= 0:
            self.bar.setTabText(i, "" if t.pinned else (text[:26] or "…"))

    # --- przypięte karty: sama ikona na początku paska, bez krzyżyka, kółko ich nie zamyka ---
    def pin_tab(self, t, on):
        if t.pinned == on or self.stack.indexOf(t) < 0:
            return
        t.pinned = on
        n = sum(1 for x in self.all_tabs() if x.pinned and x is not t)   # przypięte trzymają się lewej strony
        self.bar.moveTab(self.stack.indexOf(t), n)
        self._close_btn(t, not on)
        self.set_tab_text(t, t.title_text or "Ekran główny"); self.decorate(t)
        self.refresh_close_icons(); self.tabs_changed()
        self.bar.updateGeometry(); self.bar.adjustSize()   # wąska karta – pasek od razu się zwęża (bez dziury przed „+”)

    def all_tabs(self):
        return [self.stack.widget(i) for i in range(self.stack.count())]

    def activate(self, t):
        i = self.stack.indexOf(t)
        if i >= 0:
            if self.bar.currentIndex() == i:
                t.wake(); self.decorate(t)
            self.bar.setCurrentIndex(i)

    def close_tab(self, tab, remember=True):
        if tab is None:
            return
        if self.bar.count() <= 1:
            self.close(); return
        if self.store.feature("workspaces") and sum(1 for t in self.all_tabs() if t.ws == tab.ws) == 1:   # przestrzeń nie zostaje pusta
            self.new_tab(ws=tab.ws, activate=False)
        i = self.stack.indexOf(tab)
        if remember:
            self._remember_closed(tab, i)
        self.store.session.forget_tab(tab)
        self.bar.removeTab(i); self.stack.removeWidget(tab); tab.deleteLater()
        self.stack.setCurrentIndex(self.bar.currentIndex())
        self.sync_address(); self.tabs_changed()

    # --- zamknięte karty: widok zostaje uśpiony (Discarded – bez RAM-u stron), więc wraca z historią wstecz/dalej ---
    CLOSED_MAX = 10

    def _remember_closed(self, tab, index):
        url = tab.pending or (tab.main.url().toString() if tab.main is not None and not tab.on_home() else "")
        if not url:
            return
        v = None
        if tab.main is not None and not tab.pending:
            v = tab.sides[0].take_view() if tab.sides else tab._main
            if not tab.sides:
                tab.removeWidget(v)
            tab._main = None
            v.owner = _NULL; v.setParent(self); v.hide()   # bez właściciela: sygnały zamkniętej strony nic nie robią
            try:
                v.page().setLifecycleState(QWebEnginePage.LifecycleState.Discarded)
            except Exception:
                pass
        self._closed.append({"view": v, "url": url, "title": tab.title_text, "icon": tab.icon, "ws": tab.ws,
                             "group": tab.group, "container": tab.container, "index": index, "pinned": tab.pinned})
        while len(self._closed) > self.CLOSED_MAX:
            old = self._closed.pop(0)
            if old["view"] is not None:
                old["view"].deleteLater()

    # --- przeciąganie kart: na stronę (podział ekranu) albo na ikonę przestrzeni roboczej ---
    def _drag_tab_out(self, i):
        if not 0 <= i < self.stack.count():
            return
        from PyQt6.QtGui import QDrag
        from PyQt6.QtCore import QMimeData
        t = self.stack.widget(i); self._dragging = t
        back = getattr(self, "_before_last", None)   # wciśnięcie aktywowało przeciąganą kartę – wracamy na poprzednią,
        if back is not None and back is not t and back in self.all_tabs() and self.in_view(back):   # to ją dzielimy
            self.activate(back)
        md = QMimeData(); md.setData(TAB_MIME, str(id(t)).encode())   # identyfikator karty (nie indeks – ten się zmienia)
        d = QDrag(self.bar); d.setMimeData(md)
        th = getattr(t, "thumb", None)
        pm = th.scaledToWidth(180, Qt.TransformationMode.SmoothTransformation) if th is not None and not th.isNull() \
            else self.bar.grab(self.bar.tabRect(i))
        d.setPixmap(pm); d.setHotSpot(QPoint(pm.width() // 2, 10))
        if getattr(self, "_split_ov", None) is None:
            self._split_ov = SplitDropOverlay(self)
        self._split_ov.start(self.cur(), t)   # podgląd: na którą połowę ekranu trafi karta
        try:
            d.exec(Qt.DropAction.MoveAction)
        finally:
            self._split_ov.stop()
        QTimer.singleShot(50, lambda: setattr(self, "_dragging", None))   # po obsłudze upuszczenia (singleShot 0)

    def split_drop(self, T, t, zone, vertical=False):
        """Karta t upuszczona na połowę ekranu karty T (0 – lewa/górna, 1 – prawa/dolna)."""
        tabs = self.all_tabs()
        if T not in tabs or t not in tabs or T is t:
            return
        if T.sides:
            if zone >= len(T.sides):   # „dodaj jako trzecią stronę”
                self.add_tab_as_side(T, t)
            else:
                T.adopt_tab(T.sides[zone], t)
            return
        T.split_with("", vertical)
        if not T.sides:
            return
        T.adopt_tab(T.sides[1], t)
        if t in self.all_tabs():   # nie udało się przenieść – bez pustej połowy
            T.close_side(T.sides[1]); return
        if zone == 0:
            T.swap_split()

    def tab_from_mime(self, md):
        try:
            key = int(bytes(md.data(TAB_MIME) if hasattr(md, "data") else md).decode())
        except (ValueError, TypeError):
            return None
        return next((t for t in self.all_tabs() if id(t) == key), None)

    def drop_tab_on_view(self, view, t=None):
        """Karta upuszczona na stronę: podział ekranu z tą stroną (przy podziale – na wskazaną stronę)."""
        t, T = t or self._dragging, getattr(view, "owner", None)
        if t is None or not T or T is t or T not in self.all_tabs() or t not in self.all_tabs():
            return
        if T.sides:
            side = next((s for s in T.sides if s.view is view), T.sides[1])
        else:
            T.split_with(""); side = T.sides[1] if T.sides else None
        if side is not None:
            T.adopt_tab(side, t)

    def _drop_tab_on_ws(self, data=b""):
        t = self.tab_from_mime(data) or self._dragging
        if t is None or t not in self.all_tabs():
            return
        m = QMenu(self); m.addAction("Przenieś kartę do przestrzeni:").setEnabled(False)
        for w in self.workspaces():
            if w != t.ws:
                m.addAction(glyph("layers"), w, lambda w=w: self.move_to_ws(t, w))
        m.addAction(glyph("plus"), "Nowa przestrzeń…", lambda: self._move_new_ws(t))
        m.exec(QCursor.pos())

    def task_manager(self):
        TaskManager(self).exec()

    # --- tryb kompaktowy: pasek adresu i narzędzi schowany, wraca po najechaniu na pasek kart (Ctrl+Shift+F) ---
    def toggle_compact(self):
        self.set_compact(not self.store.settings.get("compact", False))

    def set_compact(self, on):
        self.store.settings["compact"] = bool(on); self.store.save_soon()
        self._tool.setVisible(not on)
        if on:
            self.notice.info("Tryb kompaktowy: pasek adresu pojawia się po najechaniu na karty (Ctrl+L, Ctrl+Shift+F – wyłącz).",
                             4000, "eye")

    def reveal_toolbar(self):
        if self.store.settings.get("compact"):
            self._tool.show(); self._compact_hover.hide_later()

    # --- ostrzeżenie przed fałszywą stroną logowania (domena udająca bank, sklep, pocztę…) ---
    def check_phishing(self, view):
        try:
            host = view.url().host().lower()
        except RuntimeError:
            return
        if not host or host in self.store.settings.get("phish_trust", []):
            return
        brand = lookalike(host, self.known_login_domains())
        if not brand:
            return

        def got(has_pw):
            if not has_pw or view is not self.web():
                return
            self.notice.ask(f"Uwaga: {host} może podszywać się pod {brand}. Nie wpisuj tu hasła ani danych karty.",
                            [(f"Przejdź na {brand}", lambda: view.setUrl(QUrl("https://" + brand)), True),
                             ("To zaufana strona", lambda: self._phish_trust(host), False)], icon="shield")
        for ms in (300, 2500):   # formularze logowania dorysowywane skryptami
            QTimer.singleShot(ms, lambda: _safe_js(view, "!!document.querySelector('input[type=password]')", got))

    def known_login_domains(self):
        own = {base_domain(QUrl(x["origin"]).host()) for x in (VAULT[0].logins() if VAULT and VAULT[0].available() else [])}
        return (own | LOGIN_DOMAINS) - {""}

    def _phish_trust(self, host):
        lst = self.store.settings.setdefault("phish_trust", [])
        if host not in lst:
            lst.append(host); self.store.save_soon()

    # --- „Ukryj ten element” (wskazany prawym przyciskiem) – reguła trafia do „Moich filtrów” ---
    def pick_element(self, view, x, y, up=0):
        z = view.zoomFactor() or 1.0

        def got(res):
            try:
                d = json.loads(res) if res else None
            except ValueError:
                d = None
            if not d or not d.get("sel"):
                self.notice.info("Nie udało się wskazać elementu.", 3000, "target"); return
            sel = d["sel"]
            self.notice.ask(f"Ukryć zaznaczony element? ({d['w']}×{d['h']} px, pasujących: {d['n']})",
                            [("Ukryj na zawsze", lambda: self.hide_element(view, sel), True),
                             ("Większy obszar", lambda: self.pick_element(view, None, None, 1), False),
                             ("Anuluj", lambda: _safe_js(view, PICK_CANCEL_JS), False)], icon="target")
        args = "null,null" if x is None else f"{x / z:.1f},{y / z:.1f}"
        _safe_js(view, PICK_JS % (args, up), got)

    def hide_element(self, view, sel):
        dom = base_domain(view.url().host())
        rule = f"{dom}##{sel}"
        _safe_js(view, PICK_HIDE_JS % json.dumps(sel))
        if SHIELD:
            cur = SHIELD[0].user_filters().rstrip("\n")
            if rule not in cur.splitlines():
                SHIELD[0].set_user_filters((cur + "\n" if cur else "") + rule + "\n")
        self.notice.info(f"Ukryto. Reguła zapisana w „Moich filtrach”: {rule}", 5000, "target")

    def restore_hidden(self, dom):
        if not SHIELD:
            return
        lines = SHIELD[0].user_filters().splitlines()
        keep = [ln for ln in lines if not ln.startswith(dom + "##")]
        SHIELD[0].set_user_filters("\n".join(keep) + ("\n" if keep else ""))
        self.notice.info(f"Przywrócono ukryte elementy na {dom} (odśwież stronę za chwilę).", 4000, "target")

    # --- podgląd linku (Shift+klik) ---
    def peek(self, url, container=""):
        if getattr(self, "_peek", None) is None:
            self._peek = PeekOverlay(self)
        self._peek.open(url, container)

    # --- AI znające stronę (podsumowanie, pytania, porównanie kart, wyjaśnienie zaznaczenia) ---
    def ai_ask(self, mode, selection=""):
        if not self.store.feature("assistant"):
            self.notice.info("Asystent AI jest wyłączony (Ustawienia → Funkcje).", 4000, "assistant"); return
        if mode == "compare":
            views = [t.main for t in self.all_tabs() if t.main is not None and not t.on_home() and not t.asleep
                     and not t.pending and t.main.url().scheme().startswith("http")][:6]
            if len(views) < 2:
                self.notice.info("Do porównania otwórz co najmniej dwie karty ze stronami.", 4000, "assistant"); return
            got = {}

            def one(i, res):
                got[i] = res
                if len(got) < len(views):
                    return
                parts = []
                for k in range(len(views)):
                    try:
                        d = json.loads(got[k]) if got[k] else None
                    except ValueError:
                        d = None
                    if d:
                        parts.append(f"### {k + 1}. {d['title']}\n{d['url']}\n\n{d['text']}")
                self._ai_send(AI_PROMPTS["compare"].format(pages="\n\n".join(parts)), True)
            for i, v in enumerate(views):
                _safe_js(v, PAGE_TEXT_JS % 4000, lambda r, i=i: one(i, r))
            return
        web = self.web()
        if web is None or not web.url().scheme() in ("http", "https", "file"):
            self.notice.info("Najpierw otwórz stronę w karcie.", 3000, "assistant"); return
        if mode == "explain":
            self._ai_send(AI_PROMPTS["explain"].format(title=web.title(), url=web.url().toString(), text=selection[:6000]), True)
            return

        def got(res):
            try:
                d = json.loads(res) if res else None
            except ValueError:
                d = None
            if d:
                self._ai_send(AI_PROMPTS[mode].format(**d), mode != "ask")
        _safe_js(web, PAGE_TEXT_JS % 14000, got)

    def _ai_send(self, text, submit):
        """Wkleja tekst w pole czatu otwartej usługi AI (prawdziwe wklejenie – działa w ChatGPT, Claude, Gemini,
        DeepSeek) i opcjonalnie wysyła Enterem. Bez kluczy API: używa Twojej sesji w panelu."""
        if not self.assistant.isVisible():
            self.toggle_assistant()
        self.assistant.ensure()
        v = self.assistant.current()
        if v is None:
            return
        cb = QGuiApplication.clipboard(); old = cb.text()

        def fail():
            cb.setText(text)
            self.notice.info("Nie znalazłem pola czatu – zaloguj się w panelu AI. Treść strony jest w schowku (Ctrl+V).",
                             8000, "assistant")

        def paste(ok):
            if not ok:
                fail(); return
            cb.setText(text); v.setFocus(); v.page().triggerAction(QWebEnginePage.WebAction.Paste)
            if submit:
                QTimer.singleShot(700, lambda: self._ai_enter(v))
            QTimer.singleShot(2000, lambda: cb.text() == text and cb.setText(old))   # przywróć schowek

        def go(tries=0):
            try:
                if not getattr(v, "_ready", True) and tries < 40:   # czat jeszcze się ładuje
                    QTimer.singleShot(500, lambda: go(tries + 1)); return
                v.page().runJavaScript(CHAT_INPUT_JS, QWebEngineScript.ScriptWorldId.ApplicationWorld,
                                       lambda ok: QTimer.singleShot(300 if tries else 0, lambda: paste(ok)) if ok or tries >= 6
                                       else QTimer.singleShot(800, lambda: go(tries + 1)))
            except RuntimeError:
                pass
        go()

    @staticmethod
    def _ai_enter(v):
        from PyQt6.QtGui import QKeyEvent
        try:
            tgt = v.focusProxy() or v
            for t_ in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                QApplication.postEvent(tgt, QKeyEvent(t_, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "\r"))
        except RuntimeError:
            pass

    # --- menu prawego przycisku na stronie ---
    def page_context_menu(self, view, d, hover_hl, pos):
        try:
            page = view.page()
        except RuntimeError:
            return
        A = QWebEnginePage.WebAction
        m = QMenu(self)
        trig = lambda a: (lambda: page.triggerAction(a))
        link, sel = d["link"], (d["sel"] or "").strip()
        if d["miss"] and d["sugg"]:   # podpowiedzi pisowni
            for s in d["sugg"][:6]:
                a = m.addAction(s); f = a.font(); f.setBold(True); a.setFont(f)
                a.triggered.connect(lambda _=False, s=s: page.replaceMisspelledWord(s))
            m.addSeparator()
        elif d["miss"]:
            m.addAction("Brak podpowiedzi pisowni").setEnabled(False); m.addSeparator()
        if hover_hl:   # zakreślenie pod kursorem
            self.act(m, "edit", "Notatka do zakreślenia…", lambda: self.highlight_note(view, hover_hl))
            self.act(m, "trash", "Usuń zakreślenie", lambda: self.highlight_remove(view, hover_hl))
            m.addSeparator()
        if link:
            self.act(m, "plus", "Otwórz link w nowej karcie", lambda: self.open_url_new_tab(link, view.container))
            self.act(m, "split", "Otwórz link w podziale ekranu", lambda: self.open_in_split(link))
            cm = m.addMenu(glyph("layers"), "Otwórz link w kontenerze")
            cm.addAction("Bez kontenera (zwykły profil)").triggered.connect(lambda _=False: self.open_url_new_tab(link, ""))
            for c in self.containers():
                cm.addAction(tab_icon(None, c["color"]), c["name"]).triggered.connect(
                    lambda _=False, x=c["id"]: self.open_url_new_tab(link, x))
            self.act(m, "window", "Otwórz link w nowym oknie", trig(A.OpenLinkInNewWindow))
            m.addSeparator()
            self.act(m, "copy", "Kopiuj link", lambda: QGuiApplication.clipboard().setText(link))
            cl = clean_url(link)
            if cl != link:
                self.act(m, "copy", "Kopiuj czysty link (bez śledzenia)", lambda: QGuiApplication.clipboard().setText(cl))
            self.act(m, "qr", "Kod QR linku", lambda: show_qr(self, cl))
            self.act(m, "download", "Zapisz plik z linku…", trig(A.DownloadLinkToDisk))
            m.addSeparator()
        if d["image"] and d["media_url"]:
            self.act(m, "external", "Otwórz obraz w nowej karcie", lambda: self.open_url_new_tab(d["media_url"], view.container))
            self.act(m, "save", "Zapisz obraz jako…", trig(A.DownloadImageToDisk))
            self.act(m, "copy", "Kopiuj obraz", trig(A.CopyImageToClipboard))
            self.act(m, "copy", "Kopiuj adres obrazu", trig(A.CopyImageUrlToClipboard))
            m.addSeparator()
        if d["video"]:
            self.act(m, "play", "Odtwórz / wstrzymaj", trig(A.ToggleMediaPlayPause))
            self.act(m, "external", "Obraz w obrazie", self.pip)
            self.speed_menu(m, view)
            self.act(m, "eye", "Pokaż / ukryj sterowanie", trig(A.ToggleMediaControls))
            m.addSeparator()
        if d["edit"]:
            for kind, text, act in (("undo", "Cofnij", A.Undo), ("redo", "Ponów", A.Redo)):
                self.act(m, kind, text, trig(act))
            m.addSeparator()
            for kind, text, act in (("cut", "Wytnij", A.Cut), ("copy", "Kopiuj", A.Copy), ("paste", "Wklej", A.Paste),
                                    ("paste", "Wklej jako zwykły tekst", A.PasteAndMatchStyle),
                                    ("select", "Zaznacz wszystko", A.SelectAll)):
                self.act(m, kind, text, trig(act))
            adr = addresses()
            if adr:
                am = m.addMenu(glyph("home"), "Wypełnij adres")
                for a_ in adr:
                    am.addAction(a_.get("label") or a_.get("street") or "Adres").triggered.connect(
                        lambda _=False, a_=a_: fill_address(view, a_))
            m.addSeparator()
        if sel:
            short = sel[:28] + ("…" if len(sel) > 28 else "")
            if not d["edit"]:
                self.act(m, "copy", "Kopiuj", trig(A.Copy))
            self.act(m, "search", f"Szukaj „{short}” w {CURRENT[0]}",
                     lambda: self.open_url_new_tab(ENGINES[CURRENT[0]] + quote(sel), view.container))
            self.act(m, "swap", f"Przetłumacz „{short}”", lambda: TranslatePopup(self, sel, QCursor.pos()))
            if self.store.feature("assistant"):
                self.act(m, "assistant", "Wyjaśnij z AI", lambda: self.ai_ask("explain", sel))
            if not d["edit"]:
                hm = m.addMenu(glyph("edit"), "Zakreśl")
                for name, col in HL_COLORS:
                    hm.addAction(tab_icon(None, col), name).triggered.connect(
                        lambda _=False, col=col: self.highlight_selection(view, col))
                hm.addSeparator()
                hm.addAction("Zakreśl i dodaj notatkę…").triggered.connect(
                    lambda _=False: self.highlight_selection(view, HL_COLORS[0][1], ask_note=True))
            m.addSeparator()
        if not (link or sel or d["edit"] or d["image"] or d["video"]):   # sama strona
            self.act(m, "back", "Wstecz", trig(A.Back), "Alt+Left", view.history().canGoBack())
            self.act(m, "forward", "Dalej", trig(A.Forward), "Alt+Right", view.history().canGoForward())
            self.act(m, "reload", "Odśwież", trig(A.Reload), "F5")
            m.addSeparator()
            tr_on = getattr(getattr(view, "_translator", None), "active", False)
            self.act(m, "swap", "Pokaż oryginał" if tr_on else f"Przetłumacz stronę na: {LANGS[translate_target(self.store)]}",
                     self.translate_page, "Ctrl+Shift+L")
            self.act(m, "book", "Tryb czytania", self.toggle_reader, "F9")
            if self.store.feature("assistant"):
                am = m.addMenu(glyph("assistant"), "AI")
                self.act(am, "assistant", "Podsumuj stronę", lambda: self.ai_ask("summary"))
                self.act(am, "assistant", "Zapytaj o tę stronę", lambda: self.ai_ask("ask"))
                self.act(am, "tabs", "Porównaj otwarte karty", lambda: self.ai_ask("compare"))
            self.act(m, "book", "Dodaj do „Do przeczytania”", self.read_later_add, "Ctrl+Shift+O")
            self.act(m, "qr", "Kod QR strony", lambda: show_qr(self, clean_url(view.url().toString())))
            self.act(m, "copy", "Kopiuj czysty link strony", lambda: QGuiApplication.clipboard().setText(clean_url(view.url().toString())))
            self.act(m, "save", "Zapisz stronę jako…", self.save_page, "Ctrl+S")
            self.act(m, "print", "Drukuj…", self.print_page, "Ctrl+P")
            self.speed_menu(m, view)
            m.addSeparator()
            self.act(m, "app", "Wyświetl źródło strony", self.view_source, "Ctrl+U")
        if d.get("pt") and not d["edit"]:
            x_, y_ = d["pt"]
            self.act(m, "target", "Ukryj ten element…", lambda: self.pick_element(view, x_, y_))
        if link:
            self.act(m, "eye", "Podgląd linku (Shift+klik)", lambda: self.peek(link, view.container))
        self.act(m, "tools", "Zbadaj element", trig(A.InspectElement))
        m.popup(pos)

    def speed_menu(self, m, view):
        sm = m.addMenu(glyph("play"), "Prędkość odtwarzania filmu")
        for r in (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0):
            sm.addAction(f"{r:g}×" + ("  (normalna)" if r == 1.0 else "")).triggered.connect(
                lambda _=False, r=r: _safe_js(view, SPEED_JS % r))

    def open_in_split(self, url):
        t = self.cur()
        if t is None:
            return
        if t.sides:   # podział już jest – nowa karta z linkiem
            self.open_url_new_tab(url, t.container); return
        if t.main is None or t.on_home():
            t.go(url); return
        t.split_with(url)

    # --- zakreślenia i notatki ---
    def highlight_selection(self, view, color, ask_note=False):
        note = ""
        if ask_note:
            note, ok = QInputDialog.getMultiLineText(self, "Notatka", "Notatka do zakreślenia:")
            if not ok:
                return
        url = view.url().toString()

        def got(res):
            try:
                h = json.loads(res) if res else None
            except ValueError:
                h = None
            if not h:
                return
            h.update(color=color, note=note.strip())
            Highlights.add(url, h, view.title())
            self.notice.info("Zakreślenie zapisane – zobaczysz je po powrocie na tę stronę.", 3500, "edit")
        _safe_js(view, HL_CAPTURE % (json.dumps(color), json.dumps(note.strip())), got)

    def highlight_note(self, view, hid):
        url = view.url().toString()
        cur = next((h.get("note", "") for h in Highlights.for_url(url) if h.get("id") == hid), "")
        note, ok = QInputDialog.getMultiLineText(self, "Notatka", "Notatka do zakreślenia:", cur)
        if ok:
            Highlights.set_note(url, hid, note.strip())
            _safe_js(view, "document.querySelectorAll('mark[data-lhl=%s]').forEach(function(m){m.title=%s;m.style.cursor=%s})"
                     % (json.dumps(hid), json.dumps(note.strip()), json.dumps("help" if note.strip() else "auto")))

    def highlight_remove(self, view, hid):
        Highlights.remove(view.url().toString(), hid)
        _safe_js(view, HL_REMOVE % json.dumps(hid))

    def show_highlights(self):
        HighlightsDialog(self).exec()

    # --- paleta poleceń (Ctrl+K) ---
    def palette(self):
        if getattr(self, "_palette", None) is None:
            self._palette = CommandPalette(self)
        self._palette.open()

    def palette_commands(self):
        """(ikona, nazwa, skrót, funkcja) – polecenia Luny dostępne z palety."""
        web = self.web()
        cmds = [("plus", "Nowa karta", "Ctrl+T", self.new_tab), ("window", "Nowe okno", "Ctrl+N", self.new_window),
                ("private", "Nowe okno prywatne", "Ctrl+Shift+N", lambda: self.new_window(True)),
                ("search", "Szukaj w kartach", "Ctrl+Shift+Space", self.search_tabs),
                ("reload", "Przywróć zamkniętą kartę", "Ctrl+Shift+T", self.restore_closed),
                ("tabs", "Karty i grupy", "Ctrl+Shift+A", self.toggle_tab_popup),
                ("history", "Historia", "Ctrl+H", self.show_history),
                ("layouts", "Zapisz układ podziału ekranu", "", self.save_layout),
                ("star", "Co nowego w Lunie", "", lambda: self.show_whats_new()),
                ("download", "Pobrane pliki", "Ctrl+Shift+Y", self.show_downloads),
                ("book", "Do przeczytania – lista", "", self.show_read_later),
                ("edit", "Zakreślenia i notatki", "", self.show_highlights),
                ("download", "Importuj z innej przeglądarki (Brave, Chrome, Edge)", "", lambda: ImportDialog(self).exec()),
                ("swap", "Język tłumaczenia (ustawienia)", "", lambda: self.open_settings("features")),
                ("grid", "Rynek Widgetów", "Ctrl+Shift+E", self.open_market),
                ("moon", "Ciemny tryb stron – przełącz", "Ctrl+Shift+D", self.toggle_dark),
                ("tools", "Menedżer zadań", "Shift+Esc", self.task_manager),
                ("trash", "Usuń dane przeglądania", "Ctrl+Shift+Del", self.clear_data),
                ("save", "Kopia zapasowa", "", lambda: BackupDialog(self).exec()),
                ("gear", "Ustawienia", "Ctrl+,", self.open_settings),
                ("exit", "Zakończ Lunę", "", self.quit_all)]
        if self.store.feature("assistant"):
            cmds.append(("assistant", "Asystent AI", "Ctrl+J", self.toggle_assistant))
            cmds += [("assistant", "AI: podsumuj stronę", "", lambda: self.ai_ask("summary")),
                     ("assistant", "AI: zapytaj o tę stronę", "", lambda: self.ai_ask("ask")),
                     ("assistant", "AI: porównaj otwarte karty", "", lambda: self.ai_ask("compare"))]
        if self.store.feature("webapps"):
            cmds.append(("chat", "Panel aplikacji (WhatsApp, Messenger…)", "Ctrl+Shift+K", self.toggle_webapps))
        if web is not None:
            cmds += [("book", "Tryb czytania", "F9", self.toggle_reader),
                     ("swap", "Przetłumacz stronę na polski / pokaż oryginał", "Ctrl+Shift+L", self.translate_page),
                     ("book", "Do przeczytania – dodaj tę stronę", "Ctrl+Shift+O", self.read_later_add),
                     ("split", "Podziel ekran", "Ctrl+\\", self.split_current),
                     ("external", "Obraz w obrazie", "Ctrl+Shift+P", self.pip),
                     ("search", "Znajdź na stronie", "Ctrl+F", self.find_bar.open),
                     ("star", "Dodaj stronę do ekranu głównego", "Ctrl+D", self.pin_current),
                     ("print", "Drukuj", "Ctrl+P", self.print_page), ("print", "Zapisz jako PDF", "", self.save_pdf),
                     ("save", "Zapisz stronę jako", "Ctrl+S", self.save_page),
                     ("copy", "Kopiuj link do strony", "", lambda: QGuiApplication.clipboard().setText(web.url().toString())),
                     ("copy", "Zrzut: widoczna część", "", lambda: self.screenshot("visible")),
                     ("copy", "Zrzut: cała strona", "", lambda: self.screenshot("full")),
                     ("copy", "Zrzut: zaznaczony fragment", "Ctrl+Shift+S", lambda: self.screenshot("region")),
                     ("zoom", "Powiększ", "Ctrl++", lambda: self.zoom(1)), ("zoom", "Pomniejsz", "Ctrl+-", lambda: self.zoom(-1)),
                     ("zoom", "Powiększenie 100%", "Ctrl+0", lambda: self.zoom(0)),
                     ("play", "Prędkość filmu: 1,5×", "", lambda: _safe_js(web, SPEED_JS % 1.5)),
                     ("play", "Prędkość filmu: 2×", "", lambda: _safe_js(web, SPEED_JS % 2.0)),
                     ("play", "Prędkość filmu: normalna", "", lambda: _safe_js(web, SPEED_JS % 1.0)),
                     ("tools", "Narzędzia deweloperskie", "F12", self.devtools),
                     ("app", "Źródło strony", "Ctrl+U", self.view_source)]
        cmds.append(("window", "Pełny ekran", "F11", self.toggle_fullscreen))
        cmds.append(("eye", "Tryb kompaktowy – przełącz", "Ctrl+Shift+F", self.toggle_compact))
        for pid, title, _ in SETTINGS_PAGES:
            cmds.append(("gear", f"Ustawienia: {title}", "", lambda p=pid: self.open_settings(p)))
        return cmds

    def palette_entries(self):
        out = []

        def add(kind, rank, icon, title, sub, fn, extra=""):
            out.append({"kind": kind, "rank": rank, "icon": icon, "title": title, "sub": sub, "fn": fn,
                        "hay": fold(f"{title} {sub} {extra}")})
        for ic, name, sc, fn in self.palette_commands():
            add("cmd", 0, glyph(ic), name, sc, fn, "polecenie")
        for t in self.all_tabs():
            url = t.pending or (t.main.url().toString() if t.main is not None and not t.on_home() else "")
            title = t.title_text or ("Ekran główny" if not url else url)

            def go_tab(t=t):
                if t in self.all_tabs():
                    if t.ws != self.ws and self.store.feature("workspaces"):
                        self.switch_ws(t.ws)
                    self.activate(t)
            add("tab", 1, tab_icon(t.icon, self.container_color(t.container), t.asleep or bool(t.pending)),
                title, "karta  ·  " + host_of(url) if url else "karta", go_tab, url)
        for lay in self.layouts():
            add("cmd", 0, glyph("layouts"), "Układ: " + lay.get("name", ""), "  +  ".join(host_of(u) for u in lay.get("urls", [])),
                lambda lay=lay: self.open_layout(lay), "układ podziału ekranu")
        for it in self.store.items[:60]:
            add("tile", 2, mini_icon(it["name"], it["url"]), it["name"], "ekran główny  ·  " + host_of(it["url"]),
                lambda u=it["url"]: self.open_url_new_tab(u), it["url"])
        for b_ in Bookmarks.items()[:500]:
            add("tile", 2, mini_icon(b_["title"], b_["url"]), b_["title"], "zakładka  ·  " + (b_.get("folder") or host_of(b_["url"])),
                lambda u=b_["url"]: self.open_url_new_tab(u), b_["url"])
        for it in ReadLater.get().unread()[:30]:
            add("later", 2, glyph("book"), it["title"], "do przeczytania  ·  " + host_of(it["url"]),
                lambda it=it: self.open_read_later(it, False), it["url"])
        seen = set()
        for h in self.store.history[:300]:
            if h["url"] in seen:
                continue
            seen.add(h["url"])
            add("hist", 3, mini_icon(h.get("name") or h["url"], h["url"]), h.get("name") or h["url"],
                "historia  ·  " + host_of(h["url"]), lambda u=h["url"]: self.open_url_new_tab(u), h["url"])
        return out

    def palette_go(self, text):
        t = self.cur()
        if t is None or not t.on_home():
            t = self.new_tab()
        t.go(text)

    # --- do przeczytania ---
    def read_later_add(self):
        web = self.web()
        if web is None or not web.url().scheme().startswith("http"):
            self.notice.info("Do listy można dodać tylko stronę internetową.", 4000, "book"); return
        it = ReadLater.get().add(web)
        self.notice.ask(f"Dodano do „Do przeczytania” (z kopią offline): {it['title'][:60]}",
                        [("Pokaż listę", self.show_read_later, False), ("OK", None, False)], icon="book")

    def show_read_later(self):
        ReadLaterDialog(self).exec()

    def open_read_later(self, it, offline=False):
        rl = ReadLater.get(); p = rl.offline_path(it)
        if offline and p.exists():
            self.open_url_new_tab(QUrl.fromLocalFile(str(p)).toString())
        else:
            self.open_url_new_tab(it["url"])
        rl.set_read(it, True)

    def read_later_menu(self, m):
        m.clear(); web = self.web(); rl = ReadLater.get()
        self.act(m, "plus", "Dodaj tę stronę", self.read_later_add, "Ctrl+Shift+O",
                 web is not None and web.url().scheme().startswith("http"))
        self.act(m, "book", "Cała lista…", self.show_read_later)
        un = rl.unread()
        if un:
            m.addSeparator()
            for it in un[:12]:
                m.addAction(mini_icon(it["title"], it["url"]), it["title"][:56]).triggered.connect(
                    lambda _=False, it=it: self.open_read_later(it, False))

    def search_tabs(self):
        if getattr(self, "_tab_search", None) is None:
            self._tab_search = TabSearch(self)
        self._tab_search.open()

    def restore_closed(self, i=None):
        if not self._closed:
            return
        d = self._closed.pop(len(self._closed) - 1 if i is None else i)
        ws = d["ws"] if d["ws"] in self.workspaces() else self.ws
        t = self.new_tab(container=d["container"], ws=ws, group=d["group"], activate=False)
        self.bar.moveTab(self.stack.indexOf(t), max(0, min(d["index"], self.bar.count() - 1)))
        v = d["view"]
        if v is not None:
            v.setParent(None)
            try:
                v.page().setLifecycleState(QWebEnginePage.LifecycleState.Active)
            except Exception:
                pass
            t.adopt_view(v); v.show()
        else:
            t.go(d["url"])
        if d.get("pinned"):
            self.pin_tab(t, True)
        if ws != self.ws:
            self.switch_ws(ws)
        self.activate(t)

    def _tab_hover(self, i):
        p = self._preview
        if i < 0 or i >= self.stack.count():
            if p is not None:
                p.hide()
            return
        t = self.stack.widget(i)
        if p is None:
            self._preview = p = TabPreview()
        url = t.pending or (t.main.url().toString() if t.main is not None and not t.on_home() else "")
        title = t.title_text or ("Ekran główny" if not url else url)
        info = [host_of(url)] + self.bar.tabToolTip(i).split("\n")[1:]   # grupa, kontener, podział, uśpienie
        r = self.bar.tabRect(i)
        p.show_for(t if t is not self.cur() else None, title, info, self.bar.mapToGlobal(QPoint(r.left(), r.bottom() + 6)))

    def _snap(self, t):
        """Miniatura do podglądu – jedno zdjęcie strony w chwili jej opuszczania (bez pracy w tle)."""
        try:
            w = t._web_widget()
            if w is None or t.on_home() or not w.isVisible():
                return
            pm = w.grab()
            if not pm.isNull() and pm.width() > 40:
                pm = pm.scaledToWidth(260, Qt.TransformationMode.SmoothTransformation)
                t.thumb = pm.copy(0, 0, 260, min(pm.height(), 160))
        except RuntimeError:
            pass

    def on_tab_changed(self, i):
        prev = self._prev_tab
        if self._preview is not None:
            self._preview.hide()
        if prev is not None and prev in self.all_tabs():
            prev.last_active = time.time()
            self._snap(prev)
            if self.saving() and 0 <= i < self.stack.count() and self.stack.widget(i) is not prev:
                self._pause_background(prev)   # na baterii film w opuszczonej karcie się zatrzymuje
        if 0 <= i < self.stack.count():
            self.stack.setCurrentIndex(i)
            t = self.stack.widget(i)
            if t is not prev:
                self._before_last = prev
            self._prev_tab = t
            if t.asleep or t.pending:
                t.wake(); self.decorate(t)
            t.last_active = time.time()
        self.sync_address()
        self.refresh_close_icons(); self.update_sidebars_soon(); self.hide_suggest(); self.tabs_changed()

    def on_tab_moved(self, frm, to):
        w = self.stack.widget(frm)
        self.stack.removeWidget(w); self.stack.insertWidget(to, w)
        self.stack.setCurrentIndex(self.bar.currentIndex()); self.tabs_changed()

    def decorate(self, t):
        i = self.stack.indexOf(t)
        if i < 0:
            return
        col = self.container_color(t.container)
        has = (t.icon is not None and not t.icon.isNull()) or col or t.asleep or t.pending or t.pinned
        self.bar.setTabIcon(i, tab_icon(t.icon, col, t.asleep or bool(t.pending)) if has else QIcon())
        tip = t.title_text or "Ekran główny"
        if t.group:
            tip += f"\nGrupa: {t.group}"
        if t.container:
            tip += f"\nKontener: {self.container_name(t.container)}"
        if t.sides and any(s.view is not None for s in t.sides[1:]):
            tip += "\nPodzielony ekran z: " + ", ".join(s.view.title() or host_of(s.view.url().toString())
                                                       for s in t.sides[1:] if s.view is not None)
        if t.asleep or t.pending:
            tip += "\nUśpiona – wybudzi się po kliknięciu"
        self.bar.setTabToolTip(i, tip)

    def tabs_changed(self):
        self._tabs_t.start(30)

    def _apply_tabs(self):
        """Pokazuje tylko karty bieżącej przestrzeni roboczej, odświeża pionowy panel i zapisuje sesję."""
        for i in range(self.bar.count()):
            self.bar.setTabVisible(i, self.in_view(self.stack.widget(i)))
        c = self.cur()
        if c is not None and not self.in_view(c):
            mine = [t for t in self.all_tabs() if t.ws == self.ws]
            last = self._ws_last.get(self.ws)
            target = last if last in mine else (mine[0] if mine else None)
            if target is None:
                self.new_tab(); return
            self.activate(target); c = target
        if c is not None:
            self._ws_last[c.ws] = c
        if self.tabpanel.isVisible():
            self.tabpanel.rebuild()
            if self.tab_popup.isVisible() and self.cur() is not self._popup_from:   # wybrano kartę z listy – zamknij
                self.tab_popup.hide()
        self.ws_btn.setToolTip(f"Przestrzeń robocza: {self.ws}")
        self.store.settings["session"] = self.session_data(); self.store.save_soon()

    def cycle_tab(self, d):
        vis = [i for i in range(self.bar.count()) if self.bar.isTabVisible(i)]
        if len(vis) > 1:
            cur = self.bar.currentIndex()
            k = vis.index(cur) if cur in vis else 0
            self.bar.setCurrentIndex(vis[(k + d) % len(vis)])

    # --- oszczędzanie baterii (tylko gdy jest bateria; stan zasilania sprawdza istniejący, minutowy zegar usypiania) ---
    def saving(self):
        return self._on_batt and self.store.feature("battery_saver") and has_battery()

    def _check_power(self):
        if not has_battery():
            return
        batt = not power_status()[1]
        if batt != self._on_batt:
            self._on_batt = batt
            if batt and self.store.feature("battery_saver") and self.isActiveWindow():
                self.notice.info("Zasilanie z baterii: karty usypiają się po 5 minutach, a filmy w tle są zatrzymywane.")

    PAUSE_VIDEO_JS = ("document.querySelectorAll('video').forEach(v => { if (!v.paused && document.pictureInPictureElement !== v) "
                      "v.pause(); })")

    def _pause_background(self, t):
        for v in t.views():
            try:
                v.page().runJavaScript(self.PAUSE_VIDEO_JS, QWebEngineScript.ScriptWorldId.ApplicationWorld)
            except RuntimeError:
                pass

    def _sleep_tick(self):
        """Usypia karty nieużywane dłużej niż ustawiony czas (nie: bieżącą, grającą dźwięk ani ładującą się).
        Na baterii (oszczędzanie włączone) – najpóźniej po 5 minutach."""
        self._check_power()
        if not self.store.feature("sleep_tabs") and not self.saving():
            return
        limit = int(self.store.settings.get("sleep_after", 15)) * 60
        if self.saving():
            limit = min(limit, 5 * 60)
        low = low_memory()
        if low:   # mało wolnej pamięci RAM w systemie: usypiaj wcześniej (karta nieużywana od 2 minut)
            limit = min(limit, 2 * 60)
        now = time.time(); cur = self.cur(); changed = False
        for t in sorted(self.all_tabs(), key=lambda x: x.last_active):   # najdawniej używane najpierw
            if t is not cur and not t.asleep and t.main is not None and now - t.last_active > limit:
                t.sleep(); changed = changed or t.asleep
                if t.asleep:
                    self.decorate(t)
        if changed:
            self.tabs_changed()

    def sleep_now(self, t):
        if t is not self.cur():
            t.sleep(); self.decorate(t); self.tabs_changed()

    # --- sesja (karty, grupy, przestrzenie i kontenery po ponownym uruchomieniu) ---
    def session_data(self):
        tabs = []
        for t in self.all_tabs():
            url = t.pending or (t.main.url().toString() if t.main is not None and not t.on_home() else "")
            d = {"url": url, "title": t.title_text if url else "", "ws": t.ws, "group": t.group, "container": t.container}
            sp = t.split_state() if url else None
            if sp:
                d["split"] = sp
            if t.pinned:
                d["pinned"] = True
            tabs.append(d)
        return {"tabs": tabs, "current": self.stack.currentIndex()}

    def restore_session(self, session=None):
        """session: zapisana sesja do odtworzenia (np. po awarii); domyślnie – ta z ustawień, gdy włączone przywracanie."""
        s = session if session is not None else (self.store.settings.get("session") if self.store.feature("restore_tabs") else None)
        tabs = [d for d in (s or {}).get("tabs", []) if isinstance(d, dict)]
        if not tabs:
            if session is None:
                self.new_tab()
            return
        known = self.workspaces()
        base = self.stack.count()   # przy przywracaniu po awarii obok już otwartych kart
        for d in tabs:
            nt = self.new_tab(container=d.get("container", ""), ws=d.get("ws") if d.get("ws") in known else known[0],
                              group=d.get("group", ""), title=d.get("title", ""), lazy_url=d.get("url", ""), activate=False)
            if d.get("url") and isinstance(d.get("split"), dict):
                nt.pending_split = d["split"]
            if d.get("pinned"):
                self.pin_tab(nt, True)
        i = s.get("current", 0)
        i = base + i if isinstance(i, int) else base
        t = self.stack.widget(i) if 0 <= i < self.stack.count() else self.stack.widget(base)
        self.ws = t.ws; self.store.settings["ws_current"] = t.ws
        self.activate(t)
        if t.pending:
            t.wake(); self.decorate(t)

    # --- przestrzenie robocze ---
    def workspaces(self):
        ws = self.store.settings.setdefault("workspaces", ["Ogólna"])
        if not ws:
            ws.append("Ogólna")
        return ws

    def switch_ws(self, name):
        if name == self.ws:
            return
        c = self.cur()
        if c is not None:
            self._ws_last[c.ws] = c
        self.ws = name; self.store.settings["ws_current"] = name; self.store.save_soon()
        self._apply_tabs()

    def in_view(self, t):
        """Karta widoczna w bieżącym widoku (bez przestrzeni roboczych widać wszystkie karty)."""
        return not self.store.feature("workspaces") or t.ws == self.ws

    def ws_menu(self):
        m = self.ws_btn.menu(); m.clear()
        m.addAction(glyph("layers"), "Przestrzenie robocze").setEnabled(False)
        for name in self.workspaces():
            n = sum(1 for t in self.all_tabs() if t.ws == name)
            a = m.addAction(f"{name}  ·  {n}"); a.setCheckable(True); a.setChecked(name == self.ws)
            a.triggered.connect(lambda _=False, x=name: self.switch_ws(x))
        m.addSeparator()
        m.addAction("Nowa przestrzeń…", self.new_ws)
        m.addAction("Zmień nazwę bieżącej…", self.rename_ws)
        d = m.addAction("Usuń bieżącą (zamyka jej karty)", self.delete_ws); d.setEnabled(len(self.workspaces()) > 1)

    def new_ws(self):
        name, ok = QInputDialog.getText(self, "Nowa przestrzeń", "Nazwa (np. Praca, Zakupy, Hobby):")
        name = name.strip()
        if ok and name and name not in self.workspaces():
            self.workspaces().append(name); self.store.save_soon(); self.switch_ws(name)

    def rename_ws(self):
        name, ok = QInputDialog.getText(self, "Zmień nazwę", "Nowa nazwa przestrzeni:", text=self.ws)
        name = name.strip()
        if ok and name and name not in self.workspaces():
            ws = self.workspaces(); ws[ws.index(self.ws)] = name
            for t in self.all_tabs():
                if t.ws == self.ws:
                    t.ws = name
            self.ws = name; self.store.settings["ws_current"] = name; self._apply_tabs()

    def delete_ws(self):
        if len(self.workspaces()) <= 1:
            return
        mine = [t for t in self.all_tabs() if t.ws == self.ws]
        if QMessageBox.question(self, "Luna", f"Usunąć przestrzeń „{self.ws}” i zamknąć jej karty ({len(mine)})?") \
                != QMessageBox.StandardButton.Yes:
            return
        gone = self.ws; ws = self.workspaces(); ws.remove(gone)
        self.switch_ws(ws[0])
        for t in mine:
            i = self.stack.indexOf(t); self.store.session.forget_tab(t)
            self.bar.removeTab(i); self.stack.removeWidget(t); t.deleteLater()
        self.stack.setCurrentIndex(self.bar.currentIndex()); self.tabs_changed()

    def move_to_ws(self, t, name):
        t.ws = name; self.tabs_changed()

    # --- grupy kart ---
    def groups(self):
        seen = []
        for t in self.all_tabs():
            if self.in_view(t) and t.group and t.group not in seen:
                seen.append(t.group)
        return seen

    def group_dialog(self, t):
        if t is None:
            return
        name, ok = QInputDialog.getItem(self, "Grupa kart", "Nazwa grupy (projektu):", self.groups() or ["Projekt"], 0, True)
        if ok and name.strip():
            t.group = name.strip(); self.decorate(t); self.tabs_changed()
            if not self.store.feature("vertical_tabs"):
                QToolTip.showText(QCursor.pos(), "Grupy widać pod przyciskiem „Karty i grupy” na pasku narzędzi.", self)

    def dock_tabpanel(self, docked):
        """Panel kart: przypięty po lewej (Funkcje) albo w okienku pod przyciskiem „Karty i grupy” na pasku narzędzi."""
        tp = self.tabpanel
        if docked:
            self.tab_popup.hide()
            if self.body.indexOf(tp) < 0:
                self.body.insertWidget(0, tp)
            tp.setFixedWidth(self._tabpanel_w()); tp.setObjectName("tabpanel"); tp.show()
        else:
            if self.tab_popup.layout().indexOf(tp) < 0:
                self.tab_popup.layout().addWidget(tp)
            tp.setFixedWidth(320); tp.setObjectName("tabpanelpop")
        tp.style().unpolish(tp); tp.style().polish(tp)

    def toggle_tab_popup(self):
        if self.store.feature("vertical_tabs"):   # panel przypięty: logo zwija / rozwija panel
            self.tabpanel.setVisible(not self.tabpanel.isVisible()); return
        p = self.tab_popup
        if p.isVisible():
            p.hide(); return
        self._popup_from = self.cur(); self.tabpanel.rebuild()
        h = min(560, max(260, self.height() - 140)); p.resize(322, h)
        b = self.logo_btn; pos = b.mapToGlobal(QPoint(0, b.height() + 6))
        p.move(pos); p.show(); self.tabpanel.tree.setFocus()

    def group_menu(self, name, pos):
        m = QMenu(self)
        m.addAction("Nowa karta w grupie", lambda: self.new_tab(group=name))
        m.addAction("Zmień nazwę…", lambda: self.rename_group(name))
        m.addAction("Rozgrupuj", lambda: self.set_group(name, ""))
        m.addSeparator(); m.addAction("Zamknij wszystkie karty grupy", lambda: self.close_group(name))
        m.exec(pos)

    def set_group(self, old, new):
        for t in self.all_tabs():
            if self.in_view(t) and t.group == old:
                t.group = new; self.decorate(t)
        self.tabs_changed()

    def rename_group(self, name):
        new, ok = QInputDialog.getText(self, "Zmień nazwę grupy", "Nowa nazwa:", text=name)
        if ok and new.strip():
            self.set_group(name, new.strip())

    def close_group(self, name):
        for t in [t for t in self.all_tabs() if self.in_view(t) and t.group == name]:
            self.close_tab(t)

    # --- kontenery (osobne ciasteczka i logowania) ---
    def containers(self):
        return self.store.settings.setdefault("containers", [])

    def container_ids(self):
        return {c["id"] for c in self.containers()}

    def container_color(self, cid):
        return next((c["color"] for c in self.containers() if c["id"] == cid), None) if cid else None

    def container_name(self, cid):
        return next((c["name"] for c in self.containers() if c["id"] == cid), "") if cid else ""

    def new_container(self, then=None):
        name, ok = QInputDialog.getText(self, "Nowy kontener", "Nazwa (np. Praca, Konto 2, Zakupy):")
        name = name.strip()
        if not (ok and name):
            return None
        cid = (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "k") + "-" + secrets.token_hex(3)
        c = {"id": cid, "name": name, "color": CONTAINER_COLORS[len(self.containers()) % len(CONTAINER_COLORS)]}
        self.containers().append(c); self.store.save_soon()
        if then:
            then(cid)
        return cid

    def container_menu(self, pos, tab=None):
        """Nowa karta w kontenerze albo (dla karty) otwarcie jej strony ponownie w wybranym kontenerze."""
        m = QMenu(self)
        act = (lambda cid: self.reopen_in(tab, cid)) if tab is not None else (lambda cid: self.new_tab(container=cid))
        a = m.addAction("Bez kontenera (zwykły profil)"); a.triggered.connect(lambda _=False: act(""))
        for c in self.containers():
            a = m.addAction(tab_icon(None, c["color"]), c["name"]); a.triggered.connect(lambda _=False, x=c["id"]: act(x))
        m.addSeparator(); m.addAction("Nowy kontener…", lambda: self.new_container(act))
        m.exec(pos)

    def reopen_in(self, tab, cid):
        if tab is None or cid == tab.container:
            return
        url = tab.pending or (tab.main.url().toString() if tab.main is not None and not tab.on_home() else "")
        t = self.new_tab(container=cid, ws=tab.ws, group=tab.group)
        self.bar.moveTab(self.stack.indexOf(t), self.stack.indexOf(tab) + 1)
        if url:
            t.go(url)
        self.close_tab(tab)

    # --- menu karty (pasek poziomy i panel pionowy) ---
    def tab_menu(self, t, pos):
        m = QMenu(self)
        m.addAction(glyph("pin"), "Odepnij kartę" if t.pinned else "Przypnij kartę", lambda: self.pin_tab(t, not t.pinned))
        m.addSeparator()
        if t.group:
            m.addAction("Nowa karta w tej grupie", lambda: self.new_tab(group=t.group, container=t.container))
        gm = m.addMenu("Grupa")
        for g in self.groups():
            if g != t.group:
                gm.addAction(f"Przenieś do „{g}”", lambda _=False, g=g: (setattr(t, "group", g), self.decorate(t), self.tabs_changed()))
        gm.addAction("Nowa grupa…", lambda: self.group_dialog(t))
        if t.group:
            gm.addAction("Usuń z grupy", lambda: (setattr(t, "group", ""), self.decorate(t), self.tabs_changed()))
        wm = m.addMenu("Przenieś do przestrzeni"); wm.menuAction().setVisible(self.store.feature("workspaces"))
        for w in self.workspaces():
            if w != t.ws:
                wm.addAction(w, lambda _=False, w=w: self.move_to_ws(t, w))
        wm.addAction("Nowa przestrzeń…", lambda: self._move_new_ws(t))
        m.addAction("Otwórz w kontenerze…", lambda: self.container_menu(QCursor.pos(), t))
        sm = m.addMenu(glyph("split"), "Podziel ekran")
        if t.main is None or t.pending:
            sm.setEnabled(False)
        if t.split is None:
            sm.addAction("Wybierz stronę…", lambda: (self.activate(t), t.split_with("")))
        cands = self.split_candidates(t)
        if cands:
            sm.addSeparator()
        for o, url in cands:
            sm.addAction(tab_icon(o.icon), (o.title_text or url)[:40], lambda _=False, o=o: self.split_with_tab(t, o))
        if t.sides:
            if len(t.sides) < Tab.MAX_SIDES:
                am = sm.addMenu(glyph("plus"), "Dodaj trzecią stronę")
                am.addAction("Wybierz stronę…", lambda: (self.activate(t), t.add_side()))
                if cands:
                    am.addSeparator()
                for o, url in cands:
                    am.addAction(tab_icon(o.icon), (o.title_text or url)[:40], lambda _=False, o=o: self.add_tab_as_side(t, o))
            sm.addSeparator()
            sm.addAction(glyph("swap"), "Zamień strony miejscami", t.swap_split)
            sm.addAction(glyph("splitv"), "Układ pionowy / poziomy", t.turn_split)
            sy = sm.addAction(glyph("scrollsync"), "Przewijaj strony razem"); sy.setCheckable(True); sy.setChecked(t.scroll_sync)
            sy.toggled.connect(lambda on: t.set_scroll_sync(on))
            sm.addAction(glyph("layouts"), "Zapisz ten układ…", lambda: self.save_layout(t))
            last = t.sides[-1]; nm = "trzecią" if len(t.sides) > 2 else "drugą"
            if last.view is not None:
                sm.addAction(glyph("external"), f"Odłącz {nm} stronę do karty", lambda: t.detach_side(last))
            sm.addAction(glyph("close"), f"Zamknij {nm} stronę", t.unsplit)
        z = m.addAction("Uśpij teraz", lambda: self.sleep_now(t)); z.setEnabled(t is not self.cur() and t.web is not None and not t.asleep)
        m.addSeparator(); m.addAction("Zamknij kartę", lambda: self.close_tab(t))
        m.exec(pos)

    def _move_new_ws(self, t):
        name, ok = QInputDialog.getText(self, "Nowa przestrzeń", "Nazwa:")
        name = name.strip()
        if ok and name:
            if name not in self.workspaces():
                self.workspaces().append(name)
            self.move_to_ws(t, name)

    def _bar_menu(self, pos):
        i = self.bar.tabAt(pos)
        if i >= 0:
            self.tab_menu(self.stack.widget(i), self.bar.mapToGlobal(pos))

    def split_current(self):
        """Ctrl+\\: włącza podział (wybór drugiej strony); ponownie – druga strona wraca do osobnej karty (nic nie ginie)."""
        t = self.cur()
        if t is None:
            return
        if t.sides:
            s = t.sides[-1]
            t.detach_side(s) if s.view is not None else t.close_side(s)
        elif t.main is not None and not t.on_home():
            t.split_with("")

    def split_with_tab(self, t, o):
        self.activate(t)
        if t.split is None:
            t.split_with("")
        if t.sides:   # pusta strona podziału, jeśli jest – inaczej druga
            t.adopt_tab(next((s for s in t.sides[1:] if s.view is None), t.sides[1]), o)

    def add_tab_as_side(self, t, o):
        """Karta o jako kolejna (trzecia) strona podziału karty t."""
        self.activate(t)
        s = t.add_side() if t.sides else None
        if s is None:
            return self.split_with_tab(t, o)
        t.adopt_tab(s, o)
        if o in self.all_tabs() and s in (t.sides or []) and s.view is None:   # nie udało się – bez pustej strony
            t.close_side(s)

    # --- zapisane układy podziału („Praca: Gmail + Kalendarz + Notion”) – jedno kliknięcie otwiera wszystkie strony ---
    def layouts(self):
        lst = self.store.settings.get("layouts")
        return lst if isinstance(lst, list) else []

    def layout_of(self, t):
        if t is None or not t.sides:
            return None
        urls = [s.view.url().toString() for s in t.sides if s.view is not None]
        urls = [u for u in urls if u.startswith(("http://", "https://", "file:"))]
        if len(urls) < 2:
            return None
        return {"urls": urls, "v": t.split.orientation() == Qt.Orientation.Vertical,
                "sizes": t.split.sizes(), "sync": bool(t.scroll_sync)}

    def save_layout(self, t=None):
        t = t or self.cur(); lay = self.layout_of(t)
        if lay is None:
            self.notice.info("Najpierw podziel ekran na 2 albo 3 strony – wtedy można zapisać układ.", 5000, "layouts"); return
        names = [host_of(u).split(".")[0].capitalize() for u in lay["urls"]]
        name = luna_prompt(self, "Zapisz układ podziału", "Nazwa układu (pojawi się w menu i w palecie Ctrl+K):",
                           " + ".join(names), "layouts")
        if not name:
            return
        lst = [x for x in self.layouts() if x.get("name") != name] + [dict(lay, name=name)]
        self.store.settings["layouts"] = lst; self.store.save_settings()
        self.notice.info(f"Zapisano układ „{name}” – znajdziesz go w menu: Karty i okna → Układy podziału.", 5000, "layouts")

    def open_layout(self, lay, tab=None):
        """Otwiera zapisany układ: na ekranie głównym bieżącej karty albo w nowej karcie."""
        urls = [u for u in lay.get("urls", []) if isinstance(u, str)][:Tab.MAX_SIDES]
        if not urls:
            return
        t = tab or self.cur()
        if t is None or not (t.main is None or t.on_home()) or t.sides or t.pending:
            t = self.new_tab()
        self.activate(t); t.go(urls[0])
        if len(urls) > 1:
            t.split_with(urls[1], bool(lay.get("v")))
            for u in urls[2:]:
                t.add_side(u)
            sz = lay.get("sizes")
            if t.split is not None and isinstance(sz, list) and len(sz) == len(t.sides) and all(isinstance(x, int) for x in sz):
                QTimer.singleShot(0, lambda: t.split is not None and t.split.setSizes(sz))
            if t.sides:
                t.set_active_side(t.sides[0])
            if lay.get("sync"):
                t.set_scroll_sync(True)

    def remove_layout(self, name):
        self.store.settings["layouts"] = [x for x in self.layouts() if x.get("name") != name]; self.store.save_settings()

    def layouts_menu(self, m):
        m.clear(); lst = self.layouts()
        for lay in lst:
            hosts = ", ".join(host_of(u) for u in lay.get("urls", []))
            a = self.act(m, "layouts", lay.get("name", "Układ"), lambda lay=lay: self.open_layout(lay)); a.setToolTip(hosts)
        if not lst:
            m.addAction("Brak zapisanych układów").setEnabled(False)
        m.addSeparator()
        self.act(m, "save", "Zapisz bieżący układ…", self.save_layout, enabled=self.layout_of(self.cur()) is not None)
        if lst:
            dm = m.addMenu(glyph("trash"), "Usuń układ")
            for lay in lst:
                dm.addAction(lay.get("name", "Układ"), lambda n=lay.get("name"): self.remove_layout(n))

    def split_candidates(self, tab):
        """Karty, które można dołożyć do podziału: z bieżącej przestrzeni, ze stroną i bez własnego podziału."""
        out = []
        for o in self.all_tabs():
            if o is tab or o.split is not None or not self.in_view(o):
                continue
            url = o.pending or (o.main.url().toString() if o.main is not None and not o.on_home() else "")
            if url:
                out.append((o, url))
        return out

    def split_focus_changed(self, tab):
        if tab is self.cur():
            self.sync_address(); self.update_page_bg()

    def _focus_changed(self, old, new):
        t = self.cur()
        if new is None or t is None or not t.sides:
            return
        for s in t.sides:
            if s.isAncestorOf(new):
                t.set_active_side(s); break

    # --- tarcza (blokada śledzenia) ---
    def shield_menu(self, m=None):
        m = m or self.shield_btn.menu(); m.clear(); t = self.cur(); sh = SHIELD[0] if SHIELD else None
        url = t.web.url().toString() if t and t.web is not None and not t.on_home() else ""
        if sh is None or not self.store.feature("adblock"):
            m.addAction("Blokada reklam i śledzenia jest wyłączona").setEnabled(False)
        else:
            m.addAction(f"Zablokowano na tej stronie: {sh.count(url)}").setEnabled(False)
            m.addAction(f"Łącznie od początku: {sh.total}").setEnabled(False)
            if sh.net is not None:
                m.addAction(f"Aktywnych reguł: {sh.rules_total():,}".replace(",", " ")).setEnabled(False)
            elif sh.status_text():
                m.addAction(sh.status_text()).setEnabled(False)
            if url:
                dom = base_domain(QUrl(url).host())
                a = m.addAction(f"Blokuj na {dom}"); a.setCheckable(True); a.setChecked(dom not in sh.allow)
                a.toggled.connect(lambda on, d=dom: self.shield_allow(d, not on))
                self.shield_details(m, sh, url, dom)
        m.addSeparator(); m.addAction("Prywatność…", lambda: self.open_settings("privacy"))

    def shield_details(self, m, sh, url, dom):
        """Co zablokowano na tej stronie (domeny i liczby) + odblokowanie jednej domeny tylko na tej stronie."""
        if dom in sh.allow:
            return
        rows = sh.breakdown(url)
        if rows:
            m.addSeparator()
            m.addAction("Zablokowane domeny (kliknij, by odblokować tylko tutaj):").setEnabled(False)
            for d, n in rows[:12]:
                sub = m.addMenu(f"{d}  ·  {n}")
                sub.addAction(f"Odblokuj {d} na {dom}", lambda d=d: self.shield_exception(url, d, True))
                sub.addAction("Kopiuj nazwę domeny", lambda d=d: QApplication.clipboard().setText(d))
            if len(rows) > 12:
                rest = sum(n for _, n in rows[12:])
                m.addAction(f"…i jeszcze {len(rows) - 12} domen ({rest} zapytań)").setEnabled(False)
        hidden = [ln for ln in sh.user_filters().splitlines() if ln.startswith(dom + "##")]
        if hidden:
            m.addSeparator()
            m.addAction(f"Przywróć elementy ukryte na {dom} ({len(hidden)})", lambda: self.restore_hidden(dom))
        exc = sh.site_exceptions(url)
        if exc:
            m.addSeparator()
            m.addAction(f"Odblokowane na {dom}:").setEnabled(False)
            for d in exc:
                m.addAction(f"Przywróć blokadę: {d}", lambda d=d: self.shield_exception(url, d, False))

    def shield_exception(self, url, domain, allowed):
        if SHIELD:
            SHIELD[0].set_site_exception(url, domain, allowed)
        self.nav("reload")

    def shield_allow(self, dom, allow):
        lst = [d for d in self.store.settings.get("shield_allow", []) if d != dom] + ([dom] if allow else [])
        self.store.settings["shield_allow"] = lst; self.store.save_soon()
        if SHIELD:
            SHIELD[0].reload()
        self.nav("reload")

    def update_shield(self):
        t = self.cur(); sh = SHIELD[0] if SHIELD else None
        on = self.store.feature("adblock") and sh is not None
        url = t.web.url().toString() if t and t.web is not None and not t.on_home() else ""
        n = sh.count(url) if on and url else 0
        self.shield_btn.setIcon(glyph("shield", "#3ddc84" if on else "#6f6f6f"))
        self.shield_btn.setToolTip(f"Blokada reklam i śledzenia: zablokowano {n} na tej stronie" if on else
                                   "Blokada reklam i śledzenia wyłączona")

    # --- hasła, generator i aliasy e-mail ---
    def vault(self):
        return VAULT[0] if VAULT and VAULT[0].available() and self.store.feature("passwords") else None

    def on_pw(self, d):
        v = self.vault()
        if v is None or self.private:
            return
        o = d.get("origin", ""); u = (d.get("u") or "").strip(); p = d.get("p") or ""
        if not o.startswith("http"):
            return
        if not p:                       # pierwszy krok logowania dwuetapowego – zapamiętaj login
            if u:
                self._last_user[o] = u
            return
        u = u or self._last_user.get(o, "")
        x = v.find(o, u)
        if v.never(o) or (x and x["pw"] == p) or self._pw_pending == (o, u, p):
            return
        self._pw_pending = (o, u, p); host = QUrl(o).host()
        text = ("Zaktualizować hasło dla " if x else "Zapisać hasło dla ") + host + (f" ({u})?" if u else "?")

        def save():
            v.put(o, u, p); self.notice.info("Hasło zapisane – zaszyfrowane na tym komputerze.")
        self.notice.ask(text, [("Zapisz", save, True), ("Nie teraz", None, False),
                               ("Nigdy dla tej strony", lambda: v.never(o, True), False)])

    def autofill(self, view):
        v = self.vault()
        if v is None or view is None:
            return
        logins = v.logins(origin_of(view.url().toString()))
        if len(logins) == 1:   # jedno konto dla tej strony – wypełniamy od razu (tylko ta sama domena i protokół)
            self.fill(view, logins[0]["user"], logins[0]["pw"])

    def fill(self, view, user, pw):
        js = FILL_JS.replace("%U%", json.dumps(user)).replace("%P%", json.dumps(pw))
        view.page().runJavaScript(js, QWebEngineScript.ScriptWorldId.ApplicationWorld, lambda ok: None)

    def key_menu(self, m=None):
        m = m or self.key_btn.menu(); m.clear(); t = self.cur()
        view = t.web if t and t.web is not None and not t.on_home() else None
        v = self.vault()
        if v is None:
            m.addAction("Menedżer haseł jest wyłączony lub niedostępny" if VAULT else "Menedżer haseł niedostępny").setEnabled(False)
        elif view is not None:
            o = origin_of(view.url().toString()); logins = v.logins(o)
            m.addAction(f"Zapisane dla {QUrl(o).host()}: {len(logins)}").setEnabled(False)
            for x in logins:
                m.addAction(glyph("key"), f"Wypełnij: {x['user'] or '(bez loginu)'}",
                            lambda _=False, x=x: self.fill(view, x["user"], x["pw"]))
                c = totp_code(x["totp"]) if x.get("totp") else None
                if c:
                    m.addAction(glyph("timer"), f"Kod 2FA: {c[0][:3]} {c[0][3:]}  (jeszcze {c[1]} s) – wpisz",
                                lambda _=False, x=x: self.fill_totp(view, x))
        if view is not None:
            m.addSeparator()
            m.addAction("Wygeneruj silne hasło i wpisz", lambda: self.fill_generated(view))
            m.addAction("Wstaw alias e-mail", lambda: self.fill_alias(view))
        m.addSeparator(); m.addAction("Hasła i aliasy…", lambda: self.open_settings("passwords"))

    def fill_totp(self, view, x):
        """Wpisuje bieżący kod 2FA w pole kodu na stronie (i kopiuje go do schowka)."""
        c = totp_code(x.get("totp", ""))
        if not c:
            return
        copy_secret(c[0])
        _safe_js(view, OTP_FILL_JS % (json.dumps(c[0]), "true"),
                 lambda n: self.notice.info("Wpisano kod 2FA." if n else "Kod 2FA jest w schowku (Ctrl+V).", 3000, "key"))

    def offer_totp(self, view):
        """Strona prosi o kod 2FA, a w sejfie jest klucz dla tej witryny → propozycja wpisania kodu."""
        v = self.vault()
        if v is None:
            return
        o = origin_of(view.url().toString())
        site = base_domain(QUrl(o).host())
        cands = [x for x in v.logins() if x.get("totp") and (x["origin"] == o or base_domain(QUrl(x["origin"]).host()) == site)]
        if not cands:
            return

        def got(n):
            if not n or view is not self.web() or (self.notice.isVisible() and self.notice.btns.count()):
                return
            x = cands[0]
            self.notice.ask(f"Strona prosi o kod 2FA. Wpisać kod dla {x['user'] or QUrl(x['origin']).host()}?",
                            [("Wpisz kod", lambda: self.fill_totp(view, x), True), ("Nie", None, False)], icon="key")
        for ms in (500, 2500):
            QTimer.singleShot(ms, lambda: _safe_js(view, OTP_FILL_JS % ('""', "false"), got))

    def fill_generated(self, view):
        pw = gen_password(int(self.store.settings.get("pw_len", 20)))
        view.page().runJavaScript(GEN_FILL_JS.replace("%P%", json.dumps(pw)),   # hasło i jego powtórzenie
                                  QWebEngineScript.ScriptWorldId.ApplicationWorld, lambda ok: None)
        copy_secret(pw)
        self.notice.info("Wpisano silne hasło (też w schowku). Luna zaproponuje zapis po wysłaniu formularza.")

    def make_alias(self, cb):
        """DuckDuckGo (adres @duck.com), gdy jest zapamiętana sesja; inaczej alias z plusem (adres+strona@…)."""
        v = VAULT[0] if VAULT and VAULT[0].available() else None
        tok = v.data.get("ddg") if v else ""
        if not tok:
            self._plus_alias(cb); return
        req = QNetworkRequest(QUrl("https://quack.duckduckgo.com/api/email/addresses"))
        req.setRawHeader(b"Authorization", b"Bearer " + tok.encode()); req.setTransferTimeout(15000)
        r = self.store.nam.post(req, b"")

        def done():
            status = r.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute); raw = bytes(r.readAll()); r.deleteLater()
            try:
                addr = json.loads(raw.decode("utf-8")).get("address")
            except Exception:
                addr = None
            if addr:
                cb(f"{addr}@duck.com", "DuckDuckGo"); return
            if status in (401, 403):   # sesja DuckDuckGo wygasła
                v.data["ddg"] = ""; v.save()
            self._plus_alias(cb)
        r.finished.connect(done)

    def _plus_alias(self, cb):
        base = self.store.settings.get("alias_base") or self.store.session.gmail.get("email", "")
        if not base:
            base, ok = QInputDialog.getText(self, "Alias e-mail", "Twój adres e-mail (aliasy: adres+strona@…), podajesz raz:")
            base = base.strip()
            if not ok or "@" not in base:
                return
            self.store.settings["alias_base"] = base; self.store.save_soon()
        local, dom = base.split("@", 1); t = self.cur()
        site = base_domain(QUrl(t.web.url()).host()).split(".")[0] if t and t.web is not None and not t.on_home() else "luna"
        cb(f"{local.split('+')[0]}+{re.sub('[^a-z0-9]', '', site.lower()) or 'luna'}@{dom}", "alias z plusem")

    def fill_alias(self, view):
        def got(addr, src):
            view.page().runJavaScript(EMAIL_FILL_JS.replace("%V%", json.dumps(addr)),
                                      QWebEngineScript.ScriptWorldId.ApplicationWorld, lambda ok: None)
            QGuiApplication.clipboard().setText(addr)
            self.notice.info(f"Wstawiono alias {addr} ({src}) – jest też w schowku.")
        self.make_alias(got)

    # --- nawigacja ---
    def nav(self, what):
        t = self.cur()
        if t and t.web and not t.on_home():
            getattr(t.web, what)()
        elif what == "forward" and t and t.web is not None:
            t.show_web()

    def go_home(self):
        t = self.cur(); t.show_home(); t.title_text, t.icon = "", None
        self.set_tab_text(t, "Ekran główny"); self.decorate(t); self.tabs_changed()
        self.address.clear(); self.update_sidebars_soon()

    def submit(self):
        text = self.address.text().strip()
        if text and not self.ai_login_link(text):
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
        tab.title_text = title
        if i >= 0:
            self.set_tab_text(tab, title); self.decorate(tab)
        self.tabs_changed()
        if tab.main is not None:
            self.store.session.on_tab_title(tab, tab.main.url().toString(), title)

    def on_icon(self, tab, icon):
        tab.icon = icon; self.decorate(tab); self.tabs_changed()

    def on_load_started(self, tab, view=None):
        view = view or tab.main
        if view is not None and getattr(view, "reader_on", False):   # nowa strona – nakładka czytania znika razem ze starą
            view.reader_on = False
            if view is self.web():
                self.update_reader_btn()
        if SHIELD and view is not None:
            SHIELD[0].reset(view.url().toString())

    def on_loaded(self, tab, ok, view=None):
        view = view or tab.main
        if tab is self.cur() and view is tab.web:
            self.update_shield(); self.update_page_bg()
            if ok:
                self.offer_translation(view)
        elif tab is self.cur() and tab.sides:   # inna strona podziału – jej kolor ma swój panel boczny
            self.update_page_bg()
        if ok and view is not None and getattr(tab, "scroll_sync", False) and tab.sides:
            tab._scroll_js(view)
        if ok and view is not None and view.url().scheme() in ("http", "https", "file"):
            apply_highlights(view)
            self.apply_site_zoom(view)
            self.on_view_url(view, view.url(), reinject=True)
            if addresses():
                self.offer_address(view)
            if view.url().scheme() in ("http", "https"):
                self.check_phishing(view)
                if self.vault() is not None:
                    self.offer_totp(view)
        if ok and view is not None:
            self.autofill(view)
            url = view.url().toString()
            if self.private:
                return
            if url.startswith("http"):
                self.store.add_recent((view.title() or host_of(url))[:40], url)

    def on_url(self, tab, url):
        if tab is self.cur() and not tab.on_home():
            self.address.setText(url.toString())
            self.update_star()

    def sync_address(self):
        t = self.cur()
        if hasattr(self, "shield_btn"):
            self.update_shield()
        self.address.setText("" if not t or t.on_home() or not t.web or t.side_empty() else t.web.url().toString())
        self.update_star()
        if hasattr(self, "reader_btn"):
            self.update_reader_btn()
        on = bool(t and t.sides)
        if hasattr(self, "split_btn") and self.split_btn.property("on") != on:   # podświetlona ikona = podział włączony
            self.split_btn.setProperty("on", on); self.split_btn.setIcon(glyph("split", "#ffffff" if on else "#c9c9c9"))
            self.split_btn.setToolTip("Zakończ podział ekranu (Ctrl+\\)" if on else "Podziel ekran (Ctrl+\\)")


def load_local_fonts():
    if FONT_DIR.exists():
        for f in FONT_DIR.glob("*.[to]tf"):
            QFontDatabase.addApplicationFont(str(f))


def wait_for_previous():
    """Po przywróceniu kopii nowa Luna czeka, aż poprzednia zamknie się i zwolni profil przeglądarki (maks. 15 s)."""
    for a in list(sys.argv):
        if a.startswith("--luna-wait="):
            sys.argv.remove(a)
            try:
                pid = int(a.split("=", 1)[1])
                if sys.platform == "win32":
                    import ctypes
                    k = ctypes.windll.kernel32; k.OpenProcess.restype = ctypes.c_void_p
                    h = k.OpenProcess(0x00100000, False, pid)   # SYNCHRONIZE
                    if h:
                        k.WaitForSingleObject(ctypes.c_void_p(h), 15000); k.CloseHandle(ctypes.c_void_p(h))
                else:
                    end = time.time() + 15
                    while time.time() < end and Path(f"/proc/{pid}").exists():
                        time.sleep(0.2)
            except (ValueError, OSError):
                pass


ERROR_LOG = HOME / ".luna_bledy.log"


def install_error_guard():
    """Nieobsłużony wyjątek w slocie/timerze Qt nie zamyka już całej Luny (PyQt6 domyślnie wtedy przerywa proces):
    trafia do dziennika ~/.luna_bledy.log (max ok. 256 KB, starsze wpisy obcinane) i na stderr."""
    import traceback

    def hook(etype, value, tb):
        text = "".join(traceback.format_exception(etype, value, tb))
        try:
            sys.__stderr__ and sys.__stderr__.write(text)
        except Exception:
            pass
        try:
            old = ERROR_LOG.read_text(encoding="utf-8") if ERROR_LOG.exists() else ""
            entry = f"--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{text}\n"
            ERROR_LOG.write_text((old + entry)[-256 * 1024:], encoding="utf-8")
        except Exception:
            pass
    sys.excepthook = hook


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--luna-adblock-compile":   # podproces kompilatora list (Luna.exe)
        from adblock import compiler
        compiler.main(sys.argv[2:])
    wait_for_previous()
    # rasteryzacja stron na GPU i przesyłanie bez kopiowania – płynniejsze przewijanie i animacje (można nadpisać zmienną)
    # --process-per-site: karty tej samej witryny dzielą jeden proces strony – wyraźnie mniej RAM przy wielu kartach
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--enable-gpu-rasterization --enable-zero-copy --process-per-site")
    if sys.platform == "win32":  # własna ikona na pasku zadań (a nie ikona Pythona)
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pl.luna.browser")
        except Exception:
            pass
    install_error_guard()
    app = QApplication(sys.argv)
    migrate_old_data()
    load_local_fonts()
    app.setApplicationName("Luna"); app.setWindowIcon(app_icon())
    app.setStyleSheet(full_style())
    w = Browser(); w.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True); w.show()
    sys.exit(app.exec())
