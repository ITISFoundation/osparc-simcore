#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

install() {
    bash ci/helpers/ensure_python_pip.bash
    pip3 install --requirement api/tests/requirements.txt
    pip list --verbose
}

test() {
  pytest --durations=10 \
          -v -m "not travis" api/tests
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
