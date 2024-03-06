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
  pip install uv
  uv pip --quiet --no-cache-dir install -r requirements/dev.txt
  cd - || exit 1
  echo "$INFO" "PIP :"
  uv pip list | sed 's/^/    /'

  APP_CONFIG=server-docker-dev.yaml
elif [ "${SC_BUILD_TARGET}" = "production" ]; then
  APP_CONFIG=server-docker-prod.yaml
fi

APP_LOG_LEVEL=${WEBSERVER_LOGLEVEL:-${LOG_LEVEL:-${LOGLEVEL:-INFO}}}
SERVER_LOG_LEVEL=$(echo "${APP_LOG_LEVEL}" | tr '[:upper:]' '[:lower:]')

# RUNNING application ----------------------------------------
echo "$INFO" "Selected config ${APP_CONFIG}"
echo "$INFO" "Log-level app/server: $APP_LOG_LEVEL/$SERVER_LOG_LEVEL"

# NOTE: the number of workers ```(2 x $num_cores) + 1``` is
# the official recommendation [https://docs.gunicorn.org/en/latest/design.html#how-many-workers]
# For now we set it to 1 to check what happens with websockets

if [ "${SC_BOOT_MODE}" = "debug" ]; then
  # NOTE: ptvsd is programmatically enabled inside of the service
  # this way we can have reload in place as well
  exec python -m debugpy --listen 0.0.0.0:"${WEBSERVER_REMOTE_DEBUGGING_PORT}" -m gunicorn simcore_service_webserver.cli:app_factory \
    --log-level="${SERVER_LOG_LEVEL}" \
    --bind 0.0.0.0:8080 \
    --worker-class aiohttp.GunicornWebWorker \
    --workers="${WEBSERVER_GUNICORN_WORKERS:-1}" \
    --name="webserver_$(hostname)_$(date +'%Y-%m-%d_%T')_$$" \
    --access-logfile='-' \
    --access-logformat='%a %t "%r" %s %b [%Dus] "%{Referer}i" "%{User-Agent}i"' \
    --worker-tmp-dir=/dev/shm \
    --reload

else

  exec gunicorn simcore_service_webserver.cli:app_factory \
    --log-level="${SERVER_LOG_LEVEL}" \
    --bind 0.0.0.0:8080 \
    --worker-class aiohttp.GunicornWebWorker \
    --workers="${WEBSERVER_GUNICORN_WORKERS:-1}" \
    --name="webserver_$(hostname)_$(date +'%Y-%m-%d_%T')_$$" \
    --access-logfile='-' \
    --access-logformat='%a %t "%r" %s %b [%Dus] "%{Referer}i" "%{User-Agent}i"' \
    --worker-tmp-dir=/dev/shm
fi
