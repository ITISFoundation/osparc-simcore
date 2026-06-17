#!/usr/bin/env python3
"""Convert Font Awesome's CFF/OTF webfonts to TrueType (.ttf).

Font Awesome 7 ships its webfonts only as ``.woff2`` (CFF/OTF flavoured).
The qooxdoo compiler that builds this client extracts glyph metrics from a
``.ttf`` resource at build time, so we vendor a TrueType copy alongside the
``.woff2`` that is actually served to browsers. The TrueType files are
generated from the upstream ``.otf`` sources with this script (see update.sh).
"""
import sys
from pathlib import Path

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import table__g_l_y_f
from fontTools.ttLib.tables._l_o_c_a import table__l_o_c_a

MAX_ERR = 1.0  # outline conversion tolerance in font units


def otf_to_ttf(src: Path, dst: Path) -> None:
    font = TTFont(str(src))
    if "glyf" in font:
        font.save(str(dst))
        return

    glyph_order = font.getGlyphOrder()
    glyph_set = font.getGlyphSet()

    glyf_glyphs = {}
    for name in glyph_order:
        tt_pen = TTGlyphPen(glyph_set)
        cu2qu_pen = Cu2QuPen(tt_pen, MAX_ERR, reverse_direction=True)
        glyph_set[name].draw(cu2qu_pen)
        glyf_glyphs[name] = tt_pen.glyph()

    glyf = table__g_l_y_f()
    glyf.glyphOrder = glyph_order
    glyf.glyphs = glyf_glyphs
    font["glyf"] = glyf
    font["loca"] = table__l_o_c_a()

    # TrueType uses sfntVersion 0x00010000 and drops the CFF outlines.
    font.sfntVersion = "\x00\x01\x00\x00"
    for tag in ("CFF ", "CFF2", "VORG"):
        if tag in font:
            del font[tag]

    for name in glyph_order:
        glyf_glyphs[name].recalcBounds(glyf)

    font.save(str(dst))


def main(argv):
    if len(argv) != 3:
        print("usage: otf2ttf.py <input.otf> <output.ttf>", file=sys.stderr)
        return 2
    otf_to_ttf(Path(argv[1]), Path(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
