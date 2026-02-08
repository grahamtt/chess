"""
Lichess API integration for fetching the daily puzzle.

Uses the public Lichess API (no authentication required):
  https://lichess.org/api/puzzle/daily

The daily puzzle response contains:
  - game.pgn: The game moves in SAN notation (space-separated)
  - puzzle.initialPly: Number of half-moves into the game before the puzzle starts
  - puzzle.solution: Correct moves in UCI format (solver and opponent interleaved)
  - puzzle.rating: Puzzle difficulty rating (Glicko-2)
  - puzzle.themes: Categorisation tags (e.g. "mateIn2", "sacrifice")

To reconstruct the puzzle position we replay *all* PGN moves on a board and
extract the resulting FEN.  The solver's first move is ``solution[0]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import chess
import httpx

DAILY_PUZZLE_URL = "https://lichess.org/api/puzzle/daily"
DEFAULT_TIMEOUT = 10.0  # seconds


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
    board = chess.Board(fen)
    sans: list[str] = []
    for uci in solution_uci:
        try:
            move = chess.Move.from_uci(uci)
            san = board.san(move)
            sans.append(san)
            board.push(move)
        except (ValueError, AssertionError):
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
