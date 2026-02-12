"""
Chess bots: pluggable API and built-in implementations.
"""

from bots.base import ChessBot
from bots.botbot import BotBot
from bots.minimax import MinimaxBot
from bots.mobility import PieceMobilityBot
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
    "PieceMobilityBot",
    "SimpleBot",
    "StockfishBot",
    "elo_to_stockfish_params",
    "find_stockfish_path",
    "is_stockfish_available",
]
