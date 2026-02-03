"""
BotBot: rule-based + one-ply greedy evaluation.
Designed to hold its own against intermediate human players without multi-ply search.
Uses: mate-in-one, winning/safe captures, checks, then best position by evaluation.
"""

import chess

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

    name = "BotBot"

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
            captures.sort(key=lambda x: -x[0])  # best capture first
            best_gain = captures[0][0]
            best_caps = [m for g, m in captures if g == best_gain]
            return best_caps[0]  # could random.choice for variety

        # 3) Moves that give check (tactical pressure)
        checks = [m for m in legal if board.gives_check(m)]
        safe_checks = [m for m in checks if not _move_hangs_piece(board, m)]
        if safe_checks:
            # Pick best check by one-ply score
            best_score = -1_000_000
            best_move = safe_checks[0]
            for move in safe_checks:
                board.push(move)
                score = -evaluate(board)  # opponent's perspective -> ours
                board.pop()
                if score > best_score:
                    best_score = score
                    best_move = move
            return best_move
        if checks:
            # All checks hang something; still prefer checks that hang less
            best_score = -1_000_000
            best_move = checks[0]
            for move in checks:
                board.push(move)
                score = -evaluate(board)
                board.pop()
                if score > best_score:
                    best_score = score
                    best_move = move
            return best_move

        # 4) One-ply greedy: pick move that gives best evaluation after our move
        # Filter out moves that hang a piece if we have a safe alternative
        scored = []
        for move in legal:
            board.push(move)
            score = -evaluate(board)
            board.pop()
            hangs = _move_hangs_piece(board, move)
            scored.append((score, hangs, move))
        # Prefer safe moves; among those, prefer higher score
        scored.sort(
            key=lambda x: (x[1], -x[0])
        )  # False (safe) before True (hangs), then higher score
        return scored[0][2]
