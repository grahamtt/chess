# Chess (Flet)

A two-player chess game built with [Flet](https://flet.dev), using custom SVG pieces.

## Setup

Using [uv](https://docs.astral.sh/uv/) and [mise](https://mise.jdx.dev/):

```bash
uv sync
uv run pre-commit install   # install git hooks for formatting, linting & test checks
```

If you use [mise](https://mise.jdx.dev/), the pre-commit hooks are installed automatically
when you enter the project directory.

Or create a venv and install manually:

```bash
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -e .
pre-commit install
```

## Run

- **Desktop:** `uv run flet run main.py`
- **Web:** `uv run flet run main.py --web`

## How to play

- Click a piece to select it (valid moves are highlighted).
- Click a highlighted square to move.
- White moves first. Status bar shows whose turn it is and check/checkmate/stalemate.

## Lichess Daily Puzzle

The app can fetch the **Puzzle of the Day** from [lichess.org](https://lichess.org):

1. Open the **Puzzles & Scenarios** dialog (book icon in the app bar).
2. Click **Lichess Daily Puzzle** at the top of the list.
3. Review the puzzle details (rating, themes, who to move).
4. Click **Play** to load the position onto the board.
5. Use the **Reveal** button to peek at the solution if you get stuck.

No Lichess account is required — the public API is used.

## Project layout

- `main.py` – Flet UI and game loop
- `chess_logic.py` – Thin wrapper around python-chess `chess.Board` (move generation, check/checkmate/stalemate, promotions default to queen)
- `lichess.py` – Lichess API client for fetching the daily puzzle
- `pieces_svg.py` – Wrapper for python-chess SVG pieces (Cburnett set)
