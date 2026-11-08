# Go Sensei

> [!NOTE]
> Main repository: [Forgejo](https://forgejo.aaaoz.fr/Rimso/go-sensei) · Mirror: [GitHub](https://github.com/Rimsoo/go-sensei) (synced automatically).
> Issues and feedback are welcome on GitHub.

**A KataGo analysis board + an AI tutor that explains the *why*, in the same window.**

You know the rules of Go but don't understand why the AI thinks your move is bad? Go Sensei analyses your games
(OGS, SGF files, The Conquest of Go…), shows you your mistakes, and — if you want — an AI tutor explains them to
you. It sees the same board you do, plays out variations, draws on it and checks every claim with KataGo.

The interface comes in **English and French**: pick **EN** or **FR** in the top bar. The choice is saved, and the
AI tutor answers in the same language. Until you choose, Go Sensei follows the system language. Below, labels are
given in English with the French text in italics.

## Installation (Linux)

1. Download `GoSensei-x86_64.AppImage` from the [Releases](../../releases).
2. Make it executable and run it:
   ```sh
   chmod +x GoSensei-x86_64.AppImage
   ./GoSensei-x86_64.AppImage
   ```
3. Optional: `./install.sh GoSensei-x86_64.AppImage` adds a `go-sensei` command and an entry in the applications
   menu. `./install.sh -u` uninstalls.

The AppImage bundles everything: Python, KataGo (GPU via OpenCL, or CPU) and two neural networks. On first launch on
a GPU, KataGo tunes itself for 1 to 2 minutes, once.

The network is picked to suit the PC: the strongest (b18) on a GPU, a medium network (b10) on CPU, where b18 would
be 10 to 15 times slower. On a small GPU where b18 doesn't fit (GeForce 940MX, 2 GB…), Go Sensei switches to b10 on
its own, which there remains about 4 times faster than on the CPU. ⚙ Settings (*Réglages*) → KataGo shows the
recommended network and why, and lets you pick another (b6, b10, b15, b18, downloaded as needed) or a custom file.

Go Sensei opens in your browser by default and keeps running in the background when you close the tab, with an icon
in the system tray (like Sunshine or Steam): click to reopen, menu to quit. Launching the app again from the menu
simply reopens the interface. **⏻ in the interface or "Quit" (*Quitter*) in the tray icon menu stops everything**:
server, KataGo and AI.

In ⚙ Settings → Launch (*Lancement*): a dedicated window without an address bar (Chromium, Chrome, Brave, Edge or
Vivaldi), automatic shutdown when the window closes, and start with the session.

## Features

- **Your games**:
  - OGS import by username (case-insensitive), link or game number, with automatic sync at launch;
  - `.sgf` files to open or drag and drop;
  - folders to watch;
  - *The Conquest of Go* games (Steam/Proton), detected automatically.

  The list shows the real dates, ranks and win/loss from your point of view, with search and filters.
- **Automatic review** of every game:
  - mistakes are classified as *inaccuracy*, *mistake* or *blunder*, with the points lost;
  - a graph shows how the score evolved;
  - one click puts you right before the mistake.
- **Live analysis**:
  - the best moves are coloured by quality, and hovering shows the expected sequence;
  - the move actually played is circled;
  - a territory map also shows dead stones;
  - you can play variations by clicking.
- **Move tree**:
  - every variation you play (click on the board) or that Sensei shows becomes a branch, saved with the game and its annotations;
  - KataGo evaluates every move of the variations, and the graph draws the displayed variation in orange over the game;
  - click a node to go there, ↑/↓ to switch between variations, right-click to delete a variation.
- **AI tutor (optional)**, chosen in ⚙ Settings:
  - **Claude Code**: Claude subscription, no API key, if the `claude` command is installed;
  - **Anthropic API** (Claude): API key;
  - **OpenAI-compatible**: OpenAI, DeepSeek, Mistral, Gemini, OpenRouter, or **Ollama** locally and for free
    (with a model that supports tools, e.g. `qwen3`).

  Each game has its own conversation. OpenAI-compatible models (Ollama included) receive, with each question, the
  facts KataGo computed on the displayed position; a small local model is still much less reliable than Claude at
  explaining the "why". Each API key is only sent to the service it was entered for.

  The **progress notebook** (📓 *Carnet* button) gathers what Sensei remembers from your games: recurring themes,
  progress, habits to build. You can read, search and edit it; each new note also appears under Sensei's message.

  The AI only has access to the board: no shell, no files. Each of its messages keeps links to the positions and
  variations it showed: one click takes you back to its explanation. It also keeps a notebook of your progress from
  one session to the next.

## Physical goban (IgOGS)

With [IgOGS](https://forgejo.aaaoz.fr/Rimso/IgOGS) running (a webcam filming your goban), click **📷 Goban**
in the top bar: the displayed position is mirrored on your physical board (IgOGS tells you which stones to
place or remove), and moves played on the board are played in Go Sensei — as variations, analysed live.
Removing the last stones goes back. The setting is saved; the IgOGS address is `goban.url` in the config
(default `http://127.0.0.1:8742`).

## Shortcuts

| Key | Action |
|---|---|
| ← / → | previous / next move (Shift = 5 moves); the mouse wheel over the board works too |
| ↑ / ↓ | previous / next variation at the same move |
| Home / End | start / end of the game |
| Esc | back to the game (or close a dialog) |
| Enter | send the message (Shift+Enter = new line) |

## From source

```sh
git clone https://forgejo.aaaoz.fr/Rimso/go-sensei.git && cd go-sensei
python3 go-sensei.py              # Python ≥ 3.10, no required dependencies
pip install anthropic             # only for the "Anthropic API" provider
./build-appimage.sh               # builds the AppImage (BUNDLE_KATAGO=0 for a light build)
```

From source, KataGo is downloaded from the interface on first launch: official v1.16.3 binary and a network suited
to the PC (`kata1-b18c384nbt` or `kata1-b10c128`), from GitHub and katagotraining.org. Launch options:
`--no-window` (server only), `--port N`, `--stop`.

## Where are the files?

- Settings: `~/.config/go-sensei/config.json` (mode 600, may contain an API key). The language is `ui.lang`:
  `auto`, `fr` or `en`.
- Data: `~/.local/share/go-sensei/`. It holds the cached reviews, OGS and imported games, chat history, the
  student's notebook (`carnet-eleve.md`), KataGo if it was downloaded, and the logs.

## Architecture

- `gosensei/server.py`: local HTTP server (Python standard library), on 127.0.0.1 only. The interface updates in
  real time (SSE). Requests coming from other sites are rejected.
- `gosensei/katago.py`: finds, downloads and runs KataGo (JSON `analysis` protocol), with automatic GPU → CPU
  fallback.
- `gosensei/study.py`: displayed position, variations, live analysis, full review.
- `gosensei/mcp.py`: the board tools, exposed over MCP at `/mcp` for Claude Code and called directly by the other
  providers.
- `gosensei/ai.py`: AI providers.
- `gosensei/goban_link.py`: physical goban through IgOGS (driver protocol client).
- `gosensei/games.py`: game library (OGS, SGF, Conquest).
- `gosensei/i18n.py` and `gosensei/static/i18n.js`: English translations. The code is written in French, and each
  dictionary maps the exact French text to its English version.

## License

MIT. KataGo and its networks are distributed under their own licenses (see `opt/katago/LICENSE-KataGo.txt` in the
AppImage and https://github.com/lightvector/KataGo).
