#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'


PYTHON_VERSION=3.9.12
IMAGE_NAME="local/pyupgrade-devkit:${PYTHON_VERSION}"
WORKDIR="$(pwd)"

Build() {
  docker buildx build \
    --build-arg HOME_DIR="/home/$USER" \
    --tag "$IMAGE_NAME" \
    - <<EOF
FROM python:${PYTHON_VERSION}-slim-buster
RUN pip --no-cache-dir install --upgrade \
  pip \
  wheel \
  setuptools

RUN pip install \
  pyupgrade

ENTRYPOINT ["pyupgrade", \
  "--py39-plus" ]
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

# Examples:
#  - SEE  https://pydeps.readthedocs.io/en/latest/#usage
#
# ./scripts/pydeps.bash services/web/server/src/simcore_service_webserver --cluster
# ./scripts/pydeps.bash services/web/server/src/simcore_service_webserver --only "simcore_service_webserver.projects" --cluster
#
#

Build
Run "$@"
echo "DONE"
