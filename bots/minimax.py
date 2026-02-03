"""
Minimax bot with configurable search depth and alpha-beta pruning.
Uses material + positional scoring (center control, mobility, piece-square).
"""

import random

import chess

from bots.base import weighted_random_choice


# Standard piece values (centipawns)
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,  # Not used in material; king is always on board
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
    Includes material, center control, pawn advancement, knight placement, and mobility.
    """
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


def negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    randomness: float = 0.0,
    rng: random.Random | None = None,
) -> tuple[int, chess.Move | None]:
    """
    Negamax with alpha-beta pruning. Returns (score, best_move).
    Score is from current side to move's perspective.

    Args:
        randomness: If > 0 and multiple moves have the same best score, randomly choose among them.
        rng: Random number generator to use (for deterministic tests).
    """
    if depth == 0 or board.is_game_over():
        return evaluate(board), None

    best_moves: list[chess.Move] = []
    best_score = -1_000_000

    for move in board.legal_moves:
        board.push(move)
        child_score, _ = negamax(board, depth - 1, -beta, -alpha, randomness, rng)
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
    """Minimax bot with configurable search depth (alpha-beta pruning)."""

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

    def choose_move(self, board: chess.Board) -> chess.Move | None:
        legal = list(board.legal_moves)
        if not legal:
            return None

        if self.randomness == 0.0:
            # Deterministic: use original negamax
            _, best = negamax(
                board.copy(), self.depth, -1_000_000, 1_000_000, 0.0, None
            )
            return best

        # Collect scores for all moves using negamax
        scored_moves = []
        for move in legal:
            test_board = board.copy()
            test_board.push(move)
            score, _ = negamax(
                test_board, self.depth - 1, -1_000_000, 1_000_000, 0.0, None
            )
            # Negate because negamax returns score from opponent's perspective
            scored_moves.append((-score, move))

        # Use weighted selection based on scores
        return weighted_random_choice(scored_moves, self.randomness, self._rng)
