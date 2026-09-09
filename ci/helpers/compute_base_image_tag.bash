#!/bin/bash
# Usage: compute_base_image_tag.bash
#
# Echoes the content-hash tag for the shared simcore base images
# (simcore-runtime-base / simcore-build-base).
#
# The tag is derived from the base image Dockerfile content, which fully
# determines the produced images (it pins PYTHON_VERSION, UV_VERSION and the
# installed apt packages). When the base Dockerfile is unchanged the tag is
# stable, so the base images are rebuilt only when they actually change.

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

repo_root="$(git rev-parse --show-toplevel)"
base_dockerfile="${repo_root}/services/_base_images/Dockerfile"

if [ ! -f "${base_dockerfile}" ]; then
  echo "ERROR: base image Dockerfile not found at ${base_dockerfile}" >&2
  exit 1
fi

content_hash="$(sha256sum "${base_dockerfile}" | cut -c1-16)"

echo "base-${content_hash}"
