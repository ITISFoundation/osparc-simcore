#!/bin/bash
#
#
GENERATOR=${QOOXDOO_PATH}/tool/bin/generator.py

version()
{
  echo qooxdoo-compiler: $(qx --help 2>&1 >/dev/null | grep  Versions | cut -c28-)
  echo qooxdoo-sdk     : $(cat ${QOOXDOO_PATH}/version.txt)
  echo http-server     : $(npm -g info http-server version)
}

run_qx()
{
  echo "Booting qooxdoo ..."

  source $(dirname $0)/.env
  echo "- script dir: " ${SCRIPT_DIR}
  echo "- client dir: " ${CLIENT_DIR}
  echo "- fonts dir : " ${FONTS_DIR}

  # TODO: add argument to avoid installing contributions
  ${SCRIPT_DIR}/install-contrib.sh

  echo Running \'qx "$@"\' ...
  qx "$@"

  # TODO: if create, then copy config.json in the output as well
}


run_gtor()
{
  # Option 1: chdir project folder and execute  $GENERATOR <--
  echo Running \'python $GENERATOR "$@"\' ...
  python $GENERATOR "$@"

  # Option 2: copy stup in project folder, chdir project folder and execute stub there
}


run_srv()
{
  # Mainly to serve api and test applicaitons.
  # test-source needs of qooxdoo-sdk and for that reason it is
  # convenient to use the qx-devel image since it already contains
  # the proper sdk at the right location
  echo Running \'http-server "$@"\' ...
  http-server "$@"
}


case $1 in
  --version )
      version
      ;;
  test | test-source| api )
      run_gtor $@
      ;;
  gtor )
      run_gtor ${@:2}
      ;;
  srv )
      run_srv ${@:2}
      ;;
  * )
      run_qx $@
      ;;
esac
