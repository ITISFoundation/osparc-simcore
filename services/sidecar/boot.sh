#!/bin/sh
source $HOME/.venv/bin/activate

echo "INFO: Sidecar running as `id $(whoami)`"

if [[ ${DEBUG} == "1" ]]
then
  echo "INFO: Booting in development mode ..."
  echo "INFO: Installing director service ..."

  pip3 install --no-cache-dir -r requirements/dev.txt
  celery worker --app sidecar.celery:app --concurrency 2 --loglevel=debug
else
  echo "INFO: Booting in production mode ..."
  celery worker --app sidecar.celery:app --concurrency 2 --loglevel=info
fi
