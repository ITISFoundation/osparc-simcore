#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

image_name="$(basename $0):latest"


docker build --tag "$image_name" -<<EOF
FROM node:12.18.2
RUN npm install -g json-schema-diff
ENTRYPOINT ["json-schema-diff"]
EOF

input_1="$(basename $1)"
input_2="$(basename $2)"
docker run --rm -v "$(realpath $1)":/src/"$input_1" -v "$(realpath $input_2)":/src/"$input_2" "$image_name" "/src/$input_1" "/src/$input_2"
