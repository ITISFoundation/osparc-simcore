#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

bash ci/helpers/dockerhub_login.bash

# define the local image tag
DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG

# push the local cache
make push-cache

# push the local images
make push-version

echo "## After push"
make info-images
