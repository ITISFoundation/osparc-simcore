#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

bash ci/helpers/dockerhub_login

# check script needed variables
if [ ! -v TAG_PREFIX ] || [ ! -v GIT_TAG ]; then
    echo "## ERROR: incorrect use of script. OWNER (e.g. itisfoundation or user) and/or TAG_PREFIX (e.g. master, staging), and/or GIT_TAG not defined!"
    exit 1
fi

# pull the tagged staging build
# find the docker image tag
export ORG=${DOCKER_REGISTRY}
export REPO="webserver"
# staging-github-DATE.GIT_SHA
export TAG_PATTERN="^${TAG_PREFIX}-.+\..+"
DOCKER_IMAGE_TAG=$(./ci/helpers/find_staging_version | awk 'END{print}') || exit $?
export DOCKER_IMAGE_TAG
make pull-version tag-local

# show current images on system
echo "## Before push"
make info-images

# re-tag staging to {GIT_TAG}-DATE.GIT_SHA
DOCKER_IMAGE_TAG=${GIT_TAG}-$(date --utc +"%Y-%m-%d--%H-%M").$(git rev-parse HEAD)
export DOCKER_IMAGE_TAG
make push-version push-latest

echo "## After push"
make info-images
