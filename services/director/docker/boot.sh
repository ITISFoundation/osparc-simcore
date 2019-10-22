#!/bin/sh
#

# BOOTING application ---------------------------------------------
echo "Booting in ${SC_BOOT_MODE} mode ..."
echo "  User    :`id $(whoami)`"
echo "  Workdir :`pwd`"

LOG_LEVEL=info
if [[ ${SC_BUILD_TARGET} == "development" ]]
then
  echo "  Environment :"
  printenv  | sed 's/=/: /' | sed 's/^/    /' | sort
  #--------------------

  APP_CONFIG=config-host-dev.yaml

  cd services/director
  $SC_PIP install --user -r requirements/dev.txt
  cd /devel

  #--------------------
  echo "  Python :"
  python --version | sed 's/^/    /'
  which python | sed 's/^/    /'
  echo "  PIP :"
  $SC_PIP list | sed 's/^/    /'
fi

# RUNNING application ----------------------------------------
if [[ ${SC_BOOT_MODE} == "debug-ptvsd" ]]
then
  echo
  echo "PTVSD Debugger initializing in port 3004"
  python3 -m ptvsd --host 0.0.0.0 --port 3000 -m simcore_service_director --loglevel=$LOG_LEVEL
else
  simcore-service-director --loglevel=$LOG_LEVEL
fi
