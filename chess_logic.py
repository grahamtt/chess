"""
Chess game logic using the python-chess engine.
UI coordinates: row 0 = rank 8 (top), row 7 = rank 1 (bottom); col 0 = a-file, col 7 = h-file.
"""

import chess


def _square_to_ui(square: chess.Square) -> tuple[int, int]:
    """Convert python-chess square index to (row, col)."""
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    return (7 - rank, file)


def _ui_to_square(row: int, col: int) -> chess.Square:
    """Convert (row, col) to python-chess square index."""
    return chess.square(col, 7 - row)


class ChessGame:
    """Thin wrapper around chess.Board for the Flet UI."""

    def __init__(self) -> None:
        self._board = chess.Board()

    def reset(self) -> None:
        self._board.reset()

    def set_fen(self, fen: str) -> bool:
        """Load position from FEN. Returns True if FEN was valid."""
        try:
            self._board.set_fen(fen)
            return True
        except (ValueError, TypeError):
            return False

    def can_undo(self) -> bool:
        """True if there is at least one move to take back."""
        return len(self._board.move_stack) > 0

    def undo(self) -> bool:
        """Take back the last move. Return True if a move was undone."""
        if not self.can_undo():
            return False
        self._board.pop()
        return True

    def piece_at(self, row: int, col: int) -> tuple[str, str] | None:
        """Return (color, piece) at (row, col) or None. piece is K,Q,R,B,N,P."""
        sq = _ui_to_square(row, col)
        p = self._board.piece_at(sq)
        if p is None:
            return None
        color = "white" if p.color else "black"
        piece = p.symbol().upper()
        return (color, piece)

    @property
    def turn(self) -> str:
        return "white" if self._board.turn else "black"

    def legal_moves_from(self, row: int, col: int) -> list[tuple[int, int]]:
        """Return list of (row, col) squares that the piece at (row, col) can move to."""
        from_sq = _ui_to_square(row, col)
        return [
            _square_to_ui(m.to_square)
            for m in self._board.legal_moves
            if m.from_square == from_sq
        ]

    def make_move(self, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        """Play the move if legal. Default to queen on promotion. Return True if moved."""
        from_sq = _ui_to_square(from_row, from_col)
        to_sq = _ui_to_square(to_row, to_col)
        candidates = [
            m for m in self._board.legal_moves
            if m.from_square == from_sq and m.to_square == to_sq
        ]
        if not candidates:
            return False
        move = next(
            (m for m in candidates if getattr(m, "promotion", None) == chess.QUEEN),
            candidates[0],
        )
        self._board.push(move)
        return True

    def get_board(self) -> chess.Board:
        """Return a copy of the current board (for bots; do not mutate)."""
        return self._board.copy()

    def apply_move(self, move: chess.Move) -> bool:
        """Apply a move from a bot. Return True if applied."""
        if move not in self._board.legal_moves:
            return False
        self._board.push(move)
        return True

    def is_checkmate(self) -> bool:
        return self._board.is_checkmate()

    def is_stalemate(self) -> bool:
        return self._board.is_stalemate()

    def is_only_kings_left(self) -> bool:
        """True if only the two kings remain (draw by insufficient material)."""
        piece_map = self._board.piece_map()
        if len(piece_map) != 2:
            return False
        return all(p.piece_type == chess.KING for p in piece_map.values())

    def is_in_check(self) -> bool:
        return self._board.is_check()

    def get_move_history(self) -> str:
        """Return move history as SAN text, e.g. '1. e4 e5 2. Nf3 Nc6'.
        Works even when the position was loaded from FEN (moves are in context of the position before each move).
        """
        if not self._board.move_stack:
            return ""
        sans: list[str] = []
        stack = self._board.move_stack
        for i, move in enumerate(stack):
            # Position before this move: copy board and pop (len - i) moves
            temp = self._board.copy()
            for _ in range(len(stack) - i):
                temp.pop()
            try:
                sans.append(temp.san(move))
            except (AssertionError, ValueError):
                sans.append(move.uci())  # fallback if SAN fails
        lines: list[str] = []
        i = 0
        n = 1
        while i < len(sans):
            white = sans[i]
            black = sans[i + 1] if i + 1 < len(sans) else None
            if black is not None:
                lines.append(f"{n}. {white} {black}")
                i += 2
            else:
                lines.append(f"{n}. {white}")
                i += 1
            n += 1
        return "\n".join(lines)
