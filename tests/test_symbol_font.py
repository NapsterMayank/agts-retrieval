"""The Symbol-font decode must be total, inert on clean text, and never guess."""

from __future__ import annotations

import pytest

from agts.parsing.quality import is_unusable
from agts.parsing.symbol_font import (
    SYMBOL_FONT,
    decode_symbol_font,
    undecoded_private_use,
)

LPAREN, RPAREN, MINUS, EQUALS = chr(0xF028), chr(0xF029), chr(0xF02D), chr(0xF03D)
DOTMATH, UNMAPPED = chr(0xF0D7), chr(0xF0FF)


def test_clean_text_is_returned_unchanged() -> None:
    for text in ["x^2 - 45x + 324 = 0", "", "Chemical reactions and equations", "α ± β"]:
        assert decode_symbol_font(text) == text


def test_each_mapped_codepoint_becomes_its_glyph() -> None:
    for codepoint, glyph in SYMBOL_FONT.items():
        assert decode_symbol_font(chr(codepoint)) == glyph


def test_a_real_extracted_formula_becomes_readable() -> None:
    # quadratic-equations:docling:texts-125, page 6, as Docling emitted it.
    raw = f"{LPAREN} {RPAREN} {LPAREN} {RPAREN} 3 2 3 2 0 x x {MINUS} {MINUS} {EQUALS}"
    decoded = decode_symbol_font(raw)
    assert undecoded_private_use(decoded) == set()
    assert decoded.count("(") == 2 and decoded.count(")") == 2
    assert "−" in decoded and "=" in decoded


def test_the_decode_removes_the_private_use_characters_it_is_for() -> None:
    """quadratic-equations:docling:texts-125, page 6.

    This test used to assert that decoding alone made the block readable, and
    R-054 counted four blocks rescued that way. Both were measured with a
    quality gate that excused any text carrying a relation symbol, and this
    block carries three. Under the corrected gate it is still unusable, which is
    the honest reading: `( ) ( ) 3 2 3 2 0 x x - - = Now, 3 2 0 x - = for 2 3 x
    = .` has lost the structure of the polynomial, and no reader reconstructs
    `(3x - 2)` from it.

    The decode did its job -- there are no private-use characters left, and the
    relations are real relations. It was never going to fix reading order, and
    the count that said otherwise was the gate flattering itself.
    """
    raw = (
        f"{LPAREN} {RPAREN} {LPAREN} {RPAREN} 3 2 3 2 0 x x {MINUS} {MINUS} {EQUALS} "
        f"Now, 3 2 0 x {MINUS} {EQUALS} for 2 3 x {EQUALS} ."
    )
    decoded = decode_symbol_font(raw)

    assert undecoded_private_use(decoded) == set()
    assert "=" in decoded and "−" in decoded
    # Still needs LaTeX, and now says so instead of passing as prose.
    assert is_unusable(decoded)


def test_the_decode_does_not_pretend_to_fix_a_scrambled_formula() -> None:
    # texts-159's problem is reading *order*, not encoding: the characters are
    # right and their sequence is not. Decoding must leave it visibly broken
    # rather than dress it up as recovered -- that block still needs LaTeX.
    raw = f"2 a 2 2 a a 2 a {MINUS} {DOTMATH}"
    assert is_unusable(raw)
    assert is_unusable(decode_symbol_font(raw))


def test_an_unmapped_private_use_character_survives_rather_than_being_guessed() -> None:
    assert decode_symbol_font(f"a{UNMAPPED}b") == f"a{UNMAPPED}b"
    assert undecoded_private_use(f"a{UNMAPPED}b") == {UNMAPPED}


def test_undecoded_reports_nothing_for_text_the_table_covers() -> None:
    covered = "".join(chr(codepoint) for codepoint in SYMBOL_FONT)
    assert undecoded_private_use(covered) == set()


@pytest.mark.parametrize("codepoint,glyph", sorted(SYMBOL_FONT.items()))
def test_no_mapping_produces_another_private_use_character(codepoint: int, glyph: str) -> None:
    assert undecoded_private_use(glyph) == set()
    assert decode_symbol_font(glyph) == glyph
