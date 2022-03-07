#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

install() {
  bash ci/helpers/ensure_python_pip.bash
  pushd services/web/server
  pip3 install -r requirements/ci.txt
  popd
  pip list -v
}

# isolated = these tests are (IMO) real unit tests, they do not need any dependencies and were already in the root test/unit folder before
# db slow = it is currently the slowest test module it takes about 10 minutes (db stand for database-dependency, these tests were already in test/unit/with_dbs folder)
# db medium = are tests that take 3-5 minutes, altogether about 10 minutes (db stand for database-dependency, these tests were already in test/unit/with_dbs folder)
# db fast = all the others (db stand for database-dependency, these tests were already in test/unit/with_dbs folder)

# As the plan is to strip the webserver into small micro-services I did not create now a super fancy classification but merely split the tests in ~equivalent test times.

test_isolated() {
  pytest --log-format="%(asctime)s %(levelname)s %(message)s" \
    --log-date-format="%Y-%m-%d %H:%M:%S" \
    --cov=simcore_service_webserver --durations=10 --cov-append \
    --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
    --asyncio-mode=auto \
    -v -m "not travis" services/web/server/tests/unit/isolated
}

test_with_db() {
  echo "testing in services/web/server/tests/unit/with_dbs/$1"
  pytest --log-format="%(asctime)s %(levelname)s %(message)s" \
    --log-date-format="%Y-%m-%d %H:%M:%S" \
    --cov=simcore_service_webserver --durations=10 --cov-append \
    --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
    --asyncio-mode=auto \
    -v -m "not travis" "services/web/server/tests/unit/with_dbs/$1"
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
