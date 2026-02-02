"""
Chess bots: pluggable API and built-in implementations.
"""

from bots.base import ChessBot
from bots.botbot import BotBot
from bots.minimax import MinimaxBot
from bots.simple import SimpleBot

__all__ = ["BotBot", "ChessBot", "MinimaxBot", "SimpleBot"]
