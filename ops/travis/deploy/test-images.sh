#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

slugify () {
    echo "$1" | iconv -t ascii//TRANSLIT | sed -r s/[~\^]+//g | sed -r s/[^a-zA-Z0-9]+/-/g | sed -r s/^-+\|-+$//g | tr A-Z a-z
}

# show current images on system
docker images

# show environment
env

# these variable must be available securely from travis
echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

# TRAVIS_PLATFORM_STAGE_VERSION=staging-$(date +"%Y-%m-%d").${TRAVIS_BUILD_NUMBER}.$(git rev-parse HEAD)
export DOCKER_IMAGE_PREFIX=${DOCKER_REGISTRY}
current_branch=$(git rev-parse --abbrev-ref HEAD)
export DOCKER_IMAGE_TAG_PREFIX=$(slugify "$current_branch")

make tag
make push
