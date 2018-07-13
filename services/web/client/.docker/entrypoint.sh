#!/bin/bash
#
#
GENERATOR=${QOOXDOO_PATH}/tool/bin/generator.py
BABEL_OUTDIR=class-es5

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
  # Option 2: copy stub in project folder, chdir project folder and execute stub there

  echo Running \'python $GENERATOR "$@"\' ...
  python $GENERATOR "$@"
}

run_babel()
{
  npx babel source/class --no-babelrc --presets es2015 --out-dir $BABEL_OUTDIR
}

run_babel_w_watch()
{
  echo "Watching source/class"
  inotifywait -qrm --event modify --format '%w%f' source/class |
  while read filepath; do
    echo "Changes in ${filepath}"
    run_babel
  done
}

run_gtor_es5()
{
  echo Pre-converting to es5 ...

  # Converts code into es5
  run_babel

  # Change temporarily manifest
  # cp --backup Manifest.json Manifest.json.bak
  sed -i 's/source\/class/$BABEL_OUTDIR/g' Manifest.json

  run_gtor $@

  sed -i 's/$BABEL_OUTDIR/source\/class/g' Manifest.json
  # cp Manifest.json.bak Manifest.json
  # rm Manifest.json.bak
}

run_srv()
{
  run_babel_w_watch &

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
  api | test | test-source )
      run_gtor_es5 $@
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
