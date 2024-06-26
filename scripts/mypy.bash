#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/

set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
IMAGE_NAME="local/scripts-$(basename "$0"):latest"
WORKDIR="$(pwd)"

DEFAULT_MYPY_CONFIG="$(git rev-parse --show-toplevel)/mypy.ini"
MYPY_CONFIG=$(realpath "${2:-${DEFAULT_MYPY_CONFIG}}")

build() {
  echo Building image "$IMAGE_NAME"
  #
  docker buildx build \
    --load \
    --quiet \
    --tag "$IMAGE_NAME" \
    "$SCRIPT_DIR/mypy"
}

echo_requirements() {
  echo "Installed :"
  docker run \
    --interactive \
    --rm \
    --user="$(id --user "$USER")":"$(id --group "$USER")" \
    --entrypoint="uv" \
    "$IMAGE_NAME" \
    --no-cache-dir pip freeze
}

run() {
  echo Using "$(docker run --rm "$IMAGE_NAME" --version)"
  echo Mypy config "${MYPY_CONFIG}"
  echo Mypying "$(realpath "$@")":
  #
  docker run \
    --rm \
    --volume="/etc/group:/etc/group:ro" \
    --volume="/etc/passwd:/etc/passwd:ro" \
    --user="$(id --user "$USER")":"$(id --group "$USER")" \
    --volume "$MYPY_CONFIG":/config/mypy.ini \
    --volume "$WORKDIR":/src \
    --workdir=/src \
    "$IMAGE_NAME" \
    "$@"
}

# ----------------------------------------------------------------------
# MAIN
#
# USAGE
#    ./scripts/mypy.bash --help
build
echo_requirements
run "$@"
echo "DONE"
# ----------------------------------------------------------------------
