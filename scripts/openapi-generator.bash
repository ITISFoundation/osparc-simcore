#!/bin/bash
# Script for calling OpenAPI Generator (generate clients, servers, and documentation from OpenAPI 2.0/3.x documents).

# OpenAPI Generator: generate clients, servers, and documentation from OpenAPI 2.0/3.x documents
#
# environment variables: Set the DOCKER_MOUNT environment variable to mount volumes for the generator to access files (e.g. templates)
# usage: openapi-generator-cli <command> [<args>]
#
# The most commonly used openapi-generator-cli commands are:
#     config-help   Config help for chosen lang
#     generate      Generate code with the specified generator.
#     help          Display help information
#     list          Lists the available generators
#     meta          MetaGenerator. Generator for creating a new template set and configuration for Codegen. The output will be based on the language you specify, and includes default templates to include.
#     validate      Validate specification
#     version       Show version information
#
# IMPORTANT: use absolute paths so they can be automaticaly mapped inside of the container
#
# REFERENCES:
#   https://openapi-generator.tech/
#   https://hub.docker.com/r/openapitools/openapi-generator-cli
#

OPENAPI_GENERATOR_VERSION=v4.2.3


fetch_openapi_generator_templates(){
  CURDIR=$(pwd)
  TMPDIR=$1
  cd ${TMPDIR}

	echo "Cloning openapi-generator into ${TMPDIR} to get templates..."
  git clone git@github.com:ITISFoundation/openapi-generator.git
  cd openapi-generator
  git checkout openapi-generator-${OPENAPI_GENERATOR_VERSION}
  git status
  git pull
	echo "Done fetching templates..."

  cd ${CURDIR}
}


openapi_generator_cli_generate(){
  TMPDIR=$(mktemp -d)
  USERID=$(stat --format=%u "$PWD")
  GROUPID=$(stat --format=%g "$PWD")
  HOST_TEMPL_DIR=${TMPDIR}/openapi-generator/modules/openapi-generator/src/main/resources/python
  CONTAINER_TEMPL_DIR=/tmp/openapi_templates

  fetch_openapi_generator_templates "${TMPDIR}"
  if [ ! -d "${HOST_TEMPL_DIR}" ]; then
    echo "Templates could not be correctly fetched from Github"
    exit 1
  fi

  (
    exec docker run --rm \
        -v ${HOST_TEMPL_DIR}:${CONTAINER_TEMPL_DIR} \
        --user "$USERID:$GROUPID" \
        --volume "$PWD:/local" \
        openapitools/openapi-generator-cli:${OPENAPI_GENERATOR_VERSION} "$@" \
        --template-dir=${CONTAINER_TEMPL_DIR}
  )

  rm -fr "${TMPDIR}"
}

openapi_generator_cli(){
  USERID=$(stat --format=%u "$PWD")
  GROUPID=$(stat --format=%g "$PWD")

  exec docker run --rm \
      --user "$USERID:$GROUPID" \
      --volume "$PWD:/local" \
      openapitools/openapi-generator-cli:${OPENAPI_GENERATOR_VERSION} "$@"
}

generate=false
if [[ $1 == "generate" ]]; then
  echo "Found generate input. Will fetch templates from git@github.com:ITISFoundation/openapi-generator.git"
  generate=true
fi

if ${generate}; then
  openapi_generator_cli_generate "$@"
else
  openapi_generator_cli "$@"
fi
