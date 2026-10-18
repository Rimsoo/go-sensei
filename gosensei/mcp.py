"""Serveur MCP (HTTP, JSON-RPC) exposant le plateau et KataGo à Claude."""

import datetime
import json
import os

from .board import to_gtp

PROTOCOL = "2025-06-18"

COLOR_FR = {"B": "Noir", "W": "Blanc"}


def lead_text(score_black):
    if score_black is None:
        return "?"
    if abs(score_black) < 0.5:
        return "partie équilibrée"
    who = "Noir" if score_black > 0 else "Blanc"
    return f"{who} mène d'environ {abs(score_black):.1f} points"


def pov(value, color):
    """Convertit une valeur du point de vue Noir vers celui de `color`."""
    return None if value is None else (value if color == "B" else -value)


class Tools:
    def __init__(self, study, notes_path):
        self.s = study
        self.notes_path = notes_path

    # ---------------------------------------------------------------- défs
    def definitions(self):
        pt = {"type": "string", "description": "Coordonnée GTP, ex. 'D4' (colonnes A-T sans I, ligne 1 en bas) ou 'pass'"}
        return [
            {"name": "get_position",
             "description": "Plateau actuellement affiché à l'élève (ASCII), numéro du coup, qui doit jouer, dernier coup et son évaluation. À appeler avant d'expliquer une position.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "get_game_review",
             "description": "Revue complète de la partie par KataGo : couleur de l'élève, erreurs de chaque camp (points perdus, meilleur coup), évolution du score.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "go_to_move",
             "description": "Affiche la position de la partie juste après le coup N (0 = plateau vide). Quitte la variante en cours.",
             "inputSchema": {"type": "object", "properties": {"move_number": {"type": "integer"}}, "required": ["move_number"]}},
            {"name": "play_moves",
             "description": "Joue une suite de coups depuis la position affichée (crée une variante visible par l'élève). Les couleurs alternent automatiquement.",
             "inputSchema": {"type": "object", "properties": {"moves": {"type": "array", "items": pt}}, "required": ["moves"]}},
            {"name": "undo",
             "description": "Recule de N coups (dans la variante, puis dans la partie).",
             "inputSchema": {"type": "object", "properties": {"count": {"type": "integer", "default": 1}}}},
            {"name": "back_to_game",
             "description": "Abandonne la variante et revient à la position de la partie réelle.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "analyze_position",
             "description": "Analyse KataGo de la position affichée : meilleurs coups (score et % de victoire pour le joueur au trait, suite principale) et carte des territoires/pierres mortes.",
             "inputSchema": {"type": "object", "properties": {
                 "visits": {"type": "integer", "description": "Profondeur de recherche (défaut adapté à la taille)"},
                 "top": {"type": "integer", "default": 5}}}},
            {"name": "evaluate_moves",
             "description": "Compare précisément des coups candidats (ex. le coup de l'élève et celui de l'IA) depuis la position affichée.",
             "inputSchema": {"type": "object", "properties": {"moves": {"type": "array", "items": pt}}, "required": ["moves"]}},
            {"name": "annotate",
             "description": "Dessine sur le plateau de l'élève pour illustrer une explication : lettres (A, B, 1, 2…) et/ou formes. Les annotations s'effacent dès que la position change, donc annoter APRÈS avoir positionné le plateau.",
             "inputSchema": {"type": "object", "properties": {
                 "marks": {"type": "array", "items": {"type": "object", "properties": {
                     "point": pt,
                     "label": {"type": "string", "description": "1 à 3 caractères"},
                     "shape": {"type": "string", "enum": ["triangle", "circle", "square", "cross", "area"]},
                     "color": {"type": "string", "enum": ["red", "green", "blue", "yellow", "purple"]}},
                     "required": ["point"]}},
                 "keep_existing": {"type": "boolean", "default": False}}, "required": ["marks"]}},
            {"name": "clear_annotations", "description": "Efface les annotations.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "list_games", "description": "Liste les parties disponibles (The Conquest of Go et OGS).",
             "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 15}}}},
            {"name": "load_game", "description": "Ouvre une partie par son identifiant (voir list_games).",
             "inputSchema": {"type": "object", "properties": {"game_id": {"type": "string"}}, "required": ["game_id"]}},
            {"name": "read_student_profile",
             "description": "Lit le carnet de l'élève : niveau, faiblesses récurrentes, progrès, notes des séances précédentes.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "save_student_note",
             "description": "Ajoute une note datée au carnet de l'élève (faiblesse récurrente, concept compris, progrès). Court et utile pour les prochaines séances.",
             "inputSchema": {"type": "object", "properties": {"note": {"type": "string"}}, "required": ["note"]}},
        ]

    # ---------------------------------------------------------------- outils
    def call(self, name, args):
        fn = getattr(self, "t_" + name, None)
        if not fn:
            raise ValueError(f"outil inconnu : {name}")
        if not self.s.game and name not in ("list_games", "load_game", "read_student_profile", "save_student_note"):
            return "Aucune partie n'est ouverte. Utilise list_games puis load_game, ou demande à l'élève d'en choisir une."
        return fn(**args)

    def _position_text(self, with_board=True):
        s = self.s
        g = s.game
        moves = s.moves()
        n = len(moves)
        lines = [f"Partie : {g['black']} (Noir) contre {g['white']} (Blanc), {g['size']}x{g['size']}, komi {g['komi']}, règles {g['rules']}."]
        if g.get("student"):
            lines.append(f"L'élève joue {COLOR_FR[g['student']]}.")
        if s.variation:
            var = " ".join(f"{c}{to_gtp(p, s.size)}" for c, p in s.variation)
            lines.append(f"VARIANTE en cours : après le coup {s.cursor} de la partie, on a essayé {var} (la partie réelle continuait par "
                         f"{to_gtp(s.main[s.cursor][1], s.size) if s.cursor < len(s.main) else 'rien'}).")
        else:
            lines.append(f"Position de la partie réelle après le coup {n}/{len(s.main)}.")
        if moves:
            c, p = moves[-1]
            lines.append(f"Dernier coup : {COLOR_FR[c]} {to_gtp(p, s.size)} (coup n°{n}).")
            if not s.variation:
                m = next((m for m in s.mistakes() if m["move_number"] == n), None)
                if m:
                    best = f"meilleur coup selon KataGo : {m['best']} (suite {' '.join(m['best_pv'][:6])})"
                    lines.append(f"Évaluation de ce coup : perte de {m['loss']} points ({m['level'] or 'correct'}), {best}.")
        if s.main[s.cursor:s.cursor + 1] and not s.variation:
            lines.append(f"Coup suivant dans la partie : {COLOR_FR[s.main[s.cursor][0]]} {to_gtp(s.main[s.cursor][1], s.size)}.")
        lines.append(f"Au trait : {COLOR_FR[s.to_play()]}.")
        board = s.board_for(moves)
        lines.append(f"Prisonniers : Noir en a capturé {board.captures['B']}, Blanc {board.captures['W']}.")
        a = s.analyses.get(s.key())
        if a and a["score"] is not None:
            lines.append(f"Estimation actuelle ({a['visits']} visites) : {lead_text(a['score'])}, Noir gagne à {a['winrate']*100:.0f}%.")
        if with_board:
            marks = {(m["x"], m["y"]): (m["label"] or "*")[:1] for m in s.marks}
            last = moves[-1][1] if moves else None
            lines.append("\nPlateau (X = Noir, O = Blanc, (·) = dernier coup) :\n" + board.ascii(last=last, marks=marks))
        return "\n".join(lines)

    def t_get_position(self):
        return self._position_text()

    def t_get_game_review(self):
        s = self.s
        r = s.review
        if not r:
            return "Pas de revue disponible."
        head = [f"Revue KataGo : {len(r['turns'])}/{r['total']} positions analysées ({r['status']})."]
        g = s.game
        if g.get("student"):
            head.append(f"L'élève joue {COLOR_FR[g['student']]}.")
        ms = [m for m in s.mistakes() if m["level"]]
        for color in ("B", "W"):
            mine = [m for m in ms if m["color"] == color]
            total = sum(m["loss"] for m in s.mistakes() if m["color"] == color and m["loss"] > 0)
            head.append(f"\n{COLOR_FR[color]} : {len(mine)} erreurs notables, ~{total:.0f} points perdus au total.")
            for m in sorted(mine, key=lambda m: -m["loss"])[:12]:
                head.append(f"  coup {m['move_number']} : {m['played']} → -{m['loss']} pts ({m['level']}), "
                            f"mieux : {m['best']} (suite {' '.join(m['best_pv'][:5])})")
        curve = sorted(r["turns"].items())
        step = max(1, len(curve) // 12)
        head.append("\nÉvolution (après coup n : score) : " + ", ".join(
            f"{t}: {lead_text(v['score'])}" for t, v in curve[::step] if v["score"] is not None))
        return "\n".join(head)

    def t_go_to_move(self, move_number):
        self.s.goto(move_number)
        return self._position_text()

    def t_play_moves(self, moves):
        try:
            played = self.s.play(moves)
        except Exception as e:
            return f"Coup refusé : {e}\n\n" + self._position_text()
        return f"Joué : {', '.join(played)}.\n\n" + self._position_text()

    def t_undo(self, count=1):
        self.s.step(-int(count))
        return self._position_text()

    def t_back_to_game(self):
        self.s.back_to_main()
        return self._position_text()

    def _ownership_map(self, a):
        own = a.get("ownership")
        if not own:
            return ""
        s = self.s
        size = s.size
        board = s.board_for(s.moves())
        grid = {(x, y): c for x, y, c in board.stones()}
        rows = ["    " + "  ".join("ABCDEFGHJKLMNOPQRST"[:size])]
        for y in range(size):
            row = []
            for x in range(size):
                v = own[y * size + x]
                c = grid.get((x, y))
                if c == "B":
                    ch = "X" if v > -0.5 else "x"  # x = pierre noire morte
                elif c == "W":
                    ch = "O" if v < 0.5 else "o"
                elif v > 0.6:
                    ch = "b"
                elif v < -0.6:
                    ch = "w"
                elif abs(v) >= 0.3:
                    ch = "+" if v > 0 else "-"
                else:
                    ch = "?"
                row.append(ch)
            rows.append(f"{size - y:>2}  " + "  ".join(row))
        return ("Carte des territoires (b = territoire Noir, w = territoire Blanc, +/- = penche Noir/Blanc, ? = disputé, "
                "x/o = pierre noire/blanche considérée MORTE) :\n" + "\n".join(rows))

    def t_analyze_position(self, visits=None, top=5):
        a = self.s.analyze(visits=visits)
        color = a["toPlay"]
        lines = [f"Analyse ({a['visits']} visites). Au trait : {COLOR_FR[color]}. {lead_text(a['score'])} "
                 f"(Noir gagne à {a['winrate']*100:.0f}%)."]
        lines.append(f"Meilleurs coups pour {COLOR_FR[color]} (score = avance de {COLOR_FR[color]} après ce coup) :")
        for m in a["moves"][:top]:
            lines.append(f"  {m['move']} : score {pov(m['score'], color):+.1f}, victoire {pov(m['winrate'] - 0.5, color) * 100 + 50:.0f}%, "
                         f"{m['visits']} visites, suite : {' '.join(m['pv'][:8])}")
        lines.append("")
        lines.append(self._ownership_map(a))
        return "\n".join(lines)

    def t_evaluate_moves(self, moves):
        color, res = self.s.evaluate(moves)
        lines = [f"Comparaison pour {COLOR_FR[color]} (score = avance de {COLOR_FR[color]} après le coup) :"]
        for r in res:
            if "illegal" in r:
                lines.append(f"  {r['move']} : illégal ({r['illegal']})")
            else:
                lines.append(f"  {r['move']} : score {pov(r['score'], color):+.1f}, victoire {pov(r['winrate'] - 0.5, color) * 100 + 50:.0f}%, "
                             f"réponse attendue : {' '.join(r['pv'][1:8])}")
        return "\n".join(lines)

    def t_annotate(self, marks, keep_existing=False):
        self.s.set_marks(marks, replace=not keep_existing)
        return f"{len(marks)} annotation(s) affichée(s) sur le plateau de l'élève."

    def t_clear_annotations(self):
        self.s.set_marks([], replace=True)
        return "Annotations effacées."

    def t_list_games(self, limit=15):
        out = []
        for e in self.s.lib.list()[:limit]:
            st = f", élève = {COLOR_FR[e['student']]}" if e["student"] else ""
            out.append(f"{e['id']} : {e['black']} vs {e['white']}, {e['size']}x{e['size']}, {e['moves']} coups, "
                       f"{e['folder']}, jouée le {datetime.datetime.fromtimestamp(e['played']):%d/%m/%Y %H:%M}, {e['result'] or ''}{st}")
        return "\n".join(out) or "Aucune partie trouvée."

    def t_load_game(self, game_id):
        self.s.load_game(game_id)
        return "Partie chargée (la revue KataGo démarre en arrière-plan).\n\n" + self._position_text()

    def t_read_student_profile(self):
        if not os.path.exists(self.notes_path):
            return "Carnet vide : première séance."
        with open(self.notes_path, encoding="utf-8") as f:
            return f.read()[-8000:]

    def t_save_student_note(self, note):
        new = not os.path.exists(self.notes_path)
        with open(self.notes_path, "a", encoding="utf-8") as f:
            if new:
                f.write("# Carnet de l'élève\n\n")
            f.write(f"- {datetime.date.today().isoformat()} : {note.strip()}\n")
        return "Note enregistrée."


def handle_rpc(tools, msg):
    """Traite un message JSON-RPC. Retourne la réponse (dict) ou None (notification)."""
    mid = msg.get("id")
    method = msg.get("method", "")
    if mid is None:
        return None
    try:
        if method == "initialize":
            client_proto = (msg.get("params") or {}).get("protocolVersion", PROTOCOL)
            result = {"protocolVersion": client_proto, "capabilities": {"tools": {}},
                      "serverInfo": {"name": "go-sensei", "version": "1.0"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": tools.definitions()}
        elif method == "tools/call":
            p = msg.get("params") or {}
            try:
                text = tools.call(p.get("name"), p.get("arguments") or {})
                result = {"content": [{"type": "text", "text": text}]}
            except Exception as e:
                result = {"content": [{"type": "text", "text": f"Erreur : {e}"}], "isError": True}
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"méthode inconnue : {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}
