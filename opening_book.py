"""
Opening book database and explorer.
Provides opening names and common move suggestions based on position.
"""

import chess


# Common opening moves database
# Format: (move_sequence_uci, opening_name, description)
OPENING_DATABASE = [
    # King's Pawn Openings
    (["e2e4"], "King's Pawn Opening", "The most popular opening move"),
    (["e2e4", "e7e5"], "Open Game", "Classical response to e4"),
    (["e2e4", "e7e5", "g1f3"], "King's Knight Opening", "Developing the knight"),
    (["e2e4", "e7e5", "g1f3", "b8c6"], "Italian Game", "Classical development"),
    (["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"], "Italian Game", "Bishop to c4"),
    (["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"], "Ruy Lopez", "Spanish Opening"),
    (["e2e4", "e7e5", "f1c4"], "Bishop's Opening", "Direct bishop development"),
    (["e2e4", "e7e5", "f2f4"], "King's Gambit", "Aggressive gambit"),
    (["e2e4", "e7e5", "d2d4"], "Center Game", "Immediate central break"),
    (["e2e4", "e7e5", "b1c3"], "Vienna Game", "Knight development"),
    
    # Sicilian Defense
    (["e2e4", "c7c5"], "Sicilian Defense", "Most popular response to e4"),
    (["e2e4", "c7c5", "g1f3"], "Sicilian Defense", "Open Sicilian"),
    (["e2e4", "c7c5", "g1f3", "d7d6"], "Sicilian Defense", "Dragon Variation"),
    (["e2e4", "c7c5", "g1f3", "b8c6"], "Sicilian Defense", "Classical Variation"),
    (["e2e4", "c7c5", "g1f3", "e7e6"], "Sicilian Defense", "Taimanov Variation"),
    
    # French Defense
    (["e2e4", "e7e6"], "French Defense", "Solid defensive opening"),
    (["e2e4", "e7e6", "d2d4"], "French Defense", "Main line"),
    (["e2e4", "e7e6", "d2d4", "d7d5"], "French Defense", "Classical French"),
    
    # Caro-Kann Defense
    (["e2e4", "c7c6"], "Caro-Kann Defense", "Solid and reliable"),
    (["e2e4", "c7c6", "d2d4"], "Caro-Kann Defense", "Main line"),
    (["e2e4", "c7c6", "d2d4", "d7d5"], "Caro-Kann Defense", "Classical Variation"),
    
    # Queen's Pawn Openings
    (["d2d4"], "Queen's Pawn Opening", "Second most popular opening"),
    (["d2d4", "d7d5"], "Closed Game", "Classical response"),
    (["d2d4", "d7d5", "c2c4"], "Queen's Gambit", "Most popular d4 opening"),
    (["d2d4", "d7d5", "c2c4", "d5c4"], "Queen's Gambit Accepted", "Accepting the gambit"),
    (["d2d4", "d7d5", "c2c4", "e7e6"], "Queen's Gambit Declined", "Declining the gambit"),
    (["d2d4", "g8f6"], "Indian Defense", "Hypermodern response"),
    (["d2d4", "g8f6", "c2c4"], "Indian Defense", "Main line"),
    (["d2d4", "g8f6", "c2c4", "e7e6"], "Nimzo-Indian Defense", "Classical Indian"),
    (["d2d4", "g8f6", "c2c4", "g7g6"], "King's Indian Defense", "Fianchetto variation"),
    
    # English Opening
    (["c2c4"], "English Opening", "Flank opening"),
    (["c2c4", "e7e5"], "English Opening", "Reversed Sicilian"),
    
    # Reti Opening
    (["g1f3"], "Reti Opening", "Hypermodern opening"),
    
    # Dutch Defense
    (["d2d4", "f7f5"], "Dutch Defense", "Aggressive response to d4"),
    
    # Pirc Defense
    (["e2e4", "d7d6"], "Pirc Defense", "Hypermodern defense"),
    (["e2e4", "d7d6", "d2d4"], "Pirc Defense", "Main line"),
    
    # Alekhine Defense
    (["e2e4", "g8f6"], "Alekhine Defense", "Provocative defense"),
    
    # Scandinavian Defense
    (["e2e4", "d7d5"], "Scandinavian Defense", "Immediate counterattack"),
]


def _get_move_sequence(board: chess.Board) -> list[str]:
    """Get the sequence of moves played so far as UCI strings."""
    moves = []
    temp_board = chess.Board()
    for move in board.move_stack:
        moves.append(move.uci())
        temp_board.push(move)
    return moves


def get_opening_name(board: chess.Board) -> tuple[str | None, str | None]:
    """
    Get the opening name for the current position.
    
    Returns:
        Tuple of (opening_name, description) or (None, None) if no match found.
    """
    move_sequence = _get_move_sequence(board)
    
    if not move_sequence:
        return None, None
    
    # Find the longest matching opening sequence
    best_match = None
    best_length = 0
    
    for opening_moves, name, description in OPENING_DATABASE:
        if len(opening_moves) <= len(move_sequence):
            if move_sequence[:len(opening_moves)] == opening_moves:
                if len(opening_moves) > best_length:
                    best_length = len(opening_moves)
                    best_match = (name, description)
    
    if best_match:
        return best_match
    
    return None, None


def get_common_moves(board: chess.Board) -> list[tuple[chess.Move, str, int]]:
    """
    Get common moves from the current position based on opening theory.
    
    Returns:
        List of (move, san_notation, frequency_score) tuples, sorted by frequency.
        Frequency score is a heuristic (1-10) based on how common the move is.
    """
    if board.is_game_over():
        return []
    
    move_sequence = _get_move_sequence(board)
    legal_moves = list(board.legal_moves)
    
    if not legal_moves:
        return []
    
    # Find openings that continue from this position
    continuation_moves: dict[str, int] = {}
    
    for opening_moves, _, _ in OPENING_DATABASE:
        if len(opening_moves) > len(move_sequence):
            if move_sequence == opening_moves[:len(move_sequence)]:
                next_move_uci = opening_moves[len(move_sequence)]
                continuation_moves[next_move_uci] = continuation_moves.get(next_move_uci, 0) + 1
    
    # Score moves based on how often they appear in continuations
    scored_moves = []
    for move in legal_moves:
        move_uci = move.uci()
        frequency = continuation_moves.get(move_uci, 0)
        
        # Convert frequency to score (1-10 scale)
        # Moves that appear in multiple openings get higher scores
        if frequency >= 3:
            score = 10
        elif frequency == 2:
            score = 7
        elif frequency == 1:
            score = 5
        else:
            # Moves not in opening book get a base score
            # Prioritize developing moves, central control, etc.
            score = _heuristic_move_score(board, move)
        
        try:
            san = board.san(move)
        except (AssertionError, ValueError):
            san = move.uci()
        
        scored_moves.append((move, san, score))
    
    # Sort by score (descending)
    scored_moves.sort(key=lambda x: x[2], reverse=True)
    
    return scored_moves


def _heuristic_move_score(board: chess.Board, move: chess.Move) -> int:
    """
    Score a move heuristically when it's not in the opening book.
    Higher scores for developing moves, central control, etc.
    """
    score = 1  # Base score
    
    # Check if it's a developing move (knight or bishop from starting square)
    from_sq = move.from_square
    piece = board.piece_at(from_sq)
    
    if piece:
        # Knight development
        if piece.piece_type == chess.KNIGHT:
            from_rank = chess.square_rank(from_sq)
            if (piece.color == chess.WHITE and from_rank == 0) or \
               (piece.color == chess.BLACK and from_rank == 7):
                score += 2
        
        # Bishop development
        if piece.piece_type == chess.BISHOP:
            from_rank = chess.square_rank(from_sq)
            if (piece.color == chess.WHITE and from_rank == 0) or \
               (piece.color == chess.BLACK and from_rank == 7):
                score += 2
        
        # Central pawn moves
        if piece.piece_type == chess.PAWN:
            to_file = chess.square_file(move.to_square)
            if to_file in [3, 4]:  # d or e file
                score += 1
    
    # Central square control
    to_sq = move.to_square
    center_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
    if to_sq in center_squares:
        score += 1
    
    return min(score, 5)  # Cap at 5 for non-book moves
