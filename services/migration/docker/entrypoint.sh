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
echo "$INFO" "UV : $(command -v uv)"

echo "$INFO ${SC_USER_NAME} rights    : $(id "$SC_USER_NAME")"
echo "$INFO local dir : $(ls -al)"

if [ -f "${SC_DONE_MARK_FILE}" ]; then
  rm "${SC_DONE_MARK_FILE}"
fi

echo "$INFO Requirements installed:"
pip freeze

echo "$INFO Starting migration ..."
sc-pg upgrade-and-close

echo "DONE" >"${SC_DONE_MARK_FILE}"

echo "$INFO Migration Done. Wait forever ..."
echo "$INFO local dir after update: $(ls -al)"
exec tail -f /dev/null
