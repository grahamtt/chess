"""
ELO rating system for tracking player skill and adjusting bot difficulty.

Provides:
  - Standard ELO rating calculation (expected score, rating update)
  - Bot ELO assignments mapping each bot to an approximate rating
  - Dynamic K-factor based on number of games played
  - Difficulty recommendation based on current player rating
  - Persistent player profile with game history (JSON file)
"""

import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Default save location for the ELO profile
DEFAULT_ELO_PATH = Path.home() / ".chess_elo.json"

# Approximate ELO ratings for each bot.  These map to the *key* strings used
# in ``main.py``'s ``player_bots`` dict.
BOT_ELO: dict[str, int] = {
    "random": 600,
    "botbot": 900,
    "minimax_1": 1100,
    "minimax_2": 1300,
    "minimax_3": 1500,
    "minimax_4": 1700,
    "stockfish_1": 1200,
    "stockfish_2": 1400,
    "stockfish_3": 1600,
    "stockfish_4": 1800,
    "stockfish_5": 2000,
    "stockfish_6": 2200,
    "stockfish_7": 2500,
    "stockfish_8": 2800,
}

# Default starting ELO for a new player
DEFAULT_RATING = 1000

# K-factor thresholds (number of rated games -> K value)
# Higher K means bigger rating swings (appropriate for new players)
K_FACTOR_THRESHOLDS: list[tuple[int, int]] = [
    (10, 40),  # First 10 games: K=40
    (30, 32),  # Games 11-30: K=32
    (999_999, 24),  # 30+ games: K=24
]

# Ordered list of bot keys from weakest to strongest (for difficulty ladder)
BOT_LADDER: list[str] = sorted(BOT_ELO, key=lambda k: BOT_ELO[k])

# Human-readable display names for bots
BOT_DISPLAY_NAMES: dict[str, str] = {
    "random": "Random",
    "botbot": "BotBot",
    "minimax_1": "Minimax 1",
    "minimax_2": "Minimax 2",
    "minimax_3": "Minimax 3",
    "minimax_4": "Minimax 4",
    "stockfish_1": "Stockfish 1",
    "stockfish_2": "Stockfish 2",
    "stockfish_3": "Stockfish 3",
    "stockfish_4": "Stockfish 4",
    "stockfish_5": "Stockfish 5",
    "stockfish_6": "Stockfish 6",
    "stockfish_7": "Stockfish 7",
    "stockfish_8": "Stockfish 8",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class GameRecord:
    """A single rated game result."""

    opponent: str  # bot key (e.g. "minimax_2")
    opponent_elo: int
    result: float  # 1.0 = win, 0.5 = draw, 0.0 = loss
    rating_before: int
    rating_after: int
    timestamp: float = 0.0  # Unix timestamp


@dataclass
class EloProfile:
    """Persistent player ELO profile."""

    rating: int = DEFAULT_RATING
    games_played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    history: list[dict] = field(default_factory=list)  # list of GameRecord dicts
    peak_rating: int = DEFAULT_RATING


# ---------------------------------------------------------------------------
# ELO calculation helpers
# ---------------------------------------------------------------------------


def expected_score(player_elo: int, opponent_elo: int) -> float:
    """Calculate expected score for *player* against *opponent*.

    Uses the standard ELO formula:
        E = 1 / (1 + 10^((R_opponent - R_player) / 400))

    Returns a float between 0 and 1.
    """
    exponent = (opponent_elo - player_elo) / 400.0
    return 1.0 / (1.0 + math.pow(10.0, exponent))


def k_factor(games_played: int) -> int:
    """Return the K-factor for a player with *games_played* rated games.

    New players have a higher K-factor so their rating converges faster.
    """
    for threshold, k in K_FACTOR_THRESHOLDS:
        if games_played < threshold:
            return k
    # Fallback (should not happen given the large last threshold)
    return K_FACTOR_THRESHOLDS[-1][1]  # pragma: no cover


def calculate_new_rating(
    player_elo: int, opponent_elo: int, result: float, games_played: int
) -> int:
    """Calculate the new ELO rating after a game.

    Args:
        player_elo: Current player rating.
        opponent_elo: Opponent's rating.
        result: 1.0 for a win, 0.5 for a draw, 0.0 for a loss.
        games_played: Number of rated games the player has completed (before this one).

    Returns:
        The updated player rating (rounded to nearest int).
    """
    e = expected_score(player_elo, opponent_elo)
    k = k_factor(games_played)
    new_rating = player_elo + k * (result - e)
    # Floor at 100 to avoid absurdly low / negative ratings
    return max(100, round(new_rating))


# ---------------------------------------------------------------------------
# Difficulty recommendation
# ---------------------------------------------------------------------------


def recommend_opponent(player_elo: int) -> str:
    """Suggest the best bot opponent for a player with rating *player_elo*.

    Picks the bot whose ELO is closest to the player's, producing the most
    competitive match-up.
    """
    best_key = BOT_LADDER[0]
    best_diff = abs(player_elo - BOT_ELO[best_key])
    for key in BOT_LADDER[1:]:
        diff = abs(player_elo - BOT_ELO[key])
        if diff < best_diff:
            best_diff = diff
            best_key = key
    return best_key


def get_difficulty_label(player_elo: int) -> str:
    """Return a human-readable difficulty label based on player ELO."""
    if player_elo < 700:
        return "Beginner"
    if player_elo < 1000:
        return "Casual"
    if player_elo < 1300:
        return "Intermediate"
    if player_elo < 1600:
        return "Advanced"
    return "Expert"


def get_bot_elo(bot_key: str) -> int | None:
    """Return the ELO rating for a bot key, or None if unknown."""
    return BOT_ELO.get(bot_key)


def get_bot_display_name(bot_key: str) -> str:
    """Return a display name for a bot key."""
    return BOT_DISPLAY_NAMES.get(bot_key, bot_key)


# ---------------------------------------------------------------------------
# Profile management / persistence
# ---------------------------------------------------------------------------


def record_game(
    profile: EloProfile,
    opponent_key: str,
    result: float,
) -> GameRecord:
    """Record a completed game and update the profile in-place.

    Args:
        profile: The player's ELO profile (mutated).
        opponent_key: Bot key (e.g. ``"minimax_2"``).
        result: 1.0 win, 0.5 draw, 0.0 loss (from the human player's perspective).

    Returns:
        The ``GameRecord`` for this game.
    """
    opponent_elo = BOT_ELO.get(opponent_key, DEFAULT_RATING)
    rating_before = profile.rating
    new_rating = calculate_new_rating(
        profile.rating, opponent_elo, result, profile.games_played
    )
    profile.rating = new_rating
    profile.games_played += 1
    if result == 1.0:
        profile.wins += 1
    elif result == 0.0:
        profile.losses += 1
    else:
        profile.draws += 1
    if new_rating > profile.peak_rating:
        profile.peak_rating = new_rating

    record = GameRecord(
        opponent=opponent_key,
        opponent_elo=opponent_elo,
        result=result,
        rating_before=rating_before,
        rating_after=new_rating,
        timestamp=time.time(),
    )
    profile.history.append(asdict(record))
    return record


def save_elo_profile(profile: EloProfile, path: str | Path | None = None) -> bool:
    """Persist the ELO profile to disk as JSON.  Returns True on success."""
    save_path = Path(path) if path is not None else DEFAULT_ELO_PATH
    try:
        data = asdict(profile)
        tmp_path = save_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, save_path)
        return True
    except (OSError, TypeError, ValueError):
        return False


def load_elo_profile(path: str | Path | None = None) -> EloProfile:
    """Load an ELO profile from disk.

    Returns a fresh ``EloProfile`` (default rating) if no save exists or the
    file is corrupt.
    """
    save_path = Path(path) if path is not None else DEFAULT_ELO_PATH
    if not save_path.exists():
        return EloProfile()
    try:
        with open(save_path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return EloProfile()
        valid_keys = {fld.name for fld in EloProfile.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return EloProfile(**filtered)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return EloProfile()


def reset_elo_profile(path: str | Path | None = None) -> bool:
    """Delete the ELO profile file.  Returns True if deleted (or absent)."""
    save_path = Path(path) if path is not None else DEFAULT_ELO_PATH
    try:
        save_path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def get_recent_form(profile: EloProfile, n: int = 5) -> str:
    """Return a short string summarising the last *n* results (e.g. ``"W W L D W"``)."""
    if not profile.history:
        return "No games yet"
    recent = profile.history[-n:]
    symbols = []
    for rec in recent:
        r = rec.get("result", 0.5)
        if r == 1.0:
            symbols.append("W")
        elif r == 0.0:
            symbols.append("L")
        else:
            symbols.append("D")
    return " ".join(symbols)


def get_win_rate(profile: EloProfile) -> float | None:
    """Return win-rate as a percentage (0-100), or None if no games played."""
    if profile.games_played == 0:
        return None
    return (profile.wins / profile.games_played) * 100.0


# ---------------------------------------------------------------------------
# Ranked play helpers
# ---------------------------------------------------------------------------

# Actions that are forbidden while a ranked game is in progress.
# Used by the UI to disable controls and show explanatory tooltips.
RANKED_RESTRICTIONS: dict[str, str] = {
    "undo": "Undo is disabled in ranked games.",
    "hint": "Hints are disabled in ranked games.",
    "change_players": "Player configuration is locked during a ranked game.",
    "change_ranked": "Cannot switch to unranked while a ranked game is in progress.",
    "set_fen": "Loading a FEN position is disabled during ranked games.",
}


def is_game_ratable(
    white_player: str,
    black_player: str,
    *,
    is_puzzle: bool = False,
    game_mode: str = "standard",
) -> bool:
    """Return True if the current game configuration is eligible for ranked play.

    A game is ratable when:
    - Exactly one side is ``"human"`` and the other is a known bot.
    - It is **not** a puzzle.

    All game modes (standard, chess960, antichess) are eligible.
    """
    if is_puzzle:
        return False
    human_side = (white_player == "human") + (black_player == "human")
    if human_side != 1:
        return False  # human-vs-human or bot-vs-bot
    bot_key = black_player if white_player == "human" else white_player
    return bot_key in BOT_ELO


def ranked_action_blocked(action: str) -> str | None:
    """Return a user-facing reason string if *action* is blocked in ranked mode.

    Returns ``None`` if the action is allowed.
    """
    return RANKED_RESTRICTIONS.get(action)
