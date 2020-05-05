#!/bin/bash
#
# Creates a graph out of a docker-compose.yml (passed as a first argument)
#
# See https://github.com/pmsipilot/docker-compose-viz
#

set -euo pipefail
IFS=$'\n\t'

USERID=$(stat --format=%u "$PWD")
GROUPID=$(stat --format=%g "$PWD")

exec docker run -it \
  --name dcv \
  --rm \
  --user "$USERID:$GROUPID" \
  --volume "$PWD:/input" \
  pmsipilot/docker-compose-viz render \
  --output-format=image \
  --output-file="$1.png" \
  --horizontal  \
  --no-ports \
  --verbose \
  --force "$1"


#
# Usage:
#   render [options] [--] [<input-file>]
#
# Arguments:
#   input-file                         Path to a docker compose file [default: "/input/docker-compose.yml"]
#
# Options:
#       --override=OVERRIDE            Tag of the override file to use [default: "override"]
#   -o, --output-file=OUTPUT-FILE      Path to a output file (Only for "dot" and "image" output format)
#   -m, --output-format=OUTPUT-FORMAT  Output format (one of: "dot", "image", "display") [default: "display"]
#       --only=ONLY                    Display a graph only for a given services (multiple values allowed)
#   -f, --force                        Overwrites output file if it already exists
#       --no-volumes                   Do not display volumes
#       --no-networks                  Do not display networks
#       --no-ports                     Do not display ports
#   -r, --horizontal                   Display a horizontal graph
#       --ignore-override              Ignore override file
#       --background=BACKGROUND        Set the graph background color [default: "#ffffff"]
#   -h, --help                         Display this help message
#   -q, --quiet                        Do not output any message
#   -V, --version                      Display this application version
#       --ansi                         Force ANSI output
#       --no-ansi                      Disable ANSI output
#   -n, --no-interaction               Do not ask any interactive question
#   -v|vv|vvv, --verbose               Increase the verbosity of messages: 1 for normal output, 2 for more verbose output and 3 for debug
#
