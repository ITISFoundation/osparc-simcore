#!/bin/sh
#
INFO="INFO: [$(basename "$0")] "

# BOOTING application ---------------------------------------------
echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "  User    :$(id "$(whoami)")"
echo "  Workdir :$(pwd)"

if [ "${SC_BUILD_TARGET}" = "development" ]
then
  echo "$INFO" "Environment :"
  printenv  | sed 's/=/: /' | sed 's/^/    /' | sort
  #--------------------

  cd services/sidecar || exit
  $SC_PIP install --user -r requirements/dev.txt
  cd /devel || exit

  #--------------------
  echo "$INFO" "Python :"
  python --version | sed 's/^/    /'
  command -v python | sed 's/^/    /'
  echo "$INFO" "PIP :"
  $SC_PIP list | sed 's/^/    /'
fi

# RUNNING application ----------------------------------------

# default
CONCURRENCY=1
POOL=prefork

if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]
then
  # NOTE: in this case, remote debugging is only available in development mode!
  # FIXME: workaround since PTVSD does not support prefork subprocess debugging: https://github.com/microsoft/ptvsd/issues/943
  POOL=solo
fi

exec celery worker \
    --app sidecar.celery:app \
    --concurrency ${CONCURRENCY} \
    --loglevel="${SIDECAR_LOGLEVEL-WARNING}" \
    --pool=${POOL}
