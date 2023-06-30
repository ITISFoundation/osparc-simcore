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
  bash ci/helpers/ensure_python_pip.bash
  pushd tests/public-api
  pip3 install -r requirements/ci.txt
  make install-latest-python-osparc
  pip freeze
  popd
  make .env
  pip list -v
  make info-images
}

test() {
  # WARNING: this test is heavy. Due to limited CI machine power, please do not
  # add too much overhead (e.g. low log-level etc)
  pytest \
    --color=yes \
    --keep-docker-up \
    --durations=5 \
    -v \
    tests/public-api
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
