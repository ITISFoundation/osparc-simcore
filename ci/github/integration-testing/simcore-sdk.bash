#!/bin/bash
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

install() {
  make devenv
  # shellcheck source=/dev/null
  source .venv/bin/activate
  sudo ./ci/github/helpers/install_aws_cli_v2.bash
  pushd packages/simcore-sdk
  make install-ci
  popd
  uv pip list
  make info-images
}

test() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd packages/simcore-sdk
  make tests-integration-ci
  popd
}

clean_up() {
  docker images
  make down
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
