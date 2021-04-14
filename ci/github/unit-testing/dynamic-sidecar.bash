#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

install() {
    bash ci/helpers/ensure_python_pip.bash;
    pushd services/dynamic-sidecar; pip3 install -r requirements/ci.txt -r requirements/_tools.txt; popd;
    pip list -v
}

codestyle(){
    pushd services/dynamic-sidecar
    echo "isort"
    isort --check setup.py src/simcore_service_dynamic_sidecar tests
    echo "black"
    black --check src/simcore_service_dynamic_sidecar tests/
    echo "pylint"
    pylint --rcfile=../../.pylintrc src/simcore_service_dynamic_sidecar tests/
    echo "mypy"
    mypy src/simcore_service_dynamic_sidecar tests/ --ignore-missing-imports
    popd
}

test() {
    pytest --cov=simcore_service_dynamic_sidecar --durations=10 --cov-append \
          --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
          -v -m "not travis" services/dynamic-sidecar/tests/unit
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
