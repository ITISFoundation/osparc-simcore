#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "
SC_DONE_FILE=migration.done

echo "$INFO" "Entrypoint for stage ${SC_BUILD_TARGET} ..."
echo "$INFO" "User :$(id "$(whoami)")"
echo "$INFO" "Workdir : $(pwd)"
echo "$INFO" "User : $(id scu)"
echo "$INFO" "python : $(command -v python)"
echo "$INFO" "pip : $(command -v pip)"

echo "$INFO ${SC_USER_NAME} rights    : $(id "$SC_USER_NAME")"
echo "$INFO local dir : $(ls -al)"

if [ -f ${SC_DONE_FILE} ];then
    rm "${SC_DONE_FILE}"
fi

echo "$INFO Starting migration ..."
sc-pg upgrade-and-close

echo "DONE" > "${SC_DONE_FILE}"

echo "$INFO Migration Done. Wait forever ..."
# TODO: perhaps we should simply stop???
exec tail -f /dev/null
