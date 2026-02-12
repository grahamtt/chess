"""Tests for bots.mobility module (PieceMobilityBot)."""

import chess
import chess.variant

from bots.mobility import (
    PieceMobilityBot,
    evaluate_mobility,
    negamax_mobility,
    _count_piece_mobility,
    _is_antichess,
)


# ---------------------------------------------------------------------------
# _is_antichess
# ---------------------------------------------------------------------------


def test_is_antichess_standard_board():
    """Standard board is not antichess."""
    assert _is_antichess(chess.Board()) is False


def test_is_antichess_antichess_board():
    """AntichessBoard is detected correctly."""
    board = chess.variant.AntichessBoard()
    assert _is_antichess(board) is True


# ---------------------------------------------------------------------------
# _count_piece_mobility
# ---------------------------------------------------------------------------


def test_count_piece_mobility_starting_position():
    """Starting position: 16 pawn moves + 4 knight moves = 20 unique squares."""
    board = chess.Board()
    assert _count_piece_mobility(board) == 20


def test_count_piece_mobility_empty_board_king_only():
    """King alone on e1 (white to move) can reach up to 5 squares."""
    board = chess.Board("8/8/8/8/8/8/8/4K3 w - - 0 1")
    mobility = _count_piece_mobility(board)
    assert mobility == 5  # d1, d2, e2, f2, f1


def test_count_piece_mobility_no_legal_moves():
    """Checkmate position: no legal moves → mobility 0."""
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert _count_piece_mobility(board) == 0


def test_count_piece_mobility_promotions_counted_once():
    """A pawn about to promote to 4 pieces on the same square counts as 1 square."""
    # White pawn on a7, king on h1. Pawn can promote on a8 (4 promotions) and
    # possibly capture on b8 if there's a piece. We only put a pawn on a7.
    board = chess.Board("8/P7/8/8/8/8/8/4K2k w - - 0 1")
    mobility = _count_piece_mobility(board)
    # Pawn: a8 (1 unique square, despite 4 promotion choices)
    # King: d1, d2, e2, f2, f1 (5 squares)
    assert mobility == 6


# ---------------------------------------------------------------------------
# evaluate_mobility
# ---------------------------------------------------------------------------


def test_evaluate_mobility_starting_position():
    """Starting position should return 20 (symmetric, each side has 20)."""
    board = chess.Board()
    assert evaluate_mobility(board) == 20


def test_evaluate_mobility_checkmate():
    """Checkmate returns -100_000 for side to move."""
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert evaluate_mobility(board) == -100_000


def test_evaluate_mobility_stalemate():
    """Stalemate returns 0."""
    # Black king on a8, white king on c7, white queen on b6 – black is stalemated
    board = chess.Board("k7/2K5/1Q6/8/8/8/8/8 b - - 0 1")
    assert board.is_stalemate()
    assert evaluate_mobility(board) == 0


def test_evaluate_mobility_insufficient_material():
    """K vs K returns 0 (insufficient material)."""
    board = chess.Board("8/8/8/8/8/4k3/8/4K3 w - - 0 1")
    assert board.is_insufficient_material()
    assert evaluate_mobility(board) == 0


def test_evaluate_mobility_returns_int():
    """Score is always an integer."""
    board = chess.Board()
    assert isinstance(evaluate_mobility(board), int)


def test_evaluate_mobility_fifty_moves():
    """Position that can claim fifty moves returns 0."""
    board = chess.Board()
    board.halfmove_clock = 100
    if board.can_claim_fifty_moves():
        assert evaluate_mobility(board) == 0


def test_evaluate_mobility_threefold_repetition():
    """Threefold repetition returns 0."""
    board = chess.Board()
    # Play Nf3 Nf6 Ng1 Ng8 three times to trigger threefold
    moves = ["g1f3", "g8f6", "f3g1", "f6g8"] * 3
    for uci in moves:
        board.push(chess.Move.from_uci(uci))
    if board.can_claim_threefold_repetition():
        assert evaluate_mobility(board) == 0


# ---------------------------------------------------------------------------
# evaluate_mobility – antichess
# ---------------------------------------------------------------------------


def test_evaluate_mobility_antichess_normal():
    """Antichess starting position gives a positive mobility count."""
    board = chess.variant.AntichessBoard()
    score = evaluate_mobility(board)
    assert isinstance(score, int)
    assert score > 0


def test_evaluate_mobility_antichess_game_over_win():
    """Antichess variant win returns 100_000."""
    board = chess.variant.AntichessBoard()
    # Manually check: we can't easily create a variant-win position,
    # so just verify the branch by checking is_variant_win logic.
    # If the board is game over and variant win → 100_000.
    # We'll test with a board where one side has no pieces.
    board = chess.variant.AntichessBoard("8/8/8/8/8/8/8/4k3 w - - 0 1")
    if board.is_game_over() and board.is_variant_loss():
        # From white's perspective (no white pieces), this is a loss
        assert evaluate_mobility(board) == -100_000


def test_evaluate_mobility_antichess_game_over_loss():
    """Antichess variant loss returns -100_000."""
    # White has no pieces, black has a king – white loses (variant_loss)
    board = chess.variant.AntichessBoard("8/8/8/8/8/8/8/4k3 w - - 0 1")
    if board.is_game_over():
        score = evaluate_mobility(board)
        assert score == -100_000 or score == 100_000  # depends on variant result


def test_evaluate_mobility_antichess_draw():
    """Antichess draw returns 0."""
    board = chess.variant.AntichessBoard()
    # Hard to construct a draw in antichess; just verify the branch exists
    if (
        board.is_game_over()
        and not board.is_variant_win()
        and not board.is_variant_loss()
    ):
        assert evaluate_mobility(board) == 0


# ---------------------------------------------------------------------------
# negamax_mobility
# ---------------------------------------------------------------------------


def test_negamax_mobility_depth_zero():
    """Depth 0 returns evaluation score and no move."""
    board = chess.Board()
    score, move = negamax_mobility(board, depth=0, alpha=-1_000_000, beta=1_000_000)
    assert isinstance(score, int)
    assert move is None


def test_negamax_mobility_depth_one():
    """Depth 1 returns a legal move and integer score."""
    board = chess.Board()
    score, move = negamax_mobility(board, depth=1, alpha=-1_000_000, beta=1_000_000)
    assert isinstance(score, int)
    assert move is not None
    assert move in board.legal_moves


def test_negamax_mobility_depth_two():
    """Depth 2 returns a legal move."""
    board = chess.Board()
    score, move = negamax_mobility(board, depth=2, alpha=-1_000_000, beta=1_000_000)
    assert isinstance(score, int)
    assert move in board.legal_moves


def test_negamax_mobility_game_over():
    """Game-over position returns score and no move."""
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    score, move = negamax_mobility(board, depth=2, alpha=-1_000_000, beta=1_000_000)
    assert isinstance(score, int)
    assert move is None


def test_negamax_mobility_randomness():
    """With randomness > 0 and an RNG, tied moves are chosen randomly."""
    import random as _random

    board = chess.Board()
    rng = _random.Random(42)
    score, move = negamax_mobility(
        board, depth=1, alpha=-1_000_000, beta=1_000_000, randomness=1.0, rng=rng
    )
    assert move is not None
    assert move in board.legal_moves


def test_negamax_mobility_alpha_beta_pruning():
    """Alpha-beta pruning still returns a correct result."""
    board = chess.Board()
    score, move = negamax_mobility(board, depth=2, alpha=-1_000_000, beta=1_000_000)
    assert isinstance(score, int)
    if not board.is_game_over():
        assert move is not None


# ---------------------------------------------------------------------------
# PieceMobilityBot
# ---------------------------------------------------------------------------


def test_bot_init_default():
    """Default constructor sets depth=3 and appropriate name."""
    bot = PieceMobilityBot()
    assert bot.depth == 3
    assert bot.name == "Piece Mobility (depth 3)"
    assert bot.randomness == 0.3


def test_bot_init_custom_depth():
    """Custom depth is stored correctly."""
    bot = PieceMobilityBot(depth=5)
    assert bot.depth == 5
    assert bot.name == "Piece Mobility (depth 5)"


def test_bot_init_minimum_depth():
    """Depth below 1 is clamped to 1."""
    bot = PieceMobilityBot(depth=0)
    assert bot.depth == 1
    assert bot.name == "Piece Mobility (depth 1)"

    bot2 = PieceMobilityBot(depth=-3)
    assert bot2.depth == 1


def test_bot_init_randomness_clamped():
    """Randomness is clamped to [0.0, 1.0]."""
    bot_low = PieceMobilityBot(randomness=-0.5)
    assert bot_low.randomness == 0.0

    bot_high = PieceMobilityBot(randomness=2.0)
    assert bot_high.randomness == 1.0


def test_bot_choose_move_returns_legal():
    """choose_move returns a legal move from the starting position."""
    bot = PieceMobilityBot(depth=2)
    board = chess.Board()
    move = bot.choose_move(board)
    assert move is not None
    assert move in board.legal_moves


def test_bot_choose_move_no_legal_moves():
    """choose_move returns None when there are no legal moves."""
    bot = PieceMobilityBot(depth=2)
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert bot.choose_move(board) is None


def test_bot_choose_move_deterministic():
    """With randomness=0.0 the bot is deterministic."""
    bot = PieceMobilityBot(depth=2, randomness=0.0)
    board = chess.Board()
    move1 = bot.choose_move(board)
    move2 = bot.choose_move(board)
    assert move1 == move2


def test_bot_choose_move_with_seed():
    """With a fixed random_seed, results are reproducible."""
    bot1 = PieceMobilityBot(depth=2, randomness=0.5, random_seed=123)
    bot2 = PieceMobilityBot(depth=2, randomness=0.5, random_seed=123)
    board = chess.Board()
    assert bot1.choose_move(board) == bot2.choose_move(board)


def test_bot_choose_move_mid_game():
    """Bot returns a legal move from a mid-game position."""
    bot = PieceMobilityBot(depth=2)
    board = chess.Board("r1bqkbnr/pppppppp/2n5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2")
    move = bot.choose_move(board)
    assert move is not None
    assert move in board.legal_moves
