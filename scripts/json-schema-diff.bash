#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

image_name="$(basename $0):latest"

docker build --tag "$image_name" - <<EOF
FROM node:12.18.2
RUN npm install -g json-schema-diff@0.15.0
ENTRYPOINT ["json-schema-diff"]
EOF

#
# To interprete differences is not obvious (for me), SEE https://www.npmjs.com/package/json-schema-diff
#
# TIPS to debug
#  1. create the dst json-schema manually through the pydantic type (see Makefile recipies in models-library)
#  2. resolve both src/dst using json-resolver (see https://github.com/davidkelley/json-dereference-cli
#      callable from ./scripts/json-schema-dereference.bash schema.json schema-deref.json)
#  3. compare both files in vscode
#
input_1="$(basename "$1")"
input_2="$(basename "$2")"

echo "json-schema-diff between source '$input_1' -> destination '$input_2' schemas:"
echo " source:      '$1'"
echo " destination: '$2'"

docker run --rm \
  -v "$(realpath "$1")":/src/"$input_1" \
  -v "$(realpath "$2")":/src/"$input_2" \
  "$image_name" \
  "/src/$input_1" "/src/$input_2"
