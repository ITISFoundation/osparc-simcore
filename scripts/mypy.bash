#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

image_name="$(basename "$0"):latest"

# NOTE: latest pydantic version (1.10.0) creates a invalid issue in mypy.
# using mypy 0.971 (compiled: yes)
# simcore_service_dynamic_sidecar/models/shared_store.py:12:47: error: Incompatible types in assignment (expression has type "List[_T]", variable has type "List[str]")
docker buildx build --tag "$image_name" - &>/dev/null <<EOF
FROM python:3.9.12-slim-buster
RUN pip install --upgrade pip \
    && pip install mypy==0.971 \
                  pydantic[email]==1.9.2 \
                  types-aiofiles==0.8.10 \
                  types-PyYAML==6.0.11 \
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
  --user "$(id -u):$(id -g)" \
  --volume "${mypy_config}":/config/mypy.ini \
  --volume "${target_path}":/src \
  --workdir=/src \
  "$image_name" \
  --config-file /config/mypy.ini \
  /src
