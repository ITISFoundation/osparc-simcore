#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

image_name="$(basename $0):latest"

# get a temp directory
tmp_dir=$(mktemp --directory)

# paste there the JS file copied from [https://github.com/oprogramador/json-schema-faker-cli/blob/master/app/generate.js]
# used here because it was linked to an old version of json-schema-faker
cat << EOF > $tmp_dir/generate.js
#!/usr/bin/env node

const jsonfile = require('jsonfile');
const faker = require('json-schema-faker');

function generate(inputPath, outputPath) {
  const inputObject = jsonfile.readFileSync(inputPath);
  const output = faker.generate(inputObject)
  jsonfile.writeFileSync(outputPath, output);
}

generate(process.argv[2], process.argv[3])
EOF

# create a Dockerfile
cat << EOF > $tmp_dir/Dockerfile
FROM node:12.18.2
COPY ./generate.js /app/generate.js
WORKDIR /app
RUN npm install \
  json-schema-faker@0.5.0-rcv.29 \
  jsonfile@6.1.0 && \
  npm list --depth=0

ENTRYPOINT ["node", "/app/generate.js"]
EOF

docker build --tag "$image_name" $tmp_dir

schema="$(basename $1)"
output="$(basename $2)"
docker run \
    --user "$(id --user ${USER})":"$(id --group ${USER})" \
    --rm \
    --volume "$(realpath $1)":/src/"$schema" \
    --volume $(dirname $(realpath "$2")):/output/ \
    "$image_name" "/src/$schema" "/output/$output"
