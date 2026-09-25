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

  cd services/autoscaling
  uv pip --quiet sync --link-mode=copy requirements/dev.txt
  cd -
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

APP_LOG_LEVEL=${AUTOSCALING_LOGLEVEL:-${LOG_LEVEL:-${LOGLEVEL:-INFO}}}
SERVER_LOG_LEVEL=$(echo "${APP_LOG_LEVEL}" | tr '[:upper:]' '[:lower:]')
echo "$INFO" "Log-level app/server: $APP_LOG_LEVEL/$SERVER_LOG_LEVEL"
echo "$INFO" "Starting service..."

#
# MEMRAY profiling (opt-in, see services/autoscaling/README.md)
#
# - AUTOSCALING_MEMRAY_ENABLED=true wraps uvicorn with memray to hunt memory leaks
# - AUTOSCALING_MEMRAY_MODE=live (default) streams allocations over a socket and
#   waits for a viewer: docker exec <container> memray live <AUTOSCALING_MEMRAY_PORT>
#   (uvicorn only starts once the viewer attaches, hence also the healthcheck will
#   report unhealthy until then)
# - AUTOSCALING_MEMRAY_MODE=file writes a capture file to AUTOSCALING_MEMRAY_OUTPUT_DIR
#   (mount it to the host) that can be analyzed after the service stops
#   (e.g. memray flamegraph --leaks <file>.bin, *inside* the container for the
#   native symbols)
# - AUTOSCALING_MEMRAY_NATIVE=true (default) also tracks native (C/C++) allocations
# - NOTE: takes precedence over SC_BOOT_MODE=debug (debugpy and memray cannot be
#   combined), and memray is only pre-installed in the development image
#
is_true() {
  case "$(printf '%s' "${1:-False}" | tr '[:upper:]' '[:lower:]')" in
    true | 1) return 0 ;;
    *) return 1 ;;
  esac
}

if is_true "${AUTOSCALING_MEMRAY_ENABLED:-False}"; then
  if ! command -v memray >/dev/null 2>&1; then
    echo "$ERROR" "AUTOSCALING_MEMRAY_ENABLED is set but memray is not installed" \
      "(only available in the development image, see requirements/_tools.in)"
    exit 1
  fi

  MEMRAY_MODE=${AUTOSCALING_MEMRAY_MODE:-live}
  MEMRAY_PORT=${AUTOSCALING_MEMRAY_PORT:-10253}
  MEMRAY_OUTPUT_DIR=${AUTOSCALING_MEMRAY_OUTPUT_DIR:-/tmp/memray}

  # memray options MUST precede '-m uvicorn', otherwise they are passed to uvicorn
  set -- run
  if is_true "${AUTOSCALING_MEMRAY_NATIVE:-True}"; then
    set -- "$@" --native
  fi
  if [ "${MEMRAY_MODE}" = "file" ]; then
    mkdir -p "${MEMRAY_OUTPUT_DIR}"
    MEMRAY_OUTPUT="${MEMRAY_OUTPUT_DIR}/autoscaling.$(date +%Y%m%dT%H%M%SZ).${$}.bin"
    echo "$INFO" "memray writing capture to ${MEMRAY_OUTPUT} ..."
    set -- "$@" --force --output "${MEMRAY_OUTPUT}"
  else
    echo "$INFO" "memray live tracking: run 'memray live ${MEMRAY_PORT}'" \
      "(e.g. via docker exec) to attach and start the service ..."
    set -- "$@" --live-remote --live-port "${MEMRAY_PORT}"
  fi

  exec memray "$@" -m uvicorn \
    --factory simcore_service_autoscaling.main:app_factory \
    --host 0.0.0.0 \
    --log-level "${SERVER_LOG_LEVEL}"
fi

if [ "${SC_BOOT_MODE}" = "debug" ]; then
  reload_dir_packages=$(fdfind src /devel/packages --exec echo '--reload-dir {} ' | tr '\n' ' ')

  exec sh -c "
    cd services/autoscaling/src/simcore_service_autoscaling && \
    python -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:${AUTOSCALING_REMOTE_DEBUGGING_PORT} -m \
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
    --factory simcore_service_autoscaling.main:app_factory \
    --host 0.0.0.0 \
    --log-level "${SERVER_LOG_LEVEL}"
fi
