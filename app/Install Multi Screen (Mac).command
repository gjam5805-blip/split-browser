#!/bin/bash
# Multi Screen install (Mac). Finder me double-click karo (ya Terminal me: bash "Install Multi Screen (Mac).command")
cd "$(dirname "$0")"
DEST="$HOME/MultiScreen"
echo ""
echo "=== Multi Screen install (Mac) ==="
if [ ! -d "/Applications/Google Chrome.app" ]; then echo "Google Chrome nahi mila. Pehle Chrome install karo."; exit 1; fi
PY=/usr/bin/python3
if ! "$PY" -c 'print(1)' >/dev/null 2>&1; then
  echo "[1/3] Python ke liye Apple ka 'Command Line Tools' popup aayega -> Install dabao. Hone ke baad ye dobara chalao."
  xcode-select --install
  exit 1
fi
echo "[1/3] Python: $($PY --version)"
mkdir -p "$DEST"
cp multiscreen.py icon.png "$DEST/"
echo "[2/3] App copy ho gaya: $DEST"
mkdir -p "$HOME/Applications"
rm -rf "$HOME/Applications/Multi Screen.app"
osacompile -o "$HOME/Applications/Multi Screen.app" -e "do shell script \"$PY '$DEST/multiscreen.py' > /dev/null 2>&1 &\""
ln -sfn "$HOME/Applications/Multi Screen.app" "$HOME/Desktop/Multi Screen"
echo "[3/3] Desktop pe 'Multi Screen' lag gaya."
open "$HOME/Applications/Multi Screen.app"
echo ""
echo "Ho gaya! Pehli baar Mac poochega 'control Google Chrome?' -> OK / Allow dabana."
echo ""
