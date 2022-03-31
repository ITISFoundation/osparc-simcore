#!/bin/bash

exec docker run --rm --interactive hadolint/hadolint hadolint \
  - < "$@"
