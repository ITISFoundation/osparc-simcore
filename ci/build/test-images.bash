#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG

pull_images() {
    {
        make pull-cache
    } || {
        # if this is the very first build in a branch
        # there is no cache available so let's use the main one if possible
        if [[ -v DOCKER_REGISTRY ]]; then
            branch_registry=${DOCKER_REGISTRY}
            export DOCKER_REGISTRY=itisfoundation
            # try getting the main cache, and set back the DOCKER_REGISTRY if it fails...
            make pull-cache || export DOCKER_REGISTRY=${branch_registry}
        fi
    } || true
    make pull-version || true
}

build_images() {
    if [[ -v DOCKER_BUILDX ]]; then
        make build-cache-x
        make build-x
    else
        make build-cache
        make build
    fi    
    make info-images
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
