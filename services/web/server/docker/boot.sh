#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

# BOOTING application ---------------------------------------------
echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "  User    :$(id "$(whoami)")"
echo "  Workdir :$(pwd)"

if [ "${SC_BUILD_TARGET}" = "development" ]; then
  echo "$INFO" "Environment :"
  printenv | sed 's/=/: /' | sed 's/^/    /' | sort
  echo "$INFO" "Python :"
  python --version | sed 's/^/    /'
  command -v python | sed 's/^/    /'
  echo "$INFO" "PIP :"
  pip list | sed 's/^/    /'

  echo "$INFO" "Setting entrypoint to use watchmedo autorestart..."
  APP_CONFIG=server-docker-dev.yaml
  PREFIX_CMD='watchmedo auto-restart --recursive --pattern="*.py" --'

elif [ "${SC_BUILD_TARGET}" = "production" ]; then
  APP_CONFIG=server-docker-prod.yaml
  PREFIX_CMD=''
fi

# RUNNING application ----------------------------------------
if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then
  echo "$INFO" "PTVSD Debugger initializing in port 3000 with ${APP_CONFIG}"
  eval "$PREFIX_CMD" python3 -m ptvsd --host 0.0.0.0 --port 3000 -m \
    simcore_service_webserver --config $APP_CONFIG
else
  exec simcore-service-webserver --config $APP_CONFIG
fi
