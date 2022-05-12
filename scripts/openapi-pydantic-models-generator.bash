#!/bin/bash
#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

PYTHON_VERSION=3.9.12
IMAGE_NAME="local/datamodel-code-generator:${PYTHON_VERSION}"
WORKDIR="$(pwd)"


Build()
{
  docker buildx build \
    --build-arg PYTHON_VERSION="${PYTHON_VERSION}" \
    --build-arg HOME_DIR="/home/$USER" \
    --tag "$IMAGE_NAME" \
    - <<EOF
FROM python:${PYTHON_VERSION}-slim
RUN pip install datamodel-code-generator[http]
ENTRYPOINT ["datamodel-codegen", \
          "--field-constraints", \
		      "--use_non_positive_negative_number_constrained_types", \
          "--use-standard-collections", \
          "--use-schema-description", \
          "--reuse-model", \
          "--set-default-enum-member", \
          "--use-title-as-name", \
          "--validation"]
EOF
}


Run()
{
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

# Examples:
#  - SEE  https://pydeps.readthedocs.io/en/latest/#usage
#
# pydeps.bash services/web/server/src/simcore_service_webserver --cluster
# pydeps.bash services/web/server/src/simcore_service_webserver --only "simcore_service_webserver.projects" --cluster
#
#

Build
Run "$@"
echo "DONE"
