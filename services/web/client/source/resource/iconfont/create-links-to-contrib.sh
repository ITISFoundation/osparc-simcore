#!/bin/sh

# NOTE: docker-compose fails if links are invalid (ie. if contrib/ not in place)
# FIXME: set proper contrib version automatically!
ln -s ../../../contrib/ITISFoundation_qx-iconfont-fontawesome5_v0.0.1/source/resource/iconfont/fontawesome5/ fontawesome5
ln -s ../../../contrib/ITISFoundation_qx-iconfont-material_v0.0.0/source/resource/iconfont/material/ material
ls -l