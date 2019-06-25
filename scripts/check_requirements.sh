#!/bin/bash

# lists all python packages used throughout all the repository that are not tied to a specific version

find . \( -name "requirements.txt" -o -name "common.txt" -o -name "devel.txt" -o -name "prod.txt" \) | xargs -I % grep -v "\-r " % | sort |uniq | awk '$0 !~ /==/'


# TODO: check how versions of give package fits throughout the entire repo, e.g. display version of sqlalchemy in all *.txts
#
# TODO: define workflows
#
# - Full upgrade:
#    for each package
#      make clean; make
#      git commit "Upgrades all dependencies to their latest versions in {package}"
# - Particular upgrade
#    for each package
#       pip-compile -P package-name ...
#
# - Remove constraint
#     TODO
#
