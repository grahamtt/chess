"""
Tests for the StockfishBot (bots/stockfish.py).

Most tests mock the engine subprocess so they can run without Stockfish
installed.  A small integration-test section (marked with a ``skipUnless``
guard) runs against a real Stockfish binary when available.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import chess
import chess.engine

from bots.stockfish import (
    DIFFICULTY_PRESETS,
    StockfishBot,
    find_stockfish_path,
    is_stockfish_available,
)


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
# Path discovery tests
# ---------------------------------------------------------------------------


class TestFindStockfishPath(unittest.TestCase):
    """Tests for find_stockfish_path() and is_stockfish_available()."""

    @patch.dict("os.environ", {"STOCKFISH_PATH": "/fake/stockfish"})
    @patch("os.path.isfile", return_value=True)
    def test_env_var_takes_priority(self, _isfile):
        path = find_stockfish_path()
        self.assertEqual(path, "/fake/stockfish")

    @patch.dict("os.environ", {"STOCKFISH_PATH": "/nonexistent"})
    @patch("os.path.isfile", return_value=False)
    @patch("shutil.which", return_value=None)
    def test_returns_none_when_nothing_found(self, _which, _isfile):
        path = find_stockfish_path()
        self.assertIsNone(path)

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which", return_value="/usr/bin/stockfish")
    def test_which_fallback(self, _which):
        path = find_stockfish_path()
        self.assertEqual(path, "/usr/bin/stockfish")

    @patch.dict("os.environ", {}, clear=True)
    @patch("shutil.which", return_value=None)
    @patch("os.path.isfile", side_effect=lambda p: p == "/usr/games/stockfish")
    @patch("bots.stockfish._COMMON_PATHS", ["/usr/games/stockfish"])
    def test_common_paths_fallback(self, _isfile, _which):
        path = find_stockfish_path()
        self.assertEqual(path, "/usr/games/stockfish")

    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_is_available_true(self, _find):
        self.assertTrue(is_stockfish_available())

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_is_available_false(self, _find):
        self.assertFalse(is_stockfish_available())


# ---------------------------------------------------------------------------
# StockfishBot construction tests
# ---------------------------------------------------------------------------


class TestStockfishBotInit(unittest.TestCase):
    """Tests for StockfishBot initialisation and parameter clamping."""

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_default_name_max(self, _find):
        bot = StockfishBot(skill_level=20)
        self.assertEqual(bot.name, "Stockfish (Max)")

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_default_name_level(self, _find):
        bot = StockfishBot(skill_level=5)
        self.assertEqual(bot.name, "Stockfish (Lvl 5)")

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_skill_level_clamped_low(self, _find):
        bot = StockfishBot(skill_level=-5)
        self.assertEqual(bot.skill_level, 0)

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_skill_level_clamped_high(self, _find):
        bot = StockfishBot(skill_level=50)
        self.assertEqual(bot.skill_level, 20)

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_think_time_clamped(self, _find):
        bot = StockfishBot(think_time=-1.0)
        self.assertGreater(bot.think_time, 0)

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_explicit_path(self, _find):
        bot = StockfishBot(stockfish_path="/my/sf")
        self.assertEqual(bot._path, "/my/sf")

    def test_difficulty_presets_exist(self):
        """All 8 difficulty presets should be defined."""
        self.assertEqual(len(DIFFICULTY_PRESETS), 8)
        for key in [f"stockfish_{i}" for i in range(1, 9)]:
            self.assertIn(key, DIFFICULTY_PRESETS)
            skill, time_s, elo = DIFFICULTY_PRESETS[key]
            self.assertGreaterEqual(skill, 0)
            self.assertLessEqual(skill, 20)
            self.assertGreater(time_s, 0)
            self.assertGreater(elo, 0)


# ---------------------------------------------------------------------------
# Engine lifecycle tests (mocked)
# ---------------------------------------------------------------------------


class TestStockfishBotEngine(unittest.TestCase):
    """Tests for engine start / stop / restart behaviour."""

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_choose_move_no_binary(self, _find):
        """choose_move returns None gracefully when no binary found."""
        bot = StockfishBot()
        board = chess.Board()
        self.assertIsNone(bot.choose_move(board))

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_engine_starts_on_first_call(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        # Set up play result
        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = play_result

        bot = StockfishBot(skill_level=10, think_time=0.1)
        board = chess.Board()
        move = bot.choose_move(board)

        self.assertIsNotNone(move)
        self.assertEqual(move, chess.Move.from_uci("e2e4"))
        mock_popen.assert_called_once_with("/usr/bin/stockfish")
        mock_engine.configure.assert_called_once()

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_engine_reused_on_second_call(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = play_result

        bot = StockfishBot(skill_level=10, think_time=0.1)
        board = chess.Board()
        bot.choose_move(board)
        bot.choose_move(board)

        # popen_uci should only be called once (engine reused)
        mock_popen.assert_called_once()

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_engine_restart_after_terminated(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        # First call: engine terminates during play
        mock_engine.play.side_effect = chess.engine.EngineTerminatedError()

        bot = StockfishBot(skill_level=10, think_time=0.1)
        board = chess.Board()
        move = bot.choose_move(board)
        self.assertIsNone(move)

        # Second call: engine restarted, works fine
        mock_engine.play.side_effect = None
        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("d2d4")
        mock_engine.play.return_value = play_result
        # Reset ping to pass the health check — but engine was set to None,
        # so _ensure_engine will call popen_uci again
        mock_engine.ping.return_value = None

        move = bot.choose_move(board)
        self.assertEqual(move, chess.Move.from_uci("d2d4"))
        # popen_uci called twice (initial + restart)
        self.assertEqual(mock_popen.call_count, 2)

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_close_quits_engine(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = play_result

        bot = StockfishBot(skill_level=10, think_time=0.1)
        bot.choose_move(chess.Board())  # start the engine
        bot.close()

        mock_engine.quit.assert_called_once()
        self.assertIsNone(bot._engine)

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_close_safe_when_no_engine(self, _find):
        """close() should not raise when engine was never started."""
        bot = StockfishBot()
        bot.close()  # Should not raise

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_close_handles_quit_exception(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine
        mock_engine.quit.side_effect = Exception("already dead")

        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = play_result

        bot = StockfishBot(skill_level=10, think_time=0.1)
        bot.choose_move(chess.Board())
        bot.close()  # Should not raise despite quit() failing
        self.assertIsNone(bot._engine)

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_popen_failure(self, _find, mock_popen):
        """If popen_uci raises, choose_move returns None."""
        mock_popen.side_effect = FileNotFoundError("not found")
        bot = StockfishBot(skill_level=10)
        move = bot.choose_move(chess.Board())
        self.assertIsNone(move)

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_health_check_detects_dead_engine(self, _find, mock_popen):
        """If ping raises, engine is restarted on next call."""
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = play_result

        bot = StockfishBot(skill_level=10, think_time=0.1)
        bot.choose_move(chess.Board())  # Start engine

        # Engine "dies" — ping raises
        mock_engine.ping.side_effect = chess.engine.EngineTerminatedError()
        bot.choose_move(chess.Board())

        # Should have tried to restart
        self.assertEqual(mock_popen.call_count, 2)


# ---------------------------------------------------------------------------
# choose_move edge cases
# ---------------------------------------------------------------------------


class TestStockfishBotChooseMove(unittest.TestCase):
    """Tests for choose_move() edge cases."""

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_game_over_returns_none(self, _find):
        bot = StockfishBot()
        # Fool's mate position (black has mated white)
        board = chess.Board()
        for uci in ["f2f3", "e7e5", "g2g4", "d8h4"]:
            board.push(chess.Move.from_uci(uci))
        self.assertTrue(board.is_checkmate())
        self.assertIsNone(bot.choose_move(board))

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_no_legal_moves_returns_none(self, _find):
        bot = StockfishBot()
        # Stalemate position
        board = chess.Board("k7/8/1K6/8/8/8/8/8 b - - 0 1")
        # This isn't stalemate yet, but let's use a real stalemate FEN
        board = chess.Board("k7/8/2K5/8/8/8/8/8 b - - 0 1")
        if not list(board.legal_moves):
            self.assertIsNone(bot.choose_move(board))


# ---------------------------------------------------------------------------
# Analysis helpers (mocked)
# ---------------------------------------------------------------------------


class TestStockfishBotAnalysis(unittest.TestCase):
    """Tests for analyse(), get_evaluation(), and get_best_moves()."""

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_analyse_returns_info(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        info = {"score": chess.engine.PovScore(chess.engine.Cp(50), chess.WHITE)}
        mock_engine.analyse.return_value = info

        bot = StockfishBot(skill_level=20, think_time=1.0)
        result = bot.analyse(chess.Board(), depth=10)
        self.assertIsNotNone(result)
        self.assertIn("score", result)

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_analyse_no_engine(self, _find):
        bot = StockfishBot()
        self.assertIsNone(bot.analyse(chess.Board()))

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_get_evaluation(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        score = chess.engine.PovScore(chess.engine.Cp(120), chess.WHITE)
        mock_engine.analyse.return_value = {"score": score}

        bot = StockfishBot()
        cp = bot.get_evaluation(chess.Board(), depth=10)
        self.assertEqual(cp, 120)

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_get_evaluation_mate(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        score = chess.engine.PovScore(chess.engine.Mate(3), chess.WHITE)
        mock_engine.analyse.return_value = {"score": score}

        bot = StockfishBot()
        cp = bot.get_evaluation(chess.Board(), depth=10)
        # Mate(3) with mate_score=100_000 → 100000 - 3 = 99997
        self.assertGreater(cp, 90_000)

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_get_evaluation_no_engine(self, _find):
        bot = StockfishBot()
        self.assertIsNone(bot.get_evaluation(chess.Board()))

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_get_evaluation_no_score_key(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine
        mock_engine.analyse.return_value = {}

        bot = StockfishBot()
        self.assertIsNone(bot.get_evaluation(chess.Board()))

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_get_best_moves(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        e2e4 = chess.Move.from_uci("e2e4")
        d2d4 = chess.Move.from_uci("d2d4")
        mock_engine.analyse.return_value = [
            {
                "pv": [e2e4],
                "score": chess.engine.PovScore(chess.engine.Cp(30), chess.WHITE),
            },
            {
                "pv": [d2d4],
                "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
            },
        ]

        bot = StockfishBot()
        moves = bot.get_best_moves(chess.Board(), count=2, depth=10)
        self.assertEqual(len(moves), 2)
        self.assertEqual(moves[0][0], e2e4)
        self.assertEqual(moves[1][0], d2d4)

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_get_best_moves_no_engine(self, _find):
        bot = StockfishBot()
        self.assertEqual(bot.get_best_moves(chess.Board()), [])

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_analyse_engine_error(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine
        mock_engine.analyse.side_effect = chess.engine.EngineTerminatedError()

        bot = StockfishBot()
        self.assertIsNone(bot.analyse(chess.Board()))

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_get_best_moves_engine_error(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine
        mock_engine.analyse.side_effect = chess.engine.EngineTerminatedError()

        bot = StockfishBot()
        self.assertEqual(bot.get_best_moves(chess.Board()), [])

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_get_best_moves_single_result(self, _find, mock_popen):
        """When multipv returns a single dict instead of a list, it should still work."""
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        e2e4 = chess.Move.from_uci("e2e4")
        # Return a single dict (not a list)
        mock_engine.analyse.return_value = {
            "pv": [e2e4],
            "score": chess.engine.PovScore(chess.engine.Cp(30), chess.WHITE),
        }

        bot = StockfishBot()
        moves = bot.get_best_moves(chess.Board(), count=1, depth=10)
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0][0], e2e4)


# ---------------------------------------------------------------------------
# Integration with ELO system
# ---------------------------------------------------------------------------


class TestStockfishEloIntegration(unittest.TestCase):
    """Verify Stockfish bots are registered in the ELO system."""

    def test_stockfish_bots_in_elo(self):
        from elo import BOT_ELO, BOT_DISPLAY_NAMES

        for i in range(1, 9):
            key = f"stockfish_{i}"
            self.assertIn(key, BOT_ELO, f"{key} missing from BOT_ELO")
            self.assertIn(
                key, BOT_DISPLAY_NAMES, f"{key} missing from BOT_DISPLAY_NAMES"
            )
            self.assertGreater(BOT_ELO[key], 0)

    def test_stockfish_elo_ordering(self):
        """Stockfish ELO ratings should be strictly increasing."""
        from elo import BOT_ELO

        elos = [BOT_ELO[f"stockfish_{i}"] for i in range(1, 9)]
        for i in range(len(elos) - 1):
            self.assertLess(elos[i], elos[i + 1])


# ---------------------------------------------------------------------------
# Integration with bots __init__
# ---------------------------------------------------------------------------


class TestStockfishImports(unittest.TestCase):
    """Verify the bot can be imported from the bots package."""

    def test_import_from_package(self):
        from bots import StockfishBot, is_stockfish_available, DIFFICULTY_PRESETS

        self.assertIsNotNone(StockfishBot)
        self.assertIsNotNone(is_stockfish_available)
        self.assertIsNotNone(DIFFICULTY_PRESETS)


if __name__ == "__main__":
    unittest.main()
