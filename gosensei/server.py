"""Serveur web local de Go Sensei : interface, flux temps réel (SSE), API et MCP."""

import json
import mimetypes
import os
import queue
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__, ai, paths
from .board import to_gtp
from .config import Config
from .games import Library
from .katago import Engine
from .mcp import Tools, handle_rpc
from .study import Study
from .tray import Tray
from .window import Window

LOGS = []
IDLE_SHUTDOWN = 45  # secondes sans fenêtre connectée avant arrêt (mode application)


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    LOGS.append(line)
    del LOGS[:-300]
    print(line, flush=True)


class Hub:
    """Diffusion d'événements vers tous les navigateurs connectés."""

    def __init__(self):
        self.clients = set()
        self.lock = threading.Lock()
        self.last_seen = time.time()
        self.ever_connected = False

    def add(self):
        q = queue.Queue(maxsize=500)
        with self.lock:
            self.clients.add(q)
            self.ever_connected = True
        return q

    def remove(self, q):
        with self.lock:
            self.clients.discard(q)
            self.last_seen = time.time()

    def count(self):
        with self.lock:
            return len(self.clients)

    def send(self, kind, data):
        msg = f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()
        with self.lock:
            for q in list(self.clients):
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    self.clients.discard(q)


class App:
    def __init__(self, port=None):
        self.cfg = Config()
        self.port = port or self.cfg["port"]
        self.url = f"http://127.0.0.1:{self.port}"
        self.hub = Hub()
        self.engine = Engine(self.cfg, log, lambda d: self.hub.send("engine", d))
        self.lib = Library(self.cfg, log)
        self.study = Study(self.lib, self.engine, self.cfg, self.hub.send, log)
        self.tools = Tools(self.study, paths.NOTES_FILE)
        self.tools.on_node = lambda nid, label: self.coach.attach_node(nid, label)
        # Une conversation par partie : on suit la partie ouverte.
        self.study.on_load = lambda gid: self.coach.set_game(gid)
        self.coach = ai.make_coach(self.cfg["ai"], self.hub.send, log, self.tools, self.url + "/mcp")
        self.window = None
        self.tray = None
        self.server = None
        self.stopping = False

    # ------------------------------------------------------------ cycle de vie
    def shutdown(self, reason=""):
        if self.stopping:
            return
        self.stopping = True
        log(f"Arrêt de Go Sensei{' (' + reason + ')' if reason else ''}")
        self.hub.send("shutdown", {})

        def later():
            time.sleep(0.6)
            if self.window:
                self.window.close()
            if self.tray:
                self.tray.stop()
            self.coach.shutdown()
            self.engine.stop()
            if self.server:
                self.server.shutdown()

        threading.Thread(target=later, daemon=True).start()

    def open_window(self):
        """Ouvre l'interface (navigateur par défaut ou fenêtre dédiée, selon les réglages).
        En arrière-plan, fermer la fenêtre n'arrête pas Go Sensei."""
        launch = self.cfg["launch"]
        on_closed = None if launch["background"] else (lambda: self.shutdown("fenêtre fermée"))
        self.window = Window(self.url, log, on_closed, launch["mode"])
        self.window.open()

    def watch_idle(self):
        """Mode application : sans fenêtre connectée pendant un moment, on s'arrête."""
        while not self.stopping:
            time.sleep(5)
            if self.hub.ever_connected and self.hub.count() == 0 and time.time() - self.hub.last_seen > IDLE_SHUTDOWN:
                self.shutdown("plus aucune fenêtre ouverte")

    def startup_tasks(self):
        games = self.lib.list()
        if games:
            self.study.load_game(games[0]["id"])
        ogs = self.cfg["ogs"]
        if ogs["username"] and ogs["auto_sync"]:
            try:
                name, new = self.lib.ogs_sync()
                log(f"OGS : {new} nouvelle(s) partie(s) pour {name}")
                if new:
                    self.hub.send("games", {"new": new})
            except Exception as e:
                log(f"OGS : synchronisation impossible ({e})")

    # ------------------------------------------------------------ infos
    def context(self):
        s = self.study
        if not s.game:
            return "aucune partie ouverte"
        g = s.game
        txt = f"partie « {g['title']} » ({g['black']} Noir / {g['white']} Blanc, {g['size']}x{g['size']}), "
        if s.variation:
            var = " ".join(c + to_gtp(p, s.size) for c, p in s.variation)
            txt += f"variante après le coup {s.cursor} : {var}, "
        else:
            txt += f"coup {s.cursor}/{len(s.main)} de la partie, "
        txt += f"au trait : {'Noir' if s.to_play() == 'B' else 'Blanc'}"
        return txt

    def rich_context(self):
        """Position complète pour les modèles qui ne vont pas la chercher eux-mêmes : d'abord
        des faits clairs calculés par KataGo, puis le plateau."""
        s = self.study
        if not s.game:
            return None
        fr = {"B": "Noir", "W": "Blanc"}
        try:
            g = s.game
            facts = [f"- Partie : {g['black']} (Noir) contre {g['white']} (Blanc), {g['size']}x{g['size']}."]
            if g.get("student"):
                facts.append(f"- L'élève joue {fr[g['student']]}.")
            facts.append(f"- Position affichée : {s.describe_node()} (coup {len(s.moves())} sur {len(s.main)} dans la partie).")
            lm = s.last_move_facts()
            if lm:
                line = f"- Dernier coup joué : {fr[lm['color']]} en {lm['move']} (coup n°{lm['number']})."
                if lm["loss"] is not None:
                    if lm["level"]:
                        line += f" C'est une {lm['level']} : il a coûté environ {lm['loss']} points à {fr[lm['color']]}."
                    else:
                        line += f" C'est un bon coup (perte {max(lm['loss'], 0):.1f} point)."
                if lm["best"] and lm["best"] != lm["move"]:
                    line += (f" Le meilleur coup à la place était {lm['best']}"
                             f" (suite prévue : {' '.join(lm['best_pv'])}).")
                facts.append(line)
            a = s.analyses.get(s.key())
            if a and a.get("score") is not None:
                lead = a["score"]
                who = "Noir" if lead > 0 else "Blanc"
                facts.append(f"- Score actuel : {who} mène d'environ {abs(lead):.1f} points.")
            if a and a.get("moves"):
                color = a["toPlay"]
                sign = 1 if color == "B" else -1
                best = a["moves"][0]["score"]
                cands = ", ".join(f"{m['move']} (perte {sign * (best - m['score']):.1f})" for m in a["moves"][:4])
                facts.append(f"- Au trait : {fr[color]}. Meilleurs coups selon KataGo : {cands}. "
                             f"Suite prévue après {a['moves'][0]['move']} : {' '.join(a['moves'][0]['pv'][:6])}.")
            mine = [m for m in s.mistakes() if m["level"] and (not g.get("student") or m["color"] == g["student"])]
            if mine:
                facts.append("- Plus grosses erreurs de l'élève dans la partie : " + ", ".join(
                    f"coup {m['move_number']} {m['played']} (-{m['loss']})" for m in sorted(mine, key=lambda m: -m["loss"])[:5]) + ".")
            return ("FAITS FIABLES (calculés par KataGo) — base-toi dessus et ne cite pas d'autres coups "
                    "sans les vérifier avec tes outils :\n" + "\n".join(facts)
                    + "\n\nDétail de la position (pour référence) :\n" + self.tools._position_text())
        except Exception as e:
            log(f"Contexte : {e!r}")
            return None

    def chat_info(self):
        provider = self.cfg["ai"]["provider"]
        return {"history": self.coach.history, "busy": self.coach.busy, "provider": provider,
                "enabled": not isinstance(self.coach, ai.NoCoach),
                "error": getattr(self.coach, "error", None)}

    def config_info(self):
        return {"config": self.cfg.public(), "presets": ai.OPENAI_PRESETS, "anthropic_models": ai.ANTHROPIC_MODELS,
                "engine": self.engine.describe(), "version": __version__,
                "paths": {"config": paths.CONFIG_FILE, "data": paths.DATA_DIR}}

    def apply_config(self, patch):
        from .ai import key_slot
        ai_patch = patch.get("ai")
        if ai_patch is not None:
            new_key = (ai_patch.pop("api_key", "") or "").strip()
            clear = ai_patch.pop("clear_api_key", False)
            for k in ("has_api_key", "key_slots", "api_keys"):
                ai_patch.pop(k, None)
            slot = key_slot(dict(self.cfg["ai"], **ai_patch))
            if slot and (new_key or clear):
                keys = dict(self.cfg["ai"].get("api_keys") or {})
                if new_key:
                    keys[slot] = new_key  # la clé ne sert qu'à ce service
                else:
                    keys.pop(slot, None)
                ai_patch["api_keys"] = keys
        patch.pop("detected", None)
        old_katago = dict(self.cfg["katago"])
        if ai_patch is not None and "api_keys" in ai_patch:
            # _merge fusionne les dictionnaires : on remplace explicitement celui des clés
            self.cfg.data["ai"]["api_keys"] = ai_patch.pop("api_keys")
        self.cfg.update(patch)
        if ai_patch is not None:
            self.coach.shutdown()
            self.coach = ai.make_coach(self.cfg["ai"], self.hub.send, log, self.tools, self.url + "/mcp")
            if self.study.game:
                self.coach.set_game(self.study.game["id"])
            self.hub.send("chat", {"kind": "reload"})
        if self.cfg["katago"] != old_katago:
            self.engine.restart()
        if "launch" in patch:
            from .config import set_autostart
            set_autostart(self.cfg["launch"]["autostart"])
        if "ogs" in patch:
            self.lib._cache.clear()  # la couleur de l'élève dépend du pseudo
        return self.config_info()

    # ------------------------------------------------------------ API POST
    def api(self, path, body):
        s = self.study
        if path == "/api/load":
            s.load_game(body["id"])
        elif path == "/api/goto":
            s.goto(body["n"])
        elif path == "/api/step":
            s.step(int(body["k"]))
        elif path == "/api/main":
            s.back_to_main()
        elif path == "/api/goto-node":
            s.goto_node(body["id"])
        elif path == "/api/sibling":
            s.sibling(int(body["d"]))
        elif path == "/api/delete-node":
            s.delete_node(body["id"])
        elif path == "/api/play":
            s.play([body["move"]])
        elif path == "/api/clear-marks":
            s.set_marks([], replace=True)
        elif path == "/api/import-sgf":
            gid = self.lib.import_sgf(body["content"], body.get("name") or "partie")
            s.load_game(gid)
            return {"id": gid}
        elif path == "/api/ogs":
            res = self.lib.ogs_import(body["query"])
            if res["username"] and res["username"] != self.cfg["ogs"]["username"]:
                self.cfg.update({"ogs": {"username": res["username"]}})
                self.lib._cache.clear()
            return dict(res, games=self.lib.list())
        elif path == "/api/chat":
            self.coach.send(body["text"], self.context(), self.rich_context())
        elif path == "/api/chat/stop":
            self.coach.stop()
        elif path == "/api/chat/reset":
            self.coach.reset()
        elif path == "/api/config":
            return self.apply_config(body)
        elif path == "/api/ai/models":
            settings = dict(self.cfg["ai"], **{k: v for k, v in body.items() if v})
            if not body.get("api_key"):
                settings["api_key"] = (self.cfg["ai"].get("api_keys") or {}).get(ai.key_slot(settings) or "", "")
            return {"models": ai.list_models(settings)}
        elif path == "/api/engine/install":
            self.engine.install()
        elif path == "/api/engine/restart":
            self.engine.restart()
        elif path == "/api/shutdown":
            self.shutdown("demandé depuis l'interface")
        else:
            raise KeyError(path)
        return {"ok": True}


def make_handler(app):
    allowed_hosts = {f"127.0.0.1:{app.port}", f"localhost:{app.port}"}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _empty(self, code):
            self.send_response(code)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _json(self, obj, code=200):
            data = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _trusted(self):
            """Refuse les requêtes venant d'autres sites (CSRF, DNS rebinding)."""
            if self.headers.get("Host") not in allowed_hosts:
                return False
            origin = self.headers.get("Origin")
            return origin is None or origin in (f"http://{h}" for h in allowed_hosts)

        def do_GET(self):
            if not self._trusted():
                return self._empty(403)
            p = self.path.split("?")[0]
            if p == "/events":
                return self._sse()
            routes = {
                "/api/state": app.study.state,
                "/api/games": app.lib.list,
                "/api/chat": app.chat_info,
                "/api/config": app.config_info,
                "/api/logs": lambda: LOGS,
                "/api/status": lambda: {"app": "go-sensei", "version": __version__},
            }
            if p in routes:
                return self._json(routes[p]())
            if p == "/mcp":
                return self._empty(405)
            f = os.path.normpath(os.path.join(paths.STATIC, "index.html" if p == "/" else p.lstrip("/")))
            if not f.startswith(paths.STATIC + os.sep) or not os.path.isfile(f):
                return self._empty(404)
            with open(f, "rb") as fh:
                data = fh.read()
            self.send_response(200)
            ctype = mimetypes.guess_type(f)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_DELETE(self):
            self._empty(200 if self._trusted() else 403)

        def do_POST(self):
            if not self._trusted():
                return self._empty(403)
            p = self.path.split("?")[0]
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return self._json({"error": "JSON invalide"}, 400)
            if p == "/mcp":
                msgs = body if isinstance(body, list) else [body]
                out = [r for r in (handle_rpc(app.tools, m) for m in msgs) if r is not None]
                if not out:
                    return self._empty(202)
                return self._json(out if isinstance(body, list) else out[0])
            # L'interface envoie cet en-tête : un autre site ne peut pas le faire sans CORS.
            if self.headers.get("X-Go-Sensei") != "1":
                return self._empty(403)
            try:
                return self._json(app.api(p, body))
            except KeyError as e:
                return self._json({"error": f"inconnu : {e}"}, 404)
            except Exception as e:
                return self._json({"error": str(e)}, 400)

        def _sse(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = app.hub.add()
            try:
                for kind, data in (("state", app.study.state()), ("engine", app.engine.describe())):
                    self.wfile.write(f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
                while not app.stopping:
                    try:
                        msg = q.get(timeout=15)
                    except queue.Empty:
                        msg = b": ping\n\n"
                    self.wfile.write(msg)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                app.hub.remove(q)

    return Handler


def run(open_window=None, port=None):
    paths.ensure_dirs()
    app = App(port)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", app.port), make_handler(app))
    except OSError as e:
        log(f"Port {app.port} indisponible ({e})")
        sys.exit(1)
    server.daemon_threads = True
    app.server = server
    with open(paths.PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    signal.signal(signal.SIGTERM, lambda *a: app.shutdown("signal"))
    app.engine.start()
    threading.Thread(target=app.startup_tasks, daemon=True).start()
    log(f"Go Sensei {__version__} : {app.url}")
    launch = app.cfg["launch"]
    if launch["tray"]:
        app.tray = Tray(on_open=app.open_window, on_quit=lambda: app.shutdown("icône de notification"), log=log)
        app.tray.start()
    if open_window if open_window is not None else app.cfg["open_window"]:
        app.open_window()
    if not launch["background"]:
        # Sans arrière-plan : on s'arrête quand plus aucune fenêtre n'est ouverte.
        threading.Thread(target=app.watch_idle, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stopping = True
        app.coach.shutdown()
        app.engine.stop()
        try:  # ne supprimer que notre propre fichier (une autre instance a pu l'écrire)
            with open(paths.PID_FILE) as f:
                if f.read().strip() == str(os.getpid()):
                    os.remove(paths.PID_FILE)
        except OSError:
            pass
