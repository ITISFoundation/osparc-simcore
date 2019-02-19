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

  APP_CONFIG=docker-dev-config.yaml
  $SC_PIP install --user -e services/storage

  #--------------------
  echo "  Python :"
  python --version | sed 's/^/    /'
  which python | sed 's/^/    /'
  echo "  PIP :"
  $SC_PIP list | sed 's/^/    /'


elif [[ ${SC_BUILD_TARGET} == "production" ]]
then
  APP_CONFIG=docker-prod-config.yaml

fi


# RUNNING application ----------------------------------------
if [[ ${SC_BOOT_MODE} == "debug" ]]
then
  echo "Debugger attached: https://docs.python.org/3.6/library/pdb.html#debugger-commands  ..."
  echo "Running: import pdb, simcore_service_storage.cli; pdb.run('simcore_service_storage.cli.main([\'-c\',\'${APP_CONFIG}\'])')"
  python -c "import pdb, simcore_service_storage.cli; \
             pdb.run('simcore_service_storage.cli.main([\'-c\',\'${APP_CONFIG}\'])')"

else
  simcore-service-storage --config $APP_CONFIG
fi
