#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

SRC_DIRECTORY_NAME=${2}
BASE_PATH_DIR=${3-MISSING_DIR}


# global config for entire repo
PYLINT_CONFIG="$(git rev-parse --show-toplevel)/.pylintrc"
MYPY_CONFIG="$(git rev-parse --show-toplevel)/mypy.ini"


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
  mypy --ignore-missing-imports --config-file "$MYPY_CONFIG" src/"$SRC_DIRECTORY_NAME" tests/
}

# invoked by ci as test (also fails on isort and black)
ci() {
  echo "checking codestyle in service=$BASE_PATH_DIR with source_directory=$SRC_DIRECTORY_NAME"
  echo "isort"
  isort --check setup.py "$BASE_PATH_DIR"/src/"$SRC_DIRECTORY_NAME" "$BASE_PATH_DIR"/tests
  echo "black"
  black --check "$BASE_PATH_DIR"/src/"$SRC_DIRECTORY_NAME" "$BASE_PATH_DIR"/tests
  echo "pylint ..."
  pylint --rcfile="$PYLINT_CONFIG" "$BASE_PATH_DIR"/src/"$SRC_DIRECTORY_NAME" "$BASE_PATH_DIR"/tests
  echo "mypy ..."
  # installing all missing stub packages (e.g. types-PyYAML, types-aiofiles, etc)
  python3 -m pip install types-aiofiles types-PyYAML types-ujson
  # runs mypy
  mypy --config-file "$MYPY_CONFIG" --ignore-missing-imports "$BASE_PATH_DIR"/src/"$SRC_DIRECTORY_NAME" "$BASE_PATH_DIR"/tests
}

# Allows to call a function based on arguments passed to the script
"$@"
