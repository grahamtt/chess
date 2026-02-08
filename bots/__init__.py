"""
Chess bots: pluggable API and built-in implementations.
"""

from bots.base import ChessBot
from bots.botbot import BotBot
from bots.minimax import MinimaxBot
from bots.simple import SimpleBot
from bots.stockfish import (
    DIFFICULTY_PRESETS,
    StockfishBot,
    find_stockfish_path,
    is_stockfish_available,
)

__all__ = [
    "BotBot",
    "ChessBot",
    "DIFFICULTY_PRESETS",
    "MinimaxBot",
    "SimpleBot",
    "StockfishBot",
    "find_stockfish_path",
    "is_stockfish_available",
]
