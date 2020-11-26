#
# Targets to pip-compile requirements as a workflow of layered requirements (see https://github.com/jazzband/pip-tools#workflow-for-layered-requirements)
#
# NOTE: More details in docs/python-dependencies.md
#

include ../../../../scripts/requirements.Makefile

packages_input_reqs = $(shell grep "requirements/_base.in" _base.in | awk '{print $$2}')

_base.txt: _base.in $(packages_input_reqs)

_dev.txt: _dev.in _base.txt _test.txt ../../../../requirements/devenv.txt
