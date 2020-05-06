#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

ssh "${SOURCE_HOST}" \
    "docker run --rm -v ${SOURCE_DATA_VOLUME}:/from alpine ash -c 'cd /from ; tar -cf - . '" \
    | \
    docker run --rm -i -v "${TARGET_DATA_VOLUME}":/to alpine ash -c "cd /to ; tar -xpvf - "