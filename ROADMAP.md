# Chess App Roadmap

> A living document tracking planned features, ideas, and future direction for the chess application.
>
> Last updated: 2026-02-08

## Current State

The app is a cross-platform (desktop/web) chess application built with **Flet** and **python-chess**, featuring:

- Human vs Human, Human vs AI, and AI vs AI game modes
- Three AI bots (SimpleBot, BotBot, MinimaxBot) with varying difficulty
- Click-to-move with legal move highlighting
- Move history, evaluation bar, and status display
- Opening explorer with common lines and popularity indicators
- Hint system showing top 3 best moves
- Configurable chess clock (1/3/5/10 min + unlimited)
- 58 puzzles and scenarios with difficulty ratings, completion/failure conditions, and progress tracking
- Undo, new game, and FEN support
- Comprehensive test suite (80%+ coverage)

---

## Phase 1 — Polish & Quality of Life

_Quick wins that improve the day-to-day experience._

### Sound Effects
- Play distinct sounds for moves, captures, checks, castling, and game-over events
- Add a mute/volume toggle in the UI

### Board Themes & Piece Sets
- Multiple board color schemes (classic green/white, blue, wood, dark mode)
- Alternative piece sets beyond Cburnett (e.g., Merida, Alpha, pixel art)
- Theme picker accessible from the game screen

### Drag-and-Drop Movement
- Support drag-and-drop as an alternative to click-to-move
- Visual feedback while dragging (ghost piece, drop target highlighting)

### Pawn Promotion Picker
- Show a selection dialog when a pawn promotes (Queen, Rook, Bishop, Knight)
- Replace the current auto-queen behavior

### Move Animation
- Smooth sliding animation when pieces move between squares
- Animate captures and castling moves

### PGN Export & Import
- Export the current game to PGN format (copy to clipboard or save to file)
- Import PGN files to replay or continue games
- Include metadata (player names, date, result, time control)

---

## Phase 2 — Deeper Gameplay

_Features that add strategic depth and learning tools._

### Stockfish Integration
- Bundle or detect a local Stockfish binary
- Use Stockfish for a "Hard" AI difficulty option
- Power the hint system and analysis mode with engine evaluations
- Show engine depth, nodes searched, and principal variation

### Game Analysis Mode
- Post-game review: step through moves with engine evaluation at each position
- Classify moves as best, good, inaccuracy, mistake, or blunder
- Show arrows for the engine's preferred continuation
- Summary statistics (accuracy %, blunder count, average centipawn loss)

### ELO Rating System ✅
- ~~Local ELO tracking across games played against bots~~
- ~~Adjust bot difficulty to approximate ELO ranges~~
- ~~Display rating history and progress chart~~
- Implemented in `elo.py` with standard ELO formula, dynamic K-factor, persistent JSON profile, and difficulty recommendation

### Puzzle Rating & Progression ✅
- ~~Assign difficulty ratings to puzzles (beginner, intermediate, advanced)~~
- ~~Track solve rate, average time, and streak~~
- ~~Unlock harder puzzles as the player improves~~
- ~~Generate random puzzle sets from a larger database~~
- ~~Comprehensive puzzle database (58 puzzles across 6 categories)~~
- ~~Puzzle completion and failure conditions separate from ending the game~~
- ~~Auto-opponent responses in multi-move puzzles~~
- ~~Elo-like rating system for puzzle skill tracking~~

### Opening Book Expansion
- Add more opening lines with ECO codes
- Show win/draw/loss statistics for each line
- Allow users to build a personal opening repertoire
- Drill openings with spaced repetition

### Keyboard Shortcuts & Accessibility
- Type moves in algebraic notation (e.g., `e4`, `Nf3`)
- Keyboard navigation of the board
- Screen reader support with ARIA labels
- High-contrast mode for visibility

---

## Phase 3 — Multiplayer & Connectivity

_Bring people together and connect to the wider chess world._

### LAN / Online Multiplayer
- Play against friends on the same local network
- Optional: simple server for online play
- Game lobby, challenge system, and rematch

### Lichess API Integration (started)
- **Daily Puzzle** — fetch and play the Lichess Puzzle of the Day (`lichess.py`) ✅
- **Stream Live Games** — watch Lichess TV with real-time board updates, channel browser, player info and clocks (`lichess.py`, `main.py`) ✅
- Import games from Lichess for analysis
- Play against Lichess bots or in rated games
- Sync puzzle progress with Lichess puzzle database

### Chess.com Integration
- Import game archives from Chess.com
- Side-by-side comparison with engine analysis

---

## Phase 4 — Advanced & Ambitious

_Longer-term ideas that would make the app truly stand out._

### Tournament Mode
- Round-robin and Swiss system support for local events
- Bracket display and standings
- Support for multiple time controls
- Bot tournaments (pit AI strategies against each other)

### Board Editor
- Drag and drop pieces to set up arbitrary positions
- Validate position legality
- Start a game or analysis from any custom position
- Save/load custom positions

### Endgame Tablebases
- Integrate Syzygy tablebases for perfect endgame play
- Show win/draw/loss and distance-to-mate for tablebase positions
- Endgame training: practice converting won positions

### AI Personality System
- Give bots distinct playing styles:
  - **The Attacker** — prioritizes king-side attacks and sacrifices
  - **The Defender** — plays solid, avoids risk, grinds in endgames
  - **The Tactician** — seeks combinations, forks, and pins
  - **The Positional Player** — focuses on pawn structure, space, and piece activity
- Each personality uses weighted evaluation functions

### Training Mode
- Spaced repetition system for opening repertoire
- Tactic puzzles with adaptive difficulty
- Endgame drills (K+R vs K, K+Q vs K, etc.)
- Pattern recognition exercises (forks, pins, skewers, discovered attacks)
- Progress tracking and weak-spot analysis

### Mobile App
- Leverage Flet's cross-platform support for iOS and Android builds
- Touch-optimized UI with larger tap targets
- Offline support for puzzles and bot play

---

## Ideas Parking Lot

_Interesting ideas that don't fit neatly into a phase yet._

- **Game database browser** — search/filter through saved games by opening, result, date
- **Commentary mode** — auto-generate natural language commentary for games
- **Blindfold mode** — hide pieces for memory training
- **Custom bot builder** — let users tweak evaluation weights and create their own bots
- **Theming engine** — full CSS-like theming for the entire UI
- **Replay speed control** — watch AI vs AI games at adjustable speed
- **FEN/position sharing** — generate shareable links or QR codes for positions
- **Clock styles** — Fischer increment, Bronstein delay, byo-yomi
- **Pre-moves** — queue a move before opponent completes theirs
- **Arrow drawing** — draw arrows and highlights on the board for analysis

---

## Contributing

Have a feature idea? Add it to the parking lot section or open an issue to discuss. When picking up a feature, move it to the appropriate phase and mark it as in progress.
