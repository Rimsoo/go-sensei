"""État de la séance d'étude : partie chargée, arbre des coups (partie + variantes),
analyses KataGo et annotations. Partagé entre le navigateur et l'IA (outils du plateau).

L'arbre : le nœud 0 est la position de départ, les nœuds 1..N sont les coups de la partie
(ligne principale, toujours premier enfant). Les variantes jouées par l'élève ou par
Sensei sont des branches supplémentaires, sauvegardées par partie avec leurs annotations."""

import json
import os
import threading
import time

from . import paths
from .katago import STOPPED
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


class Node:
    __slots__ = ("id", "parent", "move", "children", "source", "marks", "main")

    def __init__(self, nid, parent, move, source, main=False):
        self.id = nid
        self.parent = parent  # id du parent (None pour la racine)
        self.move = move  # (couleur, point) ; None pour la racine
        self.children = []  # ids ; le premier enfant est la suite principale
        self.source = source  # "game", "user" ou "sensei"
        self.marks = []
        self.main = main


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
        self.main = []  # [(couleur, point)] coups de la partie
        self.nodes = {}
        self.current = 0
        self.next_id = 0
        self.analyses = {}  # clé de position -> analyse détaillée (position affichée)
        self.node_evals = {}  # clé de position -> {"score", "winrate"} (graphique des variantes)
        self.live_qid = None
        self.line_qid = None
        self.review = None
        self.resuming = False
        self.on_load = None  # rappel(id de partie) quand une partie est ouverte

    def on_cpu(self):
        return self.engine.state.get("backend") in ("eigen", "eigenavx2")

    def live_visits(self):
        return self.cfg["katago"]["live_visits"] or live_visits(self.size, self.on_cpu())

    def review_visits(self):
        return self.cfg["katago"]["review_visits"] or review_visits(self.size, self.on_cpu())

    @property
    def size(self):
        return self.game["size"] if self.game else 9

    # ------------------------------------------------------------ arbre
    def path_ids(self, nid=None):
        nid = self.current if nid is None else nid
        out = []
        while nid is not None:
            out.append(nid)
            nid = self.nodes[nid].parent
        return out[::-1]

    def moves_of(self, nid=None):
        return [self.nodes[i].move for i in self.path_ids(nid)[1:]]

    def line_ids(self):
        """Ligne affichée : chemin jusqu'à la position actuelle, puis la suite (premiers enfants)."""
        ids = self.path_ids()
        n = self.nodes[ids[-1]]
        while n.children:
            n = self.nodes[n.children[0]]
            ids.append(n.id)
        return ids

    def main_ancestor(self, nid=None):
        """Dernier nœud de la partie réelle sur le chemin (point de départ de la variante)."""
        for i in reversed(self.path_ids(nid)):
            if self.nodes[i].main:
                return i
        return 0

    # Compatibilité avec les outils (cursor = coup de la partie, variation = coups ajoutés)
    @property
    def cursor(self):
        return self.main_ancestor()

    @property
    def variation(self):
        return self.moves_of()[self.cursor:]

    @property
    def marks(self):
        return self.nodes[self.current].marks if self.nodes else []

    def moves(self):
        return self.moves_of()

    def key(self, moves=None):
        moves = self.moves() if moves is None else moves
        return (self.game["id"] if self.game else "") + "|" + " ".join(
            f"{c}{to_gtp(p, self.size)}" for c, p in moves)

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

    # ------------------------------------------------------------ sauvegarde de l'arbre
    def _tree_path(self):
        return os.path.join(paths.TREE_DIR, f"{self.game['id']}.json")

    def save_tree(self):
        if not self.game:
            return
        data = {"next": self.next_id, "nodes": [], "marks": {}}
        for n in self.nodes.values():
            if not n.main:
                c, p = n.move
                data["nodes"].append({"id": n.id, "parent": n.parent, "c": c, "m": to_gtp(p, self.size),
                                      "src": n.source, "marks": n.marks})
            elif n.marks:
                data["marks"][str(n.id)] = n.marks
        try:
            tmp = self._tree_path() + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f)
            os.replace(tmp, self._tree_path())
        except OSError as e:
            self.log(f"Arbre : sauvegarde impossible ({e})")

    def _load_tree(self):
        try:
            with open(self._tree_path()) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        pending = data.get("nodes", [])
        # Les parents sont toujours créés avant leurs enfants, mais on reste robuste à l'ordre.
        for _ in range(len(pending) + 1):
            rest = []
            for d in pending:
                if d["parent"] not in self.nodes:
                    rest.append(d)
                    continue
                try:
                    move = (d["c"], from_gtp(d["m"], self.size))
                except (ValueError, KeyError):
                    continue
                n = Node(d["id"], d["parent"], move, d.get("src", "user"))
                n.marks = d.get("marks", [])
                self.nodes[n.id] = n
                self.nodes[d["parent"]].children.append(n.id)
            if not rest or len(rest) == len(pending):
                break
            pending = rest
        for nid, marks in data.get("marks", {}).items():
            if int(nid) in self.nodes:
                self.nodes[int(nid)].marks = marks
        self.next_id = max([self.next_id, data.get("next", 0)] + [i + 1 for i in self.nodes])

    # ------------------------------------------------------------ chargement
    def load_game(self, gid):
        g = self.lib.load(gid)
        with self.lock:
            self._stop_line_analysis()
            self.game = g
            self.main = g["moves"]
            self.nodes = {0: Node(0, None, None, "game", main=True)}
            for i, mv in enumerate(self.main, start=1):
                self.nodes[i] = Node(i, i - 1, mv, "game", main=True)
                self.nodes[i - 1].children.append(i)
            self.next_id = len(self.main) + 1
            self._load_tree()
            self.current = 0
            self.analyses = {}
            self.node_evals = {}
            self.review = None
        self.start_review()
        if self.on_load:
            self.on_load(g["id"])
        self.changed()
        return g

    # ------------------------------------------------------------ navigation
    def goto(self, n):
        """Position de la partie réelle après le coup n."""
        with self.lock:
            self.current = max(0, min(int(n), len(self.main)))
        self.changed()

    def goto_node(self, nid):
        with self.lock:
            nid = int(nid)
            if nid not in self.nodes:
                raise KeyError(f"position inconnue : {nid}")
            self.current = nid
        self.changed()

    def step(self, k):
        with self.lock:
            nid = self.current
            for _ in range(abs(int(k))):
                n = self.nodes[nid]
                if k < 0 and n.parent is not None:
                    nid = n.parent
                elif k > 0 and n.children:
                    nid = n.children[0]
            if nid == self.current:
                return
            self.current = nid
        self.changed()

    def sibling(self, d):
        """Passe à la variante voisine (même coup, autre branche)."""
        with self.lock:
            n = self.nodes[self.current]
            if n.parent is None:
                return
            sibs = self.nodes[n.parent].children
            i = sibs.index(n.id) + d
            if not 0 <= i < len(sibs):
                return
            self.current = sibs[i]
        self.changed()

    def back_to_main(self):
        with self.lock:
            self.current = self.main_ancestor()
        self.changed()

    def play(self, coords, source="user"):
        """Joue un ou plusieurs coups (GTP) depuis la position affichée. Un coup déjà présent
        dans l'arbre (partie ou variante) est simplement suivi ; sinon une branche est créée."""
        if isinstance(coords, str):
            coords = coords.replace(",", " ").split()
        played = []
        created = False
        with self.lock:
            for s in coords:
                pt = from_gtp(s, self.size)
                color = self.to_play()
                board = self.board_for(self.moves())
                board.play(color, pt)  # lève IllegalMove si illégal
                node = self.nodes[self.current]
                child = next((c for c in node.children if self.nodes[c].move == (color, pt)), None)
                if child is None:
                    child = self.next_id
                    self.next_id += 1
                    self.nodes[child] = Node(child, node.id, (color, pt), source)
                    node.children.append(child)
                    created = True
                self.current = child
                played.append(f"{'Noir' if color == 'B' else 'Blanc'} {to_gtp(pt, self.size)}")
        if created:
            self.save_tree()
        self.changed()
        return played

    def delete_node(self, nid):
        """Supprime une variante (le nœud et sa suite). La partie réelle ne peut pas être supprimée."""
        with self.lock:
            nid = int(nid)
            n = self.nodes.get(nid)
            if not n or n.main:
                raise ValueError("on ne peut supprimer que des variantes")
            stack, doomed = [nid], set()
            while stack:
                i = stack.pop()
                doomed.add(i)
                stack.extend(self.nodes[i].children)
            if self.current in doomed:
                self.current = n.parent
            self.nodes[n.parent].children.remove(nid)
            for i in doomed:
                del self.nodes[i]
        self.save_tree()
        self.changed()

    def set_marks(self, marks, replace=True):
        """Annotations de la position affichée (gardées avec elle dans l'arbre)."""
        with self.lock:
            node = self.nodes[self.current]
            if replace:
                node.marks = []
            for m in marks:
                pt = from_gtp(m["point"], self.size)
                if pt is None:
                    continue
                node.marks.append({"x": pt[0], "y": pt[1], "label": str(m.get("label", ""))[:3],
                                   "shape": m.get("shape", ""), "color": m.get("color", "")})
        self.save_tree()
        self.broadcast_state()

    def changed(self):
        self.start_live_analysis()
        self.start_line_analysis()
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
                if resp["error"] == STOPPED:
                    self._resume_after_restart()
                return
            a = self._parse(resp, moves)
            with self.lock:
                prev = self.analyses.get(key)
                if prev and prev["final"] and prev["visits"] >= a["visits"]:
                    return
                self.analyses[key] = a
                if a["final"]:
                    self.node_evals[key] = {"score": a["score"], "winrate": a["winrate"]}
                current = self.key() == key
            if current and (a["final"] or time.time() - last[0] > 0.5):
                last[0] = time.time()
                self.broadcast_state()

        self.live_qid = self.engine.query(q, cb)

    def _deferred_live(self):
        self.engine.ready.wait()
        self.start_live_analysis()

    def _resume_after_restart(self):
        """KataGo redémarre (réglages, nouveau réseau…) : on relance ce qui tournait."""
        if self.resuming:
            return
        self.resuming = True

        def run():
            self.engine.ready.wait()
            self.resuming = False
            self.start_live_analysis()
            self.start_line_analysis()
            if self.review and self.review["status"] == "interrupted" and self.game \
                    and self.review["gid"] == self.game["id"]:
                self.start_review()

        threading.Thread(target=run, daemon=True).start()

    def _stop_line_analysis(self):
        if self.line_qid:
            self.engine.terminate(self.line_qid)
            self.line_qid = None

    def start_line_analysis(self):
        """Évalue (rapidement) chaque coup des variantes de la ligne affichée, pour le graphique."""
        if not self.game:
            return
        with self.lock:
            self._stop_line_analysis()
            line = self.line_ids()
            moves = [self.nodes[i].move for i in line[1:]]
            turns, keys = [], {}
            for depth, nid in enumerate(line):
                if self.nodes[nid].main:
                    continue  # la revue de la partie couvre déjà la ligne principale
                k = self.key(moves[:depth])
                if k not in self.node_evals:
                    turns.append(depth)
                    keys[depth] = k
            if not turns:
                return
            q = dict(self.katago_base(moves), maxVisits=self.review_visits(), analyzeTurns=turns, priority=5)
        if not self.engine.ready.is_set():
            return
        last = [0.0]

        def cb(resp):
            if resp.get("error") == STOPPED:
                self._resume_after_restart()
            if "error" in resp or resp.get("isDuringSearch"):
                return
            ri = resp.get("rootInfo", {})
            k = keys.get(resp.get("turnNumber"))
            if k is None:
                return
            with self.lock:
                self.node_evals.setdefault(k, {"score": ri.get("scoreLead"), "winrate": ri.get("winrate")})
            if time.time() - last[0] > 0.4:
                last[0] = time.time()
                self.broadcast_state()

        self.line_qid = self.engine.query(q, cb)

    def analyze(self, moves=None, visits=None):
        """Analyse bloquante (pour l'IA). Réutilise l'analyse en direct si suffisante."""
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
            self.node_evals[key] = {"score": a["score"], "winrate": a["winrate"]}
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
        visits = self.review_visits()
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
            if not self.engine.ready.is_set():
                self.engine.ready.wait()
                # Moteur tout juste prêt : l'analyse en direct part d'abord, sinon la revue
                # occupe KataGo et la position affichée attend plusieurs secondes sur un CPU.
                time.sleep(0.5)
            if self.review is not review:
                return
            review["status"] = "running"
            self.broadcast_state()
            last = [0.0]

            def cb(resp):
                if resp.get("error") == STOPPED:
                    review["status"] = "interrupted"  # reprise au redémarrage du moteur
                    self._resume_after_restart()
                    return
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

    def _eval_of(self, nid):
        """Score (Noir) et meilleur coup d'une position, d'après ce qui est déjà calculé."""
        moves = self.moves_of(nid)
        depth = len(moves)
        score, best, pv = None, None, []
        if self.nodes[nid].main and self.review and depth in self.review["turns"]:
            t = self.review["turns"][depth]
            score, best, pv = t["score"], t["best"], t["pv"]
        a = self.analyses.get(self.key(moves))
        if a and a.get("moves"):
            best, pv = a["moves"][0]["move"], a["moves"][0]["pv"]
            score = a["score"] if a["score"] is not None else score
        if score is None:
            ev = self.node_evals.get(self.key(moves))
            score = ev["score"] if ev else None
        return score, best, pv

    def last_move_facts(self):
        """Ce que KataGo dit du dernier coup joué dans la position affichée."""
        node = self.nodes[self.current]
        if node.move is None:
            return None
        color, pt = node.move
        before, best, pv = self._eval_of(node.parent)
        after, _, _ = self._eval_of(node.id)
        facts = {"color": color, "move": to_gtp(pt, self.size), "number": len(self.moves_of()),
                 "best": best, "best_pv": pv[:6], "loss": None, "level": None}
        if before is not None and after is not None:
            loss = (before - after) * (1 if color == "B" else -1)
            facts["loss"] = round(loss, 1)
            facts["level"] = classify(loss) if facts["move"] != best else None
        return facts

    def describe_node(self, nid=None):
        """Libellé court d'une position, ex. « coup 17 » ou « variante après le coup 16 : E8 D7 »."""
        nid = self.current if nid is None else nid
        base = self.main_ancestor(nid)
        extra = self.moves_of(nid)[base:]
        if not extra:
            return f"coup {base}"
        seq = " ".join(to_gtp(p, self.size) for _, p in extra[:6]) + (" …" if len(extra) > 6 else "")
        return f"variante après le coup {base} : {seq}"

    # ------------------------------------------------------------ état client
    def _line_evals(self, line):
        """Score (point de vue Noir) de chaque position de la ligne affichée, ou None."""
        out = []
        turns = self.review["turns"] if self.review else {}
        moves = [self.nodes[i].move for i in line[1:]]
        for depth, nid in enumerate(line):
            e = None
            if self.nodes[nid].main:
                t = turns.get(depth)
                e = t["score"] if t else None
            if e is None:
                ev = self.node_evals.get(self.key(moves[:depth]))
                e = ev["score"] if ev else None
            out.append(e)
        return out

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
            line = self.line_ids()
            branch = next((d for d, nid in enumerate(line) if not self.nodes[nid].main), None)
            tree = []
            for n in self.nodes.values():
                c, p = n.move if n.move else (None, None)
                tree.append({"id": n.id, "parent": n.parent, "c": c,
                             "m": to_gtp(p, self.size) if n.move else None,
                             "src": n.source, "main": n.main, "kids": n.children, "marked": bool(n.marks)})
            cur = self.nodes[self.current]
            return {
                "game": {k: g.get(k) for k in ("id", "title", "black", "white", "black_rank", "white_rank",
                                               "size", "komi", "rules", "result", "source", "student", "date")},
                "engine": self.engine.describe(),
                "main": [to_gtp(p, self.size) for _, p in self.main],
                "mainColors": [c for c, _ in self.main],
                "cursor": self.cursor,
                "inVariation": not cur.main,
                "moveNumber": len(moves),
                "pathMoves": [[c, to_gtp(p, self.size)] for c, p in moves],
                "toPlay": self.to_play(moves),
                "stones": board.stones(),
                "last": [last[1][0], last[1][1]] if last and last[1] else None,
                "lastPass": bool(last and last[1] is None),
                "captures": board.captures,
                "marks": cur.marks,
                "analysis": a,
                "review": review,
                "tree": tree,
                "current": self.current,
                "line": line,
                "lineEvals": self._line_evals(line),
                "branch": branch,
                "nodeLabel": self.describe_node(),
            }

    def broadcast_state(self):
        self.broadcast("state", self.state())
