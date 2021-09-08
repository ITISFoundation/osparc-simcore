#
# Targets to pip-compile requirements as a workflow of layered requirements (see https://github.com/jazzband/pip-tools#workflow-for-layered-requirements)
#
# NOTE: More details in docs/python-dependencies.md
#

include ../../../../requirements/base.Makefile

# TODO: Check these dependencies packages_input_reqs = $(shell grep "requirements/_base.in" _base.in | awk '{print $$2}')
# _base.txt: _base.in $(packages_input_reqs)

_base.txt: _base.in _packages.in
_packages.txt: _packages.in _base.in
_test.txt: _base.txt _packages.txt
