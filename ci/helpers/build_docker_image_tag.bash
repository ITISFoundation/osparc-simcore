#!/bin/bash
# Usage: build_docker_image_tag
# returns the slugified name of the image tag that shall be used to build test images
# e.g.: current git branch name
# if on travis,
#   if on a branch: returns the name of the travis branch
#   if on a pull request: returns the name of the originating branch
#   always adds -testbuild-latest to the image tag to differentiate from the real master/staging builds

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

default_image_tag="github"

if [ -v GITHUB_ACTIONS ] && [ "$GITHUB_ACTIONS" = "true" ]; then
  # github here
  image_tag="${GITHUB_REF##*/}-$default_image_tag"
else
  # no CI here so let's use the git name directly
  image_tag="$(git rev-parse --abbrev-ref HEAD)-$default_image_tag"
fi

slugified_name="$(exec ci/helpers/slugify_name.bash "$image_tag")"

echo "$slugified_name-testbuild-latest"
