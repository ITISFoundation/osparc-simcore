#!/bin/bash
echo "Installing qooxdoo packages ..."

source $(dirname $0)/.env

# TODO: if env not defined, set defaults
echo "- script dir: " ${SCRIPT_DIR}
echo "- client dir: " ${CLIENT_DIR}
echo "- fonts dir : " ${FONTS_DIR}

# Installs themes and icon fonts
pushd ${HOME};

echo "qooxdoo and compiler versions"
npm ll qooxdoo-sdk
npm ll qxcompiler

popd


pushd ${CLIENT_DIR};

echo "Updating packages ..."
qx package update

echo "Listing packages ..."
qx package list

echo "Installing packages (based on information from qx-lock.json) ..."
qx package install

popd
