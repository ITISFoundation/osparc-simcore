#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

# BOOTING application ---------------------------------------------
echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "$INFO" "User :$(id "$(whoami)")"
echo "$INFO" "Workdir : $(pwd)"

if [ "${SC_BUILD_TARGET}" = "development" ]; then
  echo "$INFO" "Environment :"
  printenv | sed 's/=/: /' | sed 's/^/    /' | sort
  echo "$INFO" "Python :"
  python --version | sed 's/^/    /'
  command -v python | sed 's/^/    /'

  cd services/catalog || exit 1
  pip --quiet --no-cache-dir install -r requirements/dev.txt
  cd - || exit 1
  echo "$INFO" "PIP :"
  pip list | sed 's/^/    /'
fi

# RUNNING application ----------------------------------------
if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]
then
  # NOTE: ptvsd is programmatically enabled inside of the service
  # this way we can have reload in place as well
  exec uvicorn simcore_service_catalog.__main__:the_app --reload --host 0.0.0.0
else
  exec simcore-service-catalog
fi
