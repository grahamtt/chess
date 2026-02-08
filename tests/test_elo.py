"""Tests for the ELO rating system module."""

import json
import math

import pytest
from elo import (
    BOT_DISPLAY_NAMES,
    BOT_ELO,
    BOT_LADDER,
    DEFAULT_RATING,
    EloProfile,
    GameRecord,
    calculate_new_rating,
    expected_score,
    get_bot_display_name,
    get_bot_elo,
    get_difficulty_label,
    get_recent_form,
    get_win_rate,
    k_factor,
    load_elo_profile,
    recommend_opponent,
    record_game,
    reset_elo_profile,
    save_elo_profile,
)


# ---------------------------------------------------------------------------
# ELO calculation helpers
# ---------------------------------------------------------------------------


class TestExpectedScore:
    def test_equal_rating(self):
        """Equal ratings should give 0.5 expected score."""
        assert expected_score(1200, 1200) == pytest.approx(0.5)

    def test_higher_rated_player(self):
        """Higher-rated player should have expected score > 0.5."""
        score = expected_score(1400, 1200)
        assert score > 0.5
        assert score < 1.0

    def test_lower_rated_player(self):
        """Lower-rated player should have expected score < 0.5."""
        score = expected_score(1000, 1400)
        assert score < 0.5
        assert score > 0.0

    def test_400_point_difference(self):
        """A 400-point gap should give ~0.91 for the stronger player."""
        score = expected_score(1600, 1200)
        assert score == pytest.approx(1.0 / (1.0 + math.pow(10.0, -1.0)), abs=0.001)

    def test_symmetric(self):
        """Expected scores for both sides should sum to 1.0."""
        e1 = expected_score(1200, 1500)
        e2 = expected_score(1500, 1200)
        assert (e1 + e2) == pytest.approx(1.0)

    def test_very_large_gap(self):
        """Extreme rating gap should approach 0 for the weaker player."""
        score = expected_score(400, 2800)
        assert score < 0.01

    def test_very_large_gap_strong(self):
        """Extreme rating gap should approach 1 for the stronger player."""
        score = expected_score(2800, 400)
        assert score > 0.99


class TestKFactor:
    def test_new_player(self):
        assert k_factor(0) == 40
        assert k_factor(5) == 40
        assert k_factor(9) == 40

    def test_intermediate_player(self):
        assert k_factor(10) == 32
        assert k_factor(20) == 32
        assert k_factor(29) == 32

    def test_experienced_player(self):
        assert k_factor(30) == 24
        assert k_factor(100) == 24
        assert k_factor(1000) == 24


class TestCalculateNewRating:
    def test_win_against_equal(self):
        """Win against equally-rated player should increase rating."""
        new = calculate_new_rating(1200, 1200, 1.0, 0)
        assert new > 1200

    def test_loss_against_equal(self):
        """Loss against equally-rated player should decrease rating."""
        new = calculate_new_rating(1200, 1200, 0.0, 0)
        assert new < 1200

    def test_draw_against_equal(self):
        """Draw against equally-rated player should not change rating."""
        new = calculate_new_rating(1200, 1200, 0.5, 0)
        assert new == 1200

    def test_win_against_stronger(self):
        """Win against much stronger opponent should give big boost."""
        new = calculate_new_rating(1000, 1400, 1.0, 0)
        gain = new - 1000
        # Compare against win vs equal opponent
        new_equal = calculate_new_rating(1000, 1000, 1.0, 0)
        gain_equal = new_equal - 1000
        assert gain > gain_equal

    def test_loss_against_weaker(self):
        """Loss against much weaker opponent should cause big drop."""
        new = calculate_new_rating(1400, 1000, 0.0, 0)
        drop = 1400 - new
        # Compare against loss vs equal opponent
        new_equal = calculate_new_rating(1400, 1400, 0.0, 0)
        drop_equal = 1400 - new_equal
        assert drop > drop_equal

    def test_minimum_rating_floor(self):
        """Rating should never drop below 100."""
        new = calculate_new_rating(100, 2000, 0.0, 0)
        assert new >= 100

    def test_k_factor_affects_magnitude(self):
        """Higher K-factor (fewer games) should cause larger rating changes."""
        new_high_k = calculate_new_rating(1200, 1200, 1.0, 0)  # K=40
        new_low_k = calculate_new_rating(1200, 1200, 1.0, 50)  # K=24
        gain_high = new_high_k - 1200
        gain_low = new_low_k - 1200
        assert gain_high > gain_low

    def test_result_is_rounded(self):
        """New rating should be an integer."""
        new = calculate_new_rating(1000, 1200, 1.0, 5)
        assert isinstance(new, int)


# ---------------------------------------------------------------------------
# Difficulty recommendation
# ---------------------------------------------------------------------------


class TestRecommendOpponent:
    def test_beginner(self):
        """Very low-rated player should face the weakest bot."""
        rec = recommend_opponent(400)
        assert rec == "random"

    def test_intermediate(self):
        """Player around 1100 should face minimax_1."""
        rec = recommend_opponent(1100)
        assert rec == "minimax_1"

    def test_strong(self):
        """Very strong player should face the strongest bot."""
        rec = recommend_opponent(2000)
        assert rec == "minimax_4"

    def test_exact_bot_elo(self):
        """Player exactly at a bot's ELO should recommend that bot."""
        for key, elo in BOT_ELO.items():
            assert recommend_opponent(elo) == key

    def test_between_bots(self):
        """Player between two bots should get the closer one."""
        # Between botbot (900) and minimax_1 (1100)
        rec = recommend_opponent(950)
        assert rec == "botbot"
        rec = recommend_opponent(1050)
        assert rec == "minimax_1"
        # Exact midpoint (1000) — equidistant, should pick the first one found
        rec = recommend_opponent(1000)
        assert rec in ("botbot", "minimax_1")


class TestDifficultyLabel:
    def test_beginner(self):
        assert get_difficulty_label(500) == "Beginner"
        assert get_difficulty_label(699) == "Beginner"

    def test_casual(self):
        assert get_difficulty_label(700) == "Casual"
        assert get_difficulty_label(999) == "Casual"

    def test_intermediate(self):
        assert get_difficulty_label(1000) == "Intermediate"
        assert get_difficulty_label(1299) == "Intermediate"

    def test_advanced(self):
        assert get_difficulty_label(1300) == "Advanced"
        assert get_difficulty_label(1599) == "Advanced"

    def test_expert(self):
        assert get_difficulty_label(1600) == "Expert"
        assert get_difficulty_label(2500) == "Expert"


class TestBotEloHelpers:
    def test_get_bot_elo_known(self):
        assert get_bot_elo("random") == 600
        assert get_bot_elo("minimax_4") == 1700

    def test_get_bot_elo_unknown(self):
        assert get_bot_elo("nonexistent") is None

    def test_get_bot_display_name_known(self):
        assert get_bot_display_name("random") == "Random"
        assert get_bot_display_name("minimax_2") == "Minimax 2"

    def test_get_bot_display_name_unknown(self):
        assert get_bot_display_name("unknown_bot") == "unknown_bot"

    def test_bot_ladder_ordering(self):
        """BOT_LADDER should be sorted by ELO ascending."""
        elos = [BOT_ELO[k] for k in BOT_LADDER]
        assert elos == sorted(elos)

    def test_all_bots_have_display_names(self):
        for key in BOT_ELO:
            assert key in BOT_DISPLAY_NAMES


# ---------------------------------------------------------------------------
# GameRecord and EloProfile
# ---------------------------------------------------------------------------


class TestGameRecord:
    def test_creation(self):
        rec = GameRecord(
            opponent="minimax_2",
            opponent_elo=1300,
            result=1.0,
            rating_before=1000,
            rating_after=1030,
            timestamp=1700000000.0,
        )
        assert rec.opponent == "minimax_2"
        assert rec.result == 1.0
        assert rec.rating_after > rec.rating_before


class TestEloProfile:
    def test_defaults(self):
        p = EloProfile()
        assert p.rating == DEFAULT_RATING
        assert p.games_played == 0
        assert p.wins == 0
        assert p.draws == 0
        assert p.losses == 0
        assert p.history == []
        assert p.peak_rating == DEFAULT_RATING

    def test_custom_values(self):
        p = EloProfile(rating=1500, games_played=20, wins=12, losses=6, draws=2)
        assert p.rating == 1500
        assert p.games_played == 20
        assert p.wins == 12


# ---------------------------------------------------------------------------
# record_game
# ---------------------------------------------------------------------------


class TestRecordGame:
    def test_record_win(self):
        profile = EloProfile()
        rec = record_game(profile, "minimax_1", 1.0)
        assert profile.games_played == 1
        assert profile.wins == 1
        assert profile.losses == 0
        assert profile.draws == 0
        assert profile.rating > DEFAULT_RATING
        assert rec.result == 1.0
        assert rec.rating_before == DEFAULT_RATING
        assert rec.rating_after == profile.rating
        assert len(profile.history) == 1

    def test_record_loss(self):
        profile = EloProfile()
        rec = record_game(profile, "random", 0.0)
        assert profile.games_played == 1
        assert profile.losses == 1
        assert profile.rating < DEFAULT_RATING
        assert rec.result == 0.0

    def test_record_draw(self):
        profile = EloProfile()
        rec = record_game(profile, "botbot", 0.5)
        assert profile.games_played == 1
        assert profile.draws == 1
        # Draw against 900-rated bot: player is 1000, should lose a little
        assert rec.result == 0.5

    def test_multiple_games(self):
        profile = EloProfile()
        record_game(profile, "random", 1.0)
        record_game(profile, "botbot", 1.0)
        record_game(profile, "minimax_1", 0.0)
        assert profile.games_played == 3
        assert profile.wins == 2
        assert profile.losses == 1
        assert len(profile.history) == 3

    def test_peak_rating_tracked(self):
        profile = EloProfile()
        record_game(profile, "minimax_2", 1.0)
        peak_after_win = profile.peak_rating
        assert peak_after_win > DEFAULT_RATING
        # Now lose a few games
        for _ in range(5):
            record_game(profile, "random", 0.0)
        assert profile.rating < peak_after_win
        assert profile.peak_rating == peak_after_win  # Peak should not decrease

    def test_unknown_opponent_uses_default_elo(self):
        profile = EloProfile()
        rec = record_game(profile, "unknown_bot_key", 1.0)
        assert rec.opponent_elo == DEFAULT_RATING

    def test_timestamp_set(self):
        profile = EloProfile()
        rec = record_game(profile, "random", 1.0)
        assert rec.timestamp > 0


# ---------------------------------------------------------------------------
# Persistence: save / load / reset
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_save_and_load(self, tmp_path):
        path = tmp_path / "elo.json"
        profile = EloProfile(rating=1250, games_played=10, wins=7, losses=2, draws=1)
        record_game(profile, "minimax_1", 1.0)

        assert save_elo_profile(profile, path)
        loaded = load_elo_profile(path)

        assert loaded.rating == profile.rating
        assert loaded.games_played == profile.games_played
        assert loaded.wins == profile.wins
        assert loaded.losses == profile.losses
        assert loaded.draws == profile.draws
        assert loaded.peak_rating == profile.peak_rating
        assert len(loaded.history) == len(profile.history)

    def test_load_missing_file(self, tmp_path):
        path = tmp_path / "does_not_exist.json"
        profile = load_elo_profile(path)
        assert profile.rating == DEFAULT_RATING
        assert profile.games_played == 0

    def test_load_corrupt_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{{not valid json", encoding="utf-8")
        profile = load_elo_profile(path)
        assert profile.rating == DEFAULT_RATING

    def test_load_non_dict_json(self, tmp_path):
        path = tmp_path / "list.json"
        path.write_text("[1,2,3]", encoding="utf-8")
        profile = load_elo_profile(path)
        assert profile.rating == DEFAULT_RATING

    def test_load_ignores_unknown_keys(self, tmp_path):
        path = tmp_path / "extra.json"
        data = {
            "rating": 1400,
            "games_played": 5,
            "wins": 3,
            "draws": 1,
            "losses": 1,
            "history": [],
            "peak_rating": 1400,
            "some_future_field": True,
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = load_elo_profile(path)
        assert loaded.rating == 1400
        assert not hasattr(loaded, "some_future_field")

    def test_reset(self, tmp_path):
        path = tmp_path / "elo.json"
        save_elo_profile(EloProfile(rating=1500), path)
        assert path.exists()
        assert reset_elo_profile(path)
        assert not path.exists()

    def test_reset_missing(self, tmp_path):
        path = tmp_path / "nope.json"
        assert reset_elo_profile(path)

    def test_save_atomic_no_leftover_tmp(self, tmp_path):
        path = tmp_path / "elo.json"
        save_elo_profile(EloProfile(), path)
        assert not (tmp_path / "elo.tmp").exists()
        assert path.exists()

    def test_roundtrip_with_history(self, tmp_path):
        """Full save/load roundtrip including game history."""
        path = tmp_path / "elo.json"
        profile = EloProfile()
        record_game(profile, "random", 1.0)
        record_game(profile, "botbot", 0.5)
        record_game(profile, "minimax_1", 0.0)
        save_elo_profile(profile, path)

        loaded = load_elo_profile(path)
        assert loaded.games_played == 3
        assert loaded.wins == 1
        assert loaded.draws == 1
        assert loaded.losses == 1
        assert len(loaded.history) == 3
        # Check first history entry
        assert loaded.history[0]["opponent"] == "random"
        assert loaded.history[0]["result"] == 1.0


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


class TestRecentForm:
    def test_no_games(self):
        p = EloProfile()
        assert get_recent_form(p) == "No games yet"

    def test_single_win(self):
        p = EloProfile()
        record_game(p, "random", 1.0)
        assert get_recent_form(p) == "W"

    def test_mixed_results(self):
        p = EloProfile()
        record_game(p, "random", 1.0)
        record_game(p, "random", 0.0)
        record_game(p, "random", 0.5)
        record_game(p, "random", 1.0)
        record_game(p, "random", 0.0)
        form = get_recent_form(p)
        assert form == "W L D W L"

    def test_default_n(self):
        """Default n=5 should show at most 5 results."""
        p = EloProfile()
        for _ in range(10):
            record_game(p, "random", 1.0)
        form = get_recent_form(p)
        assert form == "W W W W W"

    def test_custom_n(self):
        p = EloProfile()
        for _ in range(10):
            record_game(p, "random", 1.0)
        form = get_recent_form(p, n=3)
        assert form == "W W W"


class TestWinRate:
    def test_no_games(self):
        p = EloProfile()
        assert get_win_rate(p) is None

    def test_all_wins(self):
        p = EloProfile()
        for _ in range(5):
            record_game(p, "random", 1.0)
        assert get_win_rate(p) == pytest.approx(100.0)

    def test_all_losses(self):
        p = EloProfile()
        for _ in range(5):
            record_game(p, "random", 0.0)
        assert get_win_rate(p) == pytest.approx(0.0)

    def test_mixed(self):
        p = EloProfile()
        record_game(p, "random", 1.0)
        record_game(p, "random", 0.0)
        record_game(p, "random", 1.0)
        record_game(p, "random", 0.0)
        assert get_win_rate(p) == pytest.approx(50.0)
