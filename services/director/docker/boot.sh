#!/bin/sh
#

# BOOTING application ---------------------------------------------
echo "Booting in ${SC_BOOT_MODE} mode ..."


if [[ ${SC_BUILD_TARGET} == "development" ]]
then
  echo "  User    :`id $(whoami)`"
  echo "  Workdir :`pwd`"
  echo "  Environment :"
  printenv  | sed 's/=/: /' | sed 's/^/    /' | sort
  #--------------------

  APP_CONFIG=config-host-dev.yaml
  $SC_PIP install --user -e services/director

  #--------------------
  echo "  Python :"
  python --version | sed 's/^/    /'
  which python | sed 's/^/    /'
  echo "  PIP :"
  $SC_PIP list | sed 's/^/    /'


elif [[ ${SC_BUILD_TARGET} == "production" ]]
then
  LOG_LEVEL=info
fi


# RUNNING application ----------------------------------------
if [[ ${SC_BOOT_MODE} == "debug" ]]
then
  LOG_LEVEL=debug
else
  LOG_LEVEL=info
fi

# FIXME: arguments were never wired!
simcore-service-director --loglevel=$LOG_LEVEL
