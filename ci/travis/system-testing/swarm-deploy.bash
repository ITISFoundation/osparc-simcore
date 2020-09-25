#!/bin/bash
#
#  This task in the system-testing aims to test some guarantees expected from
#  the deployment of osparc-simcore in a cluster (swarm).
#  It follows some of the points enumerated in the https://12factor.net/  methodology.
#

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

# in case it's a Pull request, the env are never available, default to itisfoundation to get a maybe not too old version for caching
DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG

if [[ ! -v DOCKER_REGISTRY ]]; then
    export DOCKER_REGISTRY="itisfoundation"
fi


before_install() {
    bash ci/travis/helpers/update-docker.bash
    bash ci/travis/helpers/install-docker-compose.bash
    bash ci/helpers/show_system_versions.bash
}

install() {
    bash ci/helpers/ensure_python_pip.bash
    pushd tests/swarm-deploy; pip3 install -r requirements/ci.txt; popd
    make pull-version || ( (make pull-cache || true) && make build tag-version)
    make .env
}

before_script() {
    pip list -v
    make info-images
}

script() {
    pytest  --color=yes --cov-report=term-missing -v tests/swarm-deploy
}

after_success() {
    make leave
}

after_failure() {
    docker images
    make down
}

# Check if the function exists (bash specific)
if declare -f "$1" > /dev/null
then
  # call arguments verbatim
  "$@"
else
  # Show a helpful error
  echo "'$1' is not a known function name" >&2
  exit 1
fi
