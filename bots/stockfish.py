"""
Stockfish-powered bot using the UCI protocol via python-chess's engine module.

Provides configurable difficulty through Stockfish's Skill Level (0–20) and
thinking time limits.  Gracefully handles a missing Stockfish binary — callers
can check :func:`is_stockfish_available` before instantiating.

Includes :class:`AdaptiveStockfishBot` which dynamically matches its playing
strength to the human player's ELO rating.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
from typing import Callable, ClassVar

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
    "stockfish_1": (1, 0.05, 1200),  # Beginner: very low skill, instant
    "stockfish_2": (3, 0.1, 1400),  # Casual: low skill, fast
    "stockfish_3": (5, 0.2, 1600),  # Intermediate
    "stockfish_4": (8, 0.3, 1800),  # Advanced
    "stockfish_5": (11, 0.5, 2000),  # Strong club player
    "stockfish_6": (14, 0.8, 2200),  # Expert
    "stockfish_7": (17, 1.0, 2500),  # Master
    "stockfish_8": (20, 1.5, 2800),  # Full strength
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
    chess960:
        If ``True``, configure the engine for Chess960 (Fischer Random)
        positions via the ``UCI_Chess960`` option.
    """

    # Class-level flag: whether the engine process is shared or per-instance.
    # We use per-instance to keep things simple and safe.
    _VALID_SKILL_RANGE: ClassVar[range] = range(0, 21)

    # Supported game modes for Stockfish
    SUPPORTED_MODES: ClassVar[frozenset[str]] = frozenset({"standard", "chess960"})

    def __init__(
        self,
        skill_level: int = 20,
        think_time: float = 1.0,
        stockfish_path: str | None = None,
        threads: int = 1,
        hash_mb: int = 16,
        chess960: bool = False,
    ) -> None:
        self.skill_level = max(0, min(20, skill_level))
        self.think_time = max(0.01, think_time)
        self.threads = max(1, threads)
        self.hash_mb = max(1, hash_mb)
        self.chess960 = chess960

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
            options: dict[str, int | bool] = {
                "Threads": self.threads,
                "Hash": self.hash_mb,
                "Skill Level": self.skill_level,
            }
            if self.chess960:
                options["UCI_Chess960"] = True
            engine.configure(options)
            self._engine = engine
            return engine
        except (chess.engine.EngineTerminatedError, FileNotFoundError, OSError) as exc:
            logger.error("Failed to start Stockfish: %s", exc)
            return None

    def set_chess960(self, enabled: bool) -> None:
        """Enable or disable Chess960 mode.

        If the setting changes and the engine is running, it is shut down so
        that it will be restarted with the correct ``UCI_Chess960`` option on
        the next call.
        """
        if enabled != self.chess960:
            self.chess960 = enabled
            # Restart the engine with the new config on next use
            self.close()

    @classmethod
    def is_mode_supported(cls, game_mode: str) -> bool:
        """Return True if the given game mode is supported by Stockfish."""
        return game_mode in cls.SUPPORTED_MODES

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


# ---------------------------------------------------------------------------
# ELO → Stockfish parameter mapping (used by AdaptiveStockfishBot)
# ---------------------------------------------------------------------------

# Piecewise-linear mapping: (player_elo, skill_level, think_time)
# Interpolated between these anchor points to produce a smooth curve.
_ELO_SKILL_ANCHORS: list[tuple[int, int, float]] = [
    (400, 0, 0.05),
    (600, 1, 0.05),
    (800, 2, 0.08),
    (1000, 3, 0.10),
    (1200, 5, 0.15),
    (1400, 8, 0.25),
    (1600, 11, 0.40),
    (1800, 14, 0.60),
    (2000, 17, 0.80),
    (2200, 19, 1.00),
    (2500, 20, 1.50),
]


def elo_to_stockfish_params(player_elo: int) -> tuple[int, float]:
    """Map a player ELO rating to ``(skill_level, think_time)`` for Stockfish.

    Uses piecewise linear interpolation between anchor points defined in
    :data:`_ELO_SKILL_ANCHORS`.  Values are clamped at the extremes.

    Returns:
        A ``(skill_level, think_time)`` tuple.
    """
    # Clamp to anchor range
    if player_elo <= _ELO_SKILL_ANCHORS[0][0]:
        return _ELO_SKILL_ANCHORS[0][1], _ELO_SKILL_ANCHORS[0][2]
    if player_elo >= _ELO_SKILL_ANCHORS[-1][0]:
        return _ELO_SKILL_ANCHORS[-1][1], _ELO_SKILL_ANCHORS[-1][2]

    # Find the two surrounding anchors and interpolate
    for i in range(len(_ELO_SKILL_ANCHORS) - 1):
        elo_lo, skill_lo, time_lo = _ELO_SKILL_ANCHORS[i]
        elo_hi, skill_hi, time_hi = _ELO_SKILL_ANCHORS[i + 1]
        if elo_lo <= player_elo <= elo_hi:
            t = (player_elo - elo_lo) / (elo_hi - elo_lo)
            skill = round(skill_lo + t * (skill_hi - skill_lo))
            think = time_lo + t * (time_hi - time_lo)
            return max(0, min(20, skill)), round(max(0.01, think), 3)

    # Fallback (should not be reached)
    return _ELO_SKILL_ANCHORS[-1][1], _ELO_SKILL_ANCHORS[-1][2]  # pragma: no cover


# ---------------------------------------------------------------------------
# AdaptiveStockfishBot
# ---------------------------------------------------------------------------


class AdaptiveStockfishBot:
    """Stockfish bot that dynamically matches its strength to the player's ELO.

    Before each move the bot queries the player's current rating (via a
    callback) and reconfigures the Stockfish engine to play at a corresponding
    skill level.  This produces a continuously-adapting opponent that grows (or
    shrinks) in difficulty as the player improves (or struggles).

    Parameters
    ----------
    elo_fn:
        A zero-argument callable that returns the player's current ELO rating
        (``int``).  This is called before every move.
    stockfish_path:
        Explicit path to the Stockfish binary.  ``None`` ⇒ auto-detect.
    threads:
        Number of Stockfish search threads.
    hash_mb:
        Hash table size in MiB.
    chess960:
        Whether to enable Chess960 mode.
    """

    # Supported game modes (same as StockfishBot)
    SUPPORTED_MODES: ClassVar[frozenset[str]] = frozenset({"standard", "chess960"})

    def __init__(
        self,
        elo_fn: Callable[[], int],
        stockfish_path: str | None = None,
        threads: int = 1,
        hash_mb: int = 16,
        chess960: bool = False,
    ) -> None:
        self._elo_fn = elo_fn
        self._stockfish_path = stockfish_path
        self._threads = threads
        self._hash_mb = hash_mb
        self.chess960 = chess960

        # Internal StockfishBot instance – replaced when the skill level changes
        self._bot: StockfishBot | None = None
        self._current_skill: int | None = None
        self._current_think: float | None = None

        self.name = "Stockfish (Adaptive)"

    # -- Internal helpers --------------------------------------------------

    def _sync_bot(self) -> StockfishBot | None:
        """Ensure the inner :class:`StockfishBot` matches the player's ELO."""
        player_elo = self._elo_fn()
        skill, think = elo_to_stockfish_params(player_elo)

        if (
            self._bot is not None
            and skill == self._current_skill
            and think == self._current_think
        ):
            return self._bot  # No change needed

        # Need to create or reconfigure the engine
        if self._bot is not None:
            self._bot.close()

        self._bot = StockfishBot(
            skill_level=skill,
            think_time=think,
            stockfish_path=self._stockfish_path,
            threads=self._threads,
            hash_mb=self._hash_mb,
            chess960=self.chess960,
        )
        self._current_skill = skill
        self._current_think = think
        return self._bot

    # -- ChessBot protocol -------------------------------------------------

    def choose_move(self, board: chess.Board) -> chess.Move | None:
        """Pick a move at a skill level matching the player's ELO."""
        bot = self._sync_bot()
        if bot is None:
            return None
        return bot.choose_move(board)

    # -- Lifecycle ---------------------------------------------------------

    def set_chess960(self, enabled: bool) -> None:
        """Enable or disable Chess960 mode."""
        if enabled != self.chess960:
            self.chess960 = enabled
            self.close()

    @classmethod
    def is_mode_supported(cls, game_mode: str) -> bool:
        """Return True if the given game mode is supported."""
        return game_mode in cls.SUPPORTED_MODES

    def close(self) -> None:
        """Shut down the underlying engine (if running)."""
        if self._bot is not None:
            self._bot.close()
            self._bot = None
            self._current_skill = None
            self._current_think = None

    def __del__(self) -> None:
        self.close()

    @property
    def current_skill_level(self) -> int | None:
        """The Stockfish Skill Level currently in use (or ``None``)."""
        return self._current_skill

    @property
    def current_think_time(self) -> float | None:
        """The think-time limit currently in use (or ``None``)."""
        return self._current_think
