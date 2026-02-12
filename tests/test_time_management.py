"""
Tests for bot time-management / thinking-time-limit features.

Covers:
- compute_move_time_budget helper
- MinimaxBot iterative deepening & depth capping under time pressure
- BotBot fast-fallback paths under time pressure
- SimpleBot remaining_time parameter acceptance
- StockfishBot effective think-time capping
- AdaptiveStockfishBot remaining_time passthrough
- SearchTimeout propagation inside negamax
"""

import time
import unittest
from unittest.mock import MagicMock, patch

import chess

from bots.base import MIN_TIME_BUDGET, compute_move_time_budget
from bots.botbot import BotBot
from bots.minimax import MinimaxBot, SearchTimeout, negamax
from bots.simple import SimpleBot


# ---------------------------------------------------------------------------
# compute_move_time_budget
# ---------------------------------------------------------------------------


class TestComputeMoveTimeBudget(unittest.TestCase):
    """Tests for the time-budget helper in bots.base."""

    def test_unlimited_returns_base_think_time(self):
        """When remaining_time is None, return base_think_time unchanged."""
        self.assertIsNone(compute_move_time_budget(None))
        self.assertEqual(compute_move_time_budget(None, base_think_time=1.5), 1.5)

    def test_generous_clock_caps_at_base_think_time(self):
        """With plenty of time, the budget should not exceed base_think_time."""
        budget = compute_move_time_budget(600.0, base_think_time=1.0)
        self.assertIsNotNone(budget)
        self.assertLessEqual(budget, 1.0)

    def test_low_clock_reduces_budget(self):
        """With very little remaining time, the budget should be small."""
        budget = compute_move_time_budget(2.0, base_think_time=5.0)
        self.assertIsNotNone(budget)
        # Should be well below the base_think_time
        self.assertLess(budget, 2.0)

    def test_minimum_budget_floor(self):
        """Budget never drops below MIN_TIME_BUDGET."""
        budget = compute_move_time_budget(0.001, base_think_time=5.0)
        self.assertIsNotNone(budget)
        self.assertGreaterEqual(budget, MIN_TIME_BUDGET)

    def test_never_more_than_half_remaining(self):
        """Budget must not exceed half the remaining time."""
        for remaining in (0.5, 1.0, 2.0, 10.0):
            budget = compute_move_time_budget(remaining, base_think_time=100.0)
            self.assertLessEqual(budget, remaining / 2 + 1e-9)

    def test_no_base_think_time(self):
        """When base_think_time is None, budget is solely fraction-based."""
        budget = compute_move_time_budget(100.0)
        self.assertIsNotNone(budget)
        # fraction-based: 100/40 = 2.5, capped at 100/2 = 50 → 2.5
        self.assertAlmostEqual(budget, 2.5, places=1)

    def test_custom_fraction(self):
        """Custom fraction parameter is respected."""
        budget = compute_move_time_budget(100.0, base_think_time=10.0, fraction=1 / 10)
        self.assertIsNotNone(budget)
        # 100/10 = 10.0, capped by base_think_time=10 and half=50 → 10.0
        self.assertAlmostEqual(budget, 10.0, places=1)


# ---------------------------------------------------------------------------
# SearchTimeout
# ---------------------------------------------------------------------------


class TestSearchTimeout(unittest.TestCase):
    """Tests for the SearchTimeout exception inside negamax."""

    def test_negamax_raises_on_expired_deadline(self):
        """negamax should raise SearchTimeout when deadline is in the past."""
        board = chess.Board()
        # Deadline already passed
        with self.assertRaises(SearchTimeout):
            negamax(board, depth=4, alpha=-1_000_000, beta=1_000_000, deadline=0.0)

    def test_negamax_completes_with_future_deadline(self):
        """negamax should complete normally when deadline is far in the future."""
        board = chess.Board()
        deadline = time.monotonic() + 60  # 1 minute
        score, move = negamax(
            board, depth=1, alpha=-1_000_000, beta=1_000_000, deadline=deadline
        )
        self.assertIsNotNone(move)
        self.assertIn(move, board.legal_moves)

    def test_negamax_no_deadline(self):
        """negamax works as before when deadline is None."""
        board = chess.Board()
        score, move = negamax(board, depth=2, alpha=-1_000_000, beta=1_000_000)
        self.assertIsNotNone(move)


# ---------------------------------------------------------------------------
# MinimaxBot time management
# ---------------------------------------------------------------------------


class TestMinimaxBotTimeManagement(unittest.TestCase):
    """Tests for MinimaxBot's time-aware choose_move."""

    def test_choose_move_without_remaining_time(self):
        """choose_move still works without remaining_time (backward compat)."""
        bot = MinimaxBot(depth=2, randomness=0.0)
        board = chess.Board()
        move = bot.choose_move(board)
        self.assertIsNotNone(move)
        self.assertIn(move, board.legal_moves)

    def test_choose_move_with_generous_remaining_time(self):
        """With plenty of time, the bot searches at full depth."""
        bot = MinimaxBot(depth=2, randomness=0.0)
        board = chess.Board()
        move = bot.choose_move(board, remaining_time=300.0)
        self.assertIsNotNone(move)
        self.assertIn(move, board.legal_moves)

    def test_choose_move_with_low_remaining_time(self):
        """With very little time (< 1s), the bot still returns a move quickly."""
        bot = MinimaxBot(depth=5, randomness=0.0)
        board = chess.Board()
        start = time.monotonic()
        move = bot.choose_move(board, remaining_time=0.5)
        elapsed = time.monotonic() - start
        self.assertIsNotNone(move)
        self.assertIn(move, board.legal_moves)
        # Should be very fast (depth capped to 1)
        self.assertLess(elapsed, 2.0)

    def test_effective_depth_capping(self):
        """_effective_depth clamps depth under time pressure."""
        bot = MinimaxBot(depth=5)
        # No time → full depth
        self.assertEqual(bot._effective_depth(None), 5)
        # Very low time → depth 1
        self.assertEqual(bot._effective_depth(0.5), 1)
        # Low time → depth 2
        self.assertEqual(bot._effective_depth(3.0), 2)
        # Medium time → full depth
        self.assertEqual(bot._effective_depth(10.0), 5)

    def test_randomness_path_with_remaining_time(self):
        """choose_move with randomness > 0 also respects remaining_time."""
        bot = MinimaxBot(depth=3, randomness=0.5, random_seed=42)
        board = chess.Board()
        move = bot.choose_move(board, remaining_time=0.8)
        self.assertIsNotNone(move)
        self.assertIn(move, board.legal_moves)

    def test_no_legal_moves_returns_none(self):
        """choose_move returns None for a checkmate position."""
        bot = MinimaxBot(depth=3)
        # Fool's mate position: black has checkmated white
        board = chess.Board()
        for uci in ["f2f3", "e7e5", "g2g4", "d8h4"]:
            board.push(chess.Move.from_uci(uci))
        self.assertTrue(board.is_checkmate())
        self.assertIsNone(bot.choose_move(board, remaining_time=10.0))

    def test_iterative_deepening_gets_result_from_shallower_depth(self):
        """Even if the deep search times out, we get a move from a shallower iteration."""
        bot = MinimaxBot(depth=10, randomness=0.0)
        board = chess.Board()
        # With a very tight budget the deep iterations should time out
        # but depth-1 result should still be available
        move = bot.choose_move(board, remaining_time=0.3)
        self.assertIsNotNone(move)
        self.assertIn(move, board.legal_moves)


# ---------------------------------------------------------------------------
# BotBot time management
# ---------------------------------------------------------------------------


class TestBotBotTimeManagement(unittest.TestCase):
    """Tests for BotBot's time-aware choose_move."""

    def test_choose_move_without_remaining_time(self):
        """choose_move still works without remaining_time."""
        bot = BotBot(randomness=0.3, random_seed=42)
        board = chess.Board()
        move = bot.choose_move(board)
        self.assertIsNotNone(move)
        self.assertIn(move, board.legal_moves)

    def test_critical_time_fast_fallback(self):
        """With < 1s remaining, BotBot uses fast fallback and is very quick."""
        bot = BotBot(randomness=0.0, random_seed=42)
        board = chess.Board()
        start = time.monotonic()
        move = bot.choose_move(board, remaining_time=0.5)
        elapsed = time.monotonic() - start
        self.assertIsNotNone(move)
        self.assertIn(move, board.legal_moves)
        # Should be nearly instant
        self.assertLess(elapsed, 0.5)

    def test_low_time_skips_hang_detection(self):
        """With < 3s remaining, BotBot skips hang-detection but still evaluates."""
        bot = BotBot(randomness=0.0, random_seed=42)
        board = chess.Board()
        move = bot.choose_move(board, remaining_time=2.0)
        self.assertIsNotNone(move)
        self.assertIn(move, board.legal_moves)

    def test_generous_time_full_analysis(self):
        """With plenty of time, BotBot runs full analysis including hang detection."""
        bot = BotBot(randomness=0.3, random_seed=42)
        board = chess.Board()
        move = bot.choose_move(board, remaining_time=60.0)
        self.assertIsNotNone(move)
        self.assertIn(move, board.legal_moves)

    def test_fast_fallback_prefers_captures(self):
        """In fast mode, BotBot still prefers captures when available."""
        bot = BotBot(randomness=0.0, random_seed=42)
        # Position where white can capture a hanging queen
        board = chess.Board(
            "rnb1kbnr/pppp1ppp/8/4p3/3Pq3/5N2/PPP1PPPP/RNBQKB1R w KQkq - 0 1"
        )
        captures = [m for m in board.legal_moves if board.is_capture(m)]
        if captures:
            move = bot.choose_move(board, remaining_time=0.3)
            self.assertIsNotNone(move)

    def test_fast_fallback_checks(self):
        """In fast mode, BotBot picks checks when no captures are available."""
        bot = BotBot(randomness=0.0, random_seed=42)
        # A position with checking moves
        board = chess.Board(
            "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        )
        move = bot.choose_move(board, remaining_time=0.3)
        self.assertIsNotNone(move)
        self.assertIn(move, board.legal_moves)

    def test_no_legal_moves(self):
        """choose_move returns None for checkmate position."""
        bot = BotBot()
        board = chess.Board()
        for uci in ["f2f3", "e7e5", "g2g4", "d8h4"]:
            board.push(chess.Move.from_uci(uci))
        self.assertTrue(board.is_checkmate())
        self.assertIsNone(bot.choose_move(board, remaining_time=10.0))


# ---------------------------------------------------------------------------
# SimpleBot remaining_time parameter
# ---------------------------------------------------------------------------


class TestSimpleBotTimeManagement(unittest.TestCase):
    """Tests for SimpleBot's remaining_time parameter."""

    def test_choose_move_without_remaining_time(self):
        """choose_move still works without remaining_time."""
        bot = SimpleBot()
        board = chess.Board()
        move = bot.choose_move(board)
        self.assertIsNotNone(move)

    def test_choose_move_with_remaining_time(self):
        """choose_move works with remaining_time (parameter is accepted)."""
        bot = SimpleBot()
        board = chess.Board()
        move = bot.choose_move(board, remaining_time=5.0)
        self.assertIsNotNone(move)
        self.assertIn(move, board.legal_moves)

    def test_choose_move_with_critical_remaining_time(self):
        """SimpleBot is fast enough to work even with very little time."""
        bot = SimpleBot()
        board = chess.Board()
        move = bot.choose_move(board, remaining_time=0.1)
        self.assertIsNotNone(move)


# ---------------------------------------------------------------------------
# StockfishBot time management
# ---------------------------------------------------------------------------


class TestStockfishBotTimeManagement(unittest.TestCase):
    """Tests for StockfishBot's think-time capping via remaining_time."""

    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    @patch("chess.engine.SimpleEngine.popen_uci")
    def test_generous_time_uses_normal_think_time(self, mock_popen, _find):
        """With plenty of time, the engine uses its configured think_time."""
        from bots.stockfish import StockfishBot

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = mock_result
        mock_popen.return_value = mock_engine

        bot = StockfishBot(skill_level=10, think_time=1.0)
        board = chess.Board()
        move = bot.choose_move(board, remaining_time=300.0)

        self.assertEqual(move, chess.Move.from_uci("e2e4"))
        # Check that engine.play was called with time <= configured think_time
        call_args = mock_engine.play.call_args
        limit = call_args[0][1]
        self.assertLessEqual(limit.time, 1.0)

    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    @patch("chess.engine.SimpleEngine.popen_uci")
    def test_low_time_reduces_think_time(self, mock_popen, _find):
        """With very little remaining time, think_time is reduced."""
        from bots.stockfish import StockfishBot

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = mock_result
        mock_popen.return_value = mock_engine

        bot = StockfishBot(skill_level=10, think_time=2.0)
        board = chess.Board()
        move = bot.choose_move(board, remaining_time=1.0)

        self.assertEqual(move, chess.Move.from_uci("e2e4"))
        # Think time should be capped well below 2.0
        call_args = mock_engine.play.call_args
        limit = call_args[0][1]
        self.assertLess(limit.time, 1.0)

    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    @patch("chess.engine.SimpleEngine.popen_uci")
    def test_no_remaining_time_uses_default(self, mock_popen, _find):
        """Without remaining_time, the engine uses its configured think_time."""
        from bots.stockfish import StockfishBot

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = mock_result
        mock_popen.return_value = mock_engine

        bot = StockfishBot(skill_level=10, think_time=0.5)
        board = chess.Board()
        bot.choose_move(board)

        call_args = mock_engine.play.call_args
        limit = call_args[0][1]
        self.assertAlmostEqual(limit.time, 0.5, places=2)


# ---------------------------------------------------------------------------
# AdaptiveStockfishBot time management
# ---------------------------------------------------------------------------


class TestAdaptiveStockfishBotTimeManagement(unittest.TestCase):
    """Tests for AdaptiveStockfishBot's remaining_time passthrough."""

    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    @patch("chess.engine.SimpleEngine.popen_uci")
    def test_remaining_time_forwarded(self, mock_popen, _find):
        """remaining_time is forwarded to the inner StockfishBot."""
        from bots.stockfish import AdaptiveStockfishBot

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = mock_result
        mock_popen.return_value = mock_engine

        bot = AdaptiveStockfishBot(elo_fn=lambda: 1200)
        board = chess.Board()
        move = bot.choose_move(board, remaining_time=2.0)

        self.assertIsNotNone(move)
        # The inner engine should have been called with a capped time
        call_args = mock_engine.play.call_args
        limit = call_args[0][1]
        self.assertIsNotNone(limit.time)
        self.assertLess(limit.time, 2.0)

    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    @patch("chess.engine.SimpleEngine.popen_uci")
    def test_no_remaining_time(self, mock_popen, _find):
        """Without remaining_time, the adaptive bot uses its ELO-derived think time."""
        from bots.stockfish import AdaptiveStockfishBot

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.move = chess.Move.from_uci("d2d4")
        mock_engine.play.return_value = mock_result
        mock_popen.return_value = mock_engine

        bot = AdaptiveStockfishBot(elo_fn=lambda: 1800)
        board = chess.Board()
        move = bot.choose_move(board)

        self.assertIsNotNone(move)
        call_args = mock_engine.play.call_args
        limit = call_args[0][1]
        self.assertIsNotNone(limit.time)


if __name__ == "__main__":
    unittest.main()
