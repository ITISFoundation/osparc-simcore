#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

PYTHON_VERSION=3.11.9
IMAGE_NAME="local/datamodel-code-generator:${PYTHON_VERSION}"
WORKDIR="$(pwd)"

Build() {
  docker buildx build \
    --build-arg PYTHON_VERSION="${PYTHON_VERSION}" \
    --build-arg HOME_DIR="/home/$USER" \
    --tag "$IMAGE_NAME" \
    --load \
    - <<EOF
FROM python:${PYTHON_VERSION}-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN uv pip install --system datamodel-code-generator[http] && uv pip list
ENTRYPOINT ["datamodel-codegen", \
          "--output-model-type=pydantic_v2.BaseModel", \
          "--input-file-type=jsonschema", \
          "--snake-case-field", \
          "--use-standard-collections", \
          "--use-union-operator", \
          "--use-schema-description", \
          "--allow-population-by-field-name", \
          "--use-subclass-enum", \
          "--use-double-quotes", \
          "--field-constraints", \
		      "--use-non-positive-negative-number-constrained-types", \
          "--reuse-model", \
          "--set-default-enum-member", \
          "--use-title-as-name", \
          "--target-python-version=${PYTHON_VERSION%.*}", \
          "--use-default-kwarg", \
          "--validation"]
EOF
}

Run() {
  docker run \
    -it \
    --workdir="/home/$USER/workdir" \
    --volume="/etc/group:/etc/group:ro" \
    --volume="/etc/passwd:/etc/passwd:ro" \
    --volume="$WORKDIR:/home/$USER/workdir" \
    --user="$(id --user "$USER")":"$(id --group "$USER")" \
    "$IMAGE_NAME" \
    "$@"

}

Help() {
  echo "Please check https://koxudaxi.github.io/datamodel-code-generator/ for help on usage"
}

Build
Run "$@"
echo "DONE"
