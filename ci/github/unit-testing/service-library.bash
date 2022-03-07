#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

# NOTE: notice that the CI uses [all]
# TODO: add STEPS where pip-sync individual extras and test separately
install_all() {
  bash ci/helpers/ensure_python_pip.bash
  pushd packages/service-library
  pip3 install -r "requirements/ci[all].txt"
  popd
  pip list -v
}

test_all() {
  pytest --log-format="%(asctime)s %(levelname)s %(message)s" \
    --log-date-format="%Y-%m-%d %H:%M:%S" \
    --cov=servicelib --durations=10 --cov-append \
    --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
    --asyncio-mode=auto \
    -v -m "not travis" packages/service-library/tests
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
