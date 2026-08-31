"""Decode Symbol-font characters that a PDF extractor leaves in the private-use area.

A PDF that sets mathematical operators in Adobe's Symbol font stores them by
*font position*, not by meaning. Extractors that cannot resolve the font emit
each one into the Unicode private-use area as ``U+F000 + position`` -- so a minus
sign set in Symbol arrives as ``U+F02D`` rather than ``U+2212``. The character is
not damaged and nothing is lost; it is written in an encoding nobody downstream
reads.

**This is a decode, not a repair.** Adobe's Symbol encoding is a published,
fixed table, so ``U+F02D`` means the glyph at Symbol position 0x2D and cannot
mean anything else. That distinction matters here: R-008 forbids *guessing* at a
formula's content, and R-043 rejected a matcher that inferred a formula from its
page. Neither applies to reading a documented encoding.

Every mapping below was nonetheless corroborated against an independent parser
before being adopted (R-054): for each codepoint, Chandra's LaTeX for the same
pages was checked for the corresponding glyph. Ten of the eleven were confirmed
on **every** page where they occur. The eleventh, ``U+F0D7`` (dot operator), has
no counterpart because Chandra wrote that multiplication implicitly -- it is
kept on the strength of the published table, and it is the only entry resting on
the table alone.

Only codepoints that actually occur in the corpus are mapped. An unrecognised
private-use character is left exactly as it is, so a new one shows up as itself
rather than being silently approximated.
"""

from __future__ import annotations

# Adobe Symbol encoding. The key is the private-use codepoint an extractor emits;
# the comment is the Symbol font position it stands for.
SYMBOL_FONT: dict[int, str] = {
    0xF028: "(",         # 0x28 parenleft
    0xF029: ")",         # 0x29 parenright
    0xF02B: "+",         # 0x2B plus
    0xF02D: "−",    # 0x2D minus
    0xF03D: "=",         # 0x3D equal
    0xF061: "α",    # 0x61 alpha
    0xF0B1: "±",    # 0xB1 plusminus
    0xF0B3: "≥",    # 0xB3 greaterequal
    0xF0B9: "≠",    # 0xB9 notequal
    0xF0D0: "∠",    # 0xD0 angle
    0xF0D7: "⋅",    # 0xD7 dotmath
}

PRIVATE_USE = range(0xE000, 0xF900)

_TRANSLATION = str.maketrans({key: value for key, value in SYMBOL_FONT.items()})


def decode_symbol_font(text: str) -> str:
    """Replace known Symbol-font private-use characters with the glyph they mean.

    Unknown private-use characters are preserved. Text with none of them is
    returned unchanged.
    """
    return text.translate(_TRANSLATION)


def undecoded_private_use(text: str) -> set[str]:
    """Private-use characters this module does not have a mapping for.

    Used to prove a decode was complete, and to notice a new font position
    appearing when another chapter is parsed rather than shipping it as a box.
    """
    return {
        character
        for character in text
        if ord(character) in PRIVATE_USE and ord(character) not in SYMBOL_FONT
    }
