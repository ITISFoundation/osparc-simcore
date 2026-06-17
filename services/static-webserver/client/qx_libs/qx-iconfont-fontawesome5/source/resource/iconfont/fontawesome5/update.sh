#!/bin/sh
git clone --depth=1 https://github.com/FortAwesome/Font-Awesome.git fa-git
cp fa-git/LICENSE.txt .
cp fa-git/CHANGELOG.md .
cp fa-git/webfonts/* .
cp fa-git/metadata/icons.yml .
rm *.svg
rm -rf fa-git
node ./fa-map-convert.js
