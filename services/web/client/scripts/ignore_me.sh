#!/bin/bash
echo Testing with $0

source $(dirname $0)/.env
echo "- script dir: " ${SCRIPT_DIR}
echo "- client dir: " ${CLIENT_DIR}
echo "- fonts dir : " ${FONTS_DIR}


# TODO: add argument to control qx command at entry point
echo Running \'qx serve "$@"\'

pushd ${FONTS_DIR}
echo ---------
pwd
echo content:
ls -la
popd

echo ---------
pwd
echo content:
ls -la
