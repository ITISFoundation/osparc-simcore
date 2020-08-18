#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

FOLDER_CHECKS=(api/ .travis.yml)

before_install() {
    if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}";
    then
        bash ci/travis/helpers/update-docker.bash
        bash ci/travis/helpers/install-docker-compose.bash
        bash ci/helpers/show_system_versions.bash
    fi
}

install() {
    if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}";
    then
        bash ci/helpers/ensure_python_pip.bash
        pip3 install --requirement api/tests/requirements.txt
    fi
}

before_script() {
    if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}";
    then
        pip list --verbose
    fi
}

script() {
    if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}";
    then
        pytest --durations=10 \
          -v -m "not travis" api/tests
    else
        echo "No changes detected. Skipping unit-testing of apihub."
    fi
}

after_success() {
    if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}";
    then
        coveralls
    fi
}

after_failure() {
    echo "failure... you can always write something more interesting here..."
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
