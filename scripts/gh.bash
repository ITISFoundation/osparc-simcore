#!/bin/bash

# Github CLI (https://cli.github.com/)
# The Dockerfile for generating the image used here is located here: https://github.com/ITISFoundation/osparc-simcore-clients/blob/master/scripts/gh/Dockerfile
# By default the pwd is mounted into the docker container and used as the current working directory

IMAGE_NAME=itisfoundation/gh
IMAGE_VERSION=v0

readonly UID=$(id -u)
USER_DIR=$(realpath ~)
GH_TOKEN_FILE=${USER_DIR}/.gh-token

if [ -v GITHUB_ACTIONS ]; then
  echo "Running in GitHub Actions. Remember to expose GITHUB_TOKEN in your Github workflow .yml file."
  gh "$@"
else
  if [ ! -f "${GH_TOKEN_FILE}" ]; then
      echo "The file '${GH_TOKEN_FILE}' does not exist. To use Gihtub CLI, create '${GH_TOKEN_FILE}' and expose your github token in it as follows:"
      echo "GH_TOKEN=<your github token>"
      exit 1
  fi
  cur_dir=/tmp/curdir
  docker run --rm --env-file=${GH_TOKEN_FILE} --volume=$(pwd):${cur_dir} --workdir=${cur_dir} --user=${UID}:${UID}\
    ${IMAGE_NAME}:${IMAGE_VERSION} "$@"
fi
