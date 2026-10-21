"""Configuration persistante (~/.config/go-sensei/config.json)."""

import copy
import glob
import json
import os
import shutil

from . import paths

DEFAULTS = {
    "port": 8765,
    "open_window": True,        # ouvrir l'interface au lancement
    "launch": {
        "mode": "browser",      # browser = navigateur par défaut ; app = fenêtre Chromium dédiée
        "background": True,     # continuer quand la fenêtre est fermée (icône de notification)
        "tray": True,           # icône dans la zone de notification
        "autostart": False,     # lancer avec la session (en arrière-plan)
    },
    "katago": {
        "backend": "auto",      # auto | gpu | cpu
        "binary": "",           # chemin d'un KataGo personnel (optionnel)
        "model": "",            # chemin d'un réseau .bin.gz personnel (optionnel)
        "live_visits": 0,       # 0 = automatique selon la taille du plateau
        "review_visits": 0,
    },
    "sources": {
        "conquest": "auto",     # auto = détection, "" = désactivé, sinon chemin
        "folders": [],          # autres dossiers de fichiers SGF
    },
    "ogs": {"username": "", "sync_count": 30, "auto_sync": True},
    "ai": {
        "provider": "none",     # none | claude-code | anthropic | openai
        "preset": "",           # pour openai : openai, deepseek, ollama, openrouter, mistral, gemini, custom
        "model": "",
        "api_key": "",          # obsolète : remplacé par api_keys (une clé par service)
        "api_keys": {},         # "anthropic", "openai", "deepseek", "mistral"… -> clé
        "base_url": "",
    },
}

STEAM_ROOTS = ["~/.local/share/Steam", "~/.steam/steam", "~/steam",
               "~/.var/app/com.valvesoftware.Steam/.local/share/Steam"]
CONQUEST_APPID = "1264970"


def detect_conquest():
    """Dossier de sauvegarde de The Conquest of Go (Steam + Proton), s'il existe."""
    for root in STEAM_ROOTS:
        root = os.path.expanduser(root)
        found = glob.glob(f"{root}/steamapps/compatdata/{CONQUEST_APPID}/pfx/drive_c/users/steamuser/AppData/"
                          f"LocalLow/Wolfey Studios/The Conquest of Go/[0-9]*")
        if found:
            return found[0]
    return ""


def detect_conquest_model():
    """Réseau KataGo fourni avec le jeu (évite un téléchargement de 100 Mo)."""
    for root in STEAM_ROOTS:
        p = os.path.join(os.path.expanduser(root), "steamapps/common/The Conquest of Go/The Conquest of Go_Data/"
                         "StreamingAssets/KataGo/Models/b18.bin.gz")
        if os.path.isfile(p):
            return p
    return ""


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self):
        paths.ensure_dirs()
        first_run = not os.path.exists(paths.CONFIG_FILE)
        data = {}
        if not first_run:
            try:
                with open(paths.CONFIG_FILE, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                data = {}
        self.data = _merge(DEFAULTS, data)
        if first_run:
            self._first_run()
        self._migrate_api_key()
        self.save()

    def _migrate_api_key(self):
        """Ancienne clé unique -> clé du service actuellement choisi."""
        from .ai import key_slot
        ai = self.data["ai"]
        if ai.get("api_key"):
            slot = key_slot(ai)
            if slot:
                ai["api_keys"].setdefault(slot, ai["api_key"])
            ai["api_key"] = ""

    def _first_run(self):
        # Claude Code installé : on l'active par défaut, sinon l'IA reste désactivée.
        if shutil.which("claude"):
            self.data["ai"]["provider"] = "claude-code"
        migrate_legacy(self)

    def __getitem__(self, k):
        return self.data[k]

    def save(self):
        tmp = paths.CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.chmod(tmp, 0o600)  # peut contenir des clés d'API
        os.replace(tmp, paths.CONFIG_FILE)

    def update(self, patch):
        self.data = _merge(self.data, patch)
        self.save()

    def conquest_dir(self):
        c = self.data["sources"]["conquest"]
        if c == "auto":
            return detect_conquest()
        return c if c and os.path.isdir(c) else ""

    def public(self):
        """Configuration envoyée au navigateur (clé d'API masquée)."""
        from .ai import key_slot
        d = copy.deepcopy(self.data)
        keys = d["ai"].pop("api_keys", {}) or {}
        d["ai"]["api_key"] = ""
        d["ai"]["has_api_key"] = bool(keys.get(key_slot(d["ai"]) or ""))
        d["ai"]["key_slots"] = sorted(k for k, v in keys.items() if v)  # services ayant une clé
        d["detected"] = {"conquest": detect_conquest(), "claude_cli": bool(shutil.which("claude"))}
        return d


def migrate_legacy(cfg):
    """Reprend les données de la toute première version (~/Documents/go-sensei/data)."""
    old = os.path.expanduser("~/Documents/go-sensei/data")
    if not os.path.isdir(old):
        return
    for name, dest in (("ogs", paths.OGS_DIR), ("reviews", paths.REVIEW_DIR)):
        src = os.path.join(old, name)
        if os.path.isdir(src):
            for f in os.listdir(src):
                if not os.path.exists(os.path.join(dest, f)):
                    shutil.copy2(os.path.join(src, f), dest)
    notes = os.path.join(old, "carnet-eleve.md")
    if os.path.isfile(notes) and not os.path.exists(paths.NOTES_FILE):
        shutil.copy2(notes, paths.NOTES_FILE)
    legacy_cfg = os.path.expanduser("~/Documents/go-sensei/config.json")
    try:
        with open(legacy_cfg) as f:
            old_cfg = json.load(f)
        if old_cfg.get("ogs_username"):
            cfg.data["ogs"]["username"] = old_cfg["ogs_username"]
        if old_cfg.get("coach_model"):
            cfg.data["ai"]["model"] = old_cfg["coach_model"]
    except (OSError, json.JSONDecodeError):
        pass


AUTOSTART_FILE = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                              "autostart", "go-sensei.desktop")


def launch_command():
    """Commande pour relancer Go Sensei (AppImage si on en vient, sinon les sources)."""
    import sys
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return f'"{appimage}"'
    root = os.path.dirname(paths.PKG)
    return f'{sys.executable} "{os.path.join(root, "go-sensei.py")}"'


def set_autostart(enabled):
    """Démarrage avec la session : fichier .desktop dans ~/.config/autostart (norme XDG)."""
    if not enabled:
        try:
            os.remove(AUTOSTART_FILE)
        except OSError:
            pass
        return
    os.makedirs(os.path.dirname(AUTOSTART_FILE), exist_ok=True)
    with open(AUTOSTART_FILE, "w") as f:
        f.write("[Desktop Entry]\nType=Application\nName=Go Sensei\n"
                "Comment=Go Sensei en arrière-plan (icône dans la zone de notification)\n"
                f"Exec={launch_command()} --no-window\nIcon=go-sensei\nTerminal=false\n"
                "X-GNOME-Autostart-enabled=true\n")
