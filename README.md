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

## Project layout

- `main.py` – Flet UI and game loop
- `chess_logic.py` – Thin wrapper around python-chess `chess.Board` (move generation, check/checkmate/stalemate, promotions default to queen)
- `pieces_svg.py` – Wrapper for python-chess SVG pieces (Cburnett set)
