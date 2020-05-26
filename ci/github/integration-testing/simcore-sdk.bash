#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# in case it's a Pull request, the env are never available, default to itisfoundation to get a maybe not too old version for caching
DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG

install() {
    bash ci/helpers/ensure_python_pip.bash
    pushd packages/simcore-sdk; pip3 install -r requirements/ci.txt; popd;
    pip list -v
    # pull the test images if registry is set up, else build the images
    make pull-version || ( (make pull-cache || true) && make build-x tag-version)
    make info-images
    # pip3 install services/storage/client-sdk/python
}

test() {
    pytest --cov=simcore_sdk --durations=10 --cov-append \
      --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
      -v -m "not travis" packages/simcore-sdk/tests/integration
}

clean_up() {
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
