"""
Lichess API integration for fetching the daily puzzle and streaming Lichess TV.

Uses the public Lichess API (no authentication required):
  - https://lichess.org/api/puzzle/daily  — Daily puzzle
  - https://lichess.org/api/tv/feed       — Stream the current featured TV game (NDJSON)
  - https://lichess.org/api/tv/channels   — List current TV channel games

The daily puzzle response contains:
  - game.pgn: The game moves in SAN notation (space-separated)
  - puzzle.initialPly: Number of half-moves into the game before the puzzle starts
  - puzzle.solution: Correct moves in UCI format (solver and opponent interleaved)
  - puzzle.rating: Puzzle difficulty rating (Glicko-2)
  - puzzle.themes: Categorisation tags (e.g. "mateIn2", "sacrifice")

To reconstruct the puzzle position we replay *all* PGN moves on a board and
extract the resulting FEN.  The solver's first move is ``solution[0]``.

The TV feed is a newline-delimited JSON (NDJSON) stream.  Each line is a JSON
object with a ``t`` (type) field:
  - ``featured``: A new game has started.  Contains ``id``, ``orientation``,
    ``players`` (list of dicts with ``color``, ``user``, ``rating``, ``seconds``),
    and ``fen``.
  - ``fen``: A position update.  Contains ``lm`` (last move in UCI), ``fen``,
    ``wc`` (White clock seconds), and ``bc`` (Black clock seconds).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Generator

import chess
import httpx

DAILY_PUZZLE_URL = "https://lichess.org/api/puzzle/daily"
TV_FEED_URL = "https://lichess.org/api/tv/feed"
TV_CHANNELS_URL = "https://lichess.org/api/tv/channels"
DEFAULT_TIMEOUT = 10.0  # seconds
TV_STREAM_TIMEOUT = 60.0  # seconds – longer timeout for streaming connections


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass
class LichessDailyPuzzle:
    """A daily puzzle fetched from Lichess."""

    puzzle_id: str
    fen: str  # Board position where the solver must move
    rating: int  # Glicko-2 difficulty rating
    themes: list[str] = field(default_factory=list)
    solution_uci: list[str] = field(default_factory=list)  # UCI moves
    game_id: str = ""
    plays: int = 0  # Times the puzzle has been attempted on Lichess
    game_url: str = ""  # Full URL to the source game


# ---------------------------------------------------------------------------
# Lichess TV data classes
# ---------------------------------------------------------------------------


@dataclass
class LichessTvPlayer:
    """A player in a Lichess TV game."""

    color: str  # "white" or "black"
    user_name: str = ""
    user_id: str = ""
    rating: int = 0
    seconds: int = 0  # Initial clock time in seconds


@dataclass
class LichessTvGame:
    """Metadata for a featured TV game (from the ``featured`` event)."""

    game_id: str
    orientation: str  # "white" or "black" — recommended board orientation
    fen: str = chess.STARTING_FEN
    players: list[LichessTvPlayer] = field(default_factory=list)

    @property
    def white_player(self) -> LichessTvPlayer | None:
        """Return the white player, or *None* if not found."""
        for p in self.players:
            if p.color == "white":
                return p
        return None

    @property
    def black_player(self) -> LichessTvPlayer | None:
        """Return the black player, or *None* if not found."""
        for p in self.players:
            if p.color == "black":
                return p
        return None

    @property
    def game_url(self) -> str:
        """Full URL to the game on lichess.org."""
        return f"https://lichess.org/{self.game_id}"


@dataclass
class LichessTvFenEvent:
    """A position update from the TV feed (from the ``fen`` event)."""

    fen: str
    last_move_uci: str = ""  # e.g. "e2e4"
    white_clock: int = 0  # White remaining seconds
    black_clock: int = 0  # Black remaining seconds


@dataclass
class LichessTvChannel:
    """A single Lichess TV channel with its current game."""

    channel_name: str  # e.g. "Bullet", "Blitz", "Rapid", etc.
    game_id: str = ""
    rating: int = 0
    user_name: str = ""
    user_id: str = ""


# ---------------------------------------------------------------------------
# PGN helpers
# ---------------------------------------------------------------------------


def _pgn_to_board(pgn_text: str) -> chess.Board:
    """Replay a space-separated SAN PGN string and return the resulting board.

    Raises ``ValueError`` if any move is illegal or unparseable.
    """
    board = chess.Board()
    for san in pgn_text.split():
        move = board.parse_san(san)
        board.push(move)
    return board


def _format_solution_san(fen: str, solution_uci: list[str]) -> list[str]:
    """Convert a UCI solution sequence to SAN notation.

    Returns a list of SAN strings in the same order as *solution_uci*.
    If a move cannot be converted, its UCI string is kept as a fallback.
    """
    try:
        board = chess.Board(fen)
    except (ValueError, TypeError):
        # Invalid FEN — return UCI strings as-is
        return list(solution_uci)
    sans: list[str] = []
    for uci in solution_uci:
        try:
            move = chess.Move.from_uci(uci)
            san = board.san(move)
            sans.append(san)
            board.push(move)
        except Exception:
            # Catch *any* error from python-chess (AssertionError from push/san,
            # ValueError, TypeError, etc.) and fall back to the UCI string.
            sans.append(uci)
    return sans


# ---------------------------------------------------------------------------
# Theme display helpers
# ---------------------------------------------------------------------------

# Friendly labels for common Lichess puzzle themes
THEME_LABELS: dict[str, str] = {
    "advancedPawn": "Advanced Pawn",
    "advantage": "Advantage",
    "anapiPhilidorPattern": "Ana-Philidor Pattern",
    "arabianMate": "Arabian Mate",
    "attackingF2F7": "Attacking f2/f7",
    "attraction": "Attraction",
    "backRankMate": "Back Rank Mate",
    "bishopEndgame": "Bishop Endgame",
    "bodenMate": "Boden's Mate",
    "capturingDefender": "Capturing Defender",
    "castling": "Castling",
    "clearance": "Clearance",
    "crushing": "Crushing",
    "defensiveMove": "Defensive Move",
    "deflection": "Deflection",
    "discoveredAttack": "Discovered Attack",
    "doubleBishopMate": "Double Bishop Mate",
    "doubleCheck": "Double Check",
    "endgame": "Endgame",
    "enPassant": "En Passant",
    "equality": "Equality",
    "exposedKing": "Exposed King",
    "fork": "Fork",
    "hangingPiece": "Hanging Piece",
    "hookMate": "Hook Mate",
    "interference": "Interference",
    "intermezzo": "Intermezzo",
    "killBoxMate": "Kill Box Mate",
    "kingsideAttack": "Kingside Attack",
    "knightEndgame": "Knight Endgame",
    "long": "Long Puzzle",
    "master": "Master Game",
    "masterVsMaster": "Master vs Master",
    "mate": "Checkmate",
    "mateIn1": "Mate in 1",
    "mateIn2": "Mate in 2",
    "mateIn3": "Mate in 3",
    "mateIn4": "Mate in 4",
    "mateIn5": "Mate in 5+",
    "middlegame": "Middlegame",
    "oneMove": "One Move",
    "opening": "Opening",
    "pawnEndgame": "Pawn Endgame",
    "pin": "Pin",
    "promotion": "Promotion",
    "queenEndgame": "Queen Endgame",
    "queenRookEndgame": "Queen & Rook Endgame",
    "queensideAttack": "Queenside Attack",
    "quietMove": "Quiet Move",
    "rookEndgame": "Rook Endgame",
    "sacrifice": "Sacrifice",
    "short": "Short Puzzle",
    "skewer": "Skewer",
    "smotheredMate": "Smothered Mate",
    "superGM": "Super GM Game",
    "trappedPiece": "Trapped Piece",
    "underPromotion": "Under-Promotion",
    "veryLong": "Very Long Puzzle",
    "xRayAttack": "X-Ray Attack",
    "zugzwang": "Zugzwang",
}


def format_themes(themes: list[str]) -> str:
    """Return a human-readable comma-separated string of theme labels."""
    labels = [THEME_LABELS.get(t, t.replace("_", " ").title()) for t in themes]
    return ", ".join(labels)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_daily_puzzle(
    timeout: float = DEFAULT_TIMEOUT,
) -> LichessDailyPuzzle | None:
    """Fetch today's puzzle from the Lichess API.

    Returns a :class:`LichessDailyPuzzle` on success, or ``None`` if the
    request fails or the response cannot be parsed.
    """
    try:
        resp = httpx.get(
            DAILY_PUZZLE_URL,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        # Replay the full PGN to reach the puzzle position
        pgn_text: str = data["game"]["pgn"]
        board = _pgn_to_board(pgn_text)
        fen = board.fen()

        puzzle = data["puzzle"]
        game_id = data["game"]["id"]

        return LichessDailyPuzzle(
            puzzle_id=puzzle["id"],
            fen=fen,
            rating=int(puzzle["rating"]),
            themes=puzzle.get("themes", []),
            solution_uci=puzzle.get("solution", []),
            game_id=game_id,
            plays=int(puzzle.get("plays", 0)),
            game_url=f"https://lichess.org/{game_id}",
        )

    except (
        httpx.HTTPError,
        httpx.TimeoutException,
        KeyError,
        ValueError,
        TypeError,
        chess.IllegalMoveError,
        chess.InvalidMoveError,
        chess.AmbiguousMoveError,
    ):
        return None


def get_solution_san(puzzle: LichessDailyPuzzle) -> list[str]:
    """Return the puzzle solution as SAN (human-readable) move strings."""
    return _format_solution_san(puzzle.fen, puzzle.solution_uci)


# ---------------------------------------------------------------------------
# Lichess TV helpers
# ---------------------------------------------------------------------------


def _parse_tv_player(raw: dict) -> LichessTvPlayer:
    """Parse a single player dict from a ``featured`` event."""
    user = raw.get("user") or {}
    return LichessTvPlayer(
        color=raw.get("color", ""),
        user_name=user.get("name", "") if isinstance(user, dict) else str(user),
        user_id=user.get("id", "") if isinstance(user, dict) else "",
        rating=int(raw.get("rating", 0)),
        seconds=int(raw.get("seconds", 0)),
    )


def _parse_featured_event(data: dict) -> LichessTvGame:
    """Parse a ``featured`` event payload into a :class:`LichessTvGame`."""
    players = [_parse_tv_player(p) for p in data.get("players", [])]
    return LichessTvGame(
        game_id=data.get("id", ""),
        orientation=data.get("orientation", "white"),
        fen=data.get("fen", chess.STARTING_FEN),
        players=players,
    )


def _parse_fen_event(data: dict) -> LichessTvFenEvent:
    """Parse a ``fen`` event payload into a :class:`LichessTvFenEvent`."""
    return LichessTvFenEvent(
        fen=data.get("fen", ""),
        last_move_uci=data.get("lm", ""),
        white_clock=int(data.get("wc", 0)),
        black_clock=int(data.get("bc", 0)),
    )


# ---------------------------------------------------------------------------
# Lichess TV public API
# ---------------------------------------------------------------------------


def _tv_feed_url(channel: str | None = None) -> str:
    """Return the TV feed URL, optionally for a specific channel.

    Lichess exposes per-channel feeds at ``/api/tv/{channel}/feed`` where
    *channel* is a lowercase channel name (e.g. ``"bullet"``, ``"blitz"``).
    When *channel* is ``None`` or empty the default top-rated feed is used.
    """
    if channel:
        safe = channel.strip().capitalize()
        return f"https://lichess.org/api/tv/{safe}/feed"
    return TV_FEED_URL


def stream_tv_feed(
    channel: str | None = None,
    timeout: float = TV_STREAM_TIMEOUT,
) -> Generator[LichessTvGame | LichessTvFenEvent, None, None]:
    """Stream the Lichess TV feed, yielding game and position events.

    Args:
        channel: Optional channel name (e.g. ``"Bullet"``, ``"Blitz"``).
                 When ``None`` the default top-rated feed is used.
        timeout: Read/connect timeout in seconds.

    This is a **blocking generator** that connects to the Lichess TV NDJSON
    stream and yields events one at a time:

    * :class:`LichessTvGame` — emitted when a new featured game starts.
    * :class:`LichessTvFenEvent` — emitted on each position update.

    The generator terminates when the server closes the connection or on
    network error.  Callers should wrap usage in a try/except if they want
    to handle reconnection.

    Example::

        for event in stream_tv_feed():
            if isinstance(event, LichessTvGame):
                print(f"New game: {event.game_id}")
            elif isinstance(event, LichessTvFenEvent):
                print(f"FEN: {event.fen}  last move: {event.last_move_uci}")
    """
    url = _tv_feed_url(channel)
    try:
        with httpx.stream(
            "GET",
            url,
            headers={"Accept": "application/x-ndjson"},
            timeout=httpx.Timeout(timeout, connect=timeout, read=timeout),
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue  # skip malformed lines

                event_type = obj.get("t", "")
                data = obj.get("d", {})
                if event_type == "featured":
                    yield _parse_featured_event(data)
                elif event_type == "fen":
                    yield _parse_fen_event(data)
                # Unknown event types are silently ignored.
    except (
        httpx.HTTPError,
        httpx.TimeoutException,
        httpx.StreamError,
    ):
        # Connection lost or timed out — generator terminates.
        return


def fetch_tv_channels(
    timeout: float = DEFAULT_TIMEOUT,
) -> list[LichessTvChannel] | None:
    """Fetch the current Lichess TV channels.

    Returns a list of :class:`LichessTvChannel` on success, or ``None`` if
    the request fails or the response cannot be parsed.

    The Lichess ``/api/tv/channels`` endpoint returns a JSON object keyed by
    channel name (e.g. ``"Bullet"``, ``"Blitz"``), each containing:

    * ``user.id``
    * ``user.name``
    * ``rating``
    * ``gameId``
    """
    try:
        resp = httpx.get(
            TV_CHANNELS_URL,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        channels: list[LichessTvChannel] = []
        for name, info in data.items():
            user = info.get("user") or {}
            channels.append(
                LichessTvChannel(
                    channel_name=name,
                    game_id=info.get("gameId", ""),
                    rating=int(info.get("rating", 0)),
                    user_name=user.get("name", "")
                    if isinstance(user, dict)
                    else str(user),
                    user_id=user.get("id", "") if isinstance(user, dict) else "",
                )
            )
        return channels

    except (
        httpx.HTTPError,
        httpx.TimeoutException,
        KeyError,
        ValueError,
        TypeError,
    ):
        return None


def fetch_tv_current_game(
    channel: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> LichessTvGame | None:
    """Fetch metadata for the current Lichess TV game (non-streaming).

    Args:
        channel: Optional channel name (e.g. ``"Bullet"``).
        timeout: Read/connect timeout in seconds.

    Connects to the TV feed, reads only the first ``featured`` event, and
    returns the resulting :class:`LichessTvGame`.  Returns ``None`` on error.
    """
    url = _tv_feed_url(channel)
    try:
        with httpx.stream(
            "GET",
            url,
            headers={"Accept": "application/x-ndjson"},
            timeout=httpx.Timeout(timeout, connect=timeout, read=timeout),
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if obj.get("t") == "featured":
                    return _parse_featured_event(obj.get("d", {}))
        return None
    except (
        httpx.HTTPError,
        httpx.TimeoutException,
        httpx.StreamError,
    ):
        return None
