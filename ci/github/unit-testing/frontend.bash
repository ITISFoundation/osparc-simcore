#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

install() {
    npm install
    make -C services/web/client clean
    npx eslint --version
    make -C services/web/client info
}

test() {
    echo "# Running Linter"
    npm run linter

    pushd services/web/client

    echo "# Building build version"
    make compile

    echo "# Building source version"
    make compile-dev flags=--machine-readable

    echo "# Serving source version"
    make serve-dev flags="--machine-readable --target=source --listen-port=8080" detached=test-server

    #TODO: move this inside qx-kit container
    echo "# Waiting for build to complete"
    while ! nc -z localhost 8080; do
        sleep 1 # wait for 10 second before check again
    done

    # FIXME: reports ERROR ReferenceError: URL is not defined. See https://github.com/ITISFoundation/osparc-simcore/issues/1071
    ## node source-output/resource/qxl/testtapper/run.js --diag --verbose http://localhost:8080/testtapper
    wget --spider http://localhost:8080/

    make clean
    popd

    #TODO: no idea what is this doing... disabled at the moment since travis is supposed to do it as well
    
    # # prepare documentation site ...
    # git clone --depth 1 https://github.com/ITISFoundation/itisfoundation.github.io.git
    # rm -rf itisfoundation.github.io/.git

    # # if we have old cruft hanging around, we should remove all this will
    # # only trigger once
    # if [ -d itisfoundation.github.io/transpiled ]; then
    #   rm -rf itisfoundation.github.io/*
    # fi

    # # add the default homepage
    # cp -rp docs/webdocroot/* itisfoundation.github.io

    # # add our build
    # if [ -d services/web/client/build-output ]; then
    #   rm -rf itisfoundation.github.io/frontend
    #   cp -rp services/web/client/build-output itisfoundation.github.io/frontend
    # fi
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
