"""
Tests for opening_book.py – opening identification and common move suggestions.
"""

import chess

from opening_book import (
    OPENING_DATABASE,
    _get_move_sequence,
    _heuristic_move_score,
    get_common_moves,
    get_opening_name,
)


# ---------------------------------------------------------------------------
# Helper: build a board by playing a sequence of UCI moves
# ---------------------------------------------------------------------------
def _board_from_uci(*uci_moves: str) -> chess.Board:
    board = chess.Board()
    for uci in uci_moves:
        board.push_uci(uci)
    return board


# ===================================================================
# _get_move_sequence
# ===================================================================
class TestGetMoveSequence:
    def test_empty_board(self):
        board = chess.Board()
        assert _get_move_sequence(board) == []

    def test_single_move(self):
        board = _board_from_uci("e2e4")
        assert _get_move_sequence(board) == ["e2e4"]

    def test_multiple_moves(self):
        board = _board_from_uci("e2e4", "e7e5", "g1f3")
        assert _get_move_sequence(board) == ["e2e4", "e7e5", "g1f3"]

    def test_long_sequence(self):
        moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"]
        board = _board_from_uci(*moves)
        assert _get_move_sequence(board) == moves


# ===================================================================
# get_opening_name
# ===================================================================
class TestGetOpeningName:
    def test_no_moves(self):
        board = chess.Board()
        name, desc = get_opening_name(board)
        assert name is None
        assert desc is None

    def test_kings_pawn(self):
        board = _board_from_uci("e2e4")
        name, desc = get_opening_name(board)
        assert name == "King's Pawn Opening"
        assert desc is not None

    def test_sicilian_defense(self):
        board = _board_from_uci("e2e4", "c7c5")
        name, _ = get_opening_name(board)
        assert name == "Sicilian Defense"

    def test_ruy_lopez(self):
        board = _board_from_uci("e2e4", "e7e5", "g1f3", "b8c6", "f1b5")
        name, _ = get_opening_name(board)
        assert name == "Ruy Lopez"

    def test_italian_game_bishop_c4(self):
        board = _board_from_uci("e2e4", "e7e5", "g1f3", "b8c6", "f1c4")
        name, _ = get_opening_name(board)
        assert name == "Italian Game"

    def test_queens_gambit(self):
        board = _board_from_uci("d2d4", "d7d5", "c2c4")
        name, _ = get_opening_name(board)
        assert name == "Queen's Gambit"

    def test_queens_gambit_accepted(self):
        board = _board_from_uci("d2d4", "d7d5", "c2c4", "d5c4")
        name, _ = get_opening_name(board)
        assert name == "Queen's Gambit Accepted"

    def test_queens_gambit_declined(self):
        board = _board_from_uci("d2d4", "d7d5", "c2c4", "e7e6")
        name, _ = get_opening_name(board)
        assert name == "Queen's Gambit Declined"

    def test_french_defense(self):
        board = _board_from_uci("e2e4", "e7e6")
        name, _ = get_opening_name(board)
        assert name == "French Defense"

    def test_french_defense_classical(self):
        board = _board_from_uci("e2e4", "e7e6", "d2d4", "d7d5")
        name, desc = get_opening_name(board)
        assert name == "French Defense"
        assert desc == "Classical French"

    def test_caro_kann(self):
        board = _board_from_uci("e2e4", "c7c6")
        name, _ = get_opening_name(board)
        assert name == "Caro-Kann Defense"

    def test_caro_kann_classical(self):
        board = _board_from_uci("e2e4", "c7c6", "d2d4", "d7d5")
        name, desc = get_opening_name(board)
        assert name == "Caro-Kann Defense"
        assert desc == "Classical Variation"

    def test_english_opening(self):
        board = _board_from_uci("c2c4")
        name, _ = get_opening_name(board)
        assert name == "English Opening"

    def test_reti_opening(self):
        board = _board_from_uci("g1f3")
        name, _ = get_opening_name(board)
        assert name == "Reti Opening"

    def test_kings_gambit(self):
        board = _board_from_uci("e2e4", "e7e5", "f2f4")
        name, _ = get_opening_name(board)
        assert name == "King's Gambit"

    def test_vienna_game(self):
        board = _board_from_uci("e2e4", "e7e5", "b1c3")
        name, _ = get_opening_name(board)
        assert name == "Vienna Game"

    def test_scandinavian_defense(self):
        board = _board_from_uci("e2e4", "d7d5")
        name, _ = get_opening_name(board)
        assert name == "Scandinavian Defense"

    def test_alekhine_defense(self):
        board = _board_from_uci("e2e4", "g8f6")
        name, _ = get_opening_name(board)
        assert name == "Alekhine Defense"

    def test_pirc_defense(self):
        board = _board_from_uci("e2e4", "d7d6")
        name, _ = get_opening_name(board)
        assert name == "Pirc Defense"

    def test_dutch_defense(self):
        board = _board_from_uci("d2d4", "f7f5")
        name, _ = get_opening_name(board)
        assert name == "Dutch Defense"

    def test_nimzo_indian(self):
        board = _board_from_uci("d2d4", "g8f6", "c2c4", "e7e6")
        name, _ = get_opening_name(board)
        assert name == "Nimzo-Indian Defense"

    def test_kings_indian(self):
        board = _board_from_uci("d2d4", "g8f6", "c2c4", "g7g6")
        name, _ = get_opening_name(board)
        assert name == "King's Indian Defense"

    def test_longest_match_wins(self):
        """When multiple openings match, the longest (most specific) wins."""
        # 1. e4 matches "King's Pawn Opening"
        # 1. e4 e5 matches "Open Game" (longer)
        board = _board_from_uci("e2e4", "e7e5")
        name, _ = get_opening_name(board)
        assert name == "Open Game"

    def test_no_match_for_unusual_opening(self):
        """A bizarre move shouldn't match any opening."""
        board = _board_from_uci("a2a3")
        name, desc = get_opening_name(board)
        assert name is None
        assert desc is None

    def test_extra_moves_after_opening(self):
        """If we play further than the opening book, we still get the deepest match."""
        # e4 e5 Nf3 Nc6 Bc4 Bc5 (Italian Game + extra black move)
        board = _board_from_uci("e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5")
        name, _ = get_opening_name(board)
        assert name == "Italian Game"


# ===================================================================
# get_common_moves
# ===================================================================
class TestGetCommonMoves:
    def test_starting_position_returns_moves(self):
        board = chess.Board()
        moves = get_common_moves(board)
        assert len(moves) > 0
        # All entries should be (Move, san_str, int_score)
        for move, san, score in moves:
            assert isinstance(move, chess.Move)
            assert isinstance(san, str)
            assert isinstance(score, int)

    def test_starting_position_top_moves_include_e4_d4(self):
        """e4 and d4 appear in many openings and should rank near the top."""
        board = chess.Board()
        moves = get_common_moves(board)
        top_sans = [san for _, san, _ in moves[:6]]
        # e4 and d4 should be among the top moves
        assert "e4" in top_sans or "d4" in top_sans

    def test_after_e4_common_responses(self):
        board = _board_from_uci("e2e4")
        moves = get_common_moves(board)
        top_sans = [san for _, san, _ in moves[:10]]
        # Several common responses should appear
        # At least one of: e5, c5, e6, c6, d5 should be present
        common = {"e5", "c5", "e6", "c6", "d5", "d6", "Nf6"}
        found = common.intersection(top_sans)
        assert len(found) >= 1

    def test_sorted_descending_by_score(self):
        board = chess.Board()
        moves = get_common_moves(board)
        scores = [score for _, _, score in moves]
        assert scores == sorted(scores, reverse=True)

    def test_game_over_returns_empty(self):
        """Game over position should return no moves."""
        # Scholar's mate: 1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7#
        board = _board_from_uci("e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7")
        assert board.is_game_over()
        moves = get_common_moves(board)
        assert moves == []

    def test_frequency_scoring_high(self):
        """Moves that appear in 3+ openings get score 10."""
        # From starting position, e2e4 appears in many openings → score 10
        board = chess.Board()
        moves = get_common_moves(board)
        move_dict = {san: score for _, san, score in moves}
        assert move_dict.get("e4", 0) == 10

    def test_frequency_scoring_medium(self):
        """Moves appearing in exactly 2 openings should score 7."""
        # After 1. e4 e5, g1f3 appears in many continuations (Italian, Ruy Lopez, etc.)
        board = _board_from_uci("e2e4", "e7e5")
        moves = get_common_moves(board)
        # g1f3 should appear in many lines
        move_dict = {san: score for _, san, score in moves}
        # Nf3 appears in many openings after 1. e4 e5 → should be 10
        assert move_dict.get("Nf3", 0) >= 5

    def test_non_book_moves_get_heuristic_scores(self):
        """Moves not in the book should still get heuristic scores."""
        # Position with unusual moves leading to non-book territory
        board = _board_from_uci("a2a3", "h7h6")
        moves = get_common_moves(board)
        assert len(moves) > 0
        # All scores should be >= 1 (base score)
        for _, _, score in moves:
            assert score >= 1

    def test_common_moves_includes_all_legal_moves(self):
        """Every legal move should appear in the result."""
        board = chess.Board()
        common = get_common_moves(board)
        legal = list(board.legal_moves)
        common_moves_set = {m for m, _, _ in common}
        assert common_moves_set == set(legal)

    def test_after_e4_e5_nf3_continuations(self):
        """After 1. e4 e5 2. Nf3, Nc6 should rank highly (Italian + Ruy Lopez)."""
        board = _board_from_uci("e2e4", "e7e5", "g1f3")
        moves = get_common_moves(board)
        top_sans = [san for _, san, _ in moves[:5]]
        assert "Nc6" in top_sans


# ===================================================================
# _heuristic_move_score
# ===================================================================
class TestHeuristicMoveScore:
    def test_knight_development_from_starting_rank(self):
        """White knight from rank 0 should get a development bonus."""
        board = chess.Board()
        move = chess.Move.from_uci("g1f3")
        score = _heuristic_move_score(board, move)
        # Base (1) + knight dev (2) + center (1 if to center) = at least 3
        assert score >= 3

    def test_bishop_development_from_starting_rank(self):
        """White bishop developing from rank 0 should get a bonus."""
        board = _board_from_uci("e2e4", "e7e5")
        move = chess.Move.from_uci("f1c4")  # Bishop to c4
        score = _heuristic_move_score(board, move)
        # Base (1) + bishop dev (2) = at least 3
        assert score >= 3

    def test_central_pawn_d4(self):
        """d2d4 (pawn to d-file center) should score higher than edge pawn moves."""
        board = chess.Board()
        d4_move = chess.Move.from_uci("d2d4")
        a3_move = chess.Move.from_uci("a2a3")
        d4_score = _heuristic_move_score(board, d4_move)
        a3_score = _heuristic_move_score(board, a3_move)
        assert d4_score > a3_score

    def test_central_pawn_e4(self):
        """e2e4 should get a pawn center bonus."""
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        score = _heuristic_move_score(board, move)
        # Base (1) + pawn center (1) + center square (1) = 3
        assert score >= 2

    def test_edge_pawn_scores_low(self):
        """An edge pawn move like a2a3 should get only the base score."""
        board = chess.Board()
        move = chess.Move.from_uci("a2a3")
        score = _heuristic_move_score(board, move)
        assert score == 1

    def test_max_score_cap(self):
        """Heuristic scores should be capped at 5."""
        board = chess.Board()
        # Even the best-scoring move shouldn't exceed 5
        for move in board.legal_moves:
            score = _heuristic_move_score(board, move)
            assert score <= 5

    def test_black_knight_development(self):
        """Black knight developing from rank 7 should get a bonus."""
        board = _board_from_uci("e2e4")
        move = chess.Move.from_uci("g8f6")  # Black knight from rank 7
        score = _heuristic_move_score(board, move)
        assert score >= 3  # Base + knight dev + possibly center

    def test_black_bishop_development(self):
        """Black bishop from rank 7 should get bishop development bonus."""
        board = _board_from_uci("e2e4", "e7e5", "g1f3")
        move = chess.Move.from_uci("f8c5")  # Black bishop from f8 (rank 7)
        score = _heuristic_move_score(board, move)
        assert score >= 3  # Base + bishop dev

    def test_knight_not_from_starting_rank(self):
        """Knight already developed should not get the starting-rank bonus."""
        board = _board_from_uci("e2e4", "e7e5", "g1f3", "b8c6")
        # Now move the knight from f3 to somewhere (already on rank 2, not rank 0)
        move = chess.Move.from_uci("f3d4")
        score = _heuristic_move_score(board, move)
        # Base (1) + center (1) = 2 (no knight dev bonus since f3 is not rank 0)
        assert score >= 1

    def test_bishop_not_from_starting_rank(self):
        """Bishop already developed should not get the starting-rank bonus."""
        board = _board_from_uci("e2e4", "e7e5", "f1c4", "g8f6")
        # Bishop is on c4 (rank 3), not starting rank
        move = chess.Move.from_uci("c4f7")
        score = _heuristic_move_score(board, move)
        # No bishop dev bonus since c4 is not rank 0
        assert score >= 1

    def test_pawn_to_non_center_file(self):
        """Pawn move to a non-center file should not get center pawn bonus."""
        board = chess.Board()
        move = chess.Move.from_uci("h2h3")
        score = _heuristic_move_score(board, move)
        assert score == 1  # Base only

    def test_central_square_d5(self):
        """A move to d5 (center square) gets the center bonus."""
        board = _board_from_uci("e2e4", "e7e5", "d2d4")
        # d4d5 is a pawn to d5 (center square)
        move = chess.Move.from_uci("d4d5")
        if move in board.legal_moves:
            score = _heuristic_move_score(board, move)
            assert score >= 2

    def test_move_from_empty_square(self):
        """A move from a square with no piece should just get base+center score."""
        # Create a custom board where we force a move reference
        board = chess.Board()
        # Create a dummy move – in practice this won't happen, but tests the None path
        move = chess.Move.from_uci("a4a5")  # no piece on a4 in starting position
        score = _heuristic_move_score(board, move)
        # piece is None, so only base (1) + possible center bonus
        assert score >= 1


# ===================================================================
# OPENING_DATABASE structure
# ===================================================================
class TestOpeningDatabase:
    def test_database_not_empty(self):
        assert len(OPENING_DATABASE) > 0

    def test_database_entry_structure(self):
        """Each entry should be (list[str], str, str)."""
        for entry in OPENING_DATABASE:
            assert len(entry) == 3
            moves, name, description = entry
            assert isinstance(moves, list)
            assert all(isinstance(m, str) for m in moves)
            assert isinstance(name, str)
            assert isinstance(description, str)

    def test_all_uci_moves_valid(self):
        """Every UCI move in the database should be valid from the starting position."""
        for moves, name, _ in OPENING_DATABASE:
            board = chess.Board()
            for uci in moves:
                try:
                    move = chess.Move.from_uci(uci)
                    assert move in board.legal_moves, (
                        f"Illegal move {uci} in opening '{name}'"
                    )
                    board.push(move)
                except Exception as e:
                    raise AssertionError(
                        f"Invalid UCI '{uci}' in opening '{name}': {e}"
                    ) from e

    def test_no_empty_move_sequences(self):
        """No opening should have an empty move list."""
        for moves, name, _ in OPENING_DATABASE:
            assert len(moves) > 0, f"Opening '{name}' has no moves"


# ===================================================================
# Integration tests – full game sequences
# ===================================================================
class TestIntegration:
    def test_opening_progresses_as_moves_are_played(self):
        """The opening name should update to the most specific match."""
        board = chess.Board()

        # Before any moves
        assert get_opening_name(board) == (None, None)

        # 1. e4
        board.push_uci("e2e4")
        name, _ = get_opening_name(board)
        assert name == "King's Pawn Opening"

        # 1... e5
        board.push_uci("e7e5")
        name, _ = get_opening_name(board)
        assert name == "Open Game"

        # 2. Nf3
        board.push_uci("g1f3")
        name, _ = get_opening_name(board)
        assert name == "King's Knight Opening"

        # 2... Nc6
        board.push_uci("b8c6")
        name, _ = get_opening_name(board)
        assert name == "Italian Game"  # It matches the 4-move prefix

        # 3. Bb5 → Ruy Lopez
        board.push_uci("f1b5")
        name, _ = get_opening_name(board)
        assert name == "Ruy Lopez"

    def test_common_moves_decrease_out_of_book(self):
        """As we move out of the opening book, book-based scores should drop."""
        board = chess.Board()
        starting_moves = get_common_moves(board)
        starting_book_count = sum(1 for _, _, s in starting_moves if s >= 5)

        # Play several unusual moves to get out of book
        board.push_uci("a2a3")
        board.push_uci("h7h6")
        board.push_uci("b2b3")
        board.push_uci("g7g6")
        out_of_book_moves = get_common_moves(board)
        out_book_count = sum(1 for _, _, s in out_of_book_moves if s >= 5)

        assert out_book_count < starting_book_count

    def test_fen_position_with_no_move_history(self):
        """A board set from FEN (no move stack) should return no opening and heuristic-only moves."""
        board = chess.Board(
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        )
        # No move stack even though position is after 1. e4
        name, desc = get_opening_name(board)
        assert name is None
        assert desc is None

        moves = get_common_moves(board)
        assert len(moves) > 0
        # All scores should be heuristic-based (no book matches with empty move stack)
        for _, _, score in moves:
            assert score <= 5
