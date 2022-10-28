#!/usr/bin/env bash
# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

my_dir="$(dirname "$0")"
# shellcheck source=/dev/null
source "$my_dir/../../scripts/helpers/logger.bash"


Help()
{
   # Display Help
   echo "This scripts is a CI helper script to pull a stack of docker images"
   echo "re-tag them and push them to dockerhub. (for example, from master to staging)"
   echo
   echo "Syntax: dockerhub-deploy.bash [-h|n]"
   echo "options:"
   echo "h     Print this Help."
   echo "n     do not pull image, in case it is already available in the local docker registry."
   echo "      The images must be set as local/webserver:production..."
   echo
}

############################################################
############################################################
# Main program                                             #
############################################################
############################################################


# check script needed variables
if [ ! -v TAG_PREFIX ]; then
    error_exit "$LINENO" "incorrect use of script. TAG_PREFIX (e.g. master, staging) not defined!"
fi


# Get the options
skip_pulling=0
while getopts ":nh:" option; do
   case $option in
      h) # display help
        Help
        exit;;
      n) # skip image pulling
        echo "skipping image pull"
        skip_pulling=1
        ;;
      \?) # Invalid option
         echo "Error: Invalid option"
         exit;;
   esac
done

log_info "logging in dockerhub..."
bash ci/helpers/dockerhub_login.bash

if [ $skip_pulling -eq 1 ]; then
  log_info "skipping image pulling (assuming the images are already available)"
else
  # pull the current tested build
  DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
  export DOCKER_IMAGE_TAG
  log_info "pulling build ${DOCKER_IMAGE_TAG}"
  make pull-version tag-local
fi

# show current images on system
log_info "Locally available images before push:"
make info-images

# re-tag build
DOCKER_IMAGE_TAG="$TAG_PREFIX-latest"
export DOCKER_IMAGE_TAG
log_info "pushing images ${DOCKER_IMAGE_TAG} to ${DOCKER_REGISTRY}..."
make push-version

# re-tag build to master-github-DATE.GIT_SHA
DOCKER_IMAGE_TAG=$TAG_PREFIX-$(date --utc +"%Y-%m-%d--%H-%M").$(git rev-parse HEAD)
export DOCKER_IMAGE_TAG
log_info "pushing images ${DOCKER_IMAGE_TAG} to ${DOCKER_REGISTRY}..."
make push-version

# show the final images
log_info "Locally available images after push:"
make info-images
