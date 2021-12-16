#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

image_name="$(basename "$0"):latest"

docker buildx build --tag "$image_name" - &>/dev/null <<EOF
FROM python:3.8.10-slim-buster
RUN pip install --upgrade pip \
    && pip install mypy==0.910 \
                  pydantic[email] \
                  types-aiofiles \
                  types-PyYAML \
                  types-ujson \
                  types-setuptools
ENTRYPOINT ["mypy"]
EOF

target_path=$(realpath "${1:-Please give target path as argument}")
cd "$(dirname "$0")"
default_mypy_config="$(git rev-parse --show-toplevel)/mypy.ini"
mypy_config=$(realpath "${2:-${default_mypy_config}}")

echo mypying "${target_path}" using config in "${mypy_config}"...
echo using "$(docker run --rm "$image_name" --version)"
docker run --rm \
  --volume /etc/passwd:/etc/passwd:ro \
  --volume /etc/group:/etc/group:ro \
  --user $(id -u):$(id -g) \
  --volume "${mypy_config}":/config/mypy.ini \
  --volume "${target_path}":/src \
  --workdir=/src \
  "$image_name" \
  --config-file /config/mypy.ini \
  /src
