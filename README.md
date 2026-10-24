# Go Sensei

**Plateau d'analyse KataGo + professeur IA qui t'explique le *pourquoi*, dans la même fenêtre.**

Tu connais les règles du Go mais tu ne comprends pas pourquoi l'IA trouve ton coup mauvais ? Go Sensei
analyse tes parties (OGS, fichiers SGF, The Conquest of Go…), te montre tes erreurs, et — si tu le
souhaites — un professeur IA te les explique en français. Il voit le même plateau que toi, joue des
variantes, dessine dessus et vérifie chaque affirmation avec KataGo.

*English summary below.*

## Installation (Linux)

1. Télécharge `GoSensei-x86_64.AppImage` depuis les [Releases](../../releases).
2. Rends-le exécutable et lance-le :
   ```sh
   chmod +x GoSensei-x86_64.AppImage
   ./GoSensei-x86_64.AppImage
   ```
3. Optionnel : `./install.sh GoSensei-x86_64.AppImage` ajoute la commande `go-sensei` et une entrée dans le menu
   des applications. `./install.sh -u` désinstalle.

L'AppImage embarque tout : Python, KataGo (carte graphique via OpenCL, ou processeur) et deux réseaux de neurones.
Au premier lancement sur carte graphique, KataGo se calibre pendant 1 à 2 minutes, une seule fois.

Le réseau est choisi selon le PC : le plus fort (b18) sur carte graphique, un réseau moyen (b10) sur processeur,
où b18 serait 10 à 15 fois plus lent. Sur une petite carte graphique où b18 ne tient pas (GeForce 940MX, 2 Go…),
Go Sensei passe tout seul à b10, qui y reste environ 4 fois plus rapide que sur le processeur. ⚙ Réglages → KataGo indique le réseau conseillé et pourquoi, et permet d'en
choisir un autre (b6, b10, b15, b18, téléchargé au besoin) ou un fichier personnel.

Go Sensei s'ouvre dans ton navigateur par défaut et continue en arrière-plan quand tu fermes l'onglet, avec une
icône dans la zone de notification (comme Sunshine ou Steam) : clic pour rouvrir, menu pour quitter. Relancer
l'appli depuis le menu rouvre simplement l'interface. **⏻ dans l'interface ou « Quitter » dans le menu de l'icône
arrête tout** : serveur, KataGo et IA.

Dans ⚙ Réglages → Lancement : fenêtre dédiée sans barre d'adresse (Chromium, Chrome, Brave, Edge ou Vivaldi),
arrêt automatique à la fermeture de la fenêtre, et lancement avec la session.

## Fonctionnalités

- **Tes parties** :
  - import OGS par pseudo (insensible à la casse), lien ou numéro, avec synchronisation automatique au lancement ;
  - fichiers `.sgf` à ouvrir ou glisser-déposer ;
  - dossiers à surveiller ;
  - parties de *The Conquest of Go* (Steam/Proton), détectées automatiquement.

  La liste montre les vraies dates, les rangs et victoire/défaite de ton point de vue, avec recherche et filtres.
- **Revue automatique** de chaque partie :
  - les erreurs sont classées *imprécision*, *erreur* ou *gaffe*, avec les points perdus ;
  - un graphique montre l'évolution du score ;
  - un clic te place juste avant l'erreur.
- **Analyse en direct** :
  - les meilleurs coups sont colorés selon leur qualité, et un survol affiche la suite prévue ;
  - le coup réellement joué est entouré ;
  - une carte des territoires montre aussi les pierres mortes ;
  - tu peux jouer des variantes en cliquant.
- **Arbre des coups** :
  - chaque variante que tu joues (clic sur le plateau) ou que Sensei montre devient une branche, sauvegardée avec la partie et ses annotations ;
  - KataGo évalue chaque coup des variantes, et le graphique trace la variante affichée en orange par-dessus la partie ;
  - clic sur un nœud pour y aller, ↑/↓ pour passer d'une variante à l'autre, clic droit pour supprimer une variante.
- **Professeur IA (optionnel)**, au choix dans ⚙ Réglages :
  - **Claude Code** : abonnement Claude, sans clé d'API, si la commande `claude` est installée ;
  - **API Anthropic** (Claude) : clé d'API ;
  - **compatible OpenAI** : OpenAI, DeepSeek, Mistral, Gemini, OpenRouter, ou **Ollama** en local et gratuit
    (avec un modèle qui gère les outils, ex. `qwen3`).

  Chaque partie a sa propre conversation. Les modèles compatibles OpenAI (dont Ollama) reçoivent avec chaque
  question les faits calculés par KataGo sur la position affichée ; un petit modèle local reste toutefois bien moins
  fiable que Claude pour expliquer le « pourquoi ». Chaque clé d'API n'est envoyée qu'au service pour lequel elle a
  été saisie.

  Le **carnet de progression** (bouton 📓 Carnet) rassemble ce que Sensei retient de tes parties : thèmes
  récurrents, progrès, réflexes à ancrer. Tu peux le lire, le rechercher et le modifier ; chaque nouvelle note
  apparaît aussi sous le message de Sensei.

  L'IA n'a accès qu'au plateau : aucun shell, aucun fichier. Chacun de ses messages garde des liens vers les
  positions et variantes qu'elle a montrées : un clic te ramène à son explication. Elle tient aussi un carnet
  de tes progrès d'une séance à l'autre.

## Raccourcis

| Touche | Action |
|---|---|
| ← / → | coup précédent / suivant (Maj = 5 coups) ; la molette sur le plateau marche aussi |
| ↑ / ↓ | variante précédente / suivante au même coup |
| Origine / Fin | début / fin de partie |
| Échap | revenir à la partie (ou fermer une fenêtre) |
| Entrée | envoyer le message (Maj+Entrée = nouvelle ligne) |

## Depuis les sources

```sh
git clone https://github.com/Rimsoo/go-sensei && cd go-sensei
python3 go-sensei.py              # Python ≥ 3.10, aucune dépendance obligatoire
pip install anthropic             # seulement pour le fournisseur « API Anthropic »
./build-appimage.sh               # construit l'AppImage (BUNDLE_KATAGO=0 pour une version légère)
```

Depuis les sources, KataGo est téléchargé depuis l'interface au premier lancement : binaire officiel v1.16.3
et réseau adapté au PC (`kata1-b18c384nbt` ou `kata1-b10c128`), depuis GitHub et katagotraining.org. Options de lancement :
`--no-window` (serveur seul), `--port N`, `--stop`.

## Où sont les fichiers ?

- Réglages : `~/.config/go-sensei/config.json` (droits 600, peut contenir une clé d'API).
- Données : `~/.local/share/go-sensei/`. On y trouve les revues en cache, les parties OGS et importées, l'historique
  du chat, le carnet de l'élève (`carnet-eleve.md`), KataGo s'il a été téléchargé, et les journaux.

## Architecture

- `gosensei/server.py` : serveur HTTP local (bibliothèque standard Python), uniquement sur 127.0.0.1. L'interface
  se met à jour en temps réel (SSE). Les requêtes venant d'autres sites sont refusées.
- `gosensei/katago.py` : localise, télécharge et lance KataGo (protocole JSON `analysis`), avec repli
  automatique GPU → CPU.
- `gosensei/study.py` : position affichée, variantes, analyse en direct, revue complète.
- `gosensei/mcp.py` : les outils du plateau, exposés en MCP sur `/mcp` pour Claude Code et appelés directement
  par les autres fournisseurs.
- `gosensei/ai.py` : fournisseurs d'IA.
- `gosensei/games.py` : bibliothèque de parties (OGS, SGF, Conquest).

---

## English summary

Go Sensei is a local KataGo analysis board with an optional AI tutor for Go beginners.

- **Game sources:** your OGS games, SGF files, and The Conquest of Go saves.
- **Review:** it reviews every move, shows your mistakes in points lost, and gives a live analysis with
  territory maps.
- **AI tutor:** it explains in plain language, while driving the same board you see (variations, drawings).
  Supported providers: Claude Code (subscription), the Anthropic API, any OpenAI-compatible API (OpenAI,
  DeepSeek, Mistral, Gemini, OpenRouter) and local Ollama.
- **Packaging:** a single AppImage for Linux, with KataGo bundled. The UI is in French for now.

## Licence

MIT. KataGo and its networks are distributed under their own licences (see `opt/katago/LICENSE-KataGo.txt` in the
AppImage and https://github.com/lightvector/KataGo).
