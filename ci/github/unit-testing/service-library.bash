#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

# NOTE: notice that the CI uses [all]
install_all() {
  make devenv
  # shellcheck source=/dev/null
  source .venv/bin/activate
  sudo ./ci/github/helpers/install_7zip.bash
  pushd packages/service-library
  make "install-ci[all]"
  popd
  uv pip list
}

test_all() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd packages/service-library
  # NOTE: xdist workers share ONE docker stack (see packages/pytest-simcore/src/pytest_simcore/helpers/xdist.py);
  # the rabbit/valkey containers are shared too, so tests pausing or restarting them are marked
  # `docker_exclusive` and run alone (see the pytest_simcore.xdist_docker_daemon plugin)
  make "test-ci[all]" pytest-parameters="--numprocesses=auto"
  popd
}

typecheck() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  uv pip install mypy
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
