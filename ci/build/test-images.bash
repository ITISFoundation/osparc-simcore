#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG

build_images() {
  make build create_cache=1
  make info-images
}

# Check if the function exists (bash specific)
if declare -f "$1" >/dev/null; then
  # call arguments verbatim
  "$@"
else
  # Show a helpful error
  echo "'$1' is not a known function name" >&2
  exit 1
fi
