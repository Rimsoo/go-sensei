"""Règles du Go : plateau, captures, ko, conversion de coordonnées.

Convention interne : (x, y) avec x = colonne (0 = gauche), y = ligne (0 = haut),
comme le format SGF. Les coordonnées "GTP" (affichées aux humains et à KataGo)
utilisent les lettres A-T sans I et les lignes numérotées depuis le bas.
"""

GTP_LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"


def other(color):
    return "W" if color == "B" else "B"


def to_gtp(pt, size):
    if pt is None:
        return "pass"
    x, y = pt
    return f"{GTP_LETTERS[x]}{size - y}"


def from_gtp(s, size):
    s = s.strip().upper()
    if s in ("PASS", ""):
        return None
    col = GTP_LETTERS.index(s[0])
    row = int(s[1:])
    if not (0 <= col < size and 1 <= row <= size):
        raise ValueError(f"coordonnée hors plateau : {s}")
    return (col, size - row)


def from_sgf(s, size):
    if s == "" or (s == "tt" and size <= 19):
        return None
    return (ord(s[0]) - 97, ord(s[1]) - 97)


def to_sgf(pt):
    if pt is None:
        return ""
    return chr(97 + pt[0]) + chr(97 + pt[1])


class IllegalMove(Exception):
    pass


class Board:
    def __init__(self, size=19):
        self.size = size
        self.grid = [[None] * size for _ in range(size)]
        self.captures = {"B": 0, "W": 0}  # pierres capturées PAR cette couleur
        self.ko = None  # point interdit pour le prochain coup (ko simple)

    def copy(self):
        b = Board(self.size)
        b.grid = [row[:] for row in self.grid]
        b.captures = dict(self.captures)
        b.ko = self.ko
        return b

    def get(self, pt):
        return self.grid[pt[1]][pt[0]]

    def neighbors(self, pt):
        x, y = pt
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < self.size and 0 <= ny < self.size:
                yield (nx, ny)

    def group(self, pt):
        """Retourne (pierres, libertés) du groupe contenant pt."""
        color = self.get(pt)
        stones, libs, stack = {pt}, set(), [pt]
        while stack:
            p = stack.pop()
            for n in self.neighbors(p):
                c = self.get(n)
                if c is None:
                    libs.add(n)
                elif c == color and n not in stones:
                    stones.add(n)
                    stack.append(n)
        return stones, libs

    def place(self, color, pt):
        """Pose une pierre sans vérification (pierres de handicap / setup)."""
        self.grid[pt[1]][pt[0]] = color

    def play(self, color, pt):
        """Joue un coup légal. Retourne la liste des pierres capturées."""
        if pt is None:
            self.ko = None
            return []
        if self.get(pt) is not None:
            raise IllegalMove(f"{to_gtp(pt, self.size)} est déjà occupé")
        if pt == self.ko:
            raise IllegalMove(f"{to_gtp(pt, self.size)} : ko, il faut d'abord jouer ailleurs")
        self.grid[pt[1]][pt[0]] = color
        captured = []
        for n in self.neighbors(pt):
            if self.get(n) == other(color):
                stones, libs = self.group(n)
                if not libs:
                    captured.extend(stones)
                    for s in stones:
                        self.grid[s[1]][s[0]] = None
        stones, libs = self.group(pt)
        if not libs:
            self.grid[pt[1]][pt[0]] = None
            raise IllegalMove(f"{to_gtp(pt, self.size)} : suicide interdit")
        self.captures[color] += len(captured)
        # Ko simple : une pierre seule qui en capture une seule et n'a qu'une liberté.
        if len(captured) == 1 and len(stones) == 1 and len(libs) == 1:
            self.ko = captured[0]
        else:
            self.ko = None
        return captured

    def stones(self):
        out = []
        for y in range(self.size):
            for x in range(self.size):
                c = self.grid[y][x]
                if c:
                    out.append((x, y, c))
        return out

    def ascii(self, last=None, marks=None):
        """Plateau texte pour Claude. X = Noir, O = Blanc, '.' vide.
        Le dernier coup est entouré de parenthèses ; marks = {pt: label}."""
        marks = marks or {}
        letters = GTP_LETTERS[: self.size]
        lines = ["    " + " ".join(f"{l} " for l in letters).rstrip()]
        for y in range(self.size):
            row = []
            for x in range(self.size):
                c = self.grid[y][x]
                ch = "X" if c == "B" else "O" if c == "W" else marks.get((x, y), ".")
                if last == (x, y):
                    row.append(f"({ch})"[:3] if len(ch) == 1 else ch)
                else:
                    row.append(f" {ch} ")
            lines.append(f"{self.size - y:>2} " + "".join(row).rstrip() + f"  {self.size - y}")
        lines.append(lines[0])
        return "\n".join(lines)
