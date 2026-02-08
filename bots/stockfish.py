"""
Stockfish-powered bot using the UCI protocol via python-chess's engine module.

Provides configurable difficulty through Stockfish's Skill Level (0–20) and
thinking time limits.  Gracefully handles a missing Stockfish binary — callers
can check :func:`is_stockfish_available` before instantiating.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
from typing import ClassVar

import chess
import chess.engine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stockfish binary discovery
# ---------------------------------------------------------------------------

# Common installation paths per platform (checked in order after $PATH).
_COMMON_PATHS: list[str] = []

_system = platform.system()
if _system == "Linux":
    _COMMON_PATHS = [
        "/usr/games/stockfish",
        "/usr/local/bin/stockfish",
        "/usr/bin/stockfish",
        "/snap/bin/stockfish",
    ]
elif _system == "Darwin":
    _COMMON_PATHS = [
        "/usr/local/bin/stockfish",
        "/opt/homebrew/bin/stockfish",
    ]
elif _system == "Windows":
    _COMMON_PATHS = [
        r"C:\stockfish\stockfish.exe",
        r"C:\Program Files\stockfish\stockfish.exe",
        r"C:\Program Files (x86)\stockfish\stockfish.exe",
    ]


def find_stockfish_path() -> str | None:
    """Return the absolute path to a Stockfish binary, or ``None``.

    Resolution order:
    1. ``STOCKFISH_PATH`` environment variable (if set and exists).
    2. ``stockfish`` on ``$PATH`` (via :func:`shutil.which`).
    3. Platform-specific common install locations.
    """
    # 1. Explicit env var
    env_path = os.environ.get("STOCKFISH_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2. $PATH lookup
    which_path = shutil.which("stockfish")
    if which_path:
        return which_path

    # 3. Well-known locations
    for candidate in _COMMON_PATHS:
        if os.path.isfile(candidate):
            return candidate

    return None


def is_stockfish_available() -> bool:
    """Return ``True`` if a usable Stockfish binary can be found."""
    return find_stockfish_path() is not None


# ---------------------------------------------------------------------------
# Preset difficulty configurations
# ---------------------------------------------------------------------------

# Each tuple: (skill_level, think_time_seconds, elo_estimate)
# Skill Level ranges from 0 (weakest) to 20 (strongest) in Stockfish.
# Think time caps how long the engine is allowed to ponder per move.
DIFFICULTY_PRESETS: dict[str, tuple[int, float, int]] = {
    "stockfish_1": (1, 0.05, 1200),   # Beginner: very low skill, instant
    "stockfish_2": (3, 0.1, 1400),    # Casual: low skill, fast
    "stockfish_3": (5, 0.2, 1600),    # Intermediate
    "stockfish_4": (8, 0.3, 1800),    # Advanced
    "stockfish_5": (11, 0.5, 2000),   # Strong club player
    "stockfish_6": (14, 0.8, 2200),   # Expert
    "stockfish_7": (17, 1.0, 2500),   # Master
    "stockfish_8": (20, 1.5, 2800),   # Full strength
}


# ---------------------------------------------------------------------------
# StockfishBot
# ---------------------------------------------------------------------------


class StockfishBot:
    """Chess bot powered by the Stockfish engine.

    Parameters
    ----------
    skill_level:
        Stockfish ``Skill Level`` UCI option (0–20).  Lower values make the
        engine play weaker.
    think_time:
        Maximum seconds the engine may think per move.
    stockfish_path:
        Explicit path to the Stockfish binary.  If ``None``,
        :func:`find_stockfish_path` is used.
    threads:
        Number of search threads (default 1 — sufficient for casual play).
    hash_mb:
        Hash table size in MiB (default 16).
    """

    # Class-level flag: whether the engine process is shared or per-instance.
    # We use per-instance to keep things simple and safe.
    _VALID_SKILL_RANGE: ClassVar[range] = range(0, 21)

    def __init__(
        self,
        skill_level: int = 20,
        think_time: float = 1.0,
        stockfish_path: str | None = None,
        threads: int = 1,
        hash_mb: int = 16,
    ) -> None:
        self.skill_level = max(0, min(20, skill_level))
        self.think_time = max(0.01, think_time)
        self.threads = max(1, threads)
        self.hash_mb = max(1, hash_mb)

        self._path = stockfish_path or find_stockfish_path()
        self._engine: chess.engine.SimpleEngine | None = None

        # Display name
        if self.skill_level == 20:
            self.name = "Stockfish (Max)"
        else:
            self.name = f"Stockfish (Lvl {self.skill_level})"

    # -- Engine lifecycle --------------------------------------------------

    def _ensure_engine(self) -> chess.engine.SimpleEngine | None:
        """Start or return the running Stockfish engine.

        Returns ``None`` if the binary is unavailable or the engine fails to
        start.
        """
        if self._engine is not None:
            # Quick health-check: see if the transport is alive
            try:
                # Attempt a ping — if the process died this will raise
                self._engine.ping()
                return self._engine
            except (chess.engine.EngineTerminatedError, Exception):
                self._engine = None

        if self._path is None:
            logger.warning("Stockfish binary not found — cannot start engine.")
            return None

        try:
            engine = chess.engine.SimpleEngine.popen_uci(self._path)
            # Configure engine options
            engine.configure({
                "Threads": self.threads,
                "Hash": self.hash_mb,
                "Skill Level": self.skill_level,
            })
            self._engine = engine
            return engine
        except (chess.engine.EngineTerminatedError, FileNotFoundError, OSError) as exc:
            logger.error("Failed to start Stockfish: %s", exc)
            return None

    def close(self) -> None:
        """Shut down the engine process (if running).

        Safe to call multiple times.
        """
        if self._engine is not None:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None

    def __del__(self) -> None:
        self.close()

    # -- ChessBot protocol -------------------------------------------------

    def choose_move(self, board: chess.Board) -> chess.Move | None:
        """Pick the best move using Stockfish.

        Returns ``None`` if the engine is unavailable or no legal moves exist.
        """
        if board.is_game_over() or not list(board.legal_moves):
            return None

        engine = self._ensure_engine()
        if engine is None:
            return None

        try:
            result = engine.play(
                board,
                chess.engine.Limit(time=self.think_time),
            )
            return result.move
        except (chess.engine.EngineTerminatedError, chess.engine.EngineError) as exc:
            logger.error("Stockfish engine error during play: %s", exc)
            # Try to restart next time
            self._engine = None
            return None
        except Exception as exc:  # pragma: no cover
            logger.error("Unexpected error from Stockfish: %s", exc)
            self._engine = None
            return None

    # -- Analysis helpers (for hints / evaluation bar) ---------------------

    def analyse(
        self,
        board: chess.Board,
        time_limit: float | None = None,
        depth: int | None = None,
    ) -> chess.engine.InfoDict | None:
        """Run Stockfish analysis and return the info dict.

        Returns ``None`` if the engine is unavailable.
        """
        engine = self._ensure_engine()
        if engine is None:
            return None

        limit = chess.engine.Limit(
            time=time_limit or self.think_time,
            depth=depth,
        )
        try:
            return engine.analyse(board, limit)
        except (chess.engine.EngineTerminatedError, chess.engine.EngineError):
            self._engine = None
            return None

    def get_evaluation(
        self,
        board: chess.Board,
        depth: int = 15,
    ) -> int | None:
        """Return position evaluation in centipawns (from white's perspective).

        Returns ``None`` if analysis fails.
        """
        info = self.analyse(board, depth=depth)
        if info is None:
            return None
        score = info.get("score")
        if score is None:
            return None
        # .white() gives score from white's perspective
        cp = score.white().score(mate_score=100_000)
        return cp

    def get_best_moves(
        self,
        board: chess.Board,
        count: int = 3,
        depth: int = 15,
    ) -> list[tuple[chess.Move, int]]:
        """Return the top *count* moves with their evaluations (centipawns).

        Each entry is ``(move, score_cp)`` where positive favours the side to
        move.
        """
        engine = self._ensure_engine()
        if engine is None:
            return []

        limit = chess.engine.Limit(depth=depth)
        try:
            results = engine.analyse(
                board,
                limit,
                multipv=count,
            )
        except (chess.engine.EngineTerminatedError, chess.engine.EngineError):
            self._engine = None
            return []

        # results is a list of info dicts when multipv > 1
        if not isinstance(results, list):
            results = [results]

        moves: list[tuple[chess.Move, int]] = []
        for info in results:
            pv = info.get("pv")
            sc = info.get("score")
            if pv and sc:
                move = pv[0]
                cp = sc.relative.score(mate_score=100_000)
                moves.append((move, cp))
        return moves
