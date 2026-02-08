"""
Persist and restore chess game state to/from a JSON file.

The save file stores everything needed to resume a game after an accidental
reload or restart:
  - Board position (initial FEN + list of UCI moves so full history is kept)
  - Player configuration (who is human, who is a bot)
  - Clock state (remaining time, whether the clock is running)
"""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


# Default save location: ~/.chess_game_state.json
DEFAULT_SAVE_PATH = Path.home() / ".chess_game_state.json"


@dataclass
class GameState:
    """Serialisable snapshot of the full game state."""

    # Board
    initial_fen: str = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    moves_uci: list[str] = field(default_factory=list)

    # Player configuration
    white_player: str = "human"
    black_player: str = "human"

    # Clock / time control
    time_control_secs: int | None = 300  # None means unlimited
    white_remaining_secs: float = 300.0
    black_remaining_secs: float = 300.0
    clock_enabled: bool = True
    clock_started: bool = False


def save_game_state(state: GameState, path: str | Path | None = None) -> bool:
    """Write *state* to disk as JSON.  Returns True on success."""
    save_path = Path(path) if path is not None else DEFAULT_SAVE_PATH
    try:
        data = asdict(state)
        # Write atomically: write to a temp file then rename
        tmp_path = save_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        # os.replace is atomic on POSIX; on Windows it overwrites the target
        os.replace(tmp_path, save_path)
        return True
    except (OSError, TypeError, ValueError):
        return False


def load_game_state(path: str | Path | None = None) -> GameState | None:
    """Read a previously-saved game state from disk.

    Returns a ``GameState`` on success, or ``None`` if no save exists or the
    file is corrupt / unreadable.
    """
    save_path = Path(path) if path is not None else DEFAULT_SAVE_PATH
    if not save_path.exists():
        return None
    try:
        with open(save_path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        # Only pass keys that GameState knows about
        valid_keys = {f.name for f in GameState.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return GameState(**filtered)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def clear_game_state(path: str | Path | None = None) -> bool:
    """Delete the save file.  Returns True if deleted (or already absent)."""
    save_path = Path(path) if path is not None else DEFAULT_SAVE_PATH
    try:
        save_path.unlink(missing_ok=True)
        return True
    except OSError:
        return False
