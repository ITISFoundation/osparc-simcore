#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

# BOOTING application ---------------------------------------------
echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "  User    :$(id "$(whoami)")"
echo "  Workdir :$(pwd)"
echo "  env     :$(env)"

if [ "${SC_BUILD_TARGET}" = "development" ]; then
  echo "$INFO" "Environment :"
  printenv | sed 's/=/: /' | sed 's/^/    /' | sort
  echo "$INFO" "Python :"
  python --version | sed 's/^/    /'
  command -v python | sed 's/^/    /'
  cd services/sidecar || exit 1
  pip install --no-cache-dir -r requirements/dev.txt
  cd - || exit 1
  echo "$INFO" "PIP :"
  pip list | sed 's/^/    /'
fi


# RUNNING application ----------------------------------------
if [ "${DASK_SCHEDULER_ADDRESS}" ]; then
  echo "$INFO" "Starting as a worker -> ${DASK_SCHEDULER_ADDRESS} ..."
  CMD=dask-worker "${DASK_SCHEDULER_ADDRESS}"
else
  echo "$INFO" "Starting as a scheduler ..."
  CMD=dask-scheduler
fi

echo "$INFO" "Executing: ${CMD}"

if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then
  # NOTE: in this case, remote debugging is only available in development mode!
  exec watchmedo auto-restart --recursive --pattern="*.py" -- \
    ${CMD}
else
  exec ${CMD}
fi
