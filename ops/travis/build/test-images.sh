#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

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
    make build
}

after_success() {
    echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
    make push
}

after_failure() {
    echo "..."
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
