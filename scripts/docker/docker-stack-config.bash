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

env_file=".env"
# Parse command line arguments
while getopts ":e:" opt; do
  case $opt in
  e)
    env_file="$OPTARG"
    ;;
  \?)
    show_error "Invalid option: -$OPTARG"
    exit 1
    ;;
  :)
    show_error "Option -$OPTARG requires an argument."
    exit 1
    ;;
  esac
done
shift $((OPTIND - 1))

if [[ "$#" -eq 0 ]]; then
  show_error "No compose files specified!"
  exit 1
fi

# Check if Docker version is greater than or equal to 24.0.9
version_check=$(docker --version | grep --extended-regexp --only-matching '[0-9]+\.[0-9]+\.[0-9]+')
IFS='.' read -r -a version_parts <<<"$version_check"

if [[ "${version_parts[0]}" -gt 24 ]] ||
  { [[ "${version_parts[0]}" -eq 24 ]] && [[ "${version_parts[1]}" -gt 0 ]]; } ||
  { [[ "${version_parts[0]}" -eq 24 ]] && [[ "${version_parts[1]}" -eq 0 ]] && [[ "${version_parts[2]}" -ge 9 ]]; }; then
  show_info "Running Docker version $version_check"
else
  show_error "Docker version 25.0.3 or higher is required."
  exit 1
fi

# shellcheck disable=SC2002
docker_command="\
set -o allexport && \
. ${env_file} && set +o allexport && \
docker stack config"

for compose_file_path in "$@"; do
  docker_command+=" --compose-file ${compose_file_path}"
done
# WE CANNOT DO THIS:
# docker_command+=" --skip-interpolation"
# because docker stack compose will *validate* that e.g. `replicas: ${SIMCORE_SERVICES_POSTGRES_REPLICAS}` is a valid number, which it is not if it is read as a literal string.

# Execute the command
show_info "Executing Docker command: ${docker_command}"
eval "${docker_command}"
