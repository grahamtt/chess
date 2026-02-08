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
        except (ValueError, TypeError, AttributeError, AssertionError):
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

    def is_promotion_move(
        self, from_row: int, from_col: int, to_row: int, to_col: int
    ) -> bool:
        """Check if moving from (from_row, from_col) to (to_row, to_col) is a pawn promotion."""
        from_sq = _ui_to_square(from_row, from_col)
        to_sq = _ui_to_square(to_row, to_col)
        candidates = [
            m
            for m in self._board.legal_moves
            if m.from_square == from_sq and m.to_square == to_sq
        ]
        return any(m.promotion is not None for m in candidates)

    def make_move(
        self,
        from_row: int,
        from_col: int,
        to_row: int,
        to_col: int,
        promotion: int | None = None,
    ) -> bool:
        """Play the move if legal. Uses specified promotion piece, or defaults to queen. Return True if moved."""
        from_sq = _ui_to_square(from_row, from_col)
        to_sq = _ui_to_square(to_row, to_col)
        candidates = [
            m
            for m in self._board.legal_moves
            if m.from_square == from_sq and m.to_square == to_sq
        ]
        if not candidates:
            return False
        if promotion is not None:
            move = next(
                (m for m in candidates if m.promotion == promotion),
                candidates[0],
            )
        else:
            move = next(
                (m for m in candidates if getattr(m, "promotion", None) == chess.QUEEN),
                candidates[0],
            )
        try:
            self._board.push(move)
        except AssertionError:
            return False
        return True

    def get_board(self) -> chess.Board:
        """Return a copy of the current board (for bots; do not mutate)."""
        return self._board.copy()

    def apply_move(self, move: chess.Move) -> bool:
        """Apply a move from a bot. Return True if applied."""
        if move not in self._board.legal_moves:
            return False
        try:
            self._board.push(move)
        except AssertionError:
            return False
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

    def get_hint_moves(
        self, depth: int = 3, top_n: int = 3
    ) -> list[tuple[chess.Move, int, str]]:
        """
        Get top N best moves for the current position using minimax evaluation.
        Returns list of (move, score, san_notation) tuples, sorted by score (best first).

        Args:
            depth: Search depth for minimax (default 3)
            top_n: Number of top moves to return (default 3)
        """
        from bots.minimax import negamax

        if self._board.is_game_over():
            return []

        legal_moves = list(self._board.legal_moves)
        if not legal_moves:
            return []

        # Evaluate each move
        scored_moves = []
        for move in legal_moves:
            test_board = self._board.copy()
            test_board.push(move)
            # Use negamax to get score from opponent's perspective, then negate
            score, _ = negamax(test_board, depth - 1, -1_000_000, 1_000_000, 0.0, None)
            # Negate because negamax returns score from opponent's perspective
            our_score = -score

            # Get SAN notation for the move
            try:
                san = self._board.san(move)
            except (AssertionError, ValueError):
                san = move.uci()

            scored_moves.append((our_score, move, san))

        # Sort by score (descending) and return top N
        scored_moves.sort(key=lambda x: x[0], reverse=True)
        return [(move, score, san) for score, move, san in scored_moves[:top_n]]

    def get_initial_fen(self) -> str:
        """Return the FEN of the position before any moves were made.

        This is needed for saving/restoring game state with full move history.
        """
        temp = self._board.copy()
        while temp.move_stack:
            temp.pop()
        return temp.fen()

    def get_moves_uci(self) -> list[str]:
        """Return all moves made as UCI strings (e.g. ['e2e4', 'e7e5', ...])."""
        return [m.uci() for m in self._board.move_stack]

    def load_from_moves(self, initial_fen: str, moves_uci: list[str]) -> bool:
        """Restore game state from an initial FEN and a list of UCI moves.

        Returns True if the state was fully restored, False on any error.
        """
        try:
            self._board.set_fen(initial_fen)
            for uci in moves_uci:
                move = chess.Move.from_uci(uci)
                if move not in self._board.legal_moves:
                    return False
                self._board.push(move)
            return True
        except (ValueError, TypeError, AttributeError, AssertionError):
            self._board.reset()
            return False

    def get_position_evaluation(self, depth: int = 2) -> int:
        """
        Get position evaluation in centipawns from white's perspective.
        Positive values favor white, negative values favor black.
        Uses a neutral evaluation that doesn't bias based on whose turn it is.

        Args:
            depth: Search depth for evaluation (default 2 for quick updates)

        Returns:
            Evaluation score in centipawns (100 = 1 pawn advantage for white)
        """
        from bots.minimax import (
            CENTER_BONUS,
            CENTER_SQUARES,
            CHECK_BONUS,
            KNIGHT_CENTER_BONUS,
            KNIGHT_CENTER_SQUARES,
            MOBILITY_BONUS,
            PAWN_ADVANCE_WEIGHT,
            PIECE_VALUES,
            _pawn_advancement_bonus,
        )

        if self._board.is_game_over():
            if self._board.is_checkmate():
                # Checkmate: return very large negative if white is mated, positive if black is mated
                return -100_000 if self._board.turn == chess.WHITE else 100_000
            # Stalemate or draw
            return 0

        # Neutral evaluation from white's perspective (not biased by whose turn it is)
        score = 0

        # Material and positional evaluation
        for square in chess.SQUARES:
            piece = self._board.piece_at(square)
            if piece is None:
                continue
            value = PIECE_VALUES[piece.piece_type]
            if piece.color == chess.WHITE:
                score += value
                if square in CENTER_SQUARES:
                    score += CENTER_BONUS
                if piece.piece_type == chess.PAWN:
                    score += (
                        _pawn_advancement_bonus(square, piece.color)
                        * PAWN_ADVANCE_WEIGHT
                    )
                if piece.piece_type == chess.KNIGHT and square in KNIGHT_CENTER_SQUARES:
                    score += KNIGHT_CENTER_BONUS
            else:  # black piece
                score -= value
                if square in CENTER_SQUARES:
                    score -= CENTER_BONUS
                if piece.piece_type == chess.PAWN:
                    score -= (
                        _pawn_advancement_bonus(square, piece.color)
                        * PAWN_ADVANCE_WEIGHT
                    )
                if piece.piece_type == chess.KNIGHT and square in KNIGHT_CENTER_SQUARES:
                    score -= KNIGHT_CENTER_BONUS

        # Mobility: average from both perspectives to avoid turn bias
        # Evaluate mobility for both sides
        white_moves = len(list(self._board.legal_moves))
        # Temporarily switch turn to get black's moves
        self._board.turn = not self._board.turn
        black_moves = len(list(self._board.legal_moves))
        self._board.turn = not self._board.turn  # switch back
        # Mobility advantage: white's moves minus black's moves
        mobility_diff = (white_moves - black_moves) * MOBILITY_BONUS
        score += mobility_diff

        # Check: if white is in check, that's bad for white
        if self._board.is_check():
            if self._board.turn == chess.WHITE:
                score -= CHECK_BONUS
            else:
                score += CHECK_BONUS

        return score
