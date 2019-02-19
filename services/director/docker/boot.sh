#!/bin/sh
#

# BOOTING application ---------------------------------------------
echo "Booting in ${MY_BOOT_MODE} mode ..."


if [[ ${MY_BUILD_TARGET} == "development" ]]
then
  echo "  User    :`id $(whoami)`"
  echo "  Workdir :`pwd`"
  echo "  Environment :"
  printenv  | sed 's/=/: /' | sed 's/^/    /' | sort
  #--------------------

  APP_CONFIG=config-host-dev.yaml
  $MY_PIP install --user -e services/director

  #--------------------
  echo "  Python :"
  python --version | sed 's/^/    /'
  which python | sed 's/^/    /'
  echo "  PIP :"
  $MY_PIP list | sed 's/^/    /'


elif [[ ${MY_BUILD_TARGET} == "production" ]]
then
  LOG_LEVEL=info
fi


# RUNNING application ----------------------------------------
if [[ ${BOOT_MODE} == "debug" ]]
then
  LOG_LEVEL=debug
else
  LOG_LEVEL=info
fi

# FIXME: arguments were never wired!
simcore-service-director --loglevel=$LOG_LEVEL
