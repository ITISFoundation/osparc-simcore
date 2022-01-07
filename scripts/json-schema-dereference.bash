#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

image_name="$(basename $0):latest"

# derefernce json-schemas for easy comparison
# SEE https://github.com/davidkelley/json-dereference-cli
docker build --tag "$image_name" - <<EOF
FROM node:12.18.2
RUN npm install -g json-dereference-cli
ENTRYPOINT ["json-dereference"]
EOF

input=$(basename "$1")
output=$(basename "$2")

echo "json-dereference schema '$input' into a deference schema in '$output'"

docker run --rm \
  -v "$(realpath "$1")":/src/"$input" \
  -v "$(realpath "$2")":/src/"$output" \
  "$image_name" \
  -s "/src/$input" \
  -o "/src/$output"
