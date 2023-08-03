#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

install() {
  bash ci/helpers/ensure_python_pip.bash
  make devenv
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/dynamic-sidecar
  make install-ci
  popd
  .venv/bin/pip list --verbose
  make info-images
}

test() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/dynamic-sidecar
  make test-ci-integration
  popd
}

clean_up() {
  docker images
  make down
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
