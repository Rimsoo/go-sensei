"""Moteur KataGo : localisation, téléchargement, choix GPU/CPU et protocole JSON 'analysis'."""

import glob
import itertools
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile

from . import paths
from .config import detect_conquest_model

KATAGO_VERSION = "1.16.3"
RELEASE = f"https://github.com/lightvector/KataGo/releases/download/v{KATAGO_VERSION}"
BUILDS = {
    "opencl": f"{RELEASE}/katago-v{KATAGO_VERSION}-opencl-linux-x64.zip",
    "eigenavx2": f"{RELEASE}/katago-v{KATAGO_VERSION}-eigenavx2-linux-x64.zip",
    "eigen": f"{RELEASE}/katago-v{KATAGO_VERSION}-eigen-linux-x64.zip",
}
MODEL_NAME = "kata1-b18c384nbt-s9791399168-d4261348054.bin.gz"
MODEL_URL = f"https://media.katagotraining.org/uploaded/networks/models/kata1/{MODEL_NAME}"

STATE_LABELS = {
    "absent": "KataGo non installé",
    "downloading": "téléchargement",
    "starting": "démarrage",
    "tuning": "calibrage du GPU (1re fois, 1-2 min)",
    "ready": "prêt",
    "error": "erreur",
    "stopped": "arrêté",
}


def is_appimage(path):
    try:
        with open(path, "rb") as f:
            return f.read(11)[8:11] == b"AI\x02"
    except OSError:
        return False


def unpack_appimage(path):
    """Les KataGo Linux officiels sont des AppImage : on les décompresse une fois
    (plus besoin de FUSE, démarrage plus rapide). 'katago' devient le script AppRun."""
    if not is_appimage(path):
        return
    dest = os.path.dirname(path)
    with tempfile.TemporaryDirectory(dir=dest) as tmp:
        subprocess.run([path, "--appimage-extract"], cwd=tmp, check=True, env=paths.host_env(),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        root = os.path.join(tmp, "squashfs-root")
        os.remove(path)
        for name in os.listdir(root):
            target = os.path.join(dest, "katago" if name == "AppRun" else name)
            if os.path.isdir(target) and not os.path.islink(target):
                shutil.rmtree(target)
            shutil.move(os.path.join(root, name), target)


def cpu_has_avx2():
    try:
        with open("/proc/cpuinfo") as f:
            return "avx2" in f.read()
    except OSError:
        return False


class Engine:
    def __init__(self, cfg, log, on_status):
        self.cfg = cfg
        self.log = log
        self.on_status = on_status
        self.proc = None
        self.callbacks = {}
        self.lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.ready = threading.Event()
        self.ids = itertools.count(1)
        self.stopping = False
        self.gpu_failed = False
        self.wake = threading.Event()  # réveille la boucle après une installation
        self.state = {"state": "stopped", "backend": None, "progress": None, "message": ""}

    # ------------------------------------------------------------ statut
    @property
    def status(self):
        s = self.state
        label = STATE_LABELS.get(s["state"], s["state"])
        if s["state"] == "downloading" and s["progress"] is not None:
            label += f" {s['progress']:.0f} %"
        if s["state"] == "ready" and s["backend"]:
            label += " (GPU)" if s["backend"] == "opencl" else " (CPU)"
        return label

    def _set(self, **kw):
        self.state.update(kw)
        self.on_status(self.describe())

    def describe(self):
        return dict(self.state, label=self.status, model=self.find_model(), binaries=self.available_binaries(),
                    can_install=not (self.find_model() and self.available_binaries()))

    # ------------------------------------------------------------ localisation
    def _binary_candidates(self, kind):
        out = []
        bundled = paths.bundled_katago_dir()
        if bundled:
            out.append(os.path.join(bundled, kind, "katago"))
        out.append(os.path.join(paths.KATAGO_DIR, kind, "katago"))
        return out

    def find_binary(self, kind):
        for p in self._binary_candidates(kind):
            if os.access(p, os.X_OK):
                return p
        return None

    def available_binaries(self):
        custom = self.cfg["katago"]["binary"]
        out = {k: self.find_binary(k) for k in BUILDS}
        if custom and os.access(custom, os.X_OK):
            out["custom"] = custom
        return {k: v for k, v in out.items() if v}

    def find_model(self):
        custom = self.cfg["katago"]["model"]
        if custom and os.path.isfile(custom):
            return custom
        bundled = paths.bundled_katago_dir()
        cands = []
        if bundled:
            cands += sorted(glob.glob(os.path.join(bundled, "models", "*.bin.gz")))
        cands.append(os.path.join(paths.KATAGO_DIR, "models", MODEL_NAME))
        cands.append(detect_conquest_model())
        for c in cands:
            if c and os.path.isfile(c):
                return c
        return None

    def cpu_kind(self):
        return "eigenavx2" if cpu_has_avx2() else "eigen"

    def choose(self):
        """(type, binaire) à lancer selon les réglages et ce qui est disponible."""
        custom = self.cfg["katago"]["binary"]
        if custom and os.access(custom, os.X_OK):
            return "custom", custom
        backend = self.cfg["katago"]["backend"]
        cpu = self.cpu_kind()
        order = {"gpu": ["opencl"], "cpu": [cpu, "eigen"]}.get(backend) or \
            ([cpu, "eigen"] if self.gpu_failed else ["opencl", cpu, "eigen"])
        for kind in order:
            b = self.find_binary(kind)
            if b:
                return kind, b
        return None, None

    def wanted_downloads(self):
        backend = self.cfg["katago"]["backend"]
        kind = self.cpu_kind() if backend == "cpu" or self.gpu_failed else "opencl"
        need = []
        if not self.find_binary(kind) and not self.cfg["katago"]["binary"]:
            need.append(("binary", kind))
        if not self.find_model():
            need.append(("model", MODEL_NAME))
        return need

    # ------------------------------------------------------------ téléchargement
    def install(self, wait=False):
        t = threading.Thread(target=self._install, daemon=True)
        t.start()
        if wait:
            t.join()

    def _download(self, url, dest, done_before, total):
        req = urllib.request.Request(url, headers={"User-Agent": "GoSensei"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            got = 0
            last = 0
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if time.time() - last > 0.5:
                    last = time.time()
                    self._set(progress=100 * (done_before + got) / total)
        return got

    def _install(self):
        need = self.wanted_downloads()
        if not need:
            self.wake.set()
            return
        sizes = {"binary": 36_000_000, "model": 97_900_000}
        total = sum(sizes[k] for k, _ in need)
        done = 0
        self._set(state="downloading", progress=0, message="")
        try:
            for what, name in need:
                if what == "binary":
                    self.log(f"Téléchargement de KataGo ({name})")
                    with tempfile.TemporaryDirectory() as tmp:
                        z = os.path.join(tmp, "k.zip")
                        done += self._download(BUILDS[name], z, done, total)
                        with zipfile.ZipFile(z) as zf:
                            member = next(m for m in zf.namelist() if os.path.basename(m) == "katago")
                            dest_dir = os.path.join(paths.KATAGO_DIR, name)
                            os.makedirs(dest_dir, exist_ok=True)
                            with zf.open(member) as src, open(os.path.join(dest_dir, "katago"), "wb") as out:
                                shutil.copyfileobj(src, out)
                            os.chmod(os.path.join(dest_dir, "katago"), 0o755)
                        unpack_appimage(os.path.join(dest_dir, "katago"))
                else:
                    self.log("Téléchargement du réseau de neurones KataGo")
                    d = os.path.join(paths.KATAGO_DIR, "models")
                    os.makedirs(d, exist_ok=True)
                    part = os.path.join(d, name + ".part")
                    done += self._download(MODEL_URL, part, done, total)
                    os.replace(part, os.path.join(d, name))
            self._set(state="starting", progress=None)
            self.wake.set()
        except Exception as e:
            self.log(f"Téléchargement échoué : {e}")
            self._set(state="error", progress=None, message=f"Téléchargement échoué : {e}")

    # ------------------------------------------------------------ process
    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def restart(self):
        """Relance avec les réglages actuels (changement de backend, de réseau…)."""
        self.gpu_failed = False
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        self.wake.set()

    def stop(self):
        self.stopping = True
        self.wake.set()
        if self.proc and self.proc.poll() is None:
            self.proc.kill()

    def _command(self, kind, binary):
        model = self.find_model()
        threads = 16 if kind in ("opencl", "custom") else max(2, os.cpu_count() or 4)
        overrides = f"logDir={paths.LOG_DIR},numSearchThreads={threads}"
        return [binary, "analysis", "-config", os.path.join(paths.RESOURCES, "analysis.cfg"),
                "-model", model, "-override-config", overrides]

    def _loop(self):
        for kind in BUILDS:
            p = os.path.join(paths.KATAGO_DIR, kind, "katago")
            try:
                unpack_appimage(p)
            except Exception as e:
                self.log(f"KataGo : décompression impossible de {p} ({e})")
        while not self.stopping:
            kind, binary = self.choose()
            if not binary or not self.find_model():
                self._set(state="absent", backend=None)
                if self.cfg["katago"]["backend"] == "auto" and self.gpu_failed and self.find_model():
                    self.install()  # repli CPU automatique : petit téléchargement
                self.wake.wait()
                self.wake.clear()
                continue
            self.wake.clear()
            self._set(state="starting", backend=kind, message="")
            self.log(f"KataGo : démarrage ({kind}, {os.path.basename(self.find_model())})")
            started = time.time()
            try:
                self.proc = subprocess.Popen(self._command(kind, binary), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE, text=True, bufsize=1,
                                             env=paths.host_env())
            except OSError as e:
                self._set(state="error", message=str(e))
                self.wake.wait()
                continue
            threading.Thread(target=self._read_err, args=(self.proc,), daemon=True).start()
            self._send_raw({"id": "warmup", "moves": [], "rules": "japanese", "komi": 6.5,
                            "boardXSize": 9, "boardYSize": 9, "maxVisits": 1})
            self._read_out(self.proc)
            # Le process s'est terminé.
            was_ready = self.ready.is_set()
            self.ready.clear()
            self._fail_pending()
            if self.stopping:
                break
            if not was_ready and kind == "opencl" and self.cfg["katago"]["backend"] == "auto":
                self.log("KataGo : le GPU (OpenCL) ne démarre pas, passage au CPU")
                self.gpu_failed = True
                continue
            if self.wake.is_set():  # relance demandée
                continue
            if not was_ready:
                self._set(state="error", message="KataGo n'a pas pu démarrer (voir le journal)")
                self.wake.wait()
                continue
            self.log("KataGo : arrêt inattendu, relance")
            time.sleep(max(0.0, 3 - (time.time() - started)))
        self._set(state="stopped")

    def _read_err(self, proc):
        for line in proc.stderr:
            line = line.strip()
            low = line.lower()
            if "tuning" in low and self.state["state"] == "starting":
                self._set(state="tuning")
            if "tuning" in low:  # lignes de calibrage (contiennent « ErrorProp »)
                continue
            if any(w in low for w in ("error", "exception", "failed")):
                self.log(f"KataGo : {line[:300]}")
                self.state["message"] = line[:300]

    def _read_out(self, proc):
        for line in proc.stdout:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                resp = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = resp.get("id")
            if rid == "warmup":
                if not self.ready.is_set():
                    self.ready.set()
                    self._set(state="ready")
                    self.log("KataGo : prêt")
                continue
            if "warning" in resp:
                self.log(f"KataGo warning : {resp['warning']}")
            with self.lock:
                cb = self.callbacks.get(rid)
            if cb:
                try:
                    cb(resp)
                except Exception as e:  # ne jamais tuer le lecteur
                    self.log(f"KataGo callback erreur : {e!r}")

    def _fail_pending(self):
        with self.lock:
            cbs = list(self.callbacks.items())
            self.callbacks.clear()
        for rid, cb in cbs:
            try:
                cb({"id": rid, "error": "KataGo s'est arrêté"})
            except Exception:
                pass

    def _send_raw(self, obj):
        with self.write_lock:
            try:
                self.proc.stdin.write(json.dumps(obj) + "\n")
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError, AttributeError):
                pass

    # ------------------------------------------------------------ requêtes
    def query(self, q, callback):
        """Requête asynchrone ; callback(réponse) à chaque réponse (intermédiaires comprises)."""
        self.ready.wait()
        qid = q.get("id") or f"q{next(self.ids)}"
        q = dict(q, id=qid)
        with self.lock:
            self.callbacks[qid] = callback
        self._send_raw(q)
        return qid

    def forget(self, qid):
        with self.lock:
            self.callbacks.pop(qid, None)

    def terminate(self, qid):
        self.forget(qid)
        if self.ready.is_set():
            self._send_raw({"id": f"stop-{qid}", "action": "terminate", "terminateId": qid})

    def query_sync(self, q, timeout=120):
        if not self.ready.wait(timeout):
            raise TimeoutError(f"KataGo n'est pas prêt ({self.status})")
        done = threading.Event()
        result = {}

        def cb(resp):
            if resp.get("isDuringSearch"):
                return
            result["r"] = resp
            done.set()

        qid = self.query(q, cb)
        ok = done.wait(timeout)
        self.forget(qid)
        if not ok:
            raise TimeoutError("KataGo n'a pas répondu à temps")
        if "error" in result["r"]:
            raise RuntimeError(result["r"]["error"])
        return result["r"]
