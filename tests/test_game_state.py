"""Tests for game_state persistence module and ChessGame serialization helpers."""

import json

import pytest
from chess_logic import ChessGame
from game_state import (
    GameState,
    clear_game_state,
    load_game_state,
    save_game_state,
)


# ---------------------------------------------------------------------------
# ChessGame serialization helpers
# ---------------------------------------------------------------------------


class TestChessGameSerialization:
    """Tests for get_initial_fen, get_moves_uci, and load_from_moves."""

    def test_initial_fen_starting_position(self):
        game = ChessGame()
        fen = game.get_initial_fen()
        assert fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    def test_initial_fen_after_moves(self):
        game = ChessGame()
        game.make_move(6, 4, 4, 4)  # e2-e4
        game.make_move(1, 4, 3, 4)  # e7-e5
        fen = game.get_initial_fen()
        # Should still return the starting FEN (before any moves)
        assert fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    def test_initial_fen_custom_position(self):
        game = ChessGame()
        custom_fen = "8/8/8/8/8/8/4k3/4K3 w - - 0 1"
        game.set_fen(custom_fen)
        assert game.get_initial_fen() == custom_fen

    def test_initial_fen_custom_position_with_moves(self):
        game = ChessGame()
        # Use a FEN without en-passant since python-chess clears it on pop
        custom_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        game.set_fen(custom_fen)
        game.make_move(1, 4, 3, 4)  # e7-e5
        assert game.get_initial_fen() == custom_fen

    def test_moves_uci_empty(self):
        game = ChessGame()
        assert game.get_moves_uci() == []

    def test_moves_uci_after_moves(self):
        game = ChessGame()
        game.make_move(6, 4, 4, 4)  # e2-e4
        game.make_move(1, 4, 3, 4)  # e7-e5
        uci = game.get_moves_uci()
        assert uci == ["e2e4", "e7e5"]

    def test_load_from_moves_basic(self):
        game = ChessGame()
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        moves = ["e2e4", "e7e5", "g1f3"]
        assert game.load_from_moves(fen, moves)
        assert game.turn == "black"
        assert game.piece_at(4, 4) == ("white", "P")  # e4
        assert game.piece_at(3, 4) == ("black", "P")  # e5
        assert game.piece_at(5, 5) == ("white", "N")  # f3

    def test_load_from_moves_empty(self):
        game = ChessGame()
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        assert game.load_from_moves(fen, [])
        assert game.turn == "white"

    def test_load_from_moves_invalid_fen(self):
        game = ChessGame()
        assert not game.load_from_moves("garbage", ["e2e4"])
        # Should be reset to starting position after failure
        assert game.turn == "white"

    def test_load_from_moves_illegal_move(self):
        game = ChessGame()
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        # e2e5 is not a legal move from starting position
        assert not game.load_from_moves(fen, ["e2e5"])

    def test_load_from_moves_preserves_history(self):
        game = ChessGame()
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        moves = ["e2e4", "e7e5"]
        game.load_from_moves(fen, moves)
        # Should be able to undo
        assert game.can_undo()
        assert game.undo()
        # After undoing e7e5, it's black's turn (back to after e2e4)
        assert game.turn == "black"

    def test_roundtrip_standard_game(self):
        """Play some moves, serialize, then restore and verify state matches."""
        game1 = ChessGame()
        game1.make_move(6, 4, 4, 4)  # e2-e4
        game1.make_move(1, 4, 3, 4)  # e7-e5
        game1.make_move(6, 3, 4, 3)  # d2-d4

        fen = game1.get_initial_fen()
        moves = game1.get_moves_uci()

        game2 = ChessGame()
        assert game2.load_from_moves(fen, moves)

        # Same turn
        assert game2.turn == game1.turn
        # Same board
        for r in range(8):
            for c in range(8):
                assert game2.piece_at(r, c) == game1.piece_at(r, c)
        # Same move history
        assert game2.get_move_history() == game1.get_move_history()

    def test_roundtrip_custom_fen(self):
        """Serialize/restore from a custom FEN position with moves."""
        game1 = ChessGame()
        puzzle_fen = "5rk1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1"
        game1.set_fen(puzzle_fen)
        game1.make_move(7, 4, 0, 4)  # Re1-e8

        fen = game1.get_initial_fen()
        moves = game1.get_moves_uci()

        game2 = ChessGame()
        assert game2.load_from_moves(fen, moves)
        assert game2.turn == game1.turn
        assert game2.get_move_history() == game1.get_move_history()


# ---------------------------------------------------------------------------
# GameState dataclass
# ---------------------------------------------------------------------------


class TestGameState:
    def test_defaults(self):
        gs = GameState()
        assert gs.initial_fen.startswith("rnbqkbnr")
        assert gs.moves_uci == []
        assert gs.white_player == "human"
        assert gs.black_player == "human"
        assert gs.time_control_secs == 300
        assert gs.clock_enabled is True
        assert gs.clock_started is False

    def test_custom_values(self):
        gs = GameState(
            white_player="minimax_2",
            black_player="random",
            time_control_secs=None,
            clock_enabled=False,
        )
        assert gs.white_player == "minimax_2"
        assert gs.black_player == "random"
        assert gs.time_control_secs is None
        assert gs.clock_enabled is False


# ---------------------------------------------------------------------------
# save / load / clear
# ---------------------------------------------------------------------------


class TestSaveLoadClear:
    def test_save_and_load(self, tmp_path):
        path = tmp_path / "state.json"
        state = GameState(
            moves_uci=["e2e4", "e7e5"],
            white_player="minimax_1",
            black_player="human",
            time_control_secs=600,
            white_remaining_secs=542.7,
            black_remaining_secs=590.1,
            clock_enabled=True,
            clock_started=True,
        )
        assert save_game_state(state, path)
        loaded = load_game_state(path)
        assert loaded is not None
        assert loaded.moves_uci == ["e2e4", "e7e5"]
        assert loaded.white_player == "minimax_1"
        assert loaded.black_player == "human"
        assert loaded.time_control_secs == 600
        assert loaded.white_remaining_secs == pytest.approx(542.7)
        assert loaded.black_remaining_secs == pytest.approx(590.1)
        assert loaded.clock_enabled is True
        assert loaded.clock_started is True

    def test_save_and_load_unlimited_time(self, tmp_path):
        path = tmp_path / "state.json"
        state = GameState(time_control_secs=None, clock_enabled=False)
        assert save_game_state(state, path)
        loaded = load_game_state(path)
        assert loaded is not None
        assert loaded.time_control_secs is None
        assert loaded.clock_enabled is False

    def test_load_missing_file(self, tmp_path):
        path = tmp_path / "does_not_exist.json"
        assert load_game_state(path) is None

    def test_load_corrupt_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("this is not json{{{", encoding="utf-8")
        assert load_game_state(path) is None

    def test_load_non_dict_json(self, tmp_path):
        path = tmp_path / "list.json"
        path.write_text("[1,2,3]", encoding="utf-8")
        assert load_game_state(path) is None

    def test_load_ignores_unknown_keys(self, tmp_path):
        path = tmp_path / "extra.json"
        data = {
            "initial_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "moves_uci": [],
            "white_player": "human",
            "black_player": "human",
            "time_control_secs": 300,
            "white_remaining_secs": 300.0,
            "black_remaining_secs": 300.0,
            "clock_enabled": True,
            "clock_started": False,
            "some_future_field": True,
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = load_game_state(path)
        assert loaded is not None
        assert not hasattr(loaded, "some_future_field")

    def test_clear_existing(self, tmp_path):
        path = tmp_path / "state.json"
        save_game_state(GameState(), path)
        assert path.exists()
        assert clear_game_state(path)
        assert not path.exists()

    def test_clear_missing(self, tmp_path):
        path = tmp_path / "nope.json"
        assert clear_game_state(path)

    def test_save_atomic_no_leftover_tmp(self, tmp_path):
        """Verify .tmp file is cleaned up after save."""
        path = tmp_path / "state.json"
        save_game_state(GameState(), path)
        assert not (tmp_path / "state.tmp").exists()
        assert path.exists()


# ---------------------------------------------------------------------------
# Integration: full save-restore cycle with ChessGame
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_cycle(self, tmp_path):
        """Play a few moves, save, create a new game, restore, verify board."""
        path = tmp_path / "save.json"

        # Play moves
        game1 = ChessGame()
        game1.make_move(6, 4, 4, 4)  # e4
        game1.make_move(1, 4, 3, 4)  # e5
        game1.make_move(7, 6, 5, 5)  # Nf3

        state = GameState(
            initial_fen=game1.get_initial_fen(),
            moves_uci=game1.get_moves_uci(),
            white_player="human",
            black_player="minimax_2",
            time_control_secs=180,
            white_remaining_secs=170.5,
            black_remaining_secs=175.3,
            clock_enabled=True,
            clock_started=True,
        )
        save_game_state(state, path)

        # Restore into a fresh game
        loaded = load_game_state(path)
        assert loaded is not None
        game2 = ChessGame()
        assert game2.load_from_moves(loaded.initial_fen, loaded.moves_uci)

        # Verify board
        assert game2.turn == "black"
        assert game2.piece_at(5, 5) == ("white", "N")
        assert game2.get_moves_uci() == ["e2e4", "e7e5", "g1f3"]

        # Verify config
        assert loaded.black_player == "minimax_2"
        assert loaded.time_control_secs == 180
        assert loaded.white_remaining_secs == pytest.approx(170.5)

    def test_overwrite_save(self, tmp_path):
        """Successive saves overwrite the previous state."""
        path = tmp_path / "save.json"
        save_game_state(GameState(moves_uci=["e2e4"]), path)
        save_game_state(GameState(moves_uci=["d2d4", "d7d5"]), path)
        loaded = load_game_state(path)
        assert loaded is not None
        assert loaded.moves_uci == ["d2d4", "d7d5"]

    def test_clear_then_load_returns_none(self, tmp_path):
        path = tmp_path / "save.json"
        save_game_state(GameState(), path)
        clear_game_state(path)
        assert load_game_state(path) is None
