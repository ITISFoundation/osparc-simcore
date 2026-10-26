#!/bin/bash
#
# Entrypoint of the Renovate container (docker-cmd-file of renovatebot/github-action
# in .github/workflows/chore-renovate.yml). Starts as root to add the system packages
# .github/renovate/resync_lockfiles.py needs, then runs Renovate as the image's
# unprivileged user.
#
set -o errexit
set -o nounset
set -o pipefail

apt-get update --quiet
apt-get install --quiet --yes --no-install-recommends make

exec runuser -u ubuntu renovate
