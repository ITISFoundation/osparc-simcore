#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG

before_install() {
    bash ci/travis/helpers/update-docker.bash;
    bash ci/travis/helpers/install-docker-compose.bash;
    bash ci/helpers/show_system_versions.bash;
    env
}

install() {
    echo "nothing to install..."
}

before_script() {
    bash ci/build/test-images.bash pull_images
}

script() {
    bash ci/build/test-images.bash build_images
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
