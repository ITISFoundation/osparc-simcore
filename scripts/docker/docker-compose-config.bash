#!/bin/bash
# generated using chatgpt
show_info() {
    local message="$1"
    echo -e "\e[37mInfo:\e[0m $message" >&2
}

show_warning() {
  local message="$1"
  echo -e "\e[31mWarning:\e[0m $message" >&2
}

show_error() {
  local message="$1"
  echo -e "\e[31mError:\e[0m $message" >&2
}

if [[ "$#" -eq 0 ]]; then
    show_error "No compose files specified!"
    exit 1
fi

# REFERENCE: https://github.com/docker/compose/issues/9306
# composeV2 defines specifications for docker compose to run
# they are not 100% compatible with what docker stack deploy command expects
# some parts have to be modified




# check if docker-compose V2 is available
if docker compose version --short | grep --quiet "^2\." ; then
  show_info "Running compose V2"
  # V2 does not write the version anymore, so we take it from the first compose file
  first_compose_file="${1}"
  version=$(grep --max-count=1 "^version:" "${first_compose_file}" | cut --delimiter=' ' --fields=2 | tr --delete \"\')
  if [[ -z "$version" ]]; then
    version="3.9"  # Default to 3.9 if version is not found in file
  fi

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
| sed '1 i version: \"${version}\"' \
| sed --regexp-extended 's/cpus: ([0-9\\.]+)/cpus: \"\\1\"/'"

  # Execute the command
  show_info "Executing Docker command: ${docker_command}"
  eval ${docker_command}
else
  show_warning "docker compose V2 is not available, trying V1 instead... please update your docker engine."
  if docker-compose version --short | grep --quiet "^1\." ; then
    show_info "Running compose V1"
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
| sed --regexp-extended 's/cpus: ([0-9\\.]+)/cpus: \"\\1\"/'"
    # Execute the command
    show_info "Executing Docker command: ${docker_command}"
    eval ${docker_command}
  else
    show_error "docker-compose V1 is not available. It is impossible to run this script!"
    exit 1
  fi
fi
