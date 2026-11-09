"""Goban physique via IgOGS (driver caméra, https://forgejo.aaaoz.fr/Rimso/IgOGS).

Quand la liaison est active, Go Sensei indique à IgOGS la position affichée (POST /api/claim) :
IgOGS dit alors au joueur quoi poser ou retirer sur son goban. Les coups joués sur le goban
arrivent en retour (événements SSE) et sont joués ici comme un clic sur le plateau ; retirer les
dernières pierres revient en arrière.
"""

import json
import threading
import time
import urllib.error
import urllib.request

from .board import to_gtp
from .i18n import tr

OWNER = "go-sensei"


class GobanLink:
    def __init__(self, cfg, study, broadcast, log):
        self.cfg = cfg
        self.study = study
        self.broadcast = broadcast
        self.log = log
        self.connected = False
        self.board = None  # dernier état de la partie suivie par IgOGS
        self.error = ""
        self._claim_due = threading.Event()
        self._stop = threading.Event()
        threading.Thread(target=self._events_loop, daemon=True, name="goban-events").start()
        threading.Thread(target=self._claim_loop, daemon=True, name="goban-claim").start()

    @property
    def enabled(self):
        return bool(self.cfg["goban"]["enabled"])

    @property
    def url(self):
        return self.cfg["goban"]["url"].rstrip("/")

    def stop(self):
        self._stop.set()
        self._claim_due.set()

    # ------------------------------------------------------------ état pour l'interface
    def state(self):
        b = self.board or {}
        mine = b.get("owner") == OWNER
        return {
            "enabled": self.enabled,
            "connected": self.connected,
            "mine": mine,
            "status": (b.get("sync") or {}).get("status", "unknown") if mine else None,
            "message": self._message() if self.enabled else "",
            "error": self.error,
        }

    def _message(self):
        if not self.connected:
            return tr("IgOGS ne répond pas : lancez-le (caméra du goban)")
        b = self.board or {}
        if b.get("owner") != OWNER:
            return tr("Goban utilisé par {owner}", owner=b.get("owner", "?"))
        sync = b.get("sync") or {}
        status = sync.get("status")
        color = {"B": tr("Noir"), "W": tr("Blanc")}
        if status == "ok":
            return tr("Goban synchronisé")
        if status == "unknown":
            return tr("En attente de la caméra")
        if status == "remove-captured":
            return tr("Retirez les pierres prises : {pts}", pts=", ".join(p for p, _ in sync.get("extra", [])))
        parts = []
        for c in ("B", "W"):
            pts = [p for p, cc in sync.get("missing", []) if cc == c]
            if pts:
                parts.append(tr("posez {color} en {pts}", color=color[c], pts=", ".join(pts)))
        if sync.get("extra"):
            parts.append(tr("retirez {pts}", pts=", ".join(p for p, _ in sync["extra"])))
        msg = " · ".join(parts)
        return msg[:1].upper() + msg[1:]

    def _notify(self):
        self.broadcast("goban", self.state())

    # ------------------------------------------------------------ commandes
    def set_enabled(self, on):
        self.cfg.update({"goban": {"enabled": bool(on)}})
        self.error = ""
        if on:
            self.position_changed()
        else:
            try:
                self._post("/api/release", {"owner": OWNER})
            except Exception:
                pass
        self._notify()
        return self.state()

    def position_changed(self):
        """Appelé à chaque changement de position affichée dans Go Sensei."""
        if self.enabled:
            self._claim_due.set()

    # ------------------------------------------------------------ HTTP vers IgOGS
    def _post(self, path, body):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-IgOGS": "1"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read() or b"{}").get("error")
            except ValueError:
                msg = None
            raise ValueError(msg or f"HTTP {e.code}")

    def _claim_body(self):
        s = self.study
        with s.lock:
            if not s.game:
                return None
            size = s.size
            g = s.game
            return {
                "owner": OWNER,
                "size": size,
                "setup": {c: [to_gtp(p, size) for p in g["setup"][c]] for c in ("B", "W")},
                "first": g.get("first_player") or "B",
                "moves": [[c, to_gtp(p, size)] for c, p in s.moves()],
                "camera_colors": ["B", "W"],
                "autoplay": True,
                "allow_undo": True,
                "info": {"PB": g.get("black", ""), "PW": g.get("white", "")},
            }

    def _claim_loop(self):
        while not self._stop.is_set():
            self._claim_due.wait()
            self._claim_due.clear()
            if self._stop.is_set():
                break
            if not (self.enabled and self.connected):
                continue
            time.sleep(0.05)  # regroupe les changements rapprochés (navigation au clavier)
            body = self._claim_body()
            if body is None:
                continue
            try:
                r = self._post("/api/claim", body)
                self.board = r.get("board") or self.board
                self.error = ""
            except (ValueError, OSError) as e:
                self.error = str(e)
                self.log(f"Goban : {e}")
            self._notify()

    # ------------------------------------------------------------ événements d'IgOGS
    def _events_loop(self):
        while not self._stop.is_set():
            if not self.enabled:
                self._stop.wait(1)
                continue
            try:
                with urllib.request.urlopen(self.url + "/events", timeout=30) as resp:
                    self.connected = True
                    self._claim_due.set()
                    self._read_events(resp)
            except (urllib.error.URLError, OSError, ValueError):
                pass
            if self.connected:
                self.connected = False
                self._notify()
            self._stop.wait(3)

    def _read_events(self, resp):
        kind, data = None, []
        for raw in resp:
            if self._stop.is_set() or not self.enabled:
                return
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if line.startswith("event:"):
                kind = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
            elif not line:
                if kind and data:
                    try:
                        self._on_event(kind, json.loads("\n".join(data)))
                    except Exception as e:
                        self.log(f"Goban : événement {kind} non traité ({e!r})")
                kind, data = None, []

    def _on_event(self, kind, d):
        if kind == "state":
            self.board = d.get("board")
            self._notify()
        elif kind in ("game", "observed"):
            self.board = d
            self._notify()
        elif kind == "move" and d.get("owner") == OWNER and d.get("applied"):
            try:
                # Partie contre KataGo : le coup posé au bout de la partie est un coup de la partie
                # (comme un clic sur le plateau), pas une variante.
                match = self.study.match
                if not (match and match.user_move(d["move"])):
                    self.study.play([d["move"]])
            except Exception as e:  # position modifiée entre-temps : IgOGS se resynchronise
                self.log(f"Goban : coup {d['move']} non joué ({e})")
                self._claim_due.set()
        elif kind == "undo" and d.get("owner") == OWNER:
            self.study.step(-int(d.get("count", 1)))
