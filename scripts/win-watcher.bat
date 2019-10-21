@echo on
:: WORKAROUND for WINDOWS
::  Run this script to watch changes in files on a windows host.
::  This provides a workaround to overcome a known limitation of docker for windows [1]
::
:: [1] https://docs.docker.com/docker-for-windows/troubleshoot/#/inotify-on-shared-drives-does-not-work
:: [2] http://blog.subjectify.us/miscellaneous/2017/04/24/docker-for-windows-watch-bindings.html
::

:: REQUIRES python 3 installed and in the system path
python --version

:: installs tool in a venv (expects python 3)
python -m venv .venv-win

if %ERRORLEVEL% EQU 0 (
	.venv-win/bin/pip install --upgrade pip
	.venv-win/bin/pip install docker-windows-volume-watcher
	.venv-win/bin/activate.bat
) else (
  :: stinaslls
	python -m pip install --upgrade pip
	python -m pip install docker-windows-volume-watcher
)


:: runs watcher to notify changes to containers named with '*qooxdoo-kit*'
docker-volume-watcher *qooxdoo-kit*
