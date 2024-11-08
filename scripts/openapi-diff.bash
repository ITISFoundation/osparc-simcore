#!/bin/bash
#
#
# - https://github.com/OpenAPITools/openapi-diff
#

# NOTE: do not forget that the target /specs
#
#
#

exec docker run \
  --interactive \
  --rm \
  --volume="/etc/group:/etc/group:ro" \
  --volume="/etc/passwd:/etc/passwd:ro" \
  --user="$(id --user "$USER")":"$(id --group "$USER")" \
  --volume "$(pwd):/specs" \
  tufin/oasdiff:latest \
  "$@"
