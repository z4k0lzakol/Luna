#!/usr/bin/env bash
# Luna jako AppImage (Linux, x86_64): jeden plik, uruchamiany bez instalacji.
#   bash packaging/build_appimage.sh 1.0.0      (po: python -m PyInstaller --noconfirm packaging/luna.spec)
set -euo pipefail
VERSION="${1:?podaj wersję, np. 1.0.0}"
APPDIR=dist/Luna.AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$APPDIR/usr/share/applications"
cp -r dist/Luna/. "$APPDIR/usr/bin/"
python3 - <<'PY'
from PyQt6.QtGui import QImage, QGuiApplication
import sys
app = QGuiApplication(["x", "-platform", "offscreen"])
QImage("luna-logo.png").scaled(256, 256).save("dist/Luna.AppDir/luna.png")
PY
cp "$APPDIR/luna.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/luna.png"
cat > "$APPDIR/luna.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Luna
GenericName=Przeglądarka internetowa
Comment=Lekka, ciemna przeglądarka z widgetami, podziałem ekranu i blokadą reklam
Exec=Luna %U
Icon=luna
Terminal=false
Categories=Network;WebBrowser;
MimeType=text/html;x-scheme-handler/http;x-scheme-handler/https;
StartupWMClass=Luna
EOF
cp "$APPDIR/luna.desktop" "$APPDIR/usr/share/applications/luna.desktop"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
# Ubuntu 24.04+ blokuje przestrzenie nazw użytkownika potrzebne piaskownicy Chromium – wtedy silnik startuje bez niej
if [ "$(cat /proc/sys/kernel/apparmor_restrict_unprivileged_userns 2>/dev/null)" = "1" ]; then
  export QTWEBENGINE_DISABLE_SANDBOX=1
fi
exec "$HERE/usr/bin/Luna" "$@"
EOF
chmod +x "$APPDIR/AppRun"
if [ ! -x appimagetool ]; then
  wget -q https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage -O appimagetool
  chmod +x appimagetool
fi
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 ./appimagetool "$APPDIR" "dist/Luna-$VERSION-Linux-x86_64.AppImage"
echo "Gotowe: dist/Luna-$VERSION-Linux-x86_64.AppImage"
