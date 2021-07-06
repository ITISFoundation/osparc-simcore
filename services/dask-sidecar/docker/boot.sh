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
  cd services/dask-sidecar || exit 1
  pip install --no-cache-dir -r requirements/dev.txt
  cd - || exit 1
  echo "$INFO" "PIP :"
  pip list | sed 's/^/    /'
fi

# RUNNING application ----------------------------------------
#
# - If DASK_START_AS_SCHEDULER is set, then it boots as scheduler otherwise as worker
# - SEE https://docs.dask.org/en/latest/setup/cli.html
# - SEE https://stackoverflow.com/questions/3601515/how-to-check-if-a-variable-is-set-in-bash
# - FIXME: create command prefix: https://unix.stackexchange.com/questions/444946/how-can-we-run-a-command-stored-in-a-variable
#

if [ ${DASK_START_AS_SCHEDULER+x} ]; then
  SCHEDULER_VERSION=$(dask-scheduler --version)

  echo "$INFO" "Starting as ${SCHEDULER_VERSION}..."
  if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then

    exec watchmedo auto-restart --recursive --pattern="*.py" -- \
      dask-scheduler

  else

    exec dask-scheduler

  fi
else
  DASK_WORKER_VERSION=$(dask-worker --version)
  DASK_SCHEDULER_ADDRESS="tcp://${DASK_SCHEDULER_HOST}:8786"

  echo "$INFO" "Starting as a ${DASK_WORKER_VERSION} -> ${DASK_SCHEDULER_ADDRESS} ..."
  if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then

    exec watchmedo auto-restart --recursive --pattern="*.py" -- \
      dask-worker "${DASK_SCHEDULER_ADDRESS}" \
      --local-directory /tmp/dask-sidecar \
      --preload simcore_service_dask_sidecar.tasks \
      --reconnect \
      --no-nanny \
      --dashboard-address 8787

  else

    exec dask-worker "${DASK_SCHEDULER_ADDRESS}" \
      --local-directory /tmp/dask-sidecar \
      --preload simcore_service_dask_sidecar.tasks \
      --reconnect \
      --no-nanny \
      --dashboard-address 8787

  fi
fi
