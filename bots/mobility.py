"""
Minimax bot with piece-mobility evaluation.

The utility function simply sums the total number of unique squares each piece
can move to on the next turn.  The bot reuses the same negamax / alpha-beta
framework as the standard MinimaxBot but with this simpler evaluation.

Because the search uses negamax, the opponent's mobility is automatically
subtracted when scores are negated at each level of the tree.
"""

import random

import chess
import chess.variant

from bots.base import weighted_random_choice


def _is_antichess(board: chess.Board) -> bool:
    """Return True if *board* is an antichess variant board."""
    return isinstance(board, chess.variant.AntichessBoard)


def _count_piece_mobility(board: chess.Board) -> int:
    """Count total unique destination squares across all pieces for the side to move.

    For each piece that has at least one legal move, count how many distinct
    squares it can reach.  Promotion moves to the same square are counted only
    once (the square itself, not the choice of piece).
    """
    destinations: dict[int, set[int]] = {}
    for move in board.legal_moves:
        destinations.setdefault(move.from_square, set()).add(move.to_square)
    return sum(len(dests) for dests in destinations.values())


def evaluate_mobility(board: chess.Board) -> int:
    """Evaluate a position based purely on piece mobility.

    Returns a score from the **side to move's** perspective:
    * Terminal positions (checkmate / stalemate / variant end) are handled
      with large fixed values.
    * Otherwise the score equals the total number of unique destination
      squares available to the side to move's pieces.

    The negamax framework takes care of subtracting the opponent's mobility
    at alternating plies.
    """
    if _is_antichess(board):
        if board.is_game_over():
            if board.is_variant_win():
                return 100_000
            if board.is_variant_loss():
                return -100_000
            return 0
        return _count_piece_mobility(board)

    if board.is_checkmate():
        return -100_000
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0

    return _count_piece_mobility(board)


def negamax_mobility(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    randomness: float = 0.0,
    rng: random.Random | None = None,
) -> tuple[int, chess.Move | None]:
    """Negamax with alpha-beta pruning using the mobility evaluation.

    Returns ``(score, best_move)``.  Score is from the current side to
    move's perspective.

    Args:
        randomness: If > 0 and multiple moves share the best score,
            randomly choose among them.
        rng: Random number generator (for deterministic tests).
    """
    if depth == 0 or board.is_game_over():
        return evaluate_mobility(board), None

    best_moves: list[chess.Move] = []
    best_score = -1_000_000

    for move in board.legal_moves:
        board.push(move)
        child_score, _ = negamax_mobility(
            board, depth - 1, -beta, -alpha, randomness, rng
        )
        board.pop()
        score = -child_score

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


class PieceMobilityBot:
    """Minimax bot that evaluates positions purely by piece mobility.

    The evaluation counts the total number of unique squares each piece of the
    side to move can reach.  Higher mobility is considered better.
    """

    def __init__(
        self,
        depth: int = 3,
        randomness: float = 0.3,
        random_seed: int | None = None,
    ) -> None:
        """
        Initialize PieceMobilityBot.

        Args:
            depth: Search depth (minimum 1).
            randomness: Factor from 0.0 (deterministic, always best move) to
                1.0 (more uniform).  Better moves have higher probability but
                worse moves can still be chosen.
            random_seed: Optional seed for the RNG (for deterministic tests).
        """
        if depth < 1:
            depth = 1
        self.depth = depth
        self.randomness = max(0.0, min(1.0, randomness))
        self._rng = random.Random(random_seed) if random_seed is not None else random
        self.name = f"Piece Mobility (depth {depth})"

    def choose_move(self, board: chess.Board) -> chess.Move | None:
        legal = list(board.legal_moves)
        if not legal:
            return None

        if self.randomness == 0.0:
            _, best = negamax_mobility(
                board.copy(), self.depth, -1_000_000, 1_000_000, 0.0, None
            )
            return best

        # Collect scores for every legal move
        scored_moves: list[tuple[float, chess.Move]] = []
        for move in legal:
            test_board = board.copy()
            test_board.push(move)
            score, _ = negamax_mobility(
                test_board, self.depth - 1, -1_000_000, 1_000_000, 0.0, None
            )
            # Negate because negamax returns score from opponent's perspective
            scored_moves.append((-score, move))

        return weighted_random_choice(scored_moves, self.randomness, self._rng)
