#!/bin/bash
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
  make devenv
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/director-v2
  make install-ci
  popd
  .venv/bin/pip list --verbose
  (make pull-version tag-local) || (make build tag-version)
  make info-images
}

test() {
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd services/director-v2
  make test-ci-integration test-subfolder="$1"
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
