#!/bin/sh
#
INFO="INFO: [`basename "$0"`] "
ERROR="ERROR: [`basename "$0"`] "

# BOOTING application ---------------------------------------------
echo $INFO "Booting in ${SC_BOOT_MODE} mode ..."


if [[ ${SC_BUILD_TARGET} == "development" ]]
then
  echo $INFO "User    :`id $(whoami)`"
  echo $INFO "Workdir :`pwd`"
  echo $INFO "Environment :"
  printenv  | sed 's/=/: /' | sed 's/^/    /' | sort
  #--------------------

  APP_CONFIG=docker-dev-config.yaml

  cd services/storage
  $SC_PIP install --user -r requirements/dev.txt
  cd /devel

  #--------------------
  echo $INFO "Python :"
  python --version | sed 's/^/    /'
  which python | sed 's/^/    /'
  echo $INFO "PIP :"
  $SC_PIP list | sed 's/^/    /'

  #------------
  echo "  setting entrypoint to use watchmedo autorestart..."
  entrypoint='watchmedo auto-restart --recursive --pattern="*.py" --'

elif [[ ${SC_BUILD_TARGET} == "production" ]]
then
  APP_CONFIG=docker-prod-config.yaml
  entrypoint=''
fi


# RUNNING application ----------------------------------------
if [[ ${SC_BOOT_MODE} == "debug-pdb" ]]
then
  # NOTE: needs stdin_open: true and tty: true
  echo $INFO "Debugger attached: https://docs.python.org/3.6/library/pdb.html#debugger-commands  ..."
  echo $INFO "Running: import pdb, simcore_service_storage.cli; pdb.run('simcore_service_storage.cli.main([\'-c\',\'${APP_CONFIG}\'])')"
  eval $INFO "$entrypoint" python -c "import pdb, simcore_service_storage.cli; \
             pdb.run('simcore_service_storage.cli.main([\'-c\',\'${APP_CONFIG}\'])')"
elif [[ ${SC_BOOT_MODE} == "debug-ptvsd" ]]
then
  echo $INFO "PTVSD Debugger initializing in port 3003 with ${APP_CONFIG}"
  eval "$entrypoint" python3 -m ptvsd --host 0.0.0.0 --port 3000 -m \
      simcore_service_storage --config $APP_CONFIG
else
  exec simcore-service-storage --config $APP_CONFIG
fi
