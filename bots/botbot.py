"""
BotBot: rule-based + one-ply greedy evaluation.
Designed to hold its own against intermediate human players without multi-ply search.
Uses: mate-in-one, winning/safe captures, checks, then best position by evaluation.

For antichess boards the strategy is simplified to one-ply greedy with the
antichess evaluator (no checkmate / check logic applies).

When *remaining_time* is low the bot skips expensive analysis (hang-detection,
one-ply scoring of every legal move) and falls back to fast heuristics so it
does not flag on time.
"""

import random

import chess
import chess.variant

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

    Under severe time pressure (< 1 s) the bot skips the expensive
    hang-detection pass and mate search, instead falling back to a fast
    capture-or-random heuristic so it never flags on time.
    """

    # Time thresholds (seconds) for progressively degrading search quality.
    _CRITICAL_TIME = 1.0  # Skip hang detection + mate search
    _LOW_TIME = 3.0  # Skip hang detection only

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

    def choose_move(
        self,
        board: chess.Board,
        remaining_time: float | None = None,
    ) -> chess.Move | None:
        legal = list(board.legal_moves)
        if not legal:
            return None

        # --- Antichess: use one-ply greedy with the antichess evaluator ---
        if isinstance(board, chess.variant.AntichessBoard):
            return self._choose_move_antichess(board, legal)

        # --- Critical time: fast fallback (capture > check > random) ---
        if remaining_time is not None and remaining_time < self._CRITICAL_TIME:
            return self._choose_move_fast(board, legal)

        skip_hang_check = remaining_time is not None and remaining_time < self._LOW_TIME

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
        if skip_hang_check:
            # Under time pressure: skip the expensive hang-detection
            if checks:
                scored_checks = []
                for move in checks:
                    board.push(move)
                    score = -evaluate(board)
                    board.pop()
                    scored_checks.append((score, move))
                return weighted_random_choice(scored_checks, self.randomness, self._rng)
        else:
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
        if skip_hang_check:
            # Time-pressured: evaluate all moves without hang detection
            scored_moves: list[tuple[float, chess.Move]] = []
            for move in legal:
                board.push(move)
                score = -evaluate(board)
                board.pop()
                scored_moves.append((score, move))
            return weighted_random_choice(scored_moves, self.randomness, self._rng)

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

    def _choose_move_fast(
        self, board: chess.Board, legal: list[chess.Move]
    ) -> chess.Move:
        """Ultra-fast fallback for critical time pressure.

        Priority: winning capture > any capture > check > random.
        No evaluation, no hang-detection — just quick heuristics.
        """
        # Winning captures (captured piece value >= our piece value)
        winning_captures: list[tuple[float, chess.Move]] = []
        other_captures: list[tuple[float, chess.Move]] = []
        for move in legal:
            if board.is_capture(move):
                ex = _exchange_result(board, move)
                if ex is not None and ex >= 0:
                    winning_captures.append((float(ex), move))
                else:
                    other_captures.append((0.0, move))
        if winning_captures:
            return weighted_random_choice(winning_captures, self.randomness, self._rng)
        if other_captures:
            return weighted_random_choice(other_captures, self.randomness, self._rng)

        # Checks
        checks = [(1.0, m) for m in legal if board.gives_check(m)]
        if checks:
            return weighted_random_choice(checks, self.randomness, self._rng)

        # Random legal move
        if isinstance(self._rng, random.Random):
            return self._rng.choice(legal)
        return self._rng.choice(legal)

    def _choose_move_antichess(
        self, board: chess.Board, legal: list[chess.Move]
    ) -> chess.Move:
        """Antichess strategy: one-ply greedy using the antichess evaluator.

        In antichess:
        - There is no check or checkmate.
        - Captures are forced, so when captures exist all legal moves are captures.
        - We *want* to lose material, so prefer captures where we sacrifice
          high-value pieces for low-value ones (inverted exchange).
        """
        # Check for immediate variant win (lose all pieces / force stalemate)
        for move in legal:
            board.push(move)
            if board.is_variant_win():
                board.pop()
                return move
            board.pop()

        # One-ply greedy: pick the move that gives the best antichess evaluation
        scored_moves: list[tuple[float, chess.Move]] = []
        for move in legal:
            board.push(move)
            score = -evaluate(board)  # negated: opponent's perspective → ours
            board.pop()
            scored_moves.append((score, move))

        return weighted_random_choice(scored_moves, self.randomness, self._rng)
