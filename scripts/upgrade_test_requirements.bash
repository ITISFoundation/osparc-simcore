#!/bin/bash

# Upgrades simultaneously all _text.in requirements
# so they all use the same version of test tools

for path_to_req_test in $(find ../ -type f -name '_test.txt')
do
  rm --verbose "$path_to_req_test"
  make --directory "$(dirname -- "$path_to_req_test")"
done
