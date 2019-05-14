#!/bin/bash
# Usage: find_staging_version.sh
# returns the full image tag corresponding to the git tag name that shall be used

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

GIT_COMMIT_SHA=$(git show-ref -s ${TRAVIS_TAG})
ORG=${DOCKER_REGISTRY}
REPO="webserver"

# get token
echo "Retrieving token ..."
TOKEN=$(curl -s -H "Content-Type: application/json" -X POST -d '{"username": "'${DOCKER_USERNAME}'", "password": "'${DOCKER_PASSWORD}'"}' https://hub.docker.com/v2/users/login/ | jq -r .token)

# get list of repositories
echo "Retrieving repository list ..."
REPO_LIST=$(curl -s -H "Authorization: JWT ${TOKEN}" https://hub.docker.com/v2/repositories/${ORG}/?page_size=100 | jq -r '.results|.[]|.name')

# output images & tags
echo
echo "Images and tags for organization: ${ORG}"
echo
IMAGE_TAGS=$(curl -s -H "Authorization: JWT ${TOKEN}" https://hub.docker.com/v2/repositories/${ORG}/${REPO}/tags/?page_size=100 | jq -r '.results|.[]|.name')
for j in ${IMAGE_TAGS}
do
echo "  - ${j}"
done