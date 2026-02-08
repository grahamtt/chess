"""Tests for the Lichess API integration (lichess.py).

Covers the daily puzzle and Lichess TV streaming functionality.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import chess
import httpx
import pytest

from lichess import (
    DAILY_PUZZLE_URL,
    TV_CHANNELS_URL,
    TV_FEED_URL,
    THEME_LABELS,
    LichessDailyPuzzle,
    LichessTvChannel,
    LichessTvFenEvent,
    LichessTvGame,
    LichessTvPlayer,
    _format_solution_san,
    _parse_featured_event,
    _parse_fen_event,
    _parse_tv_player,
    _pgn_to_board,
    _tv_feed_url,
    fetch_daily_puzzle,
    fetch_tv_channels,
    fetch_tv_current_game,
    format_themes,
    get_solution_san,
    stream_tv_feed,
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


# ===========================================================================
# Lichess TV API tests
# ===========================================================================

# ---------------------------------------------------------------------------
# Sample TV API fixtures
# ---------------------------------------------------------------------------

SAMPLE_FEATURED_EVENT = {
    "t": "featured",
    "d": {
        "id": "qVSOPtMc",
        "orientation": "black",
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR",
        "players": [
            {
                "color": "white",
                "user": {"id": "player1", "name": "Player1"},
                "rating": 2540,
                "seconds": 180,
            },
            {
                "color": "black",
                "user": {"id": "player2", "name": "Player2"},
                "rating": 2610,
                "seconds": 180,
            },
        ],
    },
}

SAMPLE_FEN_EVENT = {
    "t": "fen",
    "d": {
        "lm": "e2e4",
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR",
        "wc": 178,
        "bc": 180,
    },
}

SAMPLE_CHANNELS_RESPONSE = {
    "Bullet": {
        "user": {"id": "bullet_player", "name": "BulletKing"},
        "rating": 2800,
        "gameId": "abc123",
    },
    "Blitz": {
        "user": {"id": "blitz_player", "name": "BlitzMaster"},
        "rating": 2650,
        "gameId": "def456",
    },
    "Rapid": {
        "user": {"id": "rapid_player", "name": "RapidGM"},
        "rating": 2700,
        "gameId": "ghi789",
    },
}


# ---------------------------------------------------------------------------
# LichessTvPlayer tests
# ---------------------------------------------------------------------------


class TestLichessTvPlayer:
    """Tests for the LichessTvPlayer dataclass."""

    def test_create_with_defaults(self):
        p = LichessTvPlayer(color="white")
        assert p.color == "white"
        assert p.user_name == ""
        assert p.user_id == ""
        assert p.rating == 0
        assert p.seconds == 0

    def test_create_fully_populated(self):
        p = LichessTvPlayer(
            color="black",
            user_name="Magnus",
            user_id="drmagnus",
            rating=2850,
            seconds=300,
        )
        assert p.color == "black"
        assert p.user_name == "Magnus"
        assert p.rating == 2850
        assert p.seconds == 300


# ---------------------------------------------------------------------------
# LichessTvGame tests
# ---------------------------------------------------------------------------


class TestLichessTvGame:
    """Tests for the LichessTvGame dataclass."""

    def test_create_with_defaults(self):
        g = LichessTvGame(game_id="abc", orientation="white")
        assert g.game_id == "abc"
        assert g.orientation == "white"
        assert g.fen == chess.STARTING_FEN
        assert g.players == []
        assert g.white_player is None
        assert g.black_player is None
        assert g.game_url == "https://lichess.org/abc"

    def test_white_and_black_player_properties(self):
        wp = LichessTvPlayer(color="white", user_name="Alice", rating=2000)
        bp = LichessTvPlayer(color="black", user_name="Bob", rating=2100)
        g = LichessTvGame(
            game_id="xyz",
            orientation="white",
            players=[wp, bp],
        )
        assert g.white_player is wp
        assert g.black_player is bp
        assert g.white_player.user_name == "Alice"
        assert g.black_player.user_name == "Bob"

    def test_player_property_returns_none_when_missing(self):
        p = LichessTvPlayer(color="white", user_name="Solo")
        g = LichessTvGame(game_id="z", orientation="white", players=[p])
        assert g.white_player is p
        assert g.black_player is None

    def test_game_url(self):
        g = LichessTvGame(game_id="qVSOPtMc", orientation="black")
        assert g.game_url == "https://lichess.org/qVSOPtMc"


# ---------------------------------------------------------------------------
# LichessTvFenEvent tests
# ---------------------------------------------------------------------------


class TestLichessTvFenEvent:
    """Tests for the LichessTvFenEvent dataclass."""

    def test_create_with_defaults(self):
        e = LichessTvFenEvent(fen=chess.STARTING_FEN)
        assert e.fen == chess.STARTING_FEN
        assert e.last_move_uci == ""
        assert e.white_clock == 0
        assert e.black_clock == 0

    def test_create_fully_populated(self):
        e = LichessTvFenEvent(
            fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR",
            last_move_uci="e2e4",
            white_clock=178,
            black_clock=180,
        )
        assert e.last_move_uci == "e2e4"
        assert e.white_clock == 178
        assert e.black_clock == 180


# ---------------------------------------------------------------------------
# LichessTvChannel tests
# ---------------------------------------------------------------------------


class TestLichessTvChannel:
    """Tests for the LichessTvChannel dataclass."""

    def test_create_with_defaults(self):
        c = LichessTvChannel(channel_name="Bullet")
        assert c.channel_name == "Bullet"
        assert c.game_id == ""
        assert c.rating == 0
        assert c.user_name == ""
        assert c.user_id == ""

    def test_create_fully_populated(self):
        c = LichessTvChannel(
            channel_name="Blitz",
            game_id="abc123",
            rating=2800,
            user_name="ChessKing",
            user_id="chessking",
        )
        assert c.channel_name == "Blitz"
        assert c.game_id == "abc123"
        assert c.rating == 2800


# ---------------------------------------------------------------------------
# _parse_tv_player tests
# ---------------------------------------------------------------------------


class TestParseTvPlayer:
    """Tests for the _parse_tv_player helper."""

    def test_full_player(self):
        raw = {
            "color": "white",
            "user": {"id": "magnus", "name": "Magnus"},
            "rating": 2850,
            "seconds": 300,
        }
        p = _parse_tv_player(raw)
        assert p.color == "white"
        assert p.user_name == "Magnus"
        assert p.user_id == "magnus"
        assert p.rating == 2850
        assert p.seconds == 300

    def test_missing_user_fields(self):
        raw = {"color": "black", "rating": 2000}
        p = _parse_tv_player(raw)
        assert p.color == "black"
        assert p.user_name == ""
        assert p.user_id == ""
        assert p.rating == 2000
        assert p.seconds == 0

    def test_user_as_string(self):
        """Handles edge case where user might be a plain string."""
        raw = {"color": "white", "user": "stringuser", "rating": 1500}
        p = _parse_tv_player(raw)
        assert p.user_name == "stringuser"
        assert p.user_id == ""

    def test_empty_dict(self):
        p = _parse_tv_player({})
        assert p.color == ""
        assert p.user_name == ""
        assert p.rating == 0

    def test_user_is_none(self):
        raw = {"color": "white", "user": None, "rating": 1200}
        p = _parse_tv_player(raw)
        assert p.user_name == ""
        assert p.user_id == ""


# ---------------------------------------------------------------------------
# _parse_featured_event tests
# ---------------------------------------------------------------------------


class TestParseFeaturedEvent:
    """Tests for the _parse_featured_event helper."""

    def test_full_event(self):
        data = SAMPLE_FEATURED_EVENT["d"]
        game = _parse_featured_event(data)
        assert game.game_id == "qVSOPtMc"
        assert game.orientation == "black"
        assert game.fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        assert len(game.players) == 2
        assert game.white_player.user_name == "Player1"
        assert game.white_player.rating == 2540
        assert game.black_player.user_name == "Player2"
        assert game.black_player.rating == 2610

    def test_empty_event(self):
        game = _parse_featured_event({})
        assert game.game_id == ""
        assert game.orientation == "white"
        assert game.fen == chess.STARTING_FEN
        assert game.players == []

    def test_missing_players(self):
        data = {"id": "test123", "orientation": "white", "fen": "some_fen"}
        game = _parse_featured_event(data)
        assert game.game_id == "test123"
        assert game.players == []
        assert game.white_player is None


# ---------------------------------------------------------------------------
# _parse_fen_event tests
# ---------------------------------------------------------------------------


class TestParseFenEvent:
    """Tests for the _parse_fen_event helper."""

    def test_full_event(self):
        data = SAMPLE_FEN_EVENT["d"]
        event = _parse_fen_event(data)
        assert event.fen == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR"
        assert event.last_move_uci == "e2e4"
        assert event.white_clock == 178
        assert event.black_clock == 180

    def test_empty_event(self):
        event = _parse_fen_event({})
        assert event.fen == ""
        assert event.last_move_uci == ""
        assert event.white_clock == 0
        assert event.black_clock == 0

    def test_partial_event(self):
        data = {"fen": "some/fen", "lm": "d2d4"}
        event = _parse_fen_event(data)
        assert event.fen == "some/fen"
        assert event.last_move_uci == "d2d4"
        assert event.white_clock == 0
        assert event.black_clock == 0


# ---------------------------------------------------------------------------
# stream_tv_feed tests (mocked HTTP streaming)
# ---------------------------------------------------------------------------


class _MockStreamResponse:
    """A mock httpx streaming response that yields NDJSON lines."""

    def __init__(self, lines: list[str], status_code: int = 200):
        self._lines = lines
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error", request=MagicMock(), response=self
            )

    def iter_lines(self):
        yield from self._lines

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestStreamTvFeed:
    """Tests for stream_tv_feed with mocked HTTP streaming."""

    @patch("lichess.httpx.stream")
    def test_yields_featured_and_fen_events(self, mock_stream):
        lines = [
            json.dumps(SAMPLE_FEATURED_EVENT),
            json.dumps(SAMPLE_FEN_EVENT),
        ]
        mock_stream.return_value = _MockStreamResponse(lines)

        events = list(stream_tv_feed())
        assert len(events) == 2
        assert isinstance(events[0], LichessTvGame)
        assert events[0].game_id == "qVSOPtMc"
        assert isinstance(events[1], LichessTvFenEvent)
        assert events[1].last_move_uci == "e2e4"

    @patch("lichess.httpx.stream")
    def test_skips_empty_lines(self, mock_stream):
        lines = [
            "",
            json.dumps(SAMPLE_FEN_EVENT),
            "   ",
            json.dumps(SAMPLE_FEN_EVENT),
        ]
        mock_stream.return_value = _MockStreamResponse(lines)

        events = list(stream_tv_feed())
        assert len(events) == 2
        assert all(isinstance(e, LichessTvFenEvent) for e in events)

    @patch("lichess.httpx.stream")
    def test_skips_malformed_json(self, mock_stream):
        lines = [
            "not valid json",
            json.dumps(SAMPLE_FEN_EVENT),
            "{bad json",
        ]
        mock_stream.return_value = _MockStreamResponse(lines)

        events = list(stream_tv_feed())
        assert len(events) == 1
        assert isinstance(events[0], LichessTvFenEvent)

    @patch("lichess.httpx.stream")
    def test_skips_unknown_event_types(self, mock_stream):
        lines = [
            json.dumps({"t": "unknown", "d": {"foo": "bar"}}),
            json.dumps(SAMPLE_FEN_EVENT),
        ]
        mock_stream.return_value = _MockStreamResponse(lines)

        events = list(stream_tv_feed())
        assert len(events) == 1
        assert isinstance(events[0], LichessTvFenEvent)

    @patch("lichess.httpx.stream")
    def test_empty_stream(self, mock_stream):
        mock_stream.return_value = _MockStreamResponse([])
        events = list(stream_tv_feed())
        assert events == []

    @patch("lichess.httpx.stream")
    def test_http_error_returns_empty(self, mock_stream):
        mock_stream.side_effect = httpx.HTTPError("connection refused")
        events = list(stream_tv_feed())
        assert events == []

    @patch("lichess.httpx.stream")
    def test_timeout_returns_empty(self, mock_stream):
        mock_stream.side_effect = httpx.TimeoutException("timeout")
        events = list(stream_tv_feed())
        assert events == []

    @patch("lichess.httpx.stream")
    def test_stream_error_returns_empty(self, mock_stream):
        mock_stream.side_effect = httpx.StreamError("stream broken")
        events = list(stream_tv_feed())
        assert events == []

    @patch("lichess.httpx.stream")
    def test_http_status_error_returns_empty(self, mock_stream):
        mock_stream.return_value = _MockStreamResponse([], status_code=500)
        events = list(stream_tv_feed())
        assert events == []

    @patch("lichess.httpx.stream")
    def test_multiple_featured_events(self, mock_stream):
        """Multiple featured events (game changes) are all yielded."""
        event2_data = {
            "t": "featured",
            "d": {
                "id": "newgame42",
                "orientation": "white",
                "fen": chess.STARTING_FEN,
                "players": [],
            },
        }
        lines = [
            json.dumps(SAMPLE_FEATURED_EVENT),
            json.dumps(SAMPLE_FEN_EVENT),
            json.dumps(event2_data),
        ]
        mock_stream.return_value = _MockStreamResponse(lines)

        events = list(stream_tv_feed())
        assert len(events) == 3
        assert isinstance(events[0], LichessTvGame)
        assert events[0].game_id == "qVSOPtMc"
        assert isinstance(events[1], LichessTvFenEvent)
        assert isinstance(events[2], LichessTvGame)
        assert events[2].game_id == "newgame42"


# ---------------------------------------------------------------------------
# fetch_tv_channels tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestFetchTvChannels:
    """Tests for fetch_tv_channels with mocked HTTP requests."""

    def _mock_response(self, json_data, status_code=200):
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
        mock_get.return_value = self._mock_response(SAMPLE_CHANNELS_RESPONSE)
        channels = fetch_tv_channels()

        assert channels is not None
        assert len(channels) == 3

        names = {c.channel_name for c in channels}
        assert "Bullet" in names
        assert "Blitz" in names
        assert "Rapid" in names

        # Verify individual channel data
        bullet = next(c for c in channels if c.channel_name == "Bullet")
        assert bullet.game_id == "abc123"
        assert bullet.rating == 2800
        assert bullet.user_name == "BulletKing"
        assert bullet.user_id == "bullet_player"

    @patch("lichess.httpx.get")
    def test_empty_channels(self, mock_get):
        mock_get.return_value = self._mock_response({})
        channels = fetch_tv_channels()
        assert channels is not None
        assert channels == []

    @patch("lichess.httpx.get")
    def test_http_error_returns_none(self, mock_get):
        mock_get.return_value = self._mock_response({}, status_code=500)
        assert fetch_tv_channels() is None

    @patch("lichess.httpx.get")
    def test_timeout_returns_none(self, mock_get):
        mock_get.side_effect = httpx.TimeoutException("timeout")
        assert fetch_tv_channels() is None

    @patch("lichess.httpx.get")
    def test_connection_error_returns_none(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no connection")
        assert fetch_tv_channels() is None

    @patch("lichess.httpx.get")
    def test_custom_timeout(self, mock_get):
        mock_get.return_value = self._mock_response(SAMPLE_CHANNELS_RESPONSE)
        fetch_tv_channels(timeout=5.0)
        mock_get.assert_called_once_with(
            TV_CHANNELS_URL,
            headers={"Accept": "application/json"},
            timeout=5.0,
        )

    @patch("lichess.httpx.get")
    def test_channel_with_user_as_string(self, mock_get):
        """Edge case: user field is a string instead of dict."""
        data = {
            "UltraBullet": {
                "user": "stringuser",
                "rating": 2400,
                "gameId": "xyz",
            },
        }
        mock_get.return_value = self._mock_response(data)
        channels = fetch_tv_channels()
        assert channels is not None
        assert len(channels) == 1
        assert channels[0].user_name == "stringuser"
        assert channels[0].user_id == ""

    @patch("lichess.httpx.get")
    def test_channel_with_missing_user(self, mock_get):
        """Edge case: user field is missing."""
        data = {
            "Classical": {
                "rating": 2500,
                "gameId": "abc",
            },
        }
        mock_get.return_value = self._mock_response(data)
        channels = fetch_tv_channels()
        assert channels is not None
        assert len(channels) == 1
        assert channels[0].user_name == ""
        assert channels[0].user_id == ""


# ---------------------------------------------------------------------------
# fetch_tv_current_game tests (mocked HTTP streaming)
# ---------------------------------------------------------------------------


class TestFetchTvCurrentGame:
    """Tests for fetch_tv_current_game with mocked HTTP streaming."""

    @patch("lichess.httpx.stream")
    def test_returns_first_featured_event(self, mock_stream):
        lines = [
            json.dumps(SAMPLE_FEATURED_EVENT),
            json.dumps(SAMPLE_FEN_EVENT),
        ]
        mock_stream.return_value = _MockStreamResponse(lines)

        game = fetch_tv_current_game()
        assert game is not None
        assert game.game_id == "qVSOPtMc"
        assert game.orientation == "black"
        assert len(game.players) == 2

    @patch("lichess.httpx.stream")
    def test_skips_fen_events_before_featured(self, mock_stream):
        """If fen events appear before featured, they are skipped."""
        lines = [
            json.dumps(SAMPLE_FEN_EVENT),
            json.dumps(SAMPLE_FEATURED_EVENT),
        ]
        mock_stream.return_value = _MockStreamResponse(lines)

        game = fetch_tv_current_game()
        assert game is not None
        assert game.game_id == "qVSOPtMc"

    @patch("lichess.httpx.stream")
    def test_returns_none_on_empty_stream(self, mock_stream):
        mock_stream.return_value = _MockStreamResponse([])
        assert fetch_tv_current_game() is None

    @patch("lichess.httpx.stream")
    def test_returns_none_on_no_featured(self, mock_stream):
        """If stream only has fen events and no featured event."""
        lines = [json.dumps(SAMPLE_FEN_EVENT)]
        mock_stream.return_value = _MockStreamResponse(lines)
        assert fetch_tv_current_game() is None

    @patch("lichess.httpx.stream")
    def test_http_error_returns_none(self, mock_stream):
        mock_stream.side_effect = httpx.HTTPError("connection refused")
        assert fetch_tv_current_game() is None

    @patch("lichess.httpx.stream")
    def test_timeout_returns_none(self, mock_stream):
        mock_stream.side_effect = httpx.TimeoutException("timeout")
        assert fetch_tv_current_game() is None

    @patch("lichess.httpx.stream")
    def test_stream_error_returns_none(self, mock_stream):
        mock_stream.side_effect = httpx.StreamError("stream broken")
        assert fetch_tv_current_game() is None

    @patch("lichess.httpx.stream")
    def test_malformed_json_skipped(self, mock_stream):
        lines = [
            "bad json",
            json.dumps(SAMPLE_FEATURED_EVENT),
        ]
        mock_stream.return_value = _MockStreamResponse(lines)
        game = fetch_tv_current_game()
        assert game is not None
        assert game.game_id == "qVSOPtMc"

    @patch("lichess.httpx.stream")
    def test_http_status_error_returns_none(self, mock_stream):
        mock_stream.return_value = _MockStreamResponse([], status_code=500)
        assert fetch_tv_current_game() is None


# ---------------------------------------------------------------------------
# Integration-style test for TV feed
# ---------------------------------------------------------------------------


class TestTvFeedIntegration:
    """Integration-style tests combining featured + fen events."""

    @patch("lichess.httpx.stream")
    def test_full_game_flow(self, mock_stream):
        """Simulate a short game: featured event followed by several fen events."""
        lines = [
            json.dumps(SAMPLE_FEATURED_EVENT),
            json.dumps(SAMPLE_FEN_EVENT),
            json.dumps({
                "t": "fen",
                "d": {
                    "lm": "e7e5",
                    "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR",
                    "wc": 178,
                    "bc": 176,
                },
            }),
            json.dumps({
                "t": "fen",
                "d": {
                    "lm": "g1f3",
                    "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R",
                    "wc": 175,
                    "bc": 176,
                },
            }),
        ]
        mock_stream.return_value = _MockStreamResponse(lines)

        events = list(stream_tv_feed())
        assert len(events) == 4

        # First: featured game
        game = events[0]
        assert isinstance(game, LichessTvGame)
        assert game.game_id == "qVSOPtMc"

        # Subsequent: FEN updates
        assert all(isinstance(e, LichessTvFenEvent) for e in events[1:])
        assert events[1].last_move_uci == "e2e4"
        assert events[2].last_move_uci == "e7e5"
        assert events[3].last_move_uci == "g1f3"

        # Clocks should be ticking down
        assert events[2].black_clock == 176
        assert events[3].white_clock == 175


# ---------------------------------------------------------------------------
# _tv_feed_url tests
# ---------------------------------------------------------------------------


class TestTvFeedUrl:
    """Tests for the _tv_feed_url helper."""

    def test_default_url(self):
        assert _tv_feed_url() == TV_FEED_URL
        assert _tv_feed_url(None) == TV_FEED_URL
        assert _tv_feed_url("") == TV_FEED_URL

    def test_channel_url(self):
        assert _tv_feed_url("Bullet") == "https://lichess.org/api/tv/Bullet/feed"

    def test_channel_capitalized(self):
        assert _tv_feed_url("blitz") == "https://lichess.org/api/tv/Blitz/feed"

    def test_channel_with_whitespace(self):
        assert _tv_feed_url("  rapid  ") == "https://lichess.org/api/tv/Rapid/feed"


# ---------------------------------------------------------------------------
# Channel-based streaming tests
# ---------------------------------------------------------------------------


class TestStreamTvFeedWithChannel:
    """Tests for stream_tv_feed and fetch_tv_current_game with a channel."""

    @patch("lichess.httpx.stream")
    def test_stream_passes_channel_url(self, mock_stream):
        lines = [json.dumps(SAMPLE_FEATURED_EVENT)]
        mock_stream.return_value = _MockStreamResponse(lines)

        events = list(stream_tv_feed(channel="Bullet"))
        assert len(events) == 1
        # Verify the URL passed to httpx.stream includes the channel
        call_args = mock_stream.call_args
        assert call_args[0][1] == "https://lichess.org/api/tv/Bullet/feed"

    @patch("lichess.httpx.stream")
    def test_stream_default_channel_uses_main_feed(self, mock_stream):
        lines = [json.dumps(SAMPLE_FEATURED_EVENT)]
        mock_stream.return_value = _MockStreamResponse(lines)

        list(stream_tv_feed(channel=None))
        call_args = mock_stream.call_args
        assert call_args[0][1] == TV_FEED_URL

    @patch("lichess.httpx.stream")
    def test_fetch_current_game_passes_channel_url(self, mock_stream):
        lines = [json.dumps(SAMPLE_FEATURED_EVENT)]
        mock_stream.return_value = _MockStreamResponse(lines)

        game = fetch_tv_current_game(channel="Rapid")
        assert game is not None
        call_args = mock_stream.call_args
        assert call_args[0][1] == "https://lichess.org/api/tv/Rapid/feed"
