#!/bin/sh

if [[ ${DEBUG} == "1" ]]
then
  echo "Booting in development mode ..."
  echo "Installing director service ..."

  pip install -r requirements/dev.txt
  celery worker --app sidecar --concurrency 2 --loglevel=debug
else
  echo "Booting in production mode ..."
  celery worker --app sidecar --concurrency 2 --loglevel=info
fi
