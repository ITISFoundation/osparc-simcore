#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

# BOOTING application ---------------------------------------------
echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "$INFO" "User :$(id "$(whoami)")"
echo "$INFO" "Workdir : $(pwd)"

if [ "${SC_BUILD_TARGET}" = "development" ]; then
  echo "$INFO" "Environment :"
  printenv | sed 's/=/: /' | sed 's/^/    /' | sort
  echo "$INFO" "Python :"
  python --version | sed 's/^/    /'
  command -v python | sed 's/^/    /'

  cd services/storage || exit 1
  pip --quiet --no-cache-dir install -r requirements/dev.txt
  cd - || exit 1
  echo "$INFO" "PIP :"
  pip list | sed 's/^/    /'

  echo "$INFO" "Setting entrypoint to use watchmedo autorestart..."
  entrypoint='watchmedo auto-restart --recursive --pattern="*.py;*/src/*" --ignore-patterns="*test*;pytest_simcore/*;setup.py;*ignore*" --ignore-directories --'

elif [ "${SC_BUILD_TARGET}" = "production" ]; then
  entrypoint=""
fi

# RUNNING application ----------------------------------------
echo "$INFO" "Selected config ${SC_BUILD_TARGET}"
if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then
  # NOTE: needs ptvsd installed
  echo "$INFO" "PTVSD Debugger initializing in port 3000 with ${SC_BUILD_TARGET}"
  eval "$entrypoint" python3 -m ptvsd --host 0.0.0.0 --port 3000 -m \
    simcore_service_storage run
else
  exec simcore-service-storage run
fi
