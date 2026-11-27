#!/bin/bash
# Instalacja Luny na macOS jednym poleceniem w Terminalu:
#   curl -fsSL https://raw.githubusercontent.com/z4k0lzakol/Luna/main/packaging/install-mac.sh | bash
#
# Dlaczego tak: Luna nie ma podpisu Apple (Developer ID), więc plik .dmg pobrany przeglądarką dostaje znacznik
# kwarantanny i Gatekeeper pokazuje „Rzecz »Luna« nie została otwarta”. Plik pobrany przez curl tego znacznika
# nie dostaje, a na wszelki wypadek skrypt i tak go zdejmuje (xattr). Nic poza tym nie zmienia w systemie.
set -euo pipefail

URL="https://github.com/z4k0lzakol/Luna/releases/latest/download/Luna-macOS-arm64.dmg"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "Ten skrypt jest tylko dla macOS."; exit 1
fi
if [ "$(uname -m)" != "arm64" ]; then
  echo "Luna na macOS działa na Macach z Apple M1 i nowszych (arm64). Ten Mac ma procesor Intel."; exit 1
fi

# /Applications, a gdy brak uprawnień – ~/Applications (bez hasła administratora)
DEST="/Applications"
if [ ! -w "$DEST" ]; then
  DEST="$HOME/Applications"; mkdir -p "$DEST"
fi

TMP="$(mktemp -d)"
MNT=""
cleanup() {
  [ -n "$MNT" ] && hdiutil detach "$MNT" -quiet >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

echo "Pobieranie Luny…"
curl -fL --progress-bar -o "$TMP/Luna.dmg" "$URL"

echo "Instalowanie w $DEST…"
MNT="$TMP/mnt"; mkdir -p "$MNT"
hdiutil attach "$TMP/Luna.dmg" -nobrowse -readonly -mountpoint "$MNT" -quiet

osascript -e 'tell application "Luna" to quit' >/dev/null 2>&1 || true
rm -rf "$DEST/Luna.app"
ditto "$MNT/Luna.app" "$DEST/Luna.app"
xattr -dr com.apple.quarantine "$DEST/Luna.app" 2>/dev/null || true

echo "Gotowe – Luna jest w $DEST. Uruchamiam…"
open "$DEST/Luna.app"
