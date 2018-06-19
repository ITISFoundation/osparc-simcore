@echo on
:: Run this script to watch changes in files on a windows host.
:: This provides a workaround to overcome a known limitation of docker for windows [1]
::
:: REQUIRES python 3 installed and in the system path
::
:: [1] https://docs.docker.com/docker-for-windows/troubleshoot/#/inotify-on-shared-drives-does-not-work
:: [2] http://blog.subjectify.us/miscellaneous/2017/04/24/docker-for-windows-watch-bindings.html
::

python --version

:: installs tool in a venv (expects python 3)
python -m venv .VENV

if %ERRORLEVEL% EQU 0 (
	.VENV/bin/pip install --upgrade pip
	.VENV/bin/pip install docker-windows-volume-watcher	
	:: runs watcher
	.VENV/bin/activate
) else (
	python -m pip install --upgrade pip
	python -m pip install docker-windows-volume-watcher
)

docker-volume-watcher
