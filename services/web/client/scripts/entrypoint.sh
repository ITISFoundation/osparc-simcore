#!/bin/bash
#
#
echo "Booting qooxdoo ..."

source $(dirname $0)/.env
echo "- script dir: " ${SCRIPT_DIR}
echo "- client dir: " ${CLIENT_DIR}
echo "- fonts dir : " ${FONTS_DIR}

# TODO: add argument to avoid installing contributions
${SCRIPT_DIR}/install-contrib.sh

echo Running \'qx "$@"\' ...
qx "$@"
