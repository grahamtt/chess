"""
Pluggable API for chess bots.
Bots receive a copy of the board and return a legal move (or None to resign).
"""

import math
import random
from typing import Protocol

import chess


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
        weight = math.exp(diff / temperature) if temperature > 0 else (1.0 if diff == 0 else 0.0)
        weights.append(weight)
    
    # Normalize weights to probabilities
    total_weight = sum(weights)
    if total_weight == 0 or not all(weights):
        # Fallback to uniform if all weights are zero
        return rng.choice([move for _, move in scored_moves])
    
    # Select based on weighted probabilities
    return rng.choices(
        [move for _, move in scored_moves],
        weights=weights,
        k=1
    )[0]


class ChessBot(Protocol):
    """Protocol for chess bots. Implement choose_move() and set name."""

    name: str
    """Display name for the bot."""

    def choose_move(self, board: chess.Board) -> chess.Move | None:
        """
        Pick a move for the current side to play.
        board is a copy of the game state; do not mutate it.
        Return a legal move, or None to resign.
        """
        ...
