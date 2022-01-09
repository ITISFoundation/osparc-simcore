#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

install() {
  bash ci/helpers/ensure_python_pip.bash
  pushd services/director-v2
  pip3 install -r requirements/ci.txt
  popd
  pip list --verbose
}

test() {
  pytest --numprocesses=auto --cov=simcore_service_director_v2 --durations=10 --cov-append \
    --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
    -v -m "not travis" services/director-v2/tests/unit --ignore=services/director-v2/tests/unit/with_dbs \
    --ignore=services/director-v2/tests/unit/with_swarm
  # these tests cannot be run in parallel
  pytest --log-format="%(asctime)s %(levelname)s %(message)s" \
    --log-date-format="%Y-%m-%d %H:%M:%S" \
    --cov=simcore_service_director_v2 --durations=10 --cov-append \
    --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
    -v -m "not travis" services/director-v2/tests/unit/with_swarm services/director-v2/tests/unit/with_dbs
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
