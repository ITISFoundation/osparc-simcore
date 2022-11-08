#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/

set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'


IMAGE_NAME="${DOCKER_REGISTRY:-itisfoundation}/service-integration:${DOCKER_IMAGE_TAG:-master-github-latest}"
WORKDIR="$(pwd)"

run() {
  docker run \
    -it \
    --rm \
    --volume="/etc/group:/etc/group:ro" \
    --volume="/etc/passwd:/etc/passwd:ro" \
    --user="$(id --user "$USER")":"$(id --group "$USER")" \
    --volume "$WORKDIR":/src \
    --workdir=/src \
    "$IMAGE_NAME" \
    "$@"
}


run "$@"
