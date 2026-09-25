#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "
ERROR="ERROR: [$(basename "$0")] "

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

#
# RUNNING application
#

APP_LOG_LEVEL=${LOGLEVEL:-${LOG_LEVEL:-${LOGLEVEL:-INFO}}}
SERVER_LOG_LEVEL=$(echo "${APP_LOG_LEVEL}" | tr '[:upper:]' '[:lower:]')
echo "$INFO" "Log-level app/server: $APP_LOG_LEVEL/$SERVER_LOG_LEVEL"
echo "$INFO" "Starting service..."

#
# MEMRAY profiling (opt-in, development image only, see
# services/README.md#memory-profiling-with-memray)
#
# - NOTIFICATIONS_MEMRAY_ENABLED=true wraps uvicorn/celery with memray (takes
#   precedence over SC_BOOT_MODE=debug)
# - NOTIFICATIONS_MEMRAY_MODE=live (default) streams until a viewer attaches; with
#   the celery worker (prefork) it only tracks the master, so prefer =file there
#   (writes one capture per process to NOTIFICATIONS_MEMRAY_OUTPUT_DIR)
#
is_true() {
  case "$(printf '%s' "${1:-False}" | tr '[:upper:]' '[:lower:]')" in
    true | 1) return 0 ;;
    *) return 1 ;;
  esac
}

if is_true "${NOTIFICATIONS_MEMRAY_ENABLED:-False}"; then
  if ! command -v memray >/dev/null 2>&1; then
    echo "$ERROR" "NOTIFICATIONS_MEMRAY_ENABLED is set but memray is not installed" \
      "(only available in the development image, see requirements/_tools.in)"
    exit 1
  fi

  MEMRAY_MODE=${NOTIFICATIONS_MEMRAY_MODE:-live}
  MEMRAY_PORT=${NOTIFICATIONS_MEMRAY_PORT:-10256}
  MEMRAY_OUTPUT_DIR=${NOTIFICATIONS_MEMRAY_OUTPUT_DIR:-/tmp/memray}

  # memray options MUST precede '-m uvicorn'/'-m celery', they would otherwise be
  # passed to the wrapped launcher
  set -- run
  if is_true "${NOTIFICATIONS_MEMRAY_NATIVE:-True}"; then
    set -- "$@" --native
  fi
  if [ "${MEMRAY_MODE}" = "file" ]; then
    mkdir -p "${MEMRAY_OUTPUT_DIR}"
    MEMRAY_OUTPUT="${MEMRAY_OUTPUT_DIR}/notifications.$(date +%Y%m%dT%H%M%SZ).${$}.bin"
    echo "$INFO" "memray writing capture to ${MEMRAY_OUTPUT} ..."
    set -- "$@" --force --output "${MEMRAY_OUTPUT}"
  else
    echo "$INFO" "memray live tracking: run 'memray live ${MEMRAY_PORT}'" \
      "(e.g. via docker exec) to attach and start the service ..."
    set -- "$@" --live-remote --live-port "${MEMRAY_PORT}"
  fi

  if [ "${NOTIFICATIONS_BOOT_SERVER_MODE:-}" = "AS_CELERY_WORKER" ]; then
    if [ "${MEMRAY_MODE}" = "file" ]; then
      set -- "$@" --follow-fork # track prefork workers too (own capture per process)
    fi
    exec memray "$@" -m celery \
      --app=simcore_service_notifications.modules.celery.worker_main:app \
      worker --pool="${CELERY_POOL}" \
      --loglevel="${SERVER_LOG_LEVEL}" \
      --concurrency="${CELERY_CONCURRENCY}" \
      --hostname="${NOTIFICATIONS_WORKER_NAME}" \
      --queues="${CELERY_QUEUES}"
  else
    exec memray "$@" -m uvicorn \
      --factory simcore_service_notifications.main:app_factory \
      --host 0.0.0.0 \
      --port 8000 \
      --log-level "${SERVER_LOG_LEVEL}" \
      --no-access-log
  fi
fi

if [ "${NOTIFICATIONS_BOOT_SERVER_MODE:-}" = "AS_CELERY_WORKER" ]; then
  if [ "${SC_BOOT_MODE}" = "debug" ]; then
    exec watchmedo auto-restart \
      --directory /devel/packages \
      --directory services/notifications \
      --pattern "*.py" \
      --recursive \
      -- \
      celery \
      --app=simcore_service_notifications.modules.celery.worker_main:app \
      worker --pool="${CELERY_POOL}" \
      --loglevel="${SERVER_LOG_LEVEL}" \
      --concurrency="${CELERY_CONCURRENCY}" \
      --hostname="${NOTIFICATIONS_WORKER_NAME}" \
      --queues="${CELERY_QUEUES}"
  else
    exec celery \
      --app=simcore_service_notifications.modules.celery.worker_main:app \
      worker --pool="${CELERY_POOL}" \
      --loglevel="${SERVER_LOG_LEVEL}" \
      --concurrency="${CELERY_CONCURRENCY}" \
      --hostname="${NOTIFICATIONS_WORKER_NAME}" \
      --queues="${CELERY_QUEUES}"
  fi
else
  if [ "${SC_BOOT_MODE}" = "debug" ]; then
    reload_dir_packages=$(fdfind src /devel/packages --exec echo '--reload-dir {} ' | tr '\n' ' ')

    exec sh -c "
      cd services/notifications/src/simcore_service_notifications && \
      python -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:${NOTIFICATIONS_REMOTE_DEBUGGING_PORT} -m \
      uvicorn \
        --factory main:app_factory \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        $reload_dir_packages \
        --reload-dir . \
        --log-level \"${SERVER_LOG_LEVEL}\"
    "
  else
    exec uvicorn \
      --factory simcore_service_notifications.main:app_factory \
      --host 0.0.0.0 \
      --port 8000 \
      --log-level "${SERVER_LOG_LEVEL}" \
      --no-access-log
  fi
fi
