#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

install() {
  bash ci/helpers/ensure_python_pip.bash
  pushd services/dynamic-sidecar
  pip3 install -r requirements/ci.txt -r requirements/_tools.txt
  popd
  pip list -v
}

codestyle() {
  pushd services/dynamic-sidecar
  make codestyle-ci
  popd
}

test() {
  pushd services/dynamic-sidecar
  make test-ci-unit
  popd
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
