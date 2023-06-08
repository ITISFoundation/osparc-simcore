#!/bin/bash
# Script for calling OpenAPI Generato (generate clients, servers, and documentation from OpenAPI 2.0/3.x documents) or
# fetch the associated templates for Python client generation. Which function is called is determined by the 'RUN_FCN' environment variable.
# Setting 'RUN_FCN'="OPENAPI_GENERATOR_CLI" calls the generator and setting 'RUN_FCN'="FETCH_TEMPLATES" fetches the python client templates

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

# fetch_openapi_generator_templates
# usage: fetch_openapi_generator_templates <dir to place the templates in>

OPENAPI_GENERATOR_VERSION=v4.2.3

openapi_generator_cli(){
  USERID=$(stat --format=%u "$PWD")
  GROUPID=$(stat --format=%g "$PWD")

  # to mount a directory (e.g. to find custom templates, define the DOCKER_MOUNT environment variable)
  docker_mount=""
  if [ -v DOCKER_MOUNT ]; then
    docker_mount="-v ${DOCKER_MOUNT}"
  fi

  exec docker run --rm \
      ${docker_mount} \
      --user "$USERID:$GROUPID" \
      --volume "$PWD:/local" \
      openapitools/openapi-generator-cli:${OPENAPI_GENERATOR_VERSION} "$@"
}

fetch_openapi_generator_templates(){
	TEMPLATE_DIR=$1
  TMPDIR=$(mktemp -d)

	echo "Fetching openapi generator templates from github..."
	wget -O ${TMPDIR}/openapi_zip.zip "https://github.com/OpenAPITools/openapi-generator/archive/refs/tags/${OPENAPI_GENERATOR_VERSION}.zip"
	unzip -q ${TMPDIR}/openapi_zip.zip -d ${TMPDIR}

	echo "Overwriting templates in this repo..."
	rm -r ${TEMPLATE_DIR}
	mkdir ${TEMPLATE_DIR}
	cd ${TMPDIR}
	openapi_dir=$(ls . | grep openapi-generator)
	cd ${openapi_dir}
	cp -r ./modules/openapi-generator/src/main/resources/python/* ${TEMPLATE_DIR}

	rm -r ${TMPDIR}
	echo "Done!"
}

if [[ "${RUN_FCN}" == "OPENAPI_GENERATOR_CLI" ]]; then
    openapi_generator_cli "$@"
elif [[ "${RUN_FCN}" == "FETCH_TEMPLATES" ]]; then
    fetch_openapi_generator_templates "$@"
else
    echo "The environment variable 'RUN_FCN' must be defined when calling this bash script"
fi
