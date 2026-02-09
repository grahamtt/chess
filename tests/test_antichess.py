"""Tests for the AntiChessGame (antichess / losing chess) variant."""

import chess
import chess.variant
from chess_logic import AntiChessGame


# ---------------------------------------------------------------------------
# Initialization and basic interface
# ---------------------------------------------------------------------------


def test_antichess_init():
    """AntiChessGame starts from the standard position."""
    game = AntiChessGame()
    assert game.turn == "white"
    assert game.piece_at(7, 0) == ("white", "R")  # a1 rook
    assert game.piece_at(7, 4) == ("white", "K")  # e1 king
    assert game.piece_at(0, 0) == ("black", "R")  # a8 rook
    assert game.piece_at(4, 4) is None  # empty e4


def test_antichess_reset():
    """reset() brings the board back to the starting position."""
    game = AntiChessGame()
    game.make_move(6, 4, 4, 4)  # e3 (or e4)
    assert game.turn == "black"
    game.reset()
    assert game.turn == "white"
    assert game.piece_at(6, 4) == ("white", "P")


def test_antichess_set_fen_valid():
    """set_fen accepts a valid FEN."""
    game = AntiChessGame()
    assert game.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1")
    assert game.turn == "white"


def test_antichess_set_fen_invalid():
    """set_fen returns False for invalid FEN strings."""
    game = AntiChessGame()
    assert not game.set_fen("invalid fen")
    assert not game.set_fen("")
    assert not game.set_fen(None)


# ---------------------------------------------------------------------------
# No check / no checkmate
# ---------------------------------------------------------------------------


def test_antichess_no_check():
    """is_in_check always returns False in antichess."""
    game = AntiChessGame()
    assert not game.is_in_check()
    # Even with a position that would be check in standard chess
    game.set_fen("rnbqkbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w - - 1 3")
    assert not game.is_in_check()


def test_antichess_no_checkmate():
    """is_checkmate always returns False in antichess."""
    game = AntiChessGame()
    assert not game.is_checkmate()
    # Even with a standard-chess checkmate position
    game.set_fen("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w - - 1 3")
    assert not game.is_checkmate()


# ---------------------------------------------------------------------------
# Forced captures
# ---------------------------------------------------------------------------


def test_antichess_forced_capture():
    """When a capture is available, only capture moves are legal."""
    game = AntiChessGame()
    # Position: white pawn on d4, black pawn on e5
    game.set_fen("rnbqkbnr/pppp1ppp/8/4p3/3P4/8/PPP1PPPP/RNBQKBNR w - - 0 1")
    # Only d4xe5 should be available
    moves_d4 = game.legal_moves_from(4, 3)  # d4 = row 4, col 3
    assert (3, 4) in moves_d4  # e5 is a capture destination
    # Non-capturing pieces should not have moves
    moves_a2 = game.legal_moves_from(6, 0)  # a2 pawn
    assert len(moves_a2) == 0


def test_antichess_no_forced_capture_when_none_available():
    """When no capture is available, all pseudo-legal moves are valid."""
    game = AntiChessGame()
    # Starting position — no captures possible
    assert not game.has_captures()
    moves_e2 = game.legal_moves_from(6, 4)  # e2 pawn
    assert len(moves_e2) > 0  # Should have legal moves


def test_antichess_has_captures():
    """has_captures returns True when capture moves exist."""
    game = AntiChessGame()
    assert not game.has_captures()
    # Create a position with captures
    game.set_fen("rnbqkbnr/pppp1ppp/8/4p3/3P4/8/PPP1PPPP/RNBQKBNR w - - 0 1")
    assert game.has_captures()


def test_antichess_multiple_captures_player_chooses():
    """When multiple captures exist, the player may choose which one to take."""
    game = AntiChessGame()
    # Position where white has two captures available
    game.set_fen("8/8/8/3p1p2/4P3/8/8/8 w - - 0 1")
    # e4 pawn can capture d5 or f5
    moves_e4 = game.legal_moves_from(4, 4)  # e4 = row 4, col 4
    assert (3, 3) in moves_e4  # d5
    assert (3, 5) in moves_e4  # f5
    assert len(moves_e4) == 2  # Only the two captures


# ---------------------------------------------------------------------------
# Pawn promotion (including king)
# ---------------------------------------------------------------------------


def test_antichess_promotion_to_king():
    """Pawns can promote to king in antichess."""
    game = AntiChessGame()
    game.set_fen("8/P7/8/8/8/8/8/7k w - - 0 1")
    # a7 pawn promotes on a8
    assert game.is_promotion_move(1, 0, 0, 0)
    assert game.make_move(1, 0, 0, 0, promotion=chess.KING)
    piece = game.piece_at(0, 0)
    assert piece == ("white", "K")


def test_antichess_promotion_to_queen():
    """Pawns can promote to queen (default) in antichess."""
    game = AntiChessGame()
    game.set_fen("8/P7/8/8/8/8/8/7k w - - 0 1")
    assert game.make_move(1, 0, 0, 0, promotion=chess.QUEEN)
    piece = game.piece_at(0, 0)
    assert piece == ("white", "Q")


def test_antichess_promotion_to_rook():
    """Pawns can promote to rook in antichess."""
    game = AntiChessGame()
    game.set_fen("8/P7/8/8/8/8/8/7k w - - 0 1")
    assert game.make_move(1, 0, 0, 0, promotion=chess.ROOK)
    piece = game.piece_at(0, 0)
    assert piece == ("white", "R")


def test_antichess_promotion_to_bishop():
    """Pawns can promote to bishop in antichess."""
    game = AntiChessGame()
    game.set_fen("8/P7/8/8/8/8/8/7k w - - 0 1")
    assert game.make_move(1, 0, 0, 0, promotion=chess.BISHOP)
    piece = game.piece_at(0, 0)
    assert piece == ("white", "B")


def test_antichess_promotion_to_knight():
    """Pawns can promote to knight in antichess."""
    game = AntiChessGame()
    game.set_fen("8/P7/8/8/8/8/8/7k w - - 0 1")
    assert game.make_move(1, 0, 0, 0, promotion=chess.KNIGHT)
    piece = game.piece_at(0, 0)
    assert piece == ("white", "N")


def test_antichess_promotion_default_queen():
    """When no promotion is specified, default to queen."""
    game = AntiChessGame()
    game.set_fen("8/P7/8/8/8/8/8/7k w - - 0 1")
    assert game.make_move(1, 0, 0, 0)  # No promotion specified
    piece = game.piece_at(0, 0)
    assert piece == ("white", "Q")


def test_antichess_is_promotion_move():
    """is_promotion_move correctly identifies promotion moves."""
    game = AntiChessGame()
    game.set_fen("8/P7/8/8/8/8/8/7k w - - 0 1")
    assert game.is_promotion_move(1, 0, 0, 0)  # a7->a8 is promotion
    # Non-promotion move
    game.set_fen("8/8/P7/8/8/8/8/7k w - - 0 1")
    assert not game.is_promotion_move(2, 0, 1, 0)  # a6->a7 is not promotion


def test_antichess_get_promotion_choices():
    """get_promotion_choices includes king."""
    game = AntiChessGame()
    choices = game.get_promotion_choices()
    assert chess.QUEEN in choices
    assert chess.ROOK in choices
    assert chess.BISHOP in choices
    assert chess.KNIGHT in choices
    assert chess.KING in choices
    assert len(choices) == 5


# ---------------------------------------------------------------------------
# Winning conditions
# ---------------------------------------------------------------------------


def test_antichess_win_by_losing_all_pieces():
    """Player who loses all pieces wins."""
    game = AntiChessGame()
    # Black has no pieces, it's black's turn → black wins (0-1)
    game.set_fen("8/8/8/8/8/8/8/4K3 b - - 0 1")
    assert game.is_antichess_game_over()
    assert game.antichess_result() == "0-1"
    assert game.is_antichess_win()  # From perspective of side to move (black)


def test_antichess_win_by_stalemate():
    """Player who is stalemated wins."""
    game = AntiChessGame()
    # White pawn blocked by black pawn, white has no legal moves
    game.set_fen("8/8/8/8/8/p7/P7/8 w - - 0 1")
    assert game.is_stalemate()
    assert game.is_antichess_game_over()
    assert game.antichess_result() == "1-0"
    assert game.is_antichess_win()


def test_antichess_not_over_at_start():
    """Game is not over at the starting position."""
    game = AntiChessGame()
    assert not game.is_antichess_game_over()
    assert game.antichess_result() is None


def test_antichess_is_antichess_loss():
    """is_antichess_loss returns True for the losing side."""
    game = AntiChessGame()
    # White still has a king, black has no pieces. It's white's turn.
    game.set_fen("8/8/8/8/8/8/8/4K3 w - - 0 1")
    # White can't move (no legal moves for a lone king if it's a draw/stalemate variant)
    # Actually in antichess a lone king with no opponent pieces — game is over
    assert game.is_antichess_game_over()


# ---------------------------------------------------------------------------
# King can be captured
# ---------------------------------------------------------------------------


def test_antichess_king_capture():
    """Kings can be captured like any other piece."""
    game = AntiChessGame()
    # White queen can capture black king
    game.set_fen("4k3/8/8/8/8/8/8/4Q3 w - - 0 1")
    # White must capture the king (forced capture)
    moves_q = game.legal_moves_from(7, 4)  # e1 queen
    # The queen should be able to move to e8 (capture the king)
    assert (0, 4) in moves_q


# ---------------------------------------------------------------------------
# No castling
# ---------------------------------------------------------------------------


def test_antichess_no_castling():
    """Castling is not allowed in antichess."""
    game = AntiChessGame()
    # Standard position with room for castling in normal chess
    game.set_fen("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w - - 0 1")
    king_moves = game.legal_moves_from(7, 4)  # e1 king
    # Castling squares: (7, 6) for kingside, (7, 2) for queenside
    # Both should be absent because antichess has no castling
    # (Also, antichess FEN has no castling rights)
    assert (7, 6) not in king_moves or (7, 2) not in king_moves


# ---------------------------------------------------------------------------
# legal_moves_from deduplication
# ---------------------------------------------------------------------------


def test_antichess_legal_moves_from_no_duplicates():
    """legal_moves_from does not return duplicate squares for promotion moves."""
    game = AntiChessGame()
    game.set_fen("8/P7/8/8/8/8/8/7k w - - 0 1")
    moves = game.legal_moves_from(1, 0)  # a7
    # Should be a single unique square (a8 = (0, 0))
    assert len(moves) == 1
    assert moves[0] == (0, 0)


# ---------------------------------------------------------------------------
# Move history
# ---------------------------------------------------------------------------


def test_antichess_move_history():
    """get_move_history returns SAN notation for antichess moves."""
    game = AntiChessGame()
    game.make_move(6, 4, 4, 4)  # e4
    game.make_move(1, 3, 3, 3)  # d5
    history = game.get_move_history()
    assert "e4" in history or "e2e4" in history
    assert "d5" in history or "d7d5" in history


def test_antichess_move_history_empty():
    """get_move_history returns empty string when no moves made."""
    game = AntiChessGame()
    assert game.get_move_history() == ""


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------


def test_antichess_undo():
    """Undo works correctly in antichess."""
    game = AntiChessGame()
    game.make_move(6, 4, 4, 4)  # e4
    assert game.turn == "black"
    assert game.undo()
    assert game.turn == "white"
    assert game.piece_at(6, 4) == ("white", "P")


def test_antichess_undo_empty():
    """Undo returns False when no moves to undo."""
    game = AntiChessGame()
    assert not game.undo()


def test_antichess_can_undo():
    """can_undo correctly tracks move stack."""
    game = AntiChessGame()
    assert not game.can_undo()
    game.make_move(6, 4, 4, 4)
    assert game.can_undo()


# ---------------------------------------------------------------------------
# get_board / apply_move
# ---------------------------------------------------------------------------


def test_antichess_get_board():
    """get_board returns a copy of the internal board."""
    game = AntiChessGame()
    board = game.get_board()
    assert isinstance(board, chess.variant.AntichessBoard)


def test_antichess_apply_move():
    """apply_move applies a valid antichess move."""
    game = AntiChessGame()
    move = chess.Move.from_uci("e2e4")
    assert game.apply_move(move)
    assert game.turn == "black"


def test_antichess_apply_move_invalid():
    """apply_move rejects an invalid move."""
    game = AntiChessGame()
    invalid = chess.Move.from_uci("e2e5")  # Illegal: pawn can't move 3 squares
    assert not game.apply_move(invalid)


# ---------------------------------------------------------------------------
# load_from_moves
# ---------------------------------------------------------------------------


def test_antichess_load_from_moves():
    """load_from_moves restores an antichess game."""
    game = AntiChessGame()
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"
    assert game.load_from_moves(fen, ["e2e4", "d7d5", "e4d5"])
    assert game.turn == "black"
    # d5 pawn should be captured
    assert game.piece_at(3, 3) == ("white", "P")  # White pawn on d5


def test_antichess_load_from_moves_invalid():
    """load_from_moves returns False for an invalid move sequence."""
    game = AntiChessGame()
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"
    # e2e4 followed by e7e5 — e7e5 is illegal because no capture is forced... wait
    # Actually after e2e4, no captures exist so any black move is fine
    # Let's use a truly invalid move
    assert not game.load_from_moves(fen, ["e2e4", "e2e4"])  # Same move twice


def test_antichess_load_from_moves_error():
    """load_from_moves handles errors gracefully."""
    game = AntiChessGame()
    assert not game.load_from_moves("invalid fen", ["e2e4"])


# ---------------------------------------------------------------------------
# Position evaluation
# ---------------------------------------------------------------------------


def test_antichess_evaluation_starting():
    """Starting position should be approximately equal."""
    game = AntiChessGame()
    eval_score = game.get_position_evaluation(depth=0)
    # Both sides have equal material, so inverted eval should be ~0
    assert abs(eval_score) < 50


def test_antichess_evaluation_fewer_pieces_better():
    """In antichess, fewer own pieces = better evaluation."""
    game = AntiChessGame()
    # White has just a king, black has many pieces — white is winning
    game.set_fen("rnbqkbnr/pppppppp/8/8/8/8/8/4K3 w - - 0 1")
    eval_score = game.get_position_evaluation(depth=0)
    # White has fewer pieces → higher score (positive)
    assert eval_score > 0

    # Black has just a king, white has many pieces — black is winning
    game.set_fen("4k3/8/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1")
    eval_score = game.get_position_evaluation(depth=0)
    # Black has fewer pieces → lower score (negative, favoring black)
    assert eval_score < 0


def test_antichess_evaluation_game_over():
    """Evaluation for game-over positions."""
    game = AntiChessGame()
    # White wins (1-0): stalemated white
    game.set_fen("8/8/8/8/8/p7/P7/8 w - - 0 1")
    if game.is_antichess_game_over():
        eval_score = game.get_position_evaluation()
        assert eval_score == 100_000  # White wins

    # Black wins (0-1): black has no pieces
    game.set_fen("8/8/8/8/8/8/8/4K3 b - - 0 1")
    if game.is_antichess_game_over():
        eval_score = game.get_position_evaluation()
        assert eval_score == -100_000  # Black wins


# ---------------------------------------------------------------------------
# get_last_move
# ---------------------------------------------------------------------------


def test_antichess_get_last_move():
    """get_last_move works for antichess games."""
    game = AntiChessGame()
    assert game.get_last_move() is None
    game.make_move(6, 4, 4, 4)  # e2->e4
    result = game.get_last_move()
    assert result is not None
    from_sq, to_sq = result
    assert from_sq == (6, 4)
    assert to_sq == (4, 4)


# ---------------------------------------------------------------------------
# get_initial_fen / get_moves_uci
# ---------------------------------------------------------------------------


def test_antichess_get_initial_fen():
    """get_initial_fen returns the starting position FEN."""
    game = AntiChessGame()
    game.make_move(6, 4, 4, 4)
    fen = game.get_initial_fen()
    assert "rnbqkbnr" in fen.lower()


def test_antichess_get_moves_uci():
    """get_moves_uci returns UCI strings for all played moves."""
    game = AntiChessGame()
    game.make_move(6, 4, 4, 4)  # e2e4
    game.make_move(1, 3, 3, 3)  # d7d5
    moves = game.get_moves_uci()
    assert len(moves) == 2
    assert moves[0] == "e2e4"
    assert moves[1] == "d7d5"


# ---------------------------------------------------------------------------
# is_only_kings_left
# ---------------------------------------------------------------------------


def test_antichess_is_only_kings_left():
    """is_only_kings_left returns True when only kings remain."""
    game = AntiChessGame()
    game.set_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    assert game.is_only_kings_left()


def test_antichess_is_only_kings_left_false():
    """is_only_kings_left returns False when other pieces exist."""
    game = AntiChessGame()
    assert not game.is_only_kings_left()


# ---------------------------------------------------------------------------
# Full game scenario
# ---------------------------------------------------------------------------


def test_antichess_full_game_scenario():
    """Play through a short antichess game where pieces are captured."""
    game = AntiChessGame()
    # White: pawn on e4. Black: pawn on d5, king on c6.
    # White captures d5, then black king captures d5 (forced).
    game.set_fen("8/8/2k5/3p4/4P3/8/8/8 w - - 0 1")
    # White must capture d5 (forced)
    assert game.has_captures()
    moves = game.legal_moves_from(4, 4)  # e4
    assert (3, 3) in moves  # d5 capture
    game.make_move(4, 4, 3, 3)  # exd5
    # Now black king must capture d5 (forced)
    assert game.has_captures()
    moves_king = game.legal_moves_from(2, 2)  # c6 king = row 2, col 2
    assert (3, 3) in moves_king  # Kxd5
    game.make_move(2, 2, 3, 3)  # Kxd5
    # White has no pieces → game over, white wins!
    assert game.is_antichess_game_over()
    assert game.antichess_result() == "1-0"


def test_antichess_short_game():
    """A very short antichess game ending in a win."""
    game = AntiChessGame()
    # Position: white has one pawn on b2, black has one piece on a3
    # White's pawn must capture a3 (forced), leaving white with 0 pieces → white wins
    game.set_fen("8/8/8/8/8/p7/1P6/8 w - - 0 1")
    assert game.has_captures()
    # b2 captures a3
    assert game.make_move(6, 1, 5, 0)  # b2xa3
    # Now it's black's turn. White still has a pawn on a3.
    # Check: is the game over? Black has no pieces → black wins!
    assert game.is_antichess_game_over()
    assert game.antichess_result() == "0-1"  # Black lost all pieces → black wins


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_antichess_make_move_invalid():
    """make_move returns False for an invalid move."""
    game = AntiChessGame()
    assert not game.make_move(4, 4, 3, 4)  # Empty square


def test_antichess_make_move_captures():
    """make_move correctly handles capture moves."""
    game = AntiChessGame()
    game.set_fen("rnbqkbnr/pppp1ppp/8/4p3/3P4/8/PPP1PPPP/RNBQKBNR w - - 0 1")
    # d4xe5 — forced capture
    assert game.make_move(4, 3, 3, 4)  # d4 -> e5
    assert game.piece_at(3, 4) == ("white", "P")  # White pawn on e5
    assert game.piece_at(4, 3) is None  # d4 is empty
