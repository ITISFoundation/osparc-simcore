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
  pushd services/web/server
  make install-ci
  popd
  uv pip list
}

# isolated = these tests are (IMO) real unit tests, they do not need any dependencies and were already in the root test/unit folder before
# db slow/db medium/db fast = the tests in the test/unit/with_dbs folder (db stands for database-dependency), split in four
# folders of ~equivalent test times.

# As the plan is to strip the webserver into small micro-services I did not create now a super fancy classification but merely split the tests in ~equivalent test times.

test_isolated() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/web/server
  # NOTE: distinct --junitxml so this run does not get overwritten by test_with_db's junit reports
  make test-ci-unit test-path=isolated pytest-parameters="--numprocesses=auto --junitxml=junit-isolated.xml -o junit_family=legacy"
  popd
}

# NOTE: --numprocesses=auto spreads the folder across the runner's CPUs. pytest-simcore deploys the shared core-services stack
# (postgres, rabbit, valkey) once per session and gives each worker its own database, rabbit vhost and valkey logical database.
test_with_db() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/web/server
  echo "testing in services/web/server/tests/unit/with_dbs/$1"
  # NOTE: per-folder --junitxml so the folders do not overwrite each other's report
  make test-ci-unit test-path="with_dbs/$1" pytest-parameters="--numprocesses=auto --junitxml=junit-$1.xml -o junit_family=legacy"
  popd
}

typecheck() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  uv pip install mypy
  pushd services/web/server
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
