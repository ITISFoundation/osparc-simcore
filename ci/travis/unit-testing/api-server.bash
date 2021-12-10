#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

FOLDER_CHECKS=(api/ api-server packages/ .travis.yml)

before_install() {
  if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}"; then
    bash ci/travis/helpers/update-docker.bash
    bash ci/helpers/show_system_versions.bash
    bash ci/travis/helpers/install-docker-compose.bash
  fi
}

install() {
  if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}"; then
    bash ci/helpers/ensure_python_pip.bash
    pushd services/api-server
    pip3 install -r requirements/ci.txt
    popd
  fi
}

before_script() {
  if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}"; then
    pip list -v
  fi
}

script() {
  if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}"; then
    pytest --log-format="%(asctime)s %(levelname)s %(message)s" \
      --log-date-format="%Y-%m-%d %H:%M:%S" \
      --cov=simcore_service_api_server --durations=10 --cov-append \
      --color=yes --cov-report=term-missing --cov-report=xml \
      -v -m "not travis" services/api-server/tests/unit
  else
    echo "No changes detected. Skipping unit-testing of api-server."
  fi
}

after_success() {
  if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}"; then
    coveralls
    codecov
  fi
}

after_failure() {
  echo "failure... you can always write something more interesting here..."
}

# Check if the function exists (bash specific)
if declare -f "$1" >/dev/null; then
  # call arguments verbatim
  "$@"
else
  # Show a helpful error
  echo "'$1' is not a known function name" >&2
  exit 1
fi
