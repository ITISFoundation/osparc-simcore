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
  pushd services/web/server
  make install-ci
  popd
  .venv/bin/pip list --verbose
}

# isolated = these tests are (IMO) real unit tests, they do not need any dependencies and were already in the root test/unit folder before
# db slow = it is currently the slowest test module it takes about 10 minutes (db stand for database-dependency, these tests were already in test/unit/with_dbs folder)
# db medium = are tests that take 3-5 minutes, altogether about 10 minutes (db stand for database-dependency, these tests were already in test/unit/with_dbs folder)
# db fast = all the others (db stand for database-dependency, these tests were already in test/unit/with_dbs folder)

# As the plan is to strip the webserver into small micro-services I did not create now a super fancy classification but merely split the tests in ~equivalent test times.

test_isolated() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/web/server
  make test-ci-unit test-path=isolated pytest-parameters="--numprocesses=auto"
  popd
}

test_with_db() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/web/server
  echo "testing in services/web/server/tests/unit/with_dbs/$1"
  make test-ci-unit test-path="with_dbs/$1"
  popd
}

typecheck() {
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
