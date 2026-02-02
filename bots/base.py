"""
Pluggable API for chess bots.
Bots receive a copy of the board and return a legal move (or None to resign).
"""

from typing import Protocol

import chess


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
