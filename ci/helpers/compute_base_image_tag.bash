#!/bin/bash
# Usage: compute_base_image_tag.bash
#
# Echoes the content-hash tag for the shared simcore base images
# (simcore-runtime-base / simcore-build-base).
#
# The tag is derived from the base image Dockerfile content plus
# requirements/UV_VERSION (passed to the build as UV_VERSION build-arg), which
# together fully determine the produced images (exact PYTHON_VERSION and apt
# packages are pinned as literals in the Dockerfile). When neither changes the
# tag is stable, so the base images are rebuilt only when they actually change.

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

repo_root="$(git rev-parse --show-toplevel)"
base_dockerfile="${repo_root}/services/_base_images/Dockerfile"
uv_version_file="${repo_root}/requirements/UV_VERSION"

if [ ! -f "${base_dockerfile}" ]; then
  echo "ERROR: base image Dockerfile not found at ${base_dockerfile}" >&2
  exit 1
fi

if [ ! -f "${uv_version_file}" ]; then
  echo "ERROR: UV_VERSION file not found at ${uv_version_file}" >&2
  exit 1
fi

# hash over both files: the tag must change when either the Dockerfile or the
# uv version changes, so a cached base image can never outlive either
content_hash="$(cat "${base_dockerfile}" "${uv_version_file}" | sha256sum | cut -c1-16)"

echo "base-${content_hash}"
