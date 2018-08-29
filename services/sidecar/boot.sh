#!/bin/sh
source $HOME/.venv/bin/activate

echo "This is running as `id $(whoami)`"

if [[ ${DEBUG} == "1" ]]
then
  echo "Booting in development mode ..."
  echo "Installing director service ..."

  pip3 install --no-cache-dir -r requirements/dev.txt
  celery worker --app sidecar.celery:app --concurrency 2 --loglevel=debug
else
  echo "Booting in production mode ..."
  celery worker --app sidecar.celery:app --concurrency 2 --loglevel=info
fi
