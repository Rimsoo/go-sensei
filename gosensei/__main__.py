"""Point d'entrée : python -m gosensei [--no-window] [--port N] [--stop]"""

import argparse
import json
import os
import signal
import sys
import urllib.request

from . import __version__, paths


def running(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1) as r:
            return json.loads(r.read()).get("app") == "go-sensei"
    except Exception:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(prog="go-sensei", description="Plateau d'analyse KataGo + professeur IA.")
    ap.add_argument("--no-window", action="store_true", help="ne pas ouvrir de fenêtre (serveur seul)")
    ap.add_argument("--port", type=int, help="port local (8765 par défaut)")
    ap.add_argument("--stop", action="store_true", help="arrêter une instance en cours")
    ap.add_argument("--version", action="version", version=f"Go Sensei {__version__}")
    args = ap.parse_args(argv)

    if args.stop:
        try:
            with open(paths.PID_FILE) as f:
                os.kill(int(f.read().strip()), signal.SIGTERM)
            print("Go Sensei arrêté.")
        except (OSError, ValueError):
            print("Go Sensei ne tourne pas.")
        return

    from .config import Config
    cfg = Config()
    port = args.port or cfg["port"]
    if running(port):
        # Déjà lancé (en arrière-plan par exemple) : on ouvre juste l'interface.
        if not args.no_window:
            from .window import Window
            Window(f"http://127.0.0.1:{port}", print, None, cfg["launch"]["mode"]).open()
        print(f"Go Sensei tourne déjà sur http://127.0.0.1:{port}")
        return

    from .server import run
    run(open_window=False if args.no_window else None, port=args.port)


if __name__ == "__main__":
    sys.exit(main())
