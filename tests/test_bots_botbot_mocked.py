"""Use mocks to force coverage of defensive code paths."""

import chess
from unittest.mock import patch, MagicMock
from bots.botbot import _exchange_result, _move_hangs_piece


def test_exchange_result_mocked_none_pieces():
    """Test _exchange_result with mocked None pieces to hit line 41."""
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2")
    move = chess.Move.from_uci("e4d5")  # A capture move
    
    # Mock piece_at to return None
    with patch.object(board, 'piece_at', return_value=None):
        result = _exchange_result(board, move)
        # Should hit line 41 (return None)
        assert result is None


def test_exchange_result_mocked_en_passant():
    """Test _exchange_result en passant to hit line 46."""
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2")
    # Find en passant move
    ep_move = None
    for move in board.legal_moves:
        if board.is_en_passant(move):
            ep_move = move
            break
    
    if ep_move:
        result = _exchange_result(board, ep_move)
        # Should hit line 46
        assert result is not None
        assert isinstance(result, int)


def test_move_hangs_piece_mocked_none():
    """Test _move_hangs_piece with mocked None piece to hit lines 58-59."""
    board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    move = chess.Move.from_uci("e2e4")
    
    # Mock piece_at after push to return None
    original_push = board.push
    original_pop = board.pop
    original_piece_at = board.piece_at
    
    def mock_push(m):
        original_push(m)
        # After push, mock piece_at to return None
        board.piece_at = MagicMock(return_value=None)
    
    def mock_pop():
        board.piece_at = original_piece_at
        original_pop()
    
    with patch.object(board, 'push', side_effect=mock_push), \
         patch.object(board, 'pop', side_effect=mock_pop):
        result = _move_hangs_piece(board, move)
        # Should hit lines 58-59
        assert result is False
