#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

slugify () {
    echo "$1" | iconv -t ascii//TRANSLIT | sed -r s/[~\^]+//g | sed -r s/[^a-zA-Z0-9]+/-/g | sed -r s/^-+\|-+$//g | tr A-Z a-z
}


before_install() {    
    bash ops/travis/helpers/install_docker_compose;
    bash ops/travis/helpers/show_system_versions;
    env
}

install() {
    echo "nothing to install..."
}

before_script() {
    echo "nothing to do..."
}

script() {
    export DOCKER_IMAGE_PREFIX=${DOCKER_REGISTRY}
    export DOCKER_IMAGE_TAG=$(slugify "${TRAVIS_BRANCH}-latest")
    # try to pull if possible
    make pull || true
    # build anyway
    make build
}

after_success() {
    echo "build succeeded"
}

after_failure() {
    echo "build failed"
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
