"""
Pluggable API for chess bots.
Bots receive a copy of the board and return a legal move (or None to resign).

When a game clock is active the caller passes ``remaining_time`` (seconds left
for the bot's side) so bots can dynamically reduce search effort under time
pressure.
"""

import math
import random
from typing import Protocol

import chess

# ---------------------------------------------------------------------------
# Time-budget helper
# ---------------------------------------------------------------------------

# Fraction of remaining time to allocate for a single move.
# Assumes an average of ~40 more moves to play.
DEFAULT_TIME_FRACTION = 1 / 40

# Absolute minimum time budget (seconds) — prevents bots from having zero
# time and failing to produce a move.
MIN_TIME_BUDGET = 0.05


def compute_move_time_budget(
    remaining_time: float | None,
    *,
    base_think_time: float | None = None,
    fraction: float = DEFAULT_TIME_FRACTION,
    min_budget: float = MIN_TIME_BUDGET,
) -> float | None:
    """Derive a per-move time budget from the remaining game-clock time.

    Returns ``None`` when there is no time pressure (unlimited clock).

    Parameters
    ----------
    remaining_time:
        Seconds left on the bot's clock.  ``None`` means unlimited.
    base_think_time:
        The bot's normal per-move think time (used as an upper cap when the
        clock is generous).  ``None`` means no cap beyond the fraction-based
        budget.
    fraction:
        Proportion of *remaining_time* to spend on this move.
    min_budget:
        Floor value so the bot always has *some* time to search.
    """
    if remaining_time is None:
        return base_think_time  # No clock → use default think time (or None)

    budget = max(remaining_time * fraction, min_budget)

    # Never use more than half the remaining time on a single move
    budget = min(budget, remaining_time / 2)

    # If the bot has a configured think time, don't exceed it when the clock
    # is generous (no need to think longer than normal).
    if base_think_time is not None:
        budget = min(budget, base_think_time)

    return max(budget, min_budget)


def weighted_random_choice(
    scored_moves: list[tuple[float, chess.Move]],
    randomness: float,
    rng: random.Random | None = None,
) -> chess.Move:
    """
    Select a move using weighted random selection based on scores.

    Better moves (higher scores) have higher probability, but worse moves can still
    be chosen depending on the randomness parameter.

    Args:
        scored_moves: List of (score, move) tuples. Higher scores are better.
        randomness: Factor from 0.0 (deterministic, always best) to 1.0 (more uniform).
        rng: Random number generator to use. If None, uses random module.

    Returns:
        A move selected with weighted probability.
    """
    if not scored_moves:
        raise ValueError("scored_moves cannot be empty")

    if randomness == 0.0:
        # Deterministic: return the move with the highest score
        return max(scored_moves, key=lambda x: x[0])[1]

    if rng is None:
        rng = random

    # Extract scores and find maximum
    scores = [score for score, _ in scored_moves]
    max_score = max(scores)

    # Use exponential weighting with temperature controlled by randomness
    # Lower randomness = lower temperature = sharper distribution (favor best moves)
    # Higher randomness = higher temperature = flatter distribution (more uniform)
    # Temperature ranges from very small (0.1) to large (1000) based on randomness
    # This allows worse moves to be selected when randomness is high
    temperature = 0.1 + (randomness * 999.9)

    # Calculate weights using exp((score - max_score) / temperature)
    # This ensures the best move has weight 1.0, and worse moves have exponentially lower weights
    # Lower temperature makes the distribution sharper (better moves much more likely)
    # Higher temperature makes it flatter (worse moves more likely)
    weights = []
    for score in scores:
        diff = score - max_score
        # Use exp for exponential weighting, but clamp to avoid overflow
        # For very negative differences, the weight will be very small
        weight = (
            math.exp(diff / temperature)
            if temperature > 0
            else (1.0 if diff == 0 else 0.0)
        )
        weights.append(weight)

    # Normalize weights to probabilities
    total_weight = sum(weights)
    if total_weight == 0 or not all(weights):
        # Fallback to uniform if all weights are zero
        return rng.choice([move for _, move in scored_moves])

    # Select based on weighted probabilities
    return rng.choices([move for _, move in scored_moves], weights=weights, k=1)[0]


class ChessBot(Protocol):
    """Protocol for chess bots. Implement choose_move() and set name."""

    name: str
    """Display name for the bot."""

    def choose_move(
        self,
        board: chess.Board,
        remaining_time: float | None = None,
    ) -> chess.Move | None:
        """
        Pick a move for the current side to play.

        Parameters
        ----------
        board:
            A copy of the game state; do not mutate it.
        remaining_time:
            Seconds remaining on this bot's clock, or ``None`` when the game
            has no time control.  Bots should use this to reduce search effort
            when time is running low.

        Returns
        -------
        A legal move, or ``None`` to resign.
        """
        ...
