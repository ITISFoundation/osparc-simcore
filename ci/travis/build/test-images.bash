#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

export DOCKER_IMAGE_TAG=$(exec ci/travis/helpers/build_docker_image_tag)

before_install() {
    bash ci/travis/helpers/update_docker;
    bash ci/travis/helpers/install_docker_compose;
    bash ci/helpers/show_system_versions;
    env
}

install() {
    echo "nothing to install..."
}

before_script() {
    bash ci/build/test-images pull_images
}

script() {
    bash ci/build/test-images build_images
}

after_success() {
    echo "build succeeded"
    make info-images
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
