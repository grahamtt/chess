"""
Simple rules-based bot: prefers captures, then checks, then random legal move.
"""

import random

import chess


class SimpleBot:
    """Rules-based bot: prefer captures and checks, otherwise random."""

    def __init__(self, randomness: float = 1.0, random_seed: int | None = None) -> None:
        """
        Initialize SimpleBot.

        Args:
            randomness: Factor from 0.0 (deterministic) to 1.0 (fully random).
                       When 0.0, always picks first move in list.
            random_seed: Optional seed for random number generator (for deterministic tests).
        """
        self.randomness = max(0.0, min(1.0, randomness))
        self._rng = random.Random(random_seed) if random_seed is not None else random
        self.name = "Simple Bot"

    def choose_move(self, board: chess.Board) -> chess.Move | None:
        legal = list(board.legal_moves)
        if not legal:
            return None

        # Prefer captures (including en passant)
        captures = [m for m in legal if board.is_capture(m)]
        if captures:
            # Prefer higher-value captures (simple: more pieces attacked)
            if self.randomness > 0:
                self._rng.shuffle(captures)
            return captures[0]

        # Prefer moves that give check
        checks = [m for m in legal if board.gives_check(m)]
        if checks:
            if self.randomness > 0:
                return self._rng.choice(checks)
            return checks[0]

        if self.randomness > 0:
            return self._rng.choice(legal)
        return legal[0]
