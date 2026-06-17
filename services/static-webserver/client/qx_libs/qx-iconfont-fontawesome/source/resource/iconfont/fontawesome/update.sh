#!/bin/sh
# Updates the bundled Font Awesome Free assets to the version pinned below.
#
# Font Awesome 7 ships its webfonts only as .woff2 (CFF/OTF flavoured). The
# .woff2 files are what browsers download. The qooxdoo compiler that builds
# this client, however, reads glyph metrics from a .ttf at build time, so we
# also vendor a TrueType copy generated from the upstream .otf sources
# (requires Python with fonttools + cu2qu: pip install fonttools cu2qu brotli).
set -e
FA_VERSION="7.2.0"

git clone --depth=1 --branch "${FA_VERSION}" https://github.com/FortAwesome/Font-Awesome.git fa-git
cp fa-git/LICENSE.txt .
cp fa-git/CHANGELOG.md .
cp fa-git/webfonts/fa-brands-400.woff2 .
cp fa-git/webfonts/fa-regular-400.woff2 .
cp fa-git/webfonts/fa-solid-900.woff2 .
python3 ./otf2ttf.py "fa-git/otfs/Font Awesome 7 Free-Solid-900.otf" fa-solid-900.ttf
python3 ./otf2ttf.py "fa-git/otfs/Font Awesome 7 Free-Regular-400.otf" fa-regular-400.ttf
python3 ./otf2ttf.py "fa-git/otfs/Font Awesome 7 Brands-Regular-400.otf" fa-brands-400.ttf
cp fa-git/metadata/icons.yml .
rm -rf fa-git
node ./fa-map-convert.js
