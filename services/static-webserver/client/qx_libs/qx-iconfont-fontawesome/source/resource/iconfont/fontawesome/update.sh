#!/bin/sh
# Updates the bundled Font Awesome Free assets to the version pinned below.
#
# Font Awesome 7 ships its webfonts only as .woff2 (CFF/OTF flavoured) and a few
# glyphs are drawn taller than the em square, which qooxdoo clips. build_webfonts.py
# regenerates both the served .woff2 and the build-time-metrics .ttf from the
# upstream .otf sources, normalizing any oversized glyph so it fits its box.
# Requires Python with fonttools + cu2qu + brotli:
#   pip install fonttools cu2qu brotli
set -e
FA_VERSION="7.2.0"

git clone --depth=1 --branch "${FA_VERSION}" https://github.com/FortAwesome/Font-Awesome.git fa-git
cp fa-git/LICENSE.txt .
cp fa-git/CHANGELOG.md .
python3 ./build_webfonts.py fa-git
node ./fa-map-convert.js fa-git/metadata/icons.yml
rm -rf fa-git
