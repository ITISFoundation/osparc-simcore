#!/usr/bin/env bash
# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

my_dir="$(dirname "$0")"
source "$my_dir/../../scripts/helpers/logger.bash"

# check script needed variables
if [ ! -v TAG_PREFIX ]; then
    error_exit "$LINENO" "incorrect use of script. TAG_PREFIX (e.g. master, staging) not defined!"
fi

log_info "logging in dockerhub..."
bash ci/helpers/dockerhub_login.bash

# pull the current tested build

DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG
log_info "pulling build ${DOCKER_IMAGE_TAG}"
make pull-version tag-local

# show current images on system
log_info "Before push"
make info-images

################
# TEST TO CHECK FOR CI DEPLOY FAILURE
# OBSERVED FIRST ON 01Dec2021
bash ci/helpers/ensure_commit_sha_matching.bash

# re-tag build
DOCKER_IMAGE_TAG="$TAG_PREFIX-latest"
export DOCKER_IMAGE_TAG
log_info "pushing images ${DOCKER_IMAGE_TAG} to ${DOCKER_REGISTRY}"
make push-version

# re-tag build to master-github-DATE.GIT_SHA
DOCKER_IMAGE_TAG=$TAG_PREFIX-$(date --utc +"%Y-%m-%d--%H-%M").$(git rev-parse HEAD)
export DOCKER_IMAGE_TAG
log_info "pushing images ${DOCKER_IMAGE_TAG} to ${DOCKER_REGISTRY}"
make push-version
