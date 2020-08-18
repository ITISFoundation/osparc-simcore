#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

install() {
    bash ci/helpers/ensure_python_pip.bash
    pushd services/web/server; pip3 install -r requirements/ci.txt; popd;
    pip list -v
}

# isolated = these tests are (IMO) real unit tests, they do not need any dependencies and were already in the root test/unit folder before
# db slow = it is currently the slowest test module it takes about 10 minutes (db stand for database-dependency, these tests were already in test/unit/with_dbs folder)
# db medium = are tests that take 3-5 minutes, altogether about 10 minutes (db stand for database-dependency, these tests were already in test/unit/with_dbs folder)
# db fast = all the others (db stand for database-dependency, these tests were already in test/unit/with_dbs folder)

# As the plan is to strip the webserver into small micro-services I did not create now a super fancy classification but merely split the tests in ~equivalent test times.


test_isolated() {
    pytest --cov=simcore_service_webserver --durations=10 --cov-append \
          --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
          -v -m "not travis" services/web/server/tests/unit/isolated
}

test_with_db_slow() {
    pytest --cov=simcore_service_webserver --durations=10 --cov-append \
          --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
          -v -m "not travis" services/web/server/tests/unit/with_dbs/slow
}

test_with_db_medium() {
    pytest --cov=simcore_service_webserver --durations=10 --cov-append \
          --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
          -v -m "not travis" services/web/server/tests/unit/with_dbs/medium
}

test_with_db_fast() {
    pytest --cov=simcore_service_webserver --durations=10 --cov-append \
          --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
          -v -m "not travis" services/web/server/tests/unit/with_dbs/fast
}

# Check if the function exists (bash specific)
if declare -f "$1" > /dev/null
then
  # call arguments verbatim
  "$@"
else
  # Show a helpful error
  echo "'$1' is not a known function name" >&2
  exit 1
fi
