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

  cd services/web/server || exit 1
  pip --quiet --no-cache-dir install -r requirements/dev.txt
  cd - || exit 1
  echo "$INFO" "PIP :"
  pip list | sed 's/^/    /'

  APP_CONFIG=server-docker-dev.yaml
elif [ "${SC_BUILD_TARGET}" = "production" ]; then
  APP_CONFIG=server-docker-prod.yaml
fi

# RUNNING application ----------------------------------------
echo "$INFO" "Selected config $APP_CONFIG"

# NOTE: the number of workers ```(2 x $num_cores) + 1``` is the official recommendation [https://docs.gunicorn.org/en/latest/design.html#how-many-workers]

if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then
  # NOTE: needs ptvsd installed
  echo "$INFO" "PTVSD Debugger initializing in port 3000 with ${APP_CONFIG}"
  # exec python3 -m ptvsd --host 0.0.0.0 --port 3000 -m \

  exec gunicorn simcore_service_webserver.cli:app_factory \
    --bind 0.0.0.0:8080 \
    --worker-class aiohttp.GunicornWebWorker \
    --workers="${WEBSERVER_GUNICORN_WORKERS:-1}" \
    --name="webserver_$(hostname)_$(date +'%Y-%m-%d_%T')_$$" \
    --reload

  # simcore_service_webserver --config $APP_CONFIG

else
  exec gunicorn simcore_service_webserver.cli:app_factory \
    --bind 0.0.0.0:8080 \
    --worker-class aiohttp.GunicornWebWorker \
    --workers="${WEBSERVER_GUNICORN_WORKERS:-1}" \
    --name="webserver_$(hostname)_$(date +'%Y-%m-%d_%T')_$$"
  # exec simcore-service-webserver --config $APP_CONFIG
fi
