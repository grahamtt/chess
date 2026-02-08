"""Tests for puzzle_progress module: rating calculation, progress tracking, persistence."""

import json
import time

import pytest

from puzzle_progress import (
    DEFAULT_PLAYER_RATING,
    K_FACTOR,
    UNLOCK_MARGIN,
    PuzzleProgress,
    PuzzleStats,
    _calculate_new_rating,
    _dict_to_progress,
    _progress_to_dict,
    clear_puzzle_progress,
    load_puzzle_progress,
    save_puzzle_progress,
)


# -------------------------------------------------------------------------
# Rating calculation
# -------------------------------------------------------------------------


class TestRatingCalculation:
    """Test the Elo-like rating formula."""

    def test_solve_easy_puzzle_small_gain(self):
        """Solving a puzzle far below your rating gives small gain."""
        new = _calculate_new_rating(1500, 800, solved=True)
        assert new > 1500  # Should increase
        assert new - 1500 < K_FACTOR // 2  # But not by much

    def test_solve_hard_puzzle_big_gain(self):
        """Solving a puzzle far above your rating gives big gain."""
        new = _calculate_new_rating(800, 1500, solved=True)
        assert new > 800
        gain = new - 800
        # Gain should be close to K_FACTOR (since expected is low)
        assert gain > K_FACTOR // 2

    def test_fail_easy_puzzle_big_loss(self):
        """Failing a puzzle far below your rating causes big loss."""
        new = _calculate_new_rating(1500, 800, solved=False)
        assert new < 1500
        loss = 1500 - new
        assert loss > K_FACTOR // 2

    def test_fail_hard_puzzle_small_loss(self):
        """Failing a puzzle far above your rating causes small loss."""
        new = _calculate_new_rating(800, 1500, solved=False)
        assert new < 800
        loss = 800 - new
        assert loss < K_FACTOR // 2

    def test_solve_equal_rating(self):
        """Solving a puzzle at your exact rating gives moderate gain."""
        new = _calculate_new_rating(1200, 1200, solved=True)
        gain = new - 1200
        expected_gain = K_FACTOR // 2  # ~16 when expected is 0.5
        assert abs(gain - expected_gain) <= 1

    def test_fail_equal_rating(self):
        """Failing a puzzle at your exact rating gives moderate loss."""
        new = _calculate_new_rating(1200, 1200, solved=False)
        loss = 1200 - new
        expected_loss = K_FACTOR // 2
        assert abs(loss - expected_loss) <= 1

    def test_rating_clamped_low(self):
        """Rating should not drop below 100."""
        new = _calculate_new_rating(100, 100, solved=False)
        assert new >= 100

    def test_rating_clamped_high(self):
        """Rating should not exceed 3000."""
        new = _calculate_new_rating(3000, 3000, solved=True)
        assert new <= 3000

    def test_free_play_no_change(self):
        """Free play puzzles (rating 0) should not affect player rating."""
        assert _calculate_new_rating(1200, 0, solved=True) == 1200
        assert _calculate_new_rating(1200, 0, solved=False) == 1200

    def test_symmetry(self):
        """Gain from solving should equal loss from failing at same difficulty."""
        gain = _calculate_new_rating(1200, 1200, True) - 1200
        loss = 1200 - _calculate_new_rating(1200, 1200, False)
        assert abs(gain - loss) <= 1  # May differ by 1 due to rounding


# -------------------------------------------------------------------------
# PuzzleStats
# -------------------------------------------------------------------------


class TestPuzzleStats:
    def test_initial_stats(self):
        stats = PuzzleStats(puzzle_id="test")
        assert stats.attempts == 0
        assert stats.solved is False
        assert stats.best_time_secs is None

    def test_record_solve(self):
        stats = PuzzleStats(puzzle_id="test")
        stats.record_attempt(solved=True, time_secs=5.0)
        assert stats.attempts == 1
        assert stats.solved is True
        assert stats.best_time_secs == 5.0

    def test_record_failure(self):
        stats = PuzzleStats(puzzle_id="test")
        stats.record_attempt(solved=False, time_secs=3.0)
        assert stats.attempts == 1
        assert stats.solved is False
        assert stats.best_time_secs is None

    def test_best_time_tracks_minimum(self):
        stats = PuzzleStats(puzzle_id="test")
        stats.record_attempt(solved=True, time_secs=10.0)
        stats.record_attempt(solved=True, time_secs=5.0)
        stats.record_attempt(solved=True, time_secs=7.0)
        assert stats.best_time_secs == 5.0

    def test_mixed_attempts(self):
        stats = PuzzleStats(puzzle_id="test")
        stats.record_attempt(solved=False, time_secs=2.0)
        stats.record_attempt(solved=True, time_secs=4.0)
        stats.record_attempt(solved=False, time_secs=1.0)
        assert stats.attempts == 3
        assert stats.solved is True
        assert stats.best_time_secs == 4.0

    def test_solved_stays_true_after_failure(self):
        """Once a puzzle is solved, it stays solved even if a later attempt fails."""
        stats = PuzzleStats(puzzle_id="test")
        stats.record_attempt(solved=True, time_secs=5.0)
        assert stats.solved is True
        stats.record_attempt(solved=False, time_secs=3.0)
        assert stats.solved is True

    def test_last_attempted_timestamp(self):
        stats = PuzzleStats(puzzle_id="test")
        before = time.time()
        stats.record_attempt(solved=True, time_secs=1.0)
        after = time.time()
        assert before <= stats.last_attempted <= after


# -------------------------------------------------------------------------
# PuzzleProgress
# -------------------------------------------------------------------------


class TestPuzzleProgress:
    def test_defaults(self):
        p = PuzzleProgress()
        assert p.player_rating == DEFAULT_PLAYER_RATING
        assert p.total_attempted == 0
        assert p.total_solved == 0
        assert p.current_streak == 0
        assert p.best_streak == 0
        assert p.solve_rate == 0.0
        assert p.average_time is None

    def test_record_solve(self):
        p = PuzzleProgress()
        attempt = p.record_attempt("p1", 1000, True, 5.0, 1)
        assert p.total_attempted == 1
        assert p.total_solved == 1
        assert p.current_streak == 1
        assert p.best_streak == 1
        assert attempt.solved
        assert attempt.rating_before == DEFAULT_PLAYER_RATING

    def test_record_failure(self):
        p = PuzzleProgress()
        attempt = p.record_attempt("p1", 1000, False, 3.0, 2)
        assert p.total_attempted == 1
        assert p.total_solved == 0
        assert p.current_streak == 0
        assert not attempt.solved

    def test_streak_tracking(self):
        p = PuzzleProgress()
        p.record_attempt("p1", 800, True, 1.0, 1)
        p.record_attempt("p2", 800, True, 1.0, 1)
        p.record_attempt("p3", 800, True, 1.0, 1)
        assert p.current_streak == 3
        assert p.best_streak == 3

        p.record_attempt("p4", 800, False, 1.0, 1)
        assert p.current_streak == 0
        assert p.best_streak == 3  # Best streak preserved

        p.record_attempt("p5", 800, True, 1.0, 1)
        p.record_attempt("p6", 800, True, 1.0, 1)
        assert p.current_streak == 2
        assert p.best_streak == 3  # Still 3

    def test_rating_increases_on_solve(self):
        p = PuzzleProgress()
        initial = p.player_rating
        p.record_attempt("p1", 1000, True, 1.0, 1)
        assert p.player_rating > initial

    def test_rating_decreases_on_failure(self):
        p = PuzzleProgress()
        initial = p.player_rating
        p.record_attempt("p1", 1000, False, 1.0, 1)
        assert p.player_rating < initial

    def test_free_play_no_rating_change(self):
        p = PuzzleProgress()
        initial = p.player_rating
        p.record_attempt("fp", 0, True, 1.0, 1)
        assert p.player_rating == initial
        # But stats are still tracked
        assert p.total_attempted == 1
        assert p.total_solved == 1

    def test_puzzle_unlocking(self):
        p = PuzzleProgress()
        p.player_rating = 1000

        # Free play always unlocked
        assert p.is_puzzle_unlocked(0)

        # Within range
        assert p.is_puzzle_unlocked(1000)
        assert p.is_puzzle_unlocked(1000 + UNLOCK_MARGIN)

        # Just out of range
        assert not p.is_puzzle_unlocked(1000 + UNLOCK_MARGIN + 1)

        # Easy puzzle always unlocked
        assert p.is_puzzle_unlocked(600)

    def test_get_stats_for_puzzle_creates_new(self):
        p = PuzzleProgress()
        stats = p.get_stats_for_puzzle("new_puzzle")
        assert stats.puzzle_id == "new_puzzle"
        assert stats.attempts == 0

    def test_get_stats_for_puzzle_returns_existing(self):
        p = PuzzleProgress()
        p.record_attempt("p1", 800, True, 5.0, 1)
        stats = p.get_stats_for_puzzle("p1")
        assert stats.attempts == 1
        assert stats.solved is True

    def test_solve_rate_property(self):
        p = PuzzleProgress()
        p.record_attempt("p1", 800, True, 1.0, 1)
        p.record_attempt("p2", 800, False, 1.0, 1)
        p.record_attempt("p3", 800, True, 1.0, 1)
        assert p.solve_rate == pytest.approx(2 / 3)

    def test_average_time(self):
        p = PuzzleProgress()
        p.record_attempt("p1", 800, True, 4.0, 1)
        p.record_attempt("p2", 800, True, 6.0, 1)
        assert p.average_time == pytest.approx(5.0)

    def test_average_time_ignores_failures(self):
        p = PuzzleProgress()
        p.record_attempt("p1", 800, True, 4.0, 1)
        p.record_attempt("p2", 800, False, 100.0, 1)  # Should not count
        assert p.average_time == pytest.approx(4.0)

    def test_recent_attempts_capped(self):
        p = PuzzleProgress()
        for i in range(150):
            p.record_attempt(f"p{i}", 800, True, 1.0, 1)
        assert len(p.recent_attempts) == 100

    def test_rating_change_display(self):
        p = PuzzleProgress()
        assert p.get_rating_change_display() == ""
        p.record_attempt("p1", 1000, True, 1.0, 1)
        display = p.get_rating_change_display()
        assert display.startswith("+")

        p.record_attempt("p2", 1000, False, 1.0, 1)
        display = p.get_rating_change_display()
        assert display.startswith("-")


# -------------------------------------------------------------------------
# Serialization / persistence
# -------------------------------------------------------------------------


class TestSerialization:
    def test_roundtrip_dict(self):
        p = PuzzleProgress()
        p.record_attempt("p1", 1000, True, 5.0, 1)
        p.record_attempt("p2", 800, False, 3.0, 2)

        data = _progress_to_dict(p)
        restored = _dict_to_progress(data)

        assert restored.player_rating == p.player_rating
        assert restored.total_attempted == p.total_attempted
        assert restored.total_solved == p.total_solved
        assert restored.current_streak == p.current_streak
        assert restored.best_streak == p.best_streak
        assert len(restored.puzzle_stats) == len(p.puzzle_stats)
        assert len(restored.recent_attempts) == len(p.recent_attempts)

    def test_roundtrip_file(self, tmp_path):
        path = tmp_path / "test_progress.json"
        p = PuzzleProgress()
        p.record_attempt("p1", 1000, True, 5.0, 1)
        p.record_attempt("p2", 1200, True, 3.0, 1)

        assert save_puzzle_progress(p, path)
        loaded = load_puzzle_progress(path)

        assert loaded.player_rating == p.player_rating
        assert loaded.total_attempted == 2
        assert loaded.total_solved == 2
        assert loaded.current_streak == 2

    def test_load_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        loaded = load_puzzle_progress(path)
        assert loaded.player_rating == DEFAULT_PLAYER_RATING
        assert loaded.total_attempted == 0

    def test_load_corrupt_file(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("not valid json {{{")
        loaded = load_puzzle_progress(path)
        assert loaded.player_rating == DEFAULT_PLAYER_RATING

    def test_load_non_dict_json(self, tmp_path):
        path = tmp_path / "array.json"
        path.write_text("[1,2,3]")
        loaded = load_puzzle_progress(path)
        assert loaded.player_rating == DEFAULT_PLAYER_RATING

    def test_clear_progress(self, tmp_path):
        path = tmp_path / "test_progress.json"
        p = PuzzleProgress()
        save_puzzle_progress(p, path)
        assert path.exists()

        assert clear_puzzle_progress(path)
        assert not path.exists()

    def test_clear_nonexistent(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        assert clear_puzzle_progress(path)  # Should succeed (already absent)

    def test_save_creates_file(self, tmp_path):
        path = tmp_path / "new_progress.json"
        p = PuzzleProgress()
        assert save_puzzle_progress(p, path)
        assert path.exists()

        # Verify it's valid JSON
        data = json.loads(path.read_text())
        assert isinstance(data, dict)
        assert "player_rating" in data

    def test_dict_to_progress_handles_missing_keys(self):
        """Partial data should still deserialize."""
        data = {"player_rating": 1500}
        p = _dict_to_progress(data)
        assert p.player_rating == 1500
        assert p.total_attempted == 0
        assert p.puzzle_stats == {}

    def test_dict_to_progress_skips_bad_attempts(self):
        """Malformed attempt entries should be skipped."""
        data = {
            "player_rating": 1000,
            "recent_attempts": [
                {"puzzle_id": "p1"},  # Missing fields -> skipped
                {
                    "puzzle_id": "p2",
                    "timestamp": 1.0,
                    "solved": True,
                    "time_secs": 2.0,
                    "moves_made": 1,
                    "rating_before": 1000,
                    "rating_after": 1016,
                },
            ],
        }
        p = _dict_to_progress(data)
        assert len(p.recent_attempts) == 1
        assert p.recent_attempts[0].puzzle_id == "p2"


# -------------------------------------------------------------------------
# Integration: PuzzleProgress + real puzzles
# -------------------------------------------------------------------------


class TestIntegration:
    def test_solve_multiple_puzzles_rating_progression(self):
        """Player rating should increase when consistently solving puzzles."""
        p = PuzzleProgress()
        initial = p.player_rating

        # Solve 10 puzzles at player's level
        for i in range(10):
            p.record_attempt(f"p{i}", p.player_rating, True, 5.0, 1)

        assert p.player_rating > initial
        assert p.total_solved == 10
        assert p.current_streak == 10

    def test_fail_multiple_puzzles_rating_decreases(self):
        """Player rating should decrease when consistently failing."""
        p = PuzzleProgress()
        initial = p.player_rating

        for i in range(10):
            p.record_attempt(f"p{i}", p.player_rating, False, 5.0, 1)

        assert p.player_rating < initial
        assert p.total_solved == 0
        assert p.current_streak == 0

    def test_progressive_unlocking(self):
        """As rating rises, harder puzzles should unlock."""
        p = PuzzleProgress()
        p.player_rating = 800

        # Can't access expert puzzles at 800
        assert not p.is_puzzle_unlocked(1800)

        # Raise rating
        p.player_rating = 1600
        assert p.is_puzzle_unlocked(1800)  # Within UNLOCK_MARGIN
