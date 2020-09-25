#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

echo "$INFO" "Entrypoint for stage ${SC_BUILD_TARGET} ..."
echo "$INFO" "User :$(id "$(whoami)")"
echo "$INFO" "Workdir : $(pwd)"
echo "$INFO" "User : $(id scu)"
echo "$INFO" "python : $(command -v python)"
echo "$INFO" "pip : $(command -v pip)"

echo "$INFO ${SC_USER_NAME} rights    : $(id "$SC_USER_NAME")"
echo "$INFO local dir : $(ls -al)"

echo "$INFO Starting migration ..."
sc-pg upgrade-and-close

echo "$INFO Migration Done. Wait forever ..."
exec tail -f /dev/null
