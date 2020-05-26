#!/bin/bash
#
# Static analysis tool for scripts
# - https://www.shellcheck.net
# - VS extension: https://github.com/timonwong/vscode-shellcheck
#

exec docker run --rm --interactive --volume "$PWD:/mnt:ro" koalaman/shellcheck:v0.7.0 "$@"
