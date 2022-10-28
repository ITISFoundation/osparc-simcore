#!/usr/bin/env bash
# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

my_dir="$(dirname "$0")"
# shellcheck source=/dev/null
source "$my_dir/../../scripts/helpers/logger.bash"

# check script needed variables
if [ ! -v FROM_TAG_PREFIX ] || [ ! -v TO_TAG_PREFIX ] || [ ! -v GIT_TAG ]; then
    error_exit "$LINENO" "incorrect use of script. FROM_TAG_PREFIX/TO_TAG_PREFIX (e.g. master, staging), and/or GIT_TAG not defined!"
fi

log_info "logging in dockerhub..."
bash ci/helpers/dockerhub_login.bash

log_info "finding the version in the docker hub registry..."
# find and pull the tagged build
# find the docker image tag
export ORG=${DOCKER_REGISTRY}
export REPO="webserver"
# FROM_TAG_PREFIX-DATE.GIT_SHA
export TAG_PATTERN="^${FROM_TAG_PREFIX}-.+\..+"
DOCKER_IMAGE_TAG=$(./ci/helpers/find_docker_image_tag_from_git_sha.bash | awk 'END{print}') || exit $?
log_info "found image ${DOCKER_IMAGE_TAG}"
export DOCKER_IMAGE_TAG
log_info "pulling images ${DOCKER_IMAGE_TAG} from ${DOCKER_REGISTRY}"
make pull-version tag-local

# show current images on system
log_info "Before push"
make info-images

# re-tag images to ${TO_TAG_PREFIX}-{GIT_TAG}-DATE.GIT_SHA
readonly GIT_COMMIT_SHA=$(git show-ref -s "${GIT_TAG}")
DOCKER_IMAGE_TAG="${TO_TAG_PREFIX}-${GIT_TAG}"-$(date --utc +"%Y-%m-%d--%H-%M")."${GIT_COMMIT_SHA}"
export DOCKER_IMAGE_TAG
log_info "pushing images ${DOCKER_IMAGE_TAG} to ${DOCKER_REGISTRY}"
make push-version

# push latest image ${TO_TAG_PREFIX}-latest
DOCKER_IMAGE_TAG="${TO_TAG_PREFIX}-latest"
export DOCKER_IMAGE_TAG
log_info "pushing images ${DOCKER_IMAGE_TAG} to ${DOCKER_REGISTRY}"
make push-version

log_info "complete!"
