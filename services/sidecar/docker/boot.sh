#!/bin/sh
#
INFO="INFO: [`basename "$0"`] "
ERROR="ERROR: [`basename "$0"`] "

# BOOTING application ---------------------------------------------
echo $INFO "Booting in ${SC_BOOT_MODE} mode ..."
echo "  User    :`id $(whoami)`"
echo "  Workdir :`pwd`"

if [[ ${SC_BUILD_TARGET} == "development" ]]
then
  echo $INFO "Environment :"
  printenv  | sed 's/=/: /' | sed 's/^/    /' | sort
  #--------------------

  cd services/sidecar
  $SC_PIP install --user -r requirements/dev.txt
  cd /devel

  DEBUG_LEVEL=debug
  #--------------------
  echo $INFO "Python :"
  python --version | sed 's/^/    /'
  which python | sed 's/^/    /'
  echo $INFO "PIP :"
  $SC_PIP list | sed 's/^/    /'


elif [[ ${SC_BUILD_TARGET} == "production" ]]
then
  DEBUG_LEVEL=info
fi

# RUNNING application ----------------------------------------

# default
DEBUG_LEVEL=info
CONCURRENCY=2
POOL=prefork


if [[ ${SC_BOOT_MODE} == "debug-ptvsd" ]]
then
  # NOTE: in this case, remote debugging is only available in development mode!
  # FIXME: workaround since PTVSD does not support prefork subprocess debugging: https://github.com/microsoft/ptvsd/issues/943
  POOL=solo

elif [[ ${SC_BOOT_MODE} == "debug" ]]
then
  DEBUG_LEVEL=debug
  CONCURRENCY=1
fi

exec celery worker \
    --app sidecar.celery:app \
    --concurrency ${CONCURRENCY} \
    --loglevel=${DEBUG_LEVEL} \
    --pool=${POOL}
