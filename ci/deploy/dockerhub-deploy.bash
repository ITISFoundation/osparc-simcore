#!/usr/bin/env bash
# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'


readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m'

function error_exit {
    readonly line=$1
    shift 1
    echo
    echo -e "${RED}[ERROR]:$line: ${1:-"Unknown Error"}" 1>&2
    exit 1
}

function log_msg {
    echo
    echo -e "${YELLOW}[INFO]: ${1:-"Unknown message"}${NC}"
}

# check script needed variables
if [ ! -v TAG_PREFIX ]; then
    error_exit "$LINENO" "incorrect use of script. TAG_PREFIX (e.g. master, staging) not defined!"
fi

log_msg "logging in dockerhub..."
bash ci/helpers/dockerhub_login.bash

# pull the current tested build

DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG
log_msg "pulling build ${DOCKER_IMAGE_TAG}"
make pull-version tag-local

# show current images on system
log_msg "Before push"
make info-images

# re-tag build
DOCKER_IMAGE_TAG="$TAG_PREFIX-latest"
export DOCKER_IMAGE_TAG
log_msg "pushing images ${DOCKER_IMAGE_TAG} to ${DOCKER_REGISTRY}"
make push-version

# re-tag build to master-github-DATE.GIT_SHA
DOCKER_IMAGE_TAG=$TAG_PREFIX-$(date --utc +"%Y-%m-%d--%H-%M").$(git rev-parse HEAD)
export DOCKER_IMAGE_TAG
log_msg "pushing images ${DOCKER_IMAGE_TAG} to ${DOCKER_REGISTRY}"
make push-version
