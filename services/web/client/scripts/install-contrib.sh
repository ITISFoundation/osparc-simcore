#!/bin/bash
echo "Installing qooxdoo contrib ..."

source $(dirname $0)/.env

# TODO: if env not defined, set defaults
echo "- script dir: " ${SCRIPT_DIR}
echo "- client dir: " ${CLIENT_DIR}
echo "- fonts dir : " ${FONTS_DIR}

# Installs thems and iconfonts
pushd ${CLIENT_DIR};

echo "Updating contributions ..."
qx contrib update

echo "Listing contributions ..."
qx contrib list

echo "Installing contributions ..."
qx contrib install ITISFoundation/qx-osparc-theme
qx contrib install ITISFoundation/qx-iconfont-material
qx contrib install ITISFoundation/qx-iconfont-fontawesome5

popd;
