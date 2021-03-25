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

# default
CONCURRENCY=1
POOL=prefork
if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then
  # NOTE: in this case, remote debugging is only available in development mode!
  # FIXME: workaround since PTVSD does not support prefork subprocess debugging: https://github.com/microsoft/ptvsd/issues/943
  POOL=solo
  exec watchmedo auto-restart --recursive --pattern="*.py" -- \
    celery worker \
    --app simcore_service_sidecar.celery:app \
    --concurrency ${CONCURRENCY} \
    --loglevel="${SIDECAR_LOGLEVEL-WARNING}" \
    --pool=${POOL} \
    --hostname=sidecar."$(cat ${SIDECAR_HOST_HOSTNAME_PATH})"@%h
else
  exec celery worker \
    --app simcore_service_sidecar.celery:app \
    --concurrency ${CONCURRENCY} \
    --loglevel="${SIDECAR_LOGLEVEL-WARNING}" \
    --pool=${POOL} \
    --hostname=sidecar."$(cat ${SIDECAR_HOST_HOSTNAME_PATH})"@%h
fi
