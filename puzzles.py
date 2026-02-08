"""
Chess puzzles and scenarios with difficulty ratings, completion/failure conditions,
and a comprehensive database.

Each puzzle has:
- A unique ID and display name
- A FEN position and description
- A category (checkmate, tactics, endgame, etc.)
- A difficulty rating (Elo-style) and label
- Solution moves (alternating: player, opponent, player, ...)
- An objective type (find_best_moves, checkmate_in_n, free_play, etc.)
- Completion and failure messages
- Optional progressive hints
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PuzzleCategory(str, Enum):
    """Puzzle categories for filtering and display."""

    CHECKMATE = "checkmate"
    TACTICS = "tactics"
    ENDGAME = "endgame"
    OPENING = "opening"
    DEFENSE = "defense"
    FREE_PLAY = "free_play"


class PuzzleDifficulty(str, Enum):
    """Difficulty labels tied to rating ranges."""

    BEGINNER = "Beginner"  # 600-1000
    INTERMEDIATE = "Intermediate"  # 1000-1400
    ADVANCED = "Advanced"  # 1400-1800
    EXPERT = "Expert"  # 1800+


class PuzzleObjective(str, Enum):
    """How puzzle completion is determined."""

    FIND_BEST_MOVES = "find_best_moves"  # Must play exact solution sequence
    CHECKMATE_IN_N = "checkmate_in_n"  # Must deliver checkmate within N moves
    FREE_PLAY = "free_play"  # No specific objective


def difficulty_label_for_rating(rating: int) -> PuzzleDifficulty:
    """Return the difficulty label for a given rating."""
    if rating < 1000:
        return PuzzleDifficulty.BEGINNER
    elif rating < 1400:
        return PuzzleDifficulty.INTERMEDIATE
    elif rating < 1800:
        return PuzzleDifficulty.ADVANCED
    else:
        return PuzzleDifficulty.EXPERT


@dataclass(frozen=True)
class Puzzle:
    """A chess puzzle with completion/failure conditions and metadata."""

    id: str
    name: str
    fen: str
    description: str
    category: PuzzleCategory
    difficulty_rating: int  # Elo-style rating (600-2800)
    objective: PuzzleObjective
    solution_uci: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    clock_enabled: bool = False
    completion_message: str = "Puzzle solved! Well done."
    failure_message: str = "Not the best move. Try again!"

    @property
    def difficulty_label(self) -> PuzzleDifficulty:
        return difficulty_label_for_rating(self.difficulty_rating)

    @property
    def player_moves(self) -> list[str]:
        """Return only the player's moves from the solution (indices 0, 2, 4, ...)."""
        return self.solution_uci[::2]

    @property
    def opponent_moves(self) -> list[str]:
        """Return only the opponent's responses from the solution (indices 1, 3, 5, ...)."""
        return self.solution_uci[1::2]

    @property
    def num_player_moves(self) -> int:
        """Number of moves the player needs to find."""
        return len(self.player_moves)

    def is_player_move_correct(self, move_index: int, uci_move: str) -> bool:
        """Check if the player's Nth move (0-indexed) matches the solution.

        For FIND_BEST_MOVES and CHECKMATE_IN_N objectives, the move must match
        the solution exactly. For FREE_PLAY, any legal move is accepted.

        Solution moves may contain pipe-separated alternatives (e.g.
        ``"e7e8q|e7e8r"``) — the player's move is accepted if it matches
        *any* of the alternatives.
        """
        if self.objective == PuzzleObjective.FREE_PLAY:
            return True
        player_moves = self.player_moves
        if move_index < 0 or move_index >= len(player_moves):
            return False
        accepted = player_moves[move_index].split("|")
        return uci_move in accepted

    def get_opponent_response(self, move_index: int) -> str | None:
        """Get the opponent's automatic response after the player's Nth move.

        Returns None if there is no opponent response (end of sequence).
        """
        opponent_moves = self.opponent_moves
        if move_index < 0 or move_index >= len(opponent_moves):
            return None
        return opponent_moves[move_index]

    def is_complete_after_player_move(self, move_index: int) -> bool:
        """Check if the puzzle is complete after the player makes their Nth move.

        The puzzle is complete when the player has made all required moves.
        """
        if self.objective == PuzzleObjective.FREE_PLAY:
            return False  # Free play never "completes"
        return move_index >= self.num_player_moves - 1

    def get_hint_for_move(self, move_index: int) -> str | None:
        """Return a progressive hint for the given move index."""
        if move_index < len(self.hints):
            return self.hints[move_index]
        return None


# ---------------------------------------------------------------------------
# Comprehensive puzzle database
# ---------------------------------------------------------------------------

PUZZLE_DATABASE: list[Puzzle] = [
    # ======================================================================
    # BEGINNER: Mate in 1 (600-1000)
    # ======================================================================
    Puzzle(
        id="mate1_fools",
        name="Fool's Mate",
        fen="rnbqkbnr/pppp1ppp/8/4p3/5PP1/8/PPPPP2P/RNBQKBNR b KQkq f3 0 2",
        description="Black delivers mate in 1. The shortest possible checkmate!",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=600,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["d8h4"],
        hints=["The queen can reach h4 with devastating effect."],
        completion_message="Fool's Mate! The fastest checkmate in chess.",
        failure_message="Look for a queen move that delivers immediate checkmate.",
    ),
    Puzzle(
        id="mate1_scholars",
        name="Scholar's Mate",
        fen="r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
        description="White delivers mate in 1 with the queen.",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=650,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["h5f7"],
        hints=["The f7 square is only defended by the king."],
        completion_message="Scholar's Mate! Qxf7# is devastating.",
        failure_message="Target the weak f7 pawn with your queen.",
    ),
    Puzzle(
        id="mate1_back_rank",
        name="Back Rank Mate",
        fen="6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
        description="White delivers a classic back rank checkmate.",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=700,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e1e8"],
        hints=["The black king is trapped behind its own pawns."],
        completion_message="Back rank mate! The pawns become a prison.",
        failure_message="Use your rook to invade the 8th rank.",
    ),
    Puzzle(
        id="mate1_queen_delivery",
        name="Queen Delivery",
        fen="6k1/5ppp/8/8/8/8/1Q3PPP/6K1 w - - 0 1",
        description="White delivers checkmate with the queen.",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=700,
        objective=PuzzleObjective.CHECKMATE_IN_N,
        solution_uci=["b2b8"],
        hints=["The queen can reach the 8th rank."],
        completion_message="Checkmate! The queen dominates the back rank.",
        failure_message="Find the queen move that gives checkmate.",
    ),
    Puzzle(
        id="mate1_rook_h_file",
        name="Knight-Assisted Rook Mate",
        fen="6k1/5pp1/6NR/8/8/8/5PP1/6K1 w - - 0 1",
        description="The knight supports the rook for a mating attack on h8.",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=750,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["h6h8"],
        hints=["The knight protects h8. Deliver the rook check!"],
        completion_message="Mate! The knight and rook coordinate beautifully.",
        failure_message="Your knight already covers h8. Use your rook!",
    ),
    Puzzle(
        id="mate1_bishop_queen",
        name="Bishop and Queen Mate",
        fen="r1bk3r/pppp1Qpp/2n5/2b1p3/2B1P3/8/PPPP1PPP/RNB1K2R w KQ - 0 1",
        description="White has a mating attack with queen and bishop.",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=800,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["f7f8"],
        hints=["The queen can deliver check on the 8th rank."],
        completion_message="Checkmate! The bishop and queen coordinate perfectly.",
        failure_message="Your queen can deliver the final blow on the 8th rank.",
    ),
    Puzzle(
        id="mate1_knight_smother",
        name="Smothered Mate",
        fen="6rk/6pp/8/4N3/8/8/8/6K1 w - - 0 1",
        description="The knight delivers a classic smothered mate. The king is boxed in!",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=850,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e5f7"],
        hints=["The king is trapped by its own pieces. Find the knight move!"],
        completion_message="Smothered mate! The king has no escape.",
        failure_message="The knight can deliver mate - the king is boxed in.",
    ),
    Puzzle(
        id="mate1_two_rooks",
        name="Two Rooks Mate",
        fen="6k1/R7/8/8/8/8/8/1R4K1 w - - 0 1",
        description="One rook cuts off the 7th rank. Deliver mate with the other!",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=750,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["b1b8"],
        hints=["One rook controls the 7th rank. The other delivers mate on the 8th."],
        completion_message="Ladder mate! The rooks work together beautifully.",
        failure_message="One rook already controls a rank. Use the other to checkmate.",
    ),
    Puzzle(
        id="mate1_king_rook",
        name="King and Rook Mate",
        fen="7k/8/6K1/8/8/8/8/R7 w - - 0 1",
        description="White uses king and rook to deliver checkmate.",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=800,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["a1a8"],
        hints=["Your king covers the escape squares. Deliver mate with the rook!"],
        completion_message="Checkmate with king and rook!",
        failure_message="Your king already covers g7 and h7. Use the rook to deliver mate on the 8th rank.",
    ),
    # ======================================================================
    # BEGINNER-INTERMEDIATE: Simple Tactics (800-1100)
    # ======================================================================
    Puzzle(
        id="tactic_knight_fork_royal",
        name="Royal Knight Fork",
        fen="r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
        description="Find the knight fork targeting king and queen.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=900,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["f3g5"],
        hints=["Your knight can attack two pieces at once."],
        completion_message="Knight fork! Attacking the king and rook.",
        failure_message="Look for a knight move that attacks multiple pieces.",
    ),
    Puzzle(
        id="tactic_pin_bishop",
        name="Pin and Win",
        fen="r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 4 4",
        description="Pin the knight to win material.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=950,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["c1g5"],
        hints=["A bishop can pin the knight to the queen."],
        completion_message="Pinned! The knight cannot move without losing the queen.",
        failure_message="Use your bishop to pin an enemy piece.",
    ),
    Puzzle(
        id="tactic_discovered_attack",
        name="Discovered Attack",
        fen="r1bqkb1r/pppp1ppp/2n2n2/4p1B1/2B1P3/5N2/PPPP1PPP/RN1QK2R w KQkq - 4 4",
        description="Move one piece to reveal an attack by another.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1000,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["f3e5"],
        hints=["Moving the knight reveals the bishop's power."],
        completion_message="Discovered attack! Two threats at once.",
        failure_message="Move a piece that reveals an attack from another piece behind it.",
    ),
    Puzzle(
        id="tactic_skewer_basic",
        name="Basic Skewer",
        fen="3rk3/8/8/8/8/8/8/R3K3 w - - 0 1",
        description="Use the rook to skewer the king and win the rook behind it.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=850,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["a1a8"],
        hints=["Check the king, and when it moves, win the piece behind it."],
        completion_message="Skewer! The king must move, and the rook falls.",
        failure_message="Deliver check along the 8th rank to skewer.",
    ),
    Puzzle(
        id="tactic_double_attack",
        name="Knight Attack",
        fen="r2qkb1r/ppp2ppp/2n1bn2/3pp3/4P3/2NP1N2/PPP2PPP/R1BQKB1R w KQkq - 0 5",
        description="Jump to a powerful square attacking multiple targets.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1000,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["f3g5"],
        hints=["Your knight can jump to a square attacking f7 and e6."],
        completion_message="Knight attacks! Multiple threats from one square.",
        failure_message="Find a knight move that attacks multiple enemy pieces.",
    ),
    Puzzle(
        id="tactic_removal_defender",
        name="Remove the Defender",
        fen="r2qk2r/ppp1bppp/2n1bn2/3pp3/3PP3/2N1BN2/PPP1BPPP/R2QK2R w KQkq - 0 1",
        description="Remove a key defender to create threats.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1100,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["d4e5"],
        hints=["Capture the piece that defends a critical square."],
        completion_message="Defender removed! The position collapses.",
        failure_message="Identify which piece is defending and remove it.",
    ),
    # ======================================================================
    # INTERMEDIATE: Mate in 2 (1000-1400)
    # ======================================================================
    Puzzle(
        id="mate2_double_rook",
        name="Double Rook Mate in 2",
        fen="5r1k/4R1pp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
        description="White delivers mate in 2 with double rooks on the back rank.",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=1050,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e7e8", "f8e8", "e1e8"],
        hints=["Exchange one rook to clear the way.", "Now deliver the final blow."],
        completion_message="Double rook mate in 2! Excellent technique.",
        failure_message="Think about exchanging rooks on the back rank.",
    ),
    Puzzle(
        id="mate2_ladder",
        name="Ladder Mate in 2",
        fen="6k1/8/8/8/8/8/8/RR4K1 w - - 0 1",
        description="Use two rooks to build a ladder mate. Cut off the king!",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=1100,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["a1a7", "g8f8", "b1b8"],
        hints=["Cut off the 7th rank first.", "Now deliver mate on the 8th rank."],
        completion_message="Ladder mate! The rooks march up the board.",
        failure_message="Use one rook to cut off a rank, then the other delivers mate.",
    ),
    Puzzle(
        id="mate2_bishop_rook",
        name="Bishop & Rook Coordination",
        fen="6k1/5pbp/6p1/8/8/6B1/5PPP/4R1K1 w - - 0 1",
        description="Coordinate the bishop and rook for a mating attack.",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=1150,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e1e8"],
        hints=["The bishop already controls key squares. Use the rook!"],
        completion_message="The bishop and rook coordinate for back rank pressure!",
        failure_message="Your bishop restricts the king. Use the rook to deliver the blow.",
    ),
    Puzzle(
        id="tactic_bishop_sacrifice",
        name="Bishop Sacrifice on f7",
        fen="r1b1k2r/ppppqppp/2n5/4N3/2B1P3/8/PPPP1PPP/R1BQK2R w KQkq - 0 1",
        description="Sacrifice the bishop on f7 to expose the king and win material.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1200,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["c4f7"],
        hints=["The f7 square is only protected by the queen. Sacrifice!"],
        completion_message="Brilliant sacrifice! The king is exposed.",
        failure_message="Target the weak f7 square with your bishop.",
    ),
    Puzzle(
        id="mate1_pawn_promo",
        name="Pawn Promotion Mate",
        fen="6k1/4Pppp/8/8/8/8/5PPP/6K1 w - - 0 1",
        description="Promote the pawn to deliver immediate checkmate!",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=900,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e7e8q|e7e8r"],
        hints=["Promote the pawn. What piece gives checkmate?"],
        completion_message="Promotion checkmate! Both queen and rook work here.",
        failure_message="Promote the pawn to the right piece for checkmate.",
    ),
    # ======================================================================
    # INTERMEDIATE: Tactical Combinations (1100-1400)
    # ======================================================================
    Puzzle(
        id="tactic_greek_gift",
        name="Greek Gift Sacrifice",
        fen="rnbq1rk1/ppp2ppp/4pn2/3p2B1/2PPP3/2N2N2/PP3PPP/R2QKB1R w KQ - 0 1",
        description="Develop the bishop to eye h7 for the classic Greek Gift sacrifice.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1300,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["f1d3"],
        hints=["The bishop needs to reach d3 to eye the h7 pawn."],
        completion_message="Setting up the Greek Gift! The bishop eyes h7.",
        failure_message="Develop your bishop aggressively toward the kingside via d3.",
    ),
    Puzzle(
        id="tactic_windmill",
        name="Windmill Pattern",
        fen="r4rk1/1b2bppp/p1n1pn2/1pB5/3NP3/2N5/PPP1BPPP/R3K2R w KQ - 0 1",
        description="Set up a devastating windmill pattern.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1350,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["d4e6"],
        hints=["The knight can jump to a powerful square."],
        completion_message="Powerful centralization! The knight dominates.",
        failure_message="Centralize your knight with a powerful jump.",
    ),
    Puzzle(
        id="tactic_deflection",
        name="Deflection",
        fen="r1b2rk1/ppppqppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQ1RK1 w - - 0 1",
        description="Deflect a key defender to win material.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1250,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["c4f7"],
        hints=["Attack the f7 pawn to lure the king or queen."],
        completion_message="Deflection! The defender is drawn away.",
        failure_message="Target a weak point that forces a defender to move.",
    ),
    Puzzle(
        id="tactic_decoy",
        name="Decoy Sacrifice",
        fen="r3k2r/ppp2ppp/2n1bn2/2bpp3/4P3/2NPBN2/PPP2PPP/R2QKB1R w KQkq - 0 1",
        description="Lure an enemy piece to a bad square.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1300,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e4d5"],
        hints=["Open the center with a pawn exchange."],
        completion_message="The center opens favorably!",
        failure_message="Consider opening the center to activate your pieces.",
    ),
    Puzzle(
        id="tactic_overloaded_piece",
        name="Overloaded Piece",
        fen="r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 1",
        description="Exploit a piece that has too many duties.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1350,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["c3d5"],
        hints=["A knight can jump to the center and attack multiple pieces."],
        completion_message="The overloaded piece crumbles under pressure!",
        failure_message="Find a piece that is defending too many things at once.",
    ),
    Puzzle(
        id="tactic_zwischenzug",
        name="Zwischenzug (In-Between Move)",
        fen="r1bqk2r/ppp2ppp/2n2n2/3pp3/1bPP4/2N1PN2/PP3PPP/R1BQKB1R w KQkq - 0 1",
        description="Play a surprising in-between move before recapturing.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1400,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["c4d5"],
        hints=["Don't recapture immediately - find a stronger intermediate move."],
        completion_message="Zwischenzug! The in-between move is devastating.",
        failure_message="Before making the obvious recapture, check if there's a stronger move.",
    ),
    # ======================================================================
    # INTERMEDIATE-ADVANCED: Endgame Puzzles (1200-1600)
    # ======================================================================
    Puzzle(
        id="endgame_kp_opposition",
        name="King & Pawn: Opposition",
        fen="8/4k3/8/4P3/4K3/8/8/8 w - - 0 1",
        description="Use the opposition to promote your pawn.",
        category=PuzzleCategory.ENDGAME,
        difficulty_rating=1200,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e4f5"],
        hints=["Take the opposition by stepping to the side."],
        completion_message="Opposition gained! The pawn will promote.",
        failure_message="In king and pawn endgames, the opposition is key.",
    ),
    Puzzle(
        id="endgame_rook_pawn",
        name="Rook vs Pawn Endgame",
        fen="8/8/4k3/8/4P3/4K3/8/4R3 w - - 0 1",
        description="Use the rook to support the pawn's advance.",
        category=PuzzleCategory.ENDGAME,
        difficulty_rating=1100,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e3f4"],
        hints=["Advance your king to support the pawn."],
        completion_message="Correct technique! The king leads the charge.",
        failure_message="The king should advance to support the pawn.",
    ),
    Puzzle(
        id="endgame_queen_vs_rook",
        name="Queen vs Rook",
        fen="4k3/8/4r3/8/8/8/8/4Q1K1 w - - 0 1",
        description="Win the rook using the queen's power.",
        category=PuzzleCategory.ENDGAME,
        difficulty_rating=1300,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e1a5"],
        hints=["The queen can dominate the rook from a distance."],
        completion_message="The queen wins material!",
        failure_message="Use the queen to create a fork or pin against the rook.",
    ),
    Puzzle(
        id="endgame_lucena",
        name="Lucena Position",
        fen="3K4/3P1k2/8/8/8/8/8/4R3 w - - 0 1",
        description="The most important rook endgame: build the bridge!",
        category=PuzzleCategory.ENDGAME,
        difficulty_rating=1400,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e1e4"],
        hints=["Building a bridge - use your rook to block checks."],
        completion_message="The Lucena position! The bridge technique wins.",
        failure_message="In the Lucena position, the rook must cut off the enemy king.",
    ),
    Puzzle(
        id="endgame_philidor",
        name="Philidor Position (Defense)",
        fen="8/8/8/3k4/8/3K1R2/3P4/3r4 w - - 0 1",
        description="Use the Philidor defensive technique.",
        category=PuzzleCategory.DEFENSE,
        difficulty_rating=1350,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["f3f6"],
        hints=["Keep the rook on the 6th rank to hold the position."],
        completion_message="Philidor defense! The rook on the 6th rank holds.",
        failure_message="The rook should stay on the 3rd/6th rank for the Philidor defense.",
    ),
    Puzzle(
        id="endgame_two_bishops",
        name="Two Bishops Mate",
        fen="8/8/8/8/8/1k6/8/1K2BB2 w - - 0 1",
        description="Checkmate with two bishops. Drive the king to the corner.",
        category=PuzzleCategory.ENDGAME,
        difficulty_rating=1500,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["f1d3"],
        hints=["The bishops must work together to restrict the king."],
        completion_message="The bishops coordinate to restrict the king!",
        failure_message="Use both bishops to cut off the enemy king's escape squares.",
    ),
    Puzzle(
        id="endgame_pawn_race",
        name="Pawn Race",
        fen="8/p7/8/8/8/8/7P/8 w - - 0 1",
        description="Can your pawn outrun the opponent's? Calculate precisely!",
        category=PuzzleCategory.ENDGAME,
        difficulty_rating=1050,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["h2h4"],
        hints=["Push your pawn as fast as possible!"],
        completion_message="Your pawn promotes first!",
        failure_message="Count the squares - which pawn promotes first?",
    ),
    # ======================================================================
    # ADVANCED: Complex Tactics (1400-1800)
    # ======================================================================
    Puzzle(
        id="tactic_sacrifice_clearance",
        name="Clearance Sacrifice",
        fen="r1bq1rk1/ppp1nppp/3p4/3Pp3/2P1N3/5N2/PP2PPPP/R1BQKB1R w KQ - 0 1",
        description="Sacrifice a piece to clear a line for another.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1500,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e4f6"],
        hints=["A knight sacrifice opens critical lines."],
        completion_message="Clearance sacrifice! The lines open dramatically.",
        failure_message="Sometimes you must sacrifice to open lines for your other pieces.",
    ),
    Puzzle(
        id="tactic_interference",
        name="Interference",
        fen="r2q1rk1/pp2ppbp/2np1np1/2pP4/4P3/2N2N2/PPP1BPPP/R1BQ1RK1 w - - 0 1",
        description="Place a piece to interfere with the opponent's coordination.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1550,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["d5c6"],
        hints=["A pawn advance can disrupt the enemy pieces."],
        completion_message="Interference! The opponent's pieces are disconnected.",
        failure_message="Disrupt the coordination between enemy pieces.",
    ),
    Puzzle(
        id="tactic_x_ray",
        name="X-Ray Attack",
        fen="r3k2r/pppq1ppp/2n1bn2/3pp3/3PP3/2N1BN2/PPP1BPPP/R2QK2R w KQkq - 0 1",
        description="Attack through one piece to threaten another behind it.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1450,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["d4e5"],
        hints=["Open the center to create threats."],
        completion_message="X-ray! Your piece attacks through the enemy.",
        failure_message="Look for attacks that work through enemy pieces.",
    ),
    Puzzle(
        id="tactic_trapped_piece",
        name="Trapped Piece",
        fen="r1bqk2r/pppp1ppp/2n2n2/4p3/1bB1P3/2NP4/PPP2PPP/R1BQK1NR w KQkq - 0 1",
        description="Trap the enemy bishop with precise play.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1400,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["a2a3"],
        hints=["The bishop on b4 has limited retreat squares."],
        completion_message="Trapped! The bishop has no safe square.",
        failure_message="Look for a way to restrict the opponent's bishop.",
    ),
    Puzzle(
        id="tactic_desperado",
        name="Desperado",
        fen="r1bqk2r/pppp1ppp/2n2n2/2b1N3/2B1P3/8/PPPP1PPP/RNBQK2R w KQkq - 0 1",
        description="Your piece is lost anyway - get the most for it!",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1500,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e5f7"],
        hints=["If a piece is doomed, make it count!"],
        completion_message="Desperado! Maximum damage before the piece falls.",
        failure_message="When a piece is doomed, capture the most valuable target.",
    ),
    Puzzle(
        id="tactic_attraction",
        name="Attraction Sacrifice",
        fen="r1b1k2r/ppppqppp/2n2n2/2b1p3/2BPP3/2N2N2/PPP2PPP/R1BQK2R w KQkq - 0 1",
        description="Sacrifice to attract the king to a dangerous square.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1550,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["d4e5"],
        hints=["Open the center with a pawn push."],
        completion_message="The center opens and the king is exposed!",
        failure_message="Sometimes opening the center exposes the enemy king.",
    ),
    Puzzle(
        id="tactic_back_rank_combo",
        name="Back Rank Combination",
        fen="2r3k1/5ppp/8/8/8/8/5PPP/1R2R1K1 w - - 0 1",
        description="Use a combination to exploit the weak back rank.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1450,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e1e8", "c8e8", "b1e1"],
        hints=[
            "Sacrifice the rook to clear the way.",
            "The second rook finishes the job.",
        ],
        completion_message="Back rank combination! Rook sacrifice into mate.",
        failure_message="Both rooks can work together to exploit the back rank.",
    ),
    # ======================================================================
    # ADVANCED: Defensive Puzzles (1400-1700)
    # ======================================================================
    Puzzle(
        id="defense_stalemate_trick",
        name="Stalemate Trick",
        fen="5k2/5P2/5K2/8/8/8/8/6q1 b - - 0 1",
        description="Black is losing but can find stalemate!",
        category=PuzzleCategory.DEFENSE,
        difficulty_rating=1400,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["g1f2"],
        hints=["If you can't win, try not to lose! Think stalemate."],
        completion_message="Stalemate trick! A draw snatched from the jaws of defeat.",
        failure_message="When you're losing, look for stalemate possibilities.",
    ),
    Puzzle(
        id="defense_perpetual_check",
        name="Perpetual Check",
        fen="7k/1r4p1/8/8/8/2q5/6PP/4Q1K1 w - - 0 1",
        description="White is down a whole rook but can save the game with perpetual check!",
        category=PuzzleCategory.DEFENSE,
        difficulty_rating=1350,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e1e8", "h8h7", "e8h5", "h7g8", "h5e8"],
        hints=[
            "Give check on the back rank with your queen.",
            "Keep checking! The queen can bounce between e8 and h5.",
            "One more check completes the perpetual cycle.",
        ],
        completion_message="Perpetual check! The queen bounces between e8 and h5, "
        "and the king can never escape. A draw snatched from the jaws of defeat!",
        failure_message="Look for a queen check that starts a repeating cycle of checks.",
    ),
    Puzzle(
        id="defense_fortress",
        name="Fortress Defense",
        fen="8/8/1pk5/8/1PK5/1B6/8/8 w - - 0 1",
        description="Build an impenetrable fortress to hold the draw.",
        category=PuzzleCategory.DEFENSE,
        difficulty_rating=1500,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["b3a4"],
        hints=["Place your pieces to create an unbreakable defensive formation."],
        completion_message="Fortress! The opponent cannot make progress.",
        failure_message="Position your pieces to block the opponent's plan.",
    ),
    # ======================================================================
    # EXPERT: Multi-Move Combinations (1800+)
    # ======================================================================
    Puzzle(
        id="mate3_sacrifice_cascade",
        name="Sacrifice Cascade (Mate in 3)",
        fen="r1bq1rk1/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQ - 0 1",
        description="A cascade of sacrifices leads to forced mate.",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=1800,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["c4f7"],
        hints=[
            "A bishop sacrifice on f7 opens the king's defenses.",
        ],
        completion_message="Brilliant cascade! Multiple sacrifices leading to mate.",
        failure_message="Look for a sacrifice that tears open the king's position.",
    ),
    Puzzle(
        id="expert_queen_sac_mate",
        name="Queen Sacrifice for Mate",
        fen="r1b2rk1/2q1bppp/p1n1pn2/1pBpP3/3N4/2N1B3/PPP1QPPP/R4RK1 w - - 0 1",
        description="A stunning queen sacrifice leads to forced checkmate.",
        category=PuzzleCategory.CHECKMATE,
        difficulty_rating=1900,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["d4e6"],
        hints=["The knight on d4 can jump to a devastating square."],
        completion_message="Spectacular queen sacrifice into forced mate!",
        failure_message="Look for a knight move that creates an overwhelming attack.",
    ),
    Puzzle(
        id="expert_positional_sac",
        name="Positional Exchange Sacrifice",
        fen="r1bq1rk1/pp3ppp/2nbpn2/3p4/2PP4/2N1PN2/PPB2PPP/R1BQ1RK1 w - - 0 1",
        description="A positional exchange sacrifice for long-term compensation.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1850,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["c4d5"],
        hints=["Open the center to activate your pieces."],
        completion_message="Positional mastery! Long-term compensation is overwhelming.",
        failure_message="Think about opening lines for your pieces.",
    ),
    Puzzle(
        id="expert_rook_endgame",
        name="Complex Rook Endgame",
        fen="8/5pk1/R5pp/1r6/5PP1/8/8/6K1 w - - 0 1",
        description="Navigate a tricky rook endgame with precise calculation.",
        category=PuzzleCategory.ENDGAME,
        difficulty_rating=1800,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["f4f5"],
        hints=["Advance the pawn to create a passed pawn."],
        completion_message="Precise endgame play! The passed pawn decides.",
        failure_message="Create a passed pawn to put pressure on the opponent.",
    ),
    Puzzle(
        id="expert_minor_piece_endgame",
        name="Bishop vs Knight Endgame",
        fen="8/5pk1/6p1/3B4/2n5/8/5PPP/6K1 w - - 0 1",
        description="Exploit the bishop's advantage in an open position.",
        category=PuzzleCategory.ENDGAME,
        difficulty_rating=1750,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["d5e4"],
        hints=["The bishop is stronger than the knight in open positions."],
        completion_message="The bishop dominates the knight in this open position!",
        failure_message="Use your bishop's long-range power in the open position.",
    ),
    Puzzle(
        id="expert_zugzwang",
        name="Zugzwang",
        fen="8/6k1/6p1/6P1/8/5K2/8/8 w - - 0 1",
        description="Seize the opposition to create zugzwang. The opponent's every move loses.",
        category=PuzzleCategory.ENDGAME,
        difficulty_rating=1800,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["f3f4"],
        hints=["Take the opposition by advancing your king."],
        completion_message="Zugzwang! The opponent must weaken their position.",
        failure_message="Think about the opposition - advance your king to mirror the opponent's.",
    ),
    Puzzle(
        id="expert_domination",
        name="Piece Domination",
        fen="r2qk2r/ppp1bppp/2n1bn2/3pN3/3P4/2N1B3/PPP2PPP/R2QKB1R w KQkq - 0 1",
        description="Dominate the center with powerful piece play.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1900,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["e5c6"],
        hints=["The knight on e5 is powerful - use it."],
        completion_message="Total domination! Your pieces control the board.",
        failure_message="Use your centralized pieces to exert maximum pressure.",
    ),
    Puzzle(
        id="expert_prophylaxis",
        name="Prophylaxis",
        fen="r1bq1rk1/pp3ppp/2n1pn2/2ppP3/3P4/2PB1N2/PP3PPP/R1BQ1RK1 w - - 0 1",
        description="Prevent the opponent's plan before executing your own.",
        category=PuzzleCategory.TACTICS,
        difficulty_rating=1950,
        objective=PuzzleObjective.FIND_BEST_MOVES,
        solution_uci=["d3c2"],
        hints=[
            "Before attacking, make sure your opponent's counterplay is neutralized."
        ],
        completion_message="Prophylactic thinking! Stopping the opponent's plan first.",
        failure_message="Think about what your opponent wants to do, and prevent it.",
    ),
    # ======================================================================
    # Free Play / Special
    # ======================================================================
    Puzzle(
        id="free_starting_position",
        name="Starting Position",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        description="Standard starting position. Play freely!",
        category=PuzzleCategory.FREE_PLAY,
        difficulty_rating=0,
        objective=PuzzleObjective.FREE_PLAY,
        solution_uci=[],
        clock_enabled=True,
        completion_message="",
        failure_message="",
    ),
    Puzzle(
        id="free_italian_game",
        name="Italian Game Setup",
        fen="r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
        description="Play from the Italian Game position. One of the oldest openings!",
        category=PuzzleCategory.OPENING,
        difficulty_rating=0,
        objective=PuzzleObjective.FREE_PLAY,
        solution_uci=[],
        clock_enabled=True,
        completion_message="",
        failure_message="",
    ),
    Puzzle(
        id="free_sicilian_najdorf",
        name="Sicilian Najdorf",
        fen="rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6",
        description="Play from the sharpest Sicilian: the Najdorf variation.",
        category=PuzzleCategory.OPENING,
        difficulty_rating=0,
        objective=PuzzleObjective.FREE_PLAY,
        solution_uci=[],
        clock_enabled=True,
        completion_message="",
        failure_message="",
    ),
    Puzzle(
        id="free_queens_gambit",
        name="Queen's Gambit Declined",
        fen="rnbqkb1r/ppp1pppp/5n2/3p4/2PP4/8/PP2PPPP/RNBQKBNR w KQkq - 2 3",
        description="Play from the Queen's Gambit Declined position.",
        category=PuzzleCategory.OPENING,
        difficulty_rating=0,
        objective=PuzzleObjective.FREE_PLAY,
        solution_uci=[],
        clock_enabled=True,
        completion_message="",
        failure_message="",
    ),
    Puzzle(
        id="free_ruy_lopez",
        name="Ruy Lopez",
        fen="r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
        description="Play from the Ruy Lopez (Spanish Opening).",
        category=PuzzleCategory.OPENING,
        difficulty_rating=0,
        objective=PuzzleObjective.FREE_PLAY,
        solution_uci=[],
        clock_enabled=True,
        completion_message="",
        failure_message="",
    ),
    Puzzle(
        id="free_endgame_krk",
        name="King & Rook vs King",
        fen="8/8/8/4k3/8/8/8/4RK2 w - - 0 1",
        description="Practice the fundamental King & Rook vs King checkmate.",
        category=PuzzleCategory.ENDGAME,
        difficulty_rating=0,
        objective=PuzzleObjective.FREE_PLAY,
        solution_uci=[],
        hints=["Drive the king to the edge of the board."],
        completion_message="",
        failure_message="",
    ),
    Puzzle(
        id="free_endgame_kqk",
        name="King & Queen vs King",
        fen="8/8/8/4k3/8/8/8/4QK2 w - - 0 1",
        description="Practice the King & Queen vs King checkmate.",
        category=PuzzleCategory.ENDGAME,
        difficulty_rating=0,
        objective=PuzzleObjective.FREE_PLAY,
        solution_uci=[],
        hints=["Be careful not to stalemate!"],
        completion_message="",
        failure_message="",
    ),
]

# Build an index by puzzle ID for fast lookup
PUZZLE_BY_ID: dict[str, Puzzle] = {p.id: p for p in PUZZLE_DATABASE}


def get_puzzles_by_category(category: PuzzleCategory) -> list[Puzzle]:
    """Return all puzzles in a given category, sorted by difficulty."""
    return sorted(
        [p for p in PUZZLE_DATABASE if p.category == category],
        key=lambda p: p.difficulty_rating,
    )


def get_puzzles_by_difficulty(
    min_rating: int = 0, max_rating: int = 3000
) -> list[Puzzle]:
    """Return puzzles within a difficulty range, sorted by rating."""
    return sorted(
        [p for p in PUZZLE_DATABASE if min_rating <= p.difficulty_rating <= max_rating],
        key=lambda p: p.difficulty_rating,
    )


def get_rated_puzzles() -> list[Puzzle]:
    """Return only puzzles that have a non-zero difficulty rating (excluding free play)."""
    return sorted(
        [p for p in PUZZLE_DATABASE if p.difficulty_rating > 0],
        key=lambda p: p.difficulty_rating,
    )


def get_free_play_puzzles() -> list[Puzzle]:
    """Return puzzles intended for free play (no specific objective)."""
    return [p for p in PUZZLE_DATABASE if p.objective == PuzzleObjective.FREE_PLAY]


# ---------------------------------------------------------------------------
# Backwards-compatible PUZZLES list for legacy code
# Each entry is (name, fen, description, clock_enabled)
# ---------------------------------------------------------------------------
PUZZLES: list[tuple[str, str, str, bool]] = [
    (p.name, p.fen, p.description, p.clock_enabled) for p in PUZZLE_DATABASE
]
