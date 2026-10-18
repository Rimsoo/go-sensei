"""Fenêtre de l'appli : un navigateur Chromium en mode application (profil dédié),
ou à défaut le navigateur par défaut. Fermer la fenêtre arrête Go Sensei."""

import os
import shutil
import subprocess
import threading
import time

from . import paths

CHROMIUM_LIKE = ["chromium", "chromium-browser", "google-chrome-stable", "google-chrome", "brave",
                 "brave-browser", "microsoft-edge-stable", "vivaldi-stable", "thorium-browser"]


def find_app_browser():
    for name in CHROMIUM_LIKE:
        p = shutil.which(name)
        if p:
            return p
    return None


class Window:
    def __init__(self, url, log, on_closed):
        self.url = url
        self.log = log
        self.on_closed = on_closed
        self.proc = None

    def open(self):
        browser = find_app_browser()
        env = paths.host_env()
        if browser:
            cmd = [browser, f"--app={self.url}", f"--user-data-dir={paths.BROWSER_PROFILE}", "--class=GoSensei",
                   "--no-first-run", "--no-default-browser-check", "--window-size=1600,1000"]
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
                                         start_new_session=True)
            threading.Thread(target=self._watch, daemon=True).start()
            self.log(f"Fenêtre : {os.path.basename(browser)} en mode application")
        else:
            subprocess.Popen(["xdg-open", self.url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
                             start_new_session=True)
            self.log("Fenêtre : navigateur par défaut (onglet)")

    def _watch(self):
        started = time.time()
        self.proc.wait()
        # Une sortie immédiate signifie que la fenêtre a été confiée à une instance déjà
        # ouverte : la fermeture sera alors détectée par l'absence de connexion.
        if time.time() - started > 5:
            self.log("Fenêtre fermée")
            self.on_closed()

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
