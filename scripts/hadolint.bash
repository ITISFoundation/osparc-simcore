#!/bin/bash

docker run --rm -i hadolint/hadolint hadolint \
  - < "$@"
