"""
Chess bots: pluggable API and built-in implementations.
"""

from bots.base import ChessBot, compute_move_time_budget
from bots.botbot import BotBot
from bots.minimax import MinimaxBot, SearchTimeout
from bots.simple import SimpleBot
from bots.stockfish import (
    DIFFICULTY_PRESETS,
    AdaptiveStockfishBot,
    StockfishBot,
    elo_to_stockfish_params,
    find_stockfish_path,
    is_stockfish_available,
)

__all__ = [
    "AdaptiveStockfishBot",
    "BotBot",
    "ChessBot",
    "DIFFICULTY_PRESETS",
    "MinimaxBot",
    "SearchTimeout",
    "SimpleBot",
    "StockfishBot",
    "compute_move_time_budget",
    "elo_to_stockfish_params",
    "find_stockfish_path",
    "is_stockfish_available",
]
