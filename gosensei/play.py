"""Partie contre KataGo, sur le PC.

Les niveaux humains utilisent le réseau « humain » de KataGo : il prédit le coup que jouerait un
joueur d'un rang donné, et on tire le coup au hasard selon ces probabilités (le bot fait donc les
erreurs typiques de son niveau). Le niveau maximal est KataGo lui-même.

La partie est un SGF dans paths.LOCAL_DIR, réécrit à chaque coup, avec à côté un .json qui garde
les options (niveau, couleur de l'élève, aides) : une partie non terminée reprend à sa réouverture."""

import json
import os
import random
import threading
import time

from . import paths
from .board import IllegalMove, from_gtp, other, to_gtp
from .i18n import tr
from .sgf import write_sgf

# (profil KataGo, libellé) du plus faible au plus fort
LEVELS = [
    ("rank_20k", "20 kyu"), ("rank_15k", "15 kyu"), ("rank_10k", "10 kyu"), ("rank_5k", "5 kyu"),
    ("rank_1k", "1 kyu"), ("rank_3d", "3 dan"), ("rank_9d", "9 dan"), ("max", "KataGo (maximum)"),
]
LEVEL_NAMES = dict(LEVELS)
RANKS = {k: k.removeprefix("rank_") for k, _ in LEVELS if k != "max"}
MAX_VISITS = 1000  # niveau maximal : déjà imbattable, et le coup arrive vite


class Match:
    def __init__(self, cfg, lib, study, engine, log):
        self.cfg = cfg
        self.lib = lib
        self.study = study
        self.engine = engine
        self.log = log
        self.gid = None
        self.meta = None
        self.thinking = False
        self.message = ""
        self.lock = threading.Lock()

    # ------------------------------------------------------------ fichiers
    @staticmethod
    def _path(gid, ext):
        return os.path.join(paths.LOCAL_DIR, f"{gid}.{ext}")

    def _save(self):
        s = self.study
        g = dict(s.game, moves=s.main, result=self.meta.get("result", ""))
        tmp = self._path(self.gid, "sgf.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(write_sgf(g))
        os.replace(tmp, self._path(self.gid, "sgf"))
        with open(self._path(self.gid, "json"), "w") as f:
            json.dump(self.meta, f)

    # ------------------------------------------------------------ état
    def active(self):
        """La partie contre KataGo est celle qui est ouverte."""
        return bool(self.gid and self.study.game and self.study.game["id"] == self.gid)

    def ongoing(self):
        return self.active() and not self.meta.get("over")

    def blind(self):
        return self.ongoing() and not self.meta.get("help")

    def chat_allowed(self):
        return not self.ongoing() or self.meta.get("chat")

    def bot_color(self):
        return other(self.meta["student"])

    def to_play(self):
        return self.study.to_play(self.study.main)

    def state(self):
        m = self.meta
        return {"level": m["level"], "levelName": tr(LEVEL_NAMES.get(m["level"], m["level"])),
                "student": m["student"], "help": m.get("help", False), "chat": m.get("chat", False),
                "over": m.get("over", False), "result": m.get("result", ""), "thinking": self.thinking,
                "message": self.message, "toPlay": self.to_play(), "tip": len(self.study.main),
                "atTip": self.study.current == len(self.study.main)}

    def context(self):
        """Pour Sensei : ce qui se passe dans la partie en cours."""
        if not self.active():
            return ""
        m = self.meta
        fr = {"B": "Noir", "W": "Blanc"}
        txt = (f"partie EN COURS contre KataGo (niveau {LEVEL_NAMES.get(m['level'], m['level'])}), "
               f"l'élève joue {fr[m['student']]}, {len(self.study.main)} coups joués")
        if m.get("over"):
            txt = f"partie contre KataGo terminée ({m.get('result') or 'sans résultat'}), l'élève jouait {fr[m['student']]}"
        return txt

    # ------------------------------------------------------------ début / reprise
    def levels(self):
        return [{"key": k, "label": tr(v)} for k, v in LEVELS]

    def start(self, opts):
        size = int(opts.get("size") or 9)
        if size not in (9, 13, 19):
            raise ValueError(tr("taille de plateau non gérée : {size}", size=size))
        level = opts.get("level") or "rank_15k"
        if level not in LEVEL_NAMES:
            raise ValueError(tr("niveau inconnu : {level}", level=level))
        color = opts.get("color") or "B"
        if color == "random":
            color = random.choice("BW")
        if color not in ("B", "W"):
            raise ValueError(tr("couleur inconnue : {color}", color=color))
        help_, chat = bool(opts.get("help")), bool(opts.get("chat"))
        self.cfg.update({"play": {"size": size, "color": opts.get("color") or "B", "level": level,
                                  "help": help_, "chat": chat}})
        me = self.cfg["ogs"]["username"] or tr("Moi")
        bot = "KataGo" + (f" {RANKS[level]}" if level in RANKS else "")
        gid = "local-" + time.strftime("%Y%m%d-%H%M%S")
        game = {"size": size, "komi": 6.5, "rules": "japanese", "date": time.strftime("%Y-%m-%d"), "moves": [],
                "black": me if color == "B" else bot, "white": bot if color == "B" else me,
                "black_rank": "" if color == "B" else RANKS.get(level, ""),
                "white_rank": RANKS.get(level, "") if color == "B" else ""}
        os.makedirs(paths.LOCAL_DIR, exist_ok=True)
        with open(self._path(gid, "sgf"), "w", encoding="utf-8") as f:
            f.write(write_sgf(game))
        with open(self._path(gid, "json"), "w") as f:
            json.dump({"level": level, "student": color, "help": help_, "chat": chat, "over": False}, f)
        if level != "max" and not self.engine.human_model():
            self.engine.install_human()
        self.study.load_game(gid)  # -> on_load : la partie démarre (et KataGo joue s'il a Noir)
        return gid

    def on_load(self, gid):
        """Une partie vient d'être ouverte : si c'est une partie contre KataGo, on la reprend."""
        self.gid, self.meta, self.message = None, None, ""
        try:
            with open(self._path(gid, "json")) as f:
                meta = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        self.gid, self.meta = gid, meta
        if not meta.get("over"):
            self.study.current = len(self.study.main)  # on reprend là où la partie en était
        if not meta.get("over") and self.to_play() == self.bot_color():
            self.think()

    def set_options(self, opts):
        if not self.active():
            raise ValueError(tr("aucune partie contre KataGo en cours"))
        for k in ("help", "chat"):
            if k in opts:
                self.meta[k] = bool(opts[k])
        self._save()
        self.study.changed()  # l'analyse démarre (ou s'arrête) selon l'aide

    # ------------------------------------------------------------ coups de l'élève
    def user_move(self, gtp):
        """Coup cliqué sur le plateau. Renvoie False s'il ne concerne pas la partie (variante)."""
        s = self.study
        if not self.ongoing() or s.current != len(s.main):
            return False  # pas au bout de la partie : c'est une variante d'étude
        if self.thinking or self.to_play() != self.meta["student"]:
            raise ValueError(tr("C'est à KataGo de jouer"))
        s.append_move(self.meta["student"], from_gtp(gtp, s.size))
        self._after_move()
        return True

    def user_pass(self):
        if not self.ongoing() or self.thinking or self.to_play() != self.meta["student"]:
            raise ValueError(tr("Ce n'est pas à toi de jouer"))
        self.study.append_move(self.meta["student"], None)
        self._after_move()

    def resign(self):
        if not self.ongoing():
            raise ValueError(tr("aucune partie contre KataGo en cours"))
        self._end(f"{self.bot_color()}+R")

    def _after_move(self):
        self._save()
        main = self.study.main
        if len(main) >= 2 and main[-1][1] is None and main[-2][1] is None:
            threading.Thread(target=self._count, daemon=True).start()
        elif self.to_play() == self.bot_color():
            self.think()

    # ------------------------------------------------------------ fin de partie
    def _count(self):
        """Deux passes : KataGo compte (pierres mortes comprises)."""
        self.message = tr("Comptage des points…")
        self.study.broadcast_state()
        try:
            a = self.study.analyze(moves=list(self.study.main), visits=self.study.live_visits())
            score = a["score"] or 0.0
            # Score réel : un nombre entier de points + le demi-point du komi.
            pts = int(abs(score)) + 0.5
            self._end(f"{'B' if score > 0 else 'W'}+{pts:g}")
        except Exception as e:
            self.log(f"Partie : comptage impossible ({e!r})")
            self.message = tr("Comptage impossible : {error}", error=e)
            self.study.broadcast_state()

    def _end(self, result):
        self.meta.update(over=True, result=result, help=True)  # après la partie, toute l'analyse est visible
        self.message = ""
        self.study.game["result"] = result
        self._save()
        self.study.changed()

    # ------------------------------------------------------------ coups de KataGo
    def think(self):
        with self.lock:
            if self.thinking:
                return
            self.thinking = True
        self.message = ""
        self.study.broadcast_state()
        threading.Thread(target=self._think, args=(self.gid, len(self.study.main)), daemon=True).start()

    def _think(self, gid, n):
        started = time.time()
        move = None
        try:
            move = self._choose()
        except Exception as e:
            self.log(f"Partie : KataGo n'a pas pu jouer ({e!r})")
            self.message = tr("KataGo n'a pas pu jouer : {error}", error=e)
        time.sleep(max(0.0, 0.6 - (time.time() - started)))  # un coup instantané déroute
        with self.lock:
            self.thinking = False
        if move is None or self.gid != gid or not self.active() or len(self.study.main) != n:
            # Partie fermée ou changée entre-temps : on oublie ce coup (et on rejoue si la partie
            # rouverte attend KataGo).
            if move is not None and self.ongoing() and self.to_play() == self.bot_color():
                self.think()
            self.study.broadcast_state()
            return
        try:
            self.study.append_move(self.bot_color(), from_gtp(move, self.study.size))
        except (IllegalMove, ValueError) as e:
            self.message = tr("KataGo n'a pas pu jouer : {error}", error=e)
            self.study.broadcast_state()
            return
        self._after_move()

    def _wait_human(self):
        """Attend que KataGo tourne avec le réseau « humain » (téléchargé au premier besoin)."""
        if not self.engine.human_model():
            self.engine.install_human()
        while not self.engine.human_ready():
            if not self.active():
                raise RuntimeError(tr("partie fermée"))
            d = self.engine.state.get("download")
            self.message = (tr("Téléchargement du réseau « humain » de KataGo : {p:.0f} %", p=d["progress"]) if d
                            else tr("Démarrage de KataGo…"))
            self.study.broadcast_state()
            if not self.engine.installing and not self.engine.human_model():
                raise RuntimeError(self.engine.state.get("message") or tr("réseau « humain » indisponible"))
            time.sleep(1)
        self.message = ""

    def _query(self, q):
        """Requête KataGo, en laissant passer un redémarrage du moteur (nouveau réseau…)."""
        for attempt in range(5):
            try:
                return self.engine.query_sync(dict(q, priority=30))
            except RuntimeError:
                if attempt == 4:
                    raise
                time.sleep(2)

    def _best(self, base, visits):
        resp = self._query(dict(base, maxVisits=visits))
        infos = sorted(resp.get("moveInfos", []), key=lambda m: m.get("order", 99))
        return infos[0]["move"] if infos else "pass"

    def _choose(self):
        s = self.study
        moves = list(s.main)
        base = s.katago_base(moves)
        level = self.meta["level"]
        if level == "max":
            return self._best(base, min(s.live_visits(), MAX_VISITS))
        self._wait_human()
        resp = self._query(dict(base, maxVisits=1, includePolicy=True,
                                overrideSettings={"humanSLProfile": level}))
        policy = resp.get("humanPolicy")
        if not policy:
            raise RuntimeError(tr("réseau « humain » non chargé par KataGo"))
        size = s.size
        cands = [(i, p) for i, p in enumerate(policy[:size * size]) if p > 0]
        top = max((p for _, p in cands), default=0)
        cands = [(i, p) for i, p in cands if p >= top * 0.02]  # sans les coups absurdes
        pass_p = policy[size * size] if len(policy) > size * size else 0
        # Passer seulement quand la partie est vraiment finie (sinon le bot abandonne des points
        # comme aucun joueur de son niveau) : on demande à KataGo si passer est le meilleur coup.
        user_passed = bool(moves) and moves[-1][1] is None
        if (user_passed or pass_p >= top or not cands) and self._best(base, 200) == "pass":
            return "pass"
        board = s.board_for(moves)
        color = s.to_play(moves)
        while cands:
            r = random.random() * sum(p for _, p in cands)
            for k, (i, p) in enumerate(cands):
                r -= p
                if r <= 0:
                    break
            pt = (i % size, i // size)
            try:
                board.copy().play(color, pt)
                return to_gtp(pt, size)
            except IllegalMove:
                cands.pop(k)
        return "pass"
