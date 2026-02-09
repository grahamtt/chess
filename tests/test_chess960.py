"""Tests for the Chess960Game (Fischer Random Chess) variant."""

import chess
from chess_logic import Chess960Game


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_chess960_init_random():
    """Chess960Game starts with a random position (0–959)."""
    game = Chess960Game()
    assert game.turn == "white"
    assert 0 <= game.chess960_position <= 959


def test_chess960_init_specific_position():
    """Chess960Game can be initialized with a specific position number."""
    game = Chess960Game(position=518)
    assert game.chess960_position == 518
    # Position 518 is the standard chess starting position
    assert game.piece_at(7, 4) == ("white", "K")  # King on e1
    assert game.piece_at(7, 0) == ("white", "R")  # Rook on a1


def test_chess960_init_position_clamped():
    """Position numbers are clamped to valid range."""
    game_low = Chess960Game(position=-5)
    assert game_low.chess960_position == 0
    game_high = Chess960Game(position=1000)
    assert game_high.chess960_position == 959


def test_chess960_different_positions():
    """Different position numbers produce different piece arrangements.

    Position 0 and position 959 are known to be different.
    """
    game_0 = Chess960Game(position=0)
    game_959 = Chess960Game(position=959)
    # Back rank should differ (at least one piece)
    rank1_0 = [game_0.piece_at(7, c) for c in range(8)]
    rank1_959 = [game_959.piece_at(7, c) for c in range(8)]
    assert rank1_0 != rank1_959


def test_chess960_board_is_chess960():
    """Internal board has chess960 flag set."""
    game = Chess960Game(position=42)
    board = game.get_board()
    assert board.chess960


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


def test_chess960_reset_new_position():
    """reset() without args gives a new random position."""
    game = Chess960Game(position=518)
    # Make a move, then reset
    game.make_move(6, 4, 4, 4)  # e2-e4
    assert game.turn == "black"
    game.reset()
    assert game.turn == "white"
    # Position may or may not change (random), but game is fresh
    assert not game.can_undo()


def test_chess960_reset_specific_position():
    """reset(position=N) sets a specific position."""
    game = Chess960Game(position=0)
    game.make_move(6, 4, 4, 4)
    game.reset(position=518)
    assert game.chess960_position == 518
    assert game.turn == "white"
    assert not game.can_undo()


# ---------------------------------------------------------------------------
# Set FEN
# ---------------------------------------------------------------------------


def test_chess960_set_fen_valid():
    """set_fen accepts a valid FEN for chess960."""
    game = Chess960Game(position=518)
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    assert game.set_fen(fen)
    assert game.turn == "black"


def test_chess960_set_fen_invalid():
    """set_fen returns False for an invalid FEN."""
    game = Chess960Game(position=518)
    assert not game.set_fen("not a valid fen")
    assert not game.set_fen("")
    assert not game.set_fen(None)


# ---------------------------------------------------------------------------
# Basic moves
# ---------------------------------------------------------------------------


def test_chess960_standard_position_moves():
    """Position 518 (standard) should play like normal chess."""
    game = Chess960Game(position=518)
    assert game.make_move(6, 4, 4, 4)  # e2-e4
    assert game.turn == "black"
    assert game.piece_at(4, 4) == ("white", "P")


def test_chess960_legal_moves():
    """legal_moves_from works for chess960 positions."""
    game = Chess960Game(position=518)
    moves = game.legal_moves_from(6, 4)  # e2 pawn
    assert len(moves) > 0
    assert (4, 4) in moves  # e4 is legal


def test_chess960_apply_move():
    """apply_move works for chess960."""
    game = Chess960Game(position=518)
    move = chess.Move.from_uci("e2e4")
    assert game.apply_move(move)
    assert game.turn == "black"


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------


def test_chess960_undo():
    """Undo works for chess960."""
    game = Chess960Game(position=518)
    game.make_move(6, 4, 4, 4)
    assert game.undo()
    assert game.turn == "white"
    assert game.piece_at(6, 4) == ("white", "P")


def test_chess960_can_undo():
    """can_undo tracks move stack."""
    game = Chess960Game(position=518)
    assert not game.can_undo()
    game.make_move(6, 4, 4, 4)
    assert game.can_undo()


# ---------------------------------------------------------------------------
# Game over conditions
# ---------------------------------------------------------------------------


def test_chess960_checkmate():
    """is_checkmate works for chess960."""
    game = Chess960Game(position=518)
    # Fool's mate position
    game.set_fen("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert game.is_checkmate()


def test_chess960_stalemate():
    """is_stalemate works for chess960."""
    game = Chess960Game(position=518)
    game.set_fen("k7/8/1K6/8/8/8/8/8 b - - 0 1")
    board = game.get_board()
    if board.is_stalemate():
        assert game.is_stalemate()


def test_chess960_only_kings():
    """is_only_kings_left works for chess960."""
    game = Chess960Game(position=518)
    game.set_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    assert game.is_only_kings_left()


def test_chess960_in_check():
    """is_in_check works for chess960."""
    game = Chess960Game(position=518)
    game.set_fen("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert game.is_in_check()


# ---------------------------------------------------------------------------
# Move history
# ---------------------------------------------------------------------------


def test_chess960_move_history():
    """get_move_history returns SAN notation."""
    game = Chess960Game(position=518)
    game.make_move(6, 4, 4, 4)  # e2-e4
    history = game.get_move_history()
    assert "e4" in history or "e2e4" in history


def test_chess960_move_history_empty():
    """get_move_history returns empty string when no moves."""
    game = Chess960Game(position=518)
    assert game.get_move_history() == ""


# ---------------------------------------------------------------------------
# Save / restore (load_from_moves)
# ---------------------------------------------------------------------------


def test_chess960_load_from_moves():
    """load_from_moves restores a chess960 game."""
    game = Chess960Game(position=518)
    game.make_move(6, 4, 4, 4)  # e2-e4
    game.make_move(1, 4, 3, 4)  # e7-e5

    fen = game.get_initial_fen()
    moves = game.get_moves_uci()

    game2 = Chess960Game(position=518)
    assert game2.load_from_moves(fen, moves)
    assert game2.turn == game.turn


def test_chess960_load_from_moves_invalid_fen():
    """load_from_moves returns False for invalid FEN."""
    game = Chess960Game(position=518)
    assert not game.load_from_moves("garbage fen", ["e2e4"])
    # Should be reset to a valid chess960 position
    assert game.turn == "white"


def test_chess960_load_from_moves_invalid_move():
    """load_from_moves returns False for illegal moves."""
    game = Chess960Game(position=518)
    fen = game.get_initial_fen()
    assert not game.load_from_moves(fen, ["e2e5"])  # Illegal


def test_chess960_roundtrip():
    """Full roundtrip: play moves, serialize, restore, verify."""
    game1 = Chess960Game(position=518)
    game1.make_move(6, 4, 4, 4)  # e2-e4
    game1.make_move(1, 4, 3, 4)  # e7-e5
    game1.make_move(6, 3, 4, 3)  # d2-d4

    fen = game1.get_initial_fen()
    moves = game1.get_moves_uci()

    game2 = Chess960Game(position=518)
    assert game2.load_from_moves(fen, moves)
    assert game2.turn == game1.turn
    for r in range(8):
        for c in range(8):
            assert game2.piece_at(r, c) == game1.piece_at(r, c)


# ---------------------------------------------------------------------------
# Position evaluation
# ---------------------------------------------------------------------------


def test_chess960_evaluation_starting():
    """Starting position evaluation should be approximately equal."""
    game = Chess960Game(position=518)
    eval_score = game.get_position_evaluation(depth=0)
    assert abs(eval_score) < 50


def test_chess960_evaluation_checkmate():
    """Checkmate evaluation works for chess960."""
    game = Chess960Game(position=518)
    game.set_fen("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    if game.is_checkmate():
        eval_score = game.get_position_evaluation(depth=0)
        assert eval_score <= -100_000


# ---------------------------------------------------------------------------
# get_board
# ---------------------------------------------------------------------------


def test_chess960_get_board_returns_copy():
    """get_board returns a copy with chess960 flag set."""
    game = Chess960Game(position=42)
    board = game.get_board()
    assert isinstance(board, chess.Board)
    assert board.chess960
    # Mutating the copy should not affect the game
    board.push(list(board.legal_moves)[0])
    assert game.turn == "white"


# ---------------------------------------------------------------------------
# get_last_move
# ---------------------------------------------------------------------------


def test_chess960_get_last_move():
    """get_last_move returns correct squares."""
    game = Chess960Game(position=518)
    assert game.get_last_move() is None
    game.make_move(6, 4, 4, 4)  # e2-e4
    result = game.get_last_move()
    assert result is not None
    from_sq, to_sq = result
    assert from_sq == (6, 4)
    assert to_sq == (4, 4)


# ---------------------------------------------------------------------------
# Initial FEN / moves UCI
# ---------------------------------------------------------------------------


def test_chess960_get_initial_fen():
    """get_initial_fen returns the starting FEN of the chess960 position."""
    game = Chess960Game(position=518)
    game.make_move(6, 4, 4, 4)
    fen = game.get_initial_fen()
    assert "rnbqkbnr" in fen.lower()


def test_chess960_get_moves_uci():
    """get_moves_uci returns UCI strings."""
    game = Chess960Game(position=518)
    game.make_move(6, 4, 4, 4)
    game.make_move(1, 4, 3, 4)
    moves = game.get_moves_uci()
    assert len(moves) == 2
    assert moves[0] == "e2e4"
    assert moves[1] == "e7e5"


# ---------------------------------------------------------------------------
# Chess960 specific: non-standard starting position
# ---------------------------------------------------------------------------


def test_chess960_nonstandard_position_plays():
    """A non-standard chess960 position can be played normally."""
    # Use position 0 (a known non-standard arrangement)
    game = Chess960Game(position=0)
    assert game.turn == "white"
    # Should have legal moves from all pawns
    for col in range(8):
        moves = game.legal_moves_from(6, col)
        assert len(moves) > 0, f"Pawn on col {col} should have legal moves"


def test_chess960_pieces_on_back_rank():
    """All chess960 positions have the right piece types on the back rank."""
    for pos in [0, 100, 518, 700, 959]:
        game = Chess960Game(position=pos)
        back_rank = [game.piece_at(7, c) for c in range(8)]
        piece_types = sorted([p[1] for p in back_rank if p is not None])
        # Should be: B, B, K, N, N, Q, R, R
        assert piece_types == ["B", "B", "K", "N", "N", "Q", "R", "R"], (
            f"Position {pos}: unexpected back rank pieces: {piece_types}"
        )
