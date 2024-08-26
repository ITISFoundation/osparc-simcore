#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'
#
# SEE https://github.com/asottile/pyupgrade
#
#
# NOTE: check --py* flag in CLI when PYTHON_VERSION is modified
PYTHON_VERSION=3.11.9
IMAGE_NAME="local/pyupgrade-devkit:${PYTHON_VERSION}"
WORKDIR="$(pwd)"

Build() {
  docker buildx build \
    --load \
    --build-arg HOME_DIR="/home/$USER" \
    --tag "$IMAGE_NAME" \
    - <<EOF
FROM python:${PYTHON_VERSION}-slim-bookworm
RUN pip --no-cache-dir install --upgrade \
  pip \
  wheel \
  setuptools

RUN pip install \
  pyupgrade

ENTRYPOINT ["pyupgrade", \
  "--py311-plus" ]
EOF
}

Run() {
  docker run \
    -it \
    --workdir="/home/$USER/workdir" \
    --volume="/etc/group:/etc/group:ro" \
    --volume="/etc/passwd:/etc/passwd:ro" \
    --volume="$WORKDIR:/home/$USER/workdir" \
    --user="$(id --user "$USER")":"$(id --group "$USER")" \
    "$IMAGE_NAME" \
    \
    "$@"

}

Build
Run "$@"
echo "DONE"
