#!/bin/bash

# FIXME: for the moment this has to run in sudo until Dockerfile works with non-root user

echo "Cleaning qooxdoo outputs ..."

source $(dirname $0)/.env

# WARNING: do not call this script with 'source'
echo "client dir: " ${CLIENT_DIR}
echo "fonts dir : " ${FONTS_DIR}

# Removes contrib folder and json file
rm -r ${CLIENT_DIR}/contrib 2> /dev/null
rm ${CLIENT_DIR}/contrib.json 2> /dev/null

# Removes links to
rm ${FONTS_DIR}/fontawesome5 2> /dev/null
rm ${FONTS_DIR}/material 2> /dev/null

# Runs 'qx clean'
pushd ${CLIENT_DIR};
docker run -itd -v $(pwd):/home/node/client  --entrypoint qx client_qx:latest clean
popd;
