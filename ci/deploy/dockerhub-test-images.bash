#!/bin/bash
# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
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
