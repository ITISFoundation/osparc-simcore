#!/usr/bin/env python3
"""Build the bundled Font Awesome webfonts from the upstream ``.otf`` sources.

Font Awesome 7 ships its webfonts only as ``.woff2`` (CFF/OTF flavoured) and a
few of its glyphs are drawn taller than the em square (e.g. ``cogs`` reaches
1.18em, ``comments`` 1.13em, ``question-circle`` exactly 1.0em). The qooxdoo
``qx.ui.basic.Image`` renders a font icon inside a box whose height equals the
requested size, so any ink that exceeds the em square is clipped. Font Awesome 5
did not have this problem because its glyphs stayed within the em.

This script regenerates the fonts so that:

* outlines are converted from CFF to TrueType (``glyf``) -- the qooxdoo compiler
  reads glyph metrics from a ``.ttf`` at build time, and both the served
  ``.woff2`` and the ``.ttf`` are produced from the *same* normalized outlines
  so they can never disagree;
* any glyph whose ink is taller than ``TARGET_FILL`` em is uniformly scaled down
  about its centre until it fits, leaving smaller glyphs untouched. Glyphs are
  designed centred on the em centre, so no repositioning is needed.
"""
import sys
from pathlib import Path

from fontTools.misc.transform import Identity
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import table__g_l_y_f
from fontTools.ttLib.tables._l_o_c_a import table__l_o_c_a

MAX_ERR = 1.0  # cubic -> quadratic conversion tolerance, in font units
TARGET_FILL = 0.92  # max fraction of the em a glyph's ink may occupy

# Upstream .otf file name -> output basename (without extension).
SOURCES = {
    "otfs/Font Awesome 7 Free-Solid-900.otf": "fa-solid-900",
    "otfs/Font Awesome 7 Free-Regular-400.otf": "fa-regular-400",
    "otfs/Font Awesome 7 Brands-Regular-400.otf": "fa-brands-400",
}


def _build_font(src: Path, ttf_out: Path, woff2_out: Path) -> None:
    font = TTFont(str(src))
    upm = font["head"].unitsPerEm
    em_center = (font["hhea"].ascent + font["hhea"].descent) / 2
    max_ink = TARGET_FILL * upm

    glyph_order = font.getGlyphOrder()
    glyph_set = font.getGlyphSet()

    glyf_glyphs = {}
    for name in glyph_order:
        bounds_pen = BoundsPen(glyph_set)
        glyph_set[name].draw(bounds_pen)

        transform = Identity
        if bounds_pen.bounds is not None:
            x_min, y_min, x_max, y_max = bounds_pen.bounds
            ink_height = y_max - y_min
            if ink_height > max_ink:
                scale = max_ink / ink_height
                cx = (x_min + x_max) / 2
                transform = (
                    Identity.translate(cx, em_center)
                    .scale(scale)
                    .translate(-cx, -em_center)
                )

        tt_pen = TTGlyphPen(glyph_set)
        cu2qu_pen = Cu2QuPen(tt_pen, MAX_ERR, reverse_direction=True)
        glyph_set[name].draw(TransformPen(cu2qu_pen, transform))
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

    font.flavor = None
    font.save(str(ttf_out))
    font.flavor = "woff2"
    font.save(str(woff2_out))


def main(argv):
    if len(argv) != 2:
        print("usage: build_webfonts.py <font-awesome-checkout-dir>", file=sys.stderr)
        return 2
    fa_dir = Path(argv[1])
    for rel_src, basename in SOURCES.items():
        _build_font(fa_dir / rel_src, Path(f"{basename}.ttf"), Path(f"{basename}.woff2"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
