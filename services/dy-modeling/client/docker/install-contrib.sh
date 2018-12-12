#!/bin/bash
echo "Installing qooxdoo contrib ..."

source $(dirname $0)/.env

# TODO: if env not defined, set defaults
echo "- script dir: " ${SCRIPT_DIR}
echo "- client dir: " ${CLIENT_DIR}
echo "- fonts dir : " ${FONTS_DIR}

# Installs thems and iconfonts
pushd ${CLIENT_DIR};

echo "qooxdoo and compiler versions"
npm ll qooxdoo-sdk
npm ll qxcompiler

echo "Updating contributions ..."
qx contrib update

echo "Listing contributions ..."
qx contrib list

echo "Installing contributions from contrib.js ..."
qx contrib install

popd;
