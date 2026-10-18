"""Emplacements des fichiers (norme XDG) et des ressources embarquées."""

import os

PKG = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(PKG, "static")
RESOURCES = os.path.join(PKG, "resources")


def _xdg(var, default):
    return os.path.join(os.environ.get(var) or os.path.expanduser(default), "go-sensei")


CONFIG_DIR = _xdg("XDG_CONFIG_HOME", "~/.config")
DATA_DIR = _xdg("XDG_DATA_HOME", "~/.local/share")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

LOG_DIR = os.path.join(DATA_DIR, "logs")
REVIEW_DIR = os.path.join(DATA_DIR, "reviews")
TREE_DIR = os.path.join(DATA_DIR, "trees")  # variantes et annotations, par partie
OGS_DIR = os.path.join(DATA_DIR, "ogs")
IMPORT_DIR = os.path.join(DATA_DIR, "imported")
COACH_DIR = os.path.join(DATA_DIR, "coach")
KATAGO_DIR = os.path.join(DATA_DIR, "katago")  # binaires et réseaux téléchargés
BROWSER_PROFILE = os.path.join(DATA_DIR, "browser")
NOTES_FILE = os.path.join(DATA_DIR, "carnet-eleve.md")
CHAT_FILE = os.path.join(DATA_DIR, "chat.json")
PID_FILE = os.path.join(DATA_DIR, "server.pid")


def bundled_katago_dir():
    """KataGo embarqué : dans l'AppImage ($APPDIR/opt/katago) ou via GOSENSEI_KATAGO_DIR."""
    for d in (os.environ.get("GOSENSEI_KATAGO_DIR"),
              os.path.join(os.environ["APPDIR"], "opt", "katago") if os.environ.get("APPDIR") else None):
        if d and os.path.isdir(d):
            return d
    return None


def ensure_dirs():
    for d in (CONFIG_DIR, DATA_DIR, LOG_DIR, REVIEW_DIR, TREE_DIR, OGS_DIR, IMPORT_DIR, COACH_DIR, KATAGO_DIR):
        os.makedirs(d, exist_ok=True)


def host_env():
    """Environnement pour lancer des programmes du système (navigateur, claude…) depuis
    l'AppImage : on retire ce qui pointe vers l'image (Python, bibliothèques embarquées)."""
    env = dict(os.environ)
    appdir = env.get("APPDIR")
    for k in ("PYTHONHOME", "PYTHONPATH", "PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE"):
        env.pop(k, None)
    if appdir:
        for k, v in list(env.items()):
            if k.endswith("_ORIG"):
                continue
            if appdir in v and k not in ("APPDIR", "APPIMAGE", "OWD", "ARGV0"):
                parts = [p for p in v.split(":") if appdir not in p]
                if parts:
                    env[k] = ":".join(parts)
                else:
                    env.pop(k)
        for k, v in list(env.items()):
            if k.endswith("_ORIG"):
                env[k[:-5]] = v
    return env
