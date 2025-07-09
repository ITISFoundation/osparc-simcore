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

  cd services/storage
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
APP_LOG_LEVEL=${STORAGE_LOGLEVEL:-${LOG_LEVEL:-${LOGLEVEL:-INFO}}}
SERVER_LOG_LEVEL=$(echo "${APP_LOG_LEVEL}" | tr '[:upper:]' '[:lower:]')
echo "$INFO" "Log-level app/server: $APP_LOG_LEVEL/$SERVER_LOG_LEVEL"

if [ "${STORAGE_WORKER_MODE}" = "true" ]; then
  if [ "${SC_BOOT_MODE}" = "debug" ]; then
    exec watchmedo auto-restart \
      --directory /devel/packages \
      --directory services/storage \
      --pattern "*.py" \
      --recursive \
      -- \
      celery \
      --app=simcore_service_storage.modules.celery.worker_main:app \
      worker --pool=threads \
      --loglevel="${SERVER_LOG_LEVEL}" \
      --concurrency="${CELERY_CONCURRENCY}" \
      --hostname="${STORAGE_WORKER_NAME}" \
      --queues="${CELERY_QUEUES:-default}"
  else
    exec celery \
      --app=simcore_service_storage.modules.celery.worker_main:app \
      worker --pool=threads \
      --loglevel="${SERVER_LOG_LEVEL}" \
      --concurrency="${CELERY_CONCURRENCY}" \
      --hostname="${STORAGE_WORKER_NAME}" \
      --queues="${CELERY_QUEUES:-default}"
  fi
else
  if [ "${SC_BOOT_MODE}" = "debug" ]; then
    reload_dir_packages=$(fdfind --type directory --max-depth 3 --glob '*/src/*' --exclude '*.*' --exec echo '--reload-dir {} \ ' /devel/packages)

    exec sh -c "
    cd services/storage/src/simcore_service_storage && \
    python -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:${STORAGE_REMOTE_DEBUGGING_PORT} -m uvicorn main:app \
      --host 0.0.0.0 \
      --port ${STORAGE_PORT} \
      --reload \
      $reload_dir_packages
      --reload-dir . \
      --log-level \"${SERVER_LOG_LEVEL}\"
  "
  else
    exec uvicorn simcore_service_storage.main:app \
      --host 0.0.0.0 \
      --port ${STORAGE_PORT} \
      --log-level "${SERVER_LOG_LEVEL}"
  fi
fi
