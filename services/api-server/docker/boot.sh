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

  cd services/api-server
  uv pip --quiet sync --link-mode=copy requirements/dev.txt
  cd -
  echo "$INFO" "PIP :"
  uv pip list
fi

if [ "${SC_BOOT_MODE}" = "debug" ]; then
  # NOTE: production does NOT pre-installs debugpy
  if command -v uv >/dev/null 2>&1; then
    uv pip install --link-mode=copy debugpy
  else
    pip install debugpy
  fi
fi

# RUNNING application ----------------------------------------
APP_LOG_LEVEL=${API_SERVER_LOGLEVEL:-${LOG_LEVEL:-${LOGLEVEL:-INFO}}}
SERVER_LOG_LEVEL=$(echo "${APP_LOG_LEVEL}" | tr '[:upper:]' '[:lower:]')
echo "$INFO" "Log-level app/server: $APP_LOG_LEVEL/$SERVER_LOG_LEVEL"

if [ "${API_SERVER_WORKER_MODE}" = "true" ]; then
  if [ "${SC_BOOT_MODE}" = "debug" ]; then
    exec watchmedo auto-restart \
      --directory /devel/packages \
      --directory services/api-server \
      --pattern "*.py" \
      --recursive \
      -- \
      celery \
      --app=boot_celery_worker:app \
      --workdir=services/api-server/docker \
      worker --pool=threads \
      --loglevel="${API_SERVER_LOGLEVEL}" \
      --concurrency="${CELERY_CONCURRENCY}" \
      --hostname="${API_SERVER_WORKER_NAME}" \
      --queues="${CELERY_QUEUES:-default}"
  else
    exec celery \
      --app=boot_celery_worker:app \
      --workdir=services/api-server/docker \
      worker --pool=threads \
      --loglevel="${API_SERVER_LOGLEVEL}" \
      --concurrency="${CELERY_CONCURRENCY}" \
      --hostname="${API_SERVER_WORKER_NAME}" \
      --queues="${CELERY_QUEUES:-default}"
  fi
else
  if [ "${SC_BOOT_MODE}" = "debug" ]; then
    reload_dir_packages=$(fdfind src /devel/packages --exec echo '--reload-dir {} ' | tr '\n' ' ')

    exec sh -c "
      cd services/api-server/src/simcore_service_api_server && \
      python -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:${API_SERVER_REMOTE_DEBUG_PORT} -m \
      uvicorn \
        --factory main:app_factory \
        --host 0.0.0.0 \
        --reload \
        $reload_dir_packages \
        --reload-dir . \
        --log-level \"${SERVER_LOG_LEVEL}\"
    "
  else
    exec uvicorn \
      --factory simcore_service_api_server.main:app_factory \
      --host 0.0.0.0 \
      --log-level "${SERVER_LOG_LEVEL}"
  fi
fi
