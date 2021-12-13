#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

# BOOTING application ---------------------------------------------
echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "  User    :$(id "$(whoami)")"
echo "  Workdir :$(pwd)"

if [ "${SC_BUILD_TARGET}" = "development" ]; then
  echo "$INFO" "Environment :"
  printenv | sed 's/=/: /' | sed 's/^/    /' | sort
  echo "$INFO" "Python :"
  python --version | sed 's/^/    /'
  command -v python | sed 's/^/    /'
  cd services/director || exit 1
  pip install --no-cache-dir -r requirements/dev.txt
  cd - || exit 1
  echo "$INFO" "PIP :"
  pip list | sed 's/^/    /'
fi

# RUNNING application ----------------------------------------
if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then
  watchmedo auto-restart --recursive --pattern="*.py;*/src/*" --ignore-patterns="*test*;pytest_simcore/*;setup.py;*ignore*" --ignore-directories -- \
    python3 -m ptvsd --host 0.0.0.0 --port 3000 -m \
    simcore_service_director --loglevel="${LOGLEVEL}"
else
  exec simcore-service-director --loglevel="${LOGLEVEL}"
fi
