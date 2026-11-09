"use strict";
// Langue de l'interface. Les textes sont écrits en français (dans index.html et app.js) ;
// EN donne leur traduction, clé = le texte français exact (espaces regroupés pour le HTML).

const EN = {
  // ------------------------------------------------------------ index.html
  "📂 Parties": "📂 Games",
  "Ce que Sensei a noté sur tes progrès": "What Sensei noted about your progress",
  "📓 Carnet": "📓 Notebook",
  "Suivre la position sur un goban physique filmé par IgOGS": "Follow the position on a physical goban filmed by IgOGS",
  "Aucune partie": "No game",
  "Suggestions IA": "AI suggestions",
  "Territoires": "Territory",
  "Numéros": "Numbers",
  "Moteur d'analyse KataGo": "KataGo analysis engine",
  "Langue de l'interface": "Interface language",
  "Réglages": "Settings",
  "Quitter Go Sensei (arrête tout)": "Quit Go Sensei (stops everything)",
  "Installer le moteur d'analyse": "Install the analysis engine",
  "Go Sensei utilise": "Go Sensei uses",
  ", l'une des meilleures IA de Go (gratuite et open source). Il faut la télécharger une fois (≈ 135 Mo) depuis ses sources officielles.":
    ", one of the best Go AIs (free and open source). It must be downloaded once (≈ 135 MB) from its official sources.",
  "Télécharger KataGo": "Download KataGo",
  "Début (Origine)": "Start (Home)",
  "-5 (Maj+←)": "-5 (Shift+←)",
  "Précédent (←)": "Previous (←)",
  "Suivant (→)": "Next (→)",
  "+5 (Maj+→)": "+5 (Shift+→)",
  "Fin (Fin)": "End (End)",
  "Échap": "Esc",
  "↩ Revenir à la partie": "↩ Back to the game",
  "Score (Noir en haut)": "Score (Black on top)",
  "Arbre des coups": "Move tree",
  "Replier / déplier": "Collapse / expand",
  "Analyse": "Analysis",
  "Tes erreurs dans cette partie": "Your mistakes in this game",
  "clic = y aller": "click = go there",
  "Nouvelle conversation": "New conversation",
  "Pourquoi le dernier coup est-il une erreur ? Qu'est-ce qu'il fallait comprendre ?":
    "Why is the last move a mistake? What was there to understand?",
  "Pourquoi ce coup est mauvais ?": "Why is this move bad?",
  "Que voulait jouer l'IA ici, et pourquoi ? Montre-moi la suite.":
    "What did the AI want to play here, and why? Show me the sequence.",
  "Que voulait l'IA ?": "What did the AI want?",
  "Explique-moi la situation sur le plateau : qui est fort, qui est faible, où sont les enjeux ?":
    "Explain the situation on the board: who is strong, who is weak, where are the stakes?",
  "Explique la situation": "Explain the situation",
  "Fais-moi le bilan de cette partie : mes 3 plus grosses erreurs et la leçon principale à retenir.":
    "Give me a summary of this game: my 3 biggest mistakes and the main lesson to remember.",
  "Bilan de la partie": "Game summary",
  "Pose ta question… (Entrée pour envoyer, Maj+Entrée pour une nouvelle ligne)":
    "Ask your question… (Enter to send, Shift+Enter for a new line)",
  "Envoyer": "Send",
  "Parties": "Games",
  "OGS : pseudo, lien de partie ou numéro": "OGS: username, game link or number",
  "Importer d'OGS": "Import from OGS",
  "Récupérer tes dernières parties OGS": "Fetch your latest OGS games",
  "⟳ Synchroniser": "⟳ Sync",
  "📄 Ouvrir un fichier SGF": "📄 Open an SGF file",
  "Rechercher un adversaire…": "Search for an opponent…",
  "Toutes": "All",
  "Astuce : tu peux aussi glisser-déposer un fichier .sgf n'importe où dans la fenêtre.":
    "Tip: you can also drag and drop an .sgf file anywhere in the window.",
  "Professeur IA": "AI tutor",
  "Lancement": "Launch",
  "À propos": "About",
  "Optionnel : sans IA, tu gardes le plateau, l'analyse KataGo et la revue des erreurs.":
    "Optional: without AI you keep the board, the KataGo analysis and the mistake review.",
  "Fournisseur": "Provider",
  "Aucun (désactivé)": "None (disabled)",
  "Claude Code (abonnement Claude, sans clé)": "Claude Code (Claude subscription, no key)",
  "Claude via l'API Anthropic (clé d'API)": "Claude via the Anthropic API (API key)",
  "ChatGPT, DeepSeek, Ollama, Mistral, Gemini… (compatible OpenAI)":
    "ChatGPT, DeepSeek, Ollama, Mistral, Gemini… (OpenAI-compatible)",
  "Adresse de l'API": "API address",
  "Clé d'API": "API key",
  "Modèle": "Model",
  "par défaut": "default",
  "Lister": "List",
  "Utilise la commande": "Uses the",
  "installée sur ce PC et ton abonnement. Elle n'a accès qu'au plateau (pas à tes fichiers).":
    "command installed on this PC and your subscription. It only has access to the board (not your files).",
  "Ollama : gratuit et local, mais il faut un modèle qui gère les « outils » (ex. qwen3, llama3.1…). Les petits modèles expliquent moins bien.":
    "Ollama: free and local, but you need a model that supports “tools” (e.g. qwen3, llama3.1…). Small models explain less well.",
  "Calcul": "Compute",
  "Automatique (carte graphique si possible)": "Automatic (GPU if possible)",
  "Carte graphique (OpenCL)": "GPU (OpenCL)",
  "Processeur": "CPU",
  "Réseau de neurones": "Neural network",
  "Profondeur de l'analyse en direct (visites, 0 = auto)": "Live analysis depth (visits, 0 = auto)",
  "Profondeur de la revue de partie (visites par coup, 0 = auto)": "Game review depth (visits per move, 0 = auto)",
  "KataGo personnel (optionnel)": "Custom KataGo (optional)",
  "/chemin/vers/katago": "/path/to/katago",
  "Réseau de neurones personnel (optionnel, remplace le choix ci-dessus)":
    "Custom neural network (optional, overrides the choice above)",
  "/chemin/vers/reseau.bin.gz": "/path/to/network.bin.gz",
  "Redémarrer KataGo": "Restart KataGo",
  "Télécharger / réparer": "Download / repair",
  "Pseudo OGS": "OGS username",
  "ton pseudo sur online-go.com": "your username on online-go.com",
  "Récupérer mes nouvelles parties OGS au lancement": "Fetch my new OGS games at launch",
  "Nombre de parties à récupérer (les plus récentes, 0 = toutes)": "Number of games to fetch (most recent, 0 = all)",
  "Détection automatique": "Automatic detection",
  "Désactivé": "Disabled",
  "Dossier personnalisé": "Custom folder",
  "Dossier de sauvegarde Conquest": "Conquest save folder",
  "Autres dossiers de parties SGF (un par ligne)": "Other SGF game folders (one per line)",
  "/home/moi/Go/parties": "/home/me/Go/games",
  "Ouvrir Go Sensei dans": "Open Go Sensei in",
  "Mon navigateur par défaut (Firefox, Zen…)": "My default browser (Firefox, Zen…)",
  "Une fenêtre dédiée (Chromium, sans barre d'adresse)": "A dedicated window (Chromium, no address bar)",
  "Continuer en arrière-plan quand la fenêtre est fermée": "Keep running in the background when the window is closed",
  "Icône dans la zone de notification (clic : ouvrir, menu : quitter)": "System tray icon (click: open, menu: quit)",
  "Lancer Go Sensei avec ma session (en arrière-plan)": "Start Go Sensei with my session (in the background)",
  "En arrière-plan, rouvre Go Sensei avec l'icône de notification ou depuis le menu des applications. Pour l'arrêter complètement : bouton ⏻ ou « Quitter » dans le menu de l'icône. Les changements d'icône et de mode s'appliquent au prochain lancement.":
    "In the background, reopen Go Sensei with the tray icon or from the applications menu. To stop it completely: the ⏻ button or “Quit” in the icon menu. Icon and mode changes apply at the next launch.",
  "Hyprland, Sway et certains autres gestionnaires de fenêtres ignorent les lancements automatiques standards : ajoute plutôt":
    "Hyprland, Sway and some other window managers ignore standard autostart entries: add",
  "aux commandes lancées au démarrage de ta session (ex.": "to the commands run when your session starts instead (e.g.",
  "Enregistrer": "Save",
  "📓 Carnet de progression": "📓 Progress notebook",
  "✏️ Modifier": "✏️ Edit",
  "Annuler": "Cancel",
  "Ce que Sensei retient de tes parties : thèmes récurrents, progrès, réflexes à ancrer. Il le relit au début de chaque conversation. Tu peux corriger, supprimer ou ajouter des notes (une ligne par note, « - AAAA-MM-JJ : texte »).":
    "What Sensei remembers from your games: recurring themes, progress, habits to build. It rereads it at the start of every conversation. You can correct, delete or add notes (one line per note, “- YYYY-MM-DD: text”).",
  "Rechercher (ex. vie et mort, atari, zone…)": "Search (e.g. life and death, atari, area…)",
  "Go Sensei est fermé": "Go Sensei is closed",
  "Tu peux fermer cette fenêtre ou cet onglet.": "You can close this window or tab.",
  "Dépose ton fichier .sgf": "Drop your .sgf file",

  // ------------------------------------------------------------ app.js
  "Noir": "Black",
  "Blanc": "White",
  "Erreur {status}": "Error {status}",
  "{n} prisonnier": "{n} capture",
  "{n} prisonniers": "{n} captures",
  "Coup <b>{n}</b> <span class=\"muted\">(variante depuis le coup {from})</span>":
    "Move <b>{n}</b> <span class=\"muted\">(variation from move {from})</span>",
  "Coup <b>{n}</b> / {total}": "Move <b>{n}</b> / {total}",
  " · passe": " · pass",
  "Analyse en cours…": "Analysing…",
  "{n} visites": "{n} visits",
  "Au trait : <b>{color}</b>": "To play: <b>{color}</b>",
  "équilibré": "even",
  "<b>{color}</b> mène de {pts} pts": "<b>{color}</b> leads by {pts} pts",
  "victoire Noir {pct}%": "Black wins {pct}%",
  "Coup joué ensuite dans la partie (cercle bleu) :": "Move played next in the game (blue circle):",
  "bon coup": "good move",
  "Survol : voir la suite · Clic : jouer ce coup": "Hover: see the sequence · Click: play this move",
  "meilleur : {move}": "best: {move}",
  "{n} erreur": "{n} mistake",
  "{n} erreurs": "{n} mistakes",
  "revue terminée": "review done",
  "revue : erreur": "review: error",
  "revue KataGo : {done}/{total}": "KataGo review: {done}/{total}",
  "Aucune erreur notable 🎉": "No notable mistake 🎉",
  "Analyse de la partie en cours…": "Analysing the game…",
  "gaffe": "blunder",
  "erreur": "mistake",
  "imprécision": "inaccuracy",
  "{color} a joué {move} ({level}, −{loss} pts). Mieux : {best}. Clic : position juste avant ce coup.":
    "{color} played {move} ({level}, −{loss} pts). Better: {best}. Click: position just before this move.",
  "variante": "variation",
  "Noir +{n}": "Black +{n}",
  "Blanc +{n}": "White +{n}",
  " · variante de Sensei": " · Sensei's variation",
  " · ta variante": " · your variation",
  "Début": "Start",
  "Coup {n} · {color} {move}{who}": "Move {n} · {color} {move}{who}",
  "\nClic droit : supprimer cette variante": "\nRight-click: delete this variation",
  "Supprimer cette variante (et sa suite) ?": "Delete this variation (and what follows)?",
  "{n} variante · bleu = toi, vert = Sensei · clic : y aller · ↑↓ : changer de variante":
    "{n} variation · blue = you, green = Sensei · click: go there · ↑↓: switch variation",
  "{n} variantes · bleu = toi, vert = Sensei · clic : y aller · ↑↓ : changer de variante":
    "{n} variations · blue = you, green = Sensei · click: go there · ↑↓: switch variation",
  "joue un coup sur le plateau pour créer une variante": "play a move on the board to create a variation",
  "Déplier l'analyse": "Expand the analysis",
  "Replier l'analyse": "Collapse the analysis",
  "regarde le plateau": "looks at the board",
  "lit la revue de la partie": "reads the game review",
  "va au coup": "goes to a move",
  "joue une variante": "plays a variation",
  "recule": "steps back",
  "revient à la partie": "goes back to the game",
  "analyse avec KataGo": "analyses with KataGo",
  "compare des coups": "compares moves",
  "annote le plateau": "annotates the board",
  "efface les annotations": "clears the annotations",
  "liste les parties": "lists the games",
  "ouvre une partie": "opens a game",
  "lit ton carnet": "reads your notebook",
  "note dans ton carnet": "writes in your notebook",
  "Le professeur IA est désactivé.": "The AI tutor is disabled.",
  "Le plateau, l'analyse KataGo et la revue de tes erreurs fonctionnent sans lui. Pour avoir des explications en français, choisis une IA (Claude, ChatGPT, DeepSeek, Ollama…).":
    "The board, the KataGo analysis and the review of your mistakes work without it. For explanations in plain English, choose an AI (Claude, ChatGPT, DeepSeek, Ollama…).",
  "Configurer une IA": "Set up an AI",
  "Pose-moi n'importe quelle question sur la position affichée.": "Ask me anything about the position shown.",
  "Je vois le même plateau que toi : je peux jouer des variantes, dessiner dessus et vérifier avec KataGo.":
    "I see the same board you do: I can play variations, draw on it and check with KataGo.",
  "Astuce : clique sur une erreur (en haut) pour te placer juste avant, puis demande « pourquoi ? ».":
    "Tip: click a mistake (above) to jump just before it, then ask “why?”.",
  "Ouvrir le carnet": "Open the notebook",
  "Aller au coup {n}": "Go to move {n}",
  "Noté dans ton carnet": "Noted in your notebook",
  "Cette position n'existe plus (variante supprimée ?)": "This position no longer exists (variation deleted?)",
  "Commencer une nouvelle conversation ? (Ton carnet de progression est conservé.)":
    "Start a new conversation? (Your progress notebook is kept.)",
  "Toutes sources": "All sources",
  "Victoire": "Win",
  "Défaite": "Loss",
  "{n} coups": "{n} moves",
  "Import depuis OGS en cours… (peut prendre une minute)": "Importing from OGS… (may take a minute)",
  "{user} : {n} nouvelle(s) partie(s).": "{user}: {n} new game(s).",
  "Partie importée.": "Game imported.",
  "Échec de l'import.": "Import failed.",
  "{name} n'est pas un fichier .sgf": "{name} is not an .sgf file",
  "Aucune note ne correspond.": "No note matches.",
  "Le carnet est vide : Sensei y notera tes progrès au fil des séances.":
    "The notebook is empty: Sensei will note your progress there session after session.",
  "Sans date": "Undated",
  "Calibrage de la carte graphique…": "Tuning the GPU…",
  "KataGo a un problème": "KataGo has a problem",
  "Première utilisation : KataGo optimise ses calculs pour ta carte graphique (1 à 2 minutes, une seule fois).":
    "First use: KataGo is optimising its computations for your GPU (1 to 2 minutes, once).",
  "Réessayer": "Retry",
  " — ⚙ Réglages → KataGo pour changer de calcul ou de réseau.": " — ⚙ Settings → KataGo to change compute or network.",
  "API compatible OpenAI": "OpenAI-compatible API",
  "Trouvé : {path}": "Found: {path}",
  "Jeu non détecté sur ce PC.": "Game not detected on this PC.",
  "✓ commande claude trouvée.": "✓ claude command found.",
  "⚠ commande claude introuvable.": "⚠ claude command not found.",
  "Réglages : <code>{config}</code>": "Settings: <code>{config}</code>",
  "Données (revues, parties OGS, carnet de l'élève, KataGo) : <code>{data}</code>":
    "Data (reviews, OGS games, student notebook, KataGo): <code>{data}</code>",
  "Analyse : {katago} (licence MIT). Parties en ligne : {ogs}.": "Analysis: {katago} (MIT licence). Online games: {ogs}.",
  "aucun": "none",
  "État : <b>{label}</b>": "Status: <b>{label}</b>",
  "Programme(s) : {bins}": "Program(s): {bins}",
  "Réseau : {model}": "Network: {model}",
  "Automatique (conseillé ici : {name})": "Automatic (recommended here: {name})",
  " (à télécharger, {size})": " (to download, {size})",
  "{n} Mo": "{n} MB",
  "réseau personnel": "custom network",
  "Conseillé : {name} ({why}). En service : {used}.": "Recommended: {name} ({why}). In use: {used}.",
  "Une clé est enregistrée pour ce service (laisser vide pour la garder).":
    "A key is saved for this service (leave empty to keep it).",
  "Aucune clé enregistrée pour ce service.": "No key saved for this service.",
  "Recherche des modèles…": "Looking up models…",
  "{n} modèle(s) : clique dans le champ Modèle pour choisir.": "{n} model(s): click the Model field to choose.",
  "Impossible de lister les modèles (adresse ou clé ?).": "Could not list models (address or key?).",
  "✓ Enregistré": "✓ Saved",
  "Échec de l'enregistrement.": "Saving failed.",
  "Quitter Go Sensei ? (KataGo et le professeur IA seront arrêtés)": "Quit Go Sensei? (KataGo and the AI tutor will be stopped)",
  "serveur déconnecté…": "server disconnected…",
  // Sources de parties (libellés envoyés par le serveur)
  "Importées": "Imported",
  "Conquest · récentes": "Conquest · recent",
  "Conquest · sauvegardées": "Conquest · saved",
  "Conquest · campagne": "Conquest · campaign",
  "Conquest · importées": "Conquest · imported",
  // ------------------------------------------------------------ partie contre KataGo
  "Jouer une partie contre KataGo sur ce PC": "Play a game against KataGo on this PC",
  "⚔ Jouer": "⚔ Play",
  "Courbe, évaluation, suggestions et erreurs pendant la partie": "Graph, evaluation, suggestions and mistakes during the game",
  "Aide en direct": "Live help",
  "Pouvoir poser des questions à Sensei pendant la partie": "Ask Sensei questions during the game",
  "Sensei en direct": "Live Sensei",
  "Revenir au dernier coup de la partie en cours": "Back to the last move of the current game",
  "⏭ Partie en cours": "⏭ Current game",
  "Passer": "Pass",
  "Abandonner": "Resign",
  "⚔ Jouer contre KataGo": "⚔ Play against KataGo",
  "Plateau": "Board",
  "Ta couleur": "Your color",
  "Noir (tu commences)": "Black (you start)",
  "Au hasard": "Random",
  "Niveau de KataGo": "KataGo's level",
  "Aide en direct : courbe, évaluation, suggestions et erreurs pendant la partie": "Live help: graph, evaluation, suggestions and mistakes during the game",
  "Sensei en direct : pouvoir lui poser des questions pendant la partie": "Live Sensei: ask it questions during the game",
  "Les deux se changent pendant la partie. À la fin, toute l'analyse s'affiche. Règles japonaises, komi 6,5. Pendant la partie, tu peux revenir en arrière et essayer des variantes : seul un coup joué au bout de la partie compte.": "Both can be changed during the game. At the end, the full analysis is shown. Japanese rules, komi 6.5. During the game you can go back and try variations: only a move played at the end of the game counts.",
  "Commencer la partie": "Start the game",
  "Vérifier en profondeur le coup affiché et corriger la courbe": "Check the displayed move in depth and correct the graph",
  "La revue survole chaque coup. Quand tu regardes un coup de la partie, KataGo analyse aussi en profondeur la position d'avant et celle d'après, et corrige la courbe et la liste des erreurs avec ce résultat plus fiable.": "The review skims every move. When you look at a move of the game, KataGo also analyses the positions before and after it in depth, and corrects the graph and the list of mistakes with this more reliable result.",
  " · {n} coups vérifiés en profondeur": " · {n} moves checked in depth",
  "par abandon": "by resignation",
  "de {pts} points": "by {pts} points",
  "Tu as gagné {how} !": "You won {how}!",
  "KataGo a gagné {how}.": "KataGo won {how}.",
  "{color} gagne {how}": "{color} wins {how}",
  "Contre <b>{level}</b> · tu joues {color}": "Against <b>{level}</b> · you play {color}",
  "Partie terminée": "Game over",
  "KataGo réfléchit…": "KataGo is thinking…",
  "À toi de jouer": "Your move",
  "À toi de jouer (au dernier coup de la partie)": "Your move (at the last move of the game)",
  "Abandonner la partie ?": "Resign the game?",
  "KataGo à pleine puissance : imbattable, pour voir comment joue la machine.": "KataGo at full strength: unbeatable, to see how the machine plays.",
  "KataGo joue comme un humain de ce niveau, avec les erreurs typiques de ce niveau.": "KataGo plays like a human of this level, with the typical mistakes of this level.",
  "Au premier lancement, Go Sensei télécharge le réseau « humain » de KataGo (≈ {n} Mo).": "The first time, Go Sensei downloads KataGo's \"human\" network (≈ {n} MB).",
  "Préparation de la partie…": "Preparing the game…",
  "Contre KataGo": "Against KataGo",
};

let LANG = (() => {
  try { const v = localStorage.getItem("gs-lang"); if (v === "fr" || v === "en") return v; } catch {}
  return (navigator.language || "").toLowerCase().startsWith("fr") ? "fr" : "en";
})();

function t(fr, vars) {
  let s = LANG === "en" && Object.prototype.hasOwnProperty.call(EN, fr) ? EN[fr] : fr;
  if (vars) s = s.replace(/\{(\w+)\}/g, (all, k) => (k in vars ? vars[k] : all));
  return s;
}

// Libellé d'une position montrée par Sensei (rédigé en français par le serveur, gardé dans l'historique).
function tNodeLabel(label) {
  if (LANG !== "en") return label;
  return label.replace(/^variante après le coup (\d+) : /, "variation after move $1: ").replace(/^coup (\d+)$/, "move $1");
}

// Textes fixes de la page : relevés une fois (en français), puis réécrits à chaque changement de langue.
const I18N_ATTRS = ["title", "placeholder", "data-q"];
const STATIC_TEXT = [], STATIC_ATTRS = [];
(function collectStatic() {
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.parentElement.closest("script, style, svg") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const key = n.nodeValue.replace(/\s+/g, " ").trim();
    if (key && Object.prototype.hasOwnProperty.call(EN, key)) {
      const [, lead, , trail] = n.nodeValue.match(/^(\s*)([\s\S]*?)(\s*)$/);
      STATIC_TEXT.push({ node: n, key, lead, trail });
    }
  }
  for (const el of document.querySelectorAll(I18N_ATTRS.map((a) => `[${a}]`).join(","))) {
    for (const a of I18N_ATTRS) {
      const v = el.getAttribute(a);
      if (v && Object.prototype.hasOwnProperty.call(EN, v)) STATIC_ATTRS.push({ el, a, key: v });
    }
  }
})();

function applyStaticLang() {
  document.documentElement.lang = LANG;
  for (const { node, key, lead, trail } of STATIC_TEXT) node.nodeValue = lead + t(key) + trail;
  for (const { el, a, key } of STATIC_ATTRS) el.setAttribute(a, t(key));
  const sel = document.getElementById("opt-lang");
  if (sel) sel.value = LANG;
}

function setLang(lang) {
  LANG = lang === "en" ? "en" : "fr";
  try { localStorage.setItem("gs-lang", LANG); } catch {}
  applyStaticLang();
}

applyStaticLang();
