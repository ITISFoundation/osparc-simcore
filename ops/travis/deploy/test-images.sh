#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

current_branch=$(exec ops/travis/helpers/slugify_branch.sh)
export DOCKER_IMAGE_PREFIX=${DOCKER_REGISTRY}
export DOCKER_IMAGE_TAG_PREFIX=$current_branch

# show current images on system
docker images

# these variable must be available securely from travis
echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

# push the local cache
make push-cache
# push the local images
make push
