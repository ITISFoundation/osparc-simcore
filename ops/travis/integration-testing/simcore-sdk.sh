#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

current_branch=$(exec ops/travis/helpers/slugify_branch.sh)
export DOCKER_IMAGE_PREFIX=${DOCKER_REGISTRY}/
export DOCKER_IMAGE_TAG=$current_branch-latest

FOLDER_CHECKS=(packages/ simcore-sdk storage/ simcore-sdk.sh)

before_install() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        bash ops/travis/helpers/install_docker_compose
        bash ops/travis/helpers/show_system_versions
    fi
}

install() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        pip install --upgrade pip wheel setuptools && pip3 --version
        pushd packages/service-library; pip3 install -r requirements/dev.txt; popd
        pip3 install packages/s3wrapper[test]
        pip3 install packages/simcore-sdk[test]
        pip3 install services/storage/client-sdk/python
    fi
}

before_script() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        pip freeze
        # pull the test images if registry is set up, else build the images
        make pull || make build
        docker images
    fi
}

script() {
    if bash ops/travis/helpers/test_for_changes.sh "${FOLDER_CHECKS[@]}";
    then
        pytest --color=yes --cov=simcore_sdk --cov-append -v packages/simcore-sdk/tests
    else
        echo "No changes detected. Skipping integration-testing of simcore-sdk."
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
