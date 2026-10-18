#!/usr/bin/env bash
# Installe l'AppImage dans ~/.local : une commande « go-sensei » et une entrée
# dans le menu des applications. Rien en dehors du dossier personnel, aucun sudo.
#
#   ./install.sh                  installe le dernier AppImage construit ici
#   ./install.sh chemin.AppImage  installe celui-là
#   ./install.sh -u               désinstalle (garde réglages et données)
#
# Si l'outil « shortcut » (github.com/Rimsoo/shortcut) est dans le PATH, c'est
# lui qui fait le travail. Sinon on fait la même chose à la main.

set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

NOM="go-sensei"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/256x256/apps"

desinstaller() {
    if command -v shortcut >/dev/null 2>&1; then
        shortcut -u "$NOM" && return 0
    fi
    rm -f "$BIN/$NOM" "$APPS/$NOM.desktop" "$ICONS/$NOM.png"
    echo "désinstallé (réglages : ~/.config/go-sensei, données : ~/.local/share/go-sensei)."
}

if [ "${1:-}" = "-u" ] || [ "${1:-}" = "--uninstall" ]; then
    desinstaller
    exit 0
fi

APP="${1:-}"
if [ -z "$APP" ]; then
    APP="$(ls -t ./*.AppImage 2>/dev/null | head -1 || true)"
fi
if [ -z "$APP" ] || [ ! -f "$APP" ]; then
    echo "aucun AppImage trouvé. Construis-le d'abord :" >&2
    echo "  ./build-appimage.sh" >&2
    exit 1
fi
APP="$(readlink -f "$APP")"
chmod +x "$APP"

if command -v shortcut >/dev/null 2>&1; then
    echo "== installation avec shortcut"
    shortcut "$APP" "$NOM" "$PWD/appimage/gosensei.png"
else
    echo "== installation manuelle (shortcut absent du PATH)"
    mkdir -p "$BIN" "$APPS" "$ICONS"
    ln -sf "$APP" "$BIN/$NOM"
    cp -f appimage/gosensei.png "$ICONS/$NOM.png"
    # L'Exec du fichier livré vise le point d'entrée interne ; le menu doit viser l'AppImage.
    sed -e "s|^Exec=.*|Exec=$BIN/$NOM|" \
        -e "s|^Icon=.*|Icon=$NOM|" \
        -e "s|^Name=.*|Name=Go Sensei|" \
        -e '/^#/d' \
        appimage/gosensei.desktop > "$APPS/$NOM.desktop"
    chmod 644 "$APPS/$NOM.desktop"
    command -v update-desktop-database >/dev/null 2>&1 \
        && update-desktop-database "$APPS" 2>/dev/null || true
fi

echo
echo "== terminé"
echo "   commande      :  $NOM          (--stop pour arrêter, --no-window pour le serveur seul)"
echo "   menu          :  Go Sensei (catégories Jeux / Éducation)"
echo "   désinstaller  :  ./install.sh -u"
case ":$PATH:" in
    *":$BIN:"*) ;;
    *) echo
       echo "   note : $BIN n'est pas dans ton PATH."
       echo "          Ajoute-le dans ta config de shell : export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac
