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

  #------------
  APP_CONFIG=server-docker-dev.yaml

  cd services/web/server
  $SC_PIP install --user -r requirements/dev.txt
  cd /devel

  #------------
  echo $INFO "Python :"
  python --version | sed 's/^/    /'
  which python | sed 's/^/    /'
  echo $INFO "PIP :"
  $SC_PIP list | sed 's/^/    /'

  #------------
  echo $INFO "setting entrypoint to use watchmedo autorestart..."
  entrypoint='watchmedo auto-restart --recursive --pattern="*.py" --'

elif [[ ${SC_BUILD_TARGET} == "production" ]]
then
  APP_CONFIG=server-docker-prod.yaml
  entrypoint=''
fi


# RUNNING application ----------------------------------------
if [[ ${SC_BOOT_MODE} == "debug-pdb" ]]
then
  # NOTE: needs stdin_open: true and tty: true
  echo $INFO "Debugger attached: https://docs.python.org/3.6/library/pdb.html#debugger-commands  ..."
  echo $INFO "Running: import pdb, simcore_service_server.cli; pdb.run('simcore_service_server.cli.main([\'-c\',\'${APP_CONFIG}\'])')"
  eval "$entrypoint" python -c "import pdb, simcore_service_server.cli; \
             pdb.run('simcore_service_server.cli.main([\'-c\',\'${APP_CONFIG}\'])')"
elif [[ ${SC_BOOT_MODE} == "debug-ptvsd" ]]
then
  # NOTE: needs ptvsd installed
  echo $INFO "PTVSD Debugger initializing in port 3000 with ${APP_CONFIG}"
  eval "$entrypoint" python3 -m ptvsd --host 0.0.0.0 --port 3000 -m \
    simcore_service_webserver --config $APP_CONFIG
else
  exec simcore-service-webserver --config $APP_CONFIG
fi
