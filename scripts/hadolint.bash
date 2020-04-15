#!/bin/bash
# dockerfile linter tool
# - https://github.com/hadolint/hadolint
exec docker run --rm --interactive hadolint/hadolint < "$@"