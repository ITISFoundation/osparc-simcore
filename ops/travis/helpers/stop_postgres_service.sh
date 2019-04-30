#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

# shutdown postgres because sometimes is is already up ???
sudo service postgresql stop

# wait for postgresql to shutdown
while nc -z localhost 5432; do
  sleep 1
done
