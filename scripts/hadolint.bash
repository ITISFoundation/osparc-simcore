#!/bin/bash
#
# SEE https://github.com/michaellzc/vscode-hadolint/issues/44#issuecomment-808756114

exec docker run --rm --interactive hadolint/hadolint hadolint \
  --no-color \
  - <"$@"
