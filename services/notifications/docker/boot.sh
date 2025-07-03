#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "$INFO" "User :$(id "$(whoami)")"
echo "$INFO" "Workdir : $(pwd)"

#
# DEVELOPMENT MODE
#
# - prints environ info
# - installs requirements in mounted volume
#
if [ "${SC_BUILD_TARGET}" = "development" ]; then
  echo "$INFO" "Environment :"
  printenv | sed 's/=/: /' | sed 's/^/    /' | sort
  echo "$INFO" "Python :"
  python --version | sed 's/^/    /'
  command -v python | sed 's/^/    /'

  cd services/notifications
  uv pip --quiet sync requirements/dev.txt
  cd -
  echo "$INFO" "PIP :"
  uv pip list
fi

if [ "${SC_BOOT_MODE}" = "debug" ]; then
  # NOTE: production does NOT pre-installs debugpy
  if command -v uv >/dev/null 2>&1; then
    uv pip install debugpy
  else
    pip install debugpy
  fi
fi

#
# RUNNING application
#

APP_LOG_LEVEL=${LOGLEVEL:-${LOG_LEVEL:-${LOGLEVEL:-INFO}}}
SERVER_LOG_LEVEL=$(echo "${APP_LOG_LEVEL}" | tr '[:upper:]' '[:lower:]')
echo "$INFO" "Log-level app/server: $APP_LOG_LEVEL/$SERVER_LOG_LEVEL"

if [ "${NOTIFICATIONS_WORKER_MODE:-}" = "true" ]; then
  if [ "${SC_BOOT_MODE}" = "debug" ]; then
    exec watchmedo auto-restart \
      --directory /devel/packages \
      --directory services/notifications \
      --pattern "*.py" \
      --recursive \
      -- \
      celery \
      --app=simcore_service_notifications.modules.celery.worker_main:the_celery_app \
      worker --pool=threads \
      --loglevel="${SERVER_LOG_LEVEL}" \
      --concurrency="${CELERY_CONCURRENCY}" \
      --hostname="${NOTIFICATIONS_WORKER_NAME}" \
      --queues="${CELERY_QUEUES:-default}"
  else
    exec celery \
      --app=simcore_service_notifications.modules.celery.worker_main:the_celery_app \
      worker --pool=threads \
      --loglevel="${SERVER_LOG_LEVEL}" \
      --concurrency="${CELERY_CONCURRENCY}" \
      --hostname="${NOTIFICATIONS_WORKER_NAME}" \
      --queues="${CELERY_QUEUES:-default}"
  fi
else
  if [ "${SC_BOOT_MODE}" = "debug" ]; then
    reload_dir_packages=$(find /devel/packages -maxdepth 3 -type d -path "*/src/*" ! -path "*.*" -exec echo '--reload-dir {} \' \;)

    exec sh -c "
      cd services/notifications/src/simcore_service_notifications && \
      python -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:${NOTIFICATIONS_REMOTE_DEBUGGING_PORT} -m uvicorn main:the_app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        $reload_dir_packages
        --reload-dir . \
        --log-level \"${SERVER_LOG_LEVEL}\"
    "
  else
    exec uvicorn simcore_service_notifications.main:the_app \
      --host 0.0.0.0 \
      --port 8000 \
      --log-level "${SERVER_LOG_LEVEL}" \
      --no-access-log
  fi
fi
