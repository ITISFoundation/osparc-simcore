#!/bin/sh
#

# BOOTING application ---------------------------------------------
echo "Booting in ${MY_BOOT_MODE} mode ..."


if [[ ${MY_BUILD_TARGET} == "development" ]]
then
  echo "  User    :`id $(whoami)`"
  echo "  Workdir :`pwd`"
  echo "  Environment :"
  printenv  | sed 's/=/: /' | sed 's/^/    /' | sort
  #--------------------

  cd services/sidecar
  $MY_PIP install --user -r requirements/dev.txt
  cd /devel

  DEBUG_LEVEL=debug
  #--------------------
  echo "  Python :"
  python --version | sed 's/^/    /'
  which python | sed 's/^/    /'
  echo "  PIP :"
  $MY_PIP list | sed 's/^/    /'


elif [[ ${MY_BUILD_TARGET} == "production" ]]
then
  DEBUG_LEVEL=info
fi


# RUNNING application ----------------------------------------
if [[ ${BOOT_MODE} == "debug" ]]
then
  # TODO: activate pdb??
  DEBUG_LEVEL=debug
  CONCURRENCY=1
else
  CONCURRENCY=2
fi

celery worker --app sidecar.celery:app --concurrency ${CONCURRENCY} --loglevel=${DEBUG_LEVEL}
