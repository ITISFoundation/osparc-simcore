#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

mkdir --parents ~/.docker/cli-plugins/
DOCKER_BUILDX="0.3.1"
curl --location https://github.com/docker/buildx/releases/download/v${DOCKER_BUILDX}/buildx-v${DOCKER_BUILDX}.linux-amd64 --output ~/.docker/cli-plugins/docker-buildx
chmod a+x ~/.docker/cli-plugins/docker-buildx