"""
Minimax bot with configurable search depth and alpha-beta pruning.
Uses material + positional scoring (center control, mobility, piece-square).

For antichess (losing chess) the evaluation is inverted: fewer own pieces is
better and the goal is to lose all material or be stalemated.

When a game clock is active the bot uses **iterative deepening**: it searches
at depth 1, 2, … up to the configured maximum, checking a deadline before
each deeper iteration.  Inside the search a ``SearchTimeout`` exception is
raised when time runs out, causing the bot to fall back to the deepest
completed result.
"""

import random
import time as _time

import chess
import chess.variant

from bots.base import compute_move_time_budget, weighted_random_choice


class SearchTimeout(Exception):
    """Raised inside negamax when the search deadline has been exceeded."""


def _is_antichess(board: chess.Board) -> bool:
    """Return True if *board* is an antichess variant board."""
    return isinstance(board, chess.variant.AntichessBoard)


# Standard piece values (centipawns)
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,  # Not used in material; king is always on board
}

# Piece values for antichess (king can be captured, so it has a material value)
ANTICHESS_PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 300,
}

# Center and extended center squares — bonus for control
CENTER_SQUARES = {
    chess.D4,
    chess.D5,
    chess.E4,
    chess.E5,
    chess.C3,
    chess.C4,
    chess.C5,
    chess.C6,
    chess.D3,
    chess.D6,
    chess.E3,
    chess.E6,
    chess.F3,
    chess.F4,
    chess.F5,
    chess.F6,
}
CENTER_BONUS = 12

# Mobility: bonus per legal move
MOBILITY_BONUS = 8


# Pawn advancement: bonus per rank advanced (perspective of piece color)
def _pawn_advancement_bonus(square: chess.Square, color: chess.Color) -> int:
    rank = chess.square_rank(square)
    if color:
        return rank - 1  # White: rank 1=0, rank 7=6
    return 6 - rank  # Black: rank 8=0, rank 2=6


PAWN_ADVANCE_WEIGHT = 5

# Knight on good central squares
KNIGHT_CENTER_SQUARES = {
    chess.C3,
    chess.C4,
    chess.C5,
    chess.C6,
    chess.D4,
    chess.D5,
    chess.E4,
    chess.E5,
    chess.F3,
    chess.F4,
    chess.F5,
    chess.F6,
}
KNIGHT_CENTER_BONUS = 15

# Bonus for having the enemy king in check (evaluated from side-to-move perspective: in check = bad)
CHECK_BONUS = 120


def _evaluate_material_and_position(board: chess.Board) -> int:
    """Material plus center control and piece-square bonuses."""
    score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        value = PIECE_VALUES[piece.piece_type]
        if piece.color == board.turn:
            score += value
            if square in CENTER_SQUARES:
                score += CENTER_BONUS
            if piece.piece_type == chess.PAWN:
                score += (
                    _pawn_advancement_bonus(square, piece.color) * PAWN_ADVANCE_WEIGHT
                )
            if piece.piece_type == chess.KNIGHT and square in KNIGHT_CENTER_SQUARES:
                score += KNIGHT_CENTER_BONUS
        else:
            score -= value
            if square in CENTER_SQUARES:
                score -= CENTER_BONUS
            if piece.piece_type == chess.PAWN:
                score -= (
                    _pawn_advancement_bonus(square, piece.color) * PAWN_ADVANCE_WEIGHT
                )
            if piece.piece_type == chess.KNIGHT and square in KNIGHT_CENTER_SQUARES:
                score -= KNIGHT_CENTER_BONUS
    return score


def evaluate(board: chess.Board) -> int:
    """
    Evaluate position from the side to move's perspective.

    Automatically dispatches to the antichess evaluator when the board is an
    :class:`chess.variant.AntichessBoard`.
    """
    if _is_antichess(board):
        return evaluate_antichess(board)

    if board.is_checkmate():
        return -100_000 if board.turn else 100_000
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0

    score = _evaluate_material_and_position(board)

    # Mobility: bonus for number of legal moves (more space = better)
    our_moves = len(list(board.legal_moves))
    score += our_moves * MOBILITY_BONUS

    # Having the enemy king in check is good: side to move in check = bad for them (good for us after negamax)
    if board.is_check():
        score -= CHECK_BONUS

    return score


# ---------------------------------------------------------------------------
# Antichess (losing chess) evaluation
# ---------------------------------------------------------------------------

# Weights for the antichess heuristic
_ANTI_MATERIAL_WEIGHT = 1  # Per-piece-value penalty for own material
_ANTI_PIECE_COUNT_BONUS = (
    80  # Extra bonus per opponent piece (they're further from winning)
)
_ANTI_MOBILITY_PENALTY = 5  # Fewer own moves → closer to stalemate (a win!)
_ANTI_CAPTURE_BONUS = 20  # Having captures available is good (chance to lose pieces)
_ANTI_PIECE_EXPOSURE_BONUS = 8  # Bonus for pieces that can be captured by opponent


def evaluate_antichess(board: chess.Board) -> int:
    """Evaluate an antichess position from the side to move's perspective.

    In antichess the objective is to lose all your pieces, so:
    * Fewer own pieces is better (closer to winning).
    * More opponent pieces is better (opponent further from winning).
    * Fewer own legal moves is better (closer to stalemate, which is a win).
    * Having capture opportunities is good (way to shed pieces).
    * Having own pieces that the opponent can capture is good.
    """
    # --- Terminal positions ---
    if board.is_game_over():
        if board.is_variant_win():
            return 100_000  # We won (lost all pieces or stalemated)
        if board.is_variant_loss():
            return -100_000  # We lost
        return 0  # Draw

    score = 0
    our_piece_count = 0
    their_piece_count = 0

    # Material: fewer own pieces = better (inverted from standard chess)
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        value = ANTICHESS_PIECE_VALUES.get(piece.piece_type, 100)
        if piece.color == board.turn:
            score -= value * _ANTI_MATERIAL_WEIGHT
            our_piece_count += 1
        else:
            score += value * _ANTI_MATERIAL_WEIGHT
            their_piece_count += 1

    # Piece-count bonus: strongly prefer having fewer of our pieces
    score -= our_piece_count * _ANTI_PIECE_COUNT_BONUS
    score += their_piece_count * _ANTI_PIECE_COUNT_BONUS

    # Mobility: fewer legal moves is closer to stalemate (a win)
    our_moves = list(board.legal_moves)
    score -= len(our_moves) * _ANTI_MOBILITY_PENALTY

    # Captures: having capture moves means we can shed pieces
    capture_count = sum(1 for m in our_moves if board.is_capture(m))
    score += capture_count * _ANTI_CAPTURE_BONUS

    # Piece exposure: bonus for own pieces that can be captured by the opponent
    # (opponent will be forced to capture them on their turn)
    board.push(chess.Move.null())  # Switch to opponent's turn
    opp_captures = set()
    for m in board.legal_moves:
        if board.is_capture(m):
            opp_captures.add(m.to_square)
    board.pop()
    # Count how many of our pieces are attacked (could be captured)
    for sq in opp_captures:
        piece = board.piece_at(sq)
        if piece is not None and piece.color == board.turn:
            score += _ANTI_PIECE_EXPOSURE_BONUS

    return score


def negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    randomness: float = 0.0,
    rng: random.Random | None = None,
    deadline: float | None = None,
    _nodes: list[int] | None = None,
) -> tuple[int, chess.Move | None]:
    """
    Negamax with alpha-beta pruning. Returns (score, best_move).
    Score is from current side to move's perspective.

    Args:
        randomness: If > 0 and multiple moves have the same best score, randomly choose among them.
        rng: Random number generator to use (for deterministic tests).
        deadline: Monotonic-clock timestamp after which the search should abort.
            When exceeded a :class:`SearchTimeout` is raised so the caller can
            fall back to a shallower result.
        _nodes: Internal counter (single-element list) used to amortise the
            deadline check.  Callers should not pass this.

    Raises:
        SearchTimeout: When *deadline* is not ``None`` and time has expired.
    """
    # --- deadline check (amortised: every 256 nodes) ---
    if deadline is not None:
        if _nodes is None:
            _nodes = [0]
        _nodes[0] += 1
        if _nodes[0] & 0xFF == 0 and _time.monotonic() > deadline:
            raise SearchTimeout

    if depth == 0 or board.is_game_over():
        return evaluate(board), None

    best_moves: list[chess.Move] = []
    best_score = -1_000_000

    for move in board.legal_moves:
        board.push(move)
        child_score, _ = negamax(
            board, depth - 1, -beta, -alpha, randomness, rng, deadline, _nodes
        )
        board.pop()
        score = -child_score  # our score from this move

        if score > best_score:
            best_score = score
            best_moves = [move]
        elif randomness > 0 and score == best_score:
            best_moves.append(move)
        alpha = max(alpha, score)
        if alpha >= beta:
            break

    if randomness > 0 and len(best_moves) > 1 and rng is not None:
        return best_score, rng.choice(best_moves)
    return best_score, best_moves[0] if best_moves else None


class MinimaxBot:
    """Minimax bot with configurable search depth (alpha-beta pruning).

    When *remaining_time* is passed to :meth:`choose_move`, the bot uses
    **iterative deepening**: it searches at depth 1, 2, …, up to the
    configured maximum, checking a time deadline between iterations.  If time
    runs out *during* a search, the :class:`SearchTimeout` exception causes
    the bot to fall back to the deepest completed result.  This guarantees that
    the bot always has *some* answer ready, even under extreme time pressure.

    When the remaining time is very low (< 1 s) the maximum depth is clamped
    to 1 so the bot plays an instant move rather than risking a flag.
    """

    # Depth caps applied when the remaining clock is critically low.
    _LOW_TIME_DEPTH_CAP = 1  # remaining_time < 1 s
    _MED_TIME_DEPTH_CAP = 2  # remaining_time < 5 s

    def __init__(
        self, depth: int = 3, randomness: float = 0.3, random_seed: int | None = None
    ) -> None:
        """
        Initialize MinimaxBot.

        Args:
            depth: Search depth (minimum 1).
            randomness: Factor from 0.0 (deterministic, always best move) to 1.0 (more uniform).
                       Better moves have higher probability, but worse moves can still be chosen.
            random_seed: Optional seed for random number generator (for deterministic tests).
        """
        if depth < 1:
            depth = 1
        self.depth = depth
        self.randomness = max(0.0, min(1.0, randomness))
        self._rng = random.Random(random_seed) if random_seed is not None else random
        self.name = f"Minimax (depth {depth})"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _effective_depth(self, remaining_time: float | None) -> int:
        """Return the maximum search depth clamped by remaining time."""
        if remaining_time is None:
            return self.depth
        if remaining_time < 1.0:
            return min(self.depth, self._LOW_TIME_DEPTH_CAP)
        if remaining_time < 5.0:
            return min(self.depth, self._MED_TIME_DEPTH_CAP)
        return self.depth

    def _search_deterministic(
        self,
        board: chess.Board,
        max_depth: int,
        deadline: float | None,
    ) -> chess.Move | None:
        """Deterministic search with iterative deepening."""
        best_move: chess.Move | None = None
        for d in range(1, max_depth + 1):
            # Check deadline before starting a deeper iteration
            if deadline is not None and _time.monotonic() > deadline:
                break
            try:
                _, move = negamax(
                    board.copy(), d, -1_000_000, 1_000_000, 0.0, None, deadline
                )
                if move is not None:
                    best_move = move
            except SearchTimeout:
                break
        return best_move

    def _search_with_randomness(
        self,
        board: chess.Board,
        legal: list[chess.Move],
        max_depth: int,
        deadline: float | None,
    ) -> chess.Move | None:
        """Scored search with iterative deepening and weighted random choice."""
        best_scored: list[tuple[float, chess.Move]] | None = None
        for d in range(1, max_depth + 1):
            if deadline is not None and _time.monotonic() > deadline:
                break
            try:
                scored_moves: list[tuple[float, chess.Move]] = []
                for move in legal:
                    test_board = board.copy()
                    test_board.push(move)
                    score, _ = negamax(
                        test_board,
                        d - 1,
                        -1_000_000,
                        1_000_000,
                        0.0,
                        None,
                        deadline,
                    )
                    scored_moves.append((-score, move))
                best_scored = scored_moves
            except SearchTimeout:
                break
        if best_scored:
            return weighted_random_choice(best_scored, self.randomness, self._rng)
        return None

    # ------------------------------------------------------------------
    # ChessBot protocol
    # ------------------------------------------------------------------

    def choose_move(
        self,
        board: chess.Board,
        remaining_time: float | None = None,
    ) -> chess.Move | None:
        legal = list(board.legal_moves)
        if not legal:
            return None

        max_depth = self._effective_depth(remaining_time)

        # Compute a deadline from the time budget
        budget = compute_move_time_budget(remaining_time)
        deadline: float | None = None
        if budget is not None:
            deadline = _time.monotonic() + budget

        if self.randomness == 0.0:
            return self._search_deterministic(board, max_depth, deadline)
        return self._search_with_randomness(board, legal, max_depth, deadline)
