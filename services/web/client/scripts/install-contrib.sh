#!/bin/bash
echo "Installing qooxdoo contrib ..."

CLIENT_DIR=$(dirname "$0")/../
FONTS_DIR=${CLIENT_DIR}/source/resource/iconfont/

pushd ${CLIENT_DIR};

qx contrib update
qx contrib list
qx contrib install ITISFoundation/qx-osparc-theme
qx contrib install ITISFoundation/qx-iconfont-material
qx contrib install ITISFoundation/qx-iconfont-fontawesome5

mkdir -p ${FONTS_DIR}

# FIXME: set proper contrib version automatically!
ln -s ../../../contrib/ITISFoundation_qx-iconfont-fontawesome5_v0.0.1/source/resource/iconfont/fontawesome5/ ${FONTS_DIR}/fontawesome5
ln -s ../../../contrib/ITISFoundation_qx-iconfont-material_v0.0.0/source/resource/iconfont/material/ ${FONTS_DIR}/material
ls -l ${FONTS_DIR}

popd;