"""
BotBot: rule-based + one-ply greedy evaluation.
Designed to hold its own against intermediate human players without multi-ply search.
Uses: mate-in-one, winning/safe captures, checks, then best position by evaluation.
"""

import random

import chess

from bots.base import weighted_random_choice
from bots.minimax import evaluate

# Piece values for exchange evaluation (centipawns)
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


def _piece_value(piece: chess.Piece | None) -> int:
    if piece is None:
        return 0
    return PIECE_VALUES.get(piece.piece_type, 0)


def _exchange_result(board: chess.Board, move: chess.Move) -> int | None:
    """
    If move is a capture, return approximate exchange value from our perspective
    (positive = we gain). Assumes they recapture with smallest piece. Returns None if not a capture.
    """
    if not board.is_capture(move):
        return None
    from_sq = move.from_square
    to_sq = move.to_square
    our_piece = board.piece_at(from_sq)
    their_piece = board.piece_at(to_sq)
    if our_piece is None or their_piece is None:
        return None
    # We gain their piece; we lose our piece if they recapture
    gain = _piece_value(their_piece)
    # En passant: we take a pawn, we lose our pawn if they "recapture" the square
    if board.is_en_passant(move):
        return gain - _piece_value(our_piece)  # we lose our pawn
    # They recapture with something; assume they use the smallest attacker
    loss = _piece_value(our_piece)
    return gain - loss


def _move_hangs_piece(board: chess.Board, move: chess.Move) -> bool:
    """True if after this move, the piece we moved can be captured for free or for a profit."""
    board.push(move)
    to_sq = move.to_square
    piece = board.piece_at(to_sq)
    if piece is None:
        board.pop()
        return False
    our_value = _piece_value(piece)
    # Can opponent capture on to_sq with something that costs less or equal?
    capturers = []
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if (
            p is not None
            and p.color != board.turn
            and board.is_legal(chess.Move(sq, to_sq))
        ):
            capturers.append(_piece_value(p))
    board.pop()
    if not capturers:
        return False
    # If they can take with a piece of lower or equal value, we're hanging
    return min(capturers) <= our_value


class BotBot:
    """
    Strategy: (1) Mate in one, (2) Winning/safe captures, (3) Checks, (4) One-ply best position.
    Avoids moves that hang a piece when a safe alternative exists.
    """

    def __init__(self, randomness: float = 0.5, random_seed: int | None = None) -> None:
        """
        Initialize BotBot.

        Args:
            randomness: Factor from 0.0 (deterministic, always best move) to 1.0 (more uniform).
                       Better moves have higher probability, but worse moves can still be chosen.
            random_seed: Optional seed for random number generator (for deterministic tests).
        """
        self.randomness = max(0.0, min(1.0, randomness))
        self._rng = random.Random(random_seed) if random_seed is not None else random
        self.name = "BotBot"

    def choose_move(self, board: chess.Board) -> chess.Move | None:
        legal = list(board.legal_moves)
        if not legal:
            return None

        # 1) Mate in one
        for move in legal:
            board.push(move)
            if board.is_checkmate():
                board.pop()
                return move
            board.pop()

        # 2) Winning or equal captures (by exchange), prefer bigger wins
        captures = []
        for move in legal:
            if not board.is_capture(move):
                continue
            ex = _exchange_result(board, move)
            if ex is not None and ex >= 0:  # we don't lose material
                captures.append((ex, move))
        if captures:
            # Use weighted selection: better captures more likely, but worse ones still possible
            return weighted_random_choice(captures, self.randomness, self._rng)

        # 3) Moves that give check (tactical pressure)
        checks = [m for m in legal if board.gives_check(m)]
        safe_checks = [m for m in checks if not _move_hangs_piece(board, m)]
        if safe_checks:
            # Score all safe checks and use weighted selection
            scored_checks = []
            for move in safe_checks:
                board.push(move)
                score = -evaluate(board)  # opponent's perspective -> ours
                board.pop()
                scored_checks.append((score, move))
            return weighted_random_choice(scored_checks, self.randomness, self._rng)
        if checks:
            # All checks hang something; still prefer checks that hang less
            scored_checks = []
            for move in checks:
                board.push(move)
                score = -evaluate(board)
                board.pop()
                scored_checks.append((score, move))
            return weighted_random_choice(scored_checks, self.randomness, self._rng)

        # 4) One-ply greedy: pick move that gives best evaluation after our move
        # Filter out moves that hang a piece if we have a safe alternative
        scored = []
        for move in legal:
            board.push(move)
            score = -evaluate(board)
            board.pop()
            hangs = _move_hangs_piece(board, move)
            scored.append((score, hangs, move))

        # Separate safe and unsafe moves
        safe_moves = [(s, m) for s, h, m in scored if not h]
        unsafe_moves = [(s, m) for s, h, m in scored if h]

        # Prefer safe moves if available
        if safe_moves:
            # Use weighted selection among safe moves
            return weighted_random_choice(safe_moves, self.randomness, self._rng)
        else:
            # Only unsafe moves available, use weighted selection
            return weighted_random_choice(unsafe_moves, self.randomness, self._rng)
