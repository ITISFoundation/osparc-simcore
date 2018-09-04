#!/bin/sh
source $HOME/.venv/bin/activate


if [[ ${DEBUG} == "1" ]]
then
  echo "INFO: Booting in development mode ..."
  echo "DEBUG: Sidecar running as `id $(whoami)`"
  echo "DEBUG: Sidecar running groups `groups`"

  cd $HOME/services/sidecar
  pip3 install --no-cache-dir -r requirements/dev.txt
  pip3 list

  cd $HOME
  celery worker --app sidecar.celery:app --concurrency 2 --loglevel=debug
else
  echo "INFO: Booting in production mode ..."
  celery worker --app sidecar.celery:app --concurrency 2 --loglevel=info
fi
