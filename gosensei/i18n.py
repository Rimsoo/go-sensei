"""Langue de l'interface : français (la langue du code) ou anglais.

Les messages restent écrits en français dans le code ; EN donne leur traduction,
clé = le texte français exact. L'interface web a son propre dictionnaire
(static/i18n.js) ; celui-ci couvre ce que le serveur lui envoie déjà rédigé :
état de KataGo, erreurs, menu de l'icône, langue des réponses de Sensei."""

import os
import re

LANGS = ("fr", "en")
LANG = "fr"

EN = {
    # Goban physique (IgOGS)
    "IgOGS ne répond pas : lancez-le (caméra du goban)": "IgOGS is not responding: start it (goban camera)",
    "Goban utilisé par {owner}": "Goban used by {owner}",
    "Noir": "Black",
    "Blanc": "White",
    "Goban synchronisé": "Goban in sync",
    "En attente de la caméra": "Waiting for the camera",
    "Retirez les pierres prises : {pts}": "Remove the captured stones: {pts}",
    "posez {color} en {pts}": "place {color} at {pts}",
    "retirez {pts}": "remove {pts}",
    # -- KataGo : états, réseaux, messages
    "KataGo non installé": "KataGo not installed",
    "téléchargement": "downloading",
    "démarrage": "starting",
    "calibrage du GPU (1re fois, 1-2 min)": "GPU tuning (first time, 1-2 min)",
    "prêt": "ready",
    "erreur": "error",
    "arrêté": "stopped",
    " · téléchargement du réseau {p:.0f} %": " · downloading network {p:.0f} %",
    "Léger (b6)": "Light (b6)",
    "Moyen (b10)": "Medium (b10)",
    "Fort (b15)": "Strong (b15)",
    "Très fort (b18)": "Very strong (b18)",
    "très rapide, pour les petits processeurs": "very fast, for small CPUs",
    "le bon compromis sur un processeur": "the right trade-off on a CPU",
    "processeur puissant ou petite carte graphique": "powerful CPU or small GPU",
    "pour une carte graphique": "for a GPU",
    "carte graphique modeste : b18 n'y tient pas": "modest GPU: b18 doesn't fit",
    "carte graphique : le réseau le plus fort reste rapide": "GPU: the strongest network stays fast",
    "processeur ({cores} cœurs) : b18 y serait 10 à 15 fois plus lent":
        "CPU ({cores} cores): b18 would be 10 to 15 times slower",
    "petit processeur ({cores} cœurs)": "small CPU ({cores} cores)",
    "petit processeur ({cores} cœurs, sans AVX2)": "small CPU ({cores} cores, no AVX2)",
    " (voir le journal)": " (see the log)",
    "Téléchargement échoué : {error}": "Download failed: {error}",
    "KataGo n'a pas pu démarrer": "KataGo could not start",
    "KataGo n'est pas prêt ({status})": "KataGo is not ready ({status})",
    "KataGo n'a pas répondu à temps": "KataGo did not answer in time",
    # -- parties
    "partie inconnue : {gid}": "unknown game: {gid}",
    "joueur OGS introuvable : {name} (vouliez-vous dire {suggest} ?)":
        "OGS player not found: {name} (did you mean {suggest}?)",
    "joueur OGS introuvable : {name}": "OGS player not found: {name}",
    "OGS n'a pas renvoyé de SGF pour la partie {gid}": "OGS returned no SGF for game {gid}",
    "aucun pseudo OGS configuré": "no OGS username configured",
    "position inconnue : {nid}": "unknown position: {nid}",
    "on ne peut supprimer que des variantes": "only variations can be deleted",
    "JSON invalide": "invalid JSON",
    "inconnu : {what}": "unknown: {what}",
    # -- professeur IA
    "Sensei est déjà en train de répondre": "Sensei is already answering",
    "Aucune IA n'est configurée : ouvre ⚙ Réglages pour en choisir une (optionnel).":
        "No AI is configured: open ⚙ Settings to choose one (optional).",
    "Claude Code s'est arrêté. Réessaie ton message.": "Claude Code stopped. Try your message again.",
    "Claude Code n'a pas pu démarrer : vérifie que la commande `claude` fonctionne dans un terminal.":
        "Claude Code could not start: check that the `claude` command works in a terminal.",
    "Erreur de l'IA : {error}": "AI error: {error}",
    "(Le modèle a refusé de répondre à cette demande.)": "(The model refused to answer this request.)",
    "réponse tronquée (max_tokens)": "truncated answer (max_tokens)",
    "Clé d'API Anthropic refusée : vérifie-la dans ⚙ Réglages.":
        "Anthropic API key refused: check it in ⚙ Settings.",
    "Limite de requêtes atteinte, réessaie dans un instant.": "Rate limit reached, try again in a moment.",
    "Impossible de joindre l'API Anthropic (connexion).": "Could not reach the Anthropic API (connection).",
    "Erreur de l'API Anthropic ({code}) : {message}": "Anthropic API error ({code}): {message}",
    "adresse de l'API manquante": "API address missing",
    "modèle manquant": "model missing",
    "Le modèle « {model} » ne sait pas utiliser les outils du plateau. "
    "Choisis-en un autre dans ⚙ Réglages (ex. qwen3, llama3.1, mistral-small).":
        "The model “{model}” can't use the board tools. "
        "Choose another one in ⚙ Settings (e.g. qwen3, llama3.1, mistral-small).",
    "Clé d'API refusée ({code}) : vérifie-la dans ⚙ Réglages.": "API key refused ({code}): check it in ⚙ Settings.",
    "Le service refuse la requête faute de crédit sur ton compte ({detail}).":
        "The service refuses the request: no credit left on your account ({detail}).",
    "Erreur de l'API ({code}) : {detail}": "API error ({code}): {detail}",
    "Impossible de joindre {url} ({reason}). Pour Ollama, vérifie qu'il est lancé.":
        "Could not reach {url} ({reason}). For Ollama, check that it is running.",
    "la commande `claude` (Claude Code) est introuvable": "the `claude` command (Claude Code) was not found",
    "Autre (compatible OpenAI)": "Other (OpenAI-compatible)",
    "Ollama (local, gratuit)": "Ollama (local, free)",
    # -- icône de notification
    "Ouvrir Go Sensei": "Open Go Sensei",
    "Quitter Go Sensei": "Quit Go Sensei",
    # -- partie contre KataGo
    "taille de plateau non gérée : {size}": "unsupported board size: {size}",
    "niveau inconnu : {level}": "unknown level: {level}",
    "couleur inconnue : {color}": "unknown color: {color}",
    "Moi": "Me",
    "aucune partie contre KataGo en cours": "no game against KataGo in progress",
    "C'est à KataGo de jouer": "It's KataGo's turn",
    "Ce n'est pas à toi de jouer": "It's not your turn",
    "Comptage des points…": "Counting the score…",
    "Comptage impossible : {error}": "Counting failed: {error}",
    "KataGo n'a pas pu jouer : {error}": "KataGo could not play: {error}",
    "partie fermée": "game closed",
    "Téléchargement du réseau « humain » de KataGo : {p:.0f} %": "Downloading KataGo's \"human\" network: {p:.0f} %",
    "Démarrage de KataGo…": "Starting KataGo…",
    "réseau « humain » indisponible": "\"human\" network unavailable",
    "réseau « humain » non chargé par KataGo": "\"human\" network not loaded by KataGo",
    "Sensei est désactivé pendant cette partie (option « Sensei en direct »)": "Sensei is disabled during this game (\"Live Sensei\" option)",
}

# Ajouté au rôle de Sensei quand l'interface est en anglais : le rôle reste
# rédigé en français, seule la langue des réponses change.
REPLY_IN_ENGLISH = ("\n\nIMPORTANT — LANGUAGE: the student's interface is in English. Answer in English "
                    "(clear, warm and encouraging) unless the student writes to you in another language, then use theirs. "
                    "Use English Go terms (atari, ko, sente, gote, liberties, territory…).")


def tr(text, **kw):
    """Le texte dans la langue choisie, avec ses champs {…} remplis."""
    if LANG == "en":
        text = EN.get(text, text)
    return text.format(**kw) if kw else text


def system_lang():
    env = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
    return "fr" if env.lower().startswith("fr") else "en"


def set_lang(choice):
    """`choice` : fr, en, ou auto (langue du système). Renvoie la langue retenue."""
    global LANG
    LANG = choice if choice in LANGS else system_lang()
    return LANG


def coach_prompt(base):
    return base + (REPLY_IN_ENGLISH if LANG == "en" else "")


# -- Langue d'un texte (pour garder le carnet dans la langue de la conversation)
LANG_NAMES = {"fr": "French", "en": "English", "es": "Spanish", "de": "German", "it": "Italian",
              "pt": "Portuguese", "nl": "Dutch", "ru": "Russian", "uk": "Ukrainian", "ja": "Japanese",
              "ko": "Korean", "zh": "Chinese", "ar": "Arabic", "he": "Hebrew", "el": "Greek", "th": "Thai"}
_STOPWORDS = {
    "fr": "le la les un une des du de et est que qui pour pas sur dans avec ce cette il elle tu ton ta tes "
          "mais ou en au aux son sa ses ne plus très était avait chacun mes mon ma nos vos après avant toujours "
          "chaque quand si sont être faire bien jamais coup coups groupe groupes pierres libertés",
    "en": "the a an and is are was were that which for not on in with this it you your but or of to "
          "be have has had very their there its after before at my always every when if should never move moves "
          "group groups stones liberties",
    "es": "el la los las un una y es que para no en con este esta tu pero o del al muy está son",
    "de": "der die das ein eine und ist nicht mit für auf dass du dein aber oder zu von im sehr den dem",
    "it": "il lo la gli le un una e è che per non con questo questa tu ma o del della sono molto",
    "pt": "o a os as um uma e é que para não em com este esta você mas ou do da muito são",
    "nl": "de het een en is niet met voor op dat je jouw maar of van te zeer zijn",
}
_STOPWORDS = {k: set(v.split()) for k, v in _STOPWORDS.items()}


def detect_lang(text):
    """Langue probable d'un texte (code ISO), ou None si on ne peut pas trancher."""
    text = re.sub(r"\b[A-HJ-Ta-hj-t]\d{1,2}\b", " ", text or "")  # coordonnées : A1, Q16…
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 15:
        return None
    def share(lo, hi):
        return sum(lo <= ord(c) <= hi for c in letters) / len(letters)
    if share(0x3040, 0x30FF) > 0.05:
        return "ja"
    for code, lo, hi in (("ko", 0xAC00, 0xD7AF), ("zh", 0x4E00, 0x9FFF), ("ar", 0x0600, 0x06FF),
                         ("he", 0x0590, 0x05FF), ("el", 0x0370, 0x03FF), ("th", 0x0E00, 0x0E7F)):
        if share(lo, hi) > 0.3:
            return code
    if share(0x0400, 0x04FF) > 0.3:
        return "uk" if re.search(r"[іїєґІЇЄҐ]", text) else "ru"
    words = re.findall(r"[^\W\d_]+", text.lower())
    scores = {k: sum(w in sw for w in words) for k, sw in _STOPWORDS.items()}
    best = max(scores, key=scores.get)
    second = max(v for k, v in scores.items() if k != best)
    if scores[best] < 2 or scores[best] < 1.5 * second:
        return None
    return best
