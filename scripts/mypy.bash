#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'


image_name="$(basename $0):latest"


docker build --tag "$image_name" -<<EOF
FROM python:3.8.10-slim-buster
RUN pip install --upgrade pip && pip install mypy pydantic[email]
ENTRYPOINT ["mypy"]
EOF


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
  "$image_name" \
    --config-file /config/mypy.ini \
    /src
