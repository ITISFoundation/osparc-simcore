#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

current_branch=$(exec ops/travis/helpers/slugify_branch.sh)
export DOCKER_IMAGE_PREFIX=${DOCKER_REGISTRY}/
export DOCKER_IMAGE_TAG=$current_branch-latest

before_install() {
    bash ops/travis/helpers/install_docker_compose.sh
    bash ops/travis/helpers/show_system_versions.sh
}

install() {
    pip3 install --upgrade pip wheel setuptools && pip3 --version
    pip3 install -r ops/travis/system-testing/requirements.txt
    make pull || make build
}

before_script() {
    pip freeze
    docker images
    make up
}

script() {
    # wait for a minute to let the swarm warm up...
    pytest -v ops/travis/system-testing/tests
}

after_success() {
    make down
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
