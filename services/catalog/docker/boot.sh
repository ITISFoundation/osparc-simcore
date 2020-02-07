#!/bin/sh
#
INFO="INFO: [`basename "$0"`] "
ERROR="ERROR: [`basename "$0"`] "

# BOOTING application ---------------------------------------------
echo $INFO "Booting in ${SC_BOOT_MODE} mode ..."

if [[ ${SC_BUILD_TARGET} == "development" ]]
then
  echo "  User    :`id $(whoami)`"
  echo "  Workdir :`pwd`"
  echo "  Environment :"
  printenv  | sed 's/=/: /' | sed 's/^/    /' | sort
  #--------------------

  APP_CONFIG=config-host-dev.yaml
  $SC_PIP install --user -e services/catalog

  #--------------------
  echo "  Python :"
  python --version | sed 's/^/    /'
  which python | sed 's/^/    /'
  echo "  PIP :"
  $SC_PIP list | sed 's/^/    /'


elif [[ ${SC_BUILD_TARGET} == "production" ]]
then
  APP_CONFIG=config-host-dev.yaml

fi


# RUNNING application ----------------------------------------
if [[ ${BOOT_MODE} == "debug" ]]
then
  echo $INFO "Debugger attached: https://docs.python.org/3.6/library/pdb.html#debugger-commands  ..."
  echo $INFO "Running: import pdb, simcore_service_catalog.cli; pdb.run('simcore_service_catalog.cli.main([\'-c\',\'${APP_CONFIG}\'])')"
  python -c "import pdb, simcore_service_catalog.cli; \
             pdb.run('simcore_service_catalog.cli.main([\'-c\',\'${APP_CONFIG}\'])')"

else
  simcore-service-catalog --config $APP_CONFIG
fi
