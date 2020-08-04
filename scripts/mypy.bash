#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

target_path=$(realpath ${1:-Please give target path as argument})
cd "$(dirname "$0")"
default_mypy_config="$(dirname ${PWD})/mypy.ini"
mypy_config=$(realpath ${2:-${default_mypy_config}})

echo mypying ${target_path} using config in ${mypy_config}...

echo $default_mypy_config
docker run --rm \
  -v ${mypy_config}:/config/mypy.ini \
  -v ${target_path}:/src \
  --workdir=/src \
  kiwicom/mypy mypy \
    --config-file /config/mypy.ini \
    /src
