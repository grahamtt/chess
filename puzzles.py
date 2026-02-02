"""
Chess puzzles and scenarios: name, FEN, description, and whether the clock is enabled.
Most puzzles have the clock disabled so you can think without time pressure.
"""

# (display_name, FEN, description, clock_enabled)
PUZZLES = [
    # Classic checkmates
    (
        "Fool's Mate (Black to play)",
        "rnbqkbnr/pppp1ppp/8/4p3/5PP1/8/PPPPP2P/RNBQKBNR b KQkq f3 0 2",
        "Black delivers mate in 1 with Qh4#.",
        False,
    ),
    (
        "Scholar's Mate (White to play)",
        "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
        "White delivers mate in 1 with Qxf7#.",
        False,
    ),
    (
        "Back Rank Mate (White to play)",
        "5rk1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
        "White plays Re8#. Classic back-rank mate.",
        False,
    ),
    (
        "Smothered Mate (White to play)",
        "5r1k/5p1p/6p1/8/8/8/5PPP/4N1K1 w - - 0 1",
        "White plays Nf7#. Knight smothers the king.",
        False,
    ),
    (
        "Anastasia's Mate (White to play)",
        "r1bqk2r/ppp2ppp/2n2n2/2bNp3/2B1P3/8/PPP2PPP/R1BQK2R w KQkq - 0 1",
        "Tactical theme: knight and rook combine.",
        False,
    ),
    # Mate in 2
    (
        "Mate in 2 (White)",
        "5r1k/4R1pp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
        "White plays Re8+ then Rxe8#. Double rook back-rank mate in 2.",
        False,
    ),
    (
        "Mate in 2 (Black)",
        "4r1k1/3qR1pp/8/8/8/8/5PPP/4R1K1 b - - 0 1",
        "Black plays Re1+ then Qxe1#. Rook and queen back-rank mate in 2.",
        False,
    ),
    # Endgames
    (
        "King and Pawn (White to play)",
        "8/4k3/8/4P3/4K3/8/8/8 w - - 0 1",
        "Classic king and pawn endgame. White to play and win.",
        False,
    ),
    (
        "Rook vs Pawn",
        "8/8/4k3/8/4P3/4K3/8/4R3 w - - 0 1",
        "White has an extra rook; technique to win.",
        False,
    ),
    (
        "Queen vs Rook (White to play)",
        "4k3/8/4r3/8/8/8/8/4Q1K1 w - - 0 1",
        "Queen vs rook endgame.",
        False,
    ),
    # Tactics
    (
        "Knight Fork (White to play)",
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
        "Look for a knight fork or tactical shot.",
        False,
    ),
    (
        "Pin and Win (White to play)",
        "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 4 4",
        "Pin the knight; win material.",
        False,
    ),
    (
        "Double Attack (White to play)",
        "r2qkb1r/ppp2ppp/2n1bn2/3pp3/4P3/2NP1N2/PPP2PPP/R1BQKB1R w KQkq - 0 5",
        "Create a double attack.",
        False,
    ),
    # Famous / composed
    (
        "Lolli's Mate pattern",
        "6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
        "Rook and king coordinate for back-rank mate.",
        False,
    ),
    (
        "Starting position",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "Standard starting position.",
        True,  # Clock on for a full game from the start
    ),
]
