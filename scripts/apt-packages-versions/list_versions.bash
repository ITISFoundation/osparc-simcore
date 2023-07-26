#!/bin/bash

# apt package names
PACKAGES_NAMES_LIST=(
  "docker-ce-cli"
  "docker-compose-plugin"
)

# update apt cahce
apt-get update

# dispaly verson for each package
for pckage_name in "${PACKAGES_NAMES_LIST[@]}"; do
  echo -e "\nListing versions for pckage: '${pckage_name}'\n"
  apt-cache madison "${pckage_name}" | awk '{ print $3 }'
done
