#!/bin/sh
echo "activating python virtual env..."
source $HOME/.venv/bin/activate

if [[ ${DEBUG} == "1" ]]
then
  echo "Booting in development mode ..."
  pip install -r requirements/dev.txt
  service-web-server --config server-docker-dev.yaml
else
  echo "Booting in production mode ..."
  service-web-server --config server-docker-prod.yaml
fi
