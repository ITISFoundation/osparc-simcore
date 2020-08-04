#!/bin/bash
# Usage: build_docker_image_tag
# returns the slugified name of the image tag that shall be used to build test images
# e.g.: current git branch name
# if on travis,
#   if on a branch: returns the name of the travis branch
#   if on a pull request: returns the name of the originating branch
#   always adds -testbuild-latest to the image tag to differentiate from the real master/staging builds

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

default_image_tag="github"

if [ -v TRAVIS ] && [ "$TRAVIS" = "true" ]; then
  # travis here
  if [ "$TRAVIS_PULL_REQUEST" = "false" ]; then
    image_tag="${TRAVIS_BRANCH}-travis"
  else
    # this is a pull request, let's use the name of the originating branch instead of a boring master
    image_tag="${TRAVIS_PULL_REQUEST_BRANCH}-travis"
  fi
elif [ -v GITHUB_ACTIONS ] && [ "$GITHUB_ACTIONS" = "true" ]; then
  # github here
  image_tag="${GITHUB_REF##*/}-github"
else
  # no CI here so let's use the git name directly
  image_tag="$(git rev-parse --abbrev-ref HEAD)-$default_image_tag"
fi

slugified_name="$(exec ci/helpers/slugify_name.bash "$image_tag")"

echo "$slugified_name-testbuild-latest"
