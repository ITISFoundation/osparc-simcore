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

  # NOTE: uv does not like this requirement file...
  cd /devel/services/dynamic-sidecar
  uv pip --quiet sync --link-mode=copy requirements/dev.txt
  cd -
  echo "$INFO" "PIP :"
  pip list | sed 's/^/    /'
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
APP_LOG_LEVEL=${DYNAMIC_SIDECAR_LOG_LEVEL:-${LOG_LEVEL:-${LOGLEVEL:-INFO}}}
DYNAMIC_SIDECAR_REMOTE_DEBUGGING_PORT=${DYNAMIC_SIDECAR_REMOTE_DEBUGGING_PORT:-3000}
SERVER_LOG_LEVEL=$(echo "${APP_LOG_LEVEL}" | tr '[:upper:]' '[:lower:]')
echo "$INFO" "Log-level app/server: $APP_LOG_LEVEL/$SERVER_LOG_LEVEL"

if [ "${SC_BOOT_MODE}" = "debug" ]; then
  reload_dir_packages=$(fdfind src /devel/packages --exec echo '--reload-dir {} ' | tr '\n' ' ')

  exec sh -c "
    cd services/dynamic-sidecar/src/simcore_service_dynamic_sidecar && \
    python -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:${DYNAMIC_SIDECAR_REMOTE_DEBUGGING_PORT} -m uvicorn main:the_app \
      --host 0.0.0.0 \
      --reload \
      $reload_dir_packages \
      --reload-dir . \
      --log-level \"${SERVER_LOG_LEVEL}\"
  "
else
  exec uvicorn simcore_service_dynamic_sidecar.main:the_app \
    --host 0.0.0.0 \
    --log-level "${SERVER_LOG_LEVEL}"
fi
