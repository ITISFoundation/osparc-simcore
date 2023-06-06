#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

# NOTE: notice that the CI uses [all]
# TODO: add STEPS where pip-sync individual extras and test separately
install_all() {
  bash ci/helpers/ensure_python_pip.bash
  make devenv
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd packages/service-library
  make "install-ci[all]"
  popd
  .venv/bin/pip list --verbose
}

test_all() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd packages/service-library
  make "test-ci[all]"
  popd
}

typecheck() {
  pushd packages/service-library
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
