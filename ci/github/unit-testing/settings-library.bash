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
  pushd packages/settings-library
  make install-ci
  popd
  .venv/bin/pip list --verbose
}

test() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd packages/settings-library
  make tests-ci
  popd
}

typecheck() {
  pushd services/settings-library
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
