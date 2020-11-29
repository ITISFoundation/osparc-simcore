#
# Targets to pip-compile requirements
#
include ../../../scripts/requirements.Makefile

# Add here any extra explicit dependency: e.g. _migration.txt: _base.txt

_base.txt: _base.in _packages.in
_packages.txt: _packages.in _base.in
_test.txt: _base.txt _packages.txt
