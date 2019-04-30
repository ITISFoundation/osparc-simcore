#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

current_branch=$(exec ops/travis/helpers/slugify_branch.sh)
export DOCKER_IMAGE_PREFIX=${DOCKER_REGISTRY}
export DOCKER_IMAGE_TAG_PREFIX=$current_branch

before_install() {
    bash ops/travis/helpers/install_docker_compose;
    bash ops/travis/helpers/show_system_versions;
    env
}

install() {
    echo "nothing to install..."
}

before_script() {
    make pull-cache || true
    make pull || true
}

script() {
    make build-cache
    make build
}

after_success() {
    echo "build succeeded"
}

after_failure() {
    echo "build failed"
    env
    docker images
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
