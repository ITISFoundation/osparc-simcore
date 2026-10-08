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
  pushd services/catalog
  make install-ci
  popd
  uv pip list
}

test() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/catalog
  # NOTE: with_dbs tests are safe to run alongside the rest with pytest-xdist: they share
  # ONE docker stack and each xdist worker gets its own database clone/rabbit vhost/S3 bucket
  # (see packages/pytest-simcore/src/pytest_simcore/helpers/xdist.py). Tests that need
  # exclusive access to the shared docker daemon take a cross-worker read/write lock instead
  # (@pytest.mark.docker_exclusive, see the docker_daemon_access fixture in
  # packages/pytest-simcore/src/pytest_simcore/docker_swarm.py).
  # TEMP (matrix experiment): allow overriding the xdist args from CI
  make test-ci-unit pytest-parameters="${1:---numprocesses=auto}"
  popd
}

typecheck() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  uv pip install mypy
  pushd services/catalog
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
