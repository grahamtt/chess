"""Tests for puzzles module."""

import pytest
from puzzles import PUZZLES


def test_puzzles_structure():
    """Test that all puzzles have the correct structure."""
    assert len(PUZZLES) > 0
    for puzzle in PUZZLES:
        assert len(puzzle) == 4
        name, fen, description, clock_enabled = puzzle
        assert isinstance(name, str)
        assert isinstance(fen, str)
        assert isinstance(description, str)
        assert isinstance(clock_enabled, bool)


def test_puzzles_have_valid_fen():
    """Test that all puzzles have valid FEN strings."""
    import chess
    
    for puzzle in PUZZLES:
        name, fen, _, _ = puzzle
        try:
            board = chess.Board(fen)
            assert board is not None
        except ValueError as e:
            pytest.fail(f"Invalid FEN in puzzle '{name}': {fen} - {e}")


def test_puzzles_clock_settings():
    """Test that puzzles have appropriate clock settings."""
    # Most puzzles should have clock disabled
    clock_disabled_count = sum(1 for _, _, _, clock_enabled in PUZZLES if not clock_enabled)
    assert clock_disabled_count > 0
    
    # At least one puzzle should have clock enabled (starting position)
    clock_enabled_count = sum(1 for _, _, _, clock_enabled in PUZZLES if clock_enabled)
    assert clock_enabled_count >= 1


def test_puzzles_unique_names():
    """Test that puzzle names are unique."""
    names = [name for name, _, _, _ in PUZZLES]
    assert len(names) == len(set(names)), "Puzzle names should be unique"


def test_puzzles_non_empty():
    """Test that puzzles have non-empty names and descriptions."""
    for puzzle in PUZZLES:
        name, fen, description, _ = puzzle
        assert name.strip() != "", "Puzzle name should not be empty"
        assert fen.strip() != "", "FEN should not be empty"
        assert description.strip() != "", "Description should not be empty"
