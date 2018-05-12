#!/bin/bash
echo "Installing qooxdoo contrib ..."

source ./scripts/.env

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


# Creates links in /source/resource/iconfont/
mkdir -p ${FONTS_DIR}
pushd ${FONTS_DIR};

# FIXME: set proper contrib version automatically!
ln -s ../../../contrib/ITISFoundation_qx-iconfont-fontawesome5_v0.0.1/source/resource/iconfont/fontawesome5/ fontawesome5
ln -s ../../../contrib/ITISFoundation_qx-iconfont-material_v0.0.0/source/resource/iconfont/material/ material
ls -l

popd;
