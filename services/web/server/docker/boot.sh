#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "
ERROR="ERROR: [$(basename "$0")] "

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

  cd services/web/server
  uv pip --quiet sync --link-mode=copy requirements/dev.txt
  cd -
  echo "$INFO" "PIP :"
  uv pip list

  APP_CONFIG=server-docker-dev.yaml
elif [ "${SC_BUILD_TARGET}" = "production" ]; then
  APP_CONFIG=server-docker-prod.yaml
fi

if [ "${SC_BOOT_MODE}" = "debug" ]; then
  # NOTE: production does NOT pre-installs debugpy
  if command -v uv >/dev/null 2>&1; then
    uv pip install --link-mode=copy debugpy
  else
    pip install debugpy
  fi
fi

APP_LOG_LEVEL=${WEBSERVER_LOGLEVEL:-${LOG_LEVEL:-${LOGLEVEL:-INFO}}}
SERVER_LOG_LEVEL=$(echo "${APP_LOG_LEVEL}" | tr '[:upper:]' '[:lower:]')

# RUNNING application ----------------------------------------
echo "$INFO" "Selected config ${APP_CONFIG}"
echo "$INFO" "Log-level app/server: $APP_LOG_LEVEL/$SERVER_LOG_LEVEL"
echo "$INFO" "Starting service..."

# NOTE: the number of workers ```(2 x $num_cores) + 1``` is
# the official recommendation https://docs.gunicorn.org/en/latest/design.html#how-many-workers
# For now we set it to 1 to check what happens with websockets
#
# SEE also https://docs.aiohttp.org/en/stable/deployment.html#start-gunicorn
#
# NOTE: GUNICORN_CMD_ARGS is affecting as well gunicorn
# SEE https://docs.gunicorn.org/en/latest/settings.html#settings
echo "$INFO" "GUNICORN_CMD_ARGS: $GUNICORN_CMD_ARGS"

#
# MEMRAY profiling (opt-in, development image only, see
# services/README.md#memory-profiling-with-memray)
#
# - WEBSERVER_MEMRAY_ENABLED=true wraps gunicorn with memray (takes precedence over
#   SC_BOOT_MODE=debug)
# - gunicorn forks its workers and memray cannot combine live tracking with
#   --follow-fork, therefore 'file' (the default here) writes one capture per
#   process (master + workers) to WEBSERVER_MEMRAY_OUTPUT_DIR. 'live' only tracks
#   the gunicorn master process.
#
is_true() {
  case "$(printf '%s' "${1:-False}" | tr '[:upper:]' '[:lower:]')" in
    true | 1) return 0 ;;
    *) return 1 ;;
  esac
}

if is_true "${WEBSERVER_MEMRAY_ENABLED:-False}"; then
  if ! command -v memray >/dev/null 2>&1; then
    echo "$ERROR" "WEBSERVER_MEMRAY_ENABLED is set but memray is not installed" \
      "(only available in the development image, see requirements/_tools.in)"
    exit 1
  fi

  MEMRAY_MODE=${WEBSERVER_MEMRAY_MODE:-file}
  MEMRAY_PORT=${WEBSERVER_MEMRAY_PORT:-10248}
  MEMRAY_OUTPUT_DIR=${WEBSERVER_MEMRAY_OUTPUT_DIR:-/tmp/memray}

  # memray options MUST precede '-m gunicorn', otherwise they are passed to gunicorn
  set -- run
  if is_true "${WEBSERVER_MEMRAY_NATIVE:-True}"; then
    set -- "$@" --native
  fi
  if [ "${MEMRAY_MODE}" = "live" ]; then
    echo "$INFO" "memray live tracking (gunicorn MASTER process only): run"
    echo "$INFO" "  'memray live ${MEMRAY_PORT}' (e.g. via docker exec) to attach ..."
    set -- "$@" --live-remote --live-port "${MEMRAY_PORT}"
  else
    mkdir -p "${MEMRAY_OUTPUT_DIR}"
    MEMRAY_OUTPUT="${MEMRAY_OUTPUT_DIR}/webserver.$(date +%Y%m%dT%H%M%SZ).${$}.bin"
    echo "$INFO" "memray writing captures (master + workers) to ${MEMRAY_OUTPUT}.* ..."
    set -- "$@" --force --output "${MEMRAY_OUTPUT}" --follow-fork
  fi

  exec memray "$@" -m gunicorn simcore_service_webserver.cli:app_factory \
    --log-level="${SERVER_LOG_LEVEL}" \
    --bind 0.0.0.0:8080 \
    --worker-class aiohttp.GunicornUVLoopWebWorker \
    --workers="${WEBSERVER_GUNICORN_WORKERS:-1}" \
    --name="webserver_$(hostname)_$(date +'%Y-%m-%d_%T')_$$" \
    --access-logfile='-' \
    --access-logformat='%a %t "%r" %s %b [%Dus] "%{Referer}i" "%{User-Agent}i"' \
    --worker-tmp-dir=/dev/shm
fi

if [ "${SC_BOOT_MODE}" = "debug" ]; then
  # NOTE: ptvsd is programmatically enabled inside of the service
  # this way we can have reload in place as well
  exec python -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:"${WEBSERVER_REMOTE_DEBUGGING_PORT}" -m gunicorn simcore_service_webserver.cli:app_factory \
    --log-level="${SERVER_LOG_LEVEL}" \
    --bind 0.0.0.0:8080 \
    --worker-class aiohttp.GunicornUVLoopWebWorker \
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
    --worker-class aiohttp.GunicornUVLoopWebWorker \
    --workers="${WEBSERVER_GUNICORN_WORKERS:-1}" \
    --name="webserver_$(hostname)_$(date +'%Y-%m-%d_%T')_$$" \
    --access-logfile='-' \
    --access-logformat='%a %t "%r" %s %b [%Dus] "%{Referer}i" "%{User-Agent}i"' \
    --worker-tmp-dir=/dev/shm
fi
