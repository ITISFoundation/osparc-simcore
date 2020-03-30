#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# in case it's a Pull request, the env are never available, default to itisfoundation to get a maybe not too old version for caching
DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG

FOLDER_CHECKS=(packages/ simcore-sdk storage/ simcore-sdk .travis.yml)

if [[ ! -v DOCKER_REGISTRY ]]; then
    export DOCKER_REGISTRY="itisfoundation"
fi


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
        pushd packages/simcore-sdk; pip3 install -r requirements/ci.txt; popd;
    fi
}

before_script() {
    if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}";
    then
        pip list -v
        # pull the test images if registry is set up, else build the images
        make pull-version || ( (make pull-cache || true) && make build tag-version)
        make info-images
    fi
}

script() {
    if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}";
    then
        pytest --cov=simcore_sdk --durations=10 --cov-append \
                --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
                -v -m "not travis" packages/simcore-sdk/tests/integration
    else
        echo "No changes detected. Skipping integration-testing of simcore-sdk."
    fi
}

after_success() {
    if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}";
    then
        coveralls
    fi
}

after_failure() {
    docker images
    make down
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
