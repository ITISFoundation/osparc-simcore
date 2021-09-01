#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

install() {
    bash ci/helpers/ensure_python_pip.bash
    pushd packages/service-library; pip3 install -r requirements/ci.txt; popd;
    pip list -v
}

install_aiohttp() {
    bash ci/helpers/ensure_python_pip.bash
    pushd packages/service-library; pip3 install -r requirements/ci[aiohttp].txt; popd;
    pip list -v
}

test() {
    pytest --cov=servicelib --durations=10 --cov-append \
          --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
          -v -m "not travis" --ignore=packages/service-library/tests/aiohttp \
          packages/service-library/tests
}

test_aiohttp() {
    pytest --cov=servicelib --durations=10 --cov-append \
          --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
          -v -m "not travis" packages/service-library/tests
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
