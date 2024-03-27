#!/usr/bin/env bash
# strict mode
set -o errexit   # abort on nonzero exitstatus
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes
IFS=$'\n\t'

readonly NC='\033[0m' # no color
readonly BLACK='\033[0;30m'
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly ORANGE='\033[0;33m'
readonly YELLOW='\033[1;33m'
readonly WHITE='\033[1;37m'

function error_exit {
    readonly line=$1
    shift 1
    echo
    echo -e "${RED}[ERROR]:$line: ${1:-"Unknown Error"}" 1>&2
    exit 1
}

function log_info {
  echo
  echo -e "${WHITE}[INFO]: ${1:-"Unknown message"}${NC}"
}

function log_warning {
  echo
  echo -e "${YELLOW}[WARNING]: ${1:-"Unknown message"}${NC}"
}
