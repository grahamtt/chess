"""
Simple rules-based bot: prefers captures, then checks, then random legal move.
"""

import random

import chess

from bots.base import weighted_random_choice


class SimpleBot:
    """Rules-based bot: prefer captures and checks, otherwise random."""

    def __init__(self, randomness: float = 1.0, random_seed: int | None = None) -> None:
        """
        Initialize SimpleBot.

        Args:
            randomness: Factor from 0.0 (deterministic, always best move) to 1.0 (more uniform).
                       Better moves have higher probability, but worse moves can still be chosen.
            random_seed: Optional seed for random number generator (for deterministic tests).
        """
        self.randomness = max(0.0, min(1.0, randomness))
        self._rng = random.Random(random_seed) if random_seed is not None else random
        self.name = "Simple Bot"

    def _simple_score(self, board: chess.Board, move: chess.Move) -> float:
        """Simple scoring: captures > checks > other moves."""
        score = 0.0
        if board.is_capture(move):
            # Score by captured piece value (rough estimate)
            captured_piece = board.piece_at(move.to_square)
            if captured_piece:
                piece_values = {
                    chess.PAWN: 1.0,
                    chess.KNIGHT: 3.0,
                    chess.BISHOP: 3.0,
                    chess.ROOK: 5.0,
                    chess.QUEEN: 9.0,
                }
                score += 100.0 + piece_values.get(captured_piece.piece_type, 0.0)
        if board.gives_check(move):
            score += 50.0
        # Add small random component to break ties
        score += 0.1
        return score

    def choose_move(self, board: chess.Board) -> chess.Move | None:
        legal = list(board.legal_moves)
        if not legal:
            return None

        # Score all moves
        scored_moves = [(self._simple_score(board, move), move) for move in legal]

        # Use weighted selection: better moves more likely, but worse ones still possible
        return weighted_random_choice(scored_moves, self.randomness, self._rng)
