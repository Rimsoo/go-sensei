#!/usr/bin/env bash
# Construit GoSensei-x86_64.AppImage à partir de ce dossier.
#
#   ./build-appimage.sh             AppImage complète : Python + KataGo + réseaux (≈ 245 Mo)
#   BUNDLE_KATAGO=0 ./build-appimage.sh
#                                   AppImage légère (≈ 40 Mo) : KataGo est téléchargé
#                                   depuis l'interface au premier lancement
#
# Résultat : un fichier unique et exécutable qui embarque Python, Go Sensei,
# le SDK Anthropic et (par défaut) KataGo. Rien à installer chez l'utilisateur.
# La construction télécharge une image Python manylinux, appimagetool et KataGo
# depuis leurs dépôts officiels : il lui faut un accès réseau. Les
# téléchargements sont gardés dans .build-cache/ pour les constructions suivantes.

set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
PROJET="$PWD"

PYVER="${PYVER:-3.12}"
VENV="${VENV:-.build-venv}"
CACHE="$PROJET/.build-cache"
BUNDLE_KATAGO="${BUNDLE_KATAGO:-1}"

KATAGO_VERSION="$(python3 -c 'import re;print(re.search(r"KATAGO_VERSION = \"(.+?)\"", open("gosensei/katago.py").read())[1])')"
# Réseaux embarqués : b18 pour les cartes graphiques, b10 pour les processeurs.
MODELS="$(PYTHONPATH="$PROJET" python3 -c 'from gosensei.katago import MODEL_NAME, CPU_MODEL_NAME; print(MODEL_NAME, CPU_MODEL_NAME)')"
RELEASE="https://github.com/lightvector/KataGo/releases/download/v$KATAGO_VERSION"
MODELS_URL="$(PYTHONPATH="$PROJET" python3 -c 'from gosensei.katago import MODELS_URL; print(MODELS_URL)')"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
RUNTIME_URL="https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64"

echo "== vérification des fichiers"
for f in pyproject.toml gosensei/__main__.py gosensei/static/index.html gosensei/resources/analysis.cfg \
         appimage/gosensei.desktop appimage/gosensei.png appimage/entrypoint.sh; do
    [ -f "$f" ] || { echo "manquant : $f" >&2; exit 1; }
done
if grep -q '^Name=.* ' appimage/gosensei.desktop; then
    echo "le champ Name du .desktop contient un espace : python-appimage ne le protège pas." >&2
    exit 1
fi

echo "== environnement de construction"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip python-appimage
mkdir -p "$CACHE"

# python-appimage lance « pip install » depuis son propre dossier : la recette
# donne donc le chemin ABSOLU du projet (avec l'extra anthropic).
RECETTE="$(mktemp -d)"
TRAVAIL="$(mktemp -d)"
trap 'rm -rf "$RECETTE" "$TRAVAIL"' EXIT
cp appimage/gosensei.desktop appimage/gosensei.png appimage/entrypoint.sh "$RECETTE/"
printf '%s\n' "$PROJET[anthropic,tray]" > "$RECETTE/requirements.txt"

echo "== construction (Python $PYVER manylinux)"
rm -f GoSensei-x86_64.AppImage
# python-appimage prépare seulement le dossier de l'application (--no-packaging) :
# laissé à lui-même, son appimagetool télécharge le runtime AppImage depuis GitHub
# et ce téléchargement peut se figer indéfiniment. On assemble nous-mêmes plus bas,
# avec un runtime récupéré par curl et gardé en cache.
( cd "$TRAVAIL" && "$PROJET/$VENV/bin/python" -m python_appimage build app --no-packaging -p "$PYVER" "$RECETTE" )
APPDIR="$TRAVAIL/GoSensei-$(uname -m)"
[ -x "$APPDIR/AppRun" ] || { echo "python-appimage n'a pas produit $APPDIR" >&2; exit 1; }
OUT="./GoSensei-x86_64.AppImage"

telecharger() {  # url fichier
    [ -s "$2" ] || { echo "   téléchargement de $(basename "$2")"; curl -fsSL --retry 3 -o "$2.part" "$1" && mv "$2.part" "$2"; }
}

if [ "$BUNDLE_KATAGO" != "0" ]; then
    echo "== ajout de KataGo $KATAGO_VERSION et des réseaux de neurones"
    KDIR="$APPDIR/opt/katago"
    mkdir -p "$KDIR/models"
    for build in opencl eigenavx2; do
        zip="$CACHE/katago-v$KATAGO_VERSION-$build-linux-x64.zip"
        telecharger "$RELEASE/katago-v$KATAGO_VERSION-$build-linux-x64.zip" "$zip"
        mkdir -p "$KDIR/$build"
        PYTHONPATH="$PROJET" python3 - "$zip" "$KDIR/$build" <<'PY'
import os, sys, zipfile
from gosensei.katago import unpack_appimage
zf = zipfile.ZipFile(sys.argv[1])
for m in zf.namelist():
    base = os.path.basename(m)
    if base in ("katago", "LICENSE.txt", "README.txt"):
        with zf.open(m) as src, open(os.path.join(sys.argv[2], base), "wb") as out:
            out.write(src.read())
os.chmod(os.path.join(sys.argv[2], "katago"), 0o755)
unpack_appimage(os.path.join(sys.argv[2], "katago"))  # AppImage -> fichiers (pas de FUSE imbriqué)
PY
    done
    telecharger "https://raw.githubusercontent.com/lightvector/KataGo/v$KATAGO_VERSION/LICENSE" "$CACHE/LICENSE-KataGo.txt"
    cp "$CACHE/LICENSE-KataGo.txt" "$KDIR/"
    for model in $MODELS; do
        telecharger "$MODELS_URL/$model" "$CACHE/$model"
        cp "$CACHE/$model" "$KDIR/models/"
    done
fi

echo "== assemblage de l'image"
telecharger "$APPIMAGETOOL_URL" "$CACHE/appimagetool"
telecharger "$RUNTIME_URL" "$CACHE/runtime-x86_64"
chmod +x "$CACHE/appimagetool"
ARCH=x86_64 "$CACHE/appimagetool" --appimage-extract-and-run --no-appstream \
    --runtime-file "$CACHE/runtime-x86_64" "$APPDIR" "$OUT" >/dev/null 2>"$TRAVAIL/appimagetool.log" \
    || { cat "$TRAVAIL/appimagetool.log" >&2; exit 1; }
chmod +x "$OUT"

echo
echo "== vérification de l'image"
if "$OUT" --appimage-extract-and-run --python -c "import gosensei.server, anthropic, dbus_fast" >/dev/null 2>&1; then
    echo "   Go Sensei, SDK Anthropic et icône de notification : OK"
else
    echo "   ATTENTION : Go Sensei ne s'importe pas dans l'image" >&2
fi
if [ "$BUNDLE_KATAGO" != "0" ]; then
    "$OUT" --appimage-extract-and-run --python -c "
import os; from gosensei import paths
d = paths.bundled_katago_dir(); print('   KataGo embarqué :', d and sorted(os.listdir(d)))"
fi

echo
echo "== terminé : $OUT ($(du -h "$OUT" | cut -f1))"
echo "   lancer        :  $OUT"
echo "   installer     :  ./install.sh"
echo
echo "Si le lancement répond « dlopen(): error loading libfuse.so.2 » : installer fuse2"
echo "(sudo pacman -S fuse2) ou lancer avec $OUT --appimage-extract-and-run"
