#!/usr/bin/env python3
"""Luna – lekka przeglądarka z kafelkami-aplikacjami, panelami bocznymi (widgety) i asystentem AI.

Instalacja:   pip install PyQt6 PyQt6-WebEngine   (opcjonalnie: psutil – monitor zasobów, keyring – bezpieczny token Google)
Uruchomienie: python luna.py

Dane w katalogu domowym (odpowiednik localStorage):
  .luna_ustawienia.json   ustawienia: funkcje, widgety (widoczność/strona/kolejność/zwinięcie), notatki, zadania…
  .luna.json              kafelki          .luna_ostatnie.json  ostatnio odwiedzone
  .luna_ikony/            favicony         .luna_fonty/         fonty (pobierane przy 1. uruchomieniu)
  .luna_profile/          profil przeglądarki (zapamiętane logowania, w tym do paneli AI)
"""
import sys, json, math, re, html, os, random, base64, time, ast, operator, secrets, hashlib
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode
from PyQt6.QtCore import (Qt, QUrl, QSize, QObject, QPoint, QPointF, QRectF, QEvent, QTimer, QLocale, QDateTime,
                          QPropertyAnimation, pyqtSignal)
from PyQt6.QtGui import (QCursor, QBrush, QRadialGradient, QLinearGradient, QIcon, QPixmap, QPainter, QColor, QFont,
                         QFontDatabase, QPen, QPolygonF, QKeySequence, QShortcut, QActionGroup, QTextDocument,
                         QPalette, QPainterPath, QDesktopServices)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QTcpServer, QHostAddress
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QStackedWidget, QTabBar, QToolButton, QLineEdit,
                             QListWidget, QListWidgetItem, QListView, QAbstractItemView, QMenu, QInputDialog,
                             QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QDialog, QDialogButtonBox, QFrame,
                             QScrollArea, QPlainTextEdit, QGraphicsOpacityEffect, QButtonGroup, QToolTip, QComboBox,
                             QCheckBox, QSlider, QProgressBar, QFileDialog)
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
QStackedWidget { background:transparent; }
QWidget#clear, QWidget#bgframe, QWidget#qt_scrollarea_viewport { background:transparent; }
QFrame#wf { background:transparent; border:0; }
QCheckBox, QSlider, QProgressBar { background:transparent; }
QScrollArea#sb { background:transparent; border:0; }
QToolTip { background:#1c1c1c; color:#ececec; border:1px solid #333333; padding:5px 8px; }
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
QTabBar::tab { background:transparent; color:#8c8c8c; height:30px; padding:0 4px 0 14px; margin:1px 2px;
               border-radius:15px; max-width:190px; font-size:13px; }
QTabBar::tab:hover:!selected { background:#1a1a1a; color:#d4d4d4; }
QTabBar::tab:selected { background:#ececec; color:#111111; font-weight:600; }
QToolButton { background:transparent; border:0; border-radius:18px; padding:0; }
QToolButton:hover { background:#1f1f1f; }
QToolButton#tabclose { border-radius:10px; padding:0; margin:0; }
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
    s = STYLE.replace("%CHEV%", chevron_path())
    imgs = ui_images()
    for tok, key in (("%SWOFF%", "sw_off"), ("%SWON%", "sw_on"), ("%CKOFF%", "ck_off"), ("%CKON%", "ck_on")):
        s = s.replace(tok, imgs.get(key, ""))
    return s


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
    layout_changed = pyqtSignal()
    features_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.nam = QNetworkAccessManager(self)
        self.weather_ts = 0.0
        self._save_timer = QTimer(self); self._save_timer.setSingleShot(True); self._save_timer.timeout.connect(self.save_settings)
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
        GLASS_ALPHA[0] = int(self.settings.get("glass", 168)); BG.store = self
        self.bump_day(emit=False)  # samo uruchomienie przeglądarki liczy się do serii

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

    # --- ustawienia (odpowiednik localStorage: plik JSON w katalogu domowym) ---
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
                j = json.loads(data.decode("utf-8"))
            except Exception:
                j = None
            cb(j, err, status)
        r.finished.connect(done)
        return r

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
    "gmail": ("Gmail", "right", 4, False, "google"),
    "calendar": ("Kalendarz Google", "right", 5, False, "google"),
    "gtasks": ("Zadania Google", "right", 6, False, "google"),
    "audio": ("Odtwarzacz audio", "right", 7, False, None),
    "system": ("Monitor zasobów", "right", 8, False, None),
    "rss": ("Wiadomości (RSS)", "right", 9, False, None),
}
FEATURES = {  # id: (nazwa, opis, domyślnie)
    "google": ("Integracja z Google", "Gmail, Kalendarz i Zadania. Wyłączona: brak logowania, zapytań i zasobów w tle.", True),
    "markets": ("Panele giełdowe i walutowe", "Rynki (akcje, krypto) i przelicznik walut. Wyłączone: brak zapytań o notowania.", True),
    "left": ("Lewy panel boczny", "Pokazuje widgety przypisane do lewej strony.", True),
    "right": ("Prawy panel boczny", "Pokazuje widgety przypisane do prawej strony.", True),
    "everywhere": ("Panele także na stronach WWW", "Domyślnie panele są widoczne tylko na ekranie głównym.", False),
    "shortcuts": ("Skróty klawiszowe i gesty myszy", "Ctrl+T/W/R/Tab, F5, środkowy przycisk myszy na kartach.", True),
    "assistant": ("Asystent AI", "Panel z ChatGPT, Claude, Gemini i DeepSeek (Ctrl+J).", True),
}
GLASS_ALPHA = [168]
BG_B64 = (
    "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"
    "PTxCHUjO/tLN2P4TSoAEAABtFCqyISYQj//Z"
)


def safe_disconnect(sig, slot):
    try:
        sig.disconnect(slot)
    except (TypeError, RuntimeError):
        pass


class Background:
    """Tło okna: obraz „cover” (wypełnia i centruje bez zniekształceń) + rozmyta kopia pod szklane panele.
    Cache zależy od rozmiaru i trybu; przeliczany dopiero po zakończeniu zmiany rozmiaru (debounce)."""

    def __init__(self):
        self.store = self.frame = self.cover = self.blur = self._src = self.key = None

    def source(self):
        if self._src is None:
            pm = QPixmap(); pm.loadFromData(base64.b64decode("".join(BG_B64.split()))); self._src = pm
        return self._src

    def mode(self):
        return self.store.settings.get("bg", "image") if self.store else "image"

    def wanted_key(self, size):
        return (size.width(), size.height(), self.mode())

    def prepare(self, size):
        key = self.wanted_key(size)
        if key == self.key:
            return
        w, h = max(1, size.width()), max(1, size.height())
        mode = key[2]
        if mode == "image":
            src = self.source().scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                       Qt.TransformationMode.SmoothTransformation)
            pm = src.copy(max(0, (src.width() - w) // 2), max(0, (src.height() - h) // 2), w, h)
            p = QPainter(pm); p.fillRect(pm.rect(), QColor(8, 8, 10, 96))
            g = QLinearGradient(0, 0, 0, h); g.setColorAt(0, QColor(0, 0, 0, 0)); g.setColorAt(1, QColor(0, 0, 0, 120))
            p.fillRect(pm.rect(), QBrush(g)); p.end()
        elif mode == "gradient":
            pm = QPixmap(w, h); p = QPainter(pm)
            g = QLinearGradient(0, 0, w, h)
            g.setColorAt(0, QColor("#26282d")); g.setColorAt(0.55, QColor("#16171a")); g.setColorAt(1, QColor("#0b0b0d"))
            p.fillRect(pm.rect(), QBrush(g)); p.end()
        else:
            pm = QPixmap(w, h); pm.fill(QColor("#111111"))
        small = pm.scaled(max(1, w // 14), max(1, h // 14), Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
        self.blur = small.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.cover, self.key = pm, key

    def draw_under(self, p, widget):
        """Rysuje rozmyty fragment tła znajdujący się pod widgetem (efekt matowego szkła)."""
        if self.blur is None or self.frame is None:
            return
        pos = widget.mapTo(self.frame, QPoint(0, 0))
        p.drawPixmap(0, 0, self.blur, pos.x(), pos.y(), widget.width(), widget.height())


BG = Background()


class BgFrame(QWidget):
    """Kontener obszaru roboczego z tłem. Przeliczenie tła po zmianie rozmiaru jest opóźnione (debounce)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("bgframe")
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self._recompute)

    def _recompute(self):
        BG.prepare(self.size()); self.update()
        for w in self.findChildren(WidgetFrame):
            w.update()

    def showEvent(self, ev):
        BG.frame = self
        if BG.cover is None:
            BG.prepare(self.size())
        super().showEvent(ev)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#111111"))
        if BG.key != BG.wanted_key(self.size()):
            self._t.start(90)          # trwa zmiana rozmiaru – rysujemy stary cache, nowy po 90 ms ciszy
        if BG.cover is not None:
            p.drawPixmap(0, 0, BG.cover)


def paint_glass(w, radius=18):
    p = QPainter(w); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath(); path.addRoundedRect(QRectF(w.rect()).adjusted(.5, .5, -.5, -.5), radius, radius)
    p.setClipPath(path)
    BG.draw_under(p, w)
    p.fillPath(path, QColor(14, 14, 16, GLASS_ALPHA[0]))
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


class WidgetFrame(QFrame):
    """Szklana ramka widgetu: nagłówek (tytuł, zwijanie, menu) + treść. Timery i sieć działają tylko, gdy
    widget jest widoczny i rozwinięty (start/stop); po wyłączeniu widget jest usuwany z pamięci."""

    def __init__(self, wid, store, host):
        super().__init__()
        self.wid, self.store, self.host = wid, store, host
        self.setObjectName("wf"); self.running = False; self._alive = True
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        self.head = QWidget(); self.head.setObjectName("clear")
        h = QHBoxLayout(self.head); h.setContentsMargins(16, 9, 8, 4); h.setSpacing(2)
        self.title = QLabel(WIDGETS[wid][0].upper()); self.title.setObjectName("cap")
        self.badge = QLabel(); self.badge.setObjectName("badge"); self.badge.hide()
        h.addWidget(self.title); h.addSpacing(6); h.addWidget(self.badge); h.addStretch()
        self.menu = QMenu(self)
        self.menu_btn = QToolButton(); self.menu_btn.setObjectName("more"); self.menu_btn.setText("⋯")
        self.menu_btn.setFixedSize(26, 26); self.menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_btn.setMenu(self.menu)
        self.fold_btn = QToolButton(); self.fold_btn.setFixedSize(26, 26); self.fold_btn.setIconSize(QSize(16, 16))
        self.fold_btn.setToolTip("Zwiń / rozwiń"); self.fold_btn.clicked.connect(lambda: self.toggle())
        h.addWidget(self.menu_btn); h.addWidget(self.fold_btn)
        v.addWidget(self.head)
        self.head.mousePressEvent = lambda ev: self.toggle() if ev.button() == Qt.MouseButton.LeftButton else None
        self.body = QWidget(); self.body.setObjectName("clear")
        self.lay = QVBoxLayout(self.body); self.lay.setContentsMargins(16, 0, 16, 14); self.lay.setSpacing(6)
        v.addWidget(self.body)
        self.collapsed = bool(store.wcfg(wid)["collapsed"])
        self.anim = QPropertyAnimation(self.body, b"maximumHeight", self); self.anim.setDuration(170)
        self.anim.finished.connect(self._anim_done)
        self.build()
        if self.menu.actions():
            self.menu.addSeparator()
        self.menu.addAction("Zwiń / rozwiń", self.toggle)
        self.menu.addAction("Przesuń w górę", lambda: host.move(wid, -1))
        self.menu.addAction("Przesuń w dół", lambda: host.move(wid, 1))
        self.menu.addAction("Przenieś na drugą stronę", lambda: host.flip(wid))
        self.menu.addAction("Ukryj widget", lambda: store.set_wcfg(wid, on=False))
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
        want = self.isVisible() and not self.collapsed
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


class Sidebar(QWidget):
    """Boczny panel: przewijana kolumna widgetów + wąska szyna do zwijania/rozwijania całego panelu."""
    W = 300

    def __init__(self, side, store):
        super().__init__()
        self.side, self.store = side, store
        self.setObjectName("clear")
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        self.scroll = QScrollArea(); self.scroll.setObjectName("sb"); self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        self.inner = QWidget(); self.inner.setObjectName("clear"); self.inner.setFixedWidth(self.W - 12)
        self.col = QVBoxLayout(self.inner); self.col.setContentsMargins(10, 12, 2, 12); self.col.setSpacing(12)
        self.scroll.setWidget(self.inner)
        # półprzezroczyste tło: wymuś pełne odmalowanie przy przewijaniu (bez artefaktów po kopiowaniu pikseli)
        self.scroll.verticalScrollBar().valueChanged.connect(lambda _: self.scroll.viewport().update())
        self.scroll.setMinimumWidth(0); self.scroll.setMaximumWidth(self.W)
        self.rail = QToolButton(); self.rail.setObjectName("rail"); self.rail.setFixedSize(16, 54)
        self.rail.setCursor(Qt.CursorShape.PointingHandCursor); self.rail.setIconSize(QSize(14, 14))
        self.rail.clicked.connect(lambda: self.set_collapsed(not self.collapsed))
        rb = QVBoxLayout(); rb.setContentsMargins(2, 18, 2, 0); rb.addWidget(self.rail); rb.addStretch()
        if side == "left":
            lay.addWidget(self.scroll); lay.addLayout(rb)
        else:
            lay.addLayout(rb); lay.addWidget(self.scroll)
        self.anim = QPropertyAnimation(self.scroll, b"maximumWidth", self); self.anim.setDuration(180)
        self.anim.finished.connect(self._anim_done)
        self.collapsed = bool(store.settings.get("sidebar", {}).get(side, False))
        self.scroll.setVisible(not self.collapsed); self._rail_icon()
        self._count = 0

    def has_widgets(self):
        return self._count > 0

    def _rail_icon(self):
        left = self.side == "left"
        kind = ("back" if left else "forward") if not self.collapsed else ("forward" if left else "back")
        self.rail.setIcon(glyph(kind, "#9a9a9a"))
        self.rail.setToolTip("Zwiń panel" if not self.collapsed else "Rozwiń panel")

    def set_collapsed(self, c):
        self.collapsed = c
        self.store.settings.setdefault("sidebar", {})[self.side] = c; self.store.save_soon()
        self.anim.stop()
        if c:
            self.anim.setStartValue(self.scroll.width()); self.anim.setEndValue(0)
        else:
            self.scroll.setMaximumWidth(0); self.scroll.show()
            self.anim.setStartValue(0); self.anim.setEndValue(self.W)
        self.anim.start(); self._rail_icon()

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
        self._count = len(ws)


class WidgetHost(QObject):
    """Tworzy i usuwa widgety zgodnie z ustawieniami (widoczność, strona, kolejność, funkcje)."""

    def __init__(self, store, browser):
        super().__init__()
        self.store, self.browser = store, browser
        self.inst = {}
        self._google = None
        self.left, self.right = Sidebar("left", store), Sidebar("right", store)
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self.sync)
        store.layout_changed.connect(lambda: self._t.start(30))

    @property
    def google(self):
        if self._google is None and self.store.feature("google"):
            self._google = GoogleService(self.store)
        return self._google

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
        if not self.store.feature("google"):
            self._google = None  # funkcja wyłączona: usuń usługę (bez zapytań i nasłuchiwaczy)
        for sb in (self.left, self.right):
            ws = sorted((w for wid, w in self.inst.items() if self.store.wcfg(wid)["side"] == sb.side),
                        key=lambda w: self.store.wcfg(w.wid)["order"])
            sb.set_widgets(ws)
        self.browser.update_sidebars()

    def move(self, wid, delta):
        side = self.store.wcfg(wid)["side"]
        ids = self.store.side_order(side)
        i = ids.index(wid); j = max(0, min(len(ids) - 1, i + delta))
        ids.insert(j, ids.pop(i))
        self.store.apply_layout(**{side: ids, ("right" if side == "left" else "left"):
                                   self.store.side_order("right" if side == "left" else "left")})

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
def lbl(text="", obj=None, wrap=False, align=None):
    w = QLabel(text)
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
        self.chg.setText(f"{'▲' if up else '▼'} {abs(chg):.2f}%")
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
        self.a, self.b = QComboBox(), QComboBox()
        for c in self.CODES:
            self.a.addItem(c); self.b.addItem(c)
        self.a.setCurrentText("PLN"); self.b.setCurrentText("USD")
        self.a.currentTextChanged.connect(self.calc); self.b.currentTextChanged.connect(self.calc)
        sw = QToolButton(); sw.setText("⇄"); sw.setFixedSize(28, 28); sw.setToolTip("Zamień waluty")
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
            cb = QCheckBox(it["t"]); cb.setObjectName("todo"); cb.setChecked(it["d"]); cb.setToolTip(it["t"])
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
            b = QPushButton(t.replace("\n", " ")[:42] + ("…" if len(t) > 42 else "")); b.setObjectName("clipitem")
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
        self.a, self.b = QComboBox(), QComboBox()
        for c, n in self.LANGS:
            self.a.addItem(n, c); self.b.addItem(n, c)
        self.a.setCurrentIndex(0); self.b.setCurrentIndex(1)
        sw = QToolButton(); sw.setText("⇄"); sw.setFixedSize(28, 28); sw.clicked.connect(self.swap)
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
    except Exception:
        pass
    return cpu, ram, bat, plug


class SystemWidget(WidgetFrame):
    def build(self):
        self.bars = {}
        for k, t in (("cpu", "Procesor"), ("ram", "Pamięć RAM"), ("bat", "Bateria")):
            row = QHBoxLayout(); a = lbl(t, "muted2"); v = lbl("–", "h3")
            row.addWidget(a); row.addStretch(); row.addWidget(v); self.lay.addLayout(row)
            pb = QProgressBar(); pb.setRange(0, 100); pb.setTextVisible(False); pb.setFixedHeight(6); self.lay.addWidget(pb)
            self.bars[k] = (v, pb)
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick)

    def start(self):
        read_system(); self.timer.start(2000); QTimer.singleShot(400, self.tick)

    def stop(self):
        self.timer.stop()

    def tick(self):
        cpu, ram, bat, plug = read_system()
        for k, val in (("cpu", cpu), ("ram", ram), ("bat", bat)):
            v, pb = self.bars[k]
            v.setText("–" if val is None else f"{val:.0f}%" + (" ⚡" if k == "bat" and plug else ""))
            pb.setValue(int(val or 0))


class AudioWidget(WidgetFrame):
    """Mini-odtwarzacz lokalnych plików (QtMultimedia ładowane dopiero tutaj). Spotify: skrót do wersji WWW."""

    def build(self):
        self.ok = False
        try:
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaMetaData
        except ImportError:
            self.lay.addWidget(lbl("Brak modułu QtMultimedia.", "muted2")); return
        self.MP, self.MD = QMediaPlayer, QMediaMetaData
        self.player = QMediaPlayer(self); self.out = QAudioOutput(self); self.player.setAudioOutput(self.out)
        self.out.setVolume(0.6); self.files, self.idx = [], -1; self.ok = True
        top = QHBoxLayout(); top.setSpacing(10)
        self.cover = QLabel(); self.cover.setFixedSize(58, 58); self.cover.setObjectName("cover")
        info = QVBoxLayout(); info.setSpacing(0)
        self.song = lbl("Brak utworu", "h3", wrap=True); self.artist = lbl("Dodaj pliki audio ＋", "muted")
        info.addWidget(self.song); info.addWidget(self.artist)
        top.addWidget(self.cover); top.addLayout(info, 1); self.lay.addLayout(top)
        self.pos = QSlider(Qt.Orientation.Horizontal); self.pos.setRange(0, 0)
        self.pos.sliderMoved.connect(self.player.setPosition); self.lay.addWidget(self.pos)
        row = QHBoxLayout(); row.setSpacing(4)
        self.prev_b, self.play_b, self.next_b = (QToolButton() for _ in range(3))
        for b, txt, fn in ((self.prev_b, "⏮", lambda: self.step(-1)), (self.play_b, "▶", self.toggle), (self.next_b, "⏭", lambda: self.step(1))):
            b.setText(txt); b.setFixedSize(34, 34); b.clicked.connect(lambda _=False, f=fn: f()); row.addWidget(b)
        add = QToolButton(); add.setText("＋"); add.setFixedSize(34, 34); add.setToolTip("Dodaj pliki audio"); add.clicked.connect(self.add)
        sp = QPushButton("Spotify"); sp.setToolTip("Otwórz Spotify w karcie (odtwarzanie DRM nie działa w osadzonym Chromium)")
        sp.clicked.connect(lambda: self.host.browser.open_url_new_tab("https://open.spotify.com"))
        row.addStretch(); row.addWidget(add); row.addWidget(sp); self.lay.addLayout(row)
        self.player.positionChanged.connect(lambda p: self.pos.setValue(p) if not self.pos.isSliderDown() else None)
        self.player.durationChanged.connect(lambda d: self.pos.setRange(0, d))
        self.player.metaDataChanged.connect(self.meta)
        self.player.mediaStatusChanged.connect(lambda s: self.step(1) if s == self.MP.MediaStatus.EndOfMedia else None)
        self.player.playbackStateChanged.connect(lambda s: self.play_b.setText("⏸" if s == self.MP.PlaybackState.PlayingState else "▶"))

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
                b = QPushButton(title[:90]); b.setObjectName("newsitem"); b.setToolTip(title)
                b.clicked.connect(lambda _=False, u=link: u and self.host.browser.open_url_new_tab(u))
                self.rows.addWidget(b)
            host = host_of(self.feed()); self.src.setText(f"Źródło: {host}")
            if not items:
                raise ValueError
        except Exception:
            self.rows.addWidget(lbl("Nie udało się wczytać kanału RSS.", "muted2"))


# ---------------------------------------------------------------- Google (OAuth 2.0 + PKCE, logowanie w zwykłej przeglądarce)
GOOGLE_SCOPES = ("openid email https://www.googleapis.com/auth/gmail.readonly "
                 "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/tasks")


def secret_get(store, key):
    """Token odświeżania: w systemowym pęku kluczy (pakiet keyring), a gdy go brak – w pliku ustawień (chmod 600)."""
    try:
        import keyring
        v = keyring.get_password("Luna", key)
        if v:
            return v
    except Exception:
        pass
    return store.settings.get("google", {}).get(key)


def secret_set(store, key, value):
    try:
        import keyring
        keyring.set_password("Luna", key, value)
        store.settings.get("google", {}).pop(key, None); store.save_settings(); return
    except Exception:
        pass
    store.settings.setdefault("google", {})[key] = value; store.save_settings()


def secret_del(store, key):
    try:
        import keyring
        keyring.delete_password("Luna", key)
    except Exception:
        pass
    store.settings.get("google", {}).pop(key, None); store.save_settings()


class OAuthListener(QObject):
    """Jednorazowy lokalny serwer (127.0.0.1) odbierający przekierowanie OAuth z kodem."""
    done = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.srv = QTcpServer(self)
        self.srv.listen(QHostAddress(QHostAddress.SpecialAddress.LocalHost), 0)
        self.srv.newConnection.connect(self._conn)
        self.port = self.srv.serverPort()
        QTimer.singleShot(180000, self.srv.close)  # limit czasu na logowanie: 3 minuty

    def _conn(self):
        sock = self.srv.nextPendingConnection()
        sock.readyRead.connect(lambda s=sock: self._read(s))

    def _read(self, sock):
        first = bytes(sock.readAll()).decode("utf-8", "ignore").split("\r\n", 1)[0].split(" ")
        path = first[1] if len(first) > 1 else ""
        q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(path).query).items()}
        if "code" not in q and "error" not in q:
            sock.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"); sock.disconnectFromHost(); return
        body = ("<html><head><meta charset='utf-8'></head><body style='font-family:sans-serif;background:#111;color:#eee;"
                "text-align:center;padding-top:20vh'><h2>Luna</h2><p>Gotowe – możesz zamknąć tę kartę i wrócić do przeglądarki.</p>"
                "</body></html>").encode("utf-8")
        sock.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\nContent-Length: "
                   + str(len(body)).encode() + b"\r\n\r\n" + body)
        sock.disconnectFromHost(); self.srv.close(); self.done.emit(q)


class GoogleService(QObject):
    """Sesja Google: trwały token odświeżania, automatyczne odnawianie tokenu dostępu, obsługa wygaśnięcia sesji.
    Tworzona dopiero, gdy funkcja „Integracja z Google” jest włączona; sama nie uruchamia żadnych timerów."""
    state_changed = pyqtSignal()
    CT = QNetworkRequest.KnownHeaders.ContentTypeHeader
    STATUS = QNetworkRequest.Attribute.HttpStatusCodeAttribute

    def __init__(self, store):
        super().__init__()
        self.store, self.token, self.exp = store, None, 0.0
        self.expired, self.busy, self.last_error = False, False, ""
        self._waiters, self._listener = None, None

    def cfg(self):
        return self.store.settings.get("google", {})

    def configured(self):
        c = self.cfg(); return bool(c.get("client_id") and c.get("client_secret"))

    def refresh_token(self):
        return secret_get(self.store, "refresh")

    def logged_in(self):
        return self.configured() and bool(self.refresh_token()) and not self.expired

    def email(self):
        return self.cfg().get("email", "")

    # --- logowanie ---
    def login(self):
        if not self.configured():
            return
        self.last_error = ""
        if self._listener:
            self._listener.srv.close()
        self._listener = OAuthListener()
        self.verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode().rstrip("=")
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip("=")
        self.state = secrets.token_urlsafe(16); self.redirect = f"http://127.0.0.1:{self._listener.port}"
        q = urlencode({"client_id": self.cfg()["client_id"], "redirect_uri": self.redirect, "response_type": "code",
                       "scope": GOOGLE_SCOPES, "code_challenge": challenge, "code_challenge_method": "S256",
                       "state": self.state, "access_type": "offline", "prompt": "consent"})
        self._listener.done.connect(self._got_code)
        self.busy = True; self.state_changed.emit()
        QDesktopServices.openUrl(QUrl("https://accounts.google.com/o/oauth2/v2/auth?" + q))  # zwykła przeglądarka systemowa

    def _got_code(self, q):
        self.busy = False
        if q.get("state") != self.state or "code" not in q:
            self.last_error = q.get("error", "Logowanie przerwane."); self.state_changed.emit(); return
        self._token_post({"grant_type": "authorization_code", "code": q["code"], "redirect_uri": self.redirect,
                          "code_verifier": self.verifier}, self._login_done)

    def _login_done(self, j, status, neterr):
        if "access_token" in j and j.get("refresh_token"):
            self.token, self.exp, self.expired = j["access_token"], time.time() + int(j.get("expires_in", 3600)), False
            secret_set(self.store, "refresh", j["refresh_token"])

            def got(info, err):
                self.store.settings.setdefault("google", {})["email"] = (info or {}).get("email", "")
                self.store.save_settings(); self.state_changed.emit()
            self.state_changed.emit()
            self.request("GET", "https://openidconnect.googleapis.com/v1/userinfo", got)
        else:
            self.last_error = j.get("error_description") or j.get("error") or "Nie udało się zalogować."
            self.state_changed.emit()

    def logout(self):
        tok = self.refresh_token()
        if tok:
            req = QNetworkRequest(QUrl("https://oauth2.googleapis.com/revoke?token=" + quote(tok)))
            req.setHeader(self.CT, "application/x-www-form-urlencoded")
            r = self.store.nam.post(req, b""); r.finished.connect(r.deleteLater)
        secret_del(self.store, "refresh"); self.store.settings.get("google", {}).pop("email", None)
        self.store.save_settings(); self.token, self.expired, self.last_error = None, False, ""
        self.state_changed.emit()

    # --- tokeny ---
    def _token_post(self, extra, cb):
        c = self.cfg(); body = {"client_id": c.get("client_id", ""), "client_secret": c.get("client_secret", "")}; body.update(extra)
        req = QNetworkRequest(QUrl("https://oauth2.googleapis.com/token"))
        req.setHeader(self.CT, "application/x-www-form-urlencoded"); req.setTransferTimeout(15000)
        r = self.store.nam.post(req, urlencode(body).encode())
        r.finished.connect(lambda r=r: self._token_reply(r, cb))

    def _token_reply(self, r, cb):
        status = r.attribute(self.STATUS); raw = bytes(r.readAll()); neterr = r.error() != QNetworkReply.NetworkError.NoError
        r.deleteLater()
        try:
            j = json.loads(raw.decode("utf-8"))
        except Exception:
            j = {}
        cb(j, status, neterr and not j)

    def _with_token(self, then):
        if self.token and time.time() < self.exp - 60:
            then(True); return
        if self._waiters is not None:          # odświeżanie już trwa – dołącz do kolejki
            self._waiters.append(then); return
        self._waiters = [then]
        self._token_post({"grant_type": "refresh_token", "refresh_token": self.refresh_token() or ""}, self._refreshed)

    def _refreshed(self, j, status, neterr):
        waiters, self._waiters = self._waiters or [], None
        ok = "access_token" in j
        if ok:
            self.token, self.exp = j["access_token"], time.time() + int(j.get("expires_in", 3600))
        elif j.get("error") == "invalid_grant" or status in (400, 401):
            self.token, self.expired = None, True      # token odświeżania unieważniony / wygasł
            self.state_changed.emit()
        for w in waiters:
            w(ok)

    # --- zapytania do API ---
    def request(self, method, url, cb, body=None, _retry=True):
        """cb(json|None, błąd|None). Przy 401 odświeża token i ponawia dokładnie raz."""
        if not self.logged_in():
            cb(None, "Nie zalogowano do Google."); return

        def go(ok):
            if not ok:
                cb(None, "Sesja wygasła – zaloguj się ponownie." if self.expired else "Brak połączenia z Google."); return
            req = QNetworkRequest(QUrl(url)); req.setRawHeader(b"Authorization", ("Bearer " + self.token).encode())
            req.setTransferTimeout(15000); data = b""
            if body is not None:
                req.setHeader(self.CT, "application/json"); data = json.dumps(body).encode()
            if method == "GET":
                r = self.store.nam.get(req)
            elif method == "POST":
                r = self.store.nam.post(req, data)
            else:
                r = self.store.nam.sendCustomRequest(req, method.encode(), data)
            r.finished.connect(lambda r=r: self._reply(r, method, url, cb, body, _retry))
        self._with_token(go)

    def _reply(self, r, method, url, cb, body, retry):
        status = r.attribute(self.STATUS); raw = bytes(r.readAll())
        neterr = r.errorString() if r.error() != QNetworkReply.NetworkError.NoError else None
        r.deleteLater()
        if status == 401 and retry:
            self.token = None; self.request(method, url, cb, body, False); return
        try:
            j = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            j = None
        if status and status >= 400:
            e = (j or {}).get("error") if isinstance(j, dict) else None
            msg = e.get("message") if isinstance(e, dict) else (e or "")
            if status == 401:
                self.expired = True; self.state_changed.emit()
            cb(None, f"Błąd Google {status}: {msg}".strip(": ")); return
        if neterr and j is None:
            cb(None, "Brak połączenia z Google."); return
        cb(j if j is not None else {}, None)


class GoogleWidget(WidgetFrame):
    """Wspólna baza widgetów Google: stany (brak konfiguracji / wylogowany / wygasła sesja / ładowanie / błąd)."""
    INTERVAL = 120000  # synchronizacja w tle co 2 min – tylko gdy widget jest widoczny

    def build(self):
        self.gen, self.loaded, self._mode = 0, False, "login"
        self.msg = lbl("", "muted2", wrap=True); self.act = QPushButton(); self.act.clicked.connect(self.on_action)
        self.skel = Skeleton(3); self.err = lbl("", "muted2", wrap=True)
        self.content = QVBoxLayout(); self.content.setSpacing(4)
        for w in (self.msg, self.act, self.skel, self.err):
            self.lay.addWidget(w)
        self.lay.addLayout(self.content)
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh)
        self.extra_build()

    def extra_build(self): pass
    def fetch(self): pass

    def svc(self):
        return self.host.google

    def start(self):
        g = self.svc()
        if g is not None:
            g.state_changed.connect(self.sync_state); self.sync_state(); self.timer.start(self.INTERVAL)

    def stop(self):
        g = self.svc()
        if g is not None:
            safe_disconnect(g.state_changed, self.sync_state)
        self.timer.stop()

    def sync_state(self):
        g = self.svc()
        for w in (self.msg, self.act, self.skel, self.err):
            w.hide()
        if g is None:
            return
        if not g.configured():
            self._mode = "cfg"; self.msg.setText("Skonfiguruj logowanie Google (Client ID i Secret) w Ustawieniach.")
            self.act.setText("Otwórz ustawienia")
        elif g.expired:
            self._mode = "login"; self.msg.setText("Sesja wygasła – zaloguj się ponownie."); self.act.setText("Zaloguj przez Google")
        elif not g.logged_in():
            self._mode = "login"; self.msg.setText("Zaloguj się kontem Google, aby zobaczyć dane."); self.act.setText("Zaloguj przez Google")
        elif g.busy:
            self.msg.setText("Dokończ logowanie w oknie przeglądarki…"); self.msg.show(); return
        else:
            self.refresh(); return
        self.loaded = False; self.clear(); self.msg.show(); self.act.show()

    def on_action(self):
        g = self.svc()
        if self._mode == "cfg":
            self.host.browser.open_settings("google")
        elif g is not None:
            g.login()

    def refresh(self):
        g = self.svc()
        if g is None or not g.logged_in():
            self.sync_state(); return
        self.msg.hide(); self.act.hide()
        if not self.loaded:
            self.skel.show()
        self.fetch()

    refresh_now = refresh

    def clear(self):
        while self.content.count():
            w = self.content.takeAt(0).widget()
            if w:
                w.deleteLater()

    def finish(self, err=None):
        self.skel.hide()
        self.err.setText(err or ""); self.err.setVisible(bool(err))
        if not err:
            self.loaded = True


def _sender(v):
    m = re.match(r'\s*"?([^"<]*?)"?\s*<[^>]*>\s*$', v or "")
    return (m.group(1).strip() if m and m.group(1).strip() else (v or "").strip("<> "))[:28]


class GmailWidget(GoogleWidget):
    def fetch(self):
        g = self.svc()
        g.request("GET", "https://gmail.googleapis.com/gmail/v1/users/me/labels/INBOX", self.guard(self._label))
        g.request("GET", "https://gmail.googleapis.com/gmail/v1/users/me/messages?labelIds=INBOX&q=is%3Aunread&maxResults=5",
                  self.guard(self._list))

    def _label(self, j, err):
        if j:
            self.set_badge(j.get("messagesUnread", 0))

    def _list(self, j, err):
        if err:
            self.finish(err); return
        ids = [m["id"] for m in (j or {}).get("messages", [])]
        self.gen += 1; gen = self.gen; self.msgs = {}; self.want = len(ids)
        if not ids:
            self.show_msgs([]); return
        for i in ids:
            self.svc().request("GET", f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{i}"
                               "?format=metadata&metadataHeaders=From&metadataHeaders=Subject",
                               self.guard(lambda j, e, i=i, gen=gen: self._one(gen, i, j)))

    def _one(self, gen, i, j):
        if gen != self.gen:
            return
        self.msgs[i] = j or {"id": i}; self.want -= 1
        if self.want == 0:
            self.show_msgs(sorted(self.msgs.values(), key=lambda m: -int(m.get("internalDate", 0) or 0)))

    def show_msgs(self, ms):
        self.clear(); self.finish()
        if not ms:
            self.content.addWidget(lbl("Brak nieprzeczytanych wiadomości 🎉", "muted2")); return
        for m in ms:
            h = {x["name"].lower(): x["value"] for x in (m.get("payload") or {}).get("headers", [])}
            ts = int(m.get("internalDate", 0) or 0) / 1000
            d = datetime.fromtimestamp(ts) if ts else None
            when = "" if not d else (d.strftime("%H:%M") if d.date() == date.today() else d.strftime("%d.%m"))
            b = QPushButton(f"{_sender(h.get('from', ''))}   {when}\n{(h.get('subject') or '(bez tematu)')[:46]}")
            b.setObjectName("mailitem"); b.setToolTip(h.get("subject", ""))
            b.clicked.connect(lambda _=False, i=m.get("id"): self.host.browser.open_url_new_tab(
                f"https://mail.google.com/mail/u/0/#inbox/{i}"))
            self.content.addWidget(b)


class CalendarWidget(GoogleWidget):
    def fetch(self):
        now = datetime.now().astimezone(); end = (now + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
        q = urlencode({"timeMin": now.isoformat(), "timeMax": end.isoformat(), "singleEvents": "true",
                       "orderBy": "startTime", "maxResults": 8})
        self.svc().request("GET", "https://www.googleapis.com/calendar/v3/calendars/primary/events?" + q, self.guard(self._ev))

    def _ev(self, j, err):
        if err:
            self.finish(err); return
        self.clear(); self.finish()
        items = (j or {}).get("items", [])
        if not items:
            self.content.addWidget(lbl("Brak nadchodzących wydarzeń.", "muted2")); return
        today, last = date.today(), None
        for ev in items:
            s = ev.get("start", {})
            try:
                if s.get("dateTime"):
                    d = datetime.fromisoformat(s["dateTime"].replace("Z", "+00:00")).astimezone(); hh = d.strftime("%H:%M")
                else:
                    d = datetime.fromisoformat(s["date"]); hh = "cały dzień"
            except Exception:
                continue
            day = "Dziś" if d.date() == today else "Jutro" if d.date() == today + timedelta(days=1) else d.strftime("%d.%m")
            if day != last:
                self.content.addWidget(section(day)); last = day
            b = QPushButton(f"{hh}   {(ev.get('summary') or '(bez tytułu)')[:36]}"); b.setObjectName("mailitem")
            b.clicked.connect(lambda _=False, u=ev.get("htmlLink"): u and self.host.browser.open_url_new_tab(u))
            self.content.addWidget(b)


class GTasksWidget(GoogleWidget):
    BASE = "https://tasks.googleapis.com/tasks/v1/lists/@default/tasks"

    def extra_build(self):
        self.inp = QLineEdit(); self.inp.setObjectName("glassin"); self.inp.setPlaceholderText("Dodaj zadanie i naciśnij Enter")
        self.inp.returnPressed.connect(self.add); self.lay.insertWidget(0, self.inp); self.inp.hide()

    def sync_state(self):
        super().sync_state()
        if not (self.svc() and self.svc().logged_in()):
            self.inp.hide()

    def fetch(self):
        self.svc().request("GET", self.BASE + "?showCompleted=false&maxResults=15", self.guard(self._tasks))

    def _tasks(self, j, err):
        if err:
            self.finish(err); return
        self.clear(); self.finish(); self.inp.show()
        items = [t for t in (j or {}).get("items", []) if t.get("title")]
        if not items:
            self.content.addWidget(lbl("Brak zadań.", "muted2")); return
        for t in items:
            cb = QCheckBox(t["title"][:44]); cb.setObjectName("todo"); cb.setToolTip(t["title"])
            cb.toggled.connect(lambda v, tid=t["id"]: v and self.complete(tid)); self.content.addWidget(cb)

    def add(self):
        t = self.inp.text().strip()
        if t:
            self.inp.clear()
            self.svc().request("POST", self.BASE, self.guard(lambda j, e: self.refresh()), {"title": t})

    def complete(self, tid):
        self.svc().request("PATCH", f"{self.BASE}/{tid}", self.guard(lambda j, e: self.refresh()), {"status": "completed"})


WIDGET_CLASSES = {"streak": StreakWidget, "clock": ClockWidget, "weather": WeatherWidget, "markets": MarketsWidget,
                  "currency": CurrencyWidget, "notes": NotesWidget, "todo": TodoWidget, "pomodoro": PomodoroWidget,
                  "clipboard": ClipboardWidget, "calc": CalcWidget, "translate": TranslateWidget, "system": SystemWidget,
                  "audio": AudioWidget, "rss": RssWidget, "gmail": GmailWidget, "calendar": CalendarWidget,
                  "gtasks": GTasksWidget}


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
    sa = QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.Shape.NoFrame)
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
        l.addWidget(switch_row(name, desc, dlg.store.feature(fid), lambda v, f=fid: dlg.store.set_feature(f, v)))
        sep = QFrame(); sep.setObjectName("sep"); l.addWidget(sep)
    l.addStretch(1)
    return scroll_page(w)


class WidgetsPage(QWidget):
    """Dwie listy (lewy / prawy panel): przeciągaj, aby zmienić panel i kolejność; pole = włączony."""

    def __init__(self, dlg):
        super().__init__()
        self.setObjectName("clear"); self.dlg, self.store = dlg, dlg.store; self._busy = False
        l = QVBoxLayout(self); l.setContentsMargins(24, 20, 24, 20); l.setSpacing(8)
        l.addWidget(lbl("Widgety", "h1"))
        l.addWidget(lbl("Przeciągnij widget do drugiej listy, aby zmienić panel, lub w obrębie listy, aby zmienić kolejność. "
                        "Zaznaczone widgety są włączone.", "muted2", wrap=True))
        cols = QHBoxLayout(); cols.setSpacing(14); self.lists = {}
        for side, title in (("left", "Lewy panel"), ("right", "Prawy panel")):
            box = QVBoxLayout(); box.addWidget(section(title))
            lw = QListWidget(); lw.setObjectName("wlist")
            lw.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop); lw.setDefaultDropAction(Qt.DropAction.MoveAction)
            lw.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); lw.setSpacing(2)
            lw.viewport().setAutoFillBackground(False)
            self.lists[side] = lw; box.addWidget(lw, 1); cols.addLayout(box, 1)
        l.addLayout(cols, 1)
        row = QHBoxLayout(); row.setSpacing(6)
        for text, fn in (("▲ W górę", lambda: self.shift(-1)), ("▼ W dół", lambda: self.shift(1)),
                         ("⇄ Drugi panel", self.flip), ("Zwiń / rozwiń", self.collapse), ("Przywróć domyślne", self.reset)):
            b = QPushButton(text); b.clicked.connect(lambda _=False, f=fn: f()); row.addWidget(b)
        row.addStretch(); l.addLayout(row)
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self.apply)
        self.fill()
        for lw in self.lists.values():
            m = lw.model(); m.rowsInserted.connect(self._soon); m.rowsRemoved.connect(self._soon); m.rowsMoved.connect(self._soon)
            lw.itemChanged.connect(self._soon)

    def _soon(self, *a):
        if not self._busy:
            self._t.start(60)

    def fill(self):
        self._busy = True
        for side, lw in self.lists.items():
            lw.clear()
            for wid in self.store.side_order(side):
                title, _, _, _, gate = WIDGETS[wid]; c = self.store.wcfg(wid)
                note = f"  — wymaga: {FEATURES[gate][0]}" if gate and not self.store.feature(gate) else ""
                it = QListWidgetItem(title + ("  · zwinięty" if c["collapsed"] else "") + note)
                it.setData(Qt.ItemDataRole.UserRole, wid)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsDragEnabled)
                it.setCheckState(Qt.CheckState.Checked if c["on"] else Qt.CheckState.Unchecked); lw.addItem(it)
        self._busy = False

    def apply(self):
        ids = {s: [lw.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lw.count())] for s, lw in self.lists.items()}
        if len(ids["left"]) + len(ids["right"]) != len(WIDGETS) or set(ids["left"]) | set(ids["right"]) != set(WIDGETS):
            return  # przeciąganie w toku
        ons = {lw.item(i).data(Qt.ItemDataRole.UserRole): lw.item(i).checkState() == Qt.CheckState.Checked
               for lw in self.lists.values() for i in range(lw.count())}
        self.store.apply_layout(ids["left"], ids["right"], ons)

    def current(self):
        for side, lw in self.lists.items():
            if lw.currentRow() >= 0 and lw.currentItem() is not None and lw.currentItem().isSelected():
                return side, lw
        for side, lw in self.lists.items():
            if lw.currentItem() is not None:
                return side, lw
        return None, None

    def shift(self, d):
        side, lw = self.current()
        if lw is None:
            return
        r = lw.currentRow(); n = r + d
        if 0 <= n < lw.count():
            self._busy = True; it = lw.takeItem(r); lw.insertItem(n, it); lw.setCurrentRow(n); self._busy = False
            self.apply()

    def flip(self):
        side, lw = self.current()
        if lw is None:
            return
        wid = lw.currentItem().data(Qt.ItemDataRole.UserRole); self.dlg.host.flip(wid); self.fill()

    def collapse(self):
        side, lw = self.current()
        if lw is None:
            return
        wid = lw.currentItem().data(Qt.ItemDataRole.UserRole); inst = self.dlg.host.inst.get(wid)
        if inst is not None:
            inst.toggle()
        else:
            self.store.set_wcfg(wid, collapsed=not self.store.wcfg(wid)["collapsed"], emit=False)
        self.fill()

    def reset(self):
        self.store.settings.pop("widgets", None); self.store.save_settings(); self.store.layout_changed.emit(); self.fill()


@settings_page("widgets", "Widgety")
def page_widgets(dlg):
    return WidgetsPage(dlg)


@settings_page("google", "Konto Google")
def page_google(dlg):
    w, l = page_box("Konto Google", "Gmail, Kalendarz i Zadania. Logowanie odbywa się w Twojej zwykłej przeglądarce "
                                    "(OAuth 2.0 + PKCE); sesja jest trwała i odnawiana w tle.")
    g = dlg.host.google
    if g is None:
        l.addWidget(lbl("Integracja z Google jest wyłączona (Ustawienia → Funkcje).", "muted2", wrap=True)); l.addStretch(1)
        return scroll_page(w)
    store = dlg.store; cfg = g.cfg()
    cid = QLineEdit(cfg.get("client_id", "")); cid.setObjectName("glassin"); cid.setPlaceholderText("Client ID  (…apps.googleusercontent.com)")
    sec = QLineEdit(cfg.get("client_secret", "")); sec.setObjectName("glassin"); sec.setPlaceholderText("Client Secret")
    sec.setEchoMode(QLineEdit.EchoMode.Password)

    def save():
        store.settings.setdefault("google", {}).update(client_id=cid.text().strip(), client_secret=sec.text().strip())
        store.save_settings(); g.state_changed.emit()
    cid.editingFinished.connect(save); sec.editingFinished.connect(save)
    status = lbl("", "h3", wrap=True)
    b_in = QPushButton("Zaloguj przez Google"); b_out = QPushButton("Wyloguj")
    b_in.clicked.connect(lambda: (save(), g.login())); b_out.clicked.connect(g.logout)
    row = QHBoxLayout(); row.addWidget(b_in); row.addWidget(b_out); row.addStretch()

    def refresh():
        if g.logged_in():
            t = f"Zalogowano jako {g.email() or 'konto Google'}"
        elif g.expired:
            t = "Sesja wygasła – zaloguj się ponownie."
        elif g.busy:
            t = "Dokończ logowanie w oknie przeglądarki…"
        elif not g.configured():
            t = "Podaj Client ID i Client Secret."
        else:
            t = "Nie zalogowano."
        status.setText(t + (f"\n{g.last_error}" if g.last_error else ""))
        b_in.setVisible(not g.logged_in()); b_out.setVisible(g.logged_in())
    g.state_changed.connect(refresh); dlg.finished.connect(lambda _=0: safe_disconnect(g.state_changed, refresh)); refresh()
    help_ = lbl("Jak uzyskać dane logowania (jednorazowo):\n"
                "1. Wejdź na console.cloud.google.com/apis/credentials, utwórz projekt i włącz API: Gmail, Google Calendar, Google Tasks.\n"
                "2. Utwórz „Identyfikator klienta OAuth” typu Aplikacja na komputer.\n"
                "3. Wklej Client ID i Secret powyżej i kliknij „Zaloguj przez Google”.\n\n"
                "Uwaga: gdy ekran zgody ma status „Testing”, dodaj swoje konto do użytkowników testowych – Google "
                "unieważnia wtedy sesję co 7 dni (Luna pokaże komunikat i poprosi o ponowne logowanie). "
                "Token odświeżania trafia do systemowego pęku kluczy (pakiet keyring), a gdy go brak – do pliku ustawień.",
                "muted", wrap=True)
    openc = QPushButton("Otwórz konsolę Google Cloud")
    openc.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://console.cloud.google.com/apis/credentials")))
    for x in (status, cid, sec):
        l.addWidget(x)
    l.addLayout(row); l.addSpacing(10); l.addWidget(help_); l.addWidget(openc, 0, Qt.AlignmentFlag.AlignLeft); l.addStretch(1)
    return scroll_page(w)


@settings_page("look", "Wygląd")
def page_look(dlg):
    w, l = page_box("Wygląd", "Tło ekranu głównego skaluje się w trybie „cover” (wypełnia i centruje bez zniekształceń).")
    store = dlg.store
    combo = QComboBox()
    for key, name in (("image", "Obraz – ciemne ukośne paski"), ("gradient", "Gradient"), ("solid", "Jednolite czarne")):
        combo.addItem(name, key)
    combo.setCurrentIndex(max(0, combo.findData(store.settings.get("bg", "image"))))

    def bg_changed(_):
        store.settings["bg"] = combo.currentData(); store.save_settings()
        BG.key = None; dlg.browser.bgframe._recompute(); dlg.host.repaint_all()
    combo.currentIndexChanged.connect(bg_changed)
    sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(60, 235); sl.setValue(GLASS_ALPHA[0])

    def glass(v):
        GLASS_ALPHA[0] = v; store.settings["glass"] = v; store.save_soon(); dlg.host.repaint_all()
    sl.valueChanged.connect(glass)
    l.addWidget(lbl("Tło", "h3")); l.addWidget(combo); l.addSpacing(10)
    l.addWidget(lbl("Nieprzezroczystość paneli (szkło)", "h3")); l.addWidget(sl); l.addStretch(1)
    return scroll_page(w)


@settings_page("keys", "Skróty")
def page_keys(dlg):
    w, l = page_box("Skróty klawiszowe i gesty", "Można je wyłączyć w Funkcje → Skróty klawiszowe i gesty myszy.")
    for k, d in (("Ctrl + T", "Nowa karta"), ("Ctrl + W", "Zamknij kartę"), ("F5 / Ctrl + R", "Odśwież kartę lub widgety"),
                 ("Ctrl + Tab / Ctrl + Shift + Tab", "Następna / poprzednia karta"), ("Ctrl + L", "Pasek adresu"),
                 ("Ctrl + J", "Asystent AI"), ("Ctrl + ,", "Ustawienia"),
                 ("Środkowy przycisk na karcie", "Zamyka kartę"), ("Środkowy przycisk na pustym pasku", "Nowa karta")):
        row = QHBoxLayout(); a = lbl(k, "h3"); b = lbl(d, "muted2")
        row.addWidget(a); row.addStretch(); row.addWidget(b); l.addLayout(row)
    l.addStretch(1)
    return scroll_page(w)


class DragBar(QWidget):
    def __init__(self):
        super().__init__(); self.setObjectName("setHead")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def mousePressEvent(self, ev):
        h = self.window().windowHandle()
        if ev.button() == Qt.MouseButton.LeftButton and h:
            h.startSystemMove()


class SettingsDialog(QDialog):
    def __init__(self, store, host, browser):
        super().__init__(browser)
        self.store, self.host, self.browser, self.built = store, host, browser, {}
        self.setObjectName("settings"); self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setModal(True); self.resize(940, 640); self.setMinimumSize(660, 460)
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

        self.grid.viewport().setAutoFillBackground(False); self.recent.viewport().setAutoFillBackground(False)
        self._dirty = False
        self._rt = QTimer(self); self._rt.setSingleShot(True); self._rt.timeout.connect(self.refresh)
        self.store.changed.connect(self._soon)
        self.refresh()

    def _soon(self):
        """Odświeżanie kafelków tylko gdy strona jest widoczna; w tle jedynie znacznik „do odświeżenia”."""
        if self.isVisible():
            self._rt.start(120)
        else:
            self._dirty = True

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
        self.browser.update_sidebars_soon()

    def show_home(self):
        self.setCurrentWidget(self.home)
        self.browser.update_sidebars_soon()

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
        self._ri = QTimer(self); self._ri.setSingleShot(True); self._ri.timeout.connect(self.refresh_icons)
        store.changed.connect(lambda: self._ri.start(400))

    def release(self):
        """Zwalnia strony AI z pamięci (po wyłączeniu funkcji)."""
        for v in self.views.values():
            self.stack.removeWidget(v); v.deleteLater()
        self.views.clear()

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


class TabBar(QTabBar):
    """Pasek kart: środkowy przycisk myszy zamyka kartę (na pustym miejscu paska – nowa karta)."""
    middle_close = pyqtSignal(int)
    middle_new = pyqtSignal()

    def mouseReleaseEvent(self, ev):
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Luna"); self.setWindowIcon(app_icon()); self.resize(1300, 860)
        self.setMinimumSize(640, 480)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)  # bez ramki systemowej
        self.store = Store()

        central = Frame(); v = QVBoxLayout(central); self.frame_layout = v
        v.setContentsMargins(5, 5, 5, 5); v.setSpacing(0)

        # --- pasek kart (jednocześnie pasek tytułu) ---
        strip = TitleStrip(); strip.middle_new.connect(lambda: self.mmb_new())
        sl = QHBoxLayout(strip); sl.setContentsMargins(10, 5, 6, 4); sl.setSpacing(6)
        self.bar = TabBar(); self.bar.setExpanding(False); self.bar.setMovable(True); self.bar.setFixedHeight(34)
        self.bar.setDrawBase(False); self.bar.setElideMode(Qt.TextElideMode.ElideRight)
        self.bar.currentChanged.connect(self.on_tab_changed)
        self.bar.tabMoved.connect(self.on_tab_moved)
        self.bar.middle_close.connect(lambda i: self.store.feature("shortcuts") and self.close_tab(self.stack.widget(i)))
        self.bar.middle_new.connect(lambda: self.mmb_new())
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
        tl.addWidget(self.btn("gear", "Ustawienia (Ctrl+,)", self.open_settings))
        v.addWidget(tool)

        self.stack = QStackedWidget()
        self.bgframe = BgFrame()
        body = QHBoxLayout(self.bgframe); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(0)
        self.host = WidgetHost(self.store, self)
        self.assistant = Assistant(self.store, self); self.assistant.hide()
        body.addWidget(self.host.left); body.addWidget(self.stack, 1); body.addWidget(self.host.right)
        body.addWidget(self.assistant)
        v.addWidget(self.bgframe, 1)
        self.setCentralWidget(central)
        # drobne odświeżenia UI z debouncingiem (zdarzeń „changed” jest dużo: ikony, ładowanie stron)
        self._ui_t = QTimer(self); self._ui_t.setSingleShot(True); self._ui_t.timeout.connect(self._ui_refresh)
        self.store.changed.connect(lambda: self._ui_t.start(150))
        self._sb_t = QTimer(self); self._sb_t.setSingleShot(True); self._sb_t.timeout.connect(self.update_sidebars)
        self.update_engine_ui()
        self.setup_shortcuts()
        self.store.features_changed.connect(self.apply_features)
        self.new_tab()
        self.apply_features(); self.host.sync()
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

    def _ui_refresh(self):
        self.update_engine_ui(); self.update_star()

    def setup_shortcuts(self):
        defs = [("Ctrl+T", self.new_tab), ("Ctrl+W", lambda: self.close_tab(self.cur())),
                ("F5", self.reload_current), ("Ctrl+R", self.reload_current),
                ("Ctrl+Tab", lambda: self.cycle_tab(1)), ("Ctrl+Shift+Tab", lambda: self.cycle_tab(-1)),
                ("Ctrl+Backtab", lambda: self.cycle_tab(-1)), ("Ctrl+PgDown", lambda: self.cycle_tab(1)),
                ("Ctrl+PgUp", lambda: self.cycle_tab(-1)), ("Ctrl+J", self.toggle_assistant),
                ("Ctrl+,", self.open_settings),
                ("Ctrl+L", lambda: (self.address.setFocus(), self.address.selectAll()))]
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
        self.update_sidebars()

    def update_sidebars(self):
        t = self.cur()
        ok = bool(t and t.on_home()) or self.store.feature("everywhere")
        avail = self.width() - (self.assistant.width() if self.assistant.isVisible() else 0)
        for sb in (self.host.left, self.host.right):
            sb.setVisible(self.store.feature(sb.side) and ok and avail >= 1020 and sb.has_widgets())

    def update_sidebars_soon(self):
        self._sb_t.start(40)

    def resizeEvent(self, ev):
        super().resizeEvent(ev); self._sb_t.start(120)

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

    def cycle_tab(self, d):
        n = self.bar.count()
        if n > 1:
            self.bar.setCurrentIndex((self.bar.currentIndex() + d) % n)

    def refresh_close_icons(self):
        cur = self.bar.currentIndex()
        for i in range(self.bar.count()):
            b = self.bar.tabButton(i, QTabBar.ButtonPosition.RightSide)
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
        self.assistant.setVisible(show)
        self.ai_btn.setIcon(glyph("assistantfill" if show else "assistant"))
        if show:
            self.assistant.ensure()
        self.update_sidebars_soon()

    def open_url_new_tab(self, url):
        self.new_tab(); self.cur().go(url)

    def closeEvent(self, ev):
        self.host.shutdown_all(); self.store.save_settings()
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

    # --- karty ---
    def new_tab(self):
        t = Tab(self.store, self)
        self.stack.addWidget(t)
        i = self.bar.addTab("Ekran główny")
        cb = QToolButton(); cb.setObjectName("tabclose"); cb.setFixedSize(20, 20); cb.setIconSize(QSize(14, 14))
        cb.setIcon(glyph("close", "#8c8c8c")); cb.setCursor(Qt.CursorShape.PointingHandCursor); cb.setToolTip("Zamknij kartę")
        cb.clicked.connect(lambda: self.close_tab(t))
        self.bar.setTabButton(i, QTabBar.ButtonPosition.RightSide, cb)
        self.bar.setCurrentIndex(i)
        self.refresh_close_icons()

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
        self.refresh_close_icons(); self.update_sidebars_soon()

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
        self.address.clear(); self.update_sidebars_soon()

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
