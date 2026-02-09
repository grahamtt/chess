"""Tests for Stockfish bot Chess960 support and game mode filtering."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import chess
import chess.engine

from bots.stockfish import StockfishBot


# ---------------------------------------------------------------------------
# Helper: build a mock engine
# ---------------------------------------------------------------------------


def _make_mock_engine() -> MagicMock:
    """Return a MagicMock that behaves like chess.engine.SimpleEngine."""
    engine = MagicMock(spec=chess.engine.SimpleEngine)
    engine.ping.return_value = None
    engine.configure.return_value = None
    engine.quit.return_value = None
    return engine


# ---------------------------------------------------------------------------
# is_mode_supported
# ---------------------------------------------------------------------------


class TestStockfishModeSupport(unittest.TestCase):
    """Tests for StockfishBot.is_mode_supported()."""

    def test_standard_supported(self):
        assert StockfishBot.is_mode_supported("standard") is True

    def test_chess960_supported(self):
        assert StockfishBot.is_mode_supported("chess960") is True

    def test_antichess_not_supported(self):
        assert StockfishBot.is_mode_supported("antichess") is False

    def test_unknown_mode_not_supported(self):
        assert StockfishBot.is_mode_supported("crazyhouse") is False

    def test_empty_string_not_supported(self):
        assert StockfishBot.is_mode_supported("") is False


# ---------------------------------------------------------------------------
# Chess960 init flag
# ---------------------------------------------------------------------------


class TestStockfishChess960Init(unittest.TestCase):
    """Tests for chess960 parameter in StockfishBot init."""

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_default_chess960_false(self, _find):
        bot = StockfishBot()
        assert bot.chess960 is False

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_chess960_true(self, _find):
        bot = StockfishBot(chess960=True)
        assert bot.chess960 is True


# ---------------------------------------------------------------------------
# set_chess960
# ---------------------------------------------------------------------------


class TestStockfishSetChess960(unittest.TestCase):
    """Tests for set_chess960() method."""

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_set_chess960_enables(self, _find):
        bot = StockfishBot(chess960=False)
        bot.set_chess960(True)
        assert bot.chess960 is True

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_set_chess960_disables(self, _find):
        bot = StockfishBot(chess960=True)
        bot.set_chess960(False)
        assert bot.chess960 is False

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_set_chess960_no_change(self, _find):
        """Setting to same value does not close engine."""
        bot = StockfishBot(chess960=False)
        bot._engine = MagicMock()  # Fake engine
        bot.set_chess960(False)
        # Engine should NOT be closed (no change)
        assert bot._engine is not None

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_set_chess960_closes_engine(self, _find, mock_popen):
        """Changing chess960 flag closes running engine."""
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = play_result

        bot = StockfishBot(skill_level=10, think_time=0.1, chess960=False)
        bot.choose_move(chess.Board())  # Start engine

        bot.set_chess960(True)
        # Engine should have been closed
        mock_engine.quit.assert_called_once()
        assert bot._engine is None
        assert bot.chess960 is True


# ---------------------------------------------------------------------------
# Engine configuration with UCI_Chess960
# ---------------------------------------------------------------------------


class TestStockfishChess960Engine(unittest.TestCase):
    """Tests for engine configuration with UCI_Chess960."""

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_engine_config_without_chess960(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = play_result

        bot = StockfishBot(skill_level=10, think_time=0.1, chess960=False)
        bot.choose_move(chess.Board())

        # Check configure was called without UCI_Chess960
        config_call = mock_engine.configure.call_args[0][0]
        assert "UCI_Chess960" not in config_call

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_engine_config_with_chess960(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = play_result

        bot = StockfishBot(skill_level=10, think_time=0.1, chess960=True)
        bot.choose_move(chess.Board())

        # Check configure was called with UCI_Chess960
        config_call = mock_engine.configure.call_args[0][0]
        assert "UCI_Chess960" in config_call
        assert config_call["UCI_Chess960"] is True

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_engine_restarts_with_chess960_after_toggle(self, _find, mock_popen):
        """After toggling chess960, engine restarts with new config."""
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = play_result

        bot = StockfishBot(skill_level=10, think_time=0.1, chess960=False)
        bot.choose_move(chess.Board())  # Start engine without chess960

        # Toggle to chess960
        bot.set_chess960(True)
        # Reset mock to track new configure call
        mock_engine.configure.reset_mock()
        mock_engine.ping.return_value = None

        bot.choose_move(chess.Board())  # Should restart engine with chess960

        # Verify popen was called again (restart)
        assert mock_popen.call_count == 2
        # Verify new config includes UCI_Chess960
        config_call = mock_engine.configure.call_args[0][0]
        assert config_call.get("UCI_Chess960") is True


# ---------------------------------------------------------------------------
# Choose move with Chess960 board
# ---------------------------------------------------------------------------


class TestStockfishChess960ChooseMove(unittest.TestCase):
    """Tests for choose_move with chess960 boards."""

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_choose_move_chess960_board(self, _find, mock_popen):
        """choose_move works with a chess960 board."""
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = play_result

        bot = StockfishBot(skill_level=10, think_time=0.1, chess960=True)
        board = chess.Board(chess960=True)
        board.set_chess960_pos(518)
        move = bot.choose_move(board)

        assert move is not None
        assert move == chess.Move.from_uci("e2e4")


# ---------------------------------------------------------------------------
# SUPPORTED_MODES class attribute
# ---------------------------------------------------------------------------


class TestStockfishSupportedModes(unittest.TestCase):
    """Tests for SUPPORTED_MODES class attribute."""

    def test_supported_modes_includes_standard(self):
        assert "standard" in StockfishBot.SUPPORTED_MODES

    def test_supported_modes_includes_chess960(self):
        assert "chess960" in StockfishBot.SUPPORTED_MODES

    def test_supported_modes_excludes_antichess(self):
        assert "antichess" not in StockfishBot.SUPPORTED_MODES

    def test_supported_modes_is_frozenset(self):
        assert isinstance(StockfishBot.SUPPORTED_MODES, frozenset)


if __name__ == "__main__":
    unittest.main()
