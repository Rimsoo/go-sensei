"""Lecture minimale de fichiers SGF (ligne principale uniquement)."""

import sys

from .board import from_sgf

# Les SGF d'OGS imbriquent chaque coup dans une variation : un arbre par coup.
sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))


class _Parser:
    def __init__(self, text):
        self.t, self.i = text, 0

    def ws(self):
        while self.i < len(self.t) and self.t[self.i] in " \t\r\n":
            self.i += 1

    def peek(self):
        self.ws()
        return self.t[self.i] if self.i < len(self.t) else ""

    def node(self):
        self.i += 1  # ';'
        node = {}
        while True:
            self.ws()
            j = self.i
            while self.i < len(self.t) and self.t[self.i].isalpha():
                self.i += 1
            ident = self.t[j:self.i]
            if not ident:
                return node
            vals = []
            while self.peek() == "[":
                self.i += 1
                buf = []
                while self.i < len(self.t) and self.t[self.i] != "]":
                    if self.t[self.i] == "\\" and self.i + 1 < len(self.t):
                        self.i += 1
                    buf.append(self.t[self.i])
                    self.i += 1
                self.i += 1
                vals.append("".join(buf))
            node[ident.upper()] = vals

    def tree(self):
        """Lit '(' noeuds* arbres* ')' et retourne la ligne principale."""
        self.i += 1  # '('
        main = []
        while self.peek() == ";":
            main.append(self.node())
        first = True
        while self.peek() == "(":
            sub = self.tree()
            if first:
                main += sub
                first = False
        if self.peek() == ")":
            self.i += 1
        return main


def _parse_nodes(text):
    """Ligne principale d'un SGF : liste de noeuds {prop: [valeurs]}."""
    p = _Parser(text)
    while p.peek() not in ("(", ""):
        p.i += 1
    return p.tree() if p.peek() == "(" else []


def _expand_points(vals, size):
    pts = []
    for v in vals:
        if ":" in v:  # rectangle compressé "aa:cc"
            a, b = v.split(":")
            (x1, y1), (x2, y2) = from_sgf(a, size), from_sgf(b, size)
            for x in range(min(x1, x2), max(x1, x2) + 1):
                for y in range(min(y1, y2), max(y1, y2) + 1):
                    pts.append((x, y))
        else:
            p = from_sgf(v, size)
            if p:
                pts.append(p)
    return pts


def parse_sgf(text):
    nodes = _parse_nodes(text)
    if not nodes:
        raise ValueError("SGF vide ou illisible")
    root = nodes[0]

    def prop(name, default=""):
        return root.get(name, [default])[0]

    size_s = prop("SZ", "19").split(":")[0]
    size = int(size_s) if size_s.isdigit() else 19
    try:
        komi = float(prop("KM", "6.5") or 6.5)
    except ValueError:
        komi = 6.5
    setup = {"B": [], "W": []}
    moves = []
    for k, node in enumerate(nodes):
        setup["B"] += _expand_points(node.get("AB", []), size)
        setup["W"] += _expand_points(node.get("AW", []), size)
        for color in ("B", "W"):
            if color in node:
                moves.append((color, from_sgf(node[color][0], size)))
    rules = (prop("RU", "japanese") or "japanese").lower()
    if rules not in ("japanese", "chinese", "korean", "aga", "new-zealand", "tromp-taylor"):
        rules = "japanese"
    return {
        "size": size,
        "komi": komi,
        "rules": rules,
        "black": prop("PB", "Noir"),
        "white": prop("PW", "Blanc"),
        "black_rank": prop("BR"),
        "white_rank": prop("WR"),
        "result": prop("RE"),
        "date": prop("DT"),
        "name": prop("GN"),
        "handicap": prop("HA"),
        "setup": setup,
        "first_player": prop("PL", "") or (moves[0][0] if moves else ("W" if setup["B"] and not setup["W"] else "B")),
        "moves": moves,
    }
