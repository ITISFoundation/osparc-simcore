#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PYTHON_VERSION=3.9.12
IMAGE_NAME="local/pydeps-devkit:${PYTHON_VERSION}"
WORKDIR="$(pwd)"


Build()
{
  docker build \
    --build-arg PYTHON_VERSION="${PYTHON_VERSION}" \
    --build-arg HOME_DIR="/home/$USER" \
    --tag "$IMAGE_NAME" \
    "$SCRIPT_DIR/pydeps-docker"
}


Run()
{
  docker run \
    -it \
    --workdir="/home/$USER/workdir" \
    --volume="/etc/group:/etc/group:ro" \
    --volume="/etc/passwd:/etc/passwd:ro" \
    --volume="$WORKDIR:/home/$USER/workdir" \
    --user="$(id --user "$USER")":"$(id --group "$USER")" \
    --entrypoint=pydeps \
    "$IMAGE_NAME" \
    "$@"

}

# Examples:
#  - SEE  https://pydeps.readthedocs.io/en/latest/#usage
#
# pydeps.bash services/web/server/src/simcore_service_webserver --cluster
# pydeps.bash services/web/server/src/simcore_service_webserver --only "simcore_service_webserver.projects" --cluster
#
#

Build
Run "$@"
echo "DONE"
