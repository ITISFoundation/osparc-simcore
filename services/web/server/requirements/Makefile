#
# Targets to pip-compile requirements
#
include ../../../../scripts/requirements.Makefile

# Add here any extra explicit dependency: e.g. _migration.txt: _base.txt

packages_input_reqs = $(shell grep "requirements/_base.in" _base.in | awk '{print $$2}')
$(info in-repo deps: $(packages_input_reqs))

_base.txt: _base.in $(packages_input_reqs)
