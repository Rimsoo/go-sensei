"""Bibliothèque de parties : OGS, fichiers SGF importés, dossiers locaux et
(optionnellement) The Conquest of Go."""

import datetime
import glob
import hashlib
import json
import os
import re
import threading
import urllib.parse
import urllib.request

from . import paths
from .sgf import parse_sgf

OGS = "https://online-go.com"
UA = {"User-Agent": "GoSensei (outil d'étude personnel)"}

CONQUEST_FOLDERS = {
    "Recent Matches": "Conquest · récentes",
    "Saved Matches": "Conquest · sauvegardées",
    "Campaign Match Records": "Conquest · campagne",
    "Imported Content": "Conquest · importées",
}

AI_NAMES = re.compile(r"\b(ai|ia|katago|gnugo|bot)\b", re.I)


def _http_json(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _http_text(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _parse_date(g, path):
    """Date de la partie (timestamp) : nom de fichier horodaté, propriété DT, sinon date du fichier."""
    m = re.search(r"(20\d\d)(\d\d)(\d\d)-(\d\d)(\d\d)(\d\d)", os.path.basename(path))
    if m:
        try:
            return datetime.datetime(*map(int, m.groups())).timestamp()
        except ValueError:
            pass
    dt = (g.get("date") or "").split(",")[0].strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%Y-%m"):
        try:
            return datetime.datetime.strptime(dt, fmt).timestamp()
        except ValueError:
            continue
    return os.path.getmtime(path)


def _outcome(result, student):
    """'win' / 'loss' / None du point de vue de l'élève."""
    if not student or not result or result[0] not in "BW":
        return None
    return "win" if result[0] == student else "loss"


class Library:
    def __init__(self, cfg, log=print):
        self.cfg = cfg
        self.log = log
        self._cache = {}  # chemin -> (mtime, taille, entrée)
        self.sync_lock = threading.Lock()

    @property
    def ogs_username(self):
        return self.cfg["ogs"]["username"]

    # ------------------------------------------------------------ inventaire
    def _sources(self):
        """Liste de (motif glob, source, libellé)."""
        out = [(os.path.join(paths.OGS_DIR, "*.sgf"), "ogs", "OGS"),
               (os.path.join(paths.IMPORT_DIR, "*.sgf"), "import", "Importées")]
        conquest = self.cfg.conquest_dir()
        if conquest:
            for folder, label in CONQUEST_FOLDERS.items():
                out.append((os.path.join(conquest, folder, "**", "*.sgf"), "conquest", label))
        for folder in self.cfg["sources"]["folders"]:
            if folder and os.path.isdir(os.path.expanduser(folder)):
                out.append((os.path.join(os.path.expanduser(folder), "**", "*.sgf"), "folder",
                            os.path.basename(os.path.normpath(folder))))
        return out

    def student_color(self, g, source):
        """Devine quelle couleur est l'élève (l'humain)."""
        u = (self.ogs_username or "").lower()
        if u:
            if g["black"].lower() == u:
                return "B"
            if g["white"].lower() == u:
                return "W"
        b_ai, w_ai = bool(AI_NAMES.search(g["black"])), bool(AI_NAMES.search(g["white"]))
        if b_ai and not w_ai:
            return "W"
        if w_ai and not b_ai:
            return "B"
        return None

    def _entry(self, path, source, label):
        try:
            st = os.stat(path)
        except OSError:
            return None
        cached = self._cache.get(path)
        if cached and cached[0] == st.st_mtime and cached[1] == st.st_size:
            return cached[2]
        try:
            with open(path, "rb") as f:
                raw = f.read()
            g = parse_sgf(raw.decode("utf-8", "replace"))
        except Exception:
            return None
        played = _parse_date(g, path)
        meta_path = path[:-4] + ".json"
        if os.path.exists(meta_path):  # métadonnées OGS (date de fin exacte, classement)
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                if meta.get("ended"):
                    played = datetime.datetime.fromisoformat(meta["ended"].replace("Z", "+00:00")).timestamp()
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        student = self.student_color(g, source)
        e = {
            "id": hashlib.sha1(raw).hexdigest()[:12],
            "path": path,
            "source": source,
            "folder": label,
            "black": g["black"], "white": g["white"],
            "black_rank": g["black_rank"], "white_rank": g["white_rank"],
            "size": g["size"],
            "moves": len(g["moves"]),
            "result": g["result"],
            "played": played,
            "student": student,
            "outcome": _outcome(g["result"], student),
        }
        self._cache[path] = (st.st_mtime, st.st_size, e)
        return e

    def list(self):
        out, seen = [], set()
        for pattern, source, label in self._sources():
            for p in glob.glob(pattern, recursive=True):
                e = self._entry(p, source, label)
                if e and e["id"] not in seen:
                    seen.add(e["id"])
                    out.append(e)
        out.sort(key=lambda e: e["played"], reverse=True)
        return out

    def get(self, gid):
        return next((e for e in self.list() if e["id"] == gid), None)

    def load(self, gid):
        e = self.get(gid)
        if not e:
            raise KeyError(f"partie inconnue : {gid}")
        with open(e["path"], encoding="utf-8", errors="replace") as f:
            g = parse_sgf(f.read())
        title = f"{g['black']} vs {g['white']}"
        g.update(id=gid, source=e["source"], folder=e["folder"], student=e["student"], title=title,
                 played=e["played"])
        return g

    # ------------------------------------------------------------ import de fichiers
    def import_sgf(self, text, name="partie"):
        parse_sgf(text)  # valide le contenu (lève une erreur si illisible)
        safe = re.sub(r"[^\w.-]+", "_", os.path.splitext(name)[0])[:60] or "partie"
        gid = hashlib.sha1(text.encode()).hexdigest()[:12]
        path = os.path.join(paths.IMPORT_DIR, f"{safe}-{gid[:6]}.sgf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return self._entry(path, "import", "Importées")["id"]

    # ------------------------------------------------------------ OGS
    def ogs_find_player(self, name):
        """Recherche insensible à la casse ('rimseau' trouve 'Rimseau')."""
        data = _http_json(f"{OGS}/api/v1/ui/omniSearch?q={urllib.parse.quote(name)}")
        players = data.get("players") or []
        exact = [p for p in players if p["username"].lower() == name.lower()]
        if exact:
            return exact[0]
        if players:
            raise ValueError(f"joueur OGS introuvable : {name} (vouliez-vous dire {', '.join(p['username'] for p in players[:3])} ?)")
        raise ValueError(f"joueur OGS introuvable : {name}")

    def _ogs_save(self, gid, meta=None):
        path = os.path.join(paths.OGS_DIR, f"ogs-{gid}.sgf")
        new = not os.path.exists(path)
        if new:
            sgf = _http_text(f"{OGS}/api/v1/games/{gid}/sgf")
            if "(;" not in sgf:
                raise ValueError(f"OGS n'a pas renvoyé de SGF pour la partie {gid}")
            with open(path, "w", encoding="utf-8") as f:
                f.write(sgf)
        meta_path = path[:-4] + ".json"
        if meta is None and not os.path.exists(meta_path):
            try:
                meta = _http_json(f"{OGS}/api/v1/games/{gid}")
            except Exception:
                meta = None
        if meta:
            keep = {k: meta.get(k) for k in ("id", "name", "ended", "started", "ranked", "outcome", "width")}
            with open(meta_path, "w") as f:
                json.dump(keep, f)
        return path, new

    def ogs_import_game(self, game_id):
        path, _ = self._ogs_save(int(game_id))
        return self._entry(path, "ogs", "OGS")["id"]

    def ogs_sync(self, username=None, count=None):
        """Importe les parties terminées d'un joueur (les `count` plus récentes, 0 = toutes).
        Retourne (pseudo exact, nb nouvelles)."""
        username = username or self.ogs_username
        if not username:
            raise ValueError("aucun pseudo OGS configuré")
        count = int(count if count is not None else self.cfg["ogs"]["sync_count"] or 0) or float("inf")
        with self.sync_lock:
            player = self.ogs_find_player(username)
            url = f"{OGS}/api/v1/players/{player['id']}/games/?ordering=-ended&page_size=50"
            new = 0
            seen = 0
            while url and seen < count:
                data = _http_json(url)
                for g in data.get("results", []):
                    if seen >= count:
                        break
                    if not g.get("ended") or g.get("annulled"):
                        continue
                    seen += 1
                    try:
                        _, is_new = self._ogs_save(g["id"], g)
                        new += is_new
                    except Exception as e:
                        self.log(f"OGS : partie {g['id']} ignorée ({e})")
                url = data.get("next")
            return player["username"], new

    def ogs_import(self, text):
        """Lien de partie OGS, numéro de partie, ou pseudo (synchronise ses parties)."""
        text = text.strip()
        m = re.search(r"online-go\.com/(?:game|review)/(?:view/)?(\d+)", text)
        if m or text.isdigit():
            return {"username": None, "new": 1, "first": self.ogs_import_game(m.group(1) if m else text)}
        username, new = self.ogs_sync(text)
        return {"username": username, "new": new, "first": None}
