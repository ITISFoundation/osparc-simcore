#!/bin/bash
# OpenAPI Generator: generate clients, servers, and documentation from OpenAPI 2.0/3.x documents
#
#
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

USERID=$(stat --format=%u "$PWD")
GROUPID=$(stat --format=%g "$PWD")

# FIXME: replaces automatically $PWD by /local so it maps correctly in the container
#PATTERN=s+$PWD+/local+
#CMD=$(echo "$@" | sed $PATTERN)

exec docker run --rm \
    --user "$USERID:$GROUPID" \
    --volume "$PWD:/local" \
    openapitools/openapi-generator-cli:v4.2.3 "$@"

# Example
#   openapi-generator-cli generate -i /local/api/specs/webserver/openapi.yaml -g python -o /local/out/sdk/webserver
#
