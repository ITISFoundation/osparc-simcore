#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

# BOOTING application ---------------------------------------------
echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "  User    :$(id "$(whoami)")"
echo "  Workdir :$(pwd)"
echo "  env     :$(env)"

if [ "${SC_BUILD_TARGET}" = "development" ]; then
  echo "$INFO" "Environment :"
  printenv | sed 's/=/: /' | sed 's/^/    /' | sort
  echo "$INFO" "Python :"
  python --version | sed 's/^/    /'
  command -v python | sed 's/^/    /'
  cd services/osparc-gateway-server || exit 1
  pip install --no-cache-dir -r requirements/dev.txt
  cd - || exit 1
  echo "$INFO" "PIP :"
  pip list | sed 's/^/    /'
fi

if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then
  exec watchmedo auto-restart \
      --recursive \
      --pattern="*.py;*/src/*" \
      --ignore-patterns="*test*;pytest_simcore/*;setup.py;*ignore*" \
      --ignore-directories -- \
      osparc-gateway-server \
      --config "${GATEWAY_SERVER_CONFIG_FILE_CONTAINER}" \
      --debug
else
  exec osparc-gateway-server \
    --config "${GATEWAY_SERVER_CONFIG_FILE_CONTAINER}"
fi
