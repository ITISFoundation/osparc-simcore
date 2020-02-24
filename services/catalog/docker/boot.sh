#!/bin/sh
#
INFO="INFO: [$(basename "$0")] "
ERROR="ERROR: [$(basename "$0")] "

# BOOTING application ---------------------------------------------
echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "  User    :$(id "$(whoami)")"
echo "  Workdir :$(pwd)"

if [ "${SC_BUILD_TARGET}" = "development" ]
then
  echo "  Environment :"
  printenv  | sed 's/=/: /' | sed 's/^/    /' | sort
  #--------------------

  cd services/catalog || exit
  $SC_PIP install --user -r requirements/dev.txt
  cd /devel || exit

  #--------------------
  echo "$INFO" "  Python :"
  python --version | sed 's/^/    /'
  command -v python | sed 's/^/    /'
  echo "$INFO" "  PIP :"
  $SC_PIP list | sed 's/^/    /'
fi


# RUNNING application ----------------------------------------
if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]
then
  # NOTE: ptvsd is programmatically enabled inside of the service
  # this way we can have reload in place as well
  exec uvicorn simcore_service_catalog.main:app --reload --host 0.0.0.0
else
  exec simcore-service-catalog
fi
