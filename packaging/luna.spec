# PyInstaller: Luna jako aplikacja (folder z programem) – wspólne dla Windows, Linuksa i macOS.
#   python -m PyInstaller --noconfirm packaging/luna.spec
# Wynik: dist/Luna/ (Windows, Linux) albo dist/Luna.app (macOS). Instalatory buduje workflow .github/workflows/release.yml.
import os
import re
import sys

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = re.search(r'^VERSION = "([^"]+)"', open(os.path.join(ROOT, "luna.py"), encoding="utf-8").read(), re.M).group(1)

datas = [
    (os.path.join(ROOT, "adblock", "js"), "adblock/js"),
    (os.path.join(ROOT, "adblock", "res"), "adblock/res"),
    (os.path.join(ROOT, "adblock", "luna-filters.txt"), "adblock"),
    (os.path.join(ROOT, "LICENSE"), "."),
]
binaries, hidden = [], ["adblock.compiler", "luna_link"]
# cryptography 50+ na Windows: moduł _rust jest zbudowany pod stabilne ABI Pythona 3.15 (abi3t) i ładuje python3t.dll,
# której PyInstaller sam nie dołącza – bez niej Luna nie tworzy certyfikatu (połączone urządzenia, kod QR)
_p3t = os.path.join(sys.base_prefix, "python3t.dll")
if sys.platform == "win32" and os.path.exists(_p3t):
    binaries.append((_p3t, "."))
optional = ["psutil", "cryptography"] + (["winrt"] if sys.platform == "win32" else ["keyring"])
for pkg in optional:   # moduły opcjonalne – dołączane, gdy są zainstalowane
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hidden += h
    except Exception:
        pass

version_file = None
if sys.platform == "win32":   # właściwości pliku Luna.exe (Szczegóły w Eksploratorze)
    nums = tuple(int(x) for x in re.findall(r"\d+", VERSION)[:3]) + (0,)
    version_file = os.path.join(SPECPATH, "build", "version_info.txt")
    os.makedirs(os.path.dirname(version_file), exist_ok=True)
    open(version_file, "w", encoding="utf-8").write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('041504B0', [
    StringStruct('CompanyName', 'Luna'), StringStruct('FileDescription', 'Luna – przeglądarka'),
    StringStruct('FileVersion', '{VERSION}'), StringStruct('InternalName', 'Luna'),
    StringStruct('LegalCopyright', 'Luna – GNU GPL v3'), StringStruct('OriginalFilename', 'Luna.exe'),
    StringStruct('ProductName', 'Luna'), StringStruct('ProductVersion', '{VERSION}')])]),
        VarFileInfo([VarStruct('Translation', [0x0415, 1200])])])
""")

a = Analysis([os.path.join(ROOT, "luna.py")], pathex=[ROOT], binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=["tkinter", "unittest", "pydoc"])
# Odchudzenie: biblioteki Qt, których Luna nie używa (3D, kontrolki QML, czujniki, Bluetooth…), i tłumaczenia Qt /
# silnika poza polskim i angielskim – bez nich pakiet jest o kilkaset MB mniejszy.
UNUSED = re.compile(r"(?:^|[/\\])(?:lib)?Qt6?(?:Quick3D|QuickControls2|QuickDialogs2|QuickTest|QuickTimeline|QuickParticles|"
                    r"QuickVectorImage|RemoteObjects|PdfQuick|MultimediaQuick|PositioningQuick|Designer|Sensors|Bluetooth|"
                    r"Nfc|SerialPort|SerialBus|Charts|DataVisualization|Graphs|SpatialAudio|TextToSpeech|Scxml|StateMachine|"
                    r"VirtualKeyboard|Location|3D|Test)", re.I)


def keep(dest):
    d = dest.replace("\\", "/")
    if UNUSED.search(d) or re.search(r"\.debug\.(pak|bin)$", d):   # zasoby silnika dla wersji debug (~75 MB)
        return False
    if "/translations/qtwebengine_locales/" in d:
        return d.rsplit("/", 1)[-1] in ("pl.pak", "en-US.pak")
    if "/translations/" in d and d.endswith(".qm"):
        return bool(re.search(r"_(pl|en)\.qm$", d))
    if "/qml/" in d and re.search(r"/qml/(QtQuick3D|QtQuick/Controls|QtQuick/Dialogs|QtQuick/Particles|QtQuick/Timeline|"
                                  r"QtTest|QtRemoteObjects|QtCharts|QtDataVisualization|QtGraphs|QtSensors|Qt3D)", d):
        return False
    return True


a.binaries = [x for x in a.binaries if keep(x[0])]
a.datas = [x for x in a.datas if keep(x[0])]
pyz = PYZ(a.pure)
icon = {"win32": os.path.join(ROOT, "luna.ico"), "darwin": os.path.join(ROOT, "luna-logo.png")}.get(sys.platform)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Luna", console=False, icon=icon, version=version_file)
coll = COLLECT(exe, a.binaries, a.datas, name="Luna")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="Luna.app", icon=icon, bundle_identifier="pl.luna.browser",
                 info_plist={"CFBundleName": "Luna", "CFBundleDisplayName": "Luna",
                             "CFBundleShortVersionString": VERSION, "CFBundleVersion": VERSION,
                             "NSHighResolutionCapable": True, "LSMinimumSystemVersion": "12.0",
                             "NSCameraUsageDescription": "Strony mogą prosić o dostęp do kamery (np. wideorozmowy).",
                             "NSMicrophoneUsageDescription": "Strony mogą prosić o dostęp do mikrofonu (np. wideorozmowy)."})
