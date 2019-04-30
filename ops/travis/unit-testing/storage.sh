#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

FOLDER_CHECKS=(api/ storage packages/)

before_install() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        bash ops/travis/helpers/show_system_versions
        bash ops/travis/helpers/install_docker_compose
    fi
}

install() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        pip install --upgrade pip wheel setuptools && pip3 --version
        pushd services/storage; pip3 install -r requirements/prod.txt; popd
        pushd services/storage; pip3 install -r tests/requirements.txt; popd
        pip3 install services/storage/client-sdk/python
    fi
}

before_script() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        pip freeze
        docker images
    fi
}

script() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        pytest --cov=simcore_service_storage --cov-append -v -m "not travis" services/storage/tests
    else
        echo "No changes detected. Skipping unit-testing of storage."
    fi
}

after_success() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        coveralls
        codecov
    fi
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
