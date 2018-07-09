#!/bin/bash

# lists all python packages used throughout all the repository that are not tied to a specific version

find . \( -name "requirements.txt" -o -name "common.txt" -o -name "devel.txt" -o -name "prod.txt" \) | xargs -I % grep -v "\-r " % | sort |uniq | awk '$0 !~ /==/'
