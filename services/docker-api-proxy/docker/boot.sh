#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "$INFO" "User :$(id "$(whoami)")"

#
# RUNNING application
#
socat TCP-LISTEN:8888,fork,reuseaddr UNIX-CONNECT:/var/run/docker.sock
