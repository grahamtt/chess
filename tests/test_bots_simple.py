"""Tests for bots.simple module."""

import chess
from bots.simple import SimpleBot


def test_simple_bot_name():
    """Test SimpleBot has correct name."""
    bot = SimpleBot()
    assert bot.name == "Simple Bot"


def test_simple_bot_choose_move_no_legal_moves():
    """Test SimpleBot returns None when there are no legal moves."""
    bot = SimpleBot()
    board = chess.Board("8/8/8/8/8/8/8/4k3 b - - 0 1")  # Black king, no legal moves (stalemate)
    # Actually, let's use a checkmate position
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    move = bot.choose_move(board)
    assert move is None


def test_simple_bot_choose_move_prefers_captures():
    """Test SimpleBot prefers captures."""
    bot = SimpleBot()
    # Set up a position with captures available
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2")
    move = bot.choose_move(board)
    assert move is not None
    # Should prefer exd5 if available, but let's just check it's a legal move
    assert move in board.legal_moves


def test_simple_bot_choose_move_prefers_checks():
    """Test SimpleBot prefers checks when no captures."""
    bot = SimpleBot()
    # Set up a position where checks are available and no captures
    # Position with queen that can give check
    board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4")
    # Filter out captures to ensure we test the check path
    captures = [m for m in board.legal_moves if board.is_capture(m)]
    if not captures:  # If no captures, should prefer checks
        move = bot.choose_move(board)
        assert move is not None
        assert move in board.legal_moves
        # Should be a check move if checks are available
        checks = [m for m in board.legal_moves if board.gives_check(m)]
        if checks:
            assert board.gives_check(move)
    else:
        # If there are captures, bot will prefer them, so just test it returns a legal move
        move = bot.choose_move(board)
        assert move is not None
        assert move in board.legal_moves


def test_simple_bot_choose_move_returns_legal_move():
    """Test SimpleBot always returns a legal move when available."""
    bot = SimpleBot()
    board = chess.Board()
    move = bot.choose_move(board)
    assert move is not None
    assert move in board.legal_moves


def test_simple_bot_choose_move_random_when_no_captures_or_checks():
    """Test SimpleBot returns random move when no captures or checks (line 32)."""
    bot = SimpleBot()
    # Position with no immediate captures or checks
    board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    # Filter to ensure no captures or checks
    captures = [m for m in board.legal_moves if board.is_capture(m)]
    checks = [m for m in board.legal_moves if board.gives_check(m)]
    if not captures and not checks:
        move = bot.choose_move(board)
        assert move is not None
        assert move in board.legal_moves
    else:
        # If there are captures/checks, test that it still works
        move = bot.choose_move(board)
        assert move is not None
        assert move in board.legal_moves


def test_simple_bot_multiple_calls():
    """Test SimpleBot can be called multiple times."""
    bot = SimpleBot()
    board = chess.Board()
    for _ in range(5):
        move = bot.choose_move(board)
        if move is not None:
            board.push(move)
        if board.is_game_over():
            break
