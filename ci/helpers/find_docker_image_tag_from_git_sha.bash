#!/usr/bin/env bash
# Usage: find_docker_image_tag_from_git_sha.bash
#
# returns the full image tag corresponding to the git tag name that shall be used

# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

my_dir="$(dirname "$0")"
source "$my_dir/../../scripts/helpers/logger.bash"

log_info "Retrieving SHA for tag ${GIT_TAG}"
readonly GIT_COMMIT_SHA=$(git show-ref -s "${GIT_TAG}")
log_info "Found SHA for tag ${GIT_COMMIT_SHA}"

# get token
log_info "Retrieving token ..."
readonly TOKEN=$(curl -s -H "Content-Type: application/json" -X POST -d '{"username": "'"${DOCKER_USERNAME}"'", "password": "'"${DOCKER_PASSWORD}"'"}' https://hub.docker.com/v2/users/login/ | jq -r .token)

# output images & tags

log_info "Images and tags for organization: ${ORG} in repo ${REPO}"
readonly IMAGE_TAGS=$(curl -s -H "Authorization: JWT ${TOKEN}" https://hub.docker.com/v2/repositories/"${ORG}"/"${REPO}"/tags/?page_size=100 | jq -r '.results|.[]|.name')
for j in ${IMAGE_TAGS}
do
    if [[ ${j} =~ ${TAG_PATTERN} ]]; then
        if [[ ${j} =~ ${GIT_COMMIT_SHA} ]]; then
            echo "${j}"
            exit 0
        fi
    fi
done
# not found
error_exit "$LINENO" "could not find image:${GIT_TAG} with ${GIT_COMMIT_SHA}. Is the image available in the registry?"
