"""Configuration persistante (~/.config/go-sensei/config.json)."""

import copy
import glob
import json
import os
import shutil

from . import paths

DEFAULTS = {
    "port": 8765,
    "open_window": True,
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
        "api_key": "",
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
        self.save()

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
        d = copy.deepcopy(self.data)
        key = d["ai"].get("api_key") or ""
        d["ai"]["api_key"] = ""
        d["ai"]["has_api_key"] = bool(key)
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
