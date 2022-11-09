#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
#
# ERD states for Entity Relationship Diagrams
#
# This is a list of tools to produce ERDs of different libraries:
# - [erdantic](https://erdantic.drivendata.org/stable/): ERDs for pydantic models
#
#
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
IMAGE_NAME="local/scripts/$(basename "$0"):latest"
IMAGE_DIR_EXT=${SCRIPT_DIR}/$(basename "$0")
IMAGE_DIR=${IMAGE_DIR_EXT%%.*}
WORKDIR="$(pwd)"

echo ${IMAGE_DIR}

build() {
  echo Building image "${IMAGE_NAME}" at "${IMAGE_DIR}"
  docker build \
    --quiet \
    --tag "$IMAGE_NAME" \
    "$IMAGE_DIR"
}

inspect(){
  docker inspect "$IMAGE_NAME" | jq ".[0].RepoTags"
}


run() {
  docker run \
    --rm \
    --volume="/etc/group:/etc/group:ro" \
    --volume="/etc/passwd:/etc/passwd:ro" \
    --user="$(id --user "$USER")":"$(id --group "$USER")" \
    --volume "$WORKDIR":/src \
    --workdir=/src \
    "$IMAGE_NAME" \
    "$@"
}

# ----------------------------------------------------------------------
# MAIN
#
# USAGE
#    ./scripts/erd.bash erdantic --help
build
inspect
run "$@"
# ----------------------------------------------------------------------
