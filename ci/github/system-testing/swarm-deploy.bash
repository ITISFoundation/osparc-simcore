#!/bin/bash
#
#  This task in the system-testing aims to test some guarantees expected from
#  the deployment of osparc-simcore in a cluster (swarm).
#  It follows some of the points enumerated in the https://12factor.net/  methodology.
#

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

# in case it's a Pull request, the env are never available, default to itisfoundation to get a maybe not too old version for caching
DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG

install() {
  bash ci/helpers/ensure_python_pip.bash
  pushd tests/swarm-deploy
  pip3 install -r requirements/ci.txt
  popd
  make pull-version || (make build tag-version)
  make .env
  pip list -v
  make info-images
}

test() {
  # WARNING: this test is heavy. Due to limited CI machine power, please do not
  # add too much overhead (e.g. low log-level etc)
  pytest \
    --color=yes \
    --cov-report=term-missing \
    -v \
    --durations=5 \
    --log-level=INFO \
    tests/swarm-deploy
}

clean_up() {
  docker images
  make down
  make leave
}

# Check if the function exists (bash specific)
if declare -f "$1" >/dev/null; then
  # call arguments verbatim
  "$@"
else
  # Show a helpful error
  echo "'$1' is not a known function name" >&2
  exit 1
fi
