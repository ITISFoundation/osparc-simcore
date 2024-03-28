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

install() {
  make devenv
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pushd tests/swarm-deploy
  make install-ci
  popd
  uv pip list
  make info-images
}

test() {
  # WARNING: this test is heavy. Due to limited CI machine power, please do not
  # add too much overhead (e.g. low log-level etc)
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pytest \
    --asyncio-mode=auto \
    --color=yes \
    --durations=5 \
    --log-level=INFO \
    -v \
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
