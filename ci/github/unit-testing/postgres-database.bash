#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

install() {
    bash ci/helpers/ensure_python_pip.bash
    pushd packages/postgres-database; pip3 install -r requirements/ci.txt; popd;
    pip list -v
}

test() {
    pytest \
      --color=yes \
      --durations=10 \
      --cov=simcore_postgres_database \
      --cov-append \
      --cov-report=term-missing \
      --cov-report=xml \
      --cov-config=.coveragerc \
      --verbose \
      packages/postgres-database/tests
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
