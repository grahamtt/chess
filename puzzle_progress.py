"""
Puzzle progress tracking: player rating, solve stats, streaks, and unlocking.

The system uses an Elo-like rating to track puzzle skill:
- Players start at 1000 rating
- Solving a puzzle above your rating gains more points
- Failing an easy puzzle loses more points
- Puzzles unlock progressively based on the player's rating

Progress is persisted to disk as JSON.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


DEFAULT_PROGRESS_PATH = Path.home() / ".chess_puzzle_progress.json"
DEFAULT_PLAYER_RATING = 1000
K_FACTOR = 32  # How much rating can change per puzzle
UNLOCK_MARGIN = 300  # Player can attempt puzzles up to this much above their rating


@dataclass
class PuzzleAttempt:
    """Record of a single puzzle attempt."""

    puzzle_id: str
    timestamp: float  # time.time()
    solved: bool
    time_secs: float  # How long the attempt took
    moves_made: int  # How many moves the player made
    rating_before: int  # Player rating before this attempt
    rating_after: int  # Player rating after this attempt


@dataclass
class PuzzleStats:
    """Aggregate statistics for a single puzzle."""

    puzzle_id: str
    attempts: int = 0
    solved: bool = False
    best_time_secs: float | None = None
    last_attempted: float | None = None  # timestamp

    def record_attempt(self, solved: bool, time_secs: float) -> None:
        """Record a new attempt."""
        self.attempts += 1
        self.last_attempted = time.time()
        if solved:
            self.solved = True
            if self.best_time_secs is None or time_secs < self.best_time_secs:
                self.best_time_secs = time_secs


@dataclass
class PuzzleProgress:
    """Full puzzle progress state for a player."""

    player_rating: int = DEFAULT_PLAYER_RATING
    total_attempted: int = 0
    total_solved: int = 0
    current_streak: int = 0
    best_streak: int = 0
    puzzle_stats: dict[str, PuzzleStats] = field(default_factory=dict)
    recent_attempts: list[PuzzleAttempt] = field(default_factory=list)

    @property
    def solve_rate(self) -> float:
        """Overall solve percentage."""
        if self.total_attempted == 0:
            return 0.0
        return self.total_solved / self.total_attempted

    @property
    def average_time(self) -> float | None:
        """Average time of successful solves across all puzzles."""
        times = [
            s.best_time_secs
            for s in self.puzzle_stats.values()
            if s.best_time_secs is not None
        ]
        if not times:
            return None
        return sum(times) / len(times)

    def is_puzzle_unlocked(self, puzzle_rating: int) -> bool:
        """Check if a puzzle is accessible based on the player's current rating.

        Free-play puzzles (rating 0) are always unlocked.
        Other puzzles are unlocked if the player's rating is within UNLOCK_MARGIN
        of the puzzle's rating.
        """
        if puzzle_rating == 0:
            return True
        return puzzle_rating <= self.player_rating + UNLOCK_MARGIN

    def get_stats_for_puzzle(self, puzzle_id: str) -> PuzzleStats:
        """Get or create stats for a specific puzzle."""
        if puzzle_id not in self.puzzle_stats:
            self.puzzle_stats[puzzle_id] = PuzzleStats(puzzle_id=puzzle_id)
        return self.puzzle_stats[puzzle_id]

    def record_attempt(
        self,
        puzzle_id: str,
        puzzle_rating: int,
        solved: bool,
        time_secs: float,
        moves_made: int,
    ) -> PuzzleAttempt:
        """Record a puzzle attempt and update rating/stats.

        Returns the PuzzleAttempt record.
        """
        rating_before = self.player_rating

        # Update rating using Elo-like formula
        self.player_rating = _calculate_new_rating(
            self.player_rating, puzzle_rating, solved
        )

        # Update global counters
        self.total_attempted += 1
        if solved:
            self.total_solved += 1
            self.current_streak += 1
            if self.current_streak > self.best_streak:
                self.best_streak = self.current_streak
        else:
            self.current_streak = 0

        # Update per-puzzle stats
        stats = self.get_stats_for_puzzle(puzzle_id)
        stats.record_attempt(solved, time_secs)

        # Create attempt record
        attempt = PuzzleAttempt(
            puzzle_id=puzzle_id,
            timestamp=time.time(),
            solved=solved,
            time_secs=time_secs,
            moves_made=moves_made,
            rating_before=rating_before,
            rating_after=self.player_rating,
        )

        # Keep only the last 100 attempts in memory
        self.recent_attempts.append(attempt)
        if len(self.recent_attempts) > 100:
            self.recent_attempts = self.recent_attempts[-100:]

        return attempt

    def get_rating_change_display(self) -> str:
        """Return a display string showing the last rating change."""
        if not self.recent_attempts:
            return ""
        last = self.recent_attempts[-1]
        diff = last.rating_after - last.rating_before
        if diff > 0:
            return f"+{diff}"
        elif diff < 0:
            return str(diff)
        return "0"


def _calculate_new_rating(player_rating: int, puzzle_rating: int, solved: bool) -> int:
    """Calculate new player rating using Elo-like formula.

    Args:
        player_rating: Current player rating
        puzzle_rating: Difficulty rating of the puzzle
        solved: Whether the puzzle was solved

    Returns:
        New player rating (clamped to 100-3000 range)
    """
    if puzzle_rating == 0:
        # Free play puzzles don't affect rating
        return player_rating

    # Expected score (probability of solving based on rating difference)
    expected = 1.0 / (1.0 + math.pow(10, (puzzle_rating - player_rating) / 400.0))

    # Actual score: 1.0 for solve, 0.0 for failure
    actual = 1.0 if solved else 0.0

    # Rating change
    change = K_FACTOR * (actual - expected)

    new_rating = int(round(player_rating + change))

    # Clamp to reasonable range
    return max(100, min(3000, new_rating))


def _progress_to_dict(progress: PuzzleProgress) -> dict:
    """Serialize PuzzleProgress to a JSON-safe dict."""
    data = {
        "player_rating": progress.player_rating,
        "total_attempted": progress.total_attempted,
        "total_solved": progress.total_solved,
        "current_streak": progress.current_streak,
        "best_streak": progress.best_streak,
        "puzzle_stats": {},
        "recent_attempts": [],
    }

    for pid, stats in progress.puzzle_stats.items():
        data["puzzle_stats"][pid] = asdict(stats)

    for attempt in progress.recent_attempts:
        data["recent_attempts"].append(asdict(attempt))

    return data


def _dict_to_progress(data: dict) -> PuzzleProgress:
    """Deserialize a dict back into PuzzleProgress."""
    progress = PuzzleProgress(
        player_rating=data.get("player_rating", DEFAULT_PLAYER_RATING),
        total_attempted=data.get("total_attempted", 0),
        total_solved=data.get("total_solved", 0),
        current_streak=data.get("current_streak", 0),
        best_streak=data.get("best_streak", 0),
    )

    for pid, stats_data in data.get("puzzle_stats", {}).items():
        # Backward compat: old saves stored "solves" as an int count.
        # Convert to bool: any non-zero value means solved.
        raw_solved = stats_data.get("solved", stats_data.get("solves", False))
        solved_bool = bool(raw_solved)
        progress.puzzle_stats[pid] = PuzzleStats(
            puzzle_id=stats_data.get("puzzle_id", pid),
            attempts=stats_data.get("attempts", 0),
            solved=solved_bool,
            best_time_secs=stats_data.get("best_time_secs"),
            last_attempted=stats_data.get("last_attempted"),
        )

    for attempt_data in data.get("recent_attempts", []):
        try:
            attempt = PuzzleAttempt(
                puzzle_id=attempt_data["puzzle_id"],
                timestamp=attempt_data["timestamp"],
                solved=attempt_data["solved"],
                time_secs=attempt_data["time_secs"],
                moves_made=attempt_data["moves_made"],
                rating_before=attempt_data["rating_before"],
                rating_after=attempt_data["rating_after"],
            )
            progress.recent_attempts.append(attempt)
        except (KeyError, TypeError):
            continue  # Skip malformed attempts

    return progress


def save_puzzle_progress(
    progress: PuzzleProgress, path: str | Path | None = None
) -> bool:
    """Save puzzle progress to disk. Returns True on success."""
    save_path = Path(path) if path is not None else DEFAULT_PROGRESS_PATH
    try:
        data = _progress_to_dict(progress)
        tmp_path = save_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, save_path)
        return True
    except (OSError, TypeError, ValueError):
        return False


def load_puzzle_progress(path: str | Path | None = None) -> PuzzleProgress:
    """Load puzzle progress from disk.

    Returns a PuzzleProgress object (fresh one if no save exists or file is corrupt).
    """
    save_path = Path(path) if path is not None else DEFAULT_PROGRESS_PATH
    if not save_path.exists():
        return PuzzleProgress()
    try:
        with open(save_path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return PuzzleProgress()
        return _dict_to_progress(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return PuzzleProgress()


def clear_puzzle_progress(path: str | Path | None = None) -> bool:
    """Delete the progress save file. Returns True on success."""
    save_path = Path(path) if path is not None else DEFAULT_PROGRESS_PATH
    try:
        save_path.unlink(missing_ok=True)
        return True
    except OSError:
        return False
