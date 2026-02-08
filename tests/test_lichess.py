"""Tests for the Lichess daily puzzle integration (lichess.py)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import chess
import httpx
import pytest

from lichess import (
    DAILY_PUZZLE_URL,
    THEME_LABELS,
    LichessDailyPuzzle,
    _format_solution_san,
    _pgn_to_board,
    fetch_daily_puzzle,
    format_themes,
    get_solution_san,
)

# ---------------------------------------------------------------------------
# Sample API response fixture (based on a real Lichess daily puzzle)
# ---------------------------------------------------------------------------

SAMPLE_API_RESPONSE = {
    "game": {
        "id": "kQsFfCy4",
        "perf": {"key": "blitz", "name": "Blitz"},
        "rated": True,
        "players": [
            {
                "name": "mustanco",
                "id": "mustanco",
                "color": "white",
                "rating": 1807,
            },
            {
                "name": "Ilnasogonfiabile",
                "id": "ilnasogonfiabile",
                "color": "black",
                "rating": 1834,
            },
        ],
        "pgn": "d4 e5 c3 exd4 cxd4 d5 Bf4 Nc6 Nc3 Be6 Nf3 Bb4 e3 Nge7 a3 Ba5 "
        "b4 Bb6 Bb5 O-O Bxc6 Nxc6 O-O Bg4 a4 a6 b5 Na5 h3 Bh5 g4 Bg6 "
        "Ne5 Qh4 Nxg6 fxg6 Kh2 Nc4 Nxd5 Rad8 Nxb6 Nxb6 Bxc7 Rd7 Bxb6 "
        "Rdf7 Qb3 Kh8 Ra2 Rf3 Rh1 Qxh3+ Kg1",
        "clock": "5+0",
    },
    "puzzle": {
        "id": "VAfZj",
        "rating": 1999,
        "plays": 101763,
        "solution": ["f3g3", "f2g3", "f8f1"],
        "themes": [
            "clearance",
            "mateIn2",
            "middlegame",
            "short",
            "sacrifice",
            "kingsideAttack",
            "killBoxMate",
        ],
        "initialPly": 52,
    },
}

# Minimal PGN for quick tests
SIMPLE_PGN = "e4 e5 Nf3"  # 3 half-moves
SIMPLE_FEN_AFTER = None  # will be computed in test


# ---------------------------------------------------------------------------
# _pgn_to_board tests
# ---------------------------------------------------------------------------


class TestPgnToBoard:
    """Tests for the _pgn_to_board helper."""

    def test_simple_pgn(self):
        board = _pgn_to_board("e4 e5 Nf3")
        # After 1. e4 e5 2. Nf3, it's Black's turn
        assert board.turn == chess.BLACK
        assert len(board.move_stack) == 3

    def test_empty_pgn(self):
        board = _pgn_to_board("")
        assert board.turn == chess.WHITE
        assert len(board.move_stack) == 0

    def test_single_move(self):
        board = _pgn_to_board("e4")
        assert board.turn == chess.BLACK
        assert len(board.move_stack) == 1

    def test_full_sample_pgn(self):
        """Replay the full sample game PGN."""
        board = _pgn_to_board(SAMPLE_API_RESPONSE["game"]["pgn"])
        # After Kg1, it should be Black's turn (53 half-moves, odd = Black to move)
        assert board.turn == chess.BLACK
        assert len(board.move_stack) == 53

    def test_invalid_pgn_raises(self):
        with pytest.raises(ValueError):
            _pgn_to_board("e4 e5 INVALID_MOVE")

    def test_illegal_move_raises(self):
        """A syntactically valid but illegal move should raise."""
        with pytest.raises((ValueError, chess.IllegalMoveError)):
            _pgn_to_board("e4 e4")  # e4 by Black is illegal after 1.e4


# ---------------------------------------------------------------------------
# _format_solution_san tests
# ---------------------------------------------------------------------------


class TestFormatSolutionSan:
    """Tests for _format_solution_san."""

    def test_converts_uci_to_san(self):
        # From starting position after 1. e4 e5 2. Nf3
        board = _pgn_to_board("e4 e5 Nf3")
        fen = board.fen()
        # Black can play Nc6 (b8c6)
        result = _format_solution_san(fen, ["b8c6"])
        assert result == ["Nc6"]

    def test_multiple_moves(self):
        fen = chess.STARTING_FEN
        result = _format_solution_san(fen, ["e2e4", "e7e5", "g1f3"])
        assert result == ["e4", "e5", "Nf3"]

    def test_empty_solution(self):
        result = _format_solution_san(chess.STARTING_FEN, [])
        assert result == []

    def test_invalid_uci_fallback(self):
        """Invalid UCI moves should be kept as fallback strings."""
        result = _format_solution_san(chess.STARTING_FEN, ["ZZZZ"])
        assert result == ["ZZZZ"]

    def test_illegal_move_on_wrong_position_fallback(self):
        """A legal-looking UCI move applied to the wrong position falls back to UCI."""
        # h3g3 is not legal on the starting position (no piece on h3)
        result = _format_solution_san(chess.STARTING_FEN, ["h3g3"])
        assert result == ["h3g3"]

    def test_invalid_fen_returns_uci_list(self):
        """An invalid FEN should return the UCI list as-is."""
        result = _format_solution_san("not a valid fen", ["e2e4", "e7e5"])
        assert result == ["e2e4", "e7e5"]

    def test_sample_puzzle_solution(self):
        """Convert the sample puzzle solution to SAN."""
        board = _pgn_to_board(SAMPLE_API_RESPONSE["game"]["pgn"])
        fen = board.fen()
        solution_uci = SAMPLE_API_RESPONSE["puzzle"]["solution"]
        result = _format_solution_san(fen, solution_uci)
        # The solution should be valid SAN moves (not UCI fallbacks)
        assert len(result) == 3
        # First move: Rook from f3 to g3
        assert result[0] == "Rg3+"  # or Rg3+ depending on check
        # The remaining moves should also be valid SAN
        for san in result:
            assert san != ""


# ---------------------------------------------------------------------------
# format_themes tests
# ---------------------------------------------------------------------------


class TestFormatThemes:
    """Tests for the format_themes helper."""

    def test_known_themes(self):
        themes = ["mateIn2", "sacrifice", "short"]
        result = format_themes(themes)
        assert "Mate in 2" in result
        assert "Sacrifice" in result
        assert "Short Puzzle" in result

    def test_unknown_theme_fallback(self):
        result = format_themes(["someNewTheme"])
        # Unknown themes get title-cased with underscores replaced
        assert "Somenewtheme" in result or "someNewTheme" in result

    def test_empty_themes(self):
        assert format_themes([]) == ""

    def test_single_theme(self):
        result = format_themes(["fork"])
        assert result == "Fork"

    def test_theme_labels_populated(self):
        """Ensure the THEME_LABELS dict has a reasonable number of entries."""
        assert len(THEME_LABELS) >= 30


# ---------------------------------------------------------------------------
# LichessDailyPuzzle dataclass tests
# ---------------------------------------------------------------------------


class TestLichessDailyPuzzle:
    """Tests for the LichessDailyPuzzle dataclass."""

    def test_create_with_defaults(self):
        p = LichessDailyPuzzle(puzzle_id="abc", fen=chess.STARTING_FEN, rating=1500)
        assert p.puzzle_id == "abc"
        assert p.rating == 1500
        assert p.themes == []
        assert p.solution_uci == []
        assert p.game_id == ""
        assert p.plays == 0
        assert p.game_url == ""

    def test_create_fully_populated(self):
        p = LichessDailyPuzzle(
            puzzle_id="VAfZj",
            fen="some/fen",
            rating=1999,
            themes=["mateIn2"],
            solution_uci=["f3g3", "f2g3", "f8f1"],
            game_id="kQsFfCy4",
            plays=101763,
            game_url="https://lichess.org/kQsFfCy4",
        )
        assert p.plays == 101763
        assert len(p.solution_uci) == 3


# ---------------------------------------------------------------------------
# get_solution_san tests
# ---------------------------------------------------------------------------


class TestGetSolutionSan:
    """Tests for get_solution_san."""

    def test_returns_san_list(self):
        board = _pgn_to_board(SAMPLE_API_RESPONSE["game"]["pgn"])
        puzzle = LichessDailyPuzzle(
            puzzle_id="VAfZj",
            fen=board.fen(),
            rating=1999,
            solution_uci=["f3g3", "f2g3", "f8f1"],
        )
        result = get_solution_san(puzzle)
        assert isinstance(result, list)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# fetch_daily_puzzle tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestFetchDailyPuzzle:
    """Tests for fetch_daily_puzzle with mocked HTTP requests."""

    def _mock_response(self, json_data, status_code=200):
        """Create a mock httpx.Response."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data
        mock_resp.raise_for_status.return_value = None
        if status_code >= 400:
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=mock_resp
            )
        return mock_resp

    @patch("lichess.httpx.get")
    def test_successful_fetch(self, mock_get):
        mock_get.return_value = self._mock_response(SAMPLE_API_RESPONSE)

        puzzle = fetch_daily_puzzle()

        assert puzzle is not None
        assert puzzle.puzzle_id == "VAfZj"
        assert puzzle.rating == 1999
        assert puzzle.game_id == "kQsFfCy4"
        assert puzzle.game_url == "https://lichess.org/kQsFfCy4"
        assert puzzle.plays == 101763
        assert len(puzzle.solution_uci) == 3
        assert "clearance" in puzzle.themes
        assert "mateIn2" in puzzle.themes

        # The FEN should be a valid chess position
        board = chess.Board(puzzle.fen)
        assert board.is_valid()
        # Black to move (puzzle position after Kg1)
        assert board.turn == chess.BLACK

    @patch("lichess.httpx.get")
    def test_http_error_returns_none(self, mock_get):
        mock_get.return_value = self._mock_response({}, status_code=500)
        assert fetch_daily_puzzle() is None

    @patch("lichess.httpx.get")
    def test_timeout_returns_none(self, mock_get):
        mock_get.side_effect = httpx.TimeoutException("timeout")
        assert fetch_daily_puzzle() is None

    @patch("lichess.httpx.get")
    def test_connection_error_returns_none(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no connection")
        assert fetch_daily_puzzle() is None

    @patch("lichess.httpx.get")
    def test_malformed_json_returns_none(self, mock_get):
        # Missing required keys
        mock_get.return_value = self._mock_response({"unexpected": "data"})
        assert fetch_daily_puzzle() is None

    @patch("lichess.httpx.get")
    def test_invalid_pgn_returns_none(self, mock_get):
        """If the PGN contains illegal moves, return None."""
        bad_response = {
            "game": {
                "id": "test123",
                "pgn": "e4 e5 INVALID",
                "clock": "5+0",
            },
            "puzzle": {
                "id": "test",
                "rating": 1500,
                "solution": ["e2e4"],
                "themes": [],
                "initialPly": 2,
            },
        }
        mock_get.return_value = self._mock_response(bad_response)
        assert fetch_daily_puzzle() is None

    @patch("lichess.httpx.get")
    def test_missing_puzzle_key_returns_none(self, mock_get):
        """Missing 'puzzle' top-level key."""
        bad_response = {
            "game": {
                "id": "test123",
                "pgn": "e4 e5",
                "clock": "5+0",
            },
        }
        mock_get.return_value = self._mock_response(bad_response)
        assert fetch_daily_puzzle() is None

    @patch("lichess.httpx.get")
    def test_empty_pgn_valid(self, mock_get):
        """An empty PGN results in starting position."""
        response_data = {
            "game": {
                "id": "test123",
                "pgn": "",
                "clock": "5+0",
            },
            "puzzle": {
                "id": "test",
                "rating": 1200,
                "solution": ["e2e4"],
                "themes": ["opening"],
                "plays": 500,
                "initialPly": 0,
            },
        }
        mock_get.return_value = self._mock_response(response_data)
        puzzle = fetch_daily_puzzle()
        assert puzzle is not None
        assert puzzle.fen == chess.STARTING_FEN
        assert puzzle.rating == 1200

    @patch("lichess.httpx.get")
    def test_custom_timeout(self, mock_get):
        """Verify custom timeout is passed through."""
        mock_get.return_value = self._mock_response(SAMPLE_API_RESPONSE)
        fetch_daily_puzzle(timeout=5.0)
        mock_get.assert_called_once_with(
            DAILY_PUZZLE_URL,
            headers={"Accept": "application/json"},
            timeout=5.0,
        )

    @patch("lichess.httpx.get")
    def test_missing_optional_fields(self, mock_get):
        """Optional fields like themes and plays should default gracefully."""
        response_data = {
            "game": {
                "id": "g123",
                "pgn": "e4 e5",
                "clock": "5+0",
            },
            "puzzle": {
                "id": "p123",
                "rating": 1400,
                "solution": ["g1f3"],
                "initialPly": 2,
            },
        }
        mock_get.return_value = self._mock_response(response_data)
        puzzle = fetch_daily_puzzle()
        assert puzzle is not None
        assert puzzle.themes == []
        assert puzzle.plays == 0
        assert puzzle.solution_uci == ["g1f3"]


# ---------------------------------------------------------------------------
# Integration-style test (still mocked, but tests full flow)
# ---------------------------------------------------------------------------


class TestFetchAndSolve:
    """End-to-end flow: fetch puzzle → extract FEN → validate solution."""

    @patch("lichess.httpx.get")
    def test_full_flow(self, mock_get):
        """Fetch, parse, and verify the solution is playable."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.json.return_value = SAMPLE_API_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        puzzle = fetch_daily_puzzle()
        assert puzzle is not None

        # The FEN should be valid
        board = chess.Board(puzzle.fen)
        assert board.is_valid()

        # Play the solution moves — they should all be legal
        for uci in puzzle.solution_uci:
            move = chess.Move.from_uci(uci)
            assert move in board.legal_moves, f"{uci} not legal at {board.fen()}"
            board.push(move)

        # After the full solution, the game should be over (mate in this case)
        assert board.is_game_over()
