#!/bin/bash
# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

mkdir --parents ~/.docker/cli-plugins/
DOCKER_BUILDX="0.4.2"
curl --location https://github.com/docker/buildx/releases/download/v${DOCKER_BUILDX}/buildx-v${DOCKER_BUILDX}.linux-amd64 --output ~/.docker/cli-plugins/docker-buildx
chmod a+x ~/.docker/cli-plugins/docker-buildx
