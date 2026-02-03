"""
Minimax bot with configurable search depth and alpha-beta pruning.
Uses material + positional scoring (center control, mobility, piece-square).
"""

import chess


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
) -> tuple[int, chess.Move | None]:
    """
    Negamax with alpha-beta pruning. Returns (score, best_move).
    Score is from current side to move's perspective.
    """
    if depth == 0 or board.is_game_over():
        return evaluate(board), None

    best_move: chess.Move | None = None
    best_score = -1_000_000

    for move in board.legal_moves:
        board.push(move)
        child_score, _ = negamax(board, depth - 1, -beta, -alpha)
        board.pop()
        score = -child_score  # our score from this move

        if score > best_score:
            best_score = score
            best_move = move
        alpha = max(alpha, score)
        if alpha >= beta:
            break

    return best_score, best_move


class MinimaxBot:
    """Minimax bot with configurable search depth (alpha-beta pruning)."""

    def __init__(self, depth: int = 3) -> None:
        if depth < 1:
            depth = 1
        self.depth = depth
        self.name = f"Minimax (depth {depth})"

    def choose_move(self, board: chess.Board) -> chess.Move | None:
        legal = list(board.legal_moves)
        if not legal:
            return None
        _, best = negamax(board.copy(), self.depth, -1_000_000, 1_000_000)
        return best
