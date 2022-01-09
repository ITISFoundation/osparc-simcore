#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "$INFO" "User :$(id "$(whoami)")"
echo "$INFO" "Workdir : $(pwd)"

#
# DEVELOPMENT MODE
#
# - prints environ info
# - installs requirements in mounted volume
#
if [ "${SC_BUILD_TARGET}" = "development" ]; then
  echo "$INFO" "Environment :"
  printenv | sed 's/=/: /' | sed 's/^/    /' | sort
  echo "$INFO" "Python :"
  python --version | sed 's/^/    /'
  command -v python | sed 's/^/    /'

  cd services/director-v2 || exit 1
  pip --quiet --no-cache-dir install -r requirements/dev.txt
  cd - || exit 1
  echo "$INFO" "PIP :"
  pip list | sed 's/^/    /'
fi

#
# RUNNING application
#
if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then
  # NOTE: ptvsd is programmatically enabled inside of the service
  # this way we can have reload in place as well
  reload_dir_packages=$(find packages -maxdepth 3 -type d -path "*/src/*" ! -path "*.*" -exec echo --reload-dir {} \;)

  # NOTE: keep the reload_dir_package as un-quoted as the IFS (internal field separators works only this way. any SH shell guru is welcome to enhance this!
  # FIXME: when uvicorn >0.15.0 comes in, replace it with --reload-include '*.py'
  IFS=$(printf ' \n\t');
  #shellcheck disable=SC2086
  exec uvicorn simcore_service_director_v2.main:the_app \
    --host 0.0.0.0 \
    --reload \
    $reload_dir_packages \
    --reload-dir services/director-v2/src/simcore_service_director_v2
else
  exec uvicorn simcore_service_director_v2.main:the_app \
    --host 0.0.0.0
fi
