"""Tests for pieces_svg module."""

from pieces_svg import get_svg


def test_get_svg_white_pieces():
    """Test SVG generation for white pieces."""
    white_pieces = ["K", "Q", "R", "B", "N", "P"]
    for piece in white_pieces:
        svg = get_svg("white", piece)
        assert isinstance(svg, str)
        assert len(svg) > 0
        assert "svg" in svg.lower() or "<svg" in svg


def test_get_svg_black_pieces():
    """Test SVG generation for black pieces."""
    black_pieces = ["K", "Q", "R", "B", "N", "P"]
    for piece in black_pieces:
        svg = get_svg("black", piece)
        assert isinstance(svg, str)
        assert len(svg) > 0
        assert "svg" in svg.lower() or "<svg" in svg


def test_get_svg_all_pieces():
    """Test SVG generation for all piece types."""
    pieces = ["K", "Q", "R", "B", "N", "P"]
    colors = ["white", "black"]

    for color in colors:
        for piece in pieces:
            svg = get_svg(color, piece)
            assert isinstance(svg, str)
            assert len(svg) > 0


def test_get_svg_different_outputs():
    """Test that white and black pieces produce different SVGs."""
    white_svg = get_svg("white", "K")
    black_svg = get_svg("black", "K")
    # They should be different (different colors)
    assert white_svg != black_svg


def test_get_svg_case_sensitivity():
    """Test that piece symbols are handled correctly."""
    # Both "K" and "k" are valid piece symbols and return SVG (white king vs black king)
    svg1 = get_svg("white", "K")
    svg2 = get_svg("white", "k")
    assert svg1 and svg2
    # So for white, "K" stays "K", for black "K" becomes "k"
    svg_white_k = get_svg("white", "K")
    svg_black_k = get_svg("black", "K")
    assert svg_white_k != svg_black_k
