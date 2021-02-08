#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

FOLDER_CHECKS=(api/ director packages/ .travis.yml)

before_install() {
    if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}";
    then
        bash ci/travis/helpers/update-docker.bash
        bash ci/travis/helpers/install-docker-compose.bash
        bash ci/helpers/show_system_versions.bash
    fi
}

install() {
    if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}";
    then
        bash ci/helpers/ensure_python_pip.bash
        pushd services/director; pip3 install -r requirements/ci.txt; popd
    fi
}

before_script() {
    if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}";
    then
        pip list -v
    fi
}

script() {
    if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}";
    then
        pytest --cov=simcore_service_director --durations=10 --cov-append \
          --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
          -v -m "not travis" services/director/tests
    else
        echo "No changes detected. Skipping unit-testing of director."
    fi
}

after_success() {
    if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}";
    then
        coveralls
    fi
}

after_failure() {
    echo "failure... you can always write something more interesting here..."
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
