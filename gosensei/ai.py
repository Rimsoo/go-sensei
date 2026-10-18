"""Professeur IA (optionnel) : Claude Code, API Anthropic ou API compatible OpenAI
(OpenAI, DeepSeek, Ollama, OpenRouter, Mistral, Gemini…).

Tous les fournisseurs partagent la même interface : send / stop / reset, et
diffusent les mêmes événements au navigateur (start, delta, tool, done, reset)."""

import json
import os
import shutil
import subprocess
import threading
import urllib.error
import urllib.request

from . import paths

COACH_PROMPT = """Tu es « Sensei », un professeur de Go patient et pédagogue, intégré à l'appli Go Sensei.
L'élève est débutant : il connaît les règles mais ne comprend pas encore la stratégie ni le « pourquoi » des coups.
Il voit le même plateau que toi, en direct, souvent sur un second écran pendant qu'il joue.

Comment travailler :
- Le plateau de l'élève est piloté par tes outils. Avant d'expliquer une position, regarde-la (get_position).
  Pour une partie entière, commence par get_game_review.
- Appuie TOUJOURS tes explications sur KataGo (analyze_position, evaluate_moves) mais ne te contente jamais de « l'IA dit » :
  traduis les chiffres en idées concrètes et en concepts (territoire, solidité des groupes, libertés, coupes, sente/gote,
  efficacité d'un coup, grands points, direction du jeu, menaces, taille d'un coup en points, pierres faibles/mortes).
- Raisonne en POINTS (« ce coup a coûté ~5 points ») plutôt qu'en % de victoire, plus parlant pour un débutant.
- Montre au lieu de décrire : joue des variantes avec play_moves pour illustrer, puis reviens avec back_to_game.
  Les variantes restent dans l'arbre des coups de l'élève, avec leurs annotations : il peut y revenir depuis ton message.
  Les annotations (annotate) sont attachées à la position affichée : annote APRÈS avoir positionné le plateau.
  Lettres (A, B, C) pour comparer des options, triangles rouges pour les pierres faibles, cercles verts pour les bons points,
  'area' pour colorer une zone. Dis à l'élève ce que représentent les marques.
- Vérifie avec KataGo avant d'affirmer, surtout pour la vie et la mort ; augmente les visites si une évaluation te surprend.
- Réponses courtes et structurées : quelques phrases ou puces, une idée principale par message, avec une petite règle
  à retenir quand c'est pertinent. Termine si utile par une question pour vérifier la compréhension.
- Coordonnées : colonnes A-T sans la lettre I, ligne 1 en bas.
- Français, ton chaleureux et encourageant, jamais condescendant.
- Mémoire : au début d'une conversation, lis le carnet de l'élève (read_student_profile). Quand tu repères une faiblesse
  récurrente, un concept compris ou un progrès, note-le brièvement (save_student_note).
- Chaque message de l'élève commence par [Plateau : ...] qui résume ce qu'il voit : tiens-en compte."""

OPENAI_PRESETS = {
    "openai": {"label": "OpenAI (ChatGPT)", "base_url": "https://api.openai.com/v1", "key": True},
    "deepseek": {"label": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "key": True},
    "ollama": {"label": "Ollama (local, gratuit)", "base_url": "http://localhost:11434/v1", "key": False},
    "openrouter": {"label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "key": True},
    "mistral": {"label": "Mistral", "base_url": "https://api.mistral.ai/v1", "key": True},
    "gemini": {"label": "Google Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "key": True},
    "custom": {"label": "Autre (compatible OpenAI)", "base_url": "", "key": False},
}
ANTHROPIC_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
MAX_TOOL_ROUNDS = 25


class Coach:
    """Base commune : historique affiché, état occupé, diffusion des événements."""

    def __init__(self, broadcast, log):
        self.broadcast = broadcast
        self.log = log
        self.lock = threading.Lock()
        self.busy = False
        self.history = []  # [{role, text, tools}] pour l'affichage
        self._load()

    # ------------------------------------------------------------ persistance
    def _load(self):
        try:
            with open(paths.CHAT_FILE, encoding="utf-8") as f:
                st = json.load(f)
            self.history = st.get("history", [])
            self.restore(st)
        except (OSError, json.JSONDecodeError):
            pass

    def restore(self, state):
        pass

    def extra_state(self):
        return {}

    def _save(self):
        with open(paths.CHAT_FILE, "w", encoding="utf-8") as f:
            json.dump(dict(self.extra_state(), history=self.history[-200:]), f, ensure_ascii=False)

    # ------------------------------------------------------------ événements
    def _current(self):
        if not self.history or self.history[-1]["role"] != "assistant":
            self.history.append({"role": "assistant", "text": "", "tools": []})
        return self.history[-1]

    def emit_text(self, txt):
        self._current()["text"] += txt
        self.broadcast("chat", {"kind": "delta", "text": txt})

    def emit_tool(self, name):
        cur = self._current()
        cur["tools"].append(name)
        if cur["text"] and not cur["text"].endswith("\n\n"):
            self.emit_text("\n\n")
        self.broadcast("chat", {"kind": "tool", "name": name})

    def attach_node(self, nid, label):
        """Rattache au message en cours une position que l'IA a montrée (lien cliquable)."""
        if not self.busy:
            return
        nodes = self._current().setdefault("nodes", [])
        if nodes and nodes[-1]["id"] == nid:
            nodes[-1]["label"] = label
        else:
            nodes.append({"id": nid, "label": label})
        self.broadcast("chat", {"kind": "node", "id": nid, "label": label})

    def finish(self, error=None):
        if error:
            self.emit_text(f"\n\n⚠️ {error}")
        self.busy = False
        self._save()
        self.broadcast("chat", {"kind": "done"})

    def begin(self, text):
        if self.busy:
            raise RuntimeError("Sensei est déjà en train de répondre")
        self.busy = True
        self.history.append({"role": "user", "text": text})
        self.history.append({"role": "assistant", "text": "", "tools": []})
        self.broadcast("chat", {"kind": "start"})

    # ------------------------------------------------------------ interface
    def send(self, text, context):
        raise NotImplementedError

    def stop(self):
        pass

    def reset(self):
        self.stop()
        with self.lock:
            self.history = []
            self.clear_conversation()
            self._save()
        self.broadcast("chat", {"kind": "reset"})

    def clear_conversation(self):
        pass

    def shutdown(self):
        self.stop()


class NoCoach(Coach):
    def send(self, text, context):
        raise RuntimeError("Aucune IA n'est configurée : ouvre ⚙ Réglages pour en choisir une (optionnel).")


# =================================================================== Claude Code
class ClaudeCodeCoach(Coach):
    """Claude Code en mode headless (abonnement Claude, sans clé d'API).
    Il n'a accès qu'aux outils MCP de Go Sensei (pas de shell, pas de fichiers)."""

    def __init__(self, broadcast, log, mcp_url, model=""):
        self.mcp_url = mcp_url
        self.model = model
        self.proc = None
        self.session_id = None
        super().__init__(broadcast, log)

    def restore(self, state):
        self.session_id = state.get("claude_session")

    def extra_state(self):
        return {"claude_session": self.session_id}

    def clear_conversation(self):
        self.session_id = None

    def _spawn(self):
        cfg = os.path.join(paths.COACH_DIR, "mcp.json")
        with open(cfg, "w") as f:
            json.dump({"mcpServers": {"gosensei": {"type": "http", "url": self.mcp_url}}}, f)
        cmd = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json",
               "--verbose", "--include-partial-messages",
               "--mcp-config", cfg, "--strict-mcp-config",
               "--tools", "", "--allowedTools", "mcp__gosensei", "--permission-mode", "dontAsk",
               "--disable-slash-commands", "--append-system-prompt", COACH_PROMPT]
        if self.model:
            cmd += ["--model", self.model]
        if self.session_id:
            cmd += ["--resume", self.session_id]
        self.log("IA : lancement de Claude Code" + (" (reprise de session)" if self.session_id else ""))
        self.proc = subprocess.Popen(cmd, cwd=paths.COACH_DIR, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1, env=paths.host_env())
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()
        threading.Thread(target=self._read_err, args=(self.proc,), daemon=True).start()

    def _read_err(self, proc):
        for line in proc.stderr:
            if line.strip():
                self.log(f"Claude Code : {line.strip()[:300]}")

    def _read(self, proc):
        for line in proc.stdout:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("session_id"):
                self.session_id = ev["session_id"]
            t = ev.get("type")
            if t == "stream_event":
                e = ev.get("event", {})
                if e.get("type") == "content_block_delta" and e.get("delta", {}).get("type") == "text_delta":
                    self.emit_text(e["delta"]["text"])
                elif e.get("type") == "content_block_start" and e.get("content_block", {}).get("type") == "tool_use":
                    self.emit_tool(e["content_block"].get("name", "").replace("mcp__gosensei__", ""))
            elif t == "result":
                self.finish(ev.get("result") or "erreur inconnue" if ev.get("is_error") else None)
        if self.busy:
            self.finish("Claude Code s'est arrêté. Réessaie ton message.")

    def send(self, text, context):
        with self.lock:
            self.begin(text)
            if not self.proc or self.proc.poll() is not None:
                self._spawn()
            payload = {"type": "user", "message": {"role": "user", "content": f"[Plateau : {context}]\n{text}"}}
            try:
                self.proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError):
                self.proc = None
                self.finish("Claude Code n'a pas pu démarrer : vérifie que la commande `claude` fonctionne dans un terminal.")

    def stop(self):
        with self.lock:
            if self.proc and self.proc.poll() is None:
                self.proc.kill()
            self.proc = None
            if self.busy:
                self.finish("(interrompu)")


# =================================================================== API (boucle d'agent locale)
class ApiCoach(Coach):
    """Boucle d'agent exécutée localement : le modèle appelle les outils du plateau
    directement (sans MCP). Les sous-classes implémentent un tour de conversation."""

    def __init__(self, broadcast, log, tools, settings):
        self.tools = tools
        self.settings = settings
        self.messages = []  # historique au format du fournisseur
        self.cancel = threading.Event()
        super().__init__(broadcast, log)

    def restore(self, state):
        if state.get("api_provider") == self.provider_id():
            self.messages = state.get("api_messages", [])

    def extra_state(self):
        return {"api_provider": self.provider_id(), "api_messages": self.messages[-120:]}

    def clear_conversation(self):
        self.messages = []

    def provider_id(self):
        return f"{type(self).__name__}:{self.settings.get('base_url', '')}:{self.settings.get('model', '')}"

    def run_tool(self, name, args):
        """Exécute un outil ; renvoie (texte, erreur?)."""
        if not isinstance(args, dict):
            return "Arguments invalides (objet JSON attendu).", True
        defs = {d["name"]: d for d in self.tools.definitions()}
        if name not in defs:
            return f"Outil inconnu : {name}", True
        missing = [k for k in defs[name]["inputSchema"].get("required", []) if k not in args]
        if missing:
            return f"Arguments manquants : {', '.join(missing)}", True
        try:
            return self.tools.call(name, args), False
        except Exception as e:
            return f"Erreur : {e}", True

    def send(self, text, context):
        with self.lock:
            self.begin(text)
            self.cancel.clear()
        threading.Thread(target=self._run, args=(f"[Plateau : {context}]\n{text}",), daemon=True).start()

    def _run(self, content):
        try:
            self.user_turn(content)
            for _ in range(MAX_TOOL_ROUNDS):
                if self.cancel.is_set():
                    return self.finish("(interrompu)")
                if not self.assistant_turn():
                    break
            self.finish("(interrompu)" if self.cancel.is_set() else None)
        except Exception as e:
            self.log(f"IA : {e!r}")
            if not self.cancel.is_set():
                self.finish(self.describe_error(e))

    def describe_error(self, e):
        return f"Erreur de l'IA : {e}"

    def stop(self):
        self.cancel.set()

    # À implémenter : user_turn(content) et assistant_turn() -> True s'il faut continuer (outils appelés)


class AnthropicCoach(ApiCoach):
    """API Claude (clé d'API Anthropic) via le SDK officiel."""

    def __init__(self, broadcast, log, tools, settings):
        super().__init__(broadcast, log, tools, settings)
        import anthropic  # dépendance optionnelle, embarquée dans l'AppImage
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=settings.get("api_key") or None)
        self.model = settings.get("model") or ANTHROPIC_MODELS[0]
        self.tool_defs = [{"name": d["name"], "description": d["description"], "input_schema": d["inputSchema"],
                           "eager_input_streaming": True} for d in tools.definitions()]

    def user_turn(self, content):
        last = self.messages[-1] if self.messages else None
        if last and last["role"] == "user":  # tour précédent interrompu : on fusionne
            if isinstance(last["content"], str):
                last["content"] = [{"type": "text", "text": last["content"]}]
            last["content"].append({"type": "text", "text": content})
        else:
            self.messages.append({"role": "user", "content": content})

    def assistant_turn(self):
        json_retries = 0
        while True:
            try:
                with self.client.beta.messages.stream(
                    model=self.model,
                    max_tokens=64000,
                    system=COACH_PROMPT,
                    tools=self.tool_defs,
                    messages=self.messages,
                    thinking={"type": "adaptive"},
                    output_config={"effort": "medium"},
                    betas=["server-side-fallback-2026-07-01"],
                    extra_body={"fallbacks": "default"},
                ) as stream:
                    for event in stream:
                        if self.cancel.is_set():
                            return False
                        if event.type == "text":
                            self.emit_text(event.text)
                        elif event.type == "content_block_start" and getattr(event.content_block, "type", "") == "tool_use":
                            self.emit_tool(event.content_block.name)
                    response = stream.get_final_message()
                break
            except ValueError:  # JSON d'outil illisible : on refait le tour
                json_retries += 1
                if json_retries > 2:
                    raise
        content = [b.model_dump(exclude_none=True) for b in response.content]
        self.messages.append({"role": "assistant", "content": content})
        if response.stop_reason == "pause_turn":
            return True
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason == "refusal":
            self.emit_text("\n\n(Le modèle a refusé de répondre à cette demande.)")
            return False
        if not tool_uses:
            return False
        if response.stop_reason == "max_tokens":
            raise RuntimeError("réponse tronquée (max_tokens)")
        results = []
        for b in tool_uses:
            out, err = self.run_tool(b.name, b.input)
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": out, "is_error": err})
        self.messages.append({"role": "user", "content": results})
        return True

    def describe_error(self, e):
        a = self.anthropic
        if isinstance(e, a.AuthenticationError):
            return "Clé d'API Anthropic refusée : vérifie-la dans ⚙ Réglages."
        if isinstance(e, a.RateLimitError):
            return "Limite de requêtes atteinte, réessaie dans un instant."
        if isinstance(e, a.APIStatusError):
            return f"Erreur de l'API Anthropic ({e.status_code}) : {e.message}"
        if isinstance(e, a.APIConnectionError):
            return "Impossible de joindre l'API Anthropic (connexion)."
        return super().describe_error(e)


class OpenAICoach(ApiCoach):
    """Toute API compatible OpenAI /chat/completions avec appels d'outils."""

    def __init__(self, broadcast, log, tools, settings):
        super().__init__(broadcast, log, tools, settings)
        self.base_url = (settings.get("base_url") or "").rstrip("/")
        if not self.base_url:
            raise ValueError("adresse de l'API manquante")
        if not settings.get("model"):
            raise ValueError("modèle manquant")
        self.tool_defs = [{"type": "function", "function": {"name": d["name"], "description": d["description"],
                                                            "parameters": d["inputSchema"]}}
                          for d in tools.definitions()]

    def user_turn(self, content):
        if not self.messages:
            self.messages.append({"role": "system", "content": COACH_PROMPT})
        self.messages.append({"role": "user", "content": content})

    def _request(self, body):
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        if self.settings.get("api_key"):
            headers["Authorization"] = f"Bearer {self.settings['api_key']}"
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=json.dumps(body).encode(),
                                     headers=headers, method="POST")
        return urllib.request.urlopen(req, timeout=300)

    def assistant_turn(self):
        body = {"model": self.settings["model"], "messages": self.messages, "tools": self.tool_defs, "stream": True}
        text, calls = "", {}
        with self._request(body) as r:
            for raw in r:
                if self.cancel.is_set():
                    return False
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta") or {}
                    if delta.get("content"):
                        text += delta["content"]
                        self.emit_text(delta["content"])
                    for tc in delta.get("tool_calls") or []:
                        c = calls.setdefault(tc.get("index", 0), {"id": "", "name": "", "args": ""})
                        c["id"] = tc.get("id") or c["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            c["name"] = fn["name"]
                            self.emit_tool(fn["name"])
                        c["args"] += fn.get("arguments") or ""
        msg = {"role": "assistant", "content": text or None}
        if calls:
            msg["tool_calls"] = [{"id": c["id"] or f"call_{i}", "type": "function",
                                  "function": {"name": c["name"], "arguments": c["args"] or "{}"}}
                                 for i, c in sorted(calls.items())]
        self.messages.append(msg)
        if not calls:
            return False
        for tc in msg["tool_calls"]:
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                out, err = "Arguments JSON invalides, réessaie.", True
            else:
                out, err = self.run_tool(tc["function"]["name"], args)
            self.messages.append({"role": "tool", "tool_call_id": tc["id"], "content": out})
        return True

    def describe_error(self, e):
        if isinstance(e, urllib.error.HTTPError):
            try:
                raw = e.read().decode("utf-8", "replace")
            except Exception:
                raw = ""
            detail = raw[:300]
            try:  # format habituel : {"error": {"message": "..."}}
                err = json.loads(raw).get("error")
                detail = (err.get("message") if isinstance(err, dict) else str(err)) or detail
            except (ValueError, AttributeError):
                pass
            if "support tools" in detail or "does not support tool" in detail:
                return (f"Le modèle « {self.settings.get('model')} » ne sait pas utiliser les outils du plateau. "
                        "Choisis-en un autre dans ⚙ Réglages (ex. qwen3, llama3.1, mistral-small).")
            if e.code in (401, 403):
                return f"Clé d'API refusée ({e.code}) : vérifie-la dans ⚙ Réglages."
            if e.code == 402:
                return f"Le service refuse la requête faute de crédit sur ton compte ({detail})."
            if e.code == 429:
                return "Limite de requêtes atteinte, réessaie dans un instant."
            return f"Erreur de l'API ({e.code}) : {detail}"
        if isinstance(e, urllib.error.URLError):
            return f"Impossible de joindre {self.base_url} ({e.reason}). Pour Ollama, vérifie qu'il est lancé."
        return super().describe_error(e)


# =================================================================== fabrique
def list_models(settings):
    """Modèles proposés par le fournisseur (pour le menu des réglages)."""
    provider = settings.get("provider")
    if provider == "anthropic":
        return ANTHROPIC_MODELS
    if provider == "claude-code":
        return ["", "opus", "sonnet", "haiku"]
    if provider == "openai":
        base = (settings.get("base_url") or "").rstrip("/")
        headers = {"Authorization": f"Bearer {settings['api_key']}"} if settings.get("api_key") else {}
        req = urllib.request.Request(f"{base}/models", headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        return sorted(m["id"] for m in data.get("data", []))
    return []


def make_coach(ai_cfg, broadcast, log, tools, mcp_url):
    provider = ai_cfg.get("provider") or "none"
    try:
        if provider == "claude-code":
            if not shutil.which("claude"):
                raise RuntimeError("la commande `claude` (Claude Code) est introuvable")
            return ClaudeCodeCoach(broadcast, log, mcp_url, ai_cfg.get("model", ""))
        if provider == "anthropic":
            return AnthropicCoach(broadcast, log, tools, ai_cfg)
        if provider == "openai":
            return OpenAICoach(broadcast, log, tools, ai_cfg)
    except Exception as e:
        log(f"IA désactivée : {e}")
        coach = NoCoach(broadcast, log)
        coach.error = str(e)
        return coach
    return NoCoach(broadcast, log)
