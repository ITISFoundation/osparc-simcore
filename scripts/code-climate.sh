#!/bin/bash
#
# Runs code climate locally on CWD
#
# SEE https://github.com/codeclimate/codeclimate#manual-docker-invocation
#     https://github.com/codeclimate/codeclimate#commands
#
echo Running codeclimate on "$PWD"

TMPDIR=/tmp/cc
mkdir --parent ${TMPDIR}

docker run \
  --interactive --tty --rm \
  --env CODECLIMATE_CODE="$PWD" \
  --volume "$PWD":/code \
  --volume /var/run/docker.sock:/var/run/docker.sock \
  --volume ${TMPDIR}:/tmp/cc \
  codeclimate/codeclimate "$@"


if [ -z "$@" ];then
  echo "----"
  echo "Listing other engines (in dockers)"
  docker images codeclimate/*
fi
