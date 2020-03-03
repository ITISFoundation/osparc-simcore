#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

bash ci/helpers/dockerhub_login.bash

# check script needed variables
if [ ! -v TAG_PREFIX ]; then
    echo "## ERROR: incorrect use of script. TAG_PREFIX (e.g. master, staging) not defined!"
    exit 1
fi

# pull the current tested build
DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash.bash)
export DOCKER_IMAGE_TAG
make pull-version tag-local

# show current images on system
echo "## Before push"
make info-images

# re-tag build
DOCKER_IMAGE_TAG="$TAG_PREFIX-latest"
export DOCKER_IMAGE_TAG
make push-version

# re-tag build to master-github-DATE.GIT_SHA
DOCKER_IMAGE_TAG=$TAG_PREFIX-$(date --utc +"%Y-%m-%d--%H-%M").$(git rev-parse HEAD)
export DOCKER_IMAGE_TAG
make push-version

# show update of images on system
echo "## After push"
make info-images
