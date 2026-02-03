"""
Simple rules-based bot: prefers captures, then checks, then random legal move.
"""

import random

import chess


class SimpleBot:
    """Rules-based bot: prefer captures and checks, otherwise random."""

    name = "Simple Bot"

    def choose_move(self, board: chess.Board) -> chess.Move | None:
        legal = list(board.legal_moves)
        if not legal:
            return None

        # Prefer captures (including en passant)
        captures = [m for m in legal if board.is_capture(m)]
        if captures:
            # Prefer higher-value captures (simple: more pieces attacked)
            random.shuffle(captures)
            return captures[0]

        # Prefer moves that give check
        checks = [m for m in legal if board.gives_check(m)]
        if checks:
            return random.choice(checks)

        return random.choice(legal)
