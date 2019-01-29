#!/bin/sh
source $HOME/.venv/bin/activate


if [[ ${DEBUG} == "1" ]]
then
  echo "INFO: Booting in development mode ..."
  echo "DEBUG: Sidecar running as `id $(whoami)`"
  echo "DEBUG: Sidecar running groups `groups`"

  cd $HOME/services/sidecar
  $PIP install -r requirements/dev.txt
  $PIP list

  cd $HOME
  celery worker --app sidecar.celery:app --concurrency 2 --loglevel=debug
else
  echo "INFO: Booting in production mode ..."
  celery worker --app sidecar.celery:app --concurrency 2 --loglevel=info
fi
