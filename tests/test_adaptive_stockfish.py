"""
Tests for the AdaptiveStockfishBot and elo_to_stockfish_params mapping.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import chess
import chess.engine

from bots.stockfish import (
    AdaptiveStockfishBot,
    _ELO_SKILL_ANCHORS,
    elo_to_stockfish_params,
)


# ---------------------------------------------------------------------------
# elo_to_stockfish_params
# ---------------------------------------------------------------------------


class TestEloToStockfishParams(unittest.TestCase):
    """Tests for the ELO → Stockfish parameter mapping function."""

    def test_very_low_elo_clamped(self):
        """Player ELO far below the anchor range should return the lowest settings."""
        skill, think = elo_to_stockfish_params(100)
        self.assertEqual(skill, _ELO_SKILL_ANCHORS[0][1])
        self.assertAlmostEqual(think, _ELO_SKILL_ANCHORS[0][2])

    def test_very_high_elo_clamped(self):
        """Player ELO far above the anchor range should return the highest settings."""
        skill, think = elo_to_stockfish_params(3500)
        self.assertEqual(skill, _ELO_SKILL_ANCHORS[-1][1])
        self.assertAlmostEqual(think, _ELO_SKILL_ANCHORS[-1][2])

    def test_exact_anchor_points(self):
        """At exact anchor ELOs, values should match the anchor."""
        for elo, expected_skill, expected_time in _ELO_SKILL_ANCHORS:
            skill, think = elo_to_stockfish_params(elo)
            self.assertEqual(skill, expected_skill, f"Skill mismatch at ELO {elo}")
            self.assertAlmostEqual(
                think, expected_time, places=3, msg=f"Think time mismatch at ELO {elo}"
            )

    def test_interpolation_midpoint(self):
        """Values between anchors should be interpolated."""
        # Midpoint between 400 (skill=0) and 600 (skill=1)
        skill, think = elo_to_stockfish_params(500)
        self.assertIn(skill, (0, 1))  # Rounded from 0.5
        self.assertGreater(think, 0)

    def test_skill_always_in_range(self):
        """Skill level should always be between 0 and 20."""
        for elo in range(200, 3200, 100):
            skill, think = elo_to_stockfish_params(elo)
            self.assertGreaterEqual(skill, 0)
            self.assertLessEqual(skill, 20)
            self.assertGreater(think, 0)

    def test_monotonically_increasing(self):
        """Higher ELO should produce equal or higher skill / think time."""
        prev_skill, prev_think = elo_to_stockfish_params(300)
        for elo in range(400, 2600, 50):
            skill, think = elo_to_stockfish_params(elo)
            self.assertGreaterEqual(skill, prev_skill, f"Skill decreased at ELO {elo}")
            self.assertGreaterEqual(
                think, prev_think - 0.001, f"Think time decreased at ELO {elo}"
            )
            prev_skill, prev_think = skill, think

    def test_boundary_elo(self):
        """ELO exactly at the first/last anchor should not error."""
        first_elo = _ELO_SKILL_ANCHORS[0][0]
        last_elo = _ELO_SKILL_ANCHORS[-1][0]
        elo_to_stockfish_params(first_elo)
        elo_to_stockfish_params(last_elo)


# ---------------------------------------------------------------------------
# AdaptiveStockfishBot construction
# ---------------------------------------------------------------------------


def _make_mock_engine() -> MagicMock:
    engine = MagicMock(spec=chess.engine.SimpleEngine)
    engine.ping.return_value = None
    engine.configure.return_value = None
    engine.quit.return_value = None
    return engine


class TestAdaptiveStockfishBotInit(unittest.TestCase):
    """Tests for AdaptiveStockfishBot initialisation."""

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_name(self, _find):
        bot = AdaptiveStockfishBot(elo_fn=lambda: 1000)
        self.assertEqual(bot.name, "Stockfish (Adaptive)")

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_initial_state(self, _find):
        bot = AdaptiveStockfishBot(elo_fn=lambda: 1200)
        self.assertIsNone(bot._bot)
        self.assertIsNone(bot.current_skill_level)
        self.assertIsNone(bot.current_think_time)


# ---------------------------------------------------------------------------
# AdaptiveStockfishBot move selection (mocked)
# ---------------------------------------------------------------------------


class TestAdaptiveStockfishBotChooseMove(unittest.TestCase):
    """Tests for choose_move with dynamic ELO-based skill adjustment."""

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_choose_move_uses_elo(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = play_result

        current_elo = 1200
        bot = AdaptiveStockfishBot(elo_fn=lambda: current_elo)
        board = chess.Board()
        move = bot.choose_move(board)

        self.assertIsNotNone(move)
        self.assertEqual(move, chess.Move.from_uci("e2e4"))
        # Skill should have been set based on ELO 1200
        expected_skill, expected_think = elo_to_stockfish_params(1200)
        self.assertEqual(bot.current_skill_level, expected_skill)
        self.assertAlmostEqual(bot.current_think_time, expected_think, places=3)

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_skill_changes_with_elo(self, _find, mock_popen):
        """When player ELO changes enough, the bot should reconfigure."""
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = play_result

        elo_box = [800]
        bot = AdaptiveStockfishBot(elo_fn=lambda: elo_box[0])
        board = chess.Board()

        bot.choose_move(board)
        skill_at_800 = bot.current_skill_level

        # Raise ELO significantly
        elo_box[0] = 2000
        bot.choose_move(board)
        skill_at_2000 = bot.current_skill_level

        self.assertGreater(skill_at_2000, skill_at_800)

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_choose_move_no_binary(self, _find):
        """choose_move returns None gracefully when no binary found."""
        bot = AdaptiveStockfishBot(elo_fn=lambda: 1000)
        self.assertIsNone(bot.choose_move(chess.Board()))


# ---------------------------------------------------------------------------
# AdaptiveStockfishBot lifecycle
# ---------------------------------------------------------------------------


class TestAdaptiveStockfishBotLifecycle(unittest.TestCase):
    """Tests for close / set_chess960."""

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_close_safe_when_no_engine(self, _find):
        bot = AdaptiveStockfishBot(elo_fn=lambda: 1000)
        bot.close()  # Should not raise

    @patch("chess.engine.SimpleEngine.popen_uci")
    @patch("bots.stockfish.find_stockfish_path", return_value="/usr/bin/stockfish")
    def test_close_shuts_inner_bot(self, _find, mock_popen):
        mock_engine = _make_mock_engine()
        mock_popen.return_value = mock_engine

        play_result = MagicMock()
        play_result.move = chess.Move.from_uci("e2e4")
        mock_engine.play.return_value = play_result

        bot = AdaptiveStockfishBot(elo_fn=lambda: 1000)
        bot.choose_move(chess.Board())
        self.assertIsNotNone(bot._bot)

        bot.close()
        self.assertIsNone(bot._bot)
        self.assertIsNone(bot.current_skill_level)
        self.assertIsNone(bot.current_think_time)

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_set_chess960_resets(self, _find):
        bot = AdaptiveStockfishBot(elo_fn=lambda: 1000)
        self.assertFalse(bot.chess960)
        bot.set_chess960(True)
        self.assertTrue(bot.chess960)

    @patch("bots.stockfish.find_stockfish_path", return_value=None)
    def test_set_chess960_no_change_no_close(self, _find):
        bot = AdaptiveStockfishBot(elo_fn=lambda: 1000, chess960=True)
        # Setting to same value should be a no-op
        bot.set_chess960(True)
        self.assertTrue(bot.chess960)

    def test_is_mode_supported(self):
        self.assertTrue(AdaptiveStockfishBot.is_mode_supported("standard"))
        self.assertTrue(AdaptiveStockfishBot.is_mode_supported("chess960"))
        self.assertFalse(AdaptiveStockfishBot.is_mode_supported("antichess"))


# ---------------------------------------------------------------------------
# Integration with ELO system
# ---------------------------------------------------------------------------


class TestAdaptiveStockfishEloIntegration(unittest.TestCase):
    """Verify the adaptive bot is properly registered in the ELO system."""

    def test_adaptive_in_bot_elo(self):
        from elo import BOT_ELO, BOT_DISPLAY_NAMES

        self.assertIn("stockfish_adaptive", BOT_ELO)
        self.assertIn("stockfish_adaptive", BOT_DISPLAY_NAMES)

    def test_adaptive_bot_elo_matches_player(self):
        from elo import get_bot_elo

        # Adaptive bot's ELO should equal the player's
        self.assertEqual(get_bot_elo("stockfish_adaptive", player_elo=1200), 1200)
        self.assertEqual(get_bot_elo("stockfish_adaptive", player_elo=800), 800)
        self.assertEqual(get_bot_elo("stockfish_adaptive", player_elo=2500), 2500)

    def test_adaptive_bot_elo_default_fallback(self):
        from elo import DEFAULT_RATING, get_bot_elo

        # When player_elo is not given, should fall back to DEFAULT_RATING
        self.assertEqual(get_bot_elo("stockfish_adaptive"), DEFAULT_RATING)

    def test_regular_bots_unaffected(self):
        """get_bot_elo for regular bots should be unchanged."""
        from elo import BOT_ELO, get_bot_elo

        for key in ("random", "botbot", "minimax_1", "stockfish_1"):
            self.assertEqual(get_bot_elo(key), BOT_ELO[key])

    def test_record_game_adaptive(self):
        """Recording a game against adaptive bot uses player's rating as opponent ELO."""
        from elo import EloProfile, record_game

        profile = EloProfile(rating=1200)
        rec = record_game(profile, "stockfish_adaptive", 1.0)
        # Opponent ELO should equal the player's pre-game rating
        self.assertEqual(rec.opponent_elo, 1200)

    def test_record_game_adaptive_draw(self):
        """A draw against the adaptive bot (equal ELO) should barely change rating."""
        from elo import EloProfile, record_game

        profile = EloProfile(rating=1500)
        rec = record_game(profile, "stockfish_adaptive", 0.5)
        # Draw against equal-rated: rating should not change
        self.assertEqual(rec.rating_after, 1500)

    def test_recommend_opponent_excludes_adaptive(self):
        """recommend_opponent should not suggest the adaptive bot."""
        from elo import recommend_opponent

        for elo in (400, 800, 1200, 1600, 2000, 2500):
            rec = recommend_opponent(elo)
            self.assertNotEqual(rec, "stockfish_adaptive")

    def test_is_game_ratable_adaptive(self):
        """Games against the adaptive bot should be ratable."""
        from elo import is_game_ratable

        self.assertTrue(is_game_ratable("human", "stockfish_adaptive"))
        self.assertTrue(is_game_ratable("stockfish_adaptive", "human"))

    def test_import_from_package(self):
        from bots import AdaptiveStockfishBot, elo_to_stockfish_params

        self.assertIsNotNone(AdaptiveStockfishBot)
        self.assertIsNotNone(elo_to_stockfish_params)


# ---------------------------------------------------------------------------
# ELO reset (verifying existing functionality)
# ---------------------------------------------------------------------------


class TestEloReset(unittest.TestCase):
    """Tests verifying that the ELO reset mechanism works correctly."""

    def test_reset_clears_profile(
        self,
    ):
        """Resetting ELO should delete the save file and return a fresh profile."""
        from elo import (
            DEFAULT_RATING,
            EloProfile,
            load_elo_profile,
            record_game,
            reset_elo_profile,
            save_elo_profile,
        )
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "elo_test.json"
            # Build up a profile with history
            profile = EloProfile()
            record_game(profile, "random", 1.0)
            record_game(profile, "botbot", 0.0)
            record_game(profile, "minimax_1", 1.0)
            save_elo_profile(profile, path)
            self.assertTrue(path.exists())
            self.assertGreater(profile.games_played, 0)

            # Reset
            self.assertTrue(reset_elo_profile(path))
            self.assertFalse(path.exists())

            # Load should give a fresh profile
            fresh = load_elo_profile(path)
            self.assertEqual(fresh.rating, DEFAULT_RATING)
            self.assertEqual(fresh.games_played, 0)
            self.assertEqual(fresh.wins, 0)
            self.assertEqual(fresh.losses, 0)
            self.assertEqual(fresh.draws, 0)
            self.assertEqual(fresh.history, [])
            self.assertEqual(fresh.peak_rating, DEFAULT_RATING)

    def test_reset_nonexistent_file(self):
        """Resetting when no profile exists should succeed gracefully."""
        from elo import reset_elo_profile
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "does_not_exist.json"
            self.assertTrue(reset_elo_profile(path))


if __name__ == "__main__":
    unittest.main()
