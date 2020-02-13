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

  $SC_PIP install --user --editable services/catalog

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
  # TODO: add ptvsd programmatically instead
  #echo $INFO "PTVSD Debugger initializing in port 3000 with ${APP_CONFIG}"
  #eval "$entrypoint" python3 -m ptvsd --host 0.0.0.0 --port 3000 -m \
  #  simcore_service_catalog
  uvicorn simcore_service_catalog.main:app --reload --host 0.0.0.0
else
  exec simcore-service-catalog
fi
