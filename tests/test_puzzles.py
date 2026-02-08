"""Tests for the puzzle module: database integrity, dataclass behavior, and helpers."""

import chess
import pytest

from puzzles import (
    PUZZLE_BY_ID,
    PUZZLE_DATABASE,
    PUZZLES,
    Puzzle,
    PuzzleCategory,
    PuzzleDifficulty,
    PuzzleObjective,
    difficulty_label_for_rating,
    get_free_play_puzzles,
    get_puzzles_by_category,
    get_puzzles_by_difficulty,
    get_rated_puzzles,
)


# -------------------------------------------------------------------------
# Database integrity
# -------------------------------------------------------------------------


class TestDatabaseIntegrity:
    """Verify the puzzle database is well-formed."""

    def test_puzzles_not_empty(self):
        assert len(PUZZLE_DATABASE) > 0

    def test_unique_ids(self):
        ids = [p.id for p in PUZZLE_DATABASE]
        assert len(ids) == len(set(ids)), "Puzzle IDs must be unique"

    def test_unique_names(self):
        names = [p.name for p in PUZZLE_DATABASE]
        assert len(names) == len(set(names)), "Puzzle names must be unique"

    def test_all_fens_valid(self):
        for p in PUZZLE_DATABASE:
            try:
                board = chess.Board(p.fen)
                assert board is not None
            except ValueError:
                pytest.fail(f"Invalid FEN in puzzle '{p.id}': {p.fen}")

    def test_all_solutions_legal(self):
        """Every move in every solution must be legal in sequence.

        Solution entries may contain pipe-separated alternatives (e.g.
        ``"e7e8q|e7e8r"``).  All alternatives must be legal at that
        position; the first alternative is used to advance the board.
        """
        for p in PUZZLE_DATABASE:
            if not p.solution_uci:
                continue
            board = chess.Board(p.fen)
            for i, uci_entry in enumerate(p.solution_uci):
                alternatives = uci_entry.split("|")
                for alt in alternatives:
                    move = chess.Move.from_uci(alt)
                    assert move in board.legal_moves, (
                        f"Illegal move {alt} at step {i} in puzzle '{p.id}'"
                    )
                # Advance board with the first (canonical) alternative
                board.push(chess.Move.from_uci(alternatives[0]))

    def test_non_empty_fields(self):
        for p in PUZZLE_DATABASE:
            assert p.id.strip(), f"Empty ID on puzzle {p.name}"
            assert p.name.strip(), f"Empty name on puzzle {p.id}"
            assert p.fen.strip(), f"Empty FEN on puzzle {p.id}"
            assert p.description.strip(), f"Empty description on puzzle {p.id}"

    def test_difficulty_ratings_non_negative(self):
        for p in PUZZLE_DATABASE:
            assert p.difficulty_rating >= 0, (
                f"Negative rating {p.difficulty_rating} on puzzle {p.id}"
            )

    def test_rated_puzzles_have_solutions(self):
        """Puzzles with a difficulty rating > 0 must have solution moves."""
        for p in PUZZLE_DATABASE:
            if p.difficulty_rating > 0 and p.objective != PuzzleObjective.FREE_PLAY:
                assert len(p.solution_uci) > 0, f"Rated puzzle '{p.id}' has no solution"

    def test_free_play_puzzles_have_no_solution(self):
        """Free play puzzles should have empty solutions."""
        for p in PUZZLE_DATABASE:
            if p.objective == PuzzleObjective.FREE_PLAY:
                assert p.solution_uci == [], (
                    f"Free play puzzle '{p.id}' should have no solution"
                )

    def test_puzzle_by_id_matches_database(self):
        """The PUZZLE_BY_ID index must match the database."""
        assert len(PUZZLE_BY_ID) == len(PUZZLE_DATABASE)
        for p in PUZZLE_DATABASE:
            assert PUZZLE_BY_ID[p.id] is p

    def test_has_multiple_categories(self):
        """Database should contain puzzles from multiple categories."""
        categories = {p.category for p in PUZZLE_DATABASE}
        assert len(categories) >= 3

    def test_has_multiple_difficulty_levels(self):
        """Database should span beginner through expert."""
        labels = {
            p.difficulty_label for p in PUZZLE_DATABASE if p.difficulty_rating > 0
        }
        assert PuzzleDifficulty.BEGINNER in labels
        assert PuzzleDifficulty.EXPERT in labels


# -------------------------------------------------------------------------
# Backwards-compatible PUZZLES list
# -------------------------------------------------------------------------


class TestLegacyPuzzlesList:
    """The legacy PUZZLES list must remain usable by old code."""

    def test_length_matches_database(self):
        assert len(PUZZLES) == len(PUZZLE_DATABASE)

    def test_tuple_structure(self):
        for entry in PUZZLES:
            assert len(entry) == 4
            name, fen, desc, clock = entry
            assert isinstance(name, str)
            assert isinstance(fen, str)
            assert isinstance(desc, str)
            assert isinstance(clock, bool)

    def test_clock_settings(self):
        clock_disabled = sum(1 for *_, c in PUZZLES if not c)
        clock_enabled = sum(1 for *_, c in PUZZLES if c)
        assert clock_disabled > 0
        assert clock_enabled >= 1


# -------------------------------------------------------------------------
# Puzzle dataclass behaviour
# -------------------------------------------------------------------------


class TestPuzzleDataclass:
    """Test Puzzle properties and methods."""

    @pytest.fixture()
    def mate_in_1(self):
        return Puzzle(
            id="test_m1",
            name="Test Mate 1",
            fen="6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
            description="Test",
            category=PuzzleCategory.CHECKMATE,
            difficulty_rating=700,
            objective=PuzzleObjective.FIND_BEST_MOVES,
            solution_uci=["e1e8"],
        )

    @pytest.fixture()
    def mate_in_2(self):
        return Puzzle(
            id="test_m2",
            name="Test Mate 2",
            fen="6k1/8/8/8/8/8/8/RR4K1 w - - 0 1",
            description="Test",
            category=PuzzleCategory.CHECKMATE,
            difficulty_rating=1100,
            objective=PuzzleObjective.FIND_BEST_MOVES,
            solution_uci=["a1a7", "g8f8", "b1b8"],
        )

    @pytest.fixture()
    def free_play(self):
        return Puzzle(
            id="test_fp",
            name="Test Free",
            fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            description="Test",
            category=PuzzleCategory.FREE_PLAY,
            difficulty_rating=0,
            objective=PuzzleObjective.FREE_PLAY,
        )

    def test_difficulty_label_beginner(self, mate_in_1):
        assert mate_in_1.difficulty_label == PuzzleDifficulty.BEGINNER

    def test_difficulty_label_intermediate(self, mate_in_2):
        assert mate_in_2.difficulty_label == PuzzleDifficulty.INTERMEDIATE

    def test_player_moves(self, mate_in_2):
        assert mate_in_2.player_moves == ["a1a7", "b1b8"]

    def test_opponent_moves(self, mate_in_2):
        assert mate_in_2.opponent_moves == ["g8f8"]

    def test_num_player_moves(self, mate_in_1):
        assert mate_in_1.num_player_moves == 1

    def test_num_player_moves_multi(self, mate_in_2):
        assert mate_in_2.num_player_moves == 2

    def test_is_player_move_correct(self, mate_in_1):
        assert mate_in_1.is_player_move_correct(0, "e1e8")
        assert not mate_in_1.is_player_move_correct(0, "e1e7")

    def test_is_player_move_correct_alternatives(self):
        """Pipe-separated alternatives should all be accepted."""
        p = Puzzle(
            id="test_alt",
            name="Test Alternatives",
            fen="6k1/4Pppp/8/8/8/8/5PPP/6K1 w - - 0 1",
            description="Test",
            category=PuzzleCategory.CHECKMATE,
            difficulty_rating=900,
            objective=PuzzleObjective.FIND_BEST_MOVES,
            solution_uci=["e7e8q|e7e8r"],
        )
        assert p.is_player_move_correct(0, "e7e8q")
        assert p.is_player_move_correct(0, "e7e8r")
        assert not p.is_player_move_correct(0, "e7e8b")
        assert not p.is_player_move_correct(0, "e7e8n")

    def test_is_player_move_correct_multi(self, mate_in_2):
        assert mate_in_2.is_player_move_correct(0, "a1a7")
        assert not mate_in_2.is_player_move_correct(0, "b1b8")
        assert mate_in_2.is_player_move_correct(1, "b1b8")

    def test_is_player_move_correct_out_of_range(self, mate_in_1):
        assert not mate_in_1.is_player_move_correct(1, "e1e8")
        assert not mate_in_1.is_player_move_correct(-1, "e1e8")

    def test_is_player_move_correct_free_play(self, free_play):
        # Free play: any move is accepted
        assert free_play.is_player_move_correct(0, "e2e4")
        assert free_play.is_player_move_correct(0, "anything")

    def test_get_opponent_response(self, mate_in_2):
        assert mate_in_2.get_opponent_response(0) == "g8f8"
        assert mate_in_2.get_opponent_response(1) is None

    def test_get_opponent_response_out_of_range(self, mate_in_1):
        assert mate_in_1.get_opponent_response(0) is None
        assert mate_in_1.get_opponent_response(-1) is None

    def test_is_complete_after_player_move_single(self, mate_in_1):
        assert mate_in_1.is_complete_after_player_move(0)

    def test_is_complete_after_player_move_multi(self, mate_in_2):
        assert not mate_in_2.is_complete_after_player_move(0)
        assert mate_in_2.is_complete_after_player_move(1)

    def test_is_complete_free_play(self, free_play):
        assert not free_play.is_complete_after_player_move(0)
        assert not free_play.is_complete_after_player_move(100)

    def test_get_hint_for_move(self):
        p = Puzzle(
            id="hint_test",
            name="Hint Test",
            fen="8/8/8/8/8/8/8/4K3 w - - 0 1",
            description="Test",
            category=PuzzleCategory.TACTICS,
            difficulty_rating=500,
            objective=PuzzleObjective.FREE_PLAY,
            hints=["First hint", "Second hint"],
        )
        assert p.get_hint_for_move(0) == "First hint"
        assert p.get_hint_for_move(1) == "Second hint"
        assert p.get_hint_for_move(2) is None


# -------------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------------


class TestHelperFunctions:
    def test_difficulty_label_for_rating(self):
        assert difficulty_label_for_rating(500) == PuzzleDifficulty.BEGINNER
        assert difficulty_label_for_rating(999) == PuzzleDifficulty.BEGINNER
        assert difficulty_label_for_rating(1000) == PuzzleDifficulty.INTERMEDIATE
        assert difficulty_label_for_rating(1399) == PuzzleDifficulty.INTERMEDIATE
        assert difficulty_label_for_rating(1400) == PuzzleDifficulty.ADVANCED
        assert difficulty_label_for_rating(1799) == PuzzleDifficulty.ADVANCED
        assert difficulty_label_for_rating(1800) == PuzzleDifficulty.EXPERT
        assert difficulty_label_for_rating(2500) == PuzzleDifficulty.EXPERT

    def test_get_puzzles_by_category(self):
        checkmates = get_puzzles_by_category(PuzzleCategory.CHECKMATE)
        assert len(checkmates) > 0
        assert all(p.category == PuzzleCategory.CHECKMATE for p in checkmates)
        # Sorted by difficulty
        ratings = [p.difficulty_rating for p in checkmates]
        assert ratings == sorted(ratings)

    def test_get_puzzles_by_difficulty(self):
        beginners = get_puzzles_by_difficulty(600, 999)
        assert len(beginners) > 0
        assert all(600 <= p.difficulty_rating <= 999 for p in beginners)

    def test_get_puzzles_by_difficulty_empty_range(self):
        empty = get_puzzles_by_difficulty(9000, 9999)
        assert empty == []

    def test_get_rated_puzzles(self):
        rated = get_rated_puzzles()
        assert len(rated) > 0
        assert all(p.difficulty_rating > 0 for p in rated)
        # Sorted by rating
        ratings = [p.difficulty_rating for p in rated]
        assert ratings == sorted(ratings)

    def test_get_free_play_puzzles(self):
        fps = get_free_play_puzzles()
        assert len(fps) > 0
        assert all(p.objective == PuzzleObjective.FREE_PLAY for p in fps)

    def test_categories_cover_database(self):
        """Getting puzzles by every category should cover the entire database."""
        total = 0
        for cat in PuzzleCategory:
            total += len(get_puzzles_by_category(cat))
        assert total == len(PUZZLE_DATABASE)
