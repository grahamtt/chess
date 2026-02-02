"""
Piece SVGs from the python-chess library (Cburnett set, GPL/BSD/GFDL).
Maps our (color, piece) to chess.Piece and returns chess.svg.piece() SVG.
"""

import chess
import chess.svg


def get_svg(color: str, piece: str) -> str:
    """Return SVG string for the given piece. color is 'white'|'black', piece is K,Q,R,B,N,P."""
    symbol = piece if color == "white" else piece.lower()
    p = chess.Piece.from_symbol(symbol)
    return chess.svg.piece(p)
