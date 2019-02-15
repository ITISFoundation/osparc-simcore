#!/bin/sh
#

# BOOTING application ---------------------------------------------
echo "Booting in ${MY_BOOT_MODE} mode ..."

APP_CONFIG=server-docker-prod.yaml

if [[ ${MY_BUILD_TARGET} == "development" ]]
then
  echo "  User    :`id $(whoami)`"
  echo "  Workdir :`pwd`"
  echo "  Environment :"
  printenv  | sed 's/=/: /' | sed 's/^/    /' | sort

  $MY_PIP install --user --editable services/web/server

  echo "  Python :"
  python --version | sed 's/^/    /'
  which python | sed 's/^/    /'
  echo "  PIP :"
  $MY_PIP list | sed 's/^/    /'

  APP_CONFIG=server-docker-dev.yaml

elif [[ ${MY_BUILD_TARGET} == "production" ]]
then
  APP_CONFIG=server-docker-prod.yaml
fi


# RUNNING application ----------------------------------------
if [[ ${BOOT_MODE} == "debug" ]]
then
  echo "Debugger attached: https://docs.python.org/3.6/library/pdb.html#debugger-commands  ..."
  echo "Running: import pdb, simcore_service_server.cli; pdb.run('simcore_service_server.cli.main([\'-c\',\'${APP_CONFIG}\'])')"
  python -c "import pdb, simcore_service_server.cli; \
             pdb.run('simcore_service_server.cli.main([\'-c\',\'${APP_CONFIG}\'])')"

else
  simcore-service-webserver --config $APP_CONFIG
fi
