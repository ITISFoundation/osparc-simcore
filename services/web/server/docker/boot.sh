#!/bin/sh
echo "Activating python virtual env..."
source $HOME/.venv/bin/activate

if [[ ${DEBUG} == "1" ]]
then
  echo "Booting in development mode ..."
  echo "DEBUG: User    :`id $(whoami)`"
  echo "DEBUG: Workdir :`pwd`"

  cd $HOME/services/web/server
  pip install -r requirements/dev.txt
  pip list

  cd $HOME/
  simcore-service-webserver --config server-docker-dev.yaml
else
  echo "Booting in production mode ..."
  simcore-service-webserver --config server-docker-prod.yaml
fi
