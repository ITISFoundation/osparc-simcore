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


# Creates links in /source/resource/iconfont/
mkdir -p ${FONTS_DIR}
cd ${FONTS_DIR}


# TODO: with the next release of qx-compiler these lines can be removed
#rm *
#ln -s ../../../contrib/ITISFoundation_qx-iconfont-fontawesome5_v0.0.2/source/resource/iconfont/fontawesome5/ fontawesome5
#ln -s ../../../contrib/ITISFoundation_qx-iconfont-material_v0.0.1/source/resource/iconfont/material/ material
#ls -l
