#!/bin/bash

# generated using chatgpt

# check if docker-compose V2 is available
if docker compose version --short | grep --quiet "^2\." ; then
  docker_command="\
  docker \
  --log-level=ERROR \
  compose \
  --env-file .env"

  for compose_file_path in "$@"
  do
    docker_command+=" --file=${compose_file_path}"
  done
  docker_command+="\
  config \
  | sed '/published:/s/\"//g' \
  | sed '/size:/s/\"//g' \
  | sed '1 { /name:.*/d ; }' \
  | sed '1 i\version: \"3.9\"' \
  | sed --regexp-extended 's/cpus: ([0-9\\.]+)/cpus: \"\\1\"/'"

  # Execute the command
  echo "Executing Docker command: ${docker_command}"
  eval ${docker_command}
else
  echo "WARNING: docker compose V2 is not available, trying V1 instead... please update your docker engine."
  if docker-compose version --short | grep --quiet "^1\." ; then
    docker_command="\
docker-compose \
--log-level=ERROR \
--env-file .env"
    for compose_file_path in "$@"
    do
      docker_command+=" --file=${compose_file_path}"
    done
    docker_command+="\
config \
| sed '/published:/s/\"//g' \
| sed '/size:/s/\"//g' \
| sed '1 { /name:.*/d ; }' \
| sed '1 i\version: \"3.9\"' \
| sed --regexp-extended 's/cpus: ([0-9\\.]+)/cpus: \"\\1\"/'"
    # Execute the command
    echo "Executing Docker command: ${docker_command}"
    eval ${docker_command}
  else
    echo "ERROR: docker-compose V1 is not available. It is impossible to run this script!"
    exit 1
  fi
fi
