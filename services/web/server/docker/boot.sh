#!/bin/sh
#

# BOOTING application ---------------------------------------------
echo "Booting in ${SC_BOOT_MODE} mode ..."
echo "  User    :`id $(whoami)`"
echo "  Workdir :`pwd`"

if [[ ${SC_BUILD_TARGET} == "development" ]]
then
  echo "  Environment :"
  printenv  | sed 's/=/: /' | sed 's/^/    /' | sort

  #------------
  APP_CONFIG=server-docker-dev.yaml

  cd services/web/server
  $SC_PIP install --user -r requirements/dev.txt
  cd /devel

  #------------
  echo "  Python :"
  python --version | sed 's/^/    /'
  which python | sed 's/^/    /'
  echo "  PIP :"
  $SC_PIP list | sed 's/^/    /'

  echo "  setting entrypoint to use watchmedo autorestart..."
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
  echo "Debugger attached: https://docs.python.org/3.6/library/pdb.html#debugger-commands  ..."
  echo "Running: import pdb, simcore_service_server.cli; pdb.run('simcore_service_server.cli.main([\'-c\',\'${APP_CONFIG}\'])')"
  eval "$entrypoint" python -c "import pdb, simcore_service_server.cli; \
             pdb.run('simcore_service_server.cli.main([\'-c\',\'${APP_CONFIG}\'])')"
elif [[ ${SC_BOOT_MODE} == "debug-ptvsd" ]]
then
  # NOTE: needs ptvsd installed
  echo "PTVSD Debugger initializing in port 3000 with ${APP_CONFIG}"
  eval "$entrypoint" python3 -m ptvsd --host 0.0.0.0 --port 3000 -m simcore_service_webserver --config $APP_CONFIG
else
  eval "$entrypoint" simcore-service-webserver --config $APP_CONFIG
fi
