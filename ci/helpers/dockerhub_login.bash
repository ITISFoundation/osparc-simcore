#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

# check needed variables are defined
if [ ! -v DOCKER_USERNAME ] ||\
    [ ! -v DOCKER_PASSWORD ] ||\
    [ ! -v DOCKER_REGISTRY ]; then
    echo "## ERROR: Please define the environs (DOCKER_USERNAME, DOCKER_PASSWORD, DOCKER_REGISTRY) in your CI settings!"
    exit 1
fi

# check script needed variables
if [ ! -v OWNER ]; then
    echo "## ERROR: incorrect usage of CI. OWNER (e.g. dockerhub organization like itisfoundation or user private name) not defined!"
    exit 1
fi

# only upstream is allowed to push to itisfoundation repo
if [ "${OWNER,,}" != "itisfoundation" ] &&\
    { [ ! -v DOCKER_REGISTRY ] || [ -z "${DOCKER_REGISTRY}" ] || [ "$DOCKER_REGISTRY" = "itisfoundation" ]; }; then
    echo "## ERROR: it is not allowed to push to the main dockerhub repository from a fork!"
    echo "## Please adapt your CI-defined environs (DOCKER_USERNAME, DOCKER_PASSWORD, DOCKER_REGISTRY)"
    exit 1
fi

# these variable must be available securely from the CI
echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

echo "logged into dockerhub successfully, ready to push"
exit 0
