#!/bin/sh
# Updates the bundled Font Awesome Free assets to the version pinned below.
# Font Awesome 6 ships its webfonts only as .woff2 and .ttf.
set -e
FA_VERSION="6.7.2"

git clone --depth=1 --branch "${FA_VERSION}" https://github.com/FortAwesome/Font-Awesome.git fa-git
cp fa-git/LICENSE.txt .
cp fa-git/CHANGELOG.md .
cp fa-git/webfonts/fa-brands-400.woff2 fa-git/webfonts/fa-brands-400.ttf .
cp fa-git/webfonts/fa-regular-400.woff2 fa-git/webfonts/fa-regular-400.ttf .
cp fa-git/webfonts/fa-solid-900.woff2 fa-git/webfonts/fa-solid-900.ttf .
cp fa-git/metadata/icons.yml .
rm -rf fa-git
node ./fa-map-convert.js
