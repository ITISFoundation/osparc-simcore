#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

install() {
  make devenv
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/datcore-adapter
  make install-ci
  popd
  uv pip list
}

test() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/datcore-adapter
  make test-ci-unit pytest-parameters="--numprocesses=auto"
  popd
}

typecheck() {
  pushd services/datcore-adapter
  make mypy
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
