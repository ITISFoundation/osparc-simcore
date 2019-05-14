#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

FOLDER_CHECKS=(packages/ simcore-sdk .travis.yml)

before_install() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        bash ops/travis/helpers/install_docker_compose.sh
        bash ops/travis/helpers/show_system_versions.sh
    fi
}

install() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        bash ops/travis/helpers/ensure_python_pip
        pushd packages/simcore-sdk; pip3 install -r requirements/ci.txt; popd
    fi
}

before_script() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        pip list -v
    fi
}

script() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        pytest --cov=s3wrapper --cov-append -v packages/s3wrapper/tests
        # pytest --cov=servicelib --cov-append -v packages/service-library/tests
    else
        echo "No changes detected. Skipping unit-testing of simcore-sdk."
    fi
}

after_success() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        coveralls
        codecov
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
