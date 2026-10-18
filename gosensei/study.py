"""État de la séance d'étude : partie chargée, position affichée, variantes,
analyses KataGo et annotations. Partagé entre le navigateur et Claude (MCP)."""

import json
import os
import threading
import time

from . import paths
from .board import Board, IllegalMove, from_gtp, other, to_gtp

# Seuils de perte (en points) pour classer les erreurs.
MISTAKE_LEVELS = [(8.0, "gaffe"), (4.0, "erreur"), (1.5, "imprécision")]


def classify(loss):
    for threshold, name in MISTAKE_LEVELS:
        if loss >= threshold:
            return name
    return None


def review_visits(size, cpu=False):
    v = 600 if size <= 9 else 400 if size <= 13 else 300
    return v // 3 if cpu else v


def live_visits(size, cpu=False):
    v = 3000 if size <= 9 else 2500 if size <= 13 else 2000
    return v // 6 if cpu else v


class Study:
    def __init__(self, library, engine, cfg, broadcast, log):
        self.lib = library
        self.engine = engine
        self.broadcast = broadcast
        self.log = log
        self.cfg = cfg
        self.review_dir = paths.REVIEW_DIR
        self.lock = threading.RLock()
        self.game = None
        self.main = []  # [(couleur, point)]
        self.cursor = 0
        self.variation = []
        self.marks = []
        self.analyses = {}  # clé de position -> analyse
        self.live_qid = None
        self.review = None
        self.review_gid = None

    def on_cpu(self):
        return self.engine.state.get("backend") in ("eigen", "eigenavx2")

    def live_visits(self):
        return self.cfg["katago"]["live_visits"] or live_visits(self.size, self.on_cpu())

    # ------------------------------------------------------------ positions
    def moves(self):
        return self.main[: self.cursor] + self.variation

    def key(self, moves=None):
        moves = self.moves() if moves is None else moves
        return (self.game["id"] if self.game else "") + "|" + " ".join(
            f"{c}{to_gtp(p, self.size)}" for c, p in moves)

    @property
    def size(self):
        return self.game["size"] if self.game else 9

    def board_for(self, moves):
        b = Board(self.size)
        for c in ("B", "W"):
            for p in self.game["setup"][c]:
                b.place(c, p)
        for c, p in moves:
            try:
                b.play(c, p)
            except IllegalMove:
                if p:
                    b.place(c, p)
        return b

    def to_play(self, moves=None):
        moves = self.moves() if moves is None else moves
        if moves:
            return other(moves[-1][0])
        return self.game.get("first_player") or "B"

    def katago_base(self, moves):
        return {
            "moves": [[c, to_gtp(p, self.size)] for c, p in moves],
            "initialStones": [[c, to_gtp(p, self.size)] for c in ("B", "W") for p in self.game["setup"][c]],
            "initialPlayer": self.game.get("first_player") or "B",
            "rules": self.game["rules"],
            "komi": self.game["komi"],
            "boardXSize": self.size,
            "boardYSize": self.size,
        }

    # ------------------------------------------------------------ chargement
    def load_game(self, gid):
        g = self.lib.load(gid)
        with self.lock:
            self.game = g
            self.main = g["moves"]
            self.cursor = 0
            self.variation = []
            self.marks = []
            self.analyses = {}
            self.review = None
        self.start_review()
        self.changed()
        return g

    # ------------------------------------------------------------ navigation
    def goto(self, n):
        with self.lock:
            self.cursor = max(0, min(int(n), len(self.main)))
            self.variation = []
        self.changed()

    def step(self, k):
        with self.lock:
            if k < 0 and self.variation:
                drop = min(-k, len(self.variation))
                self.variation = self.variation[: len(self.variation) - drop]
                k += drop
                if k == 0:
                    self.changed()
                    return
            if self.variation and k > 0:
                return
            self.cursor = max(0, min(self.cursor + k, len(self.main)))
        self.changed()

    def back_to_main(self):
        with self.lock:
            self.variation = []
        self.changed()

    def play(self, coords):
        """Joue un ou plusieurs coups (GTP) depuis la position affichée.
        Si le coup est celui de la partie, on avance simplement dans la partie."""
        if isinstance(coords, str):
            coords = coords.replace(",", " ").split()
        played = []
        with self.lock:
            for s in coords:
                pt = from_gtp(s, self.size)
                color = self.to_play()
                board = self.board_for(self.moves())
                board.play(color, pt)  # lève IllegalMove si illégal
                if not self.variation and self.cursor < len(self.main) and self.main[self.cursor] == (color, pt):
                    self.cursor += 1
                else:
                    self.variation.append((color, pt))
                played.append(f"{'Noir' if color == 'B' else 'Blanc'} {to_gtp(pt, self.size)}")
        self.changed()
        return played

    def set_marks(self, marks, replace=True):
        with self.lock:
            if replace:
                self.marks = []
            for m in marks:
                pt = from_gtp(m["point"], self.size)
                if pt is None:
                    continue
                self.marks.append({"x": pt[0], "y": pt[1], "label": str(m.get("label", ""))[:3],
                                   "shape": m.get("shape", ""), "color": m.get("color", "")})
        self.broadcast_state()

    def changed(self):
        with self.lock:
            self.marks = []
        self.start_live_analysis()
        self.broadcast_state()

    # ------------------------------------------------------------ analyse
    def _parse(self, resp, moves):
        ri = resp.get("rootInfo", {})
        out = {
            "key": self.key(moves),
            "visits": ri.get("visits", 0),
            "winrate": ri.get("winrate"),  # point de vue Noir
            "score": ri.get("scoreLead"),  # point de vue Noir
            "toPlay": self.to_play(moves),
            "moves": [],
            "ownership": resp.get("ownership"),
            "final": not resp.get("isDuringSearch", False),
        }
        for mi in sorted(resp.get("moveInfos", []), key=lambda m: m.get("order", 99)):
            out["moves"].append({
                "move": mi["move"],
                "visits": mi.get("visits", 0),
                "winrate": mi.get("winrate"),
                "score": mi.get("scoreLead"),
                "prior": mi.get("prior"),
                "pv": mi.get("pv", [])[:12],
                "order": mi.get("order"),
            })
        return out

    def start_live_analysis(self):
        if not self.game:
            return
        with self.lock:
            moves = self.moves()
            key = self.key(moves)
            if self.live_qid:
                self.engine.terminate(self.live_qid)
                self.live_qid = None
            cached = self.analyses.get(key)
            if cached and cached["final"]:
                return
            q = dict(self.katago_base(moves), maxVisits=self.live_visits(), includeOwnership=True,
                     reportDuringSearchEvery=0.6, priority=10)
        if not self.engine.ready.is_set():
            threading.Thread(target=self._deferred_live, daemon=True).start()
            return
        last = [0.0]

        def cb(resp):
            if "error" in resp:
                return
            a = self._parse(resp, moves)
            with self.lock:
                prev = self.analyses.get(key)
                if prev and prev["final"] and prev["visits"] >= a["visits"]:
                    return
                self.analyses[key] = a
                current = self.key() == key
            if current and (a["final"] or time.time() - last[0] > 0.5):
                last[0] = time.time()
                self.broadcast_state()

        self.live_qid = self.engine.query(q, cb)

    def _deferred_live(self):
        self.engine.ready.wait()
        self.start_live_analysis()

    def analyze(self, moves=None, visits=None):
        """Analyse bloquante (pour Claude). Réutilise l'analyse en direct si suffisante."""
        moves = self.moves() if moves is None else moves
        visits = visits or self.live_visits()
        key = self.key(moves)
        a = self.analyses.get(key)
        if a and a["final"] and a["visits"] >= visits * 0.9:
            return a
        resp = self.engine.query_sync(dict(self.katago_base(moves), maxVisits=visits,
                                           includeOwnership=True, priority=20))
        a = self._parse(resp, moves)
        with self.lock:
            prev = self.analyses.get(key)
            if not prev or prev["visits"] <= a["visits"]:
                self.analyses[key] = a
        if key == self.key():
            self.broadcast_state()
        return a

    def evaluate(self, candidates, visits=400):
        """Évalue précisément des coups candidats depuis la position affichée."""
        moves = self.moves()
        color = self.to_play(moves)
        out = []
        for s in candidates:
            pt = from_gtp(s, self.size)
            gtp = to_gtp(pt, self.size)
            try:
                self.board_for(moves).play(color, pt)
            except IllegalMove as e:
                out.append({"move": gtp, "illegal": str(e)})
                continue
            q = dict(self.katago_base(moves), maxVisits=visits, priority=20,
                     allowMoves=[{"player": color, "moves": [gtp], "untilDepth": 1}])
            resp = self.engine.query_sync(q)
            mi = (resp.get("moveInfos") or [{}])[0]
            out.append({"move": gtp, "winrate": mi.get("winrate"), "score": mi.get("scoreLead"),
                        "visits": mi.get("visits"), "pv": mi.get("pv", [])[:10]})
        return color, out

    # ------------------------------------------------------------ revue complète
    def _review_path(self, gid):
        return os.path.join(self.review_dir, f"{gid}.json")

    def start_review(self):
        g = self.game
        gid = g["id"]
        n = len(self.main)
        visits = self.cfg["katago"]["review_visits"] or review_visits(self.size, self.on_cpu())
        path = self._review_path(gid)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    saved = json.load(f)
                if saved.get("moves") == n and saved.get("visits") >= visits:
                    turns = {int(k): v for k, v in saved["turns"].items()}
                    self.review = {"gid": gid, "status": "done", "turns": turns, "total": n + 1}
                    return
            except Exception:
                pass
        self.review = {"gid": gid, "status": "waiting", "turns": {}, "total": n + 1}
        review = self.review

        def run():
            self.engine.ready.wait()
            if self.review is not review:
                return
            review["status"] = "running"
            self.broadcast_state()
            last = [0.0]

            def cb(resp):
                if "error" in resp:
                    review["status"] = "error"
                    self.log(f"Revue : {resp['error']}")
                    return
                if resp.get("isDuringSearch"):
                    return
                t = resp["turnNumber"]
                ri = resp.get("rootInfo", {})
                best = sorted(resp.get("moveInfos", []), key=lambda m: m.get("order", 99))
                review["turns"][t] = {
                    "winrate": ri.get("winrate"), "score": ri.get("scoreLead"),
                    "best": best[0]["move"] if best else None,
                    "pv": best[0].get("pv", [])[:8] if best else [],
                    "alts": [{"move": m["move"], "score": m.get("scoreLead")} for m in best[:4]],
                }
                if len(review["turns"]) >= review["total"]:
                    review["status"] = "done"
                    with open(path, "w") as f:
                        json.dump({"moves": n, "visits": visits, "turns": review["turns"]}, f)
                    self.engine.forget(qid)
                    self.broadcast_state()
                elif time.time() - last[0] > 1.0:
                    last[0] = time.time()
                    self.broadcast_state()

            q = dict(self.katago_base(self.main), maxVisits=visits, analyzeTurns=list(range(n + 1)), priority=0)
            qid = self.engine.query(q, cb)

        threading.Thread(target=run, daemon=True).start()

    def mistakes(self):
        """Liste des erreurs de la partie (ligne principale) d'après la revue."""
        r = self.review
        if not r:
            return []
        out = []
        turns = r["turns"]
        for i, (color, pt) in enumerate(self.main):
            a, b = turns.get(i), turns.get(i + 1)
            if not a or not b or a["score"] is None or b["score"] is None:
                continue
            sign = 1 if color == "B" else -1
            loss = (a["score"] - b["score"]) * sign
            wr_loss = (a["winrate"] - b["winrate"]) * sign
            level = classify(loss)
            played = to_gtp(pt, self.size)
            out.append({"move_number": i + 1, "color": color, "played": played, "loss": round(loss, 1),
                        "winrate_loss": round(wr_loss * 100, 1), "best": a["best"],
                        "best_pv": a["pv"], "level": level if played != a["best"] else None})
        return out

    # ------------------------------------------------------------ état client
    def state(self):
        with self.lock:
            if not self.game:
                return {"game": None, "engine": self.engine.describe()}
            moves = self.moves()
            board = self.board_for(moves)
            g = self.game
            last = moves[-1] if moves else None
            review = None
            if self.review:
                r = self.review
                review = {
                    "status": r["status"],
                    "done": len(r["turns"]),
                    "total": r["total"],
                    "curve": [[t, v["winrate"], v["score"]] for t, v in sorted(r["turns"].items())],
                    "mistakes": [m for m in self.mistakes() if m["level"]],
                }
            a = self.analyses.get(self.key(moves))
            return {
                "game": {k: g.get(k) for k in ("id", "title", "black", "white", "black_rank", "white_rank",
                                               "size", "komi", "rules", "result", "source", "student", "date")},
                "engine": self.engine.describe(),
                "main": [to_gtp(p, self.size) for _, p in self.main],
                "mainColors": [c for c, _ in self.main],
                "cursor": self.cursor,
                "variation": [[c, to_gtp(p, self.size)] for c, p in self.variation],
                "moveNumber": len(moves),
                "toPlay": self.to_play(moves),
                "stones": board.stones(),
                "last": [last[1][0], last[1][1]] if last and last[1] else None,
                "lastPass": bool(last and last[1] is None),
                "captures": board.captures,
                "marks": self.marks,
                "analysis": a,
                "review": review,
            }

    def broadcast_state(self):
        self.broadcast("state", self.state())
