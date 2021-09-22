#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

SRC_DIRECTORY_NAME=${2}


# global config for entire repo
PYLINT_CONFIG="$(git rev-parse --show-toplevel)/.pylintrc"


# used for development (fails on pylint and mypy)
development() {
  echo "enforcing codestyle to source_directory=$SRC_DIRECTORY_NAME"
  echo "isort"
  isort setup.py src/"$SRC_DIRECTORY_NAME" tests
  echo "black"
  black src/"$SRC_DIRECTORY_NAME" tests/
  echo "pylint"
  pylint --rcfile="$PYLINT_CONFIG" src/"$SRC_DIRECTORY_NAME" tests/
  echo "mypy"
  make mypy
}

# invoked by ci as test (also fails on isort and black)
ci() {
  echo "enforcing codestyle to source_directory=$SRC_DIRECTORY_NAME"
  echo "isort"
  isort --check setup.py src/"$SRC_DIRECTORY_NAME" tests
  echo "black"
  black --check src/"$SRC_DIRECTORY_NAME" tests
  echo "pylint ..."
  pylint --rcfile="$PYLINT_CONFIG" src/"$SRC_DIRECTORY_NAME" tests/
  echo "mypy ..."
  make --silent mypy
}

# Allows to call a function based on arguments passed to the script
"$@"
