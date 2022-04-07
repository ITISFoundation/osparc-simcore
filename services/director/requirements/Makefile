#
# Targets to pip-compile requirements
#
include ../../../requirements/base.Makefile

# Add here any extra explicit dependency: e.g. _migration.txt: _base.txt


_test.txt: _base.txt _test.in
	## NOTE: this recipe override has to be removed
	## to execute target upgrades e.g. due to vulnerability of
	## a library.
	@echo INFO: test.txt is frozen. Skipping upgrade.
