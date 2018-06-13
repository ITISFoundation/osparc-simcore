#!/bin/bash
echo "Installing qooxdoo contrib ..."

source $(dirname $0)/.env

# TODO: if env not defined, set defaults
echo "- script dir: " ${SCRIPT_DIR}
echo "- client dir: " ${CLIENT_DIR}
echo "- fonts dir : " ${FONTS_DIR}

# Installs thems and iconfonts
pushd ${CLIENT_DIR};

qx contrib update
qx contrib list
qx contrib install ITISFoundation/qx-osparc-theme
qx contrib install ITISFoundation/qx-iconfont-material
qx contrib install ITISFoundation/qx-iconfont-fontawesome5

popd;
