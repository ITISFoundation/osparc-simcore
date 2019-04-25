#!/bin/bash
set -euo pipefail
IFS=$'\n\t'
# these variable must be available securely from travis
echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

export DOCKER_IMAGE_PREFIX=itisfoundation
export DOCKER_IMAGE_TAG_PREFIX=master
make push