# Chess (Flet)

A two-player chess game built with [Flet](https://flet.dev), using custom SVG pieces.

## Setup

Using [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

Or create a venv and install manually:

```bash
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -e .
```

## Run

- **Desktop:** `uv run flet run main.py`
- **Web:** `uv run flet run main.py --web`

## How to play

- Click a piece to select it (valid moves are highlighted).
- Click a highlighted square to move.
- White moves first. Status bar shows whose turn it is and check/checkmate/stalemate.

## Project layout

- `main.py` – Flet UI and game loop
- `chess_logic.py` – Thin wrapper around python-chess `chess.Board` (move generation, check/checkmate/stalemate, promotions default to queen)
- `pieces_svg.py` – Wrapper for python-chess SVG pieces (Cburnett set)
